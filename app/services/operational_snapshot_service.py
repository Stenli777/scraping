"""Operational snapshots, trends, incident memory (Phase D) ??? bounded, no metrics platform."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.feature_flags import all_flags
from app.models.operational_snapshot import OperationalSnapshot
from app.models.scheduler_state import SchedulerState
from app.services.runtime_diagnostics_service import (
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    build_governance_drift_warnings,
    build_llm_diagnostics,
    build_publish_diagnostics,
    build_queue_summary,
)

# Retention & capture guardrails
RETENTION_DAYS = 30
MAX_SNAPSHOT_ROWS = 500
MIN_CAPTURE_INTERVAL_SECONDS = 900  # 15 minutes
TREND_WINDOW_SNAPSHOTS = 48
INCIDENT_MEMORY_LIMIT = 20
DRIFT_HISTORY_SNAPSHOTS = 72

THROTTLE_KEY = "ops_snapshot_last_capture_at"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _compact_metrics(db: Session) -> dict[str, Any]:
    """Single-pass compact metrics for snapshot storage (no secrets)."""
    queue = build_queue_summary(db)
    drift = build_governance_drift_warnings(db)
    llm = build_llm_diagnostics(db)
    publish = build_publish_diagnostics(db, limit=5)

    st = queue["scraping_tasks"]
    drift_by_sev = {SEVERITY_CRITICAL: 0, SEVERITY_WARNING: 0, SEVERITY_INFO: 0}
    drift_ids: list[str] = []
    for w in drift:
        drift_by_sev[w.get("severity", SEVERITY_INFO)] = (
            drift_by_sev.get(w.get("severity", SEVERITY_INFO), 0) + 1
        )
        drift_ids.append(w["id"])

    flags = all_flags()
    safe_flags = {k: bool(v) for k, v in flags.items()}

    return {
        "queue_queued": st["queued"],
        "queue_running": st["running"],
        "queue_failed_retryable": st["failed_retryable"],
        "queue_failed_terminal": st["failed_terminal"],
        "queue_stale_running": st["stale_running_count"],
        "backlog_pressure": queue["backlog_pressure"],
        "enrichment_queued": queue["enrichment_jobs"]["queued"],
        "enrichment_failed_retryable": queue["enrichment_jobs"]["failed_retryable"],
        "llm_failed_24h": llm.get("failed_count_24h", 0),
        "llm_rate_limit_hints": llm.get("rate_limit_hint_count", 0),
        "publish_failed_sample": publish.get("failed_recent_count", 0),
        "force_without_reason_total": publish.get("force_without_reason_total", 0),
        "drift_critical": drift_by_sev.get(SEVERITY_CRITICAL, 0),
        "drift_warning": drift_by_sev.get(SEVERITY_WARNING, 0),
        "drift_info": drift_by_sev.get(SEVERITY_INFO, 0),
        "drift_ids": drift_ids[:20],
        "feature_flags": safe_flags,
    }


def _get_last_capture_at(db: Session) -> datetime | None:
    row = db.get(SchedulerState, THROTTLE_KEY)
    if not row or not row.value:
        return None
    try:
        return datetime.fromisoformat(row.value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _set_last_capture_at(db: Session, when: datetime) -> None:
    row = db.get(SchedulerState, THROTTLE_KEY)
    val = when.isoformat()
    if row:
        row.value = val
    else:
        db.add(SchedulerState(key=THROTTLE_KEY, value=val))
    db.flush()


def cleanup_old_snapshots(db: Session) -> int:
    """Bounded retention: age + max rows."""
    cutoff = _utcnow() - timedelta(days=RETENTION_DAYS)
    r1 = db.execute(
        delete(OperationalSnapshot).where(OperationalSnapshot.captured_at < cutoff)
    )
    deleted = r1.rowcount or 0

    total = db.scalar(select(func.count()).select_from(OperationalSnapshot)) or 0
    if total > MAX_SNAPSHOT_ROWS:
        excess = total - MAX_SNAPSHOT_ROWS
        oldest_ids = list(
            db.scalars(
                select(OperationalSnapshot.id)
                .order_by(OperationalSnapshot.captured_at.asc())
                .limit(excess)
            ).all()
        )
        if oldest_ids:
            r2 = db.execute(
                delete(OperationalSnapshot).where(OperationalSnapshot.id.in_(oldest_ids))
            )
            deleted += r2.rowcount or 0
    return deleted


def capture_operational_snapshot(
    db: Session, *, source: str = "diagnostics", force: bool = False
) -> OperationalSnapshot | None:
    """Persist compact operational metrics. Returns None if throttled."""
    if not force:
        last = _get_last_capture_at(db)
        if last:
            age = (_utcnow() - last).total_seconds()
            if age < MIN_CAPTURE_INTERVAL_SECONDS:
                return None

    metrics = _compact_metrics(db)
    snap = OperationalSnapshot(source=source[:32], metrics_json=metrics)
    db.add(snap)
    _set_last_capture_at(db, _utcnow())
    cleanup_old_snapshots(db)
    db.flush()
    return snap


def maybe_capture_snapshot(db: Session, *, source: str = "diagnostics") -> bool:
    return capture_operational_snapshot(db, source=source) is not None


def list_recent_snapshots(db: Session, *, limit: int = TREND_WINDOW_SNAPSHOTS) -> list[OperationalSnapshot]:
    return list(
        db.scalars(
            select(OperationalSnapshot)
            .order_by(OperationalSnapshot.captured_at.desc())
            .limit(limit)
        ).all()
    )


def build_queue_trends(db: Session) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(OperationalSnapshot)
            .order_by(OperationalSnapshot.captured_at.asc())
            .limit(TREND_WINDOW_SNAPSHOTS)
        ).all()
    )
    if not rows:
        return {
            "sample_note": "No snapshots yet; open /admin/diagnostics periodically to build history.",
            "points": [],
            "window_snapshots": 0,
        }

    points = []
    for s in rows:
        m = s.metrics_json or {}
        points.append(
            {
                "at": s.captured_at.isoformat() if s.captured_at else None,
                "queued": m.get("queue_queued", 0),
                "running": m.get("queue_running", 0),
                "failed_retryable": m.get("queue_failed_retryable", 0),
                "stale_running": m.get("queue_stale_running", 0),
                "pressure": m.get("backlog_pressure", "low"),
            }
        )

    first, last = points[0], points[-1]
    return {
        "sample_note": f"Last {len(points)} snapshots (max {TREND_WINDOW_SNAPSHOTS}), not realtime.",
        "window_snapshots": len(points),
        "points": points,
        "delta": {
            "queued": last["queued"] - first["queued"],
            "failed_retryable": last["failed_retryable"] - first["failed_retryable"],
            "stale_running": last["stale_running"] - first["stale_running"],
        },
        "latest_pressure": last.get("pressure"),
    }


def build_llm_failure_trends(db: Session) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(OperationalSnapshot)
            .order_by(OperationalSnapshot.captured_at.asc())
            .limit(TREND_WINDOW_SNAPSHOTS)
        ).all()
    )
    points = [
        {
            "at": s.captured_at.isoformat() if s.captured_at else None,
            "failed_24h": (s.metrics_json or {}).get("llm_failed_24h", 0),
            "rate_limit_hints": (s.metrics_json or {}).get("llm_rate_limit_hints", 0),
        }
        for s in rows
    ]
    max_failed = max((p["failed_24h"] for p in points), default=0)
    degradation = max_failed >= 5 or any(p["rate_limit_hints"] >= 2 for p in points[-6:])
    return {
        "sample_note": "Derived from operational snapshots; live detail in diagnostics.llm.",
        "points": points,
        "degradation_window": degradation,
        "max_failed_24h_in_window": max_failed,
    }


def build_drift_history(db: Session) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(OperationalSnapshot)
            .order_by(OperationalSnapshot.captured_at.desc())
            .limit(DRIFT_HISTORY_SNAPSHOTS)
        ).all()
    )
    id_counts: dict[str, int] = {}
    recurring: list[dict[str, Any]] = []
    for s in rows:
        m = s.metrics_json or {}
        for did in m.get("drift_ids") or []:
            id_counts[did] = id_counts.get(did, 0) + 1
    for did, cnt in sorted(id_counts.items(), key=lambda x: -x[1])[:15]:
        if cnt >= 2:
            recurring.append({"drift_id": did, "occurrences": cnt})

    return {
        "sample_note": f"Recurring drift IDs across last {len(rows)} snapshots (visibility only).",
        "recurring_warnings": recurring,
        "latest_drift_counts": (
            {
                "critical": (rows[0].metrics_json or {}).get("drift_critical", 0),
                "warning": (rows[0].metrics_json or {}).get("drift_warning", 0),
                "info": (rows[0].metrics_json or {}).get("drift_info", 0),
            }
            if rows
            else {}
        ),
        "no_auto_remediation": True,
    }


def build_incident_memory(db: Session) -> dict[str, Any]:
    """Lightweight episodes from snapshots ??? not a ticketing system."""
    rows = list(
        db.scalars(
            select(OperationalSnapshot)
            .order_by(OperationalSnapshot.captured_at.desc())
            .limit(100)
        ).all()
    )
    episodes: list[dict[str, Any]] = []
    for s in rows:
        m = s.metrics_json or {}
        pressure = m.get("backlog_pressure", "low")
        critical = m.get("drift_critical", 0)
        stale = m.get("queue_stale_running", 0)
        llm_fail = m.get("llm_failed_24h", 0)
        pub_fail = m.get("publish_failed_sample", 0)

        reasons = []
        if pressure in ("medium", "high"):
            reasons.append(f"queue pressure {pressure}")
        if critical:
            reasons.append(f"drift critical={critical}")
        if stale >= 2:
            reasons.append(f"stale running={stale}")
        if llm_fail >= 5:
            reasons.append(f"llm failures 24h={llm_fail}")
        if pub_fail >= 2:
            reasons.append("publish failures in sample")

        if reasons:
            episodes.append(
                {
                    "captured_at": s.captured_at.isoformat() if s.captured_at else None,
                    "snapshot_id": s.id,
                    "reasons": reasons,
                    "summary": "; ".join(reasons),
                }
            )
        if len(episodes) >= INCIDENT_MEMORY_LIMIT:
            break

    return {
        "read_only": True,
        "not_ticketing": True,
        "retention_days": RETENTION_DAYS,
        "max_rows": MAX_SNAPSHOT_ROWS,
        "episodes": episodes,
        "episode_count": len(episodes),
    }


def build_snapshot_comparison(db: Session) -> dict[str, Any]:
    """Compare latest snapshot to previous — operator debugging hint."""
    rows = list(
        db.scalars(
            select(OperationalSnapshot)
            .order_by(OperationalSnapshot.captured_at.desc())
            .limit(2)
        ).all()
    )
    if len(rows) < 2:
        return {
            "available": False,
            "sample_note": "Need at least 2 snapshots; open /admin/diagnostics periodically.",
        }
    cur, prev = rows[0], rows[1]
    cm, pm = cur.metrics_json or {}, prev.metrics_json or {}

    def _delta(key: str) -> int:
        return int(cm.get(key, 0) or 0) - int(pm.get(key, 0) or 0)

    return {
        "available": True,
        "current_at": cur.captured_at.isoformat() if cur.captured_at else None,
        "previous_at": prev.captured_at.isoformat() if prev.captured_at else None,
        "delta": {
            "queue_queued": _delta("queue_queued"),
            "queue_failed_retryable": _delta("queue_failed_retryable"),
            "queue_stale_running": _delta("queue_stale_running"),
            "llm_failed_24h": _delta("llm_failed_24h"),
            "publish_failed_sample": _delta("publish_failed_sample"),
            "drift_critical": _delta("drift_critical"),
        },
        "pressure_changed": cm.get("backlog_pressure") != pm.get("backlog_pressure"),
        "current_pressure": cm.get("backlog_pressure"),
        "previous_pressure": pm.get("backlog_pressure"),
    }


def build_operational_history(db: Session) -> dict[str, Any]:
    """Aggregate trends + drift history + incident memory for diagnostics."""
    total = db.scalar(select(func.count()).select_from(OperationalSnapshot)) or 0
    return {
        "bounded_history": True,
        "not_realtime": True,
        "not_metrics_platform": True,
        "snapshot_total": total,
        "retention": {
            "max_days": RETENTION_DAYS,
            "max_rows": MAX_SNAPSHOT_ROWS,
            "min_capture_interval_seconds": MIN_CAPTURE_INTERVAL_SECONDS,
        },
        "snapshot_comparison": build_snapshot_comparison(db),
        "queue_trends": build_queue_trends(db),
        "llm_trends": build_llm_failure_trends(db),
        "drift_history": build_drift_history(db),
        "incident_memory": build_incident_memory(db),
    }
