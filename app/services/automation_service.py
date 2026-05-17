"""Controlled automation execution — bounded, auditable, no auto-publish."""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DiscoveredUrlStatus
from app.core.feature_flags import is_automation_enabled, is_quality_review_enabled, is_source_discovery_enabled
from app.models.automation_run import AutomationRun
from app.models.automation_rule import AutomationRule
from app.models.content_quality_score import ContentQualityScore
from app.models.discovered_url import DiscoveredUrl
from app.models.parsed_document import ParsedDocument
from app.models.scraping_task import ScrapingTask
from app.core.enums import TaskStatus
from app.services.discovery_service import enqueue_discovered_url, run_discovery
from app.services.quality_service import get_latest_quality_score, run_quality_for_document

logger = logging.getLogger(__name__)


class AutomationError(Exception):
    pass


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
            config_json={"max_documents": 5, "interval_minutes": 30},
            rate_limit_per_hour=10,
            max_daily_runs=48,
        ),
    ]
    for r in rules:
        db.add(r)
    db.commit()
    logger.info("Seeded default automation rules (disabled)")


def execute_automation_rule(
    db: Session,
    rule_id: int,
    *,
    trigger: str = "manual",
) -> AutomationRun:
    if not is_automation_enabled():
        raise AutomationError("Automation disabled (ENABLE_AUTOMATION=false)")

    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise AutomationError(f"Rule {rule_id} not found")
    if not rule.enabled and trigger == "scheduled":
        raise AutomationError("Rule is disabled")

    run = AutomationRun(
        automation_rule_id=rule.id,
        status="running",
        started_at=datetime.now(timezone.utc),
        logs_json=[],
    )
    db.add(run)
    db.flush()

    logs: list[str] = []
    affected: dict[str, Any] = {"trigger": trigger}

    try:
        cfg = dict(rule.config_json or {})
        if rule.automation_type == "discovery":
            result = _run_discovery(db, rule, cfg, run, logs, affected)
        elif rule.automation_type == "enqueue":
            result = _run_enqueue(db, rule, cfg, run, logs, affected)
        elif rule.automation_type == "pipeline_progression":
            result = _run_pipeline_progression(db, rule, cfg, run, logs, affected)
        elif rule.automation_type == "analytics_refresh":
            result = _run_analytics_refresh(db, rule, cfg, run, logs, affected)
        elif rule.automation_type == "media_generation":
            raise AutomationError("media_generation automation not enabled in 4A")
        else:
            raise AutomationError(f"Unknown automation_type: {rule.automation_type}")

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.affected_entities_json = affected
        run.logs_json = logs
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        logger.exception("Automation run failed rule=%s", rule_id)
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        run.logs_json = logs + [f"error: {exc}"]
        run.affected_entities_json = affected
        db.commit()
        raise


def _run_discovery(db: Session, rule, cfg, run, logs, affected) -> dict:
    if not is_source_discovery_enabled():
        raise AutomationError("Source discovery disabled")
    dir_id = cfg.get("source_directory_id")
    if not dir_id:
        raise AutomationError("config.source_directory_id required")
    result = run_discovery(db, int(dir_id), max_urls=cfg.get("max_urls"))
    run.created_discoveries = result.discovered_new
    logs.append(f"discovery: new={result.discovered_new} dup={result.duplicates}")
    affected["discovery"] = {
        "source_directory_id": dir_id,
        "discovered_new": result.discovered_new,
        "duplicates": result.duplicates,
        "blocked": result.blocked,
    }
    return affected


def _run_enqueue(db: Session, rule, cfg, run, logs, affected) -> dict:
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
    enqueued = []
    for record in urls:
        try:
            enqueue_discovered_url(db, record.id)
            enqueued.append(record.id)
            run.created_tasks += 1
        except Exception as exc:
            logs.append(f"enqueue skip {record.id}: {exc}")
    logs.append(f"enqueued {len(enqueued)} urls")
    affected["enqueued_discovered_url_ids"] = enqueued
    return affected


def _run_pipeline_progression(db: Session, rule, cfg, run, logs, affected) -> dict:
    """Safe stages only: quality review for DONE tasks. No publish/editorial."""
    max_docs = int(cfg.get("max_documents", 5))
    quality_runs = []
    if is_quality_review_enabled():
        q = (
            select(ParsedDocument)
            .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
            .where(ScrapingTask.status == TaskStatus.DONE.value)
            .order_by(ParsedDocument.id.desc())
            .limit(max_docs * 3)
        )
        if rule.project_id:
            q = q.where(ScrapingTask.project_id == rule.project_id)
        for doc in db.scalars(q).all():
            if len(quality_runs) >= max_docs:
                break
            if get_latest_quality_score(db, doc.id):
                continue
            try:
                res = run_quality_for_document(db, doc.id)
                if res.success and not res.skipped:
                    quality_runs.append(doc.id)
                    run.created_documents += 1
                    logs.append(f"quality doc={doc.id} score={res.overall_score}")
            except Exception as exc:
                logs.append(f"quality failed doc={doc.id}: {exc}")
    affected["quality_document_ids"] = quality_runs
    logs.append(f"pipeline_progression: quality on {len(quality_runs)} docs")
    return affected


def _run_analytics_refresh(db: Session, rule, cfg, run, logs, affected) -> dict:
    logs.append("analytics_refresh: no-op in 4A (manual import only)")
    affected["note"] = "use manual analytics import API"
    return affected


def set_rule_enabled(db: Session, rule_id: int, enabled: bool) -> AutomationRule:
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise AutomationError(f"Rule {rule_id} not found")
    rule.enabled = enabled
    db.commit()
    db.refresh(rule)
    return rule
