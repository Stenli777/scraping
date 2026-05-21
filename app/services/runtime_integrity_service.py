"""Runtime integrity scans and safe RC remediation (Integrity phase H)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.publish_run import PublishRun
from app.services.release_candidate_service import (
    OPEN_STATUSES,
    RC_APPROVED,
    RC_ARCHIVED,
    ReleaseCandidateError,
    _revision_stale_for_candidate,
)
from app.models.document_revision import DocumentRevision
from app.services.revision_service import get_latest_revision

INTEGRITY_SCAN_LIMIT = 200
STALE_APPROVED_LIST_LIMIT = 50
SUPERSEDE_BATCH_LIMIT = 20


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def archive_stale_open_rc_for_document(
    db: Session, document_id: int, latest_revision_id: int, *, source: str = "revision"
) -> int:
    """Archive open RCs bound to non-current revision. Audit-preserving; no row delete."""
    rows = db.scalars(
        select(ContentReleaseCandidate).where(
            ContentReleaseCandidate.document_id == document_id,
            ContentReleaseCandidate.status.in_(tuple(OPEN_STATUSES)),
        )
    ).all()
    archived = 0
    stamp = _utcnow().isoformat()
    for row in rows:
        if row.document_revision_id != latest_revision_id:
            row.status = RC_ARCHIVED
            row.updated_at = _utcnow()
            tag = f"\n[integrity-archived {stamp} via {source}] superseded: revision {row.document_revision_id} != latest {latest_revision_id}"
            row.notes = (row.notes or "") + tag
            archived += 1
    if archived:
        db.flush()
    return archived


def list_stale_approved_rc(db: Session, *, limit: int = STALE_APPROVED_LIST_LIMIT) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cand in db.scalars(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.status == RC_APPROVED)
        .order_by(ContentReleaseCandidate.id.desc())
        .limit(min(limit, INTEGRITY_SCAN_LIMIT))
    ).all():
        stale, detail = _revision_stale_for_candidate(db, cand)
        if not stale:
            continue
        rev = db.get(DocumentRevision, cand.document_revision_id)
        latest = get_latest_revision(db, cand.document_id)
        out.append(
            {
                "id": cand.id,
                "document_id": cand.document_id,
                "status": cand.status,
                "approved_at": cand.approved_at.isoformat() if cand.approved_at else None,
                "bound_revision_number": rev.revision_number if rev else None,
                "latest_revision_number": latest.revision_number if latest else None,
                "detail": detail,
                "remediation": "supersede-stale admin action or create new RC after rerun",
            }
        )
    return out


def supersede_stale_approved_rc(
    db: Session, candidate_id: int, *, note: str = "operator supersede stale approved RC"
) -> dict[str, Any]:
    """Safe invalidation: approved + stale → archived with audit note."""
    from app.services.release_candidate_service import get_candidate_status

    candidate = db.get(ContentReleaseCandidate, candidate_id)
    if not candidate:
        raise ReleaseCandidateError(f"Candidate {candidate_id} not found")
    if candidate.status != RC_APPROVED:
        raise ReleaseCandidateError(f"Only approved RC can be superseded (status={candidate.status})")
    stale, detail = _revision_stale_for_candidate(db, candidate)
    if not stale:
        raise ReleaseCandidateError(detail or "RC revision is current; supersede not needed")
    candidate.status = RC_ARCHIVED
    candidate.updated_at = _utcnow()
    candidate.notes = (candidate.notes or "") + f"\n[integrity-supersede {_utcnow().isoformat()}] {note}"
    db.flush()
    return get_candidate_status(db, candidate_id)


def supersede_stale_approved_batch(
    db: Session, *, limit: int = SUPERSEDE_BATCH_LIMIT, dry_run: bool = True
) -> dict[str, Any]:
    items = list_stale_approved_rc(db, limit=limit)
    if dry_run:
        return {"dry_run": True, "would_supersede": [i["id"] for i in items], "count": len(items)}
    done: list[int] = []
    for item in items:
        supersede_stale_approved_rc(db, item["id"], note="batch integrity remediation")
        done.append(item["id"])
    return {"dry_run": False, "superseded_ids": done, "count": len(done)}


def build_runtime_integrity_report(db: Session) -> dict[str, Any]:
    from app.services.publish_retry_service import is_retryable_publish_run
    from app.services.runtime_diagnostics_service import _count_approved_stale_release_candidates

    stale_approved = list_stale_approved_rc(db)
    stale_count = _count_approved_stale_release_candidates(db)

    retryable_runs: list[dict[str, Any]] = []
    for run in db.scalars(
        select(PublishRun).order_by(PublishRun.id.desc()).limit(30)
    ).all():
        if is_retryable_publish_run(run):
            retryable_runs.append(
                {
                    "id": run.id,
                    "document_id": run.document_id,
                    "release_candidate_id": run.release_candidate_id,
                    "retry_count": run.retry_count or 0,
                    "replay_safe": "manual retry only; verify revision/RC before republish",
                }
            )

    orphan_rc_publish = db.scalar(
        select(func.count())
        .select_from(PublishRun)
        .where(PublishRun.release_candidate_id.is_(None), PublishRun.dry_run.is_(False))
    )

    checks: list[dict[str, Any]] = [
        {
            "id": "stale_approved_rc",
            "status": "fail" if stale_count else "pass",
            "count": stale_count,
            "authority": "runtime_enforced",
            "message": "Approved RC binding non-latest revision",
            "remediation": "/admin/integrity or supersede-stale per RC",
        },
        {
            "id": "publish_without_rc_sample",
            "status": "info" if orphan_rc_publish else "pass",
            "count": orphan_rc_publish or 0,
            "authority": "governance_only",
            "message": "Recent publish_runs without release_candidate_id (legacy path indicator)",
            "remediation": "Prefer RC-first publish for production",
        },
        {
            "id": "retryable_publish_runs",
            "status": "warn" if retryable_runs else "pass",
            "count": len(retryable_runs),
            "authority": "runtime_enforced",
            "message": "Publish runs in failed_retryable (manual recovery)",
            "remediation": "/admin/publish-runs — check chain before retry",
        },
    ]

    return {
        "read_only": True,
        "bounded_scan_limit": INTEGRITY_SCAN_LIMIT,
        "stale_approved_rc_count": stale_count,
        "stale_approved_rc": stale_approved,
        "checks": checks,
        "retryable_publish_sample": retryable_runs[:10],
        "no_auto_remediation": True,
    }


def build_recovery_discipline_report(db: Session) -> dict[str, Any]:
    integrity = build_runtime_integrity_report(db)
    return {
        "read_only": True,
        "replay_safe_principles": [
            "New content change → new document_revision → new RC (do not republish stale binding).",
            "Publish retry must target same revision intent; if revision advanced, new RC required.",
            "force=true bypasses gates but never bypasses stale revision guard.",
            "supersede-stale archives approved RC; does not delete publish_runs or revisions.",
        ],
        "stale_approved_rc_count": integrity["stale_approved_rc_count"],
        "stale_approved_rc": integrity["stale_approved_rc"][:5],
        "retryable_publish_sample": integrity["retryable_publish_sample"],
        "integrity_checks": integrity["checks"],
    }


def apply_bounded_integrity_cleanup(
    db: Session, *, supersede_stale_approved: bool = False, limit: int = SUPERSEDE_BATCH_LIMIT
) -> dict[str, Any]:
    """Operator-visible bounded cleanup — never touches audit tables."""
    from app.services.operational_incident_service import cleanup_old_incidents
    from app.services.operational_snapshot_service import cleanup_old_snapshots

    out: dict[str, Any] = {
        "snapshots_deleted": cleanup_old_snapshots(db),
        "incidents_deleted": cleanup_old_incidents(db),
    }
    if supersede_stale_approved:
        out["supersede"] = supersede_stale_approved_batch(db, limit=limit, dry_run=False)
    else:
        out["supersede_preview"] = supersede_stale_approved_batch(db, limit=limit, dry_run=True)
    return out
