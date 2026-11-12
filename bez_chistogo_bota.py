# -*- coding: utf-8 -*-
"""Когорта лидов за день без тех, кого бот вёл в одиночку.

Оставляем только клиентов, где менеджер написал хотя бы раз, и считаем
долю ИИ и долю менеджера по ним.

python -I bez_chistogo_bota.py 2026-11-10 [отдел]
"""
import collections, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import fetch_cache as F
import method as M

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEP = int(sys.argv[2]) if len(sys.argv) > 2 else 122
NAME = dict((d[1], d[2]) for d in A.DEPARTMENTS)[DEP]
f = lambda x: format(int(round(x)), ",d").replace(",", " ")

hp = os.path.join(HERE, "handover_map_%d.json" % DEP)
hmap = ({int(k): v for k, v in json.load(open(hp, encoding="utf-8")).items()}
        if os.path.exists(hp) else {})

dump = F.fetch_range(DEP, DAY, 1, verbose=False)[0]
dialogs = dump["dialogs"]

rows = []
for d in dialogs:
    cid = d.get("customer_id")
    h = hmap.get(cid)
    cut = (datetime.combine(datetime.strptime(h, "%Y-%m-%d").date(),
                            datetime.max.time()).replace(tzinfo=A.MSK)
           if h else None)
    ai = man = cli = 0
    for m in d.get("messages") or []:
        t = A.parse_dt(m.get("sent_at") or "")
        if not t or (cut and t > cut):
            continue
        r = M.who(m)
        if r == "ai": ai += 1
        elif r == "manager": man += 1
        elif r == "client": cli += 1
    rows.append({"cid": cid, "ai": ai, "man": man, "cli": cli, "reached": bool(h)})

n = len(rows)
only_bot = [r for r in rows if r["man"] == 0 and r["ai"] > 0]
nobody = [r for r in rows if r["man"] == 0 and r["ai"] == 0]
with_man = [r for r in rows if r["man"] > 0]

print("ОФОРМЛЕНИЕ. %s. Лиды, пришедшие %s" % (NAME, DAY))
print("=" * 72)
print("всего лидов:                          %s" % f(dump["leads_total"]))
print("из них бот вёл в одиночку:            %s  (убираем)" % f(len(only_bot)))
print("никто не написал ни слова:            %s  (убираем)" % f(len(nobody)))
print("осталось — где менеджер вмешался:     %s  (%.0f%% от всех)"
      % (f(len(with_man)), 100.0 * len(with_man) / max(1, n)))
print()

ai = sum(r["ai"] for r in with_man)
man = sum(r["man"] for r in with_man)
cli = sum(r["cli"] for r in with_man)
print("=" * 72)
print("ПО ЭТИМ %s КЛИЕНТАМ" % f(len(with_man)))
print("=" * 72)
print("   сообщений ИИ:         %6s   ->  ДОЛЯ ИИ        %s"
      % (f(ai), M.share(ai, man)))
print("   сообщений менеджеров: %6s   ->  ДОЛЯ МЕНЕДЖЕРА %s"
      % (f(man), M.share(man, ai)))
print("   сообщений клиентов:   %6s   (в дробь не входят)" % f(cli))
print()
print("   на одного клиента: %.1f сообщ. ИИ, %.1f менеджера, %.1f клиента"
      % (ai / max(1, len(with_man)), man / max(1, len(with_man)),
         cli / max(1, len(with_man))))
print("   дошли до ведения: %d" % sum(1 for r in with_man if r["reached"]))

# для сравнения — что было до отсечки
ai_all = sum(r["ai"] for r in rows)
man_all = sum(r["man"] for r in rows)
print()
print("для сравнения, по всем %s лидам: ИИ %s, менеджеры %s -> доля ИИ %s"
      % (f(n), f(ai_all), f(man_all), M.share(ai_all, man_all)))
print("бот в одиночку написал %s сообщений — это %.0f%% всей его работы"
      % (f(sum(r["ai"] for r in only_bot)),
         100.0 * sum(r["ai"] for r in only_bot) / max(1, ai_all)))

# насколько глубоко бот доводит в одиночку
print()
print("СКОЛЬКО СООБЩЕНИЙ БОТ УСПЕВАЕТ ДО ПОДКЛЮЧЕНИЯ ЧЕЛОВЕКА:")
b = collections.Counter()
for r in only_bot:
    k = r["ai"]
    b["1-2" if k <= 2 else "3-5" if k <= 5 else "6-10" if k <= 10 else "больше 10"] += 1
for k in ("1-2", "3-5", "6-10", "больше 10"):
    if b[k]:
        print("   %-10s %4d клиентов, которых бот вёл один" % (k, b[k]))
