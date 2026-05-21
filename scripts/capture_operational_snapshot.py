#!/usr/bin/env python3
"""Capture one operational snapshot (cron/manual). Safe, bounded."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.operational_snapshot_service import capture_operational_snapshot


def main() -> int:
    db = SessionLocal()
    try:
        snap = capture_operational_snapshot(db, source="script", force=True)
        db.commit()
        if snap:
            print(f"[PASS] snapshot #{snap.id} captured")
            return 0
        print("[PASS] throttled (recent snapshot exists)")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[FAIL] {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
