"""Read-only release operations summary for admin / operations."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.draft_review_feedback import DraftReviewFeedback
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.services.strategy_gate_service import detect_test_document
from app.models.parsed_document import ParsedDocument
from app.models.seo_metadata import SeoMetadata


def _document_is_test(db: Session, document_id: int) -> bool:
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return False
    seo = db.scalar(
        select(SeoMetadata).where(SeoMetadata.document_id == document_id).order_by(SeoMetadata.id.desc())
    )
    title = (seo.seo_title if seo else None) or (doc.metadata_json or {}).get("title") or ""
    slug = (seo.slug if seo else "") or ""
    is_test, _ = detect_test_document(title=title, text=doc.rewritten_text or "", slug=slug)
    return is_test


def build_release_operations_summary(db: Session) -> dict:
    latest_drafts = db.scalars(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.status == "published_draft")
        .order_by(ContentReleaseCandidate.id.desc())
        .limit(10)
    ).all()

    draft_candidates = [
        {
            "id": c.id,
            "document_id": c.document_id,
            "draft_review_status": c.draft_review_status,
            "is_test": _document_is_test(db, c.document_id),
        }
        for c in latest_drafts
    ]

    missing_feedback: list[dict] = []
    pubs = db.scalars(
        select(PublicationRecord)
        .where(PublicationRecord.publication_status == "draft")
        .order_by(PublicationRecord.id.desc())
        .limit(50)
    ).all()
    for pub in pubs:
        if _document_is_test(db, pub.document_id):
            continue
        if not pub.external_url:
            continue
        fb = db.scalar(
            select(DraftReviewFeedback)
            .where(DraftReviewFeedback.publication_record_id == pub.id)
            .order_by(DraftReviewFeedback.id.desc())
        )
        if not fb or fb.review_status in ("pending", None):
            missing_feedback.append(
                {
                    "publication_id": pub.id,
                    "document_id": pub.document_id,
                    "draft_url": pub.external_url,
                    "draft_review_status": pub.draft_review_status or "pending",
                }
            )

    needs_edits_count = db.scalar(
        select(func.count())
        .select_from(PublicationRecord)
        .where(PublicationRecord.draft_review_status == "needs_edits")
    ) or 0
    rejected_count = db.scalar(
        select(func.count())
        .select_from(PublicationRecord)
        .where(PublicationRecord.draft_review_status == "rejected")
    ) or 0

    smoke_warnings = [c for c in draft_candidates if c["is_test"]]

    return {
        "latest_published_draft_candidates": draft_candidates,
        "publications_missing_feedback": missing_feedback[:15],
        "needs_edits_count": needs_edits_count,
        "rejected_count": rejected_count,
        "smoke_test_draft_warnings": smoke_warnings,
    }
