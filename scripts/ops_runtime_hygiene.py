#!/usr/bin/env python3
"""Runtime hygiene report — dry-run by default; optional bounded retention apply."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrap runtime hygiene report")
    parser.add_argument("--apply-snapshots", action="store_true", help="Run snapshot retention cleanup")
    parser.add_argument("--apply-incidents", action="store_true", help="Run incident retention cleanup")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from app.db.session import SessionLocal
    from app.services.runtime_hygiene_service import apply_safe_hygiene, build_runtime_hygiene_report

    db = SessionLocal()
    try:
        report = build_runtime_hygiene_report(db)
        if args.apply_snapshots or args.apply_incidents:
            applied = apply_safe_hygiene(
                db, snapshots=args.apply_snapshots, incidents=args.apply_incidents
            )
            report["applied"] = applied
            db.commit()
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print("=== Runtime hygiene ===")
            print(f"git clean: {report['git']['clean']} changed_files={report['git']['changed_files']}")
            if report["tmp_artifacts"]:
                print(f"tmp artifacts ({report['tmp_artifact_count']}):")
                for t in report["tmp_artifacts"]:
                    print(f"  - {t}")
            print(f"snapshots: {report['operational_tables']['snapshots']}")
            print(f"incidents: {report['operational_tables']['incidents']}")
            print(f"storage MB: {report['storage_mb']}")
            if report.get("applied"):
                print(f"applied: {report['applied']}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
