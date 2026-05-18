#!/usr/bin/env python3
"""Stage 4M release run checks (safe by default, --publish for production draft)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.parsed_document import ParsedDocument
from app.models.publish_target import PublishTarget
from app.services.publish_readiness_service import get_publish_readiness
from app.services.publish_target_health_service import check_publish_target_health
from app.services.release_candidate_service import (
    PRODUCTION_TARGET_NAME,
    build_payload_preview,
    create_release_candidate,
    get_candidate_status,
    publish_draft_from_candidate,
    resolve_production_publish_target,
    run_release_qa,
)
from app.services.strategy_gate_service import detect_test_document


def main() -> None:
    ap = argparse.ArgumentParser(description="4M release candidate readiness checks")
    ap.add_argument("--document-id", type=int, default=4)
    ap.add_argument("--publish", action="store_true", help="Approve and publish to CRMFlow24 production")
    args = ap.parse_args()

    with SessionLocal() as db:
        doc = db.get(ParsedDocument, args.document_id)
        if not doc:
            print(f"Document {args.document_id} not found")
            sys.exit(1)

        target = resolve_production_publish_target(db, doc.task.project_id if doc.task else 1)
        print("target", target.name if target else None, "enabled", target.enabled if target else None)
        if target:
            health = check_publish_target_health(db, target)
            print("target_health", json.dumps({k: health[k] for k in ("healthy", "reach_detail", "payload_format")}, ensure_ascii=False))

        is_test, reason = detect_test_document(
            title=(doc.metadata_json or {}).get("title", ""),
            text=doc.rewritten_text or "",
            slug="",
        )
        print("smoke_test", is_test, reason)
        print("readiness", json.dumps(get_publish_readiness(db, args.document_id), ensure_ascii=False)[:500])

        c = create_release_candidate(db, args.document_id)
        db.commit()
        qa = run_release_qa(db, c.id)
        db.commit()
        print("candidate", c.id, "qa", qa["status"], "score", qa["qa_score"], "blockers", len(qa["blocking_issues"]))

        prev = build_payload_preview(db, c.id)
        print("payload_preview valid", prev.get("valid"))
        if prev.get("payload"):
            p = prev["payload"]
            print("  title", p.get("title"), "slug", p.get("slug"), "status", p.get("status"))

        if not args.publish:
            print("Dry-run complete (use --publish to send draft)")
            return

        if qa["status"] != "qa_passed":
            print("QA failed; not publishing")
            sys.exit(2)

        from app.services.release_candidate_service import approve_release_candidate

        approve_release_candidate(db, c.id)
        db.commit()
        pub = publish_draft_from_candidate(db, c.id)
        db.commit()
        print("publish", json.dumps(pub, ensure_ascii=False))


if __name__ == "__main__":
    main()
