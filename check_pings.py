#!/usr/bin/env python3
"""Easy-Mo: payment request without a follow-up ping within 10 minutes -> Telegram."""
import json, os, re, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

CRM_URL = "https://crm.easy-mo.ru/external/v1/customers/dialogs/export"
# Secrets come from the environment when available (GitHub Actions), else local defaults.
CRM_TOKEN = os.environ.get("CRM_TOKEN") or "EQWbTNEJUxWHXB13W$402QVLvf8@$#Rb"
DEPARTMENTS = [int(x) for x in
               (os.environ.get("DEPARTMENT_IDS") or "122").split(",") if x.strip()]
TG_TOKEN = os.environ.get("TG_TOKEN") or ""
TG_CHAT_ID = int(os.environ.get("TG_CHAT_ID") or 0)

PING_MINUTES = 10
LOOKBACK_DAYS = 7
WORKERS = 2
OUR = ("manager", "arthur_ai", "bot")
MSK = timezone(timedelta(hours=3))

PAY_LINK = re.compile(r"pay=\d+")
CARD = re.compile(r"\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}")

_lock = threading.Lock()


def parse_dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK)


def is_payment_request(m):
    if m.get("sender_type") not in OUR:
        return False
    t = m.get("text") or ""
    return bool(PAY_LINK.search(t) or CARD.search(t))


def crm_post(payload, retries=6):
    """POST with backoff. 429 is expected under load — back off hard and retry."""
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
            detail = e.read().decode("utf-8", "replace")[:200]
            last = "HTTP %s: %s" % (e.code, detail)
            if e.code == 422:
                raise RuntimeError("422 dialogs_limit_exceeded for %s: %s"
                                   % (payload["date_from"], detail))
            if e.code == 429:
                time.sleep(min(20 * (attempt + 1), 90))
                continue
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("CRM request failed after %d tries (%s): %s"
                       % (retries, payload["date_from"], last))


def tg_send(text):
    if os.environ.get("PING_DRY_RUN"):
        print("[dry-run] telegram message suppressed")
        return
    for start in range(0, len(text), 3800):
        data = json.dumps({"chat_id": TG_CHAT_ID, "text": text[start:start + 3800],
                           "disable_web_page_preview": True}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % TG_TOKEN,
            data=data, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()


def scan_dialog(dlg, hour_start, hour_end):
    """Return (active, events) for one dialog."""
    msgs = sorted(dlg.get("messages") or [], key=lambda m: m.get("sent_at") or "")
    active = False
    events = []
    for m in msgs:
        try:
            t = parse_dt(m["sent_at"])
        except Exception:
            continue
        if hour_start <= t < hour_end:
            active = True
            break

    for idx, m in enumerate(msgs):
        if not is_payment_request(m):
            continue
        try:
            T = parse_dt(m["sent_at"])
        except Exception:
            continue
        if not (hour_start <= T < hour_end):
            continue

        deadline = T + timedelta(minutes=PING_MINUTES)
        our_ping = client_reply = next_our = None
        for n in msgs[idx + 1:]:
            try:
                tn = parse_dt(n["sent_at"])
            except Exception:
                continue
            if tn <= T:
                continue
            if next_our is None and n.get("sender_type") in OUR:
                next_our = tn
            if tn > deadline:
                if next_our is not None:
                    break
                continue
            if n.get("sender_type") == "client":
                client_reply = client_reply or n
            elif n.get("sender_type") in OUR:
                our_ping = our_ping or n

        order_after = None
        for o in (dlg.get("orders") or []):
            try:
                ot = parse_dt(o["created_at"])
            except Exception:
                continue
            if ot >= T:
                delta = int((ot - T).total_seconds() // 60)
                if order_after is None or delta < order_after:
                    order_after = delta

        events.append({
            "customer_id": dlg.get("customer_id"),
            "message_id": m.get("message_id"),
            "at": T,
            "req_by": m.get("sender_name") or m.get("sender_type"),
            "manager": (dlg.get("manager") or {}).get("name"),
            "text": (m.get("text") or "").strip(),
            "pinged": our_ping is not None,
            "client_replied": client_reply is not None,
            "silence_min": (int((next_our - T).total_seconds() // 60)
                            if next_our else None),
            "order_after_min": order_after,
        })
    return active, events


def main():
    now = datetime.now(MSK)
    hour_end = now.replace(minute=0, second=0, microsecond=0)
    hour_start = hour_end - timedelta(hours=1)
    if os.environ.get("PING_WINDOW_START"):
        hour_start = parse_dt(os.environ["PING_WINDOW_START"])
        hour_end = parse_dt(os.environ["PING_WINDOW_END"])

    days = sorted({(hour_start.date() - timedelta(days=i)) for i in range(LOOKBACK_DAYS)}
                  | {now.date()}, reverse=True)

    state = {"active": set(), "events": {}, "pages": 0}

    def absorb(resp):
        act, evs = set(), {}
        for dlg in resp.get("dialogs", []):
            a, e = scan_dialog(dlg, hour_start, hour_end)
            if a:
                act.add(dlg.get("customer_id"))
            for ev in e:
                evs[(ev["customer_id"], ev["message_id"])] = ev
        with _lock:
            state["active"] |= act
            state["events"].update(evs)
            state["pages"] += 1

    tasks = []
    for day in days:
        ds = day.strftime("%Y-%m-%d")
        first = crm_post({"date_from": ds, "date_to": ds, "department_ids": DEPARTMENTS,
                          "page": 1, "per_page": 100})
        absorb(first)
        last_page = first.get("pagination", {}).get("last_page", 1) or 1
        for p in range(2, last_page + 1):
            tasks.append((ds, p))

    def work(t):
        ds, p = t
        absorb(crm_post({"date_from": ds, "date_to": ds, "department_ids": DEPARTMENTS,
                         "page": p, "per_page": 100}))

    if tasks:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(work, tasks))

    events = list(state["events"].values())
    flagged = sorted([e for e in events if not e["pinged"] and not e["client_replied"]],
                     key=lambda e: e["at"])

    header = ("%s–%s МСК · отдел 122\n"
              "Диалогов активно: %d\n"
              "Запросов оплаты: %d\n"
              "Без пинга за 10 мин: %d"
              % (hour_start.strftime("%d.%m %H:%M"), hour_end.strftime("%H:%M"),
                 len(state["active"]), len(events), len(flagged)))

    if not flagged:
        print(header)
        print("pages_fetched=%d ; nothing to report" % state["pages"])
        if os.environ.get("PING_FORCE_SEND"):
            tg_send(header + "\n\nВсё чисто — пропущенных пингов нет.")
            print("forced heartbeat sent")
        return

    lines = [header, ""]
    for e in flagged:
        quote = " ".join(e["text"].split())
        if len(quote) > 220:
            quote = quote[:220] + "..."
        silence = ("ответа так и не было" if e["silence_min"] is None
                   else "молчание %d мин" % e["silence_min"])
        extra = ("" if e["order_after_min"] is None
                 else " · заказ появился через %d мин" % e["order_after_min"])
        lines.append("customer_id %s — нет пинга после запроса оплаты (%s, %s, %s)%s"
                     % (e["customer_id"], e["at"].strftime("%H:%M"),
                        e["req_by"], silence, extra))
        if e["manager"]:
            lines.append("   менеджер: %s" % e["manager"])
        lines.append("   «%s»" % quote)
        lines.append("")

    msg = "\n".join(lines)
    tg_send(msg)
    print(msg)
    print("pages_fetched=%d ; sent to telegram" % state["pages"])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err = "⚠ Агент проверки пингов упал: %s: %s" % (type(e).__name__, e)
        print(err, file=sys.stderr)
        try:
            tg_send(err)
        except Exception:
            pass
        sys.exit(1)
