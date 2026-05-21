#!/usr/bin/env python3
"""Smoke: runtime diagnostics API and admin page."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")


def main() -> int:
    failures = 0

    from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
    from app.db.session import SessionLocal
    from app.services.runtime_diagnostics_service import (
        build_queue_summary,
        build_runtime_diagnostics,
    )

    if is_automation_enabled():
        print("[FAIL] automation_must_stay_disabled")
        failures += 1
    else:
        print("[PASS] automation_disabled")

    if is_auto_publish_enabled():
        print("[FAIL] auto_publish_must_stay_disabled")
        failures += 1
    else:
        print("[PASS] auto_publish_disabled")


    SECRET_MARKERS = ("token", "secret", "password", "database_url", "dsn", "api_key", "bearer")

    def _has_secret_keys(obj, depth=0):
        if depth > 8:
            return False
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if any(m in kl for m in SECRET_MARKERS):
                    return True
                if _has_secret_keys(v, depth + 1):
                    return True
        elif isinstance(obj, list):
            return any(_has_secret_keys(x, depth + 1) for x in obj[:20])
        return False

    db = SessionLocal()
    try:
        diag = build_runtime_diagnostics(db)
        if "feature_flags" not in diag or "queue" not in diag:
            print("[FAIL] diagnostics_structure")
            failures += 1
        else:
            print("[PASS] diagnostics_structure")

        q = build_queue_summary(db)
        if "scraping_tasks" not in q or "backlog_pressure" not in q:
            print("[FAIL] queue_summary")
            failures += 1
        else:
            print("[PASS] queue_summary")

        if diag.get("stage5_runtime") is not False:
            print("[FAIL] stage5_not_runtime")
            failures += 1
        else:
            print("[PASS] stage5_not_runtime")

        if "incident_triage" not in diag:
            print("[FAIL] incident_triage_block")
            failures += 1
        else:
            print("[PASS] incident_triage_block")

        if "llm" not in diag or "recent_failures" not in diag.get("llm", {}):
            print("[FAIL] llm_diagnostics_structure")
            failures += 1
        else:
            print("[PASS] llm_diagnostics_structure")

        drift = diag.get("governance_drift") or []
        if drift and not all(w.get("severity") in ("info", "warning", "critical") for w in drift):
            print("[FAIL] drift_severity_model")
            failures += 1
        else:
            print("[PASS] drift_severity_model")

        if diag.get("meta", {}).get("sample_limits"):
            print("[PASS] diagnostics_bounded_meta")
        else:
            print("[FAIL] diagnostics_bounded_meta")
            failures += 1

        if _has_secret_keys(diag):
            print("[FAIL] diagnostics_no_secret_keys")
            failures += 1
        else:
            print("[PASS] diagnostics_no_secret_keys")
    finally:
        db.close()

    try:
        with urllib.request.urlopen(BASE + "/api/ops/diagnostics", timeout=30) as resp:
            if resp.status != 200:
                print(f"[FAIL] api_ops_diagnostics HTTP {resp.status}")
                failures += 1
            else:
                import json
                data = json.loads(resp.read().decode())
                if "feature_flags" in data and "queue" in data and "meta" in data:
                    if _has_secret_keys(data):
                        print("[FAIL] api_no_secret_keys")
                        failures += 1
                    else:
                        print("[PASS] api_ops_diagnostics")
                        print("[PASS] api_no_secret_keys")
                else:
                    print("[FAIL] api_ops_diagnostics payload")
                    failures += 1
    except Exception as exc:
        print(f"[FAIL] api_ops_diagnostics ??? {exc}")
        failures += 1

    try:
        with urllib.request.urlopen(BASE + "/admin/diagnostics", timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status != 200:
                print(f"[FAIL] admin_diagnostics HTTP {resp.status}")
                failures += 1
            elif "Incident triage" not in body or "Feature flags" not in body:
                print("[FAIL] admin_diagnostics markers")
                failures += 1
            else:
                print("[PASS] admin_diagnostics page")
    except Exception as exc:
        print(f"[FAIL] admin_diagnostics ??? {exc}")
        failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
