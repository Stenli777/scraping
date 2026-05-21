"""Operational predictability and replay determinism (phase J)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.document_revision import DocumentRevision
from app.models.publish_run import PublishRun
from app.services.publish_retry_service import get_retry_chain, is_retryable_publish_run
from app.services.release_candidate_service import RC_APPROVED, _revision_stale_for_candidate
from app.services.revision_service import get_latest_revision

REPLAY_SAMPLE_LIMIT = 25

# Canonical verdict catalog — deterministic operator semantics
VERDICT_CATALOG: dict[str, dict[str, Any]] = {
    "retry_allowed_same_revision": {
        "label": "Retry allowed (same revision)",
        "operator_action": "Manual retry via publish API/admin if error is transient; same revision binding.",
        "expected_outcome": "New publish_run child linked via retry_parent; stale guard re-evaluated.",
        "manual_retry_allowed": True,
        "path": "publish_retry",
    },
    "blocked_new_revision_required": {
        "label": "Blocked — new revision",
        "operator_action": "Do not retry this run. Rerun rewrite → create new RC → publish from RC.",
        "expected_outcome": "Publish service rejects stale binding until new RC.",
        "manual_retry_allowed": False,
        "path": "new_rc",
    },
    "blocked_stale_rc_on_document": {
        "label": "Blocked — stale approved RC",
        "operator_action": "Supersede stale approved RC on /admin/integrity or create new RC after rerun.",
        "expected_outcome": "Approve/publish blocked until RC archived or renewed.",
        "manual_retry_allowed": False,
        "path": "integrity_supersede",
    },
    "blocked_not_retryable": {
        "label": "Blocked — terminal status",
        "operator_action": "Inspect error; fix payload/target. New publish_run from RC if content changed.",
        "expected_outcome": "retry_publish_run API returns not retryable.",
        "manual_retry_allowed": False,
        "path": "new_publish_from_rc",
    },
    "review_chain": {
        "label": "Review retry chain",
        "operator_action": "Open full chain in /admin/publish-runs; identify root failure before action.",
        "expected_outcome": "Operator understands parent→child publish_run lineage.",
        "manual_retry_allowed": False,
        "path": "inspect_chain",
    },
}


def _document_has_stale_approved_rc(db: Session, document_id: int) -> bool:
    for cand in db.scalars(
        select(ContentReleaseCandidate)
        .where(
            ContentReleaseCandidate.document_id == document_id,
            ContentReleaseCandidate.status == RC_APPROVED,
        )
        .limit(20)
    ).all():
        stale, _ = _revision_stale_for_candidate(db, cand)
        if stale:
            return True
    return False


def resolve_replay_verdict(db: Session, publish_run_id: int) -> dict[str, Any]:
    """Deterministic replay decision for one publish_run (read-only)."""
    run = db.get(PublishRun, publish_run_id)
    if not run:
        return {**VERDICT_CATALOG["review_chain"], "verdict_id": "review_chain", "deterministic": True}

    if not is_retryable_publish_run(run):
        out = dict(VERDICT_CATALOG["blocked_not_retryable"])
        out["verdict_id"] = "blocked_not_retryable"
        out["deterministic"] = True
        out["publish_run_id"] = publish_run_id
        return out

    if _document_has_stale_approved_rc(db, run.document_id):
        out = dict(VERDICT_CATALOG["blocked_stale_rc_on_document"])
        out["verdict_id"] = "blocked_stale_rc_on_document"
        out["deterministic"] = True
        out["publish_run_id"] = publish_run_id
        return out

    if not run.document_revision_id:
        out = dict(VERDICT_CATALOG["review_chain"])
        out["verdict_id"] = "review_chain"
        out["deterministic"] = True
        out["publish_run_id"] = publish_run_id
        return out

    rev = db.get(DocumentRevision, run.document_revision_id)
    latest = get_latest_revision(db, run.document_id)
    if rev and latest and rev.id != latest.id:
        out = dict(VERDICT_CATALOG["blocked_new_revision_required"])
        out["verdict_id"] = "blocked_new_revision_required"
        out["deterministic"] = True
        out["publish_run_id"] = publish_run_id
        out["bound_revision"] = rev.revision_number
        out["latest_revision"] = latest.revision_number
        return out

    out = dict(VERDICT_CATALOG["retry_allowed_same_revision"])
    out["verdict_id"] = "retry_allowed_same_revision"
    out["deterministic"] = True
    out["publish_run_id"] = publish_run_id
    return out


def normalize_retry_chain(db: Session, publish_run_id: int) -> dict[str, Any]:
    """Ordered retry chain with explicit roles for operator UI."""
    chain = get_retry_chain(db, publish_run_id)
    if not chain:
        return {"root_id": None, "nodes": [], "depth": 0}

    root_id = chain[0].id
    nodes = []
    for i, r in enumerate(chain):
        nodes.append(
            {
                "id": r.id,
                "status": r.status,
                "document_id": r.document_id,
                "revision_number": None,
                "position": i,
                "role": "root" if i == 0 else ("leaf" if i == len(chain) - 1 else "middle"),
                "parent_id": r.retry_parent_publish_run_id,
                "retry_count": r.retry_count or 0,
                "force_used": bool(r.force_used),
            }
        )
    return {
        "root_id": root_id,
        "leaf_id": chain[-1].id,
        "depth": len(chain),
        "nodes": nodes,
        "normalization": "sorted by publish_run.id ascending",
    }


def build_consistency_guarantees(db: Session) -> dict[str, Any]:
    """Runtime-enforced guarantees vs governance-only — explicit for operators."""
    return {
        "read_only": True,
        "runtime_enforced": [
            {
                "id": "stale_revision_publish",
                "guarantee": "Publish and RC approve/publish reject non-latest revision binding.",
                "surfaces": "publish_service, release_candidate_service",
            },
            {
                "id": "force_reason",
                "guarantee": "force=true requires non-empty force_reason (audit).",
                "surfaces": "publish_service, admin publish",
            },
            {
                "id": "force_not_stale",
                "guarantee": "force does not bypass stale revision guard.",
                "surfaces": "validate_revision_current_for_publish",
            },
            {
                "id": "auto_publish_block",
                "guarantee": "ENABLE_AUTO_PUBLISH=true blocks publish path.",
                "surfaces": "publish_service",
                "current": not is_auto_publish_enabled(),
            },
            {
                "id": "retry_lineage",
                "guarantee": "Retry creates new publish_run with retry_parent link; parent row immutable.",
                "surfaces": "publish_retry_service",
            },
            {
                "id": "revision_archive_rc",
                "guarantee": "New document_revision archives stale open RC for that document.",
                "surfaces": "revision_service, create_release_candidate",
            },
        ],
        "governance_only": [
            {"id": "rc_first", "guarantee": "Production should use RC → QA → approve → publish."},
            {"id": "trust_level", "guarantee": "projects.trust_level does not gate automation (decorative)."},
            {"id": "publication_public", "guarantee": "publication_record does not mean live on site."},
        ],
        "dangerous_by_design": [
            {"id": "force_bypass", "guarantee": "force bypasses review/QC/editorial/duplicate when reason set."},
        ],
        "automation_off": not is_automation_enabled(),
        "auto_publish_off": not is_auto_publish_enabled(),
    }


def build_replay_determinism_report(db: Session) -> dict[str, Any]:
    """Normalized replay view for retryable runs in sample."""
    from app.models.publish_run import PublishRun
    from app.core.enums import PublishRunStatus

    retryable = list(
        db.scalars(
            select(PublishRun)
            .where(PublishRun.status == PublishRunStatus.FAILED_RETRYABLE.value)
            .order_by(PublishRun.id.desc())
            .limit(REPLAY_SAMPLE_LIMIT)
        ).all()
    )

    items = []
    for run in retryable:
        verdict = resolve_replay_verdict(db, run.id)
        chain = normalize_retry_chain(db, run.id)
        items.append(
            {
                "publish_run_id": run.id,
                "document_id": run.document_id,
                "release_candidate_id": run.release_candidate_id,
                "verdict": verdict,
                "chain": chain,
            }
        )

    allowed = sum(1 for i in items if i["verdict"].get("manual_retry_allowed"))
    blocked = len(items) - allowed

    return {
        "read_only": True,
        "no_auto_retry": True,
        "sample_limit": REPLAY_SAMPLE_LIMIT,
        "retryable_sample_count": len(items),
        "manual_retry_allowed_count": allowed,
        "blocked_count": blocked,
        "verdict_catalog": {k: v["label"] for k, v in VERDICT_CATALOG.items()},
        "items": items,
    }


def build_recovery_normalization(db: Session) -> dict[str, Any]:
    """Deterministic remediation paths — reduces ad-hoc recovery."""
    integrity_stale = 0
    try:
        from app.services.runtime_diagnostics_service import _count_approved_stale_release_candidates

        integrity_stale = _count_approved_stale_release_candidates(db)
    except Exception:
        pass

    paths = [
        {
            "id": "stale_approved_rc",
            "trigger": "approved RC + stale revision",
            "steps": ["POST supersede-stale on RC", "OR rerun rewrite → new RC"],
            "surface": "/admin/integrity",
            "active": integrity_stale > 0,
        },
        {
            "id": "publish_retryable",
            "trigger": "publish_run status=failed_retryable",
            "steps": [
                "Read replay_determinism verdict",
                "If manual_retry_allowed: retry_publish_run API",
                "Else: new RC path",
            ],
            "surface": "/admin/publish-runs",
            "active": True,
        },
        {
            "id": "stale_running_task",
            "trigger": "scraping task running > stale threshold",
            "steps": ["POST reset-stale on task"],
            "surface": "/admin/failed-items",
            "active": True,
        },
    ]

    return {
        "read_only": True,
        "deterministic_paths": paths,
        "prefer_order": ["fix safety flags", "stale approved RC", "stale revision", "retry vs new RC"],
    }


def build_operational_predictability(db: Session) -> dict[str, Any]:
    """Single cohesion model for diagnostics surfaces."""
    from app.services.runtime_reliability_service import build_operational_confidence
    from app.services.runtime_integrity_service import build_runtime_integrity_report

    confidence = build_operational_confidence(db)
    integrity = build_runtime_integrity_report(db)
    replay = build_replay_determinism_report(db)
    guarantees = build_consistency_guarantees(db)
    recovery_norm = build_recovery_normalization(db)

    interpret = (
        f"Confidence={confidence.get('confidence_level')}; "
        f"stale_approved_rc={integrity.get('stale_approved_rc_count')}; "
        f"retryable_sample={replay.get('retryable_sample_count')} "
        f"(allowed={replay.get('manual_retry_allowed_count')}, blocked={replay.get('blocked_count')})"
    )

    return {
        "read_only": True,
        "not_orchestration": True,
        "interpretation": interpret,
        "confidence_level": confidence.get("confidence_level"),
        "consistency_guarantees": guarantees,
        "replay_determinism": replay,
        "recovery_normalization": recovery_norm,
        "linked_surfaces": confidence.get("surfaces", {}),
        "operator_read_order": [
            "1. consistency_guarantees (what code enforces)",
            "2. operational_confidence level",
            "3. replay_determinism verdicts before any retry",
            "4. integrity stale RC remediation if needed",
            "5. recovery_normalization paths",
        ],
    }
