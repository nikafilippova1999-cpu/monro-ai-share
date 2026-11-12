# -*- coding: utf-8 -*-
"""Построчный разбор одного клиента: как именно считается его оформление.

python -I show_one.py 2026-11-10 122 [номер клиента в списке]
"""
import json, os, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import fetch_cache as F
import method as M

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEP = int(sys.argv[2]) if len(sys.argv) > 2 else 122
IDX = int(sys.argv[3]) if len(sys.argv) > 3 else 0

orders = json.load(open(os.path.join(HERE, "handover_%d_%s.json" % (DEP, DAY)),
                        encoding="utf-8"))
want = {o["customer_id"] for o in orders}
found = []
for dump in F.fetch_range(DEP, DAY, M.WEEK_DAYS + 1, verbose=False):
    came = datetime.strptime(dump["date"], "%Y-%m-%d").date()
    for d in dump["dialogs"]:
        if d.get("customer_id") in want:
            found.append((came, d))
found.sort(key=lambda x: len(x[1].get("messages") or []))
came, d = found[min(IDX, len(found) - 1)]
cid = d.get("customer_id")
CUT = datetime.combine(DAY, datetime.max.time()).replace(tzinfo=A.MSK)

print("КЛИЕНТ %s" % cid)
print("пришёл %s, заказ переведён на ведение %s" % (came, DAY))
print("считаем всё до конца дня перевода\n")
print("%-17s %-10s %-26s %s" % ("когда", "кто", "имя", "текст"))
print("-" * 100)
ai = man = 0
for msg in sorted((d.get("messages") or []),
                  key=lambda m: str(m.get("sent_at") or "")):
    t = A.parse_dt(msg.get("sent_at") or "")
    if not t:
        continue
    after = t > CUT
    r = M.who(msg)
    if not after:
        if r == "ai":
            ai += 1
        elif r == "manager":
            man += 1
    tag = {"ai": "ИИ", "manager": "менеджер", "client": "клиент",
           "skip": "не в счёт"}[r]
    if after:
        tag = "(ведение)"
    txt = " ".join(str(msg.get("text") or "").split())[:46]
    print("%-17s %-10s %-26s %s" % (str(msg.get("sent_at"))[:16], tag,
                                    str(msg.get("sender_name") or "")[:26], txt))
print("-" * 100)
print("ИТОГ по этому клиенту: ИИ %d + менеджеры %d  ->  доля ИИ %s"
      % (ai, man, M.share(ai, man)))
