#!/usr/bin/env python3
"""Release and draft-review consistency checks (read-only).

Safety:
- read-only by default
- does not modify CRMFlow24
- does not publish
- does not print secrets
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.draft_review_feedback import DraftReviewFeedback
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.models.seo_metadata import SeoMetadata
from app.services.strategy_gate_service import detect_test_document

LEVEL_FAIL = "FAIL"
LEVEL_WARN = "WARN"
LEVEL_PASS = "PASS"


@dataclass
class Finding:
    level: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message}


def _is_test_document(db: Session, document_id: int) -> bool:
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return False
    seo = db.scalar(
        select(SeoMetadata).where(SeoMetadata.document_id == document_id).order_by(SeoMetadata.id.desc())
    )
    title = (seo.seo_title if seo else None) or (seo.h1 if seo else None) or (doc.metadata_json or {}).get("title") or ""
    slug = (seo.slug if seo else "") or ""
    is_test, _ = detect_test_document(title=title, text=doc.rewritten_text or "", slug=slug)
    return is_test


def _latest_feedback(db: Session, *, publication_id: int | None = None, candidate_id: int | None = None) -> DraftReviewFeedback | None:
    q = select(DraftReviewFeedback).order_by(DraftReviewFeedback.id.desc())
    if publication_id:
        q = q.where(DraftReviewFeedback.publication_record_id == publication_id)
    if candidate_id:
        q = q.where(DraftReviewFeedback.release_candidate_id == candidate_id)
    return db.scalar(q.limit(1))


def _visibility_present(pub: PublicationRecord, fb: DraftReviewFeedback | None) -> bool:
    if fb and fb.visibility_check_json:
        return True
    meta = pub.metadata_json or {}
    return bool(meta.get("visibility_check"))


def run_checks(db: Session) -> list[Finding]:
    findings: list[Finding] = []

    candidates = db.scalars(select(ContentReleaseCandidate)).all()
    for cand in candidates:
        if cand.status != "published_draft":
            continue
        runs = db.scalars(
            select(PublishRun).where(PublishRun.release_candidate_id == cand.id)
        ).all()
        if not runs:
            findings.append(
                Finding(
                    LEVEL_FAIL,
                    "candidate_no_publish_run",
                    f"Candidate #{cand.id} is published_draft but has no publish_run",
                )
            )
        pub = db.scalar(
            select(PublicationRecord)
            .where(PublicationRecord.document_id == cand.document_id)
            .order_by(PublicationRecord.id.desc())
        )
        if not pub:
            findings.append(
                Finding(
                    LEVEL_FAIL,
                    "candidate_no_publication",
                    f"Candidate #{cand.id} published_draft without publication_record",
                )
            )
        if _is_test_document(db, cand.document_id):
            findings.append(
                Finding(
                    LEVEL_WARN,
                    "smoke_test_published_draft",
                    f"Candidate #{cand.id} published_draft on test/smoke document #{cand.document_id}",
                )
            )

    pubs = db.scalars(
        select(PublicationRecord).where(PublicationRecord.publication_status == "draft")
    ).all()
    for pub in pubs:
        is_test = _is_test_document(db, pub.document_id)
        fb = _latest_feedback(db, publication_id=pub.id)
        if not is_test and pub.external_url and "crmflow24" in (pub.external_url or "").lower():
            if not fb:
                findings.append(
                    Finding(
                        LEVEL_WARN,
                        "production_draft_no_feedback",
                        f"Publication #{pub.id} (production draft) has no draft_review_feedback",
                    )
                )
            if not _visibility_present(pub, fb):
                findings.append(
                    Finding(
                        LEVEL_WARN,
                        "visibility_metadata_missing",
                        f"Publication #{pub.id} missing public visibility check metadata",
                    )
                )

        cand = None
        if pub.publish_run_id:
            run = db.get(PublishRun, pub.publish_run_id)
            if run and run.release_candidate_id:
                cand = db.get(ContentReleaseCandidate, run.release_candidate_id)

        if fb and cand:
            if pub.draft_review_status and fb.review_status != pub.draft_review_status:
                findings.append(
                    Finding(
                        LEVEL_FAIL,
                        "feedback_publication_mismatch",
                        f"Publication #{pub.id} status {pub.draft_review_status!r} != latest feedback {fb.review_status!r}",
                    )
                )
            if cand.draft_review_status and fb.review_status != cand.draft_review_status:
                findings.append(
                    Finding(
                        LEVEL_FAIL,
                        "feedback_candidate_mismatch",
                        f"Candidate #{cand.id} status {cand.draft_review_status!r} != latest feedback {fb.review_status!r}",
                    )
                )
            if pub.draft_review_status and cand.draft_review_status and pub.draft_review_status != cand.draft_review_status:
                findings.append(
                    Finding(
                        LEVEL_FAIL,
                        "publication_candidate_mismatch",
                        f"Publication #{pub.id} {pub.draft_review_status!r} != candidate #{cand.id} {cand.draft_review_status!r}",
                    )
                )

        if fb and fb.review_status == "rejected":
            if pub.draft_review_status == "accepted" or (cand and cand.draft_review_status == "accepted"):
                findings.append(
                    Finding(
                        LEVEL_FAIL,
                        "rejected_feedback_still_accepted",
                        f"Latest feedback rejected but derived status accepted (pub #{pub.id})",
                    )
                )

        if fb and fb.review_status == "needs_edits":
            doc = db.get(ParsedDocument, pub.document_id)
            if doc and doc.editorial_status not in ("needs_revision", "rejected"):
                findings.append(
                    Finding(
                        LEVEL_WARN,
                        "needs_edits_editorial_not_revision",
                        f"Publication #{pub.id} needs_edits but document #{pub.document_id} editorial={doc.editorial_status!r}",
                    )
                )

    if not any(f.level in (LEVEL_FAIL, LEVEL_WARN) for f in findings):
        findings.append(Finding(LEVEL_PASS, "ok", "No release consistency issues detected"))

    return findings


def summarize(findings: list[Finding]) -> str:
    if any(f.level == LEVEL_FAIL for f in findings):
        return "FAIL"
    if any(f.level == LEVEL_WARN for f in findings):
        return "WARN"
    return "PASS"


def main() -> int:
    parser = argparse.ArgumentParser(description="Release state consistency (read-only)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    with SessionLocal() as db:
        findings = run_checks(db)
    overall = summarize(findings)

    payload = {"overall": overall, "findings": [f.to_dict() for f in findings]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"OVERALL: {overall}")
        for f in findings:
            print(f"  [{f.level}] {f.code}: {f.message}")

    return 0 if overall != LEVEL_FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
