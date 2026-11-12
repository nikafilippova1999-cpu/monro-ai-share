# -*- coding: utf-8 -*-
"""Выгрузка диалогов отдела с кэшем на диск.

Выгрузка идёт по дате СОЗДАНИЯ клиента — других фильтров API не даёт.
Один день одного отдела складываем в cache/dlg_<dep>_<ГГГГ-ММ-ДД>.json.gz,
чтобы пересчитывать методику сколько угодно раз без повторной выгрузки.
"""
import gzip, json, os, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)

sys.path.insert(0, HERE)
import ai_share_daily as A


def path(dep, ds):
    return os.path.join(CACHE, "dlg_%d_%s.json.gz" % (dep, ds))


def fetch_day(dep, ds, workers=6, verbose=True):
    """Все диалоги клиентов, созданных в этот день. Берёт из кэша, если он есть."""
    p = path(dep, ds)
    if os.path.exists(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)

    first = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [dep],
                        "page": 1, "per_page": 100})
    if first.get("_error"):
        raise RuntimeError("%s %s: %s" % (dep, ds, first["_error"]))
    pg = first.get("pagination") or {}
    dialogs = list(first.get("dialogs", []))
    last = pg.get("last_page") or 1
    if last > 1:
        def work(page):
            r = A.crm_post({"date_from": ds, "date_to": ds, "department_ids": [dep],
                            "page": page, "per_page": 100})
            if r.get("_error"):
                raise RuntimeError("%s %s p%d: %s" % (dep, ds, page, r["_error"]))
            return r.get("dialogs", [])
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for chunk in pool.map(work, range(2, last + 1)):
                dialogs += chunk

    out = {"dep": dep, "date": ds, "leads_total": pg.get("total") or 0,
           "dialogs": dialogs}
    tmp = p + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, p)
    if verbose:
        print("  выгружен %s: лидов %d, диалогов %d"
              % (ds, out["leads_total"], len(dialogs)), flush=True)
    return out


def fetch_range(dep, last_day, days, verbose=True):
    """Список дневных выгрузок за последние `days` дней, считая last_day включительно."""
    from datetime import timedelta
    res = []
    for i in range(days):
        ds = (last_day - timedelta(days=i)).strftime("%Y-%m-%d")
        res.append(fetch_day(dep, ds, verbose=verbose))
    return res


if __name__ == "__main__":
    from datetime import datetime
    dep = int(sys.argv[1])
    last_day = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    days = int(sys.argv[3])
    print("выгрузка отдела %d за %d дн. до %s" % (dep, days, last_day), flush=True)
    tot_l = tot_d = 0
    for d in fetch_range(dep, last_day, days):
        tot_l += d["leads_total"]
        tot_d += len(d["dialogs"])
    print("готово: лидов %d, диалогов %d" % (tot_l, tot_d), flush=True)
