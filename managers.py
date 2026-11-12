#!/usr/bin/env python3
"""Manager breakdown for one day, built from locally saved Easy-Mo exports."""
import glob, json, os, re, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-07-27"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MSK = timezone(timedelta(hours=3))
OUR = ("manager", "arthur_ai", "bot")
PING_MINUTES = 10
PAY_LINK = re.compile(r"pay=\d+")
CARD = re.compile(r"\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}")


def parse_dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK)


def is_pay(m):
    if m.get("sender_type") not in OUR:
        return False
    t = m.get("text") or ""
    return bool(PAY_LINK.search(t) or CARD.search(t))


start = parse_dt(DAY + " 00:00:00")
end = start + timedelta(days=1)

seen_dialogs = set()
stat = defaultdict(lambda: {"dialogs": 0, "pay": 0, "miss": 0, "replies": 0,
                            "orders": 0, "amount": 0, "prepay": 0})
manual_replies = defaultdict(int)
order_rows = []
totals = {"dialogs": 0, "pay": 0, "miss": 0, "orders": 0, "amount": 0, "prepay": 0}

for f in sorted(glob.glob(os.path.join(DATA, "dialogs_*.json"))):
    with open(f, encoding="utf-8-sig") as fh:
        dialogs = json.load(fh)
    for dlg in dialogs:
        cid = dlg.get("customer_id")
        if cid in seen_dialogs:
            continue
        msgs = sorted(dlg.get("messages") or [], key=lambda m: m.get("sent_at") or "")
        in_day = []
        for m in msgs:
            try:
                t = parse_dt(m["sent_at"])
            except Exception:
                continue
            if start <= t < end:
                in_day.append((t, m))
        if not in_day:
            continue
        seen_dialogs.add(cid)

        who = (dlg.get("manager") or {}).get("name") or "— без менеджера —"
        stat[who]["dialogs"] += 1
        totals["dialogs"] += 1

        for t, m in in_day:
            if m.get("sender_type") == "manager":
                manual_replies[m.get("sender_name") or "?"] += 1

        for idx, m in enumerate(msgs):
            if not is_pay(m):
                continue
            try:
                T = parse_dt(m["sent_at"])
            except Exception:
                continue
            if not (start <= T < end):
                continue
            stat[who]["pay"] += 1
            totals["pay"] += 1
            deadline = T + timedelta(minutes=PING_MINUTES)
            ping = reply = None
            for n in msgs[idx + 1:]:
                try:
                    tn = parse_dt(n["sent_at"])
                except Exception:
                    continue
                if tn <= T:
                    continue
                if tn > deadline:
                    break
                if n.get("sender_type") == "client":
                    reply = reply or n
                elif n.get("sender_type") in OUR:
                    ping = ping or n
            if ping is None and reply is None:
                stat[who]["miss"] += 1
                totals["miss"] += 1

        for o in (dlg.get("orders") or []):
            try:
                ot = parse_dt(o["created_at"])
            except Exception:
                continue
            if not (start <= ot < end):
                continue
            om = (o.get("manager") or {}).get("name") or "— без менеджера —"
            amt = o.get("amount") or 0
            pre = o.get("prepayment") or 0
            stat[om]["orders"] += 1
            stat[om]["amount"] += amt
            stat[om]["prepay"] += pre
            totals["orders"] += 1
            totals["amount"] += amt
            totals["prepay"] += pre
            order_rows.append((om, cid, amt, pre))

print("=" * 78)
print("АНАЛИТИКА ПО МЕНЕДЖЕРАМ — %s, отдел 122" % DAY)
print("=" * 78)
print("Диалогов с активностью: %d | запросов оплаты: %d | без пинга: %d"
      % (totals["dialogs"], totals["pay"], totals["miss"]))
print("Заказов: %d | сумма: %s ₽ | предоплат: %s ₽"
      % (totals["orders"], format(totals["amount"], ",").replace(",", " "),
         format(totals["prepay"], ",").replace(",", " ")))
print()

hdr = "%-26s %7s %6s %6s %7s %7s %10s" % (
    "менеджер", "диалог", "оплат", "б/пинг", "%проп", "заказ", "сумма ₽")
print(hdr)
print("-" * len(hdr))
for who, s in sorted(stat.items(), key=lambda kv: -kv[1]["dialogs"]):
    pct = ("%d%%" % round(100 * s["miss"] / s["pay"])) if s["pay"] else "—"
    print("%-26s %7d %6d %6d %7s %7d %10s"
          % (who[:26], s["dialogs"], s["pay"], s["miss"], pct, s["orders"],
             format(s["amount"], ",").replace(",", " ")))

print()
print("Ответы, написанные живым менеджером вручную (сообщений за день):")
for who, n in sorted(manual_replies.items(), key=lambda kv: -kv[1]):
    print("   %-26s %5d" % (who[:26], n))

print()
print("Конверсия диалог -> заказ по закреплённому менеджеру:")
for who, s in sorted(stat.items(), key=lambda kv: -kv[1]["dialogs"]):
    if s["dialogs"] < 20:
        continue
    print("   %-26s %5d диал. -> %3d зак. = %.1f%%"
          % (who[:26], s["dialogs"], s["orders"],
             100.0 * s["orders"] / s["dialogs"]))
