# -*- coding: utf-8 -*-
"""Примеры сообщений, засчитанных боту и менеджеру, с customer_id для проверки."""
import sys, collections, random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\Менеджер\nika-bot")
import ai_share_daily as A

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEP, GROUP, NAME = 122, "КНИГИ", "Алина и Регина"
LOOK = 2
rows = []
jobs = []
for i in range(LOOK):
    ds = (DAY - timedelta(days=i)).strftime("%Y-%m-%d")
    first = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [DEP],
                        "page": 1, "per_page": 100})
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

ofo = [r for r in rows if r["stage"] == "ofo" and r["text"]]
bot = [r for r in ofo if r["role"] == "bot" and len(r["text"]) > 40
       and not r["text"].startswith("http")]
man = [r for r in ofo if r["role"] == "manager" and len(r["text"]) > 40
       and not r["text"].startswith("http")]

print("%s — %s, %s. Оформление." % (GROUP, NAME, DAY))
print("\n" + "=" * 76)
print("ЗАСЧИТАНО БОТУ  (отправители: %s)"
      % ", ".join(sorted({r["name"] for r in bot})))
print("=" * 76)
for r in random.sample(bot, min(14, len(bot))):
    print("\nклиент %s, %s, отправитель «%s»"
          % (r["cid"], r["t"].strftime("%d.%m %H:%M"), r["name"]))
    print("   %s" % r["text"][:230])

print("\n\n" + "=" * 76)
print("ЗАСЧИТАНО МЕНЕДЖЕРУ")
print("=" * 76)
WANT = ["Алина Роп книги", "Яна Гавриленко", "Артур Пещеров",
        "Физалия Галеева", "Регина Исмагилова", "Сабина Гасанова"]
for w in WANT:
    sub = [r for r in man if r["name"].startswith(w)]
    if not sub:
        continue
    r = random.choice(sub)
    print("\n«%s» — всего %d сообщ. за день" % (r["name"], len(sub)))
    print("   клиент %s, %s" % (r["cid"], r["t"].strftime("%d.%m %H:%M")))
    print("   %s" % r["text"][:230])
