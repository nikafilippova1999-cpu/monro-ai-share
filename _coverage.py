# -*- coding: utf-8 -*-
"""Насколько полно каждый кандидат-маркер покрывает диалоги с заказом."""
import collections, gzip, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A

DEP = int(sys.argv[1]) if len(sys.argv) > 1 else 122

CAND = [
    ("оплата + оформляю заказ", re.compile(r"за\s+оплату.{0,40}оформля\w+\s+заказ", re.I | re.S)),
    ("просто «оформляю заказ»", re.compile(r"оформля\w+\s+заказ", re.I)),
    ("благодарю за оплату", re.compile(r"(благодар\w+|спасибо)\s+(вас\s+)?за\s+оплату", re.I)),
    ("спасибо за заказ", re.compile(r"спасибо\s+за\s+заказ", re.I)),
    ("данные на доставку СДЭК", re.compile(r"для\s+оформления\s+доставки\s+заказанн\w+\s+книги|"
                                           r"для\s+оформления\s+доставки\s+заказа", re.I)),
    ("имя и телефон для заказа", re.compile(r"для\s+оформления\s+заказа\s+мне\s+понадоб\w+", re.I)),
    ("передаю сценаристу", re.compile(r"передаю\s+пожелания\s+сценаристу", re.I)),
]

files = sorted(f for f in os.listdir(os.path.join(HERE, "cache"))
               if f.startswith("dlg_%d_" % DEP))
have_order = 0
hit = collections.Counter()
hit_noorder = collections.Counter()
no_order = 0
# насколько маркер близок к дате заказа
delta = collections.defaultdict(list)

for fn in files:
    with gzip.open(os.path.join(HERE, "cache", fn), "rt", encoding="utf-8") as f:
        dump = json.load(f)
    for d in dump["dialogs"]:
        pts = [A.parse_dt(o.get("created_at") or "") for o in (d.get("orders") or [])]
        pts = [p for p in pts if p]
        order_t = min(pts) if pts else None
        if order_t:
            have_order += 1
        else:
            no_order += 1
        texts = []
        for m in d.get("messages") or []:
            if A.role(m) == "client":
                continue
            t = A.parse_dt(m.get("sent_at") or "")
            if t:
                texts.append((t, " ".join(str(m.get("text") or "").split())))
        for label, rx in CAND:
            first = None
            for t, txt in texts:
                if rx.search(txt):
                    first = t if first is None or t < first else first
            if first is None:
                continue
            if order_t:
                hit[label] += 1
                delta[label].append((first - order_t).total_seconds() / 3600.0)
            else:
                hit_noorder[label] += 1

print("Отдел %d, дней в кэше %d" % (DEP, len(files)))
print("Диалогов с заказом в CRM: %d, без заказа: %d\n" % (have_order, no_order))
print("%-28s %12s %12s %16s" % ("маркер", "из заказов", "ложно*", "сдвиг к заказу"))
print("-" * 72)
for label, _ in CAND:
    dd = sorted(delta[label])
    med = ("%+.1f ч" % dd[len(dd) // 2]) if dd else "—"
    print("%-28s %7d (%3d%%) %12d %16s"
          % (label, hit[label], 100 * hit[label] // max(1, have_order),
             hit_noorder[label], med))
print("\n* ложно — встретился в диалоге, где заказа в CRM нет вообще")
