#!/usr/bin/env python3
"""Smoke: runtime authority boundaries and invariant consistency."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    failures = 0
    from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
    from app.db.session import SessionLocal
    from app.services.runtime_authority_service import AUTH_DECORATIVE, AUTH_RUNTIME_ENFORCED
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
        diag = build_runtime_diagnostics(db)
        ab = diag.get("authority_boundaries") or {}
        if not ab.get("domains"):
            print("[FAIL] authority_boundaries")
            failures += 1
        else:
            print("[PASS] authority_boundaries")

        ids = {d["id"] for d in ab["domains"]}
        for required in ("publish_stale_revision", "projects_trust_level", "legacy_document_publish"):
            if required not in ids:
                print(f"[FAIL] authority_domain_{required}")
                failures += 1
            else:
                print(f"[PASS] authority_domain_{required}")

        trust_dom = next((d for d in ab["domains"] if d["id"] == "projects_trust_level"), None)
        if not trust_dom or trust_dom.get("authority") != AUTH_DECORATIVE:
            print("[FAIL] trust_decorative_authority")
            failures += 1
        else:
            print("[PASS] trust_decorative_authority")

        stale_dom = next((d for d in ab["domains"] if d["id"] == "publish_stale_revision"), None)
        if not stale_dom or stale_dom.get("authority") != AUTH_RUNTIME_ENFORCED:
            print("[FAIL] stale_publish_runtime_enforced")
            failures += 1
        else:
            print("[PASS] stale_publish_runtime_enforced")

        inv = diag.get("invariant_consistency") or {}
        if inv.get("trust_level_semantics") != AUTH_DECORATIVE:
            print("[FAIL] invariant_trust_semantics")
            failures += 1
        else:
            print("[PASS] invariant_trust_semantics")

        if not diag.get("runtime_cohesion"):
            print("[FAIL] runtime_cohesion_notes")
            failures += 1
        else:
            print("[PASS] runtime_cohesion_notes")

        if diag.get("stage5_runtime") is not False:
            print("[FAIL] stage5_absent")
            failures += 1
        else:
            print("[PASS] stage5_absent")
    finally:
        db.close()

    if failures:
        print("=== FAIL ===")
        return 1
    print("=== PASS: runtime cohesion ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
