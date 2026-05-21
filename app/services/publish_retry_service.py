"""Manual publish retry and retry chain semantics."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from typing import Any

from app.core.enums import PublishRunStatus
from app.models.publish_run import PublishRun
from app.publishers.exceptions import PublishValidationError


RETRYABLE_STATUSES = frozenset({PublishRunStatus.FAILED_RETRYABLE.value})
TERMINAL_STATUSES = frozenset(
    {
        PublishRunStatus.FAILED_TERMINAL.value,
        PublishRunStatus.SUCCESS.value,
        PublishRunStatus.DRY_RUN.value,
    }
)
DEFAULT_RETRY_BACKOFF_SECONDS = 300
MAX_AUTO_RETRY_COUNT = 5


@dataclass
class PublishRetryResult:
    success: bool
    new_publish_run_id: int | None = None
    parent_publish_run_id: int | None = None
    error_message: str | None = None


def is_retryable_publish_run(run: PublishRun) -> bool:
    return run.status in RETRYABLE_STATUSES


def classify_failure(*, status_code: int | None, error_message: str | None) -> str:
    msg = (error_message or "").lower()
    if status_code == 401 or status_code == 403 or "unauthorized" in msg:
        return "unauthorized"
    if status_code == 400 or "validation" in msg or "unsupported" in msg:
        return "validation_failed"
    if "unsupported payload" in msg or "payload_version" in msg:
        return "unsupported_payload"
    if status_code and 500 <= status_code < 600:
        return "retryable"
    if status_code in (502, 503, 504) or "timeout" in msg or "network" in msg:
        return "retryable"
    if status_code and 400 <= status_code < 500:
        return "terminal"
    return "retryable"


def compute_next_retry_at(retry_count: int) -> datetime:
    backoff = min(DEFAULT_RETRY_BACKOFF_SECONDS * (2 ** max(retry_count - 1, 0)), 3600)
    return datetime.now(timezone.utc) + timedelta(seconds=backoff)


def get_retry_chain(db: Session, run_id: int) -> list[PublishRun]:
    run = db.get(PublishRun, run_id)
    if not run:
        return []

    root_id = run_id
    current = run
    while current.retry_parent_publish_run_id:
        parent = db.get(PublishRun, current.retry_parent_publish_run_id)
        if not parent:
            break
        root_id = parent.id
        current = parent

    chain: list[PublishRun] = []
    to_visit = [root_id]
    seen: set[int] = set()
    while to_visit:
        rid = to_visit.pop(0)
        if rid in seen:
            continue
        seen.add(rid)
        node = db.get(PublishRun, rid)
        if not node:
            continue
        chain.append(node)
        children = (
            db.query(PublishRun)
            .filter(PublishRun.retry_parent_publish_run_id == rid)
            .order_by(PublishRun.id.asc())
            .all()
        )
        for child in children:
            to_visit.append(child.id)

    chain.sort(key=lambda r: r.id)
    return chain


def describe_retry_chain_for_operator(db: Session, publish_run_id: int) -> dict[str, Any]:
    """Normalized chain + verdict for admin (phase J)."""
    from app.services.runtime_predictability_service import (
        normalize_retry_chain,
        resolve_replay_verdict,
    )

    return {
        "chain": normalize_retry_chain(db, publish_run_id),
        "verdict": resolve_replay_verdict(db, publish_run_id),
    }


def retry_publish_run(db: Session, publish_run_id: int) -> PublishRetryResult:
    parent = db.get(PublishRun, publish_run_id)
    if not parent:
        raise PublishValidationError(f"Publish run {publish_run_id} not found")

    if not is_retryable_publish_run(parent):
        return PublishRetryResult(
            success=False,
            parent_publish_run_id=parent.id,
            error_message=f"Publish run #{parent.id} is not retryable (status={parent.status})",
        )

    if parent.retry_count >= MAX_AUTO_RETRY_COUNT:
        return PublishRetryResult(
            success=False,
            parent_publish_run_id=parent.id,
            error_message=f"Maximum retry count ({MAX_AUTO_RETRY_COUNT}) reached",
        )

    from app.services.publish_service import publish_draft_for_document

    parent.last_retry_error = parent.error_message
    parent.next_retry_at = compute_next_retry_at(parent.retry_count + 1)
    db.flush()

    result = publish_draft_for_document(
        db,
        parent.document_id,
        publish_target_id=parent.publish_target_id,
        dry_run=parent.dry_run,
        force=parent.force_used,
        force_reason=parent.force_reason,
        retry_parent_publish_run_id=parent.id,
        retry_count=parent.retry_count + 1,
    )

    if result.publish_run_id:
        child = db.get(PublishRun, result.publish_run_id)
        if child:
            child.retry_parent_publish_run_id = parent.id
            child.retry_count = parent.retry_count + 1
            db.flush()

    return PublishRetryResult(
        success=result.success,
        new_publish_run_id=result.publish_run_id,
        parent_publish_run_id=parent.id,
        error_message=result.error_message,
    )
