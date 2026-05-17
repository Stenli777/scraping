#!/usr/bin/env python3
"""Stage 2C tests — run on server: PYTHONPATH=/opt/scrap python scripts/test_2c_review_seo.py [review|seo|flags_off|degraded]"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8800"
DOC_ID = 6


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return json.loads(r.read())


def post(path: str) -> dict:
    req = urllib.request.Request(BASE + path, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "review"
    print("health", get("/health"))
    print("ready", get("/health/ready"))

    if mode == "review":
        print("run-review", post(f"/api/documents/{DOC_ID}/run-review"))
    elif mode == "seo":
        print("run-seo", post(f"/api/documents/{DOC_ID}/run-seo"))
    elif mode == "flags_off":
        print("flags test — verify pipeline still works (create task via API manually)")
    elif mode == "degraded":
        print("degraded — run review after breaking CLIPROXYAPI_BASE_URL in .env")
    else:
        print("Usage: test_2c_review_seo.py [review|seo|flags_off|degraded]")
        sys.exit(1)


if __name__ == "__main__":
    main()
