#!/usr/bin/env python3
"""Stage 2D publish tests."""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8800"
DOC_ID = 6


def post(path: str, data: dict | None = None) -> dict:
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "detail": json.loads(e.read())}


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry_run"
    print("health", get("/health"))
    if mode == "dry_run":
        print(post(f"/api/documents/{DOC_ID}/publish-draft", {"dry_run": True}))
    elif mode == "no_seo":
        print("doc 1 (expect 400):", post("/api/documents/1/publish-draft", {"dry_run": True}))
    elif mode == "no_rewrite":
        print("doc 1 (expect 400):", post("/api/documents/1/publish-draft", {"dry_run": True}))
    elif mode == "webhook_fail":
        print(post(f"/api/documents/{DOC_ID}/publish-draft", {"publish_target_id": 2, "dry_run": False}))
    elif mode == "disabled":
        print("Set ENABLE_PUBLISHING=false and restart first")
    else:
        print("modes: dry_run no_seo no_rewrite")


if __name__ == "__main__":
    main()
