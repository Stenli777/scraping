#!/usr/bin/env python3
"""Read-only status report for crmflow24-first-5 pilot.

Usage:
  PYTHONPATH=/opt/scrap .venv/bin/python scripts/run_pilot_first5_check.py
  PYTHONPATH=/opt/scrap .venv/bin/python scripts/run_pilot_first5_check.py --refresh --json
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.content_pilot import ContentPilot
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.services.pilot_service import get_pilot_dashboard, refresh_pilot_status, suggest_pilot_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="First 5 pilot status (read-only)")
    parser.add_argument("--pilot-id", type=int, default=None, help="Pilot ID (default: slug crmflow24-first-5)")
    parser.add_argument("--refresh", action="store_true", help="Refresh pilot item statuses before report")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.pilot_id:
            pilot = db.get(ContentPilot, args.pilot_id)
        else:
            pilot = db.scalar(select(ContentPilot).where(ContentPilot.slug == "crmflow24-first-5"))
        if not pilot:
            print("Pilot not found", file=sys.stderr)
            return 1

        if args.refresh:
            refresh_pilot_status(db, pilot.id)
            db.commit()

        dash = get_pilot_dashboard(db, pilot.id)
        candidates = suggest_pilot_candidates(db, pilot.project_id, limit=10)

        rows = []
        for r in dash["item_rows"]:
            pub_id = r.get("publication_id")
            draft_url = None
            if pub_id:
                pub = db.get(PublicationRecord, pub_id)
                draft_url = pub.external_url if pub else None
                if not draft_url:
                    pr = db.scalar(
                        select(PublishRun)
                        .where(PublishRun.document_id == r["document_id"], PublishRun.dry_run == False)
                        .order_by(PublishRun.id.desc())
                    )
                    draft_url = pr.draft_url if pr else None
            rows.append({**r, "draft_url": draft_url})

        report = {
            "pilot": {
                "id": pilot.id,
                "slug": pilot.slug,
                "name": pilot.name,
                "status": pilot.status,
                "target_count": pilot.target_count,
            },
            "progress": dash["progress"],
            "items": rows,
            "suggested_candidates": candidates,
            "note": (
                "Only safe non-test documents are listed as candidates. "
                "Add items manually via admin or API."
            ),
        }

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        else:
            p = report["progress"]
            print(f"Pilot #{pilot.id} {pilot.slug} [{pilot.status}] — {p['done']}/{p['total']} done ({p['count']} items)")
            print()
            for row in rows:
                print(f"  doc #{row['document_id']}: {row['title'][:50]}")
                print(f"    score={row.get('score')} status={row['status']} next={row['next_action']}")
                print(f"    blockers={row.get('blockers')}")
                print(f"    rc={row.get('release_candidate_id')} ({row.get('rc_status')}) pub={row.get('publication_id')}")
                print(f"    draft_review={row.get('draft_review_status')} public={row.get('public_status')} analytics={row.get('analytics_status')}")
                if row.get("draft_url"):
                    print(f"    draft_url={row['draft_url']}")
                print()
            if candidates:
                print("Suggested candidates (not in pilot):")
                for c in candidates[:5]:
                    print(f"  doc #{c['document_id']} score={c['score']} — {c.get('title', '')[:40]}")
            else:
                print("No additional safe candidates (run discovery to add more documents).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
