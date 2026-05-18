"""Lightweight enrichment metrics (no Prometheus)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.llm_enrichment_job import EnrichmentJobStatus, LlmEnrichmentJob


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_enrichment_metrics(db: Session, *, window_hours: int = 24) -> dict[str, Any]:
    since = _utcnow() - timedelta(hours=window_hours)
    total = db.scalar(select(func.count()).select_from(LlmEnrichmentJob)) or 0
    recent_q = select(LlmEnrichmentJob).where(LlmEnrichmentJob.created_at >= since)

    by_status: dict[str, int] = {}
    for status in (
        EnrichmentJobStatus.QUEUED,
        EnrichmentJobStatus.RUNNING,
        EnrichmentJobStatus.COMPLETED,
        EnrichmentJobStatus.FAILED_RETRYABLE,
        EnrichmentJobStatus.FAILED_TERMINAL,
        EnrichmentJobStatus.CANCELLED,
        EnrichmentJobStatus.SKIPPED,
    ):
        by_status[status] = db.scalar(
            select(func.count()).select_from(LlmEnrichmentJob).where(LlmEnrichmentJob.status == status)
        ) or 0

    by_type_rows = db.execute(
        select(LlmEnrichmentJob.enrichment_type, func.count())
        .group_by(LlmEnrichmentJob.enrichment_type)
    ).all()
    by_type = {row[0]: row[1] for row in by_type_rows}

    completed = by_status.get(EnrichmentJobStatus.COMPLETED, 0)
    retryable = by_status.get(EnrichmentJobStatus.FAILED_RETRYABLE, 0)
    terminal = by_status.get(EnrichmentJobStatus.FAILED_TERMINAL, 0)
    skipped = by_status.get(EnrichmentJobStatus.SKIPPED, 0)
    finished = completed + retryable + terminal + skipped
    completed_pct = round(100.0 * completed / finished, 1) if finished else 0.0
    retryable_pct = round(100.0 * retryable / finished, 1) if finished else 0.0

    # avg latency completed jobs (recent)
    latencies: list[int] = []
    for job in db.scalars(
        select(LlmEnrichmentJob)
        .where(
            LlmEnrichmentJob.status == EnrichmentJobStatus.COMPLETED,
            LlmEnrichmentJob.started_at.isnot(None),
            LlmEnrichmentJob.completed_at.isnot(None),
        )
        .order_by(LlmEnrichmentJob.id.desc())
        .limit(200)
    ).all():
        s, c = job.started_at, job.completed_at
        if s and c:
            if s.tzinfo is None:
                s = s.replace(tzinfo=timezone.utc)
            if c.tzinfo is None:
                c = c.replace(tzinfo=timezone.utc)
            latencies.append(int((c - s).total_seconds() * 1000))
    avg_latency_ms = int(sum(latencies) / len(latencies)) if latencies else None

    timeout_count = db.scalar(
        select(func.count()).select_from(LlmEnrichmentJob).where(
            LlmEnrichmentJob.error_message.ilike("%timeout%")
        )
    ) or 0
    timeout_pct = round(100.0 * timeout_count / total, 1) if total else 0.0

    settings = get_settings()
    stale_cutoff = _utcnow() - timedelta(seconds=settings.enrichment_stale_seconds)
    stale_running = db.scalar(
        select(func.count()).select_from(LlmEnrichmentJob).where(
            LlmEnrichmentJob.status == EnrichmentJobStatus.RUNNING,
            LlmEnrichmentJob.heartbeat_at < stale_cutoff,
        )
    ) or 0

    return {
        "window_hours": window_hours,
        "total_jobs": total,
        "by_status": by_status,
        "by_type": by_type,
        "completed_pct": completed_pct,
        "retryable_pct": retryable_pct,
        "avg_latency_ms": avg_latency_ms,
        "timeout_pct": timeout_pct,
        "skipped_pct": round(100.0 * skipped / finished, 1) if finished else 0.0,
        "stale_recovered_running": stale_running,
        "queue_depth": by_status.get(EnrichmentJobStatus.QUEUED, 0),
        "running": by_status.get(EnrichmentJobStatus.RUNNING, 0),
    }


def get_enrichment_health(db: Session) -> dict[str, Any]:
    metrics = get_enrichment_metrics(db, window_hours=1)
    settings = get_settings()
    queue_depth = metrics["queue_depth"]
    stale = metrics["stale_recovered_running"]
    failed_retryable = metrics["by_status"].get(EnrichmentJobStatus.FAILED_RETRYABLE, 0)

    status = "ok"
    if stale > 0 or queue_depth >= settings.enrichment_degraded_queue_threshold:
        status = "degraded"
    if stale >= settings.enrichment_severe_stale_threshold:
        status = "degraded"

    return {
        "status": status,
        "queue_depth": queue_depth,
        "running": metrics["running"],
        "stale_jobs": stale,
        "failed_retryable": failed_retryable,
        "failed_terminal": metrics["by_status"].get(EnrichmentJobStatus.FAILED_TERMINAL, 0),
    }
