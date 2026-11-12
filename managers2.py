#!/usr/bin/env python3
"""Manager breakdown, corrected: personal touch + order-level attribution."""
import glob, json, os, re, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-07-27"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MSK = timezone(timedelta(hours=3))
OUR = ("manager", "arthur_ai", "bot")
BROADCAST = "Алина Роп книги 🧿"          # bulk-mailing account, not a person
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

s = defaultdict(lambda: {"touched": 0, "msgs": 0, "orders": 0, "amount": 0,
                         "pay": 0, "miss": 0})
seen = set()
tot = {"dialogs": 0, "orders": 0, "amount": 0, "pay": 0, "miss": 0}

for f in sorted(glob.glob(os.path.join(DATA, "dialogs_*.json"))):
    with open(f, encoding="utf-8-sig") as fh:
        dialogs = json.load(fh)
    for dlg in dialogs:
        cid = dlg.get("customer_id")
        if cid in seen:
            continue
        msgs = sorted(dlg.get("messages") or [], key=lambda m: m.get("sent_at") or "")
        day_msgs = []
        for m in msgs:
            try:
                t = parse_dt(m["sent_at"])
            except Exception:
                continue
            if start <= t < end:
                day_msgs.append(m)
        if not day_msgs:
            continue
        seen.add(cid)
        tot["dialogs"] += 1

        touched = set()
        for m in day_msgs:
            if m.get("sender_type") != "manager":
                continue
            who = m.get("sender_name") or "?"
            if who == BROADCAST:
                continue
            s[who]["msgs"] += 1
            touched.add(who)
        for who in touched:
            s[who]["touched"] += 1

        assigned = (dlg.get("manager") or {}).get("name")
        for idx, m in enumerate(msgs):
            if not is_pay(m):
                continue
            try:
                T = parse_dt(m["sent_at"])
            except Exception:
                continue
            if not (start <= T < end):
                continue
            tot["pay"] += 1
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
            owner = assigned if assigned and assigned != BROADCAST else None
            if owner is None:
                owner = sorted(touched)[0] if touched else "— никто не закреплён —"
            s[owner]["pay"] += 1
            if ping is None and reply is None:
                s[owner]["miss"] += 1
                tot["miss"] += 1

        for o in (dlg.get("orders") or []):
            try:
                ot = parse_dt(o["created_at"])
            except Exception:
                continue
            if not (start <= ot < end):
                continue
            om = (o.get("manager") or {}).get("name") or "— без менеджера —"
            s[om]["orders"] += 1
            s[om]["amount"] += o.get("amount") or 0
            tot["orders"] += 1
            tot["amount"] += o.get("amount") or 0

money = lambda v: format(v, ",").replace(",", " ")

print("=" * 80)
print("МЕНЕДЖЕРЫ — %s, отдел 122 (рассылочный аккаунт исключён)" % DAY)
print("=" * 80)
print("Всего диалогов с активностью: %d | заказов: %d на %s ₽"
      % (tot["dialogs"], tot["orders"], money(tot["amount"])))
print("Запросов оплаты: %d | без пинга за 10 мин: %d (%.0f%%)"
      % (tot["pay"], tot["miss"], 100.0 * tot["miss"] / max(tot["pay"], 1)))
print()
hdr = "%-24s %8s %7s %6s %7s %7s %11s %8s" % (
    "менеджер", "диалогов", "сообщ", "оплат", "б/пинг", "заказов", "сумма ₽", "ср.чек")
print(hdr)
print("-" * len(hdr))
rows = sorted(s.items(), key=lambda kv: -kv[1]["orders"])
for who, v in rows:
    if not (v["touched"] or v["orders"] or v["pay"]):
        continue
    avg = money(round(v["amount"] / v["orders"])) if v["orders"] else "—"
    print("%-24s %8d %7d %6d %7d %7d %11s %8s"
          % (who[:24], v["touched"], v["msgs"], v["pay"], v["miss"],
             v["orders"], money(v["amount"]), avg))

print()
print("Заказов на 100 диалогов, которые менеджер вёл лично (от 20 диалогов):")
for who, v in sorted(s.items(), key=lambda kv: -(kv[1]["orders"] / max(kv[1]["touched"], 1))):
    if v["touched"] < 20:
        continue
    print("   %-24s %5d диал. -> %3d зак. = %5.1f на 100"
          % (who[:24], v["touched"], v["orders"], 100.0 * v["orders"] / v["touched"]))
