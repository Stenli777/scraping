"""LLM SEO enrichment stage."""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_seo_enrich_enabled
from app.core.pipeline_states import PipelineStage
from app.llm.schemas import SeoEnrichRequest, SeoEnrichResponse
from app.models.seo_metadata import SeoMetadata
from app.models.scraping_task import ScrapingTask
from app.services.llm_tasks import execute_seo_enrich
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.project_profile_service import build_seo_context, resolve_task_project

logger = logging.getLogger(__name__)


@dataclass
class SeoStageResult:
    success: bool
    skipped: bool = False
    seo_metadata_id: int | None = None
    llm_run_id: int | None = None
    seo_title: str = ""
    slug: str = ""
    model_alias: str = ""
    upstream_model: str = ""
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)


def run_seo_stage(
    db: Session,
    task: ScrapingTask,
    *,
    content: str,
    parsed_metadata: dict | None = None,
    document_id: int | None = None,
) -> SeoStageResult:
    if not is_seo_enrich_enabled():
        return SeoStageResult(success=True, skipped=True)

    settings = get_settings()
    meta = dict(parsed_metadata or {})
    project = resolve_task_project(db, task)

    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.SEO_ENRICH_PENDING,
        status="entered",
        payload={"project_id": task.project_id},
    )

    request = SeoEnrichRequest(
        task_id=task.id,
        project_id=task.project_id,
        document_id=document_id,
        source_url=task.source_url,
        title=meta.get("title") or meta.get("extracted_title") or meta.get("rewritten_title"),
        content=content,
        model_alias=settings.seo_model_alias,
        profile_context=build_seo_context(project),
        metadata=meta,
    )

    response = execute_seo_enrich(db, request)
    return _persist_seo(db, task, response, document_id=document_id)


def run_seo_for_document(db: Session, document_id: int) -> SeoStageResult:
    from app.models.parsed_document import ParsedDocument

    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError("Document not found")
    content = document.rewritten_text or document.clean_text
    if not content:
        raise ValueError("No rewritten_text or clean_text for SEO")
    task = document.task
    if not task:
        raise ValueError("Task not found for document")
    meta = dict(document.metadata_json or {})
    result = run_seo_stage(
        db, task, content=content, parsed_metadata=meta, document_id=document.id
    )
    if result.success and not result.skipped:
        meta["seo"] = {
            "seo_metadata_id": result.seo_metadata_id,
            "seo_title": result.seo_title,
            "slug": result.slug,
            "llm_run_id": result.llm_run_id,
        }
        document.metadata_json = meta
        from app.core.enums import RevisionSourceType
        from app.models.seo_metadata import SeoMetadata
        from app.services.revision_service import create_revision_snapshot

        seo_row = db.get(SeoMetadata, result.seo_metadata_id) if result.seo_metadata_id else None
        create_revision_snapshot(
            db,
            document,
            source_type=RevisionSourceType.SEO_UPDATE.value,
            source_reference_id=result.seo_metadata_id,
            seo=seo_row,
        )
        db.commit()
    return result


def _persist_seo(
    db: Session,
    task: ScrapingTask,
    response: SeoEnrichResponse,
    *,
    document_id: int | None,
) -> SeoStageResult:
    llm_run_id = response.metadata.get("llm_run_id")

    if response.success and document_id:
        record = SeoMetadata(
            document_id=document_id,
            task_id=task.id,
            project_id=task.project_id,
            seo_title=response.seo_title,
            seo_description=response.seo_description,
            h1=response.h1,
            slug=response.slug,
            excerpt=response.excerpt,
            tags_json=response.tags,
            faq_json=response.faq,
            suggested_category=response.suggested_category,
            llm_run_id=llm_run_id,
        )
        db.add(record)
        db.flush()

        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.SEO_ENRICH_PENDING,
            status="completed",
            payload={"seo_metadata_id": record.id, "slug": response.slug},
        )

        return SeoStageResult(
            success=True,
            seo_metadata_id=record.id,
            llm_run_id=llm_run_id,
            seo_title=response.seo_title,
            slug=response.slug,
            model_alias=response.model_alias,
            upstream_model=response.upstream_model,
            metadata=response.metadata,
        )

    if response.success and not document_id:
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.SEO_ENRICH_PENDING,
            status="completed",
            payload={"note": "no document_id yet"},
        )
        return SeoStageResult(
            success=True,
            llm_run_id=llm_run_id,
            seo_title=response.seo_title,
            slug=response.slug,
            model_alias=response.model_alias,
            upstream_model=response.upstream_model,
            metadata=response.metadata,
        )

    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.SEO_ENRICH_PENDING,
        status="failed",
        payload={"error": response.error_message},
    )
    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.FAILED_RETRYABLE,
        status="entered",
        payload={"reason": "seo_failed"},
    )

    return SeoStageResult(
        success=False,
        llm_run_id=llm_run_id,
        model_alias=response.model_alias,
        warnings=response.warnings,
        error_message=response.error_message,
        metadata=response.metadata,
    )
