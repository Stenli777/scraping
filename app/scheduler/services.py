"""Scheduler tick — evaluate rules and dispatch automation."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
from app.models.automation_run import AutomationRun
from app.models.automation_rule import AutomationRule
from app.models.scheduler_state import SchedulerState
from app.scheduler.locks import recover_stale_runs
from app.scheduler.rules import is_rule_due
from app.services.automation_service import execute_automation_rule

logger = logging.getLogger(__name__)


def _hour_bucket() -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d%H")


def _day_bucket() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_counter(db: Session, key: str) -> int:
    row = db.get(SchedulerState, key)
    if not row or not row.value:
        return 0
    try:
        return int(row.value)
    except ValueError:
        return 0


def _incr_counter(db: Session, key: str) -> int:
    val = _get_counter(db, key) + 1
    row = db.get(SchedulerState, key)
    if row:
        row.value = str(val)
    else:
        db.add(SchedulerState(key=key, value=str(val)))
    db.flush()
    return val


def _running_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(AutomationRun).where(AutomationRun.status == "running")
    ) or 0


def can_start_automation(db: Session, rule: AutomationRule) -> tuple[bool, str]:
    settings = get_settings()
    if _running_count(db) >= settings.automation_max_concurrent_runs:
        return False, "max concurrent runs"
    hour_key = f"automation_hour:{_hour_bucket()}"
    if _get_counter(db, hour_key) >= settings.automation_global_hourly_limit:
        return False, "global hourly limit"
    rule_hour_key = f"automation_rule_hour:{rule.id}:{_hour_bucket()}"
    if _get_counter(db, rule_hour_key) >= rule.rate_limit_per_hour:
        return False, "rule hourly limit"
    day_key = f"automation_rule_day:{rule.id}:{_day_bucket()}"
    if _get_counter(db, day_key) >= rule.max_daily_runs:
        return False, "rule daily limit"
    return True, ""


def tick_automation(db: Session) -> dict:
    if not is_scheduler_enabled() or not is_automation_enabled():
        return {"skipped": True}

    recovered = recover_stale_runs(db)
    rules = list(db.scalars(select(AutomationRule).where(AutomationRule.enabled.is_(True))).all())
    started = 0
    skipped = 0
    for rule in rules:
        if not is_rule_due(db, rule):
            continue
        ok, reason = can_start_automation(db, rule)
        if not ok:
            skipped += 1
            logger.info("Rule %s skipped: %s", rule.id, reason)
            continue
        try:
            execute_automation_rule(db, rule.id, trigger="scheduled")
            _incr_counter(db, f"automation_hour:{_hour_bucket()}")
            _incr_counter(db, f"automation_rule_hour:{rule.id}:{_hour_bucket()}")
            _incr_counter(db, f"automation_rule_day:{rule.id}:{_day_bucket()}")
            db.commit()
            started += 1
        except Exception as exc:
            logger.exception("Automation rule %s failed: %s", rule.id, exc)
            db.rollback()
    return {"recovered_stale": recovered, "started": started, "skipped": skipped}
