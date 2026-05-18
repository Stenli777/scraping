"""Analytics-ready queue and dashboard helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.content_performance import ContentPerformance
from app.models.publication_record import PublicationRecord
from app.services.campaign_service import document_strategy_context
from app.services.publication_confirmation_service import analytics_ready


def list_analytics_ready_publications(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    records = db.scalars(
        select(PublicationRecord)
        .where(PublicationRecord.publication_status == "published")
        .where(PublicationRecord.public_visibility_status == "public")
        .where(PublicationRecord.public_confirmed_at.isnot(None))
        .order_by(PublicationRecord.public_confirmed_at.desc())
        .limit(limit)
    ).all()
    rows: list[dict[str, Any]] = []
    for pub in records:
        if not analytics_ready(pub):
            continue
        perf = db.scalar(
            select(ContentPerformance).where(
                ContentPerformance.publication_record_id == pub.id
            )
        )
        last_snap_date = db.scalar(
            select(func.max(AnalyticsSnapshot.snapshot_date)).where(
                AnalyticsSnapshot.publication_record_id == pub.id
            )
        )
        ctx = document_strategy_context(db, pub.document_id)
        campaign = ctx["campaigns"][0] if ctx.get("campaigns") else None
        cluster = ctx["clusters"][0] if ctx.get("clusters") else None
        rows.append(
            {
                "publication": pub,
                "performance": perf,
                "last_snapshot_date": last_snap_date,
                "campaign_name": campaign["name"] if campaign else None,
                "campaign_id": campaign["id"] if campaign else None,
                "cluster_name": cluster["name"] if cluster else None,
                "cluster_id": cluster["id"] if cluster else None,
                "missing_metrics": perf is None or perf.latest_views is None,
            }
        )
    return rows


def count_analytics_ready(db: Session) -> int:
    return len(list_analytics_ready_publications(db, limit=500))


def count_missing_metrics(db: Session) -> int:
    return sum(1 for r in list_analytics_ready_publications(db, limit=500) if r["missing_metrics"])


def build_analytics_dashboard(db: Session) -> dict[str, Any]:
    from app.services.analytics_insight_service import (
        list_documents_by_insight,
        INSIGHT_HIGH_QUALITY_LOW_TRAFFIC,
        INSIGHT_HIGH_TRAFFIC_LOW_QUALITY,
        INSIGHT_NEEDS_TITLE_SEO,
    )
    from app.services.editorial_insights_service import low_performing_content, top_performing_content

    ready_count = count_analytics_ready(db)
    missing_count = count_missing_metrics(db)
    recent_snapshots = db.scalars(
        select(AnalyticsSnapshot)
        .order_by(AnalyticsSnapshot.created_at.desc().nullslast(), AnalyticsSnapshot.id.desc())
        .limit(10)
    ).all()
    return {
        "analytics_ready_count": ready_count,
        "missing_metrics_count": missing_count,
        "recent_snapshots": recent_snapshots,
        "top_opportunities": list_documents_by_insight(
            db, INSIGHT_HIGH_QUALITY_LOW_TRAFFIC, limit=5
        ),
        "low_performance_warnings": low_performing_content(db, limit=5),
        "high_traffic_low_quality": list_documents_by_insight(
            db, INSIGHT_HIGH_TRAFFIC_LOW_QUALITY, limit=5
        ),
        "needs_seo_review": list_documents_by_insight(db, INSIGHT_NEEDS_TITLE_SEO, limit=5),
        "top_performing": top_performing_content(db, limit=5),
    }
