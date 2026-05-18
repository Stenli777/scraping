#!/usr/bin/env python3
"""Smoke: pilot list, scoring, detail, consistency script."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.db.session import SessionLocal
    from app.models.project import Project
    from app.services.pilot_service import (
        ensure_crmflow24_first5_pilot,
        list_pilots,
        score_pilot_candidate,
        suggest_pilot_candidates,
        get_pilot_dashboard,
    )

    db = SessionLocal()
    try:
        pilot = ensure_crmflow24_first5_pilot(db)
        db.commit()
        if pilot.slug != "crmflow24-first-5":
            print("[FAIL] pilot seed slug")
            return 1
        print("[PASS] pilot seed")

        rows = list_pilots(db)
        if not any(r["pilot"].id == pilot.id for r in rows):
            print("[FAIL] pilot list")
            return 1
        print("[PASS] pilot list")

        project = db.query(Project).filter_by(slug="crmflow24").first()
        candidates = suggest_pilot_candidates(db, project.id, limit=5)
        print(f"[PASS] pilot candidates — count={len(candidates)}")

        if candidates:
            scored = score_pilot_candidate(db, candidates[0]["document_id"])
            if "score" not in scored or "next_action" not in scored:
                print("[FAIL] pilot scoring shape")
                return 1
        print("[PASS] pilot scoring")

        dash = get_pilot_dashboard(db, pilot.id)
        if "progress" not in dash:
            print("[FAIL] pilot dashboard")
            return 1
        print("[PASS] pilot detail")

    finally:
        db.close()

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_pilot_state.py")],
        cwd=ROOT,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        print(f"[FAIL] check_pilot_state exit {proc.returncode}")
        print(proc.stderr[:500])
        return 1
    print("[PASS] check_pilot_state — ran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
