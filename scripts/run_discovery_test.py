#!/usr/bin/env python3
"""Run discovery tests on hermes (PYTHONPATH=/opt/scrap)."""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8800"


def req(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "habr"
    if cmd == "habr":
        print("discover habr", req("POST", "/api/source-directories/3/discover", {"max_urls": 15}))
    elif cmd == "dup":
        print("discover habr again", req("POST", "/api/source-directories/3/discover", {"max_urls": 15}))
    elif cmd == "list":
        print(req("GET", "/api/discovered-urls?status=discovered"))
    elif cmd == "enqueue":
        _, data = req("GET", "/api/discovered-urls?status=discovered")
        urls = data.get("urls") or []
        if not urls:
            print("no discovered urls")
            return
        uid = urls[0]["id"]
        print("enqueue", uid, req("POST", f"/api/discovered-urls/{uid}/enqueue"))
    elif cmd == "ignore":
        _, data = req("GET", "/api/discovered-urls?status=discovered")
        urls = data.get("urls") or []
        if not urls:
            print("no discovered urls")
            return
        uid = urls[0]["id"]
        print("ignore", uid, req("POST", f"/api/discovered-urls/{uid}/ignore"))
    elif cmd == "sitemap":
        print("discover sotbit", req("POST", "/api/source-directories/2/discover", {"max_urls": 10}))


if __name__ == "__main__":
    main()
