# -*- coding: utf-8 -*-
"""ОФОРМЛЕНИЕ: все лиды, пришедшие в заданный день, и вся работа по ним.

Оформление для каждого клиента — от первого сообщения до перевода его
заказа на ведение (по карте handover_map_<отдел>.json). У кого перевода
нет — весь диалог целиком, он всё ещё в оформлении.

python -I cohort_day.py 2026-11-09 [отдел] [обрезать_по_дату]
"""
import collections, json, os, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import fetch_cache as F
import method as M

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEP = int(sys.argv[2]) if len(sys.argv) > 2 else 122
TILL = (datetime.strptime(sys.argv[3], "%Y-%m-%d").date()
        if len(sys.argv) > 3 else None)
NAME = dict((d[1], d[2]) for d in A.DEPARTMENTS)[DEP]

hmap = {}
p = os.path.join(HERE, "handover_map_%d.json" % DEP)
if os.path.exists(p):
    hmap = {int(k): v for k, v in json.load(open(p, encoding="utf-8")).items()}

dump = F.fetch_range(DEP, DAY, 1, verbose=False)[0]
leads = dump["leads_total"]
dialogs = dump["dialogs"]

print("ОФОРМЛЕНИЕ. %s" % NAME)
print("Когорта: все лиды, пришедшие %s — %d" % (DAY, leads))
if TILL:
    print("Сообщения учитываем по %s включительно" % TILL)
print("ИИ: Артур и Геннадий по sender_type. роповские учётки не считаются.\n")

ai = man = cli = skip = 0
split = {"reached": collections.Counter(), "open": collections.Counter()}
ai_names, mgr_names = collections.Counter(), collections.Counter()
reached = silent = only_ai = only_man = 0
msgs_per = []
for d in dialogs:
    cid = d.get("customer_id")
    cut = None
    if cid in hmap:
        reached += 1
        cut = datetime.combine(datetime.strptime(hmap[cid], "%Y-%m-%d").date(),
                               datetime.max.time()).replace(tzinfo=A.MSK)
    till = (datetime.combine(TILL, datetime.max.time()).replace(tzinfo=A.MSK)
            if TILL else None)
    a = m = c = 0
    for msg in d.get("messages") or []:
        t = A.parse_dt(msg.get("sent_at") or "")
        if not t:
            continue
        if cut and t > cut:
            continue
        if till and t > till:
            continue
        r = M.who(msg)
        nm = str(msg.get("sender_name") or "").strip()
        if r == "client":
            cli += 1; c += 1
        elif r == "skip":
            skip += 1
        elif r == "ai":
            ai += 1; a += 1; ai_names[nm] += 1
        else:
            man += 1; m += 1; mgr_names[nm] += 1
    msgs_per.append(a + m)
    if c == 0:
        silent += 1
    if a and not m:
        only_ai += 1
    if m and not a:
        only_man += 1
    part = "reached" if cid in hmap else "open"
    split[part]["ai"] += a
    split[part]["man"] += m
    split[part]["n"] += 1

n = len(dialogs)
print("=" * 72)
print("ДОЛЯ ИИ В ОФОРМЛЕНИИ: %s" % M.share(ai, man))
print("=" * 72)
print("сообщений ИИ:         %6d" % ai)
print("сообщений менеджеров: %6d" % man)
print("сообщений клиентов:   %6d  (в дробь не входят)" % cli)
print("не считали (роповские учётки): %d" % skip)
print()
print("лидов в когорте:              %5d" % n)
print("из них дошли до ведения:      %5d  (%.1f%%)" % (reached, 100.0 * reached / max(1, n)))
print("клиент не ответил ни разу:    %5d  (%.0f%%)" % (silent, 100.0 * silent / max(1, n)))
print("вёл только ИИ, без менеджера: %5d" % only_ai)
print("вёл только менеджер, без ИИ:  %5d" % only_man)
print("на лида в среднем: %.1f сообщ. ИИ, %.1f менеджера"
      % (ai / max(1, n), man / max(1, n)))

print()
print("Из чего складывается эта цифра (обе части уже в ней):")
for key, label in (("reached", "дошли до ведения"), ("open", "ещё в оформлении")):
    s = split[key]
    print("   %-18s %4d чел. — ИИ %5d, менеджеры %5d  ->  %s"
          % (label, s["n"], s["ai"], s["man"], M.share(s["ai"], s["man"])))

print("\nИИ по именам:")
for nm, c in ai_names.most_common():
    print("   %-32s %6d" % (nm, c))
print("Менеджеры (топ-15):")
for nm, c in mgr_names.most_common(15):
    print("   %-32s %6d" % (nm or "(без имени)", c))
