# -*- coding: utf-8 -*-
"""Кто вообще пишет клиентам в отделе и как выглядит фраза «Спасибо за заказ»."""
import collections, gzip, io, json, os, re, sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DEP = int(sys.argv[1]) if len(sys.argv) > 1 else 122
files = sorted(f for f in os.listdir(os.path.join(HERE, "cache"))
               if f.startswith("dlg_%d_" % DEP))

by_name = collections.Counter()
types_of = collections.defaultdict(collections.Counter)
spasibo = collections.Counter()
RX = re.compile(r"спасибо\s+за\s+заказ", re.I)

for fn in files:
    with gzip.open(os.path.join(HERE, "cache", fn), "rt", encoding="utf-8") as f:
        dump = json.load(f)
    for d in dump["dialogs"]:
        for m in d.get("messages") or []:
            st = str(m.get("sender_type") or "")
            if st == "client":
                continue
            nm = str(m.get("sender_name") or "").strip() or "(без имени)"
            by_name[nm] += 1
            types_of[nm][st] += 1
            txt = " ".join(str(m.get("text") or "").split())
            if RX.search(txt):
                spasibo[txt[:150]] += 1

print("Файлов в кэше: %d (%s)\n" % (len(files), ", ".join(f[8:18] for f in files)))
print("=" * 78)
print("ВСЕ, КТО ПИШЕТ КЛИЕНТАМ (кроме самих клиентов)")
print("=" * 78)
print("%-40s %8s  %s" % ("имя отправителя", "сообщ.", "sender_type"))
for nm, c in by_name.most_common(60):
    tp = ", ".join("%s:%d" % kv for kv in types_of[nm].most_common())
    print("%-40s %8d  %s" % (nm[:40], c, tp))

print()
print("=" * 78)
print("ВАРИАНТЫ ФРАЗЫ «СПАСИБО ЗА ЗАКАЗ» (%d вхождений)" % sum(spasibo.values()))
print("=" * 78)
for txt, c in spasibo.most_common(15):
    print("%5d x  %s" % (c, txt))
