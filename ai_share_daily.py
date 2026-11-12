#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Доля ИИ за вчера по отделам, отдельно оформление и ведение -> Telegram."""
import json, os, re, sys, io, time, urllib.request, urllib.error, collections
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = {}
try:
    for ln in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            ENV[k.strip()] = v.strip().strip('"').strip("'")
except OSError:
    pass


def cfg(name, default=None):
    return os.environ.get(name) or ENV.get(name) or default


CRM_URL = cfg("EASYMO_API_URL",
              "https://crm.easy-mo.ru/external/v1/customers/dialogs/export")
CRM_TOKEN = cfg("EASYMO_API_TOKEN")
TG_TOKEN = cfg("TELEGRAM_BOT_TOKEN")
# Отчёт уходит в группу РОПов; если её id не задан — в личный чат из TELEGRAM_CHAT_ID.
TG_CHAT = cfg("AI_TG_CHAT_ID") or cfg("TELEGRAM_CHAT_ID")
MSK = timezone(timedelta(hours=3))

# Сколько дней назад смотреть создание клиента, чтобы поймать вчерашние касания.
LOOKBACK_DAYS = int(cfg("AI_LOOKBACK_DAYS", "30"))
WORKERS = int(cfg("AI_WORKERS", "2"))

DEPARTMENTS = [
    ("КНИГИ", 122, "Алина и Регина"),
    ("СТАТУЭТКИ", 126, "Зарина"),
    ("СТАТУЭТКИ", 128, "Диана и София"),
    ("СТАТУЭТКИ", 127, "Ангелина"),
    ("ПОРТРЕТЫ", 10, "Настя и Руслан"),
]

# Бот определяется по имени отправителя, а не только по sender_type:
# цепочки бота уходят под учёткой CRM и помечаются там как manager.
BOT_NAME = re.compile(
    r"артур\s*(бот|ии)"          # Артур Бот, Артур ИИ
    r"|геннадий\s*горин"         # Геннадий Горин
    r"|^\s*бот\s*$"              # просто «Бот»
    r"|алина\s*роп\s*книги",     # роповская учётка книг — через неё идут дожимы
    re.I)
BOT_TYPES = ("bot", "ai", "arthur_ai")
# Где кончается оформление и начинается ведение — у каждого направления своя точка.
# КНИГИ: когда начинают брать данные на доставку.
# СТАТУЭТКИ и ПОРТРЕТЫ: когда клиенту ушёл эскиз (дальше идёт окрас/акрил — это ведение).
_ESKIZ = re.compile(
    r"отправля\w+\s+готов\w+\s+эскиз|готов\w+\s+эскиз\s+с\s+проработанн\w+\s+образом|"
    r"эскиз\s+с\s+проработанным", re.I)
HANDOVER = {
    # Книги: когда начинают брать данные на доставку.
    "КНИГИ": re.compile(r"для\s+оформления\s+доставки\s+заказанн\w+\s+книги|"
                        r"для\s+оформления\s+доставки\s+заказа", re.I),
    # Статуэтки и портреты: когда клиенту ушёл готовый эскиз (дальше окрас, акрил).
    "СТАТУЭТКИ": _ESKIZ,
    "ПОРТРЕТЫ": _ESKIZ,
}


def parse_dt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK)
    except Exception:
        return None


def role(m):
    st = m.get("sender_type")
    if st == "client":
        return "client"
    if st in BOT_TYPES:
        return "bot"
    if BOT_NAME.search(str(m.get("sender_name") or "")):
        return "bot"
    return "manager"


def crm_post(payload, retries=6):
    body = json.dumps(payload).encode("utf-8")
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            CRM_URL, data=body, method="POST",
            headers={"Authorization": "Bearer " + CRM_TOKEN,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:600]
            last = "HTTP %s: %s" % (e.code, detail)
            if e.code == 422:           # слишком большая выборка за день
                return {"dialogs": [], "pagination": {}, "_error": last}
            if e.code == 429:
                time.sleep(min(20 * (attempt + 1), 90))
                continue
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        time.sleep(5 * (attempt + 1))
    return {"dialogs": [], "pagination": {}, "_error": last}


def tg_send(text):
    if os.environ.get("AI_DRY_RUN"):
        print(text)
        return
    for start in range(0, len(text), 3800):
        data = json.dumps({"chat_id": int(TG_CHAT),
                           "text": text[start:start + 3800],
                           "parse_mode": "HTML",
                           "disable_web_page_preview": True}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % TG_TOKEN,
            data=data, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            # Запоминаем id сообщения: без него отправленное уже не удалить.
            try:
                res = json.loads(r.read().decode("utf-8"))
                mid = (res.get("result") or {}).get("message_id")
                if mid:
                    with open(os.path.join(HERE, "sent_messages.log"), "a",
                              encoding="utf-8") as f:
                        f.write("%s\tchat=%s\tmessage_id=%s\n"
                                % (datetime.now(MSK).isoformat(), TG_CHAT, mid))
            except Exception:
                pass


def split_point(dlg, group):
    """Переход оформление -> ведение по своей фразе; запасной вариант — создание заказа."""
    rx = HANDOVER.get(group)
    best = None
    if rx is not None:
        for m in dlg.get("messages") or []:
            if role(m) == "client":
                continue
            if rx.search(str(m.get("text") or "")):
                t = parse_dt(m.get("sent_at") or "")
                if t and (best is None or t < best):
                    best = t
    if best:
        return best
    for o in dlg.get("orders") or []:
        t = parse_dt(o.get("created_at") or "")
        if t and (best is None or t < best):
            best = t
    return best


def scan(dlg, day, rows, group):
    """Собирает вчерашние сообщения диалога в общий список для последующего разбора."""
    cut = split_point(dlg, group)
    cid = dlg.get("customer_id")
    msgs = []
    for m in dlg.get("messages") or []:
        t = parse_dt(m.get("sent_at") or "")
        if not t:
            continue
        msgs.append((t, m))
    msgs.sort(key=lambda x: x[0])
    last_client = None
    for t, m in msgs:
        r = role(m)
        if t.date() != day:
            if r == "client":
                last_client = t
            continue
        rows.append({
            "cid": cid,
            "t": t,
            "role": r,
            "stage": "ved" if (cut and t > cut) else "ofo",
            "name": str(m.get("sender_name") or "").strip(),
            "text": " ".join(str(m.get("text") or "").split()),
            # сколько часов назад клиент писал в последний раз перед этим сообщением
            "since_client": (None if last_client is None
                             else (t - last_client).total_seconds() / 3600.0),
        })
        if r == "client":
            last_client = t


# Веерная отправка: один и тот же текст ушёл многим клиентам, и клиент перед этим молчал.
BLAST_MIN_COPIES = int(cfg("AI_BLAST_COPIES", "15"))
BLAST_SILENT_HOURS = float(cfg("AI_BLAST_SILENT_HOURS", "12"))


def summarize(rows):
    """Считает долю ИИ и нагрузку, отделив веерные отправки от живой переписки."""
    copies = collections.Counter()
    for r in rows:
        if r["role"] == "bot" and len(r["text"]) > 25:
            copies[r["text"][:120]] += 1

    def is_blast(r):
        if r["role"] != "bot" or len(r["text"]) <= 25:
            return False
        if copies[r["text"][:120]] < BLAST_MIN_COPIES:
            return False
        sc = r["since_client"]
        return sc is None or sc >= BLAST_SILENT_HOURS

    acc = collections.Counter()
    for k in ("dialogs", "dlg_ofo", "dlg_ved", "mgr_ofo", "mgr_ved", "blast_dlg"):
        acc[k] = set()
    live_by_cid = collections.defaultdict(set)   # cid -> этапы, где был живой контакт
    for r in rows:
        if is_blast(r):
            acc["blast_msg"] += 1
            acc["blast_dlg"].add(r["cid"])
            continue
        acc["dialogs"].add(r["cid"])
        if r["role"] == "client":
            live_by_cid[r["cid"]].add(r["stage"])
            continue
        acc[r["stage"] + ("_bot" if r["role"] == "bot" else "_man")] += 1
        acc["dlg_" + r["stage"]].add(r["cid"])
        if r["role"] == "manager" and r["name"]:
            acc["mgr_" + r["stage"]].add(r["name"])
        live_by_cid[r["cid"]].add(r["stage"])
    # лид = диалог, где за день был живой обмен, а не только веерная отправка
    acc["live_ofo"] = {c for c, s in live_by_cid.items() if "ofo" in s}
    acc["live_ved"] = {c for c, s in live_by_cid.items() if "ved" in s}
    return acc


def collect(dep_id, day, group):
    rows = []
    lead_total = 0
    days = [(day - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(LOOKBACK_DAYS)]
    pages = []
    for ds in days:
        first = crm_post({"date_from": ds, "date_to": ds,
                          "department_ids": [dep_id], "page": 1, "per_page": 100})
        # Лиды дня = total за день создания клиента: та же цифра, что на панели CRM.
        if ds == day.strftime("%Y-%m-%d"):
            lead_total = (first.get("pagination") or {}).get("total") or 0
        for d in first.get("dialogs", []):
            scan(d, day, rows, group)
        lp = (first.get("pagination") or {}).get("last_page") or 1
        pages += [(ds, p) for p in range(2, lp + 1)]

    def work(t):
        ds, p = t
        r = crm_post({"date_from": ds, "date_to": ds,
                      "department_ids": [dep_id], "page": p, "per_page": 100})
        return r.get("dialogs", [])

    if pages:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for chunk in pool.map(work, pages):
                for d in chunk:
                    scan(d, day, rows, group)
    acc = summarize(rows)
    acc["leads"] = lead_total
    return acc


def pct(b, m):
    tot = b + m
    return ("%.0f%%" % (100.0 * b / tot)) if tot else "—"


def per_mgr(count, managers):
    """Среднее на одного менеджера: нагрузка за день / людей, работавших на этапе."""
    n = len(managers)
    if not n or not count:
        return "—"
    return "%.0f" % (float(count) / n)


def main():
    day = datetime.now(MSK).date() - timedelta(days=1)
    if os.environ.get("AI_DAY"):
        day = datetime.strptime(os.environ["AI_DAY"], "%Y-%m-%d").date()
    # Метка «за этот день уже отправлено»: позволяет планировщику
    # повторять попытки, не рискуя двойным сообщением в группе.
    flag = os.path.join(HERE, "sent_%s.flag" % day.strftime("%Y-%m-%d"))
    if os.path.exists(flag) and not os.environ.get("AI_FORCE"):
        print("отчёт за %s уже отправлен — выходим" % day, flush=True)
        return
    if os.environ.get("AI_DEPARTMENTS"):
        want = {int(x) for x in os.environ["AI_DEPARTMENTS"].split(",")}
        deps = [d for d in DEPARTMENTS if d[1] in want]
    else:
        deps = DEPARTMENTS

    months = ("января февраля марта апреля мая июня июля августа сентября "
              "октября ноября декабря").split()
    lines = ["<b>Доля ИИ за %d %s</b>" % (day.day, months[day.month - 1]), ""]
    tot = collections.Counter()
    for k in ("live_ofo", "live_ved", "mgr_ofo", "mgr_ved", "blast_dlg"):
        tot[k] = set()
    last_group = None
    for group, dep_id, name in deps:
        acc = collect(dep_id, day, group)
        for k in ("ofo_bot", "ofo_man", "ved_bot", "ved_man", "blast_msg", "leads"):
            tot[k] += acc[k]
        for k in ("live_ofo", "live_ved", "mgr_ofo", "mgr_ved", "blast_dlg"):
            tot[k] |= acc[k]
        if group != last_group:
            if last_group is not None:
                lines.append("")
            lines.append("<b>%s</b>" % group)
            last_group = group
        if len(acc["dialogs"]) == 0:
            lines.append("%s — нет диалогов" % name)
            continue
        lines.append("<b>%s</b>" % name)
        lines.append("   оформление — ИИ %s, лидов на менеджера %s"
                     % (pct(acc["ofo_bot"], acc["ofo_man"]),
                        per_mgr(acc["leads"], acc["mgr_ofo"])))
        lines.append("   ведение — ИИ %s, заказов на менеджера %s"
                     % (pct(acc["ved_bot"], acc["ved_man"]),
                        per_mgr(len(acc["live_ved"]), acc["mgr_ved"])))
        print("  готов %s" % name, flush=True)
    lines.append("")
    lines.append("<b>Итого</b>")
    lines.append("   оформление — ИИ %s, лидов на менеджера %s"
                 % (pct(tot["ofo_bot"], tot["ofo_man"]),
                    per_mgr(tot["leads"], tot["mgr_ofo"])))
    lines.append("   ведение — ИИ %s, заказов на менеджера %s"
                 % (pct(tot["ved_bot"], tot["ved_man"]),
                    per_mgr(len(tot["live_ved"]), tot["mgr_ved"])))
    lines.append("   лидов всего за день: %d" % tot["leads"])
    lines.append("")
    lines.append("<i>Отдельно рассылки: %d сообщений в %d диалогов — в расчёт не вошли.</i>"
                 % (tot["blast_msg"], len(tot["blast_dlg"])))
    text = "\n".join(lines)
    # Сначала сохраняем — чтобы результат не пропал, если отправка не пройдёт.
    try:
        out = os.path.join(HERE, "report_%s.txt" % day.strftime("%Y-%m-%d"))
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        with open(os.path.join(HERE, "last_report.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        print("отчёт сохранён:", out, flush=True)
    except OSError as e:
        print("не удалось сохранить отчёт:", e, flush=True)
    tg_send(text)
    print("отправлено в телеграм", flush=True)
    try:
        with open(flag, "w", encoding="utf-8") as f:
            f.write(datetime.now(MSK).isoformat())
    except OSError:
        pass


if __name__ == "__main__":
    main()
