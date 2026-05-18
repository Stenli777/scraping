#!/usr/bin/env python3
"""Release candidate ops helper: QA, approve, optional CRMFlow24 draft publish.

Safety:
- read-only by default (no --publish)
- does not modify CRMFlow24 except via publish API when --publish is passed
- does not publish unless --publish is explicitly passed
- does not print secrets
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.media_asset import MediaAsset
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.services.media_service import approve_media, run_preview_generation
from app.services.release_candidate_service import (
    approve_release_candidate,
    build_payload_preview,
    create_release_candidate,
    publish_draft_from_candidate,
    run_release_qa,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--document-id", type=int, default=4)
    ap.add_argument("--publish", action="store_true", help="Send draft to CRMFlow24 (destructive)")
    args = ap.parse_args()

    with SessionLocal() as db:
        doc = db.get(ParsedDocument, args.document_id)
        if not doc:
            print("document not found")
            return 1

        try:
            run_preview_generation(db, args.document_id, provider="placeholder", use_llm_prompt=False)
            db.commit()
        except Exception as exc:
            print("media gen:", exc)

        asset = db.scalar(
            select(MediaAsset)
            .where(MediaAsset.document_id == args.document_id, MediaAsset.media_type == "preview")
            .order_by(MediaAsset.id.desc())
        )
        if asset and asset.status != "approved":
            approve_media(db, asset.id)
            db.commit()
            print("media approved", asset.id)

        c = create_release_candidate(db, args.document_id)
        db.commit()
        print("candidate", c.id)

        qa = run_release_qa(db, c.id)
        db.commit()
        print(
            "qa",
            json.dumps(
                {
                    "status": qa["status"],
                    "score": qa["qa_score"],
                    "blockers": len(qa["blocking_issues"]),
                    "warnings": len(qa["warnings"]),
                },
                ensure_ascii=False,
            ),
        )

        prev = build_payload_preview(db, c.id)
        print("preview valid", prev.get("valid"), "keys", list((prev.get("payload") or {}).keys())[:8])

        if qa["status"] != "qa_passed":
            print("BLOCKERS:", json.dumps(qa["blocking_issues"], ensure_ascii=False, indent=2))
            return 1

        appr = approve_release_candidate(db, c.id)
        db.commit()
        print("approved", appr["status"])

        if not args.publish:
            print("dry-run: skip publish (pass --publish to send CRMFlow24 draft)")
            return 0

        pub = publish_draft_from_candidate(db, c.id)
        db.commit()
        print("publish", json.dumps(pub, ensure_ascii=False, default=str)[:500])
        run = db.scalar(select(PublishRun).where(PublishRun.release_candidate_id == c.id).order_by(PublishRun.id.desc()))
        rec = db.scalar(
            select(PublicationRecord).where(PublicationRecord.document_id == args.document_id).order_by(PublicationRecord.id.desc())
        )
        if run:
            print("publish_run", run.id, run.status, run.draft_url)
        if rec:
            print("publication_record", rec.id, rec.external_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
