"""Analytics snapshots and content performance — deterministic, no AI.

Performance score formula (0–100):
  views_score    = min(100, views / 100)           # 10k views => 100
  ctr_score      = min(100, ctr * 1000)            # 10% CTR => 100
  position_score = max(0, 100 - position_avg * 10) # rank 1 => 90
  conv_score     = min(100, conversions * 5)       # 20 conv => 100
  score = round(0.35*views + 0.25*ctr + 0.25*position + 0.15*conv)

Status from score: 0-25 low, 26-50 average, 51-75 high, 76-100 top
Trend: compare latest two snapshots views (+/- 5% threshold)
"""

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.content_performance import ContentPerformance
from app.models.publication_record import PublicationRecord


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

    source = str(payload.get("source") or "manual").strip().lower()
    if source not in ("manual", "import", "api", "estimated"):
        errors.append("source must be manual|import|api|estimated")
    else:
        cleaned["source"] = source

    if errors:
        raise AnalyticsValidationError("; ".join(errors))
    return cleaned


def create_snapshot(
    db: Session,
    publication_record_id: int,
    metrics: dict[str, Any],
    *,
    snapshot_date: date | None = None,
) -> AnalyticsSnapshot:
    record = db.get(PublicationRecord, publication_record_id)
    if not record:
        raise AnalyticsValidationError(f"Publication record {publication_record_id} not found")

    cleaned = _validate_metrics(metrics)
    snap = AnalyticsSnapshot(
        publication_record_id=publication_record_id,
        snapshot_date=snapshot_date or date.today(),
        views=cleaned.get("views"),
        unique_visitors=cleaned.get("unique_visitors"),
        avg_time_seconds=cleaned.get("avg_time_seconds"),
        bounce_rate=cleaned.get("bounce_rate"),
        ctr=cleaned.get("ctr"),
        impressions=cleaned.get("impressions"),
        conversions=cleaned.get("conversions"),
        position_avg=cleaned.get("position_avg"),
        source=cleaned.get("source", "manual"),
        metadata_json=metrics.get("metadata") if isinstance(metrics.get("metadata"), dict) else None,
    )
    db.add(snap)
    db.flush()

    record.last_checked_at = datetime.now(timezone.utc)
    update_content_performance(db, publication_record_id)
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
        perf.performance_feedback_json = {
            "formula_version": "v1",
            "weights": {"views": 0.35, "ctr": 0.25, "position": 0.25, "conversions": 0.15},
            "last_snapshot_id": latest.id,
            "ready_for_ai_optimization": False,
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
