"""Rule-based analytics insight labels v2 — no LLM."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_performance import ContentPerformance
from app.models.content_quality_score import ContentQualityScore
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.seo_metadata import SeoMetadata
from app.services.campaign_service import detect_duplicate_topics, document_strategy_context
from app.services.publication_confirmation_service import analytics_ready

INSIGHT_HIGH_TRAFFIC_LOW_QUALITY = "high_traffic_low_quality"
INSIGHT_HIGH_QUALITY_LOW_TRAFFIC = "high_quality_low_traffic"
INSIGHT_NEEDS_TITLE_SEO = "needs_title_seo_review"
INSIGHT_INTERNAL_LINKS = "good_candidate_for_internal_links"
INSIGHT_CANNIBALIZATION = "potential_cannibalization_watch"

ALL_INSIGHTS = (
    INSIGHT_HIGH_TRAFFIC_LOW_QUALITY,
    INSIGHT_HIGH_QUALITY_LOW_TRAFFIC,
    INSIGHT_NEEDS_TITLE_SEO,
    INSIGHT_INTERNAL_LINKS,
    INSIGHT_CANNIBALIZATION,
)


def compute_insight_labels(db: Session, publication_record_id: int) -> list[str]:
    pub = db.get(PublicationRecord, publication_record_id)
    if not pub:
        return []
    perf = db.scalar(
        select(ContentPerformance).where(
            ContentPerformance.publication_record_id == publication_record_id
        )
    )
    if not perf:
        return []
    labels: list[str] = []
    views = perf.latest_views or 0
    score = perf.performance_score or 0
    ctr = perf.latest_ctr

    quality = db.scalar(
        select(ContentQualityScore)
        .where(ContentQualityScore.document_id == pub.document_id)
        .order_by(ContentQualityScore.id.desc())
    )
    q_score = quality.overall_score if quality and quality.overall_score is not None else None

    if views >= 1000 and q_score is not None and q_score < 60:
        labels.append(INSIGHT_HIGH_TRAFFIC_LOW_QUALITY)
    if views < 500 and q_score is not None and q_score >= 70:
        labels.append(INSIGHT_HIGH_QUALITY_LOW_TRAFFIC)

    seo = db.scalar(
        select(SeoMetadata)
        .where(SeoMetadata.document_id == pub.document_id)
        .order_by(SeoMetadata.id.desc())
    )
    title = (seo.seo_title if seo else None) or ""
    impressions = perf.latest_views  # proxy when impressions not on perf
    if (ctr is not None and ctr < 0.02 and views >= 200) or len(title.strip()) < 20:
        labels.append(INSIGHT_NEEDS_TITLE_SEO)

    if score >= 75 and perf.trend == "up":
        labels.append(INSIGHT_INTERNAL_LINKS)

    doc = db.get(ParsedDocument, pub.document_id)
    project_id = pub.project_id
    if doc:
        dupes = detect_duplicate_topics(db, document_id=pub.document_id, project_id=project_id)
        if dupes:
            labels.append(INSIGHT_CANNIBALIZATION)

    return labels


def list_documents_by_insight(
    db: Session,
    insight: str,
    *,
    project_id: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    q = select(ContentPerformance).where(ContentPerformance.performance_score.isnot(None))
    if project_id:
        q = q.where(ContentPerformance.project_id == project_id)
    out: list[dict[str, Any]] = []
    for perf in db.scalars(q.limit(limit * 20)).all():
        pub = db.get(PublicationRecord, perf.publication_record_id)
        if not pub or not analytics_ready(pub):
            continue
        labels = (perf.performance_feedback_json or {}).get("insight_labels") or compute_insight_labels(
            db, perf.publication_record_id
        )
        if insight in labels:
            out.append(
                {
                    "document_id": perf.document_id,
                    "publication_record_id": perf.publication_record_id,
                    "performance_score": perf.performance_score,
                    "latest_views": perf.latest_views,
                    "insight_labels": labels,
                }
            )
        if len(out) >= limit:
            break
    return out
