# -*- coding: utf-8 -*-
"""Оформление по всем отделам, две когорты, по правилам method.py.

Когорта 1 — заказы, переведённые на ведение в DAY_H, клиенты пришли с AI_SINCE.
            Переписка берётся из выгрузок get_dialogs по списку клиентов.
Когорта 2 — все лиды, пришедшие в DAY_L. Берётся из кэша диалогов.

python -I itogi_otdely.py 2026-11-11 2026-11-10
"""
import collections, glob, gzip, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import fetch_cache as F
import method as M

RESULTS = (r"C:\Users\Менеджер\.claude\projects\C--Users---------"
           r"\f65b89dc-e878-4160-91e0-e0dbfc0a12d0\tool-results")
f = lambda x: format(int(round(x)), ",d").replace(",", " ")

DAY_H = sys.argv[1] if len(sys.argv) > 1 else "2026-11-11"
DAY_L = sys.argv[2] if len(sys.argv) > 2 else "2026-11-10"
DEPS = [(122, "Фотокниги Алина и Регина"), (126, "Статуэтки Зарина"),
        (128, "Статуэтки Диана и София"), (127, "Статуэтки Ангелина"),
        (10, "Портреты Настя и Руслан")]

CUT_H = datetime.combine(datetime.strptime(DAY_H, "%Y-%m-%d").date(),
                         datetime.max.time()).replace(tzinfo=A.MSK)

# --- всё, что выгрузили инструментом по спискам клиентов ---
pool = {}
for p in glob.glob(os.path.join(RESULTS, "*get_dialogs*.txt")):
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for c in (d.get("data") or []):
        pool[c["customer_id"]] = c


def tally(msgs, cut, time_field):
    ai = man = 0
    for m in msgs:
        raw = str(m.get(time_field) or m.get("sent_at") or m.get("created_at") or "")
        t = A.parse_dt(raw[:19].replace("T", " "))
        if not t or (cut and t > cut):
            continue
        r = M.who(m)
        if r == "ai": ai += 1
        elif r == "manager": man += 1
    return ai, man


print("ОФОРМЛЕНИЕ. Доля ИИ = сообщения ИИ / (ИИ + менеджеры).")
print("ИИ — Артур и Геннадий по sender_type. Роповские учётки не считаются.\n")

print("=" * 86)
print("КОГОРТА 1. Заказы, перешедшие на ведение %s. Клиент пришёл с %s"
      % (DAY_H, M.AI_SINCE))
print("=" * 86)
print("%-26s %8s %8s %8s %8s %9s %9s"
      % ("отдел", "заказов", "с авг.", "ИИ", "менедж.", "доля ИИ", "на клиента"))
print("-" * 86)
tot = collections.Counter()
rows1 = {}
for dep, name in DEPS:
    path = os.path.join(HERE, "handover_%d_%s.json" % (dep, DAY_H))
    if not os.path.exists(path):
        print("%-26s нет списка заказов" % name)
        continue
    want = {x["customer_id"] for x in json.load(open(path, encoding="utf-8"))}
    have = [pool[c] for c in want if c in pool
            and str(pool[c].get("created_at") or "")[:10] >= M.AI_SINCE]
    ai = man = 0
    for c in have:
        a, m = tally(c.get("messages") or [], CUT_H, "created_at")
        ai += a; man += m
    rows1[dep] = (len(want), len(have), ai, man)
    tot["want"] += len(want); tot["have"] += len(have)
    tot["ai"] += ai; tot["man"] += man
    print("%-26s %8d %8d %8s %8s %9s %9.0f"
          % (name, len(want), len(have), f(ai), f(man), M.share(ai, man),
             (ai + man) / max(1, len(have))))
print("-" * 86)
print("%-26s %8d %8d %8s %8s %9s"
      % ("ИТОГО", tot["want"], tot["have"], f(tot["ai"]), f(tot["man"]),
         M.share(tot["ai"], tot["man"])))

# =====================================================================
print()
print("=" * 86)
print("КОГОРТА 2. Все лиды, пришедшие %s" % DAY_L)
print("=" * 86)
print("%-26s %8s %8s %8s %8s %9s %9s"
      % ("отдел", "лидов", "дошли", "ИИ", "менедж.", "доля ИИ", "только ИИ"))
print("-" * 86)
tot2 = collections.Counter()
for dep, name in DEPS:
    hp = os.path.join(HERE, "handover_map_%d.json" % dep)
    hmap = ({int(k): v for k, v in json.load(open(hp, encoding="utf-8")).items()}
            if os.path.exists(hp) else {})
    try:
        dump = F.fetch_range(dep, datetime.strptime(DAY_L, "%Y-%m-%d").date(),
                             1, verbose=False)[0]
    except Exception as e:
        print("%-26s нет данных (%s)" % (name, str(e)[:40]))
        continue
    ai = man = 0; reached = only_ai = 0
    for d in dump["dialogs"]:
        h = hmap.get(d.get("customer_id"))
        cut = (datetime.combine(datetime.strptime(h, "%Y-%m-%d").date(),
                                datetime.max.time()).replace(tzinfo=A.MSK)
               if h else None)
        a, m = tally(d.get("messages") or [], cut, "sent_at")
        ai += a; man += m
        if h: reached += 1
        if a and not m: only_ai += 1
    n = len(dump["dialogs"])
    tot2["leads"] += dump["leads_total"]; tot2["reached"] += reached
    tot2["ai"] += ai; tot2["man"] += man; tot2["only_ai"] += only_ai
    print("%-26s %8s %8d %8s %8s %9s %9d"
          % (name, f(dump["leads_total"]), reached, f(ai), f(man),
             M.share(ai, man), only_ai))
print("-" * 86)
print("%-26s %8s %8d %8s %8s %9s %9d"
      % ("ИТОГО", f(tot2["leads"]), tot2["reached"], f(tot2["ai"]), f(tot2["man"]),
         M.share(tot2["ai"], tot2["man"]), tot2["only_ai"]))
