# -*- coding: utf-8 -*-
"""ОФОРМЛЕНИЕ: доля ИИ по клиентам, переведённым на ведение в заданный день.

Выборка: клиенты отдела, у которых точка перехода оформление -> ведение
попала на заданный день. Когда клиент пришёл — не важно, он мог прийти
и месяц назад. Считаем всю работу по его оформлению: от первого сообщения
до точки перехода.

Запуск:  python -I ofo_handover.py 2026-11-10 [отдел] [дней_назад]
"""
import collections, os, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_share_daily as A
import fetch_cache as F

DAY = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
DEP = int(sys.argv[2]) if len(sys.argv) > 2 else 122
LOOK = int(sys.argv[3]) if len(sys.argv) > 3 else 35
GROUP = dict((d[1], d[0]) for d in A.DEPARTMENTS)[DEP]
NAME = dict((d[1], d[2]) for d in A.DEPARTMENTS)[DEP]


def phrase_point(dlg):
    """Когда клиенту ушла фраза-граница этапа. Только она, без запасных вариантов."""
    rx = A.HANDOVER.get(GROUP)
    best = None
    for m in dlg.get("messages") or []:
        if A.role(m) == "client":
            continue
        if rx.search(str(m.get("text") or "")):
            t = A.parse_dt(m.get("sent_at") or "")
            if t and (best is None or t < best):
                best = t
    return best


def order_point(dlg):
    best = None
    for o in dlg.get("orders") or []:
        t = A.parse_dt(o.get("created_at") or "")
        if t and (best is None or t < best):
            best = t
    return best


# ---------- собираем ----------
print("ОФОРМЛЕНИЕ. %s (отдел %d), переход на ведение %s" % (NAME, DEP, DAY))
print("Просмотр создания клиента: %d дн. назад\n" % LOOK, flush=True)

picked = []        # (dlg, cut, created_date)  — переход по фразе в нужный день
only_order = []    # фразы нет, но заказ создан в нужный день
missing = 0
for dump in F.fetch_range(DEP, DAY, LOOK, verbose=False):
    created = datetime.strptime(dump["date"], "%Y-%m-%d").date()
    for d in dump["dialogs"]:
        p = phrase_point(d)
        if p is not None:
            if p.date() == DAY:
                picked.append((d, p, created))
            continue
        o = order_point(d)
        if o is not None and o.date() == DAY:
            only_order.append((d, o, created))

print("Клиентов с переходом %s по фразе-границе: %d" % (DAY, len(picked)))
print("Плюс без фразы, но с заказом в этот день:  %d" % len(only_order))
print()

# ---------- доля ИИ в их оформлении ----------
def rows_for(items):
    rows = []
    for d, cut, created in items:
        cid = d.get("customer_id")
        msgs = sorted([(A.parse_dt(m.get("sent_at") or ""), m)
                       for m in (d.get("messages") or [])
                       if A.parse_dt(m.get("sent_at") or "")], key=lambda x: x[0])
        last_client = None
        for t, m in msgs:
            if t > cut:                      # всё после перехода — это уже ведение
                break
            r = A.role(m)
            rows.append({"cid": cid, "t": t, "role": r, "stage": "ofo",
                         "name": str(m.get("sender_name") or "").strip(),
                         "text": " ".join(str(m.get("text") or "").split()),
                         "since_client": (None if last_client is None else
                                          (t - last_client).total_seconds() / 3600.0)})
            if r == "client":
                last_client = t
    return rows


rows = rows_for(picked)
bot = sum(1 for r in rows if r["role"] == "bot")
man = sum(1 for r in rows if r["role"] == "manager")
cli = sum(1 for r in rows if r["role"] == "client")
print("=" * 68)
print("ВСЕ СООБЩЕНИЯ ОФОРМЛЕНИЯ (рассылки внутри)")
print("=" * 68)
print("бот %d + менеджер %d = %d   ->  ДОЛЯ ИИ %s" % (bot, man, bot + man, A.pct(bot, man)))
print("сообщений клиентов: %d" % cli)
print("на одного клиента: %.1f сообщ. бота, %.1f менеджера"
      % (bot / max(1, len(picked)), man / max(1, len(picked))))

acc = A.summarize(rows)
print()
print("=" * 68)
print("ТО ЖЕ БЕЗ ВЕЕРНЫХ РАССЫЛОК (%d копий текста и молчание клиента %dч+)"
      % (A.BLAST_MIN_COPIES, A.BLAST_SILENT_HOURS))
print("=" * 68)
print("бот %d + менеджер %d = %d   ->  ДОЛЯ ИИ %s"
      % (acc["ofo_bot"], acc["ofo_man"], acc["ofo_bot"] + acc["ofo_man"],
         A.pct(acc["ofo_bot"], acc["ofo_man"])))
print("исключено рассылками: %d сообщ. в %d диалогах"
      % (acc["blast_msg"], len(acc["blast_dlg"])))
print("менеджеров участвовало: %d" % len(acc["mgr_ofo"]))

# ---------- хватает ли окна просмотра ----------
print()
print("=" * 68)
print("СКОЛЬКО ДНЕЙ ПРОШЛО ОТ ПРИХОДА ЛИДА ДО ПЕРЕХОДА")
print("=" * 68)
gap = collections.Counter((DAY - c).days for _, _, c in picked)
run = 0
for g in sorted(gap):
    run += gap[g]
    print("   %2d дн. назад пришёл — %4d клиентов   (накопительно %3d%%)"
          % (g, gap[g], 100 * run // max(1, len(picked))))

# ---------- кто есть кто ----------
print()
print("=" * 68)
print("КТО ПИСАЛ В ЭТОМ ОФОРМЛЕНИИ")
print("=" * 68)
print("  БОТ:")
for n, c in collections.Counter(r["name"] for r in rows if r["role"] == "bot").most_common(10):
    print("     %-36s %6d" % (n or "(без имени)", c))
print("  МЕНЕДЖЕРЫ:")
for n, c in collections.Counter(r["name"] for r in rows if r["role"] == "manager").most_common(15):
    print("     %-36s %6d" % (n or "(без имени)", c))

# ---------- справочно: что добавил бы запасной вариант ----------
if only_order:
    r2 = rows_for(only_order)
    b2 = sum(1 for r in r2 if r["role"] == "bot")
    m2 = sum(1 for r in r2 if r["role"] == "manager")
    print()
    print("=" * 68)
    print("СПРАВОЧНО: %d клиентов без фразы, у кого заказ создан %s" % (len(only_order), DAY))
    print("=" * 68)
    print("их оформление: бот %d + менеджер %d  ->  ДОЛЯ ИИ %s" % (b2, m2, A.pct(b2, m2)))
    print("вместе с основными: ДОЛЯ ИИ %s" % A.pct(bot + b2, man + m2))
