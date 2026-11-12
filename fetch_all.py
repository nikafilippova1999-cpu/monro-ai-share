# -*- coding: utf-8 -*-
"""Выгрузка нескольких отделов подряд: python -I fetch_all.py 2026-11-10 8 126 128 127"""
import os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_cache as F

last = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
days = int(sys.argv[2])
for dep in [int(x) for x in sys.argv[3:]]:
    print("=== отдел %d ===" % dep, flush=True)
    tot_l = tot_d = 0
    for d in F.fetch_range(dep, last, days):
        tot_l += d["leads_total"]
        tot_d += len(d["dialogs"])
    print("   итого лидов %d, диалогов %d" % (tot_l, tot_d), flush=True)
print("ВСЁ ГОТОВО", flush=True)
