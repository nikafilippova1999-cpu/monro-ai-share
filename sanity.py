#!/usr/bin/env python3
"""Sanity checks before drawing conclusions about managers."""
import glob, json, os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

DAY = "2026-07-27"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MSK = timezone(timedelta(hours=3))


def parse_dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK)


start = parse_dt(DAY + " 00:00:00")
end = start + timedelta(days=1)

same = diff = 0
pairs = Counter()
alina_times = []
alina_texts = Counter()
seen = set()

for f in sorted(glob.glob(os.path.join(DATA, "dialogs_*.json"))):
    with open(f, encoding="utf-8-sig") as fh:
        dialogs = json.load(fh)
    for dlg in dialogs:
        cid = dlg.get("customer_id")
        if cid in seen:
            continue
        seen.add(cid)
        dm = (dlg.get("manager") or {}).get("name")
        for o in (dlg.get("orders") or []):
            try:
                ot = parse_dt(o["created_at"])
            except Exception:
                continue
            if not (start <= ot < end):
                continue
            om = (o.get("manager") or {}).get("name")
            if om == dm:
                same += 1
            else:
                diff += 1
                pairs[(str(dm), str(om))] += 1
        for m in (dlg.get("messages") or []):
            if m.get("sender_name") != "Алина Роп книги 🧿":
                continue
            try:
                t = parse_dt(m["sent_at"])
            except Exception:
                continue
            if start <= t < end:
                alina_times.append(t)
                alina_texts[" ".join((m.get("text") or "").split())[:60]] += 1

print("=== ORDERS: manager on order vs manager on dialog (%s) ===" % DAY)
print("совпадает: %d ; отличается: %d" % (same, diff))
print("топ расхождений (диалог -> заказ):")
for (dm, om), n in pairs.most_common(8):
    print("   %-24s -> %-24s %3d" % (dm[:24], om[:24], n))

print()
print("=== 'Алина Роп книги' — что это за аккаунт ===")
print("сообщений за день: %d" % len(alina_times))
if alina_times:
    alina_times.sort()
    span = (alina_times[-1] - alina_times[0]).total_seconds() / 3600
    print("интервал активности: %s - %s (%.1f ч)"
          % (alina_times[0].strftime("%H:%M"), alina_times[-1].strftime("%H:%M"), span))
    gaps = [(alina_times[i + 1] - alina_times[i]).total_seconds()
            for i in range(len(alina_times) - 1)]
    tiny = sum(1 for g in gaps if g <= 2)
    print("пар сообщений с интервалом <=2 сек: %d из %d" % (tiny, len(gaps)))
    by_hour = Counter(t.hour for t in alina_times)
    night = sum(n for h, n in by_hour.items() if h < 6)
    print("сообщений в 00:00-05:59: %d" % night)
print("топ повторяющихся текстов:")
for txt, n in alina_texts.most_common(5):
    print("   %4d x  %s" % (n, txt))
