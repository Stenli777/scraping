#!/usr/bin/env python3
"""Stage 2G publish hardening tests (API only)."""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8800"
DOC_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def api(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw.decode()
        return e.code, detail


def main():
    print("readiness", api("GET", f"/api/documents/{DOC_ID}/publish-readiness"))
    tid = 1
    _, targets = api("GET", "/api/publish-targets")
    if targets.get("targets"):
        tid = targets["targets"][0]["id"]
    print("publish dry-run", api("POST", f"/api/documents/{DOC_ID}/publish-draft", {"publish_target_id": tid, "dry_run": True}))
    print("duplicate attempt", api("POST", f"/api/documents/{DOC_ID}/publish-draft", {"publish_target_id": tid, "dry_run": False}))
    print("force attempt", api("POST", f"/api/documents/{DOC_ID}/publish-draft", {"publish_target_id": tid, "force": True}))


if __name__ == "__main__":
    main()
