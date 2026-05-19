#!/usr/bin/env python3
"""Smoke: admin discovered-urls page and status filters return 200."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")

PATHS = [
    "/admin/discovered-urls",
    "/admin/discovered-urls?status=discovered",
    "/admin/discovered-urls?status=enqueued",
]


def get_status(path: str) -> tuple[int | None, str]:
    try:
        req = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        return exc.code, f"HTTP {exc.code}"
    except Exception as exc:
        return None, str(exc)


def main() -> int:
    failed = 0
    for path in PATHS:
        code, err = get_status(path)
        ok = code == 200
        label = path.replace("?", " ")
        print(f"[{'PASS' if ok else 'FAIL'}] admin_discovered {label} — {code or err}")
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
