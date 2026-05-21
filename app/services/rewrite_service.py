"""Rewrite stage for scraping pipeline — mock or CLIProxy via LLM layer."""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.pipeline_states import PipelineStage
from app.llm.schemas import RewriteRequest, RewriteResponse
from app.models.parsed_document import ParsedDocument
from app.services.human_override_service import mark_operator_touched
from app.models.scraping_task import ScrapingTask
from app.rewriters.mock_rewriter import MockRewriter
from app.services.llm_tasks import execute_rewrite
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.project_profile_service import build_rewrite_context, resolve_task_project

logger = logging.getLogger(__name__)


@dataclass
class RewriteStageResult:
    success: bool
    rewritten_text: str = ""
    provider: str = ""
    model_alias: str = ""
    upstream_model: str = ""
    fallback_used: bool = False
    llm_run_id: int | None = None
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)


def run_rewrite_stage(
    db: Session,
    task: ScrapingTask,
    *,
    clean_text: str,
    parsed_metadata: dict | None = None,
) -> RewriteStageResult:
    settings = get_settings()
    provider = settings.rewriter_provider.lower()
    meta = dict(parsed_metadata or {})
    meta["task_id"] = task.id
    meta["project_id"] = task.project_id

    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.REWRITING,
        status="entered",
        payload={"provider": provider},
    )

    if provider == "mock":
        text = MockRewriter().rewrite(clean_text, meta)
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.REWRITING,
            status="completed",
            payload={"provider": "mock"},
        )
        return RewriteStageResult(
            success=True,
            rewritten_text=text,
            provider="mock",
            model_alias="mock",
            metadata={"provider": "mock"},
        )

    if provider == "cliproxy":
        project = resolve_task_project(db, task)
        if project and not task.project_id:
            task.project_id = project.id
            meta["project_id"] = project.id
        profile_ctx = build_rewrite_context(project)
        model_alias = meta.get("model_alias") or settings.rewrite_model_alias
        request = RewriteRequest(
            task_id=task.id,
            project_id=task.project_id,
            source_url=task.source_url,
            title=meta.get("title") or meta.get("extracted_title"),
            content=clean_text,
            model_alias=model_alias,
            language=meta.get("language", project.default_language if project else "ru"),
            metadata=meta,
        )
        response = execute_rewrite(db, request, profile_context=profile_ctx)
        return _stage_result_from_response(db, task, response, provider="cliproxy")

    raise ValueError(f"Unknown rewriter provider: {provider}. Use mock or cliproxy.")


def rerun_rewrite_for_document(db: Session, document_id: int) -> RewriteStageResult:
    from datetime import datetime, timezone

    from app.models.document_version import DocumentVersion
    from app.services.backup_service import BackupService
    from app.services.task_log_service import add_task_log
    from app.core.enums import LogLevel

    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    mark_operator_touched(db, document_id, operator="rerun_rewrite")
    if not document.clean_text:
        raise ValueError("Document has no clean_text to rewrite")

    task = document.task
    if not task:
        raise ValueError(f"Task for document {document_id} not found")

    meta = dict(document.metadata_json or {})
    result = run_rewrite_stage(db, task, clean_text=document.clean_text, parsed_metadata=meta)

    if result.success:
        document.rewritten_text = result.rewritten_text
        document.version += 1
        meta["rewrite"] = {
            "provider": result.provider,
            "model_alias": result.model_alias,
            "upstream_model": result.upstream_model,
            "fallback_used": result.fallback_used,
            "llm_run_id": result.llm_run_id,
        }
        document.metadata_json = meta
        db.add(
            DocumentVersion(
                document_id=document.id,
                version=document.version,
                raw_text=document.raw_text,
                clean_text=document.clean_text,
                rewritten_text=document.rewritten_text,
                content_hash=document.content_hash,
            )
        )
        BackupService().save_task_backup(
            task.id,
            raw_html=document.raw_html,
            raw_text=document.raw_text,
            clean_text=document.clean_text,
            rewritten_text=document.rewritten_text,
            metadata=meta,
            finished_at=datetime.now(timezone.utc),
        )
        add_task_log(db, task.id, "Rewrite rerun succeeded", LogLevel.INFO, meta["rewrite"])
        from app.core.enums import RevisionSourceType
        from app.services.revision_service import create_revision_snapshot

        create_revision_snapshot(
            db,
            document,
            source_type=RevisionSourceType.REWRITE.value,
            source_reference_id=result.llm_run_id,
            rewrite_text=document.rewritten_text,
        )
        db.commit()
    else:
        meta["rewrite_error"] = result.error_message
        document.metadata_json = meta
        add_task_log(
            db,
            task.id,
            "Rewrite rerun failed",
            LogLevel.WARNING,
            {"error": result.error_message},
        )
        db.commit()

    return result


def _stage_result_from_response(
    db: Session,
    task: ScrapingTask,
    response: RewriteResponse,
    *,
    provider: str,
) -> RewriteStageResult:
    if response.success:
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.REWRITING,
            status="completed",
            payload={
                "provider": provider,
                "model_alias": response.model_alias,
                "upstream_model": response.upstream_model,
                "fallback_used": response.fallback_used,
            },
        )
        return RewriteStageResult(
            success=True,
            rewritten_text=response.rewritten_content,
            provider=provider,
            model_alias=response.model_alias,
            upstream_model=response.upstream_model,
            fallback_used=response.fallback_used,
            llm_run_id=response.metadata.get("llm_run_id"),
            metadata=response.metadata,
        )

    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.REWRITING,
        status="failed",
        payload={
            "provider": provider,
            "error": response.error_message,
            "warnings": response.warnings,
        },
    )
    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.FAILED_RETRYABLE,
        status="entered",
        payload={"reason": "rewrite_failed"},
    )

    return RewriteStageResult(
        success=False,
        provider=provider,
        model_alias=response.model_alias,
        upstream_model=response.upstream_model or "",
        fallback_used=response.fallback_used,
        warnings=response.warnings,
        error_message=response.error_message,
        metadata=response.metadata,
    )
