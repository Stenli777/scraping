#!/usr/bin/env python3
"""Smoke: operational incidents + recovery payloads (Ops Stability Phase)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    failures = 0
    from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
    from app.db.session import SessionLocal
    from app.services.operational_incident_service import (
        MAX_INCIDENT_ROWS,
        build_incident_history,
        sync_incidents_from_runtime,
    )
    from app.services.runtime_diagnostics_service import build_recovery_playbook, build_runtime_diagnostics

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
        n = sync_incidents_from_runtime(db)
        db.commit()
        print(f"[PASS] sync_incidents recorded={n}")

        hist = build_incident_history(db)
        if not hist.get("not_ticketing"):
            print("[FAIL] not_ticketing")
            failures += 1
        else:
            print("[PASS] incident_history_flags")

        diag = build_runtime_diagnostics(db)
        for key in ("incident_history", "recovery_playbook", "runtime_hygiene"):
            if key not in diag:
                print(f"[FAIL] diagnostics_{key}")
                failures += 1
            else:
                print(f"[PASS] diagnostics_{key}")

        rb = build_recovery_playbook(db)
        if "scenarios" not in rb:
            print("[FAIL] recovery_scenarios")
            failures += 1
        else:
            print("[PASS] recovery_playbook")

        if MAX_INCIDENT_ROWS < 50:
            print("[FAIL] retention_constants")
            failures += 1
        else:
            print("[PASS] retention_constants")
    finally:
        db.close()

    if failures:
        print("=== FAIL ===")
        return 1
    print("=== PASS: operational incidents ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
