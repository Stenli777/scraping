"""Analytics snapshots and content performance — deterministic, no AI."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.content_performance import ContentPerformance
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.services.analytics_insight_service import compute_insight_labels
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.publication_confirmation_service import analytics_ready

logger = logging.getLogger(__name__)

ANALYTICS_IMPORT_STAGE = "analytics_import"
MAX_FUTURE_SNAPSHOT_DAYS = 1


class AnalyticsValidationError(ValueError):
    pass


def _views_score(views: int | None) -> float:
    if views is None or views < 0:
        return 0.0
    return min(100.0, views / 100.0)


def _ctr_score(ctr: float | None) -> float:
    if ctr is None or ctr < 0:
        return 0.0
    return min(100.0, ctr * 1000.0)


def _position_score(position_avg: float | None) -> float:
    if position_avg is None or position_avg < 0:
        return 50.0
    return max(0.0, 100.0 - position_avg * 10.0)


def _conversion_score(conversions: int | None) -> float:
    if conversions is None or conversions < 0:
        return 0.0
    return min(100.0, conversions * 5.0)


def calculate_performance_score(
    *,
    views: int | None = None,
    ctr: float | None = None,
    position_avg: float | None = None,
    conversions: int | None = None,
) -> int:
    vs = _views_score(views)
    cs = _ctr_score(ctr)
    ps = _position_score(position_avg)
    conv = _conversion_score(conversions)
    raw = 0.35 * vs + 0.25 * cs + 0.25 * ps + 0.15 * conv
    return int(max(0, min(100, round(raw))))


def _score_to_status(score: int) -> str:
    if score <= 25:
        return "low"
    if score <= 50:
        return "average"
    if score <= 75:
        return "high"
    return "top"


def calculate_trend(db: Session, publication_record_id: int) -> str:
    snaps = list(
        db.scalars(
            select(AnalyticsSnapshot)
            .where(AnalyticsSnapshot.publication_record_id == publication_record_id)
            .order_by(AnalyticsSnapshot.snapshot_date.desc(), AnalyticsSnapshot.id.desc())
            .limit(2)
        ).all()
    )
    if len(snaps) < 2:
        return "unknown"
    latest, prev = snaps[0], snaps[1]
    if latest.views is None or prev.views is None:
        return "unknown"
    if prev.views == 0:
        return "up" if latest.views > 0 else "stable"
    change = (latest.views - prev.views) / prev.views
    if change > 0.05:
        return "up"
    if change < -0.05:
        return "down"
    return "stable"


def _validate_snapshot_date(snapshot_date: date) -> None:
    today = date.today()
    if snapshot_date > today + timedelta(days=MAX_FUTURE_SNAPSHOT_DAYS):
        raise AnalyticsValidationError(
            f"snapshot_date must not be more than {MAX_FUTURE_SNAPSHOT_DAYS} day(s) in the future"
        )


def _validate_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    cleaned: dict[str, Any] = {}

    int_fields = ("views", "unique_visitors", "avg_time_seconds", "impressions", "conversions")
    float_fields = ("bounce_rate", "ctr", "position_avg")

    for key in int_fields:
        if key not in payload or payload[key] is None:
            continue
        try:
            val = int(payload[key])
            if val < 0:
                errors.append(f"{key} must be >= 0")
            else:
                cleaned[key] = val
        except (TypeError, ValueError):
            errors.append(f"{key} must be integer")

    for key in float_fields:
        if key not in payload or payload[key] is None:
            continue
        try:
            val = float(payload[key])
            if key == "bounce_rate" and (val < 0 or val > 1):
                errors.append("bounce_rate must be 0..1")
            elif key == "ctr" and (val < 0 or val > 1):
                errors.append("ctr must be 0..1")
            elif key == "position_avg" and val < 0:
                errors.append("position_avg must be >= 0")
            else:
                cleaned[key] = val
        except (TypeError, ValueError):
            errors.append(f"{key} must be number")

    views = cleaned.get("views")
    uv = cleaned.get("unique_visitors")
    if views is not None and views > 0 and uv is not None and uv > views:
        errors.append("unique_visitors must be <= views when views > 0")

    metric_keys = (
        "views",
        "unique_visitors",
        "avg_time_seconds",
        "impressions",
        "conversions",
        "bounce_rate",
        "ctr",
        "position_avg",
    )
    if not any(k in cleaned for k in metric_keys):
        errors.append("at least one metric field is required")

    source = str(payload.get("source") or "manual").strip().lower()
    if source not in ("manual", "import", "api", "estimated"):
        errors.append("source must be manual|import|api|estimated")
    else:
        cleaned["source"] = source

    if errors:
        raise AnalyticsValidationError("; ".join(errors))
    return cleaned


def _build_metadata(metrics: dict[str, Any], *, sample: bool = False) -> dict[str, Any] | None:
    meta: dict[str, Any] = {}
    if isinstance(metrics.get("metadata"), dict):
        meta.update(metrics["metadata"])
    notes = metrics.get("import_notes") or metrics.get("notes")
    if notes:
        meta["import_notes"] = str(notes).strip()
    if metrics.get("imported_by"):
        meta["imported_by"] = str(metrics["imported_by"]).strip()
    if sample:
        meta["sample"] = True
        meta["sample_warning"] = "TEST ONLY — not for production reporting"
    return meta or None


def _emit_analytics_import(
    db: Session,
    *,
    document_id: int,
    publication_id: int,
    snapshot_id: int,
    source: str,
    imported_by: str | None,
    score: int | None,
) -> None:
    doc = db.get(ParsedDocument, document_id)
    if not doc or not doc.task_id:
        return
    try:
        emit_pipeline_event(
            db,
            doc.task_id,
            ANALYTICS_IMPORT_STAGE,
            status="imported",
            payload={
                "publication_id": publication_id,
                "snapshot_id": snapshot_id,
                "source": source,
                "imported_by": imported_by,
                "performance_score": score,
            },
        )
    except Exception as exc:
        logger.warning("analytics_import pipeline event failed: %s", exc)


def create_snapshot(
    db: Session,
    publication_record_id: int,
    metrics: dict[str, Any],
    *,
    snapshot_date: date | None = None,
    require_analytics_ready: bool = True,
    imported_by: str | None = None,
    sample: bool = False,
) -> AnalyticsSnapshot:
    record = db.get(PublicationRecord, publication_record_id)
    if not record:
        raise AnalyticsValidationError(f"Publication record {publication_record_id} not found")

    if require_analytics_ready and not analytics_ready(record):
        raise AnalyticsValidationError(
            "Publication is not analytics_ready: confirm public in CRMFlow24 first"
        )

    snap_date = snapshot_date or date.today()
    _validate_snapshot_date(snap_date)

    cleaned = _validate_metrics(metrics)
    if sample:
        cleaned["source"] = "estimated"

    meta = _build_metadata(metrics, sample=sample)

    snap = AnalyticsSnapshot(
        publication_record_id=publication_record_id,
        snapshot_date=snap_date,
        views=cleaned.get("views"),
        unique_visitors=cleaned.get("unique_visitors"),
        avg_time_seconds=cleaned.get("avg_time_seconds"),
        bounce_rate=cleaned.get("bounce_rate"),
        ctr=cleaned.get("ctr"),
        impressions=cleaned.get("impressions"),
        conversions=cleaned.get("conversions"),
        position_avg=cleaned.get("position_avg"),
        source=cleaned.get("source", "manual"),
        metadata_json=meta,
    )
    db.add(snap)
    db.flush()

    record.last_checked_at = datetime.now(timezone.utc)
    perf = update_content_performance(db, publication_record_id)
    _emit_analytics_import(
        db,
        document_id=record.document_id,
        publication_id=publication_record_id,
        snapshot_id=snap.id,
        source=snap.source,
        imported_by=imported_by or (meta or {}).get("imported_by"),
        score=perf.performance_score,
    )
    db.commit()
    db.refresh(snap)
    return snap


def update_content_performance(db: Session, publication_record_id: int) -> ContentPerformance:
    record = db.get(PublicationRecord, publication_record_id)
    if not record:
        raise AnalyticsValidationError(f"Publication record {publication_record_id} not found")

    latest = db.scalar(
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.publication_record_id == publication_record_id)
        .order_by(AnalyticsSnapshot.snapshot_date.desc(), AnalyticsSnapshot.id.desc())
    )

    perf = db.scalar(
        select(ContentPerformance).where(
            ContentPerformance.publication_record_id == publication_record_id
        )
    )
    if not perf:
        perf = ContentPerformance(
            project_id=record.project_id,
            document_id=record.document_id,
            publication_record_id=publication_record_id,
        )
        db.add(perf)

    prior_feedback = dict(perf.performance_feedback_json or {})

    if latest:
        score = calculate_performance_score(
            views=latest.views,
            ctr=latest.ctr,
            position_avg=latest.position_avg,
            conversions=latest.conversions,
        )
        perf.latest_views = latest.views
        perf.latest_ctr = latest.ctr
        perf.latest_position = latest.position_avg
        perf.latest_conversions = latest.conversions
        perf.performance_score = score
        perf.status = _score_to_status(score)
        perf.trend = calculate_trend(db, publication_record_id)
        insights = compute_insight_labels(db, publication_record_id)
        perf.performance_feedback_json = {
            **prior_feedback,
            "formula_version": "v1",
            "weights": {"views": 0.35, "ctr": 0.25, "position": 0.25, "conversions": 0.15},
            "last_snapshot_id": latest.id,
            "ready_for_ai_optimization": False,
            "insight_labels": insights,
        }
    else:
        perf.trend = "unknown"
        perf.status = "average"

    perf.updated_at = datetime.now(timezone.utc)
    db.flush()
    return perf


def summarize_project_metrics(db: Session, project_id: int) -> dict[str, Any]:
    perfs = list(
        db.scalars(
            select(ContentPerformance).where(ContentPerformance.project_id == project_id)
        ).all()
    )
    if not perfs:
        return {"count": 0, "avg_score": None, "top_count": 0, "low_count": 0}

    scores = [p.performance_score for p in perfs if p.performance_score is not None]
    return {
        "count": len(perfs),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "top_count": sum(1 for p in perfs if p.status == "top"),
        "low_count": sum(1 for p in perfs if p.status == "low"),
        "trend_up": sum(1 for p in perfs if p.trend == "up"),
        "trend_down": sum(1 for p in perfs if p.trend == "down"),
    }
