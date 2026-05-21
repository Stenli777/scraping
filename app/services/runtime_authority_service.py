"""Runtime authority boundaries and invariant consistency (cohesion phase)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import all_flags, is_auto_publish_enabled, is_automation_enabled
from app.models.content_release_candidate import ContentReleaseCandidate
from app.services.revision_service import get_latest_revision

AUTH_RUNTIME_ENFORCED = "runtime_enforced"
AUTH_GOVERNANCE_ONLY = "governance_only"
AUTH_DECORATIVE = "decorative"
AUTH_DEPRECATED = "deprecated"
AUTH_DANGEROUS = "dangerous_by_design"
AUTH_OPTIONAL = "optional_integration"
AUTH_TARGET = "target"

STALE_RC_SAMPLE = 15


def build_authority_boundaries() -> dict[str, Any]:
    """Catalog — reduces operator confusion about what code actually enforces."""
    domains = [
        {
            "id": "publish_stale_revision",
            "label": "Stale revision on publish/approve",
            "authority": AUTH_RUNTIME_ENFORCED,
            "surface": "publish_service, release_candidate_service",
        },
        {
            "id": "force_reason",
            "label": "force=true requires force_reason",
            "authority": AUTH_RUNTIME_ENFORCED,
            "surface": "publish_service, admin publish",
        },
        {
            "id": "force_gates_bypass",
            "label": "force bypasses review/QC/editorial/duplicate",
            "authority": AUTH_DANGEROUS,
            "surface": "publish validators",
        },
        {
            "id": "auto_publish",
            "label": "ENABLE_AUTO_PUBLISH blocks publish when true",
            "authority": AUTH_RUNTIME_ENFORCED,
            "surface": "publish_service preconditions",
        },
        {
            "id": "rc_qa_approve_publish",
            "label": "RC QA → approve → publish-draft",
            "authority": AUTH_RUNTIME_ENFORCED,
            "surface": "release_candidate_service (preferred path)",
        },
        {
            "id": "legacy_document_publish",
            "label": "POST /documents/{id}/publish-draft",
            "authority": AUTH_DEPRECATED,
            "surface": "admin legacy form, API",
        },
        {
            "id": "projects_trust_level",
            "label": "projects.trust_level column",
            "authority": AUTH_DECORATIVE,
            "surface": "admin visibility; no automation gating",
        },
        {
            "id": "publication_record_public",
            "label": "publication_record implies live site",
            "authority": AUTH_GOVERNANCE_ONLY,
            "surface": "ops/docs; CRMFlow24 manual public",
        },
        {
            "id": "stage5_content_studio",
            "label": "Stage 5 entities / batch gen",
            "authority": AUTH_TARGET,
            "surface": "governance only; no runtime schema",
        },
        {
            "id": "hermes_research",
            "label": "Hermes module",
            "authority": AUTH_OPTIONAL,
            "surface": "ENABLE_HERMES default off",
        },
        {
            "id": "diagnostics",
            "label": "Runtime diagnostics / incidents",
            "authority": AUTH_RUNTIME_ENFORCED,
            "surface": "read-only visibility; no auto-fix",
        },
        {
            "id": "automation_scheduler",
            "label": "Automation + scheduler",
            "authority": AUTH_RUNTIME_ENFORCED,
            "surface": "env gates; must stay off in production",
        },
    ]
    return {
        "read_only": True,
        "not_policy_engine": True,
        "legend": {
            AUTH_RUNTIME_ENFORCED: "Code blocks or guarantees behavior",
            AUTH_GOVERNANCE_ONLY: "Documented; operator discipline",
            AUTH_DECORATIVE: "Visible but does not change runtime gates",
            AUTH_DEPRECATED: "Backward compatible; avoid in production",
            AUTH_DANGEROUS: "Allowed with audit; bypasses safety gates",
            AUTH_OPTIONAL: "Implemented; default off",
            AUTH_TARGET: "Not built in runtime",
        },
        "domains": domains,
        "canonical_doc": "docs/governance/ENFORCEMENT_MATRIX.md",
    }


def _list_approved_stale_rc(db: Session) -> list[dict[str, Any]]:
    from app.services.release_candidate_service import RC_APPROVED

    out: list[dict[str, Any]] = []
    for cand in db.scalars(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.status == RC_APPROVED)
        .order_by(ContentReleaseCandidate.id.desc())
        .limit(STALE_RC_SAMPLE)
    ).all():
        latest = get_latest_revision(db, cand.document_id)
        if latest and cand.document_revision_id != latest.id:
            out.append(
                {
                    "release_candidate_id": cand.id,
                    "document_id": cand.document_id,
                    "bound_revision_id": cand.document_revision_id,
                    "latest_revision_id": latest.id,
                }
            )
    return out


def build_invariant_consistency_checks(db: Session) -> dict[str, Any]:
    """Runtime consistency — visibility + sample invalid states (no auto-fix)."""
    from app.services.runtime_diagnostics_service import _count_approved_stale_release_candidates

    flags = all_flags()
    stale_approved = _list_approved_stale_rc(db)
    stale_count = _count_approved_stale_release_candidates(db)
    issues: list[dict[str, Any]] = []

    if stale_count:
        issues.append(
            {
                "id": "approved_rc_stale_revision",
                "severity": "warning",
                "authority": AUTH_RUNTIME_ENFORCED,
                "message": f"{stale_count} approved RC(s) bind stale revision (approve/publish blocked; row remains in DB).",
                "action": "Create new RC after rerun rewrite; do not delete audit rows.",
            }
        )

    if is_automation_enabled():
        issues.append(
            {
                "id": "automation_enabled",
                "severity": "critical",
                "authority": AUTH_RUNTIME_ENFORCED,
                "message": "ENABLE_AUTOMATION is true — production manual-first invariant at risk.",
                "action": "Disable automation per OPERATIONS.md kill switch.",
            }
        )

    if is_auto_publish_enabled():
        issues.append(
            {
                "id": "auto_publish_enabled",
                "severity": "critical",
                "authority": AUTH_RUNTIME_ENFORCED,
                "message": "ENABLE_AUTO_PUBLISH is true — publish path blocked by design when on.",
                "action": "Set ENABLE_AUTO_PUBLISH=false in .env",
            }
        )

    if flags.get("ENABLE_HERMES") and not flags.get("ENABLE_PUBLISHING"):
        issues.append(
            {
                "id": "hermes_without_publish",
                "severity": "info",
                "authority": AUTH_GOVERNANCE_ONLY,
                "message": "Hermes on but ENABLE_PUBLISHING off — optional research only.",
                "action": None,
            }
        )

    return {
        "read_only": True,
        "no_auto_remediation": True,
        "stage5_runtime_absent": True,
        "automation_off_expected": not is_automation_enabled(),
        "auto_publish_off_expected": not is_auto_publish_enabled(),
        "stale_approved_rc_count": stale_count,
        "stale_approved_rc_sample": stale_approved,
        "trust_level_semantics": AUTH_DECORATIVE,
        "issues": issues,
        "issue_count": len(issues),
    }


def build_runtime_cohesion_notes() -> dict[str, Any]:
    return {
        "incident_memory_vs_episodes": "DB operational_incidents + snapshot-derived episodes — both bounded, different sources.",
        "drift_vs_invariant_checks": "governance_drift = policy/runtime flags; invariant_consistency = invalid DB states sample.",
        "triage_vs_recovery": "incident_triage = current risks; recovery_playbook = operator steps (no auto-retry).",
        "preferred_publish_path": "release_candidate → QA → approve → publish-draft",
        "deprecated_publish_path": "document publish-draft (legacy)",
    }
