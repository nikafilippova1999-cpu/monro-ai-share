#!/usr/bin/env python3
import glob, json, os
from collections import Counter, defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
WHO = ["Сабина Гасанова", "Регина Исмагилова", "Лера Антилова", "Аня Щербакова"]

by_day = defaultdict(Counter)
seen = set()
for f in sorted(glob.glob(os.path.join(DATA, "dialogs_*.json"))):
    with open(f, encoding="utf-8-sig") as fh:
        dialogs = json.load(fh)
    for dlg in dialogs:
        cid = dlg.get("customer_id")
        if cid in seen:
            continue
        seen.add(cid)
        for m in (dlg.get("messages") or []):
            if m.get("sender_type") != "manager":
                continue
            n = m.get("sender_name")
            if n in WHO:
                by_day[n][(m.get("sent_at") or "")[:10]] += 1

for who in WHO:
    days = by_day[who]
    total = sum(days.values())
    print("%-20s всего %4d сообщений" % (who, total))
    for d in sorted(days):
        print("      %s : %4d" % (d, days[d]))
    print()
