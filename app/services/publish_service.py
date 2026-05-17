"""Manual draft publish — project target → publisher adapter → audit."""

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import PublishRunStatus
from app.core.feature_flags import is_auto_publish_enabled, is_publishing_enabled
from app.core.pipeline_states import PipelineStage
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.scraping_task import ScrapingTask
from app.models.publish_run import PublishRun
from app.models.publish_target import PublishTarget
from app.models.review_result import ReviewResult
from app.models.seo_metadata import SeoMetadata
from app.publishers.exceptions import (
    PublishClientError,
    PublishError,
    PublishServerError,
    PublishTransportError,
    PublishValidationError,
)
from app.publishers.payloads import build_article_v1_payload
from app.publishers.registry import get_publisher
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.project_profile_service import resolve_task_project

logger = logging.getLogger(__name__)


@dataclass
class PublishDraftResult:
    success: bool
    publish_run_id: int | None = None
    status: str = ""
    dry_run: bool = False
    external_id: str | None = None
    error_message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    validation_error: bool = False


def _latest_seo(db: Session, document_id: int) -> SeoMetadata | None:
    return db.scalar(
        select(SeoMetadata)
        .where(SeoMetadata.document_id == document_id)
        .order_by(SeoMetadata.id.desc())
    )


def _latest_review(db: Session, document_id: int) -> ReviewResult | None:
    return db.scalar(
        select(ReviewResult)
        .where(ReviewResult.document_id == document_id)
        .order_by(ReviewResult.id.desc())
    )


def _validate_preconditions(
    db: Session,
    document: ParsedDocument,
    target: PublishTarget,
    *,
    requested_status: str | None = None,
) -> tuple[ScrapingTask, Project, SeoMetadata]:
    if not is_publishing_enabled():
        raise PublishValidationError("Publishing is disabled (ENABLE_PUBLISHING=false)")

    if is_auto_publish_enabled():
        raise PublishValidationError("Auto-publish is not allowed on this stage")

    status = requested_status or target.default_status or "draft"
    if status != "draft":
        raise PublishValidationError("Only draft status is allowed")

    if not document.rewritten_text or not document.rewritten_text.strip():
        raise PublishValidationError("Document has no rewritten_text")

    seo = _latest_seo(db, document.id)
    if not seo:
        raise PublishValidationError("Document has no seo_metadata")

    if not seo.slug:
        raise PublishValidationError("seo_metadata.slug is required")

    task = document.task
    if not task:
        raise PublishValidationError("Document has no associated task")

    project = resolve_task_project(db, task)
    if not project:
        raise PublishValidationError("No project found for document")

    if target.project_id != project.id:
        raise PublishValidationError("Publish target does not belong to document project")

    if not target.enabled:
        raise PublishValidationError("Publish target is disabled")

    return task, project, seo


def publish_draft_for_document(
    db: Session,
    document_id: int,
    *,
    publish_target_id: int | None = None,
    dry_run: bool | None = None,
) -> PublishDraftResult:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise PublishValidationError(f"Document {document_id} not found")

    task = document.task
    project = resolve_task_project(db, task) if task else None

    if publish_target_id:
        target = db.get(PublishTarget, publish_target_id)
    elif project:
        target = db.scalar(
            select(PublishTarget)
            .where(PublishTarget.project_id == project.id, PublishTarget.enabled.is_(True))
            .order_by(PublishTarget.id.asc())
        )
    else:
        target = None

    if not target:
        raise PublishValidationError("No publish target configured")

    try:
        task, project, seo = _validate_preconditions(db, document, target)
    except PublishValidationError as exc:
        return PublishDraftResult(
            success=False,
            error_message=str(exc),
            validation_error=True,
        )

    review = _latest_review(db, document.id)
    effective_dry_run = target.dry_run if dry_run is None else dry_run
    if target.target_type == "mock":
        effective_dry_run = True

    if target.payload_format != "article_v1":
        raise PublishValidationError(f"Unsupported payload_format: {target.payload_format}")

    payload = build_article_v1_payload(
        document=document,
        task=task,
        project=project,
        target=target,
        seo=seo,
        review=review,
    )

    settings = get_settings()
    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.PUBLISHING,
        status="entered",
        payload={"publish_target_id": target.id, "dry_run": effective_dry_run},
    )

    run = PublishRun(
        project_id=project.id,
        document_id=document.id,
        task_id=task.id,
        publish_target_id=target.id,
        status=PublishRunStatus.PENDING.value,
        dry_run=effective_dry_run,
        endpoint_url=target.endpoint_url,
        request_payload_json=payload,
    )
    db.add(run)
    db.flush()

    publisher = get_publisher(target)

    try:
        result = publisher.publish(
            target,
            payload,
            dry_run=effective_dry_run,
            timeout_seconds=settings.publish_default_timeout,
        )
        run.response_status_code = result.response_status_code
        run.response_body = result.response_body
        run.external_id = result.external_id
        run.dry_run = result.dry_run
        run.status = result.status
        run.endpoint_url = result.endpoint_url or target.endpoint_url

        if result.success:
            emit_pipeline_event(
                db,
                task.id,
                PipelineStage.PUBLISHED_DRAFT,
                status="completed",
                payload={
                    "publish_run_id": run.id,
                    "external_id": result.external_id,
                    "dry_run": result.dry_run,
                },
            )
            db.commit()
            return PublishDraftResult(
                success=True,
                publish_run_id=run.id,
                status=run.status,
                dry_run=run.dry_run,
                external_id=run.external_id,
                payload=payload,
            )

        run.error_message = result.error_message
        db.commit()
        return PublishDraftResult(
            success=False,
            publish_run_id=run.id,
            status=run.status,
            error_message=result.error_message,
            payload=payload,
        )

    except PublishValidationError as exc:
        run.status = PublishRunStatus.FAILED_TERMINAL.value
        run.error_message = str(exc)
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.FAILED_TERMINAL,
            status="entered",
            payload={"reason": "publish_validation", "error": str(exc)},
        )
        db.commit()
        return PublishDraftResult(
            success=False,
            publish_run_id=run.id,
            status=run.status,
            error_message=str(exc),
            payload=payload,
        )

    except PublishClientError as exc:
        run.status = PublishRunStatus.FAILED_TERMINAL.value
        run.error_message = str(exc)
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.FAILED_TERMINAL,
            status="entered",
            payload={"reason": "publish_client_error"},
        )
        db.commit()
        return PublishDraftResult(
            success=False,
            publish_run_id=run.id,
            status=run.status,
            error_message=str(exc),
            payload=payload,
        )

    except (PublishTransportError, PublishServerError) as exc:
        run.status = PublishRunStatus.FAILED_RETRYABLE.value
        run.error_message = str(exc)
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.FAILED_RETRYABLE,
            status="entered",
            payload={"reason": "publish_retryable"},
        )
        db.commit()
        return PublishDraftResult(
            success=False,
            publish_run_id=run.id,
            status=run.status,
            error_message=str(exc),
            payload=payload,
        )

    except PublishError as exc:
        logger.warning("Publish failed document=%s: %s", document_id, exc)
        run.status = PublishRunStatus.FAILED_RETRYABLE.value
        run.error_message = str(exc)
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.FAILED_RETRYABLE,
            status="entered",
            payload={"reason": "publish_error"},
        )
        db.commit()
        return PublishDraftResult(
            success=False,
            publish_run_id=run.id,
            status=run.status,
            error_message=str(exc),
            payload=payload,
        )
