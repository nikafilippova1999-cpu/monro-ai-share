# -*- coding: utf-8 -*-
"""Пересчёт книг по уточнённому списку ботов."""
import sys, collections
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\Менеджер\nika-bot")
import ai_share_daily as A

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
LOOK = int(sys.argv[2]) if len(sys.argv) > 2 else 3
DEP, GROUP, NAME = 122, "КНИГИ", "Алина и Регина"

rows, jobs, leads = [], [], 0
for i in range(LOOK):
    ds = (DAY - timedelta(days=i)).strftime("%Y-%m-%d")
    first = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [DEP],
                        "page": 1, "per_page": 100})
    if i == 0:
        leads = (first.get("pagination") or {}).get("total") or 0
    for d in first.get("dialogs", []):
        A.scan(d, DAY, rows, GROUP)
    lp = (first.get("pagination") or {}).get("last_page") or 1
    jobs += [(ds, p) for p in range(2, lp + 1)]
if jobs:
    with ThreadPoolExecutor(max_workers=6) as pool:
        for chunk in pool.map(lambda j: A.crm_post(
                {"date_from": j[0], "date_to": j[0], "department_ids": [DEP],
                 "page": j[1], "per_page": 100}).get("dialogs", []), jobs):
            for d in chunk:
                A.scan(d, DAY, rows, GROUP)

acc = A.summarize(rows)
print("КНИГИ — %s, за %s (просмотр назад %d дн.)" % (NAME, DAY, LOOK))
print("Ботом считаются: Бот, Артур ИИ, Геннадий Горин, Алина Роп книги\n")
for stage, label in (("ofo", "ОФОРМЛЕНИЕ"), ("ved", "ВЕДЕНИЕ")):
    b, m = acc[stage + "_bot"], acc[stage + "_man"]
    print("%s: бот %d + менеджер %d = %d  ->  ДОЛЯ ИИ %s"
          % (label, b, m, b + m, A.pct(b, m)))
print("\nРассылок исключено: %d сообщ. в %d диалогов"
      % (acc["blast_msg"], len(acc["blast_dlg"])))
print("Лидов за день: %d, менеджеров в оформлении: %d -> %s на человека"
      % (leads, len(acc["mgr_ofo"]), A.per_mgr(leads, acc["mgr_ofo"])))
print("Заказов в ведении: %d, менеджеров ведения: %d -> %s на человека"
      % (len(acc["live_ved"]), len(acc["mgr_ved"]),
         A.per_mgr(len(acc["live_ved"]), acc["mgr_ved"])))

ofo = [r for r in rows if r["stage"] == "ofo"]
print("\nКТО ЕСТЬ КТО В ОФОРМЛЕНИИ:")
print("  БОТ:")
for n, c in collections.Counter(r["name"] for r in ofo if r["role"] == "bot").most_common(8):
    print("     %-34s %5d" % (n or "(без имени)", c))
print("  МЕНЕДЖЕРЫ:")
for n, c in collections.Counter(r["name"] for r in ofo if r["role"] == "manager").most_common(12):
    print("     %-34s %5d" % (n or "(без имени)", c))
