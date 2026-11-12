# -*- coding: utf-8 -*-
"""Две когорты по одному отделу, с показом каждого шага расчёта.

python -I razbor.py 2026-11-11 2026-11-10 [отдел]
   первый аргумент  — день перевода на ведение (когорта 1)
   второй аргумент  — день прихода лидов       (когорта 2)
"""
import collections, json, os, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import fetch_cache as F
import method as M

DAY_H = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()     # перевод на ведение
DAY_L = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()     # приход лидов
DEP = int(sys.argv[3]) if len(sys.argv) > 3 else 122
NAME = dict((d[1], d[2]) for d in A.DEPARTMENTS)[DEP]
f = lambda x: format(int(round(x)), ",d").replace(",", " ")

hmap = {int(k): v for k, v in
        json.load(open(os.path.join(HERE, "handover_map_%d.json" % DEP),
                       encoding="utf-8")).items()}


def count(dlg, cut):
    """Сколько сообщений ИИ / менеджеров / клиента до границы cut."""
    ai = man = cli = skip = 0
    for m in dlg.get("messages") or []:
        t = A.parse_dt(m.get("sent_at") or "")
        if not t or (cut and t > cut):
            continue
        r = M.who(m)
        if r == "ai": ai += 1
        elif r == "manager": man += 1
        elif r == "client": cli += 1
        else: skip += 1
    return ai, man, cli, skip


def edge(day):
    """Конец дня — граница оформления (поле хранит дату без времени)."""
    return datetime.combine(day, datetime.max.time()).replace(tzinfo=A.MSK)


# =====================================================================
print("=" * 78)
print("КОГОРТА 1. ЗАКАЗЫ, ПЕРЕШЕДШИЕ НА ВЕДЕНИЕ %s — %s" % (DAY_H, NAME))
print("=" * 78)

orders = json.load(open(os.path.join(HERE, "handover_%d_%s.json" % (DEP, DAY_H)),
                        encoding="utf-8"))
want = {o["customer_id"] for o in orders}
print("шаг 1. в CRM заказов с датой перевода %s: %d (клиентов %d)"
      % (DAY_H, len(orders), len(want)))

EDGE = datetime.strptime(M.AI_SINCE, "%Y-%m-%d").date()
days = (DAY_H - EDGE).days + 1
found = {}
for dump in F.fetch_range(DEP, DAY_H, days, verbose=False):
    came = datetime.strptime(dump["date"], "%Y-%m-%d").date()
    for d in dump["dialogs"]:
        cid = d.get("customer_id")
        if cid in want and cid not in found:
            found[cid] = (came, d)
print("шаг 2. из них лид пришёл не раньше %s (внедрение ИИ): %d" % (EDGE, len(found)))
print("        отсеяно как пришедшие до ИИ: %d" % (len(want) - len(found)))

ai = man = cli = skip = 0
per = []
for cid, (came, d) in found.items():
    a, m, c, s = count(d, edge(DAY_H))
    ai += a; man += m; cli += c; skip += s
    per.append((cid, came, a, m))
print("шаг 3. считаем их сообщения до конца дня перевода:")
print("        ИИ %s, менеджеры %s, клиенты %s (не в счёт), роповские %s (выкинуты)"
      % (f(ai), f(man), f(cli), f(skip)))
print()
print("   >>> ДОЛЯ ИИ В ОФОРМЛЕНИИ: %s   (%s / (%s + %s))"
      % (M.share(ai, man), f(ai), f(ai), f(man)))
print()
print("   на одного клиента: %.1f сообщ. ИИ, %.1f менеджера"
      % (ai / max(1, len(found)), man / max(1, len(found))))
print("   без единого сообщения ИИ: %d из %d" % (sum(1 for x in per if x[2] == 0), len(per)))
print("   без единого сообщения менеджера: %d из %d" % (sum(1 for x in per if x[3] == 0), len(per)))
buckets = collections.Counter()
for _, c, _, _ in per:
    d_ = (DAY_H - c).days
    buckets["0-7 дней" if d_ <= 7 else "8-30 дней" if d_ <= 30
            else "31-60 дней" if d_ <= 60 else "больше 60"] += 1
print("   от прихода лида до перевода: "
      + ", ".join("%s — %d" % (b, buckets[b])
                  for b in ("0-7 дней", "8-30 дней", "31-60 дней", "больше 60")
                  if buckets[b]))

# =====================================================================
print()
print("=" * 78)
print("КОГОРТА 2. ВСЕ ЛИДЫ, ПРИШЕДШИЕ %s — %s" % (DAY_L, NAME))
print("=" * 78)
dump = F.fetch_range(DEP, DAY_L, 1, verbose=False)[0]
dialogs = dump["dialogs"]
print("шаг 1. лидов пришло: %s (столько же, сколько на панели CRM)" % f(dump["leads_total"]))

ai2 = man2 = cli2 = skip2 = 0
reached = 0
sp = {"reached": collections.Counter(), "open": collections.Counter()}
only_ai = only_man = 0
for d in dialogs:
    cid = d.get("customer_id")
    h = hmap.get(cid)
    cut = edge(datetime.strptime(h, "%Y-%m-%d").date()) if h else None
    a, m, c, s = count(d, cut)
    ai2 += a; man2 += m; cli2 += c; skip2 += s
    key = "reached" if h else "open"
    sp[key]["ai"] += a; sp[key]["man"] += m; sp[key]["n"] += 1
    if h: reached += 1
    if a and not m: only_ai += 1
    if m and not a: only_man += 1
print("шаг 2. из них уже перешли на ведение: %d (%.1f%%) — им режем по дню перехода,"
      % (reached, 100.0 * reached / max(1, len(dialogs))))
print("        остальным %d берём всю переписку, они ещё в оформлении"
      % (len(dialogs) - reached))
print("шаг 3. сообщения:")
print("        ИИ %s, менеджеры %s, клиенты %s (не в счёт), роповские %s (выкинуты)"
      % (f(ai2), f(man2), f(cli2), f(skip2)))
print()
print("   >>> ДОЛЯ ИИ В ОФОРМЛЕНИИ: %s   (%s / (%s + %s))"
      % (M.share(ai2, man2), f(ai2), f(ai2), f(man2)))
print()
print("   внутри этой цифры:")
for k, label in (("reached", "перешли на ведение"), ("open", "ещё в оформлении ")):
    s = sp[k]
    print("      %s %5d чел. — ИИ %6s, менеджеры %6s -> %s"
          % (label, s["n"], f(s["ai"]), f(s["man"]), M.share(s["ai"], s["man"])))
print()
print("   вёл только ИИ, менеджер не писал ни разу: %d лидов" % only_ai)
print("   вёл только менеджер, без ИИ: %d лидов" % only_man)
print("   на одного лида: %.1f сообщ. ИИ, %.1f менеджера"
      % (ai2 / max(1, len(dialogs)), man2 / max(1, len(dialogs))))
