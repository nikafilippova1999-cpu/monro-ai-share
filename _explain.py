# -*- coding: utf-8 -*-
"""Показывает, как считается доля ИИ в оформлении: разбор по шагам."""
import sys, collections, random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\Менеджер\nika-bot")
import ai_share_daily as A

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEPTS = [("КНИГИ", 122, "Алина и Регина"), ("СТАТУЭТКИ", 126, "Зарина")]
LOOK = 3


def gather(dep, group):
    rows = []
    jobs = []
    leads = 0
    for i in range(LOOK):
        ds = (DAY - timedelta(days=i)).strftime("%Y-%m-%d")
        first = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [dep],
                            "page": 1, "per_page": 100})
        if i == 0:
            leads = (first.get("pagination") or {}).get("total") or 0
        for d in first.get("dialogs", []):
            A.scan(d, DAY, rows, group)
        lp = (first.get("pagination") or {}).get("last_page") or 1
        jobs += [(ds, p) for p in range(2, lp + 1)]
    if jobs:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for chunk in pool.map(lambda j: A.crm_post(
                    {"date_from": j[0], "date_to": j[0], "department_ids": [dep],
                     "page": j[1], "per_page": 100}).get("dialogs", []), jobs):
                for d in chunk:
                    A.scan(d, DAY, rows, group)
    return rows, leads


for group, dep, name in DEPTS:
    rows, leads = gather(dep, group)
    ofo = [r for r in rows if r["stage"] == "ofo"]
    bot = [r for r in ofo if r["role"] == "bot"]
    man = [r for r in ofo if r["role"] == "manager"]
    cli = [r for r in ofo if r["role"] == "client"]
    acc = A.summarize(rows)

    print("=" * 78)
    print("%s — %s, за %s (просмотр назад %d дн.)" % (group, name, DAY, LOOK))
    print("=" * 78)
    print("ШАГ 1. Граница этапа: %s" % A.HANDOVER[group].pattern.replace("\\s+", " ")[:110])
    print("ШАГ 2. Сообщений в ОФОРМЛЕНИИ за день: %d" % len(ofo))
    print("        из них клиент %d, наши %d" % (len(cli), len(bot) + len(man)))
    print("ШАГ 3. Из наших исключены рассылки: %d сообщ." % acc["blast_msg"])
    print("ШАГ 4. Осталось: бот %d + менеджер %d = %d"
          % (acc["ofo_bot"], acc["ofo_man"], acc["ofo_bot"] + acc["ofo_man"]))
    print("        ДОЛЯ ИИ = %d / %d = %s"
          % (acc["ofo_bot"], acc["ofo_bot"] + acc["ofo_man"],
             A.pct(acc["ofo_bot"], acc["ofo_man"])))
    print("ШАГ 5. Лидов за день (как на панели): %d, менеджеров в оформлении: %d -> %s на человека"
          % (leads, len(acc["mgr_ofo"]), A.per_mgr(leads, acc["mgr_ofo"])))

    print("\n  КОГО СЧИТАЕМ БОТОМ (имена отправителей):")
    for n, c in collections.Counter(r["name"] for r in bot).most_common(6):
        print("     %-34s %5d сообщ." % (n or "(без имени)", c))
    print("  КОГО СЧИТАЕМ МЕНЕДЖЕРОМ:")
    for n, c in collections.Counter(r["name"] for r in man).most_common(6):
        print("     %-34s %5d сообщ." % (n or "(без имени)", c))

    print("\n  ПРИМЕРЫ СООБЩЕНИЙ БОТА:")
    for r in random.sample(bot, min(3, len(bot))):
        print("     [%s] %s" % (r["name"][:20], r["text"][:95]))
    print("  ПРИМЕРЫ СООБЩЕНИЙ МЕНЕДЖЕРА:")
    for r in random.sample(man, min(3, len(man))):
        print("     [%s] %s" % (r["name"][:20], r["text"][:95]))
    print()
