"""DB-backed scheduler locks — single active owner."""

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.automation_run import AutomationRun, AutomationRunStatus
from app.models.scheduler_state import SchedulerState
from app.services.automation_service import log_event

LOCK_KEY = "scheduler_lock"
HEARTBEAT_KEY = "scheduler_heartbeat"
STALE_LOCK_SECONDS = 300


def get_state(db: Session, key: str) -> SchedulerState | None:
    return db.get(SchedulerState, key)


def set_state(db: Session, key: str, value: str) -> None:
    row = db.get(SchedulerState, key)
    if row:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SchedulerState(key=key, value=value))
    db.flush()


def acquire_lock(db: Session, owner: str | None = None) -> bool:
    owner = owner or f"pid:{os.getpid()}"
    now = datetime.now(timezone.utc)
    lock = get_state(db, LOCK_KEY)
    if lock and lock.value:
        parts = lock.value.split("|", 1)
        lock_owner = parts[0]
        try:
            lock_time = datetime.fromisoformat(parts[1]) if len(parts) > 1 else now
            if lock_time.tzinfo is None:
                lock_time = lock_time.replace(tzinfo=timezone.utc)
        except ValueError:
            lock_time = now - timedelta(seconds=STALE_LOCK_SECONDS + 1)
        age = (now - lock_time).total_seconds()
        if lock_owner != owner and age < STALE_LOCK_SECONDS:
            return False
    set_state(db, LOCK_KEY, f"{owner}|{now.isoformat()}")
    db.commit()
    return True


def release_lock(db: Session, owner: str | None = None) -> None:
    owner = owner or f"pid:{os.getpid()}"
    lock = get_state(db, LOCK_KEY)
    if lock and lock.value and lock.value.startswith(owner):
        db.delete(lock)
        db.commit()


def touch_heartbeat(db: Session) -> None:
    set_state(db, HEARTBEAT_KEY, datetime.now(timezone.utc).isoformat())
    db.commit()


def heartbeat_age_seconds(db: Session) -> float | None:
    row = get_state(db, HEARTBEAT_KEY)
    if not row or not row.value:
        return None
    try:
        ts = datetime.fromisoformat(row.value)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except ValueError:
        return None


def recover_stale_runs(db: Session) -> int:
    """Mark runs stale by heartbeat_at — no auto-restart."""
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.automation_run_stale_seconds)
    stale = list(
        db.scalars(
            select(AutomationRun).where(
                AutomationRun.status.in_(
                    [AutomationRunStatus.RUNNING, AutomationRunStatus.CANCEL_REQUESTED]
                ),
                AutomationRun.heartbeat_at.isnot(None),
                AutomationRun.heartbeat_at < cutoff,
            )
        ).all()
    )
    # fallback: started_at for runs without heartbeat
    stale_no_hb = list(
        db.scalars(
            select(AutomationRun).where(
                AutomationRun.status == AutomationRunStatus.RUNNING,
                AutomationRun.heartbeat_at.is_(None),
                AutomationRun.started_at.isnot(None),
                AutomationRun.started_at < cutoff,
            )
        ).all()
    )
    all_stale = {r.id: r for r in stale + stale_no_hb}.values()
    for run in all_stale:
        run.status = AutomationRunStatus.FAILED
        run.error_message = "stale run recovered by scheduler (heartbeat timeout)"
        run.completed_at = datetime.now(timezone.utc)
        run.locked_by = None
        run.lock_expires_at = None
        log_event(run, "error", run.error_message)
    if all_stale:
        db.commit()
    return len(all_stale)
