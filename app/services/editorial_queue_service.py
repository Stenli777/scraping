"""Editorial queue grouped by editorial status."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import EditorialStatus
from app.core.feature_flags import is_editorial_workflow_enabled
from app.models.content_quality_score import ContentQualityScore
from app.models.document_revision import DocumentRevision
from app.models.parsed_document import ParsedDocument
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask
from app.services.project_profile_service import resolve_task_project
from app.services.publish_readiness_service import get_publish_readiness


@dataclass
class EditorialQueueItem:
    document_id: int
    task_id: int
    project_id: int | None
    project_slug: str | None
    source_url: str
    editorial_status: str
    revision_number: int
    latest_revision_at: str | None
    review_score: int | None
    quality_overall_score: int | None
    quality_verdict: str | None
    publish_ready: bool
    publish_missing: list[str] = field(default_factory=list)
    has_release_candidate: bool = False
    release_candidate_status: str | None = None
    release_candidate_qa_score: int | None = None
    release_candidate_blocking_count: int = 0


@dataclass
class EditorialQueueGroups:
    needs_review: list[EditorialQueueItem] = field(default_factory=list)
    needs_revision: list[EditorialQueueItem] = field(default_factory=list)
    ready: list[EditorialQueueItem] = field(default_factory=list)
    rejected: list[EditorialQueueItem] = field(default_factory=list)


def _build_item(db: Session, doc: ParsedDocument) -> EditorialQueueItem | None:
    if not doc.rewritten_text or not doc.rewritten_text.strip():
        return None
    task = doc.task
    project = resolve_task_project(db, task) if task else None
    review = db.scalar(
        select(ReviewResult)
        .where(ReviewResult.document_id == doc.id)
        .order_by(ReviewResult.id.desc())
    )
    quality = db.scalar(
        select(ContentQualityScore)
        .where(ContentQualityScore.document_id == doc.id)
        .order_by(ContentQualityScore.id.desc())
    )
    latest_rev = db.scalar(
        select(DocumentRevision)
        .where(DocumentRevision.document_id == doc.id)
        .order_by(DocumentRevision.revision_number.desc())
    )
    readiness = get_publish_readiness(db, doc.id)
    rc = readiness.get("release_candidate") or {}
    rev_at = latest_rev.created_at.isoformat() if latest_rev and latest_rev.created_at else None
    return EditorialQueueItem(
        document_id=doc.id,
        task_id=task.id if task else 0,
        project_id=project.id if project else None,
        project_slug=project.slug if project else None,
        source_url=doc.source_url or "",
        editorial_status=doc.editorial_status or EditorialStatus.GENERATED.value,
        revision_number=doc.current_revision_number or 0,
        latest_revision_at=rev_at,
        review_score=review.score if review else (doc.metadata_json or {}).get("review", {}).get("score"),
        quality_overall_score=quality.overall_score if quality else None,
        quality_verdict=quality.verdict if quality else None,
        publish_ready=readiness["ready"],
        publish_missing=readiness["missing"],
        has_release_candidate=bool(rc.get("exists")),
        release_candidate_status=rc.get("status"),
        release_candidate_qa_score=rc.get("qa_score"),
        release_candidate_blocking_count=len(rc.get("blocking_issues") or []),
    )


def list_editorial_queue(db: Session, *, limit_per_group: int = 50) -> EditorialQueueGroups:
    if not is_editorial_workflow_enabled():
        return EditorialQueueGroups()

    groups = EditorialQueueGroups()
    docs = db.scalars(
        select(ParsedDocument)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ParsedDocument.rewritten_text.isnot(None))
        .order_by(ParsedDocument.updated_at.desc())
        .limit(limit_per_group * 8)
    ).all()

    for doc in docs:
        item = _build_item(db, doc)
        if not item:
            continue
        status = item.editorial_status
        if status in (EditorialStatus.GENERATED.value, EditorialStatus.OPERATOR_REVIEW.value):
            if len(groups.needs_review) < limit_per_group:
                groups.needs_review.append(item)
        elif status == EditorialStatus.NEEDS_REVISION.value:
            if len(groups.needs_revision) < limit_per_group:
                groups.needs_revision.append(item)
        elif status in (
            EditorialStatus.APPROVED.value,
            EditorialStatus.READY_TO_PUBLISH.value,
        ):
            if len(groups.ready) < limit_per_group:
                groups.ready.append(item)
        elif status == EditorialStatus.REJECTED.value:
            if len(groups.rejected) < limit_per_group:
                groups.rejected.append(item)

    return groups
