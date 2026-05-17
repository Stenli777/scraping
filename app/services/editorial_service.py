"""Editorial queue — documents ready for human QC before publish."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import PublishRunStatus
from app.models.content_quality_score import ContentQualityScore
from app.models.parsed_document import ParsedDocument
from app.models.publish_run import PublishRun
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask
from app.models.seo_metadata import SeoMetadata
from app.services.project_profile_service import resolve_task_project
from app.services.publish_readiness_service import get_publish_readiness


@dataclass
class EditorialQueueItem:
    document_id: int
    task_id: int
    project_id: int | None
    project_slug: str | None
    source_url: str
    review_score: int | None
    review_take: bool | None
    quality_overall_score: int | None
    quality_verdict: str | None
    publish_ready: bool
    publish_missing: list[str]
    has_successful_publish: bool


def list_editorial_queue(db: Session, *, limit: int = 100) -> list[EditorialQueueItem]:
    """Documents with review take, rewrite, SEO; quality missing or needs_revision; not published."""
    docs = db.scalars(
        select(ParsedDocument)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ParsedDocument.rewritten_text.isnot(None))
        .order_by(ParsedDocument.id.desc())
        .limit(limit * 3)
    ).all()

    items: list[EditorialQueueItem] = []
    for doc in docs:
        if not doc.rewritten_text or not doc.rewritten_text.strip():
            continue

        review = db.scalar(
            select(ReviewResult)
            .where(ReviewResult.document_id == doc.id)
            .order_by(ReviewResult.id.desc())
        )
        meta = doc.metadata_json or {}
        review_meta = meta.get("review") or {}
        take = review.take if review else review_meta.get("take")
        if take is not True:
            continue

        seo = db.scalar(
            select(SeoMetadata)
            .where(SeoMetadata.document_id == doc.id)
            .order_by(SeoMetadata.id.desc())
        )
        if not seo or not seo.slug:
            continue

        quality = db.scalar(
            select(ContentQualityScore)
            .where(ContentQualityScore.document_id == doc.id)
            .order_by(ContentQualityScore.id.desc())
        )
        if quality and quality.verdict == "approved":
            continue

        success_publish = db.scalar(
            select(PublishRun.id)
            .where(
                PublishRun.document_id == doc.id,
                PublishRun.status == PublishRunStatus.SUCCESS.value,
                PublishRun.dry_run.is_(False),
            )
            .limit(1)
        )
        if success_publish:
            continue

        task = doc.task
        project = resolve_task_project(db, task) if task else None
        readiness = get_publish_readiness(db, doc.id)

        items.append(
            EditorialQueueItem(
                document_id=doc.id,
                task_id=task.id if task else 0,
                project_id=project.id if project else None,
                project_slug=project.slug if project else None,
                source_url=doc.source_url or "",
                review_score=review.score if review else review_meta.get("score"),
                review_take=take,
                quality_overall_score=quality.overall_score if quality else None,
                quality_verdict=quality.verdict if quality else None,
                publish_ready=readiness["ready"],
                publish_missing=readiness["missing"],
                has_successful_publish=False,
            )
        )
        if len(items) >= limit:
            break

    return items
