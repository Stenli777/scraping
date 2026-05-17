"""Extended scheduler status for API and admin."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
from app.models.automation_run import AutomationRun, AutomationRunStatus
from app.models.scheduler_state import SchedulerState
from app.scheduler.heartbeat import get_heartbeat_status
from app.scheduler.locks import LOCK_KEY, get_state, heartbeat_age_seconds


def build_scheduler_status(db: Session) -> dict:
    settings = get_settings()
    now_running = db.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(
            AutomationRun.status.in_(
                [AutomationRunStatus.RUNNING, AutomationRunStatus.CANCEL_REQUESTED]
            )
        )
    ) or 0
    queued = db.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(AutomationRun.status == AutomationRunStatus.QUEUED)
    ) or 0

    stale_cutoff = settings.automation_run_stale_seconds
    stale_running = []
    for run in db.scalars(
        select(AutomationRun).where(
            AutomationRun.status.in_(
                [AutomationRunStatus.RUNNING, AutomationRunStatus.CANCEL_REQUESTED]
            )
        )
    ).all():
        if run.heartbeat_at:
            from datetime import datetime, timezone

            age = (datetime.now(timezone.utc) - run.heartbeat_at).total_seconds()
            if age > stale_cutoff:
                stale_running.append(
                    {"id": run.id, "heartbeat_age_seconds": int(age), "status": run.status}
                )

    lock = get_state(db, LOCK_KEY)
    lock_owner = None
    if lock and lock.value:
        lock_owner = lock.value.split("|", 1)[0]

    last_error_row = db.get(SchedulerState, "scheduler_last_error")
    last_loop_error = last_error_row.value if last_error_row else None

    return {
        "scheduler_enabled": is_scheduler_enabled(),
        "automation_enabled": is_automation_enabled(),
        "heartbeat": get_heartbeat_status(db),
        "scheduler_heartbeat_age_seconds": heartbeat_age_seconds(db),
        "running_runs": now_running,
        "queued_runs": queued,
        "stale_running_runs": stale_running,
        "lock_owner": lock_owner,
        "last_loop_error": last_loop_error,
        "max_concurrent_runs": settings.automation_max_concurrent_runs,
    }
