"""Scheduler tick — queued runs first, then schedule new runs."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
from app.models.automation_run import AutomationRun, AutomationRunStatus
from app.models.automation_rule import AutomationRule
from app.models.scheduler_state import SchedulerState
from app.scheduler.locks import recover_stale_runs, set_state
from app.scheduler.rules import is_rule_due
from app.services.automation_service import (
    _get_counter,
    _hour_bucket,
    _rule_has_active_run,
    enqueue_automation_run,
    get_rule_rate_usage,
    process_automation_run,
)

logger = logging.getLogger(__name__)


def _running_count(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(
            AutomationRun.status.in_(
                [AutomationRunStatus.RUNNING, AutomationRunStatus.CANCEL_REQUESTED]
            )
        )
    ) or 0


def _queued_count(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(AutomationRun.status == AutomationRunStatus.QUEUED)
    ) or 0


def can_start_automation(db: Session, rule: AutomationRule) -> tuple[bool, str]:
    settings = get_settings()
    if _running_count(db) >= settings.automation_max_concurrent_runs:
        return False, "max concurrent runs"
    hour_key = f"automation_hour:{_hour_bucket()}"
    if _get_counter(db, hour_key) >= settings.automation_global_hourly_limit:
        return False, "global hourly limit"
    usage = get_rule_rate_usage(db, rule)
    if usage["hourly_remaining"] <= 0:
        return False, "rule hourly limit"
    if usage["daily_remaining"] <= 0:
        return False, "rule daily limit"
    return True, ""


def _pick_queued_runs(db: Session, limit: int) -> list[AutomationRun]:
    return list(
        db.scalars(
            select(AutomationRun)
            .where(AutomationRun.status == AutomationRunStatus.QUEUED)
            .order_by(AutomationRun.id.asc())
            .limit(limit)
        ).all()
    )


def process_queued_runs(db: Session) -> int:
    settings = get_settings()
    processed = 0
    slots = max(0, settings.automation_max_concurrent_runs - _running_count(db))
    if slots <= 0:
        return 0
    for run in _pick_queued_runs(db, slots):
        rule = db.get(AutomationRule, run.automation_rule_id)
        if not rule:
            continue
        ok, reason = can_start_automation(db, rule)
        if not ok:
            logger.info("Queued run %s waiting: %s", run.id, reason)
            continue
        try:
            process_automation_run(db, run.id)
            db.commit()
            processed += 1
        except Exception as exc:
            logger.exception("Queued run %s failed: %s", run.id, exc)
            db.rollback()
    return processed


def enqueue_due_scheduled_rules(db: Session) -> int:
    enqueued = 0
    rules = list(db.scalars(select(AutomationRule).where(AutomationRule.enabled.is_(True))).all())
    for rule in rules:
        if not is_rule_due(db, rule):
            continue
        if _rule_has_active_run(db, rule.id):
            continue
        ok, reason = can_start_automation(db, rule)
        if not ok:
            logger.info("Scheduled rule %s skipped: %s", rule.id, reason)
            continue
        try:
            enqueue_automation_run(db, rule.id, trigger="scheduled", requested_by="scheduler")
            enqueued += 1
        except Exception as exc:
            logger.exception("Enqueue scheduled rule %s failed: %s", rule.id, exc)
            db.rollback()
    return enqueued


def tick_automation(db: Session) -> dict:
    if not is_scheduler_enabled():
        return {"skipped": True, "reason": "scheduler disabled"}
    if not is_automation_enabled():
        return {
            "skipped": True,
            "reason": "automation disabled",
            "queued_runs": _queued_count(db),
        }

    recovered = recover_stale_runs(db)
    queued_processed = process_queued_runs(db)
    scheduled_enqueued = enqueue_due_scheduled_rules(db)
    # second pass for newly enqueued scheduled runs
    if scheduled_enqueued:
        queued_processed += process_queued_runs(db)

    return {
        "recovered_stale": recovered,
        "queued_processed": queued_processed,
        "scheduled_enqueued": scheduled_enqueued,
        "queued_remaining": _queued_count(db),
        "running": _running_count(db),
    }
