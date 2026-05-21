"""Operational confidence and replay-safe reliability (phase I)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.document_revision import DocumentRevision

from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_CRITICAL = "critical"


def _replay_rules() -> list[dict[str, str]]:
    return [
        {
            "id": "revision_advanced",
            "rule": "If document revision changed since failed publish_run → new RC required; do not retry same binding.",
            "enforcement": "runtime_enforced",
        },
        {
            "id": "stale_revision",
            "rule": "Stale revision guard applies on every publish/retry (force does not bypass).",
            "enforcement": "runtime_enforced",
        },
        {
            "id": "duplicate_409",
            "rule": "409 duplicate → intentional force only with force_reason + admin confirm.",
            "enforcement": "runtime_enforced",
        },
        {
            "id": "retry_chain",
            "rule": "Follow retry_parent_publish_run_id chain in UI before manual retry.",
            "enforcement": "governance_only",
        },
    ]


def build_replay_safety_report(db: Session) -> dict[str, Any]:
    from app.services.publish_retry_service import get_retry_chain, is_retryable_publish_run
    from app.services.runtime_integrity_service import build_runtime_integrity_report

    integrity = build_runtime_integrity_report(db)
    items: list[dict[str, Any]] = []

    from app.services.runtime_predictability_service import resolve_replay_verdict

    for sample in integrity.get("retryable_publish_sample", []):
        run_id = sample["id"]
        chain = get_retry_chain(db, run_id)
        chain_ids = [r.id for r in chain]
        v = resolve_replay_verdict(db, run_id)
        items.append(
            {
                **sample,
                "retry_chain_ids": chain_ids,
                "replay_verdict": v.get("verdict_id"),
                "replay_action": v.get("operator_action"),
                "manual_retry_allowed": v.get("manual_retry_allowed"),
            }
        )

    return {
        "read_only": True,
        "rules": _replay_rules(),
        "retryable_count": len(items),
        "retryable_runs": items,
        "deterministic": True,
        "no_auto_retry": True,
    }


def _replay_verdict_for_run(db: Session, run_id: int, stale_approved_count: int) -> str:
    from app.services.runtime_predictability_service import resolve_replay_verdict

    return resolve_replay_verdict(db, run_id).get("verdict_id", "review_chain")


def build_runtime_confidence_checks(db: Session) -> list[dict[str, Any]]:
    """Bounded deterministic checks — extends integrity without heavy engine."""
    from app.services.runtime_integrity_service import build_runtime_integrity_report
    from app.services.runtime_diagnostics_service import build_queue_summary

    integrity = build_runtime_integrity_report(db)
    queue = build_queue_summary(db)
    checks: list[dict[str, Any]] = list(integrity.get("checks", []))

    if queue["backlog_pressure"] == "high":
        checks.append(
            {
                "id": "queue_pressure_high",
                "status": "warn",
                "count": 1,
                "authority": "runtime_enforced",
                "message": "High queue backlog pressure",
                "remediation": "/admin/failed-items",
            }
        )

    if is_automation_enabled() or is_auto_publish_enabled():
        checks.append(
            {
                "id": "safety_flags",
                "status": "fail",
                "count": 1,
                "authority": "runtime_enforced",
                "message": "Automation or auto-publish flag enabled",
                "remediation": ".env kill switch",
            }
        )

    replay = build_replay_safety_report(db)
    blocked = sum(1 for r in replay["retryable_runs"] if r["replay_verdict"].startswith("blocked"))
    if blocked:
        checks.append(
            {
                "id": "replay_blocked_sample",
                "status": "warn",
                "count": blocked,
                "authority": "runtime_enforced",
                "message": "Some retryable publish runs need new RC/revision before replay",
                "remediation": "/admin/publish-runs",
            }
        )

    return checks


def build_operational_confidence(db: Session) -> dict[str, Any]:
    """Unified confidence snapshot — not a fake score; deterministic bands."""
    from app.services.operational_snapshot_service import build_snapshot_comparison
    from app.services.runtime_integrity_service import build_runtime_integrity_report

    integrity = build_runtime_integrity_report(db)
    replay = build_replay_safety_report(db)
    checks = build_runtime_confidence_checks(db)

    fail_n = sum(1 for c in checks if c.get("status") == "fail")
    warn_n = sum(1 for c in checks if c.get("status") in ("warn", "fail"))
    stale_rc = integrity.get("stale_approved_rc_count", 0)

    if fail_n or is_automation_enabled() or is_auto_publish_enabled():
        level = CONFIDENCE_CRITICAL
    elif stale_rc or warn_n >= 2:
        level = CONFIDENCE_LOW
    elif warn_n == 1:
        level = CONFIDENCE_MEDIUM
    else:
        level = CONFIDENCE_HIGH

    signals = []
    if stale_rc:
        signals.append(f"stale_approved_rc={stale_rc}")
    if replay["retryable_count"]:
        signals.append(f"retryable_publish={replay['retryable_count']}")
    if fail_n:
        signals.append(f"critical_checks={fail_n}")

    comparison = build_snapshot_comparison(db)
    trend_note = None
    if comparison.get("available") and comparison.get("pressure_changed"):
        trend_note = f"backlog pressure {comparison.get('previous_pressure')} → {comparison.get('current_pressure')}"

    return {
        "read_only": True,
        "not_slo_dashboard": True,
        "confidence_level": level,
        "confidence_legend": {
            CONFIDENCE_HIGH: "No blocking integrity issues in bounded sample",
            CONFIDENCE_MEDIUM: "Single warning — review diagnostics",
            CONFIDENCE_LOW: "Stale RC or multiple warnings — remediate before publish push",
            CONFIDENCE_CRITICAL: "Safety flags or failing checks — stop and fix env",
        },
        "signals": signals,
        "checks_summary": {"fail": fail_n, "warn": warn_n, "total": len(checks)},
        "integrity_stale_approved": stale_rc,
        "replay_retryable": replay["retryable_count"],
        "trend_note": trend_note,
        "surfaces": {
            "diagnostics": "/admin/diagnostics",
            "integrity": "/admin/integrity",
            "failed_items": "/admin/failed-items",
            "publish_runs": "/admin/publish-runs",
        },
        "cohesion_note": "Single view aggregates integrity_report, recovery_discipline, incidents, snapshots.",
    }
