"""Controlled automation — async runs, progress, cancel, audit."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import DiscoveredUrlStatus, TaskStatus
from app.core.feature_flags import (
    is_automation_enabled,
    is_quality_review_enabled,
    is_source_discovery_enabled,
)
from app.models.automation_run import AutomationRun, AutomationRunStatus
from app.models.automation_rule import AutomationRule
from app.models.discovered_url import DiscoveredUrl
from app.models.parsed_document import ParsedDocument
from app.models.scraping_task import ScrapingTask
from app.services.discovery_service import enqueue_discovered_url, run_discovery
from app.services.quality_service import get_latest_quality_score, run_quality_for_document

logger = logging.getLogger(__name__)


class AutomationError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _owner() -> str:
    return f"pid:{os.getpid()}"


def log_event(run: AutomationRun, level: str, message: str) -> None:
    events = list(run.logs_json or [])
    events.append({"ts": _utcnow().isoformat(), "level": level, "message": message})
    run.logs_json = events


def set_progress(run: AutomationRun, **fields: Any) -> None:
    progress = dict(run.progress_json or {})
    progress.update(fields)
    run.progress_json = progress


def touch_run_heartbeat(db: Session, run: AutomationRun) -> None:
    run.heartbeat_at = _utcnow()
    db.flush()


def is_cancel_requested(db: Session, run_id: int) -> bool:
    status = db.scalar(select(AutomationRun.status).where(AutomationRun.id == run_id))
    return status in (AutomationRunStatus.CANCEL_REQUESTED, AutomationRunStatus.CANCELLED)


def seed_default_rules(db: Session) -> None:
    existing = db.scalar(select(AutomationRule).limit(1))
    if existing:
        return
    rules = [
        AutomationRule(
            name="crmflow24 discovery every 6h",
            project_id=1,
            enabled=False,
            trigger_type="scheduled",
            schedule_cron="0 */6 * * *",
            automation_type="discovery",
            config_json={"source_directory_id": 1, "max_urls": 30, "interval_hours": 6},
            rate_limit_per_hour=4,
            max_daily_runs=24,
        ),
        AutomationRule(
            name="auto enqueue max 10/hour",
            project_id=1,
            enabled=False,
            trigger_type="scheduled",
            schedule_cron="0 * * * *",
            automation_type="enqueue",
            config_json={"batch_size": 5, "interval_minutes": 60},
            rate_limit_per_hour=10,
            max_daily_runs=100,
        ),
        AutomationRule(
            name="pipeline quality progression",
            project_id=None,
            enabled=False,
            trigger_type="scheduled",
            schedule_cron="*/30 * * * *",
            automation_type="pipeline_progression",
            config_json={"max_documents_per_run": 5, "interval_minutes": 30},
            rate_limit_per_hour=10,
            max_daily_runs=48,
        ),
    ]
    for r in rules:
        db.add(r)
    db.commit()


def _hour_bucket() -> str:
    return _utcnow().strftime("%Y%m%d%H")


def _day_bucket() -> str:
    return _utcnow().strftime("%Y-%m-%d")


def _get_counter(db: Session, key: str) -> int:
    from app.models.scheduler_state import SchedulerState

    row = db.get(SchedulerState, key)
    if not row or not row.value:
        return 0
    try:
        return int(row.value)
    except ValueError:
        return 0


def get_rule_rate_usage(db: Session, rule: AutomationRule) -> dict:
    hour_key = f"automation_rule_hour:{rule.id}:{_hour_bucket()}"
    day_key = f"automation_rule_day:{rule.id}:{_day_bucket()}"
    hour_used = _get_counter(db, hour_key)
    day_used = _get_counter(db, day_key)
    hour_remaining = max(0, rule.rate_limit_per_hour - hour_used)
    day_remaining = max(0, rule.max_daily_runs - day_used)
    return {
        "hourly_used": hour_used,
        "hourly_limit": rule.rate_limit_per_hour,
        "hourly_remaining": hour_remaining,
        "daily_used": day_used,
        "daily_limit": rule.max_daily_runs,
        "daily_remaining": day_remaining,
        "next_allowed": "now" if hour_remaining > 0 and day_remaining > 0 else "rate limited",
    }


def _rule_has_active_run(db: Session, rule_id: int) -> bool:
    active = db.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(
            AutomationRun.automation_rule_id == rule_id,
            AutomationRun.status.in_(
                [
                    AutomationRunStatus.QUEUED,
                    AutomationRunStatus.RUNNING,
                    AutomationRunStatus.CANCEL_REQUESTED,
                ]
            ),
        )
    )
    return bool(active)


def enqueue_automation_run(
    db: Session,
    rule_id: int,
    *,
    trigger: str = "manual",
    requested_by: str = "api",
) -> AutomationRun:
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise AutomationError(f"Rule {rule_id} not found")
    if not rule.enabled and trigger == "scheduled":
        raise AutomationError("Rule is disabled")

    now = _utcnow()
    run = AutomationRun(
        automation_rule_id=rule.id,
        status=AutomationRunStatus.QUEUED,
        trigger_type=trigger,
        requested_by=requested_by,
        requested_at=now,
        logs_json=[],
        progress_json={"current_step": "queued", "processed": 0, "total": 0},
    )
    db.add(run)
    log_event(run, "info", f"queued trigger={trigger} by={requested_by}")
    db.commit()
    db.refresh(run)
    return run


def cancel_automation_run(db: Session, run_id: int) -> AutomationRun:
    run = db.get(AutomationRun, run_id)
    if not run:
        raise AutomationError(f"Run {run_id} not found")
    if run.status == AutomationRunStatus.QUEUED:
        run.status = AutomationRunStatus.CANCELLED
        run.completed_at = _utcnow()
        log_event(run, "info", "cancelled while queued")
    elif run.status == AutomationRunStatus.RUNNING:
        run.status = AutomationRunStatus.CANCEL_REQUESTED
        log_event(run, "info", "cancel requested")
    elif run.status == AutomationRunStatus.CANCEL_REQUESTED:
        pass
    else:
        raise AutomationError(f"Cannot cancel run in status {run.status}")
    db.commit()
    db.refresh(run)
    return run


def mark_run_failed(
    db: Session,
    run_id: int,
    reason: str = "marked failed by operator",
    *,
    force: bool = False,
) -> AutomationRun:
    run = db.get(AutomationRun, run_id)
    if not run:
        raise AutomationError(f"Run {run_id} not found")
    if run.status not in (
        AutomationRunStatus.RUNNING,
        AutomationRunStatus.CANCEL_REQUESTED,
    ):
        raise AutomationError(f"Run {run_id} is not running (status={run.status})")
    settings = get_settings()
    if not force and run.heartbeat_at:
        age = (_utcnow() - run.heartbeat_at).total_seconds()
        if age < settings.automation_run_stale_seconds and run.status == AutomationRunStatus.RUNNING:
            raise AutomationError("Run heartbeat is fresh; not stale")
    run.status = AutomationRunStatus.FAILED
    run.error_message = reason
    run.completed_at = _utcnow()
    run.locked_by = None
    run.lock_expires_at = None
    log_event(run, "error", reason)
    db.commit()
    db.refresh(run)
    return run


def _incr_rate_counters(db: Session, rule_id: int) -> None:
    from app.models.scheduler_state import SchedulerState

    def incr(key: str) -> None:
        val = _get_counter(db, key) + 1
        row = db.get(SchedulerState, key)
        if row:
            row.value = str(val)
        else:
            db.add(SchedulerState(key=key, value=str(val)))

    incr(f"automation_hour:{_hour_bucket()}")
    incr(f"automation_rule_hour:{rule_id}:{_hour_bucket()}")
    incr(f"automation_rule_day:{rule_id}:{_day_bucket()}")


def _try_lock_run(db: Session, run: AutomationRun) -> bool:
    settings = get_settings()
    now = _utcnow()
    db.refresh(run)
    if run.status != AutomationRunStatus.QUEUED:
        return False
    run.status = AutomationRunStatus.RUNNING
    run.started_at = now
    run.heartbeat_at = now
    run.locked_by = _owner()
    run.lock_expires_at = now + timedelta(seconds=settings.automation_run_lock_seconds)
    log_event(run, "info", "started")
    set_progress(run, current_step="starting", processed=0, total=0)
    db.commit()
    return True


def _finish_run(
    db: Session,
    run: AutomationRun,
    status: str,
    *,
    error: str | None = None,
) -> None:
    run.status = status
    run.completed_at = _utcnow()
    run.locked_by = None
    run.lock_expires_at = None
    if error:
        run.error_message = error
        log_event(run, "error", error)
    else:
        log_event(run, "info", f"finished status={status}")
    db.commit()


def process_automation_run(db: Session, run_id: int) -> AutomationRun:
    if not is_automation_enabled():
        raise AutomationError("Automation disabled")

    run = db.get(AutomationRun, run_id)
    if not run:
        raise AutomationError(f"Run {run_id} not found")

    rule = db.get(AutomationRule, run.automation_rule_id)
    if not rule:
        raise AutomationError("Rule not found")

    if run.status == AutomationRunStatus.QUEUED:
        if not _try_lock_run(db, run):
            return run
    elif run.status not in (AutomationRunStatus.RUNNING, AutomationRunStatus.CANCEL_REQUESTED):
        return run

    db.refresh(run)
    affected: dict[str, Any] = {"trigger": run.trigger_type or "unknown"}
    trigger = run.trigger_type or "manual"

    try:
        cfg = dict(rule.config_json or {})
        if rule.automation_type == "discovery":
            _run_discovery(db, rule, cfg, run, affected)
        elif rule.automation_type == "enqueue":
            _run_enqueue(db, rule, cfg, run, affected)
        elif rule.automation_type == "pipeline_progression":
            _run_pipeline_progression(db, rule, cfg, run, affected)
        elif rule.automation_type == "analytics_refresh":
            log_event(run, "info", "analytics_refresh no-op")
            affected["note"] = "manual import only"
        elif rule.automation_type == "media_generation":
            raise AutomationError("media_generation not enabled")
        else:
            raise AutomationError(f"Unknown automation_type: {rule.automation_type}")

        db.refresh(run)
        if is_cancel_requested(db, run.id):
            run.affected_entities_json = affected
            _finish_run(db, run, AutomationRunStatus.CANCELLED)
        else:
            run.affected_entities_json = affected
            _finish_run(db, run, AutomationRunStatus.COMPLETED)
        _incr_rate_counters(db, rule.id)
    except AutomationError as exc:
        _finish_run(db, run, AutomationRunStatus.FAILED, error=str(exc))
        raise
    except Exception as exc:
        logger.exception("Automation run %s failed", run_id)
        _finish_run(db, run, AutomationRunStatus.FAILED, error=str(exc))
        raise

    db.refresh(run)
    return run


def _run_discovery(db: Session, rule, cfg, run, affected) -> None:
    if not is_source_discovery_enabled():
        raise AutomationError("Source discovery disabled")
    dir_id = cfg.get("source_directory_id")
    if not dir_id:
        raise AutomationError("config.source_directory_id required")
    set_progress(run, current_step="discovery", processed=0, total=1)
    touch_run_heartbeat(db, run)
    db.commit()
    if is_cancel_requested(db, run.id):
        return
    result = run_discovery(db, int(dir_id), max_urls=cfg.get("max_urls"))
    run.created_discoveries = result.discovered_new
    set_progress(run, current_step="discovery", processed=1, total=1, last_entity=f"directory:{dir_id}")
    log_event(run, "info", f"discovery new={result.discovered_new} dup={result.duplicates}")
    affected["discovery"] = {
        "source_directory_id": dir_id,
        "discovered_new": result.discovered_new,
        "duplicates": result.duplicates,
    }
    touch_run_heartbeat(db, run)
    db.commit()


def _run_enqueue(db: Session, rule, cfg, run, affected) -> None:
    batch = int(cfg.get("batch_size", 10))
    q = (
        select(DiscoveredUrl)
        .where(DiscoveredUrl.status == DiscoveredUrlStatus.DISCOVERED.value)
        .order_by(DiscoveredUrl.id.asc())
        .limit(batch)
    )
    if rule.project_id:
        q = q.where(DiscoveredUrl.project_id == rule.project_id)
    urls = list(db.scalars(q).all())
    set_progress(run, current_step="enqueue", processed=0, total=len(urls))
    touch_run_heartbeat(db, run)
    db.commit()
    enqueued = []
    for i, record in enumerate(urls):
        if is_cancel_requested(db, run.id):
            break
        try:
            enqueue_discovered_url(db, record.id)
            enqueued.append(record.id)
            run.created_tasks += 1
            log_event(run, "info", f"enqueued discovered_url {record.id}")
        except Exception as exc:
            log_event(run, "warning", f"enqueue skip {record.id}: {exc}")
        set_progress(
            run,
            current_step="enqueue",
            processed=i + 1,
            total=len(urls),
            last_entity=f"discovered_url:{record.id}",
        )
        touch_run_heartbeat(db, run)
        db.commit()
    affected["enqueued_discovered_url_ids"] = enqueued


def _run_pipeline_progression(db: Session, rule, cfg, run, affected) -> None:
    max_docs = int(cfg.get("max_documents_per_run", cfg.get("max_documents", 5)))
    quality_runs: list[int] = []
    if not is_quality_review_enabled():
        log_event(run, "info", "quality review disabled — skipped")
        affected["skipped"] = "quality disabled"
        return

    q = (
        select(ParsedDocument)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ScrapingTask.status == TaskStatus.DONE.value)
        .order_by(ParsedDocument.id.desc())
        .limit(max_docs * 3)
    )
    if rule.project_id:
        q = q.where(ScrapingTask.project_id == rule.project_id)
    candidates = [d for d in db.scalars(q).all() if not get_latest_quality_score(db, d.id)][:max_docs]
    set_progress(run, current_step="quality_review", processed=0, total=len(candidates))
    touch_run_heartbeat(db, run)
    db.commit()

    for i, doc in enumerate(candidates):
        if is_cancel_requested(db, run.id):
            log_event(run, "info", "cancel requested — stopping after current batch")
            break
        set_progress(
            run,
            current_step="quality_review",
            processed=i,
            total=len(candidates),
            last_entity=f"document:{doc.id}",
        )
        touch_run_heartbeat(db, run)
        db.commit()
        try:
            res = run_quality_for_document(db, doc.id)
            if res.success and not res.skipped:
                quality_runs.append(doc.id)
                run.created_documents += 1
                log_event(run, "info", f"quality document {doc.id} score={res.overall_score}")
        except Exception as exc:
            log_event(run, "error", f"quality document {doc.id}: {exc}")
        set_progress(
            run,
            current_step="quality_review",
            processed=i + 1,
            total=len(candidates),
            last_entity=f"document:{doc.id}",
        )
        touch_run_heartbeat(db, run)
        db.commit()

    affected["quality_document_ids"] = quality_runs


def set_rule_enabled(db: Session, rule_id: int, enabled: bool) -> AutomationRule:
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise AutomationError(f"Rule {rule_id} not found")
    rule.enabled = enabled
    db.commit()
    db.refresh(rule)
    return rule


# Backward compat alias
def execute_automation_rule(db: Session, rule_id: int, *, trigger: str = "manual") -> AutomationRun:
    return enqueue_automation_run(db, rule_id, trigger=trigger, requested_by="legacy")
