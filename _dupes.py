# -*- coding: utf-8 -*-
"""Проверка дублей + два честных среза: вчерашние лиды и заказы, дошедшие до ведения."""
import sys, collections
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\Менеджер\nika-bot")
import ai_share_daily as A

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEP, GROUP, NAME = 122, "КНИГИ", "Алина и Регина"

ds = DAY.strftime("%Y-%m-%d")
first = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [DEP],
                    "page": 1, "per_page": 100})
total = (first.get("pagination") or {}).get("total") or 0
lp = (first.get("pagination") or {}).get("last_page") or 1
dialogs = list(first.get("dialogs", []))
if lp > 1:
    with ThreadPoolExecutor(max_workers=6) as pool:
        for chunk in pool.map(lambda p: A.crm_post(
                {"date_from": ds, "date_to": ds, "department_ids": [DEP],
                 "page": p, "per_page": 100}).get("dialogs", []), range(2, lp + 1)):
            dialogs += chunk

print("=" * 70)
print("ПРОВЕРКА ДУБЛЕЙ — книги, лиды за %s" % ds)
print("=" * 70)
cids = [d.get("customer_id") for d in dialogs]
print("pagination.total (лидов по CRM): %d" % total)
print("записей выгружено:               %d" % len(dialogs))
print("уникальных customer_id:          %d" % len(set(cids)))
dup = [c for c, n in collections.Counter(cids).items() if n > 1]
print("клиентов, встретившихся дважды:  %d" % len(dup))

mids, msgs_total = [], 0
for d in dialogs:
    for m in d.get("messages") or []:
        msgs_total += 1
        mids.append(m.get("message_id"))
print("сообщений всего:                 %d" % msgs_total)
print("уникальных message_id:           %d" % len(set(mids)))
print("ДУБЛЕЙ СООБЩЕНИЙ:                %d" % (msgs_total - len(set(mids))))

# считаем по уникальным сообщениям
seen = set()
rows = []
reached = 0
for d in dialogs:
    cut = A.split_point(d, GROUP)
    if cut:
        reached += 1
    cid = d.get("customer_id")
    msgs = sorted([(A.parse_dt(m.get("sent_at") or ""), m)
                   for m in (d.get("messages") or []) if A.parse_dt(m.get("sent_at") or "")],
                  key=lambda x: x[0])
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
                     "since_client": (None if last_client is None
                                      else (t - last_client).total_seconds() / 3600.0)})
        if r == "client":
            last_client = t

print("\n" + "=" * 70)
print("СРЕЗ 1. ВСЕ ЛИДЫ ЗА %s (%d шт.) — этап ОФОРМЛЕНИЕ" % (ds, total))
print("=" * 70)
acc = A.summarize([r for r in rows])
b, m = acc["ofo_bot"], acc["ofo_man"]
print("бот %d + менеджер %d = %d  ->  ДОЛЯ ИИ %s" % (b, m, b + m, A.pct(b, m)))
print("рассылок исключено: %d" % acc["blast_msg"])
print("менеджеров: %d  ->  %s лидов на человека"
      % (len(acc["mgr_ofo"]), A.per_mgr(total, acc["mgr_ofo"])))

print("\n" + "=" * 70)
print("СРЕЗ 2. ТОЛЬКО ДОШЕДШИЕ ДО ВЕДЕНИЯ (%d из %d, %.1f%%)"
      % (reached, len(dialogs), 100.0 * reached / max(1, len(dialogs))))
print("=" * 70)
acc2 = A.summarize([r for r in rows if r["reached"]])
for stage, label in (("ofo", "их оформление"), ("ved", "их ведение   ")):
    bb, mm = acc2[stage + "_bot"], acc2[stage + "_man"]
    print("%s: бот %d + менеджер %d = %d  ->  ДОЛЯ ИИ %s"
          % (label, bb, mm, bb + mm, A.pct(bb, mm)))
