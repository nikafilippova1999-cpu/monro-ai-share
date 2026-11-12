# -*- coding: utf-8 -*-
"""Сколько работы приходится на одного менеджера оформления за смену.

Берём всю работу менеджеров за один день: и по новым лидам, и по тем,
кто пришёл раньше и ещё оформляется. Делим на число людей в смене.

python -I nagruzka.py 2026-11-10 [отдел] [людей в смене] [часов в смене]
"""
import collections, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import fetch_cache as F
import method as M

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-11-10"
DEP = int(sys.argv[2]) if len(sys.argv) > 2 else 122
SHIFT = int(sys.argv[3]) if len(sys.argv) > 3 else 5
HOURS = float(sys.argv[4]) if len(sys.argv) > 4 else 12
NAME = dict((d[1], d[2]) for d in A.DEPARTMENTS)[DEP]
f = lambda x: format(int(round(x)), ",d").replace(",", " ")

hp = os.path.join(HERE, "handover_map_%d.json" % DEP)
hmap = ({int(k): v for k, v in json.load(open(hp, encoding="utf-8")).items()}
        if os.path.exists(hp) else {})

# все дни, что есть в кэше: клиент мог прийти когда угодно
files = sorted(fn for fn in os.listdir(os.path.join(HERE, "cache"))
               if fn.startswith("dlg_%d_" % DEP))
import gzip
new_d = old_d = 0           # диалоги: новый лид дня / пришедший раньше
new_m = old_m = 0           # сообщения менеджеров в них
ai_today = 0
dlg_man = set()
people = collections.Counter()
hours = collections.Counter()
ord_d, ord_m = set(), 0      # работа по тем, кто в этот день перешёл на ведение

for fn in files:
    with gzip.open(os.path.join(HERE, "cache", fn), "rt", encoding="utf-8") as fh:
        dump = json.load(fh)
    came = dump["date"]
    for d in dump["dialogs"]:
        cid = d.get("customer_id")
        h = hmap.get(cid)
        if h and h < DAY:          # уже на ведении — это не оформление
            continue
        m_here = 0
        for m in d.get("messages") or []:
            s = str(m.get("sent_at") or "")
            if not s.startswith(DAY):
                continue
            if h and s[:10] > h:
                continue
            r = M.who(m)
            if r == "ai":
                ai_today += 1
            elif r == "manager":
                m_here += 1
                nm = str(m.get("sender_name") or "")
                people[nm] += 1
                hours[int(s[11:13])] += 1
        if m_here:
            dlg_man.add(cid)
            if came == DAY:
                new_d += 1; new_m += m_here
            else:
                old_d += 1; old_m += m_here
            if h == DAY:
                ord_d.add(cid); ord_m += m_here

tot_m = new_m + old_m
tot_d = new_d + old_d
print("НАГРУЗКА ОФОРМЛЕНИЯ. %s, день %s" % (NAME, DAY))
print("(дней истории в кэше: %d)" % len(files))
print("=" * 70)
print("диалогов, где менеджер писал в этот день:  %s" % f(tot_d))
print("   из них лид пришёл в этот же день:       %s  (%.0f%%)"
      % (f(new_d), 100.0 * new_d / max(1, tot_d)))
print("   пришёл раньше, ещё оформляется:         %s  (%.0f%%)"
      % (f(old_d), 100.0 * old_d / max(1, tot_d)))
print("   из них перешли на ведение в этот день:  %s" % f(len(ord_d)))
print()
print("сообщений менеджеров за день:              %s" % f(tot_m))
print("   по новым лидам:                         %s" % f(new_m))
print("   по тем, кто пришёл раньше:              %s" % f(old_m))
print("   в том числе по дошедшим до заказа:      %s" % f(ord_m))
print("сообщений ИИ за день:                      %s" % f(ai_today))
print("фактически писало людей за день:           %d" % len(people))
print("в пиковый час:                             %d сообщений" % (max(hours.values()) if hours else 0))
print()
print("=" * 70)
print("ЕСЛИ В СМЕНЕ %d ЧЕЛОВЕК (%g часов)" % (SHIFT, HOURS))
print("=" * 70)
print("   активных диалогов на одного:     %s" % f(tot_d / SHIFT))
print("   сообщений на одного за смену:    %s" % f(tot_m / SHIFT))
print("   сообщений в час:                 %.0f" % (tot_m / SHIFT / HOURS))
print("   одно сообщение каждые:           %.1f минуты" % (60.0 / (tot_m / SHIFT / HOURS)))
print()
print("   из них на доведение до заказа:   %s сообщ. (%.0f%% времени)"
      % (f(ord_m / SHIFT), 100.0 * ord_m / max(1, tot_m)))
print("   на остальных:                    %s сообщ." % f((tot_m - ord_m) / SHIFT))
print()
print("СКОЛЬКО ЛЮДЕЙ НУЖНО ПРИ РАЗНОМ ТЕМПЕ (смена %g ч):" % HOURS)
for norm in (20, 30, 40, 50):
    print("   %2d сообщ./час -> %.1f человек" % (norm, tot_m / (norm * HOURS)))
