"""Operational incident history — bounded, operator-oriented (Ops Stability Phase)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.operational_incident import OperationalIncident
from app.services.runtime_diagnostics_service import (
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    build_governance_drift_warnings,
    build_llm_diagnostics,
    build_publish_diagnostics,
    build_queue_summary,
)

INCIDENT_RETENTION_DAYS = 30
MAX_INCIDENT_ROWS = 300
DEDUPE_MINUTES = 30
LIST_DEFAULT_LIMIT = 50


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def cleanup_old_incidents(db: Session) -> int:
    cutoff = _utcnow() - timedelta(days=INCIDENT_RETENTION_DAYS)
    r1 = db.execute(delete(OperationalIncident).where(OperationalIncident.created_at < cutoff))
    deleted = r1.rowcount or 0
    total = db.scalar(select(func.count()).select_from(OperationalIncident)) or 0
    if total > MAX_INCIDENT_ROWS:
        excess = total - MAX_INCIDENT_ROWS
        oldest_ids = list(
            db.scalars(
                select(OperationalIncident.id)
                .order_by(OperationalIncident.created_at.asc())
                .limit(excess)
            ).all()
        )
        if oldest_ids:
            r2 = db.execute(
                delete(OperationalIncident).where(OperationalIncident.id.in_(oldest_ids))
            )
            deleted += r2.rowcount or 0
    return deleted


def _recent_same_kind(
    db: Session, kind: str, *, ref_type: str | None = None, ref_id: int | None = None
) -> bool:
    cutoff = _utcnow() - timedelta(minutes=DEDUPE_MINUTES)
    q = select(OperationalIncident.id).where(
        OperationalIncident.kind == kind,
        OperationalIncident.created_at >= cutoff,
    )
    if ref_type is not None:
        q = q.where(OperationalIncident.ref_type == ref_type)
    if ref_id is not None:
        q = q.where(OperationalIncident.ref_id == ref_id)
    return db.scalar(q.limit(1)) is not None


def record_incident(
    db: Session,
    *,
    kind: str,
    severity: str,
    summary: str,
    context: dict[str, Any] | None = None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    dedupe: bool = True,
) -> OperationalIncident | None:
    if dedupe and _recent_same_kind(db, kind, ref_type=ref_type, ref_id=ref_id):
        return None
    row = OperationalIncident(
        kind=kind[:48],
        severity=severity[:16],
        summary=summary[:512],
        context_json=context or {},
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(row)
    db.flush()
    return row


def sync_incidents_from_runtime(db: Session) -> int:
    """Record lightweight incidents from current diagnostics signals."""
    from app.services.runtime_diagnostics_service import _count_approved_stale_release_candidates

    recorded = 0
    queue = build_queue_summary(db)
    publish = build_publish_diagnostics(db, limit=10)
    drift = build_governance_drift_warnings(db)
    llm = build_llm_diagnostics(db)

    pressure = queue.get("backlog_pressure", "low")
    if pressure in ("medium", "high"):
        sev = SEVERITY_CRITICAL if pressure == "high" else SEVERITY_WARNING
        if record_incident(
            db,
            kind="queue_pressure",
            severity=sev,
            summary=f"Queue backlog pressure: {pressure}",
            context={"queued": queue["scraping_tasks"]["queued"], "failed_retryable": queue["scraping_tasks"]["failed_retryable"]},
            ref_type="queue",
        ):
            recorded += 1

    stale_n = _count_approved_stale_release_candidates(db)
    if stale_n:
        if record_incident(
            db,
            kind="stale_rc_approved",
            severity=SEVERITY_WARNING,
            summary=f"{stale_n} approved RC(s) bind stale revision",
            context={"count": stale_n},
            ref_type="release_candidate",
        ):
            recorded += 1

    for w in drift:
        if w.get("severity") == SEVERITY_CRITICAL:
            wid = w.get("id", "drift")
            if record_incident(
                db,
                kind="drift_critical",
                severity=SEVERITY_CRITICAL,
                summary=w.get("message", wid)[:512],
                context={"drift_id": wid},
                ref_type="drift",
                ref_id=None,
            ):
                recorded += 1

    if llm.get("failed_count_24h", 0) >= 5:
        if record_incident(
            db,
            kind="llm_failure_spike",
            severity=SEVERITY_WARNING,
            summary=f"LLM failures 24h: {llm['failed_count_24h']}",
            context={"failed_count_24h": llm["failed_count_24h"]},
            ref_type="llm",
        ):
            recorded += 1

    for f in publish.get("failed_recent", [])[:5]:
        rid = f.get("id")
        if rid and record_incident(
            db,
            kind="publish_failed",
            severity=SEVERITY_WARNING,
            summary=f"Publish run #{rid} failed (doc #{f.get('document_id')})",
            context={"status": f.get("status"), "error": (f.get("error_message") or "")[:200]},
            ref_type="publish_run",
            ref_id=rid,
        ):
            recorded += 1

    for fp in publish.get("force_publish_sample", [])[:3]:
        rid = fp.get("id")
        if rid and record_incident(
            db,
            kind="force_publish",
            severity=SEVERITY_INFO,
            summary=f"Force publish run #{rid} (doc #{fp.get('document_id')})",
            context={"force_reason": fp.get("force_reason")},
            ref_type="publish_run",
            ref_id=rid,
        ):
            recorded += 1

    cleanup_old_incidents(db)
    return recorded


def list_recent_incidents(db: Session, *, limit: int = LIST_DEFAULT_LIMIT) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(OperationalIncident)
            .order_by(OperationalIncident.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "severity": r.severity,
            "summary": r.summary,
            "context": r.context_json or {},
            "ref_type": r.ref_type,
            "ref_id": r.ref_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def build_incident_history(db: Session) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(OperationalIncident)) or 0
    by_kind: dict[str, int] = {}
    for kind, cnt in db.execute(
        select(OperationalIncident.kind, func.count())
        .group_by(OperationalIncident.kind)
        .order_by(func.count().desc())
    ).all():
        by_kind[kind] = cnt
    return {
        "read_only": True,
        "not_ticketing": True,
        "retention_days": INCIDENT_RETENTION_DAYS,
        "max_rows": MAX_INCIDENT_ROWS,
        "total": total,
        "by_kind": by_kind,
        "recent": list_recent_incidents(db),
    }
