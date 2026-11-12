# -*- coding: utf-8 -*-
"""Два среза по всем отделам: доля ИИ по всем лидам и по дошедшим до заказа."""
import sys, collections
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\Менеджер\nika-bot")
import ai_share_daily as A

LAST = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
DEPTS = [("КНИГИ", 122, "Алина и Регина"),
         ("СТАТУЭТКИ", 126, "Зарина"),
         ("СТАТУЭТКИ", 128, "Диана и София"),
         ("СТАТУЭТКИ", 127, "Ангелина"),
         ("ПОРТРЕТЫ", 10, "Настя и Руслан")]

print("КОГОРТА ЛИДОВ %s — %s\n"
      % ((LAST - timedelta(days=DAYS - 1)).strftime("%d.%m"), LAST.strftime("%d.%m")))
print("%-18s %7s %9s %12s %12s %12s"
      % ("отдел", "лидов", "дошли", "ИИ все лиды", "ИИ дошедшие", "ИИ ведение"))
print("-" * 76)
summary = []
for group, dep, name in DEPTS:
    leads, dialogs, jobs = 0, [], []
    for i in range(DAYS):
        ds = (LAST - timedelta(days=i)).strftime("%Y-%m-%d")
        first = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [dep],
                            "page": 1, "per_page": 100})
        leads += (first.get("pagination") or {}).get("total") or 0
        dialogs += first.get("dialogs", [])
        lp = (first.get("pagination") or {}).get("last_page") or 1
        jobs += [(ds, p) for p in range(2, lp + 1)]
    if jobs:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for chunk in pool.map(lambda j: A.crm_post(
                    {"date_from": j[0], "date_to": j[0], "department_ids": [dep],
                     "page": j[1], "per_page": 100}).get("dialogs", []), jobs):
                dialogs += chunk

    seen, rows, reached = set(), [], 0
    for d in dialogs:
        cut = A.split_point(d, group)
        if cut:
            reached += 1
        cid = d.get("customer_id")
        msgs = sorted([(A.parse_dt(m.get("sent_at") or ""), m)
                       for m in (d.get("messages") or [])
                       if A.parse_dt(m.get("sent_at") or "")], key=lambda x: x[0])
        last_client = None
        for t, m in msgs:
            mid = m.get("message_id")
            if mid in seen:
                continue
            seen.add(mid)
            r = A.role(m)
            rows.append({"cid": cid, "t": t, "role": r,
                         "stage": "ved" if (cut and t > cut) else "ofo",
                         "name": str(m.get("sender_name") or "").strip(),
                         "text": " ".join(str(m.get("text") or "").split()),
                         "reached": bool(cut),
                         "since_client": (None if last_client is None else
                                          (t - last_client).total_seconds() / 3600.0)})
            if r == "client":
                last_client = t

    a_all = A.summarize(rows)
    a_rch = A.summarize([r for r in rows if r["reached"]])
    row = (name, leads, reached, 100.0 * reached / max(1, len(dialogs)),
           A.pct(a_all["ofo_bot"], a_all["ofo_man"]),
           A.pct(a_rch["ofo_bot"], a_rch["ofo_man"]),
           A.pct(a_rch["ved_bot"], a_rch["ved_man"]),
           len(a_all["mgr_ofo"]), a_all, a_rch)
    summary.append(row)
    print("%-18s %7d %5d(%3.0f%%) %12s %12s %12s"
          % (name, leads, reached, row[3], row[4], row[5], row[6]), flush=True)

print("\nПОДРОБНО")
for (name, leads, reached, pc, p1, p2, p3, nmgr, a_all, a_rch) in summary:
    print("\n%s — лидов %d, дошли до заказа %d (%.0f%%)" % (name, leads, reached, pc))
    print("   все лиды, оформление: бот %d + менеджер %d  ->  %s"
          % (a_all["ofo_bot"], a_all["ofo_man"], p1))
    print("   дошедшие, оформление: бот %d + менеджер %d  ->  %s"
          % (a_rch["ofo_bot"], a_rch["ofo_man"], p2))
    print("   дошедшие, ведение:    бот %d + менеджер %d  ->  %s"
          % (a_rch["ved_bot"], a_rch["ved_man"], p3))
    print("   менеджеров в оформлении: %d  ->  %s лидов на человека"
          % (nmgr, A.per_mgr(leads, a_all["mgr_ofo"])))
