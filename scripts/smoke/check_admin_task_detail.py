#!/usr/bin/env python3
"""Smoke: admin task detail page returns 200 when tasks exist."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")


def main() -> int:
    from app.db.session import SessionLocal
    from app.models.scraping_task import ScrapingTask

    db = SessionLocal()
    try:
        task = db.query(ScrapingTask).order_by(ScrapingTask.id.desc()).first()
        if not task:
            print("[PASS] admin_task_detail — skip (no tasks in DB)")
            return 0
        task_id = task.id
    finally:
        db.close()

    path = f"/admin/tasks/{task_id}"
    try:
        req = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except Exception as exc:
        print(f"[FAIL] admin_task_detail {path} — {exc}")
        return 1

    ok = code == 200
    print(f"[{'PASS' if ok else 'FAIL'}] admin_task_detail {path} — {code}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
