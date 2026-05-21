#!/usr/bin/env python3
"""Bounded integrity remediation — dry-run by default."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply supersede (not dry-run)")
    parser.add_argument("--supersede-stale-approved", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from app.db.session import SessionLocal
    from app.services.runtime_integrity_service import (
        apply_bounded_integrity_cleanup,
        build_runtime_integrity_report,
    )

    db = SessionLocal()
    try:
        report = build_runtime_integrity_report(db)
        if args.supersede_stale_approved:
            result = apply_bounded_integrity_cleanup(
                db,
                supersede_stale_approved=bool(args.apply),
                limit=args.limit,
            )
            if args.apply:
                db.commit()
            report["cleanup"] = result
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"stale_approved_rc: {report['stale_approved_rc_count']}")
            for c in report["checks"]:
                print(f"  [{c['status']}] {c['id']}: {c['count']}")
            if report.get("cleanup"):
                print("cleanup:", report["cleanup"])
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
