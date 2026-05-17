"""Admin page context: entity links and related records."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.discovered_url import DiscoveredUrl
from app.models.llm_run import LLMRun
from app.models.parsed_document import ParsedDocument
from app.models.pipeline_event import PipelineEvent
from app.models.project import Project
from app.models.publish_run import PublishRun
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask
from app.models.seo_metadata import SeoMetadata
from app.services.project_profile_service import resolve_task_project


def load_task_context(db: Session, task: ScrapingTask) -> dict:
    document = task.document
    discovered = db.scalar(
        select(DiscoveredUrl)
        .where(DiscoveredUrl.existing_task_id == task.id)
        .order_by(DiscoveredUrl.id.desc())
    )
    project = resolve_task_project(db, task)
    review_record = None
    seo_record = None
    publish_runs: list[PublishRun] = []
    if document:
        review_record = db.scalar(
            select(ReviewResult)
            .where(ReviewResult.document_id == document.id)
            .order_by(ReviewResult.id.desc())
        )
        seo_record = db.scalar(
            select(SeoMetadata)
            .where(SeoMetadata.document_id == document.id)
            .order_by(SeoMetadata.id.desc())
        )
        publish_runs = list(
            db.scalars(
                select(PublishRun)
                .where(PublishRun.document_id == document.id)
                .order_by(PublishRun.id.desc())
                .limit(20)
            ).all()
        )
    llm_runs = list(
        db.scalars(
            select(LLMRun)
            .where(LLMRun.task_id == task.id)
            .order_by(LLMRun.id.desc())
            .limit(20)
        ).all()
    )
    pipeline_events = list(
        db.scalars(
            select(PipelineEvent)
            .where(PipelineEvent.task_id == task.id)
            .order_by(PipelineEvent.id.desc())
            .limit(20)
        ).all()
    )
    return {
        "discovered_url": discovered,
        "project": project,
        "review_record": review_record,
        "seo_record": seo_record,
        "publish_runs": publish_runs,
        "llm_runs": llm_runs,
        "pipeline_events": pipeline_events,
    }


def load_document_context(db: Session, document: ParsedDocument) -> dict:
    task = document.task
    ctx = load_task_context(db, task) if task else {}
    if task:
        return ctx
    discovered = db.scalar(
        select(DiscoveredUrl)
        .where(DiscoveredUrl.normalized_url == document.source_url)
        .order_by(DiscoveredUrl.id.desc())
    )
    ctx["discovered_url"] = discovered
    return ctx
