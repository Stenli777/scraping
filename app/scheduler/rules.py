"""Schedule evaluation for automation rules."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation_rule import AutomationRule
from app.models.automation_run import AutomationRun


def _parse_cron_minute_interval(cron: str | None) -> int | None:
    """Support '*/30 * * * *' -> every 30 minutes."""
    if not cron:
        return None
    parts = cron.strip().split()
    if len(parts) != 5:
        return None
    minute, hour, *_ = parts
    if minute.startswith("*/") and hour == "*":
        try:
            return int(minute[2:])
        except ValueError:
            return None
    return None


def _parse_cron_hour_interval(cron: str | None) -> int | None:
    """Support simple patterns: '0 */6 * * *' -> every 6 hours at minute 0."""
    if not cron:
        return None
    parts = cron.strip().split()
    if len(parts) != 5:
        return None
    minute, hour, *_ = parts
    if minute != "0" or not hour.startswith("*/"):
        return None
    try:
        return int(hour[2:])
    except ValueError:
        return None


def is_rule_due(db: Session, rule: AutomationRule) -> bool:
    if not rule.enabled:
        return False
    if rule.trigger_type == "manual":
        return False
    if rule.trigger_type == "event":
        return False

    config = rule.config_json or {}
    interval_hours = config.get("interval_hours")
    interval_minutes = config.get("interval_minutes")

    last_run = db.scalar(
        select(AutomationRun)
        .where(AutomationRun.automation_rule_id == rule.id)
        .order_by(AutomationRun.id.desc())
    )
    now = datetime.now(timezone.utc)

    if rule.trigger_type == "scheduled":
        cron_mins = _parse_cron_minute_interval(rule.schedule_cron)
        if cron_mins:
            if now.minute % cron_mins > 2:
                return False
            if last_run and last_run.created_at:
                elapsed = (now - last_run.created_at).total_seconds()
                if elapsed < cron_mins * 60 - 30:
                    return False
            return True

        cron_hours = _parse_cron_hour_interval(rule.schedule_cron)
        if cron_hours:
            if now.minute > 5:
                return False
            if now.hour % cron_hours != 0:
                return False
            if last_run and last_run.created_at:
                elapsed = (now - last_run.created_at).total_seconds()
                if elapsed < cron_hours * 3600 - 300:
                    return False
            return True

        if interval_hours:
            if last_run and last_run.created_at:
                if (now - last_run.created_at).total_seconds() < interval_hours * 3600:
                    return False
            return True
        if interval_minutes:
            if last_run and last_run.created_at:
                if (now - last_run.created_at).total_seconds() < interval_minutes * 60:
                    return False
            return True
    return False


def next_run_preview(rule: AutomationRule, db: Session) -> str:
    if rule.trigger_type == "manual":
        return "manual only"
    if not rule.enabled:
        return "disabled"
    hours = _parse_cron_hour_interval(rule.schedule_cron)
    if hours:
        return f"every {hours}h (cron {rule.schedule_cron})"
    cfg = rule.config_json or {}
    if cfg.get("interval_hours"):
        return f"every {cfg['interval_hours']}h"
    if cfg.get("interval_minutes"):
        return f"every {cfg['interval_minutes']}m"
    return "schedule not configured"
