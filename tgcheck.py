#!/usr/bin/env python3
import json, os, urllib.request, urllib.error

TG = os.environ["TG_TOKEN"]
CHAT = int(os.environ.get("TG_CHAT_ID") or 0)


def call(method, payload=None):
    url = "https://api.telegram.org/bot%s/%s" % (TG, method)
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data else "GET",
        headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"HTTPError": e.code, "body": e.read().decode("utf-8", "replace")[:400]}
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


print("--- getMe ---")
me = call("getMe")
print(json.dumps(me.get("result", me), ensure_ascii=False)[:200])

print("\n--- getChat (is the chat reachable?) ---")
c = call("getChat", {"chat_id": CHAT})
print(json.dumps(c, ensure_ascii=False)[:400])

print("\n--- sendMessage probe ---")
s = call("sendMessage", {"chat_id": CHAT,
                         "text": "Проверка доставки — если вы видите это сообщение, канал работает."})
if s.get("ok"):
    r = s["result"]
    print("OK: message_id=%s date=%s chat=%s" % (r.get("message_id"), r.get("date"),
                                                 r.get("chat", {}).get("id")))
else:
    print(json.dumps(s, ensure_ascii=False)[:400])

print("\n--- getUpdates (incoming events / blocks) ---")
u = call("getUpdates", {"limit": 20, "offset": -20})
if u.get("ok"):
    for upd in u["result"]:
        for k in ("message", "my_chat_member", "edited_message"):
            if k in upd:
                v = upd[k]
                who = v.get("from", {}).get("username")
                print("  %-16s from=%s %s" % (k, who,
                      json.dumps(v.get("new_chat_member") or v.get("text") or "",
                                 ensure_ascii=False)[:120]))
else:
    print(json.dumps(u, ensure_ascii=False)[:300])
