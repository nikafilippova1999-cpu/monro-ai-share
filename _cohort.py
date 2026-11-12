# -*- coding: utf-8 -*-
"""Когорта: все лиды, пришедшие за последние N дней, и вся работа с ними."""
import sys, re, collections
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\Менеджер\nika-bot")
import ai_share_daily as A

LAST = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
DEP, GROUP, NAME = 122, "КНИГИ", "Алина и Регина"

leads_by_day = {}
dialogs = []
jobs = []
for i in range(DAYS):
    ds = (LAST - timedelta(days=i)).strftime("%Y-%m-%d")
    first = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [DEP],
                        "page": 1, "per_page": 100})
    leads_by_day[ds] = (first.get("pagination") or {}).get("total") or 0
    dialogs += first.get("dialogs", [])
    lp = (first.get("pagination") or {}).get("last_page") or 1
    jobs += [(ds, p) for p in range(2, lp + 1)]
if jobs:
    with ThreadPoolExecutor(max_workers=6) as pool:
        for chunk in pool.map(lambda j: A.crm_post(
                {"date_from": j[0], "date_to": j[0], "department_ids": [DEP],
                 "page": j[1], "per_page": 100}).get("dialogs", []), jobs):
            dialogs += chunk

# все сообщения этих лидов, без фильтра по дате сообщения
rows = []
for d in dialogs:
    cut = A.split_point(d, GROUP)
    cid = d.get("customer_id")
    msgs = sorted([(A.parse_dt(m.get("sent_at") or ""), m)
                   for m in (d.get("messages") or []) if A.parse_dt(m.get("sent_at") or "")],
                  key=lambda x: x[0])
    last_client = None
    for t, m in msgs:
        r = A.role(m)
        rows.append({"cid": cid, "t": t, "role": r,
                     "stage": "ved" if (cut and t > cut) else "ofo",
                     "name": str(m.get("sender_name") or "").strip(),
                     "text": " ".join(str(m.get("text") or "").split()),
                     "since_client": (None if last_client is None
                                      else (t - last_client).total_seconds() / 3600.0)})
        if r == "client":
            last_client = t

acc = A.summarize(rows)
total_leads = sum(leads_by_day.values())
period = "%s — %s" % ((LAST - timedelta(days=DAYS - 1)).strftime("%d.%m"), LAST.strftime("%d.%m"))

print("КНИГИ — %s. КОГОРТА ЛИДОВ за %s" % (NAME, period))
print("Ботом считаются: Бот, Артур ИИ, Геннадий Горин, Алина Роп книги\n")
print("Лидов пришло: %d" % total_leads)
for ds in sorted(leads_by_day):
    print("   %s — %d" % (ds, leads_by_day[ds]))
print("Диалогов выгружено: %d" % len(dialogs))
print()
b, m = acc["ofo_bot"], acc["ofo_man"]
print("ОФОРМЛЕНИЕ по этой когорте: бот %d + менеджер %d = %d  ->  ДОЛЯ ИИ %s"
      % (b, m, b + m, A.pct(b, m)))
bv, mv = acc["ved_bot"], acc["ved_man"]
print("ВЕДЕНИЕ по этой когорте:    бот %d + менеджер %d = %d  ->  ДОЛЯ ИИ %s"
      % (bv, mv, bv + mv, A.pct(bv, mv)))
print("\nРассылок исключено: %d сообщ." % acc["blast_msg"])
print("Менеджеров в оформлении: %d -> %s лидов на человека"
      % (len(acc["mgr_ofo"]), A.per_mgr(total_leads, acc["mgr_ofo"])))

ofo = [r for r in rows if r["stage"] == "ofo"]
print("\nКТО ЕСТЬ КТО В ОФОРМЛЕНИИ:")
print("  БОТ:")
for n, c in collections.Counter(r["name"] for r in ofo if r["role"] == "bot").most_common(6):
    print("     %-34s %6d" % (n or "(без имени)", c))
print("  МЕНЕДЖЕРЫ:")
for n, c in collections.Counter(r["name"] for r in ofo if r["role"] == "manager").most_common(14):
    print("     %-34s %6d" % (n or "(без имени)", c))
