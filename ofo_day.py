# -*- coding: utf-8 -*-
"""ОФОРМЛЕНИЕ за день по правилам method.py.

python -I ofo_day.py 2026-11-10 [отдел]
"""
import collections, os, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A       # переключает stdout на utf-8, даёт parse_dt и выгрузку
import fetch_cache as F
import method as M

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEP = int(sys.argv[2]) if len(sys.argv) > 2 else 122
NAME = dict((d[1], d[2]) for d in A.DEPARTMENTS)[DEP]

print("ОФОРМЛЕНИЕ. %s (отдел %d)" % (NAME, DEP))
print("Заказ создан %s, лид пришёл не раньше %s (%d дн.)"
      % (DAY, DAY - timedelta(days=M.WEEK_DAYS), M.WEEK_DAYS))
print("ИИ: Артур ИИ и Бот. Не считаем: роповские учётки.\n", flush=True)

# --- выборка -----------------------------------------------------------------
picked = []            # (dlg, момент заказа, дата прихода)
too_old = 0
for dump in F.fetch_range(DEP, DAY, M.WEEK_DAYS + 1, verbose=False):
    came = datetime.strptime(dump["date"], "%Y-%m-%d").date()
    for d in dump["dialogs"]:
        t = M.order_time(d, A.parse_dt)
        if t is None or t.date() != DAY:
            continue
        picked.append((d, t, came))

print("Заказов, оформленных %s из лидов этой недели: %d" % (DAY, len(picked)))

# --- считаем -----------------------------------------------------------------
ai = man = cli = skip = 0
per_name = collections.Counter()
mgr_names = collections.Counter()
no_ai = []          # заказы, где ИИ не участвовал вовсе
no_man = []         # заказы, которые ИИ сделал целиком
for d, cut, came in picked:
    a = m = 0
    for msg in d.get("messages") or []:
        t = A.parse_dt(msg.get("sent_at") or "")
        if not t or t > cut:
            continue
        r = M.who(msg)
        nm = str(msg.get("sender_name") or "").strip()
        if r == "client":
            cli += 1
        elif r == "skip":
            skip += 1
        elif r == "ai":
            ai += 1
            a += 1
            per_name[nm] += 1
        else:
            man += 1
            m += 1
            mgr_names[nm] += 1
    if a == 0:
        no_ai.append(d.get("customer_id"))
    if m == 0:
        no_man.append(d.get("customer_id"))

print()
print("=" * 70)
print("ДОЛЯ ИИ В ОФОРМЛЕНИИ: %s" % M.share(ai, man))
print("=" * 70)
print("сообщений ИИ:        %5d" % ai)
print("сообщений менеджеров:%5d" % man)
print("сообщений клиентов:  %5d  (в дробь не входят)" % cli)
print("не считали (роповские учётки): %d" % skip)
print()
print("на один заказ: %.1f сообщ. ИИ, %.1f менеджера"
      % (ai / max(1, len(picked)), man / max(1, len(picked))))
print("заказов целиком руками (ИИ не писал ни разу): %d из %d"
      % (len(no_ai), len(picked)))
print("заказов целиком ИИ (менеджер не писал ни разу): %d из %d"
      % (len(no_man), len(picked)))

print()
print("ИИ по именам:")
for n, c in per_name.most_common():
    print("   %-34s %5d" % (n, c))
print("Менеджеры:")
for n, c in mgr_names.most_common(20):
    print("   %-34s %5d" % (n or "(без имени)", c))

gap = collections.Counter((DAY - c).days for _, _, c in picked)
print()
print("Сколько дней от прихода лида до заказа:")
for g in sorted(gap):
    print("   %d дн. — %d заказов" % (g, gap[g]))

if no_ai:
    print()
    print("Заказы без единого сообщения ИИ (customer_id): %s"
          % ", ".join(str(c) for c in no_ai[:40]))
