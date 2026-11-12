# -*- coding: utf-8 -*-
"""Сводит выгрузки get_dialogs (по списку клиентов) в один файл и считает когорту.

Выгрузки get_dialogs сохраняются инструментом в tool-results; здесь мы их
просто собираем по customer_id и считаем долю ИИ по правилам method.py.
"""
import collections, glob, gzip, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import method as M

RESULTS = (r"C:\Users\Менеджер\.claude\projects\C--Users---------"
           r"\f65b89dc-e878-4160-91e0-e0dbfc0a12d0\tool-results")
f = lambda x: format(int(round(x)), ",d").replace(",", " ")

DAY_H = sys.argv[1] if len(sys.argv) > 1 else "2026-11-11"
SINCE = sys.argv[2] if len(sys.argv) > 2 else "2026-08-01"   # ИИ внедрён с августа
DEP = int(sys.argv[3]) if len(sys.argv) > 3 else 122

want = {x["customer_id"] for x in
        json.load(open(os.path.join(HERE, "handover_%d_%s.json" % (DEP, DAY_H)),
                       encoding="utf-8"))}

# --- собираем всё, что выгрузили инструментом ---
got = {}
for p in glob.glob(os.path.join(RESULTS, "*get_dialogs*.txt")):
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for c in (d.get("data") or []):
        cid = c.get("customer_id")
        if cid in want:
            got[cid] = c

os.makedirs(os.path.join(HERE, "dialogs_by_id"), exist_ok=True)
out = os.path.join(HERE, "dialogs_by_id", "handover_%d_%s.json.gz" % (DEP, DAY_H))
with gzip.open(out, "wt", encoding="utf-8") as fh:
    json.dump(list(got.values()), fh, ensure_ascii=False)

print("Заказов переведено на ведение %s: %d клиентов" % (DAY_H, len(want)))
print("Собрано переписок: %d" % len(got))
missing = want - set(got)
if missing:
    print("Не выгружено: %d (%s)" % (len(missing), ", ".join(str(x) for x in sorted(missing))))
print()

# --- считаем ---
cut = datetime.strptime(DAY_H, "%Y-%m-%d").date()
CUT = datetime.combine(cut, datetime.max.time()).replace(tzinfo=A.MSK)

groups = {"с августа": [], "до августа": []}
for cid, c in got.items():
    came = str(c.get("created_at") or "")[:10]
    groups["с августа" if came >= SINCE else "до августа"].append((cid, came, c))

print("%-14s %8s %9s %10s %9s %8s" % ("когорта", "клиентов", "ИИ", "менеджеры", "доля ИИ", "на чел."))
print("-" * 64)
totals = {}
for name in ("с августа", "до августа"):
    rows = groups[name]
    ai = man = skip = 0
    for cid, came, c in rows:
        for m in c.get("messages") or []:
            # в этой выгрузке время сообщения лежит в created_at, формат ISO
            raw = str(m.get("created_at") or m.get("sent_at") or "")
            t = A.parse_dt(raw[:19].replace("T", " "))
            if not t or t > CUT:
                continue
            r = M.who(m)
            if r == "ai": ai += 1
            elif r == "manager": man += 1
            elif r == "skip": skip += 1
    totals[name] = (len(rows), ai, man)
    print("%-14s %8d %9s %10s %9s %8.1f" %
          (name, len(rows), f(ai), f(man), M.share(ai, man),
           (ai + man) / max(1, len(rows))))

n1, a1, m1 = totals["с августа"]
n2, a2, m2 = totals["до августа"]
print("-" * 64)
print("%-14s %8d %9s %10s %9s" % ("всего", n1 + n2, f(a1 + a2), f(m1 + m2),
                                  M.share(a1 + a2, m1 + m2)))
print()
print("Когда пришли клиенты с августа:")
cnt = collections.Counter(came[:7] for _, came, _ in groups["с августа"])
for k in sorted(cnt):
    print("   %s — %d" % (k, cnt[k]))
if groups["до августа"]:
    print("Когда пришли клиенты до августа:")
    for cid, came, _ in sorted(groups["до августа"], key=lambda x: x[1]):
        print("   %s — %s" % (came, cid))
