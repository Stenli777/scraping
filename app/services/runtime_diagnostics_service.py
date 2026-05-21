"""Runtime diagnostics ??? bounded, read-only, incident triage (Phase B/C)."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.feature_flags import (
    all_flags,
    is_auto_publish_enabled,
    is_automation_enabled,
    is_scheduler_enabled,
)
from app.models.automation_rule import AutomationRule
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.document_revision import DocumentRevision
from app.models.llm_enrichment_job import EnrichmentJobStatus
from app.models.llm_run import LLMRun
from app.models.project import Project
from app.models.publish_run import PublishRun
from app.models.scraping_task import ScrapingTask
from app.scheduler.status import build_scheduler_status
from app.services.enrichment_metrics_service import get_enrichment_metrics
from app.services.operations_service import RUNNING_STATUSES, list_stale_running_tasks
from app.services.revision_service import get_latest_revision

# Query guardrails ??? diagnostics must not become an incident source.
PUBLISH_DIAGNOSTICS_LIMIT = 25
STALE_RC_SCAN_LIMIT = 200
LLM_FAILURES_LIMIT = 20
LLM_FAILURE_WINDOW_HOURS = 24
FORCE_PUBLISH_SAMPLE_LIMIT = 10
INCIDENT_PUBLISH_FAILURES_LIMIT = 10

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

_SECRET_KEY_PATTERN = re.compile(
    r"(token|secret|password|dsn|api_key|authorization|bearer|credential)",
    re.I,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _age_seconds(dt: datetime | None) -> int | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int((_utcnow() - dt).total_seconds())


def _worker_service_state(unit: str) -> str:
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return (proc.stdout or proc.stderr or "unknown").strip() or "unknown"
    except Exception as exc:
        return f"error:{type(exc).__name__}"


def _warn(
    warnings: list[dict[str, str]],
    *,
    id: str,
    severity: str,
    message: str,
    enforcement: str = "governance-only",
) -> None:
    warnings.append(
        {
            "id": id,
            "severity": severity,
            "message": message,
            "enforcement": enforcement,
        }
    )


def build_queue_summary(db: Session) -> dict[str, Any]:
    """Aggregated counts only ??? no full-table scans."""
    task_rows = db.execute(
        select(ScrapingTask.status, func.count()).group_by(ScrapingTask.status)
    ).all()
    task_counts = {row[0]: row[1] for row in task_rows}

    oldest_queued = db.scalar(
        select(func.min(ScrapingTask.created_at)).where(ScrapingTask.status == "queued")
    )
    oldest_running = db.scalar(
        select(func.min(ScrapingTask.updated_at)).where(
            ScrapingTask.status.in_(tuple(RUNNING_STATUSES))
        )
    )
    stale_tasks = list_stale_running_tasks(db)

    enrichment = get_enrichment_metrics(db, window_hours=24)
    by_status = enrichment.get("by_status") or {}
    scheduler = build_scheduler_status(db)

    queued_tasks = task_counts.get("queued", 0)
    running_tasks = sum(task_counts.get(s, 0) for s in RUNNING_STATUSES)

    pressure = "low"
    if queued_tasks >= 20 or running_tasks >= 10 or len(stale_tasks) >= 3:
        pressure = "high"
    elif queued_tasks >= 5 or running_tasks >= 3 or len(stale_tasks) >= 1:
        pressure = "medium"

    return {
        "sample_note": "Aggregated status counts; stale list capped at 10 IDs.",
        "scraping_tasks": {
            "counts": task_counts,
            "queued": queued_tasks,
            "running": running_tasks,
            "failed_retryable": task_counts.get("failed_retryable", 0),
            "failed_terminal": task_counts.get("error", 0),
            "oldest_queued_age_seconds": _age_seconds(oldest_queued),
            "oldest_running_age_seconds": _age_seconds(oldest_running),
            "stale_running_count": len(stale_tasks),
            "stale_running_ids": [t.id for t in stale_tasks[:10]],
        },
        "enrichment_jobs": {
            "by_status": by_status,
            "queued": by_status.get(EnrichmentJobStatus.QUEUED, 0),
            "running": by_status.get(EnrichmentJobStatus.RUNNING, 0),
            "failed_retryable": by_status.get(EnrichmentJobStatus.FAILED_RETRYABLE, 0),
            "failed_terminal": by_status.get(EnrichmentJobStatus.FAILED_TERMINAL, 0),
        },
        "automation_runs": {
            "queued": scheduler.get("queued_runs", 0),
            "running": scheduler.get("running_runs", 0),
            "stale_running": (scheduler.get("stale_running") or [])[:10],
        },
        "backlog_pressure": pressure,
    }


def build_publish_diagnostics(
    db: Session, *, limit: int = PUBLISH_DIAGNOSTICS_LIMIT
) -> dict[str, Any]:
    runs = list(
        db.scalars(select(PublishRun).order_by(PublishRun.id.desc()).limit(limit)).all()
    )
    items = []
    for r in runs:
        path = "release_candidate" if r.release_candidate_id else "direct_document"
        rev_no = None
        stale_bind = False
        if r.document_revision_id:
            rev = db.get(DocumentRevision, r.document_revision_id)
            if rev:
                rev_no = rev.revision_number
                latest = get_latest_revision(db, r.document_id)
                if latest and latest.id != rev.id:
                    stale_bind = True
        items.append(
            {
                "id": r.id,
                "document_id": r.document_id,
                "status": r.status,
                "publish_target_id": r.publish_target_id,
                "path": path,
                "release_candidate_id": r.release_candidate_id,
                "document_revision_id": r.document_revision_id,
                "revision_number": rev_no,
                "revision_stale_binding": stale_bind,
                "force_used": r.force_used,
                "force_reason": r.force_reason,
                "dry_run": r.dry_run,
                "error_message": (r.error_message or "")[:200] or None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "label": "CRMFlow24 draft publish",
            }
        )
    failed_recent = [
        x for x in items if x["status"] in ("failed_retryable", "failed_terminal")
    ]
    force_without_reason = db.scalar(
        select(func.count())
        .select_from(PublishRun)
        .where(PublishRun.force_used.is_(True), PublishRun.force_reason.is_(None))
    ) or 0
    force_sample = list(
        db.scalars(
            select(PublishRun)
            .where(PublishRun.force_used.is_(True))
            .order_by(PublishRun.id.desc())
            .limit(FORCE_PUBLISH_SAMPLE_LIMIT)
        ).all()
    )
    return {
        "sample_limit": limit,
        "sample_note": f"Last {limit} publish_runs by id desc; not full history.",
        "recent_runs": items,
        "failed_recent": failed_recent[:INCIDENT_PUBLISH_FAILURES_LIMIT],
        "failed_recent_count": len(failed_recent),
        "force_without_reason_total": force_without_reason,
        "force_publish_sample": [
            {
                "id": r.id,
                "document_id": r.document_id,
                "force_reason": r.force_reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in force_sample
        ],
        "note": "Draft-only; not public live publish.",
    }


def _count_stale_release_candidates(db: Session) -> int:
    from app.services.release_candidate_service import OPEN_STATUSES, RC_PUBLISHED_DRAFT

    watch_statuses = tuple(OPEN_STATUSES | {RC_PUBLISHED_DRAFT})
    stale = 0
    for cand in db.scalars(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.status.in_(watch_statuses))
        .order_by(ContentReleaseCandidate.id.desc())
        .limit(STALE_RC_SCAN_LIMIT)
    ).all():
        latest = get_latest_revision(db, cand.document_id)
        if latest and cand.document_revision_id != latest.id:
            stale += 1
    return stale


def _count_approved_stale_release_candidates(db: Session) -> int:
    from app.services.release_candidate_service import RC_APPROVED

    stale = 0
    for cand in db.scalars(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.status == RC_APPROVED)
        .order_by(ContentReleaseCandidate.id.desc())
        .limit(STALE_RC_SCAN_LIMIT)
    ).all():
        latest = get_latest_revision(db, cand.document_id)
        if latest and cand.document_revision_id != latest.id:
            stale += 1
    return stale


def build_governance_drift_warnings(db: Session) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    flags = all_flags()

    if is_auto_publish_enabled():
        _warn(
            warnings,
            id="auto_publish_enabled",
            severity=SEVERITY_CRITICAL,
            message="ENABLE_AUTO_PUBLISH is true ??? publish safety invariant at risk.",
            enforcement="fully enforced when off",
        )
    else:
        _warn(
            warnings,
            id="auto_publish_off",
            severity=SEVERITY_INFO,
            message="ENABLE_AUTO_PUBLISH is off (expected). Auto-publish blocked at runtime.",
            enforcement="fully enforced",
        )

    if is_automation_enabled():
        _warn(
            warnings,
            id="automation_enabled",
            severity=SEVERITY_CRITICAL,
            message="ENABLE_AUTOMATION+SCHEDULER active ??? bounded automation may execute.",
            enforcement="env gate",
        )

    rules_total = db.scalar(select(func.count()).select_from(AutomationRule)) or 0
    rules_enabled = (
        db.scalar(
            select(func.count())
            .select_from(AutomationRule)
            .where(AutomationRule.enabled.is_(True))
        )
        or 0
    )
    if rules_total and not flags.get("ENABLE_AUTOMATION"):
        _warn(
            warnings,
            id="automation_disabled_rules_exist",
            severity=SEVERITY_INFO,
            message=f"Automation globally disabled; {rules_total} rule(s) in DB ({rules_enabled} enabled flag).",
        )
    if rules_enabled and not is_automation_enabled():
        _warn(
            warnings,
            id="rules_enabled_global_off",
            severity=SEVERITY_WARNING,
            message=f"{rules_enabled} automation rule(s) enabled while global automation is off.",
        )

    _warn(
        warnings,
        id="trust_visibility_only",
        severity=SEVERITY_INFO,
        message="projects.trust_level is visibility-only; trust engine is Target (ADR-002).",
    )
    _warn(
        warnings,
        id="direct_publish_legacy",
        severity=SEVERITY_INFO,
        message="Direct document publish remains (deprecated); RC-first is canonical.",
    )

    force_legacy = (
        db.scalar(
            select(func.count())
            .select_from(PublishRun)
            .where(PublishRun.force_used.is_(True), PublishRun.force_reason.is_(None))
        )
        or 0
    )
    if force_legacy:
        _warn(
            warnings,
            id="force_without_reason_legacy",
            severity=SEVERITY_WARNING,
            message=f"{force_legacy} historical publish_run(s) with force_used but no force_reason (pre-Phase-A).",
        )

    stale_rc = _count_stale_release_candidates(db)
    if stale_rc:
        _warn(
            warnings,
            id="stale_release_candidates",
            severity=SEVERITY_WARNING,
            message=f"{stale_rc} RC(s) in sample (max {STALE_RC_SCAN_LIMIT}) bound to non-latest revision.",
        )

    sched_proc = _worker_service_state("scrap-scheduler")
    if sched_proc == "active" and not is_scheduler_enabled():
        _warn(
            warnings,
            id="scheduler_process_running_flag_off",
            severity=SEVERITY_WARNING,
            message="scrap-scheduler unit active but ENABLE_SCHEDULER is false (no-op ticks expected).",
        )

    _warn(
        warnings,
        id="stage5_not_runtime",
        severity=SEVERITY_INFO,
        message="Stage 5 Content Studio is governance-only; no autonomous generation runtime.",
    )

    approved_stale = _count_approved_stale_release_candidates(db)
    if approved_stale:
        _warn(
            warnings,
            id="approved_stale_rc",
            severity=SEVERITY_WARNING,
            message=f"{approved_stale} approved RC(s) in sample bind stale revision (approve blocked on UI; publish blocked).",
        )

    return warnings


def build_llm_diagnostics(db: Session) -> dict[str, Any]:
    since = _utcnow() - timedelta(hours=LLM_FAILURE_WINDOW_HOURS)
    failed_recent = list(
        db.scalars(
            select(LLMRun)
            .where(LLMRun.success.is_(False))
            .order_by(LLMRun.id.desc())
            .limit(LLM_FAILURES_LIMIT)
        ).all()
    )
    failed_24h = (
        db.scalar(
            select(func.count())
            .select_from(LLMRun)
            .where(LLMRun.success.is_(False), LLMRun.created_at >= since)
        )
        or 0
    )
    by_alias: dict[str, int] = {}
    rate_limit_hints = 0
    items = []
    for run in failed_recent:
        alias = run.model_alias or "unknown"
        by_alias[alias] = by_alias.get(alias, 0) + 1
        err = (run.error_message or "").lower()
        if "429" in err or "rate" in err or "limit" in err:
            rate_limit_hints += 1
        items.append(
            {
                "id": run.id,
                "task_id": run.task_id,
                "model_alias": run.model_alias,
                "upstream_model": run.upstream_model,
                "success": run.success,
                "error_message": (run.error_message or "")[:200] or None,
                "latency_ms": run.latency_ms,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
        )
    last_fail_at = items[0]["created_at"] if items else None
    return {
        "sample_limit": LLM_FAILURES_LIMIT,
        "window_hours": LLM_FAILURE_WINDOW_HOURS,
        "failed_count_24h": failed_24h,
        "failed_by_model_alias": by_alias,
        "rate_limit_hint_count": rate_limit_hints,
        "last_failure_at": last_fail_at,
        "recent_failures": items,
        "cliproxy_note": "LLM via CLIProxyAPI only; routing unchanged.",
    }


def _build_incident_triage_from(
    queue: dict[str, Any],
    publish: dict[str, Any],
    drift: list[dict[str, str]],
    llm: dict[str, Any],
) -> dict[str, Any]:
    risks = []
    for w in drift:
        if w["severity"] == SEVERITY_CRITICAL:
            risks.append(w)
    for w in drift:
        if w["severity"] == SEVERITY_WARNING:
            risks.append(w)

    if queue["backlog_pressure"] in ("medium", "high"):
        risks.append(
            {
                "id": "queue_backlog_pressure",
                "severity": SEVERITY_WARNING if queue["backlog_pressure"] == "medium" else SEVERITY_CRITICAL,
                "message": f"Queue backlog pressure: {queue['backlog_pressure']}",
                "enforcement": "visibility",
            }
        )

    return {
        "top_current_risks": risks[:12],
        "queue_pressure": queue["backlog_pressure"],
        "failed_retryable_tasks": queue["scraping_tasks"]["failed_retryable"],
        "stale_running_count": queue["scraping_tasks"]["stale_running_count"],
        "stale_running_ids": queue["scraping_tasks"]["stale_running_ids"],
        "recent_publish_failures": publish.get("failed_recent", []),
        "recent_llm_failures": llm.get("recent_failures", [])[:5],
        "force_publish_sample": publish.get("force_publish_sample", []),
        "read_only": True,
        "no_auto_fix": True,
    }


def build_trust_visibility(db: Session) -> dict[str, Any]:
    projects = list(db.scalars(select(Project).order_by(Project.id.asc())).all())
    items = []
    for p in projects:
        level = getattr(p, "trust_level", 0) or 0
        items.append(
            {
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "trust_level": level,
                "trust_badge": "low" if level <= 1 else "elevated",
                "enabled": p.enabled,
            }
        )
    return {
        "visibility_only": True,
        "projects": items,
        "levels_help": {
            "0": "Most conservative ??? manual-first (default)",
            "1": "Limited automation by policy (not enabled)",
            "2": "Auto-draft Target",
            "3": "Not production-ready",
        },
        "domain_trust_note": "Domain trust (source_quality) ??? project trust_level.",
        "automation_note": "trust_level does not enable automation.",
    }


def sanitize_diagnostics_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop keys that look like secrets; flags stay boolean-only."""

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: _walk(v)
                for k, v in obj.items()
                if not _SECRET_KEY_PATTERN.search(k)
            }
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        return obj

    return _walk(payload)


def diagnostics_meta() -> dict[str, Any]:
    return {
        "read_only": True,
        "diagnostics_only": True,
        "no_auto_fix": True,
        "no_automation_execution": True,
        "access_note": "API bound to localhost; admin UI is operator context. No secrets in payload.",
        "sample_limits": {
            "publish_runs": PUBLISH_DIAGNOSTICS_LIMIT,
            "stale_rc_scan": STALE_RC_SCAN_LIMIT,
            "llm_failures": LLM_FAILURES_LIMIT,
            "force_publish_sample": FORCE_PUBLISH_SAMPLE_LIMIT,
        },
    }




def build_recovery_playbook(db: Session) -> dict[str, Any]:
    """Operator recovery hints — visibility only, no orchestration."""
    from app.services.operational_snapshot_service import build_snapshot_comparison
    from app.services.runtime_diagnostics_service import _count_approved_stale_release_candidates

    publish = build_publish_diagnostics(db, limit=5)
    queue = build_queue_summary(db)
    stale_rc = _count_approved_stale_release_candidates(db)
    failed_pub = publish.get("failed_recent", [])

    scenarios = []
    if queue["scraping_tasks"]["stale_running_count"]:
        scenarios.append(
            {
                "id": "stale_running_tasks",
                "title": "Зависшие scraping tasks",
                "steps": [
                    "Откройте /admin/failed-items",
                    "Проверьте блок «Зависшие задачи»",
                    "Используйте «Сбросить зависшее» → failed_retryable",
                    "Перезапустите worker только если очередь не двигается",
                ],
                "link": "/admin/failed-items",
            }
        )
    if stale_rc:
        scenarios.append(
            {
                "id": "stale_rc_approved",
                "title": "Approved RC на устаревшей ревизии",
                "steps": [
                    "Не публикуйте и не одобряйте старый RC",
                    "Rerun rewrite на документе → новая ревизия",
                    "Создайте новый RC → QA → approve → publish",
                    "Старый RC оставьте в notes (не удаляйте audit)",
                ],
                "link": "/admin/integrity",
                "actions": ["supersede-stale per RC", "create new RC after rerun"],
            }
        )
    if failed_pub:
        scenarios.append(
            {
                "id": "publish_failed",
                "title": "Сбой publish draft",
                "steps": [
                    "Откройте /admin/publish-runs — проверьте error_message",
                    "Если retryable — повтор с карточки документа/RC (не force без причины)",
                    "При stale revision — новый RC, не force",
                    "При duplicate 409 — force только с force_reason + подтверждением",
                ],
                "link": "/admin/publish-runs",
                "replay_safe": "Verify revision unchanged or new RC before retry",
            }
        )
    if queue["backlog_pressure"] in ("medium", "high"):
        scenarios.append(
            {
                "id": "queue_pressure",
                "title": "Давление на очередь",
                "steps": [
                    "Проверьте scrap-worker и scheduler (должны быть off для automation)",
                    "Снизьте enqueue / discovery лимиты",
                    "Разберите failed_retryable на /admin/failed-items",
                ],
                "link": "/admin/diagnostics",
            }
        )

    return {
        "read_only": True,
        "no_auto_retry": True,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "snapshot_comparison": build_snapshot_comparison(db),
    }


def build_incident_triage(db: Session) -> dict[str, Any]:
    return _build_incident_triage_from(
        build_queue_summary(db),
        build_publish_diagnostics(db),
        build_governance_drift_warnings(db),
        build_llm_diagnostics(db),
    )


def build_runtime_diagnostics(db: Session) -> dict[str, Any]:
    flags = all_flags()
    queue = build_queue_summary(db)
    publish = build_publish_diagnostics(db)
    drift = build_governance_drift_warnings(db)
    llm = build_llm_diagnostics(db)
    payload = {
        "generated_at": _utcnow().isoformat(),
        "meta": diagnostics_meta(),
        "feature_flags": flags,
        "services": {
            "scrap_api": _worker_service_state("scrap-api"),
            "scrap_worker": _worker_service_state("scrap-worker"),
            "scrap_scheduler": _worker_service_state("scrap-scheduler"),
        },
        "scheduler": build_scheduler_status(db),
        "queue": queue,
        "publish": publish,
        "llm": llm,
        "incident_triage": _build_incident_triage_from(queue, publish, drift, llm),
        "governance_drift": drift,
        "trust": build_trust_visibility(db),
        "hermes_optional": not flags.get("ENABLE_HERMES"),
        "stage5_runtime": False,
    }
    from app.services.runtime_authority_service import (
        build_authority_boundaries,
        build_invariant_consistency_checks,
        build_runtime_cohesion_notes,
    )

    payload["authority_boundaries"] = build_authority_boundaries()
    payload["invariant_consistency"] = build_invariant_consistency_checks(db)
    payload["runtime_cohesion"] = build_runtime_cohesion_notes()
    from app.services.runtime_integrity_service import (
        build_recovery_discipline_report,
        build_runtime_integrity_report,
    )

    payload["integrity_report"] = build_runtime_integrity_report(db)
    payload["recovery_discipline"] = build_recovery_discipline_report(db)
    try:
        from app.services.operational_snapshot_service import (
            build_operational_history,
            maybe_capture_snapshot,
        )
        from app.services.operational_incident_service import (
            build_incident_history,
            sync_incidents_from_runtime,
        )
        from app.services.runtime_hygiene_service import build_runtime_hygiene_report

        maybe_capture_snapshot(db, source="diagnostics")
        sync_incidents_from_runtime(db)
        payload["operational_history"] = build_operational_history(db)
        payload["incident_history"] = build_incident_history(db)
        payload["recovery_playbook"] = build_recovery_playbook(db)
        payload["runtime_hygiene"] = build_runtime_hygiene_report(db)
        payload["meta"]["history"] = {
            "snapshots": "bounded operational_snapshots table",
            "incidents": "bounded operational_incidents table",
            "not_realtime": True,
            "capture_interval_seconds": 900,
        }
    except Exception:
        payload["operational_history"] = {"error": "history_unavailable"}
        payload["incident_history"] = {"error": "incidents_unavailable"}
        payload["recovery_playbook"] = {"error": "recovery_unavailable"}
        payload["runtime_hygiene"] = {"error": "hygiene_unavailable"}
    return sanitize_diagnostics_payload(payload)
