#!/usr/bin/env python3
"""Smoke: admin release candidate detail — HTTP 200 and operator-facing HTML markers."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")

MARKERS_ANY = (
    "Что сейчас",
    "О странице",
)
MARKERS_ALL = (
    "Следующий шаг",
    "Блокирующие проблемы",
    "Проверка черновика",
)


def main() -> int:
    from app.db.session import SessionLocal
    from app.models.content_release_candidate import ContentReleaseCandidate

    db = SessionLocal()
    try:
        rc = db.query(ContentReleaseCandidate).order_by(ContentReleaseCandidate.id.desc()).first()
        if not rc:
            print("[PASS] admin_release_candidate_detail — skip (no release candidates in DB)")
            return 0
        candidate_id = rc.id
    finally:
        db.close()

    path = f"/admin/release-candidates/{candidate_id}"
    try:
        req = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
    except Exception as exc:
        print(f"[FAIL] admin_release_candidate_detail {path} — {exc}")
        return 1

    if code != 200:
        print(f"[FAIL] admin_release_candidate_detail {path} — HTTP {code}")
        return 1

    if not any(m in body for m in MARKERS_ANY):
        print(f"[FAIL] admin_release_candidate_detail {path} — missing summary marker (need one of {MARKERS_ANY})")
        return 1

    missing_all = [m for m in MARKERS_ALL if m not in body]
    if missing_all:
        print(f"[FAIL] admin_release_candidate_detail {path} — missing marker(s): {missing_all}")
        return 1

    print(f"[PASS] admin_release_candidate_detail {path} — 200 + operator markers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
