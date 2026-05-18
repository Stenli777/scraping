"""Post-publication tracking summary for admin operations."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.publication_record import PublicationRecord
from app.services.publication_confirmation_service import (
    VISIBILITY_INCONSISTENT,
    VISIBILITY_PUBLIC,
    analytics_ready,
)


def build_post_publication_tracking_summary(db: Session) -> dict:
    pubs = db.scalars(select(PublicationRecord).order_by(PublicationRecord.id.desc()).limit(200)).all()

    draft_not_confirmed = [
        {
            "publication_id": p.id,
            "document_id": p.document_id,
            "draft_review_status": p.draft_review_status,
            "public_visibility_status": p.public_visibility_status,
            "external_url": p.external_url,
        }
        for p in pubs
        if p.publication_status == "draft" and p.public_confirmed_at is None and p.external_url
    ]

    public_confirmed_count = sum(1 for p in pubs if p.publication_status == "published" and p.public_confirmed_at)
    inconsistent_count = sum(1 for p in pubs if p.public_visibility_status == VISIBILITY_INCONSISTENT)
    analytics_ready_count = sum(1 for p in pubs if analytics_ready(p))

    candidates_awaiting = db.scalar(
        select(func.count())
        .select_from(ContentReleaseCandidate)
        .where(
            ContentReleaseCandidate.status == "published_draft",
            ContentReleaseCandidate.public_status != VISIBILITY_PUBLIC,
        )
    ) or 0

    return {
        "draft_awaiting_public_confirm": draft_not_confirmed[:20],
        "draft_awaiting_count": len(draft_not_confirmed),
        "public_confirmed_count": public_confirmed_count,
        "inconsistent_visibility_count": inconsistent_count,
        "analytics_ready_count": analytics_ready_count,
        "candidates_awaiting_public": candidates_awaiting,
    }
