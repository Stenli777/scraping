"""Manual draft publish — project target → publisher adapter → audit."""

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_crmflow24_publish_endpoint, get_settings
from app.core.enums import PublishRunStatus
from app.core.feature_flags import (
    is_auto_publish_enabled,
    is_editorial_workflow_enabled,
    is_publishing_enabled,
    is_quality_review_enabled,
)
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
    PublishDuplicateError,
    PublishError,
    PublishServerError,
    PublishTransportError,
    PublishUnsupportedPayloadError,
    PublishValidationError,
)
from app.publishers.payloads import (
    PAYLOAD_VERSION_ARTICLE_V1,
    PAYLOAD_VERSION_ARTICLE_V2,
    build_publish_payload,
)
from app.publishers.registry import get_publisher
from app.publishers.validators import (
    validate_article_v1_publish,
    validate_editorial_for_publish,
    validate_quality_for_publish,
    validate_review_for_publish,
)
from app.publishers.validators_v2 import validate_article_v2_publish
from app.publishers.versions import is_supported_payload_format
from app.services.publish_retry_service import compute_next_retry_at, classify_failure
from app.services.editorial_service import mark_published_draft
from app.services.quality_service import MAX_SPAM_SCORE, get_latest_quality_score
from app.services.revision_service import ensure_revision_for_publish
from app.services.media_service import build_media_block_for_publish, get_approved_preview_asset
from app.services.publication_tracking_service import create_publication_from_publish_run
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
    draft_url: str | None = None
    error_message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    validation_error: bool = False
    duplicate: bool = False
    existing_publish_run_id: int | None = None
    publication_record_id: int | None = None


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


def resolve_target_endpoint(target: PublishTarget) -> tuple[str, bool]:
    """Effective endpoint and whether HTTP should be skipped (dry-run)."""
    settings = get_settings()
    endpoint = (target.endpoint_url or "").strip()
    if not endpoint and target.target_type != "mock":
        if target.name in ("crmflow24-draft-webhook", "crmflow24-production-v2"):
            endpoint = get_crmflow24_publish_endpoint()
    force_dry = target.dry_run or not endpoint
    return endpoint, force_dry


def find_duplicate_publish_run(
    db: Session,
    *,
    document_id: int,
    publish_target_id: int,
    payload_version: str = PAYLOAD_VERSION_ARTICLE_V1,
) -> PublishRun | None:
    return db.scalar(
        select(PublishRun)
        .where(
            PublishRun.document_id == document_id,
            PublishRun.publish_target_id == publish_target_id,
            PublishRun.payload_version == payload_version,
            PublishRun.status == PublishRunStatus.SUCCESS.value,
            PublishRun.dry_run.is_(False),
        )
        .order_by(PublishRun.id.desc())
    )


def _validate_preconditions(
    db: Session,
    document: ParsedDocument,
    target: PublishTarget,
    *,
    requested_status: str | None = None,
    force: bool = False,
) -> tuple[ScrapingTask, Project, SeoMetadata, ReviewResult | None]:
    if not is_publishing_enabled():
        raise PublishValidationError("Publishing is disabled (ENABLE_PUBLISHING=false)")

    if is_auto_publish_enabled():
        raise PublishValidationError("Auto-publish is not allowed on this stage")

    status = requested_status or target.default_status or "draft"
    if status != "draft":
        raise PublishValidationError("Only draft status is allowed")

    task = document.task
    if not task:
        raise PublishValidationError("Document has no associated task")

    project = resolve_task_project(db, task)
    if not project:
        raise PublishValidationError("No project found for document")

    if not project.enabled:
        raise PublishValidationError("Project is disabled")

    if target.project_id != project.id:
        raise PublishValidationError("Publish target does not belong to document project")

    if not target.enabled:
        raise PublishValidationError("Publish target is disabled")

    seo = _latest_seo(db, document.id)
    review = _latest_review(db, document.id)
    meta = document.metadata_json or {}

    article_check = validate_article_v1_publish(
        document=document,
        project=project,
        target=target,
        seo=seo,
    )
    article_check.raise_if_invalid()

    review_check = validate_review_for_publish(
        project=project,
        review=review,
        review_meta=meta.get("review") or {},
        force=force,
    )
    review_check.raise_if_invalid()

    settings = get_settings()
    quality = get_latest_quality_score(db, document.id)
    quality_check = validate_quality_for_publish(
        quality_enabled=is_quality_review_enabled(),
        quality_score=quality,
        min_score=settings.min_quality_score_for_publish,
        max_spamminess=MAX_SPAM_SCORE,
        force=force,
    )
    quality_check.raise_if_invalid()

    editorial_check = validate_editorial_for_publish(
        editorial_enabled=is_editorial_workflow_enabled(),
        document=document,
        force=force,
    )
    editorial_check.raise_if_invalid()

    if not seo:
        raise PublishValidationError("Document has no seo_metadata")
    if not seo.slug:
        raise PublishValidationError("seo_metadata.slug is required")

    if not document.rewritten_text or not document.rewritten_text.strip():
        raise PublishValidationError("Document has no rewritten_text")

    return task, project, seo, review


def publish_draft_for_document(
    db: Session,
    document_id: int,
    *,
    publish_target_id: int | None = None,
    dry_run: bool | None = None,
    force: bool = False,
    retry_parent_publish_run_id: int | None = None,
    retry_count: int = 0,
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
        task, project, seo, review = _validate_preconditions(
            db, document, target, force=force
        )
    except PublishValidationError as exc:
        return PublishDraftResult(
            success=False,
            error_message=str(exc),
            validation_error=True,
        )

    if not force:
        existing = find_duplicate_publish_run(
            db,
            document_id=document.id,
            publish_target_id=target.id,
            payload_version=payload_format,
        )
        if existing:
            return PublishDraftResult(
                success=False,
                duplicate=True,
                existing_publish_run_id=existing.id,
                error_message=(
                    f"Duplicate publish blocked: successful run #{existing.id} already exists. "
                    "Use force=true to publish again."
                ),
                validation_error=True,
            )

    payload_format = (target.payload_format or PAYLOAD_VERSION_ARTICLE_V1).strip()
    if not is_supported_payload_format(payload_format):
        return PublishDraftResult(
            success=False,
            error_message=f"Unsupported payload_format: {payload_format}",
            validation_error=True,
        )

    media_block = build_media_block_for_publish(db, document.id)
    revision = ensure_revision_for_publish(db, document)
    payload = build_publish_payload(
        payload_format,
        document=document,
        task=task,
        project=project,
        target=target,
        seo=seo,
        review=review,
        media=media_block,
        revision_id=revision.id,
    )
    if payload_format == PAYLOAD_VERSION_ARTICLE_V2:
        validate_article_v2_publish(
            document=document,
            project=project,
            target=target,
            seo=seo,
            payload=payload,
        ).raise_if_invalid()
    else:
        validate_article_v1_publish(
            document=document,
            project=project,
            target=target,
            seo=seo,
            payload=payload,
        ).raise_if_invalid()

    endpoint, endpoint_requires_dry = resolve_target_endpoint(target)
    if dry_run is not None:
        effective_dry_run = bool(dry_run) or endpoint_requires_dry
    else:
        effective_dry_run = endpoint_requires_dry or target.dry_run
    if target.target_type == "mock":
        effective_dry_run = True

    settings = get_settings()
    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.PUBLISHING,
        status="entered",
        payload={
            "publish_target_id": target.id,
            "dry_run": effective_dry_run,
            "force": force,
        },
    )

    preview_asset = get_approved_preview_asset(db, document.id)

    run = PublishRun(
        project_id=project.id,
        document_id=document.id,
        task_id=task.id,
        publish_target_id=target.id,
        document_revision_id=revision.id,
        preview_media_asset_id=preview_asset.id if preview_asset else None,
        status=PublishRunStatus.PENDING.value,
        dry_run=effective_dry_run,
        endpoint_url=endpoint or target.endpoint_url,
        request_payload_json=payload,
        payload_version=payload_format,
        force_used=force,
        retry_parent_publish_run_id=retry_parent_publish_run_id,
        retry_count=retry_count,
    )
    db.add(run)
    db.flush()

    publisher = get_publisher(target)
    publish_target: Any = target
    if endpoint and endpoint != (target.endpoint_url or ""):
        publish_target = SimpleNamespace(
            id=target.id,
            name=target.name,
            target_type=target.target_type,
            endpoint_url=endpoint,
            auth_type=target.auth_type,
            auth_token_env_name=target.auth_token_env_name,
            dry_run=target.dry_run,
            default_status=target.default_status,
            payload_format=target.payload_format,
            enabled=target.enabled,
        )

    try:
        result = publisher.publish(
            publish_target,
            payload,
            dry_run=effective_dry_run,
            timeout_seconds=settings.publish_default_timeout,
        )
        run.response_status_code = result.response_status_code
        run.response_body = result.response_body
        run.external_id = result.external_id
        run.draft_url = result.draft_url
        run.remote_status = result.metadata.get("remote_status") or (
            result.status if not result.dry_run else None
        )
        run.response_schema_version = result.metadata.get("response_schema_version")
        run.dry_run = result.dry_run
        run.status = (
            PublishRunStatus.DRY_RUN.value
            if result.dry_run
            else PublishRunStatus.SUCCESS.value
            if result.success
            else result.status
        )
        run.endpoint_url = result.endpoint_url or endpoint or target.endpoint_url

        if result.success:
            emit_pipeline_event(
                db,
                task.id,
                PipelineStage.PUBLISHED_DRAFT,
                status="completed",
                payload={
                    "publish_run_id": run.id,
                    "document_revision_id": revision.id,
                    "revision_number": revision.revision_number,
                    "external_id": result.external_id,
                    "draft_url": result.draft_url,
                    "dry_run": result.dry_run,
                    "force": force,
                },
            )
            mark_published_draft(db, document.id)
            pub_record = create_publication_from_publish_run(
                db,
                run=run,
                external_id=result.external_id,
                external_url=result.draft_url,
                dry_run=result.dry_run,
                remote_status=run.remote_status,
            )
            db.commit()
            return PublishDraftResult(
                success=True,
                publish_run_id=run.id,
                status=run.status,
                dry_run=run.dry_run,
                external_id=run.external_id,
                draft_url=run.draft_url,
                payload=payload,
                publication_record_id=pub_record.id if pub_record else None,
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
            validation_error=True,
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
        run.last_retry_error = str(exc)
        run.next_retry_at = compute_next_retry_at(run.retry_count + 1)
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.FAILED_RETRYABLE,
            status="entered",
            payload={"reason": "publish_retryable", "force": force},
        )
        db.commit()
        return PublishDraftResult(
            success=False,
            publish_run_id=run.id,
            status=run.status,
            error_message=str(exc),
            payload=payload,
        )

    except PublishUnsupportedPayloadError as exc:
        run.status = PublishRunStatus.FAILED_TERMINAL.value
        run.error_message = str(exc)
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.FAILED_TERMINAL,
            status="entered",
            payload={"reason": "unsupported_payload"},
        )
        db.commit()
        return PublishDraftResult(
            success=False,
            publish_run_id=run.id,
            status=run.status,
            error_message=str(exc),
            payload=payload,
            validation_error=True,
        )

    except PublishError as exc:
        logger.warning("Publish failed document=%s: %s", document_id, exc)
        failure_kind = classify_failure(status_code=run.response_status_code, error_message=str(exc))
        if failure_kind in ("validation_failed", "unauthorized", "unsupported_payload", "terminal"):
            run.status = PublishRunStatus.FAILED_TERMINAL.value
        else:
            run.status = PublishRunStatus.FAILED_RETRYABLE.value
            run.next_retry_at = compute_next_retry_at(run.retry_count + 1)
        run.error_message = str(exc)
        run.last_retry_error = str(exc)
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
