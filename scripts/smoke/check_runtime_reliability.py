#!/usr/bin/env python3
"""Smoke: operational confidence and replay safety."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    failures = 0
    from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
    from app.db.session import SessionLocal
    from app.services.runtime_diagnostics_service import build_runtime_diagnostics
    from app.services.runtime_reliability_service import (
        build_operational_confidence,
        build_replay_safety_report,
    )

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
        conf = build_operational_confidence(db)
        if conf.get("confidence_level") not in ("high", "medium", "low", "critical"):
            print("[FAIL] confidence_level")
            failures += 1
        else:
            print(f"[PASS] confidence_level={conf['confidence_level']}")

        if conf.get("not_slo_dashboard") is not True:
            print("[FAIL] not_slo_dashboard")
            failures += 1
        else:
            print("[PASS] not_slo_dashboard")

        replay = build_replay_safety_report(db)
        if "rules" not in replay or "no_auto_retry" not in replay:
            print("[FAIL] replay_safety")
            failures += 1
        else:
            print("[PASS] replay_safety")

        diag = build_runtime_diagnostics(db)
        for key in ("operational_confidence", "replay_safety", "confidence_checks"):
            if key not in diag:
                print(f"[FAIL] diagnostics_{key}")
                failures += 1
            else:
                print(f"[PASS] diagnostics_{key}")
    finally:
        db.close()

    if failures:
        print("=== FAIL ===")
        return 1
    print("=== PASS: runtime reliability ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
