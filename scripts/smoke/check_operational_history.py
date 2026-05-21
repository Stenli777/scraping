#!/usr/bin/env python3
"""Smoke: operational history / snapshots (Phase D)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    failures = 0

    from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
    from app.db.session import SessionLocal
    from app.models.operational_snapshot import OperationalSnapshot
    from app.services.operational_snapshot_service import (
        MAX_SNAPSHOT_ROWS,
        RETENTION_DAYS,
        build_operational_history,
        capture_operational_snapshot,
        cleanup_old_snapshots,
    )
    from app.services.runtime_diagnostics_service import build_runtime_diagnostics

    if is_automation_enabled():
        print("[FAIL] automation_disabled")
        failures += 1
    else:
        print("[PASS] automation_disabled")

    if is_auto_publish_enabled():
        print("[FAIL] auto_publish_disabled")
        failures += 1
    else:
        print("[PASS] auto_publish_disabled")

    db = SessionLocal()
    try:
        snap = capture_operational_snapshot(db, source="smoke", force=True)
        db.commit()
        if not snap:
            print("[FAIL] snapshot_capture")
            failures += 1
        else:
            print("[PASS] snapshot_capture")

        hist = build_operational_history(db)
        for key in ("queue_trends", "llm_trends", "drift_history", "incident_memory"):
            if key not in hist:
                print(f"[FAIL] history_{key}")
                failures += 1
            else:
                print(f"[PASS] history_{key}")

        if not hist.get("not_metrics_platform"):
            print("[FAIL] not_metrics_platform_flag")
            failures += 1
        else:
            print("[PASS] bounded_history_flags")

        diag = build_runtime_diagnostics(db)
        if "operational_history" not in diag:
            print("[FAIL] diagnostics_includes_history")
            failures += 1
        else:
            print("[PASS] diagnostics_includes_history")

        deleted = cleanup_old_snapshots(db)
        db.commit()
        print(f"[PASS] cleanup_ran deleted={deleted}")

        if RETENTION_DAYS < 1 or MAX_SNAPSHOT_ROWS < 10:
            print("[FAIL] retention_constants")
            failures += 1
        else:
            print("[PASS] retention_constants")

        row = db.get(OperationalSnapshot, snap.id) if snap else None
        if row and row.metrics_json:
            bad = [k for k in row.metrics_json if "token" in k.lower() or "secret" in k.lower()]
            if bad:
                print(f"[FAIL] snapshot_no_secrets keys={bad}")
                failures += 1
            else:
                print("[PASS] snapshot_no_secrets")
    finally:
        db.close()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
