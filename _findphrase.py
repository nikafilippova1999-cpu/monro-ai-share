# -*- coding: utf-8 -*-
"""Какие шаблоны уходят клиенту в момент оформления заказа.

Берём диалоги, где в CRM есть заказ, и смотрим, какие сообщения
(не клиента) ушли в пределах часа до/после создания заказа.
Это и есть кандидаты на фразу-границу «оформление -> ведение».
"""
import collections, gzip, io, json, os, sys
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A   # он сам переключает stdout на utf-8

DEP = int(sys.argv[1]) if len(sys.argv) > 1 else 122
WIN = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0   # окно в часах

files = sorted(f for f in os.listdir(os.path.join(HERE, "cache"))
               if f.startswith("dlg_%d_" % DEP))
near = collections.Counter()
with_order = 0
for fn in files:
    with gzip.open(os.path.join(HERE, "cache", fn), "rt", encoding="utf-8") as f:
        dump = json.load(f)
    for d in dump["dialogs"]:
        pts = [A.parse_dt(o.get("created_at") or "") for o in (d.get("orders") or [])]
        pts = [p for p in pts if p]
        if not pts:
            continue
        with_order += 1
        first = min(pts)
        for m in d.get("messages") or []:
            if A.role(m) == "client":
                continue
            t = A.parse_dt(m.get("sent_at") or "")
            if not t or abs((t - first).total_seconds()) > WIN * 3600:
                continue
            txt = " ".join(str(m.get("text") or "").split())
            if len(txt) < 20:
                continue
            near[txt[:110]] += 1

print("Отдел %d, файлов %d (%s)" % (DEP, len(files), ", ".join(f[8:18] for f in files)))
print("Диалогов с заказом: %d" % with_order)
print("\nЧТО УХОДИТ КЛИЕНТУ В ПРЕДЕЛАХ %.0f Ч ОТ СОЗДАНИЯ ЗАКАЗА" % WIN)
print("=" * 78)
for txt, c in near.most_common(25):
    print("%5d x  %s" % (c, txt))
