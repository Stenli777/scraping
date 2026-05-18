"""Analytics and publication tracking API."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_analytics_enabled
from app.db.session import get_db
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.content_performance import ContentPerformance
from app.models.publication_record import PublicationRecord
from app.services.analytics_service import AnalyticsValidationError, create_snapshot, summarize_project_metrics
from app.services.editorial_insights_service import (
    content_aging_signals,
    low_performing_content,
    top_performing_content,
)

router = APIRouter(tags=["analytics"])


class AnalyticsImportBody(BaseModel):
    views: int | None = Field(None, ge=0)
    unique_visitors: int | None = Field(None, ge=0)
    avg_time_seconds: int | None = Field(None, ge=0)
    bounce_rate: float | None = Field(None, ge=0, le=1)
    ctr: float | None = Field(None, ge=0, le=1)
    impressions: int | None = Field(None, ge=0)
    conversions: int | None = Field(None, ge=0)
    position_avg: float | None = Field(None, ge=0)
    source: str = "manual"
    snapshot_date: date | None = None
    import_notes: str | None = None
    imported_by: str | None = None


def _require_analytics():
    if not is_analytics_enabled():
        raise HTTPException(status_code=503, detail="Analytics disabled (ENABLE_ANALYTICS=false)")


@router.get("/api/publications")
def list_publications(
    document_id: int | None = None,
    project_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    _require_analytics()
    q = select(PublicationRecord).order_by(PublicationRecord.id.desc()).limit(min(limit, 200))
    if document_id is not None:
        q = q.where(PublicationRecord.document_id == document_id)
    if project_id is not None:
        q = q.where(PublicationRecord.project_id == project_id)
    records = db.scalars(q).all()
    return {
        "publications": [
            {
                "id": r.id,
                "document_id": r.document_id,
                "revision_id": r.revision_id,
                "publish_run_id": r.publish_run_id,
                "external_url": r.external_url,
                "public_url": r.public_url,
                "publication_status": r.publication_status,
                "public_visibility_status": r.public_visibility_status,
                "draft_review_status": r.draft_review_status,
                "draft_reviewed_at": r.draft_reviewed_at.isoformat() if r.draft_reviewed_at else None,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "public_confirmed_at": r.public_confirmed_at.isoformat() if r.public_confirmed_at else None,
            }
            for r in records
        ]
    }


@router.post("/api/publications/{publication_id}/analytics/import")
def import_analytics(
    publication_id: int,
    body: AnalyticsImportBody,
    db: Session = Depends(get_db),
):
    _require_analytics()
    payload = body.model_dump(exclude_none=True)
    imported_by = payload.pop("imported_by", None)
    import_notes = payload.pop("import_notes", None)
    snap_date = payload.pop("snapshot_date", None)
    if import_notes:
        payload["import_notes"] = import_notes
    try:
        snap = create_snapshot(
            db,
            publication_id,
            payload,
            snapshot_date=snap_date,
            imported_by=imported_by,
        )
        perf = db.scalar(
            select(ContentPerformance).where(
                ContentPerformance.publication_record_id == publication_id
            )
        )
    except AnalyticsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "success": True,
        "snapshot_id": snap.id,
        "performance_score": perf.performance_score if perf else None,
        "trend": perf.trend if perf else None,
        "status": perf.status if perf else None,
        "insight_labels": (perf.performance_feedback_json or {}).get("insight_labels") if perf else [],
    }


@router.get("/api/analytics/insights/top")
def api_top_content(project_id: int | None = None, db: Session = Depends(get_db)):
    _require_analytics()
    return {"items": top_performing_content(db, project_id=project_id)}


@router.get("/api/analytics/insights/low")
def api_low_content(project_id: int | None = None, db: Session = Depends(get_db)):
    _require_analytics()
    return {"items": low_performing_content(db, project_id=project_id)}


@router.get("/api/analytics/project/{project_id}/summary")
def api_project_summary(project_id: int, db: Session = Depends(get_db)):
    _require_analytics()
    return summarize_project_metrics(db, project_id)


@router.get("/api/documents/{document_id}/analytics")
def document_analytics(document_id: int, db: Session = Depends(get_db)):
    _require_analytics()
    records = db.scalars(
        select(PublicationRecord)
        .where(PublicationRecord.document_id == document_id)
        .order_by(PublicationRecord.id.desc())
    ).all()
    result = []
    for rec in records:
        perf = db.scalar(
            select(ContentPerformance).where(
                ContentPerformance.publication_record_id == rec.id
            )
        )
        snaps = db.scalars(
            select(AnalyticsSnapshot)
            .where(AnalyticsSnapshot.publication_record_id == rec.id)
            .order_by(AnalyticsSnapshot.snapshot_date.desc())
            .limit(5)
        ).all()
        result.append({
            "publication": {
                "id": rec.id,
                "revision_id": rec.revision_id,
                "external_url": rec.external_url,
                "public_url": rec.public_url,
                "publication_status": rec.publication_status,
                "public_visibility_status": rec.public_visibility_status,
                "published_at": rec.published_at.isoformat() if rec.published_at else None,
            },
            "performance": {
                "score": perf.performance_score if perf else None,
                "views": perf.latest_views if perf else None,
                "ctr": perf.latest_ctr if perf else None,
                "trend": perf.trend if perf else None,
                "status": perf.status if perf else None,
                "insight_labels": (perf.performance_feedback_json or {}).get("insight_labels") if perf else [],
            },
            "snapshots": [
                {"id": s.id, "date": str(s.snapshot_date), "views": s.views, "ctr": s.ctr}
                for s in snaps
            ],
        })
    return {"document_id": document_id, "publications": result}
