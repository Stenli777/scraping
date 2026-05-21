#!/usr/bin/env python3
"""Smoke: operational predictability and replay determinism."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def main() -> int:
    failures = 0
    from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
    from app.db.session import SessionLocal
    from app.services.runtime_diagnostics_service import build_runtime_diagnostics
    from app.services.runtime_predictability_service import (
        build_consistency_guarantees,
        build_operational_predictability,
        build_replay_determinism_report,
        resolve_replay_verdict,
    )
    if is_automation_enabled():
        failures += 1
    else:
        print("[PASS] automation_disabled")
    if is_auto_publish_enabled():
        failures += 1
    else:
        print("[PASS] auto_publish_disabled")
    db = SessionLocal()
    try:
        if not build_consistency_guarantees(db).get("runtime_enforced"):
            failures += 1
        else:
            print("[PASS] guarantees")
        rep = build_replay_determinism_report(db)
        if "verdict_catalog" not in rep:
            failures += 1
        else:
            print("[PASS] replay_determinism")
        if "operator_read_order" not in build_operational_predictability(db):
            failures += 1
        else:
            print("[PASS] operational_predictability")
        diag = build_runtime_diagnostics(db)
        for key in ("operational_predictability", "consistency_guarantees", "replay_determinism", "recovery_normalization"):
            if key not in diag:
                print(f"[FAIL] diagnostics_{key}")
                failures += 1
            else:
                print(f"[PASS] diagnostics_{key}")
        from app.models.publish_run import PublishRun
        from sqlalchemy import select
        run = db.scalars(select(PublishRun).order_by(PublishRun.id.desc()).limit(1)).first()
        if run and "verdict_id" not in resolve_replay_verdict(db, run.id):
            failures += 1
        else:
            print("[PASS] verdict_structure")
    finally:
        db.close()
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
