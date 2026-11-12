#!/usr/bin/env python3
"""Validate check_pings detection against locally saved exports (no network)."""
import json, os, sys, glob
os.environ["PING_DRY_RUN"] = "1"
os.environ["PING_WINDOW_START"] = "2026-07-27 00:00:00"
os.environ["PING_WINDOW_END"] = "2026-07-28 00:00:00"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_pings as cp

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CACHE = {}
for f in glob.glob(os.path.join(DATA, "dialogs_*.json")):
    day = os.path.basename(f)[len("dialogs_"):-len(".json")]
    with open(f, encoding="utf-8-sig") as fh:
        CACHE[day] = json.load(fh)
print("local days available:", sorted(CACHE))

calls = {"n": 0}


def fake_post(payload, retries=3):
    calls["n"] += 1
    day = payload["date_from"]
    dialogs = CACHE.get(day, [])
    per = payload["per_page"]
    page = payload["page"]
    chunk = dialogs[(page - 1) * per: page * per]
    last = max(1, -(-len(dialogs) // per))
    return {"status": "ok", "pagination": {"page": page, "per_page": per,
                                           "total": len(dialogs), "last_page": last},
            "dialogs": chunk}


cp.crm_post = fake_post
cp.LOOKBACK_DAYS = 9
cp.main()
print("fake API calls:", calls["n"])
