# -*- coding: utf-8 -*-
"""ОФОРМЛЕНИЕ за день по правилам method.py.

Вход: handover_<отдел>_<день>.json — заказы, переведённые на ведение в этот
день (выгружены инструментом CRM get_orders по полю «Дата перевода на
ведение»), и кэш диалогов за неделю.

Считаем долю ИИ в оформлении тех клиентов, чей заказ переведён на ведение
в этот день и кто пришёл не раньше чем за WEEK_DAYS дней до него.

python -I ofo_handover_day.py 2026-11-10 [отдел]
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
NAME = dict((d[1], d[2]) for d in A.DEPARTMENTS)[DEP]
EDGE = DAY - timedelta(days=M.WEEK_DAYS)          # раньше этого дня лид не берём
CUT = datetime.combine(DAY, datetime.max.time()).replace(tzinfo=A.MSK)

orders = json.load(open(os.path.join(HERE, "handover_%d_%s.json" % (DEP, DAY)),
                        encoding="utf-8"))
want = {}
for o in orders:
    want.setdefault(o["customer_id"], []).append(o)

print("ОФОРМЛЕНИЕ. %s" % NAME)
print("Заказы, переведённые на ведение %s: %d (клиентов %d)"
      % (DAY, len(orders), len(want)))
print("Лид должен прийти не раньше %s\n" % EDGE, flush=True)

# --- ищем этих клиентов в кэше диалогов -------------------------------------
found = {}        # customer_id -> (дата прихода, диалог)
for dump in F.fetch_range(DEP, DAY, M.WEEK_DAYS + 1, verbose=False):
    came = datetime.strptime(dump["date"], "%Y-%m-%d").date()
    for d in dump["dialogs"]:
        cid = d.get("customer_id")
        if cid in want and cid not in found:
            found[cid] = (came, d)

missing = [c for c in want if c not in found]
print("Нашли в диалогах за неделю: %d клиентов" % len(found))
print("Пришли раньше %s — в расчёт не идут: %d\n" % (EDGE, len(missing)))

# --- считаем ----------------------------------------------------------------
ai = man = cli = skip = 0
ai_names, mgr_names = collections.Counter(), collections.Counter()
no_ai, no_man, per_client = [], [], []
for cid, (came, d) in sorted(found.items()):
    a = m = 0
    for msg in d.get("messages") or []:
        t = A.parse_dt(msg.get("sent_at") or "")
        if not t or t > CUT:
            continue
        r = M.who(msg)
        nm = str(msg.get("sender_name") or "").strip()
        if r == "client":
            cli += 1
        elif r == "skip":
            skip += 1
        elif r == "ai":
            ai += 1; a += 1; ai_names[nm] += 1
        else:
            man += 1; m += 1; mgr_names[nm] += 1
    per_client.append((cid, came, a, m))
    if a == 0:
        no_ai.append(cid)
    if m == 0:
        no_man.append(cid)

n = len(found)
print("=" * 72)
print("ДОЛЯ ИИ В ОФОРМЛЕНИИ: %s" % M.share(ai, man))
print("=" * 72)
print("сообщений ИИ:         %5d" % ai)
print("сообщений менеджеров: %5d" % man)
print("сообщений клиентов:   %5d  (в дробь не входят)" % cli)
print("не считали (роповские учётки): %d" % skip)
print()
print("клиентов в расчёте: %d" % n)
print("на одного клиента: %.1f сообщ. ИИ, %.1f менеджера"
      % (ai / max(1, n), man / max(1, n)))
print("оформлено целиком руками (ИИ не писал): %d из %d" % (len(no_ai), n))
print("оформлено целиком ИИ (менеджер не писал): %d из %d" % (len(no_man), n))

print("\nИИ по именам:")
for nm, c in ai_names.most_common():
    print("   %-32s %5d" % (nm, c))
print("Менеджеры:")
for nm, c in mgr_names.most_common(20):
    print("   %-32s %5d" % (nm or "(без имени)", c))

gap = collections.Counter((DAY - came).days for _, came, _, _ in per_client)
print("\nСколько дней от прихода лида до перевода на ведение:")
for g in sorted(gap):
    print("   %d дн. — %d клиентов" % (g, gap[g]))

if no_ai:
    print("\nОформлены без единого сообщения ИИ (customer_id):")
    print("   " + ", ".join(str(c) for c in no_ai))
