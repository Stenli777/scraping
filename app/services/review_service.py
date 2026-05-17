"""LLM review stage — project-aware content gate."""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_llm_review_enabled
from app.core.pipeline_states import PipelineStage
from app.llm.schemas import ReviewRequest, ReviewResponse
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask
from app.services.llm_tasks import execute_review
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.project_profile_service import build_review_context, resolve_task_project

logger = logging.getLogger(__name__)


@dataclass
class ReviewStageResult:
    success: bool
    skipped: bool = False
    take: bool = True
    score: int = 0
    reason: str = ""
    review_result_id: int | None = None
    llm_run_id: int | None = None
    model_alias: str = ""
    upstream_model: str = ""
    content_type: str | None = None
    recommended_angle: str | None = None
    risks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)


def run_review_stage(
    db: Session,
    task: ScrapingTask,
    *,
    clean_text: str,
    parsed_metadata: dict | None = None,
    document_id: int | None = None,
) -> ReviewStageResult:
    if not is_llm_review_enabled():
        return ReviewStageResult(success=True, skipped=True, reason="review disabled")

    settings = get_settings()
    meta = dict(parsed_metadata or {})
    project = resolve_task_project(db, task)
    if project and not task.project_id:
        task.project_id = project.id

    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.REVIEW_PENDING,
        status="entered",
        payload={"project_id": task.project_id},
    )

    request = ReviewRequest(
        task_id=task.id,
        project_id=task.project_id,
        document_id=document_id,
        source_url=task.source_url,
        title=meta.get("title") or meta.get("extracted_title"),
        content=clean_text,
        model_alias=settings.review_model_alias,
        project_slug=project.slug if project else None,
        profile_context=build_review_context(project),
        metadata=meta,
    )

    response = execute_review(db, request)
    return _persist_review(db, task, response, document_id=document_id)


def run_review_for_document(db: Session, document_id: int) -> ReviewStageResult:
    from app.models.parsed_document import ParsedDocument

    document = db.get(ParsedDocument, document_id)
    if not document or not document.clean_text:
        raise ValueError("Document not found or has no clean_text")
    task = document.task
    if not task:
        raise ValueError("Task not found for document")
    meta = dict(document.metadata_json or {})
    result = run_review_stage(
        db, task, clean_text=document.clean_text, parsed_metadata=meta, document_id=document.id
    )
    if result.success and not result.skipped:
        meta["review"] = {
            "take": result.take,
            "score": result.score,
            "reason": result.reason,
            "review_result_id": result.review_result_id,
            "llm_run_id": result.llm_run_id,
        }
        document.metadata_json = meta
        db.commit()
    return result


def _persist_review(
    db: Session,
    task: ScrapingTask,
    response: ReviewResponse,
    *,
    document_id: int | None,
) -> ReviewStageResult:
    llm_run_id = response.metadata.get("llm_run_id")

    if response.success:
        record = ReviewResult(
            task_id=task.id,
            document_id=document_id,
            project_id=task.project_id,
            take=response.take,
            score=response.score,
            reason=response.reason,
            content_type=response.content_type,
            recommended_angle=response.recommended_angle,
            target_project=response.target_project,
            risks_json=response.risks,
            warnings_json=response.warnings,
            llm_run_id=llm_run_id,
        )
        db.add(record)
        db.flush()

        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.REVIEW_PENDING,
            status="completed",
            payload={
                "take": response.take,
                "score": response.score,
                "review_result_id": record.id,
            },
        )
        if not response.take:
            emit_pipeline_event(
                db,
                task.id,
                PipelineStage.REVIEW_REJECTED,
                status="entered",
                payload={"reason": response.reason},
            )

        return ReviewStageResult(
            success=True,
            take=response.take,
            score=response.score,
            reason=response.reason,
            review_result_id=record.id,
            llm_run_id=llm_run_id,
            model_alias=response.model_alias,
            upstream_model=response.upstream_model,
            content_type=response.content_type,
            recommended_angle=response.recommended_angle,
            risks=response.risks,
            metadata=response.metadata,
        )

    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.REVIEW_PENDING,
        status="failed",
        payload={"error": response.error_message},
    )
    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.FAILED_RETRYABLE,
        status="entered",
        payload={"reason": "review_failed"},
    )

    return ReviewStageResult(
        success=False,
        take=False,
        reason=response.error_message or "review failed",
        llm_run_id=llm_run_id,
        model_alias=response.model_alias,
        upstream_model=response.upstream_model or "",
        warnings=response.warnings,
        error_message=response.error_message,
        metadata=response.metadata,
    )
