#!/usr/bin/env python3
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8800"


def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        BASE + path, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": json.loads(e.read())}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "discover"
    dirs = get("/api/source-directories")["directories"]
    if not dirs:
        print("no directories")
        return
    did = dirs[0]["id"]
    if mode == "discover":
        print(post(f"/api/source-directories/{did}/discover", {"max_urls": 10}))
    elif mode == "disabled":
        print("check ENABLE_SOURCE_DISCOVERY=false first")
    else:
        urls = get("/api/discovered-urls?status=discovered")
        print(urls)
        if urls.get("urls"):
            uid = urls["urls"][0]["id"]
            print("enqueue", post(f"/api/discovered-urls/{uid}/enqueue"))


if __name__ == "__main__":
    main()
