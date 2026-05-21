#!/usr/bin/env python3
"""Smoke: runtime integrity and recovery discipline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    failures = 0
    from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
    from app.db.session import SessionLocal
    from app.services.runtime_diagnostics_service import build_runtime_diagnostics
    from app.services.runtime_integrity_service import (
        build_runtime_integrity_report,
        supersede_stale_approved_batch,
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
        rep = build_runtime_integrity_report(db)
        for key in ("checks", "stale_approved_rc", "no_auto_remediation"):
            if key not in rep:
                print(f"[FAIL] integrity_{key}")
                failures += 1
            else:
                print(f"[PASS] integrity_{key}")

        preview = supersede_stale_approved_batch(db, limit=5, dry_run=True)
        if not preview.get("dry_run"):
            print("[FAIL] supersede_dry_run")
            failures += 1
        else:
            print("[PASS] supersede_dry_run")

        diag = build_runtime_diagnostics(db)
        for key in ("integrity_report", "recovery_discipline"):
            if key not in diag:
                print(f"[FAIL] diagnostics_{key}")
                failures += 1
            else:
                print(f"[PASS] diagnostics_{key}")
    finally:
        db.close()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
