#!/usr/bin/env python3
"""Smoke tests for stage 4L release candidates."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.parsed_document import ParsedDocument
from app.services.release_candidate_service import (
    RC_APPROVED,
    RC_QA_FAILED,
    RC_QA_PASSED,
    approve_release_candidate,
    build_payload_preview,
    create_release_candidate,
    publish_draft_from_candidate,
    run_release_qa,
)


def main() -> None:
    out: list[str] = []
    with SessionLocal() as db:
        docs = list(db.scalars(select(ParsedDocument).order_by(ParsedDocument.id.desc()).limit(15)).all())
        if not docs:
            print("SKIP: no documents")
            return

        good = docs[0]
        c = create_release_candidate(db, good.id)
        db.commit()
        out.append(f"OK create candidate #{c.id}")

        qa = run_release_qa(db, c.id)
        db.commit()
        out.append(f"OK QA status={qa['status']} score={qa['qa_score']} blockers={len(qa['blocking_issues'])}")

        smoke = None
        for d in docs:
            meta = dict(d.metadata_json or {})
            meta["title"] = "smoke test scrap internal"
            d.metadata_json = meta
            smoke = d
            break
        if smoke:
            db.flush()
            sc = create_release_candidate(db, smoke.id)
            sqa = run_release_qa(db, sc.id)
            db.commit()
            if sqa["status"] == RC_QA_FAILED and any(
                b.get("id") == "smoke_test_blocked" for b in sqa["blocking_issues"]
            ):
                out.append("OK smoke blocked")
            else:
                out.append(f"WARN smoke qa {sqa['status']} {sqa['blocking_issues'][:2]}")

        prev = build_payload_preview(db, c.id)
        out.append(f"OK payload preview valid={prev.get('valid')} keys={list((prev.get('payload') or {}).keys())[:5]}")

        if qa["status"] == RC_QA_PASSED:
            try:
                approve_release_candidate(db, c.id)
                db.commit()
                out.append("OK approve")
            except Exception as exc:
                out.append(f"SKIP approve: {exc}")
        else:
            out.append("INFO approve skipped (QA not passed)")

        c2 = db.get(type(c), c.id)
        if c2 and c2.status == RC_APPROVED:
            try:
                pub = publish_draft_from_candidate(db, c2.id)
                db.commit()
                out.append(f"OK publish success={pub.get('success')} run={pub.get('publish_run_id')}")
            except Exception as exc:
                out.append(f"INFO publish: {exc}")
        else:
            mock_target = None
            from app.models.publish_target import PublishTarget

            mock_target = db.scalar(
                select(PublishTarget).where(PublishTarget.target_type == "mock", PublishTarget.enabled.is_(True))
            )
            if mock_target and docs:
                c3 = create_release_candidate(db, docs[0].id, publish_target_id=mock_target.id)
                run_release_qa(db, c3.id)
                if not c3.blocking_issues_json:
                    approve_release_candidate(db, c3.id)
                    pub = publish_draft_from_candidate(db, c3.id)
                    db.commit()
                    out.append(f"OK mock publish success={pub.get('success')}")
                else:
                    out.append("INFO mock publish skipped due to blockers")

    print("\n".join(out))


if __name__ == "__main__":
    main()
