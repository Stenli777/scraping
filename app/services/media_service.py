"""Manual-first media pipeline — optional preview generation."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_media_generation_enabled, is_media_pipeline_enabled
from app.media.exceptions import MediaDisabledError, MediaGenerationDisabledError, MediaProviderError
from app.media.service import get_media_provider
from app.media.schemas import MediaPromptBundle
from app.models.media_asset import MediaAsset
from app.models.media_job import MediaJob
from app.models.parsed_document import ParsedDocument
from app.services.media_prompt_service import generate_preview_prompts
from app.services.revision_service import get_latest_revision

logger = logging.getLogger(__name__)


@dataclass
class MediaOperationResult:
    success: bool
    media_asset_id: int | None = None
    media_job_id: int | None = None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)


def _require_pipeline() -> None:
    if not is_media_pipeline_enabled():
        raise MediaDisabledError("Media pipeline disabled (ENABLE_MEDIA_PIPELINE=false)")


def _resolve_revision_id(db: Session, document: ParsedDocument) -> int | None:
    rev = get_latest_revision(db, document.id)
    return rev.id if rev else None


def get_approved_preview_asset(db: Session, document_id: int) -> MediaAsset | None:
    return db.scalar(
        select(MediaAsset)
        .where(
            MediaAsset.document_id == document_id,
            MediaAsset.media_type == "preview",
            MediaAsset.status == "approved",
        )
        .order_by(MediaAsset.id.desc())
    )


def list_document_media(db: Session, document_id: int) -> list[MediaAsset]:
    return list(
        db.scalars(
            select(MediaAsset)
            .where(MediaAsset.document_id == document_id)
            .order_by(MediaAsset.id.desc())
        ).all()
    )


def create_media_job(
    db: Session,
    *,
    document_id: int,
    job_type: str,
    provider: str,
    prompt_text: str | None = None,
    negative_prompt: str | None = None,
    media_asset_id: int | None = None,
) -> MediaJob:
    _require_pipeline()
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError("Document not found")
    task = document.task
    project_id = task.project_id if task else None
    job = MediaJob(
        project_id=project_id,
        document_id=document_id,
        revision_id=_resolve_revision_id(db, document),
        media_asset_id=media_asset_id,
        job_type=job_type,
        provider=provider,
        status="queued",
        prompt_text=prompt_text,
        negative_prompt=negative_prompt,
    )
    db.add(job)
    db.flush()
    return job


def run_preview_generation(
    db: Session,
    document_id: int,
    *,
    provider: str | None = None,
    use_llm_prompt: bool = True,
) -> MediaOperationResult:
    _require_pipeline()
    settings = get_settings()
    prov_name = (provider or settings.media_provider or "placeholder").strip().lower()

    if prov_name != "placeholder" and not is_media_generation_enabled():
        raise MediaGenerationDisabledError(
            "AI media generation disabled (ENABLE_MEDIA_GENERATION=false)"
        )

    document = db.get(ParsedDocument, document_id)
    if not document:
        return MediaOperationResult(success=False, error_message="Document not found")

    prompt_result = generate_preview_prompts(db, document_id, use_llm=use_llm_prompt)
    bundle = prompt_result.bundle or MediaPromptBundle(prompt="", alt_text="", caption="")

    job = create_media_job(
        db,
        document_id=document_id,
        job_type="generate_preview",
        provider=prov_name,
        prompt_text=bundle.prompt,
    )
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.flush()

    started = time.perf_counter()
    warnings: list[str] = []
    if prompt_result.error_message:
        warnings.append(f"prompt_fallback: {prompt_result.error_message}")

    try:
        media_provider = get_media_provider(prov_name)
        gen = media_provider.generate_preview(
            prompt=bundle.prompt,
            alt_text=bundle.alt_text,
            caption=bundle.caption,
            document_id=document_id,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        if not gen.success:
            job.status = "failed"
            job.error_message = gen.error_message or "generation failed"
            job.latency_ms = latency_ms
            job.completed_at = datetime.now(timezone.utc)
            job.response_json = {"success": False}
            db.commit()
            return MediaOperationResult(
                success=False,
                media_job_id=job.id,
                error_message=job.error_message,
                warnings=warnings,
            )

        asset = MediaAsset(
            project_id=job.project_id,
            document_id=document_id,
            revision_id=job.revision_id,
            media_type="preview",
            source_type="generated" if prov_name != "placeholder" else "placeholder",
            status="generated",
            storage_path=gen.storage_path,
            prompt_text=bundle.prompt,
            alt_text=bundle.alt_text,
            caption=bundle.caption,
            width=gen.width,
            height=gen.height,
            mime_type=gen.mime_type,
            checksum=gen.checksum,
            metadata_json={
                "provider": prov_name,
                "llm_run_id": prompt_result.llm_run_id,
                **(gen.metadata or {}),
            },
        )
        db.add(asset)
        db.flush()

        job.media_asset_id = asset.id
        job.status = "completed"
        job.latency_ms = latency_ms
        job.completed_at = datetime.now(timezone.utc)
        job.response_json = {
            "success": True,
            "storage_path": gen.storage_path,
            "media_asset_id": asset.id,
        }
        db.commit()
        return MediaOperationResult(
            success=True,
            media_asset_id=asset.id,
            media_job_id=job.id,
            warnings=warnings,
        )
    except MediaProviderError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        job.status = "failed"
        job.error_message = str(exc)
        job.latency_ms = latency_ms
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return MediaOperationResult(
            success=False,
            media_job_id=job.id,
            error_message=str(exc),
            warnings=warnings,
        )


def attach_external_media(
    db: Session,
    document_id: int,
    *,
    original_url: str,
    alt_text: str | None = None,
    caption: str | None = None,
    media_type: str = "preview",
) -> MediaOperationResult:
    _require_pipeline()
    document = db.get(ParsedDocument, document_id)
    if not document:
        return MediaOperationResult(success=False, error_message="Document not found")

    job = create_media_job(
        db,
        document_id=document_id,
        job_type="import_external",
        provider="external",
        prompt_text=None,
    )
    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    job.response_json = {"original_url": original_url}

    asset = MediaAsset(
        project_id=job.project_id,
        document_id=document_id,
        revision_id=job.revision_id,
        media_type=media_type,
        source_type="external",
        status="generated",
        original_url=original_url,
        alt_text=alt_text,
        caption=caption,
    )
    db.add(asset)
    db.flush()
    job.media_asset_id = asset.id
    db.commit()
    return MediaOperationResult(success=True, media_asset_id=asset.id, media_job_id=job.id)


def approve_media(db: Session, media_asset_id: int) -> MediaOperationResult:
    _require_pipeline()
    asset = db.get(MediaAsset, media_asset_id)
    if not asset:
        return MediaOperationResult(success=False, error_message="Media asset not found")
    asset.status = "approved"
    db.commit()
    return MediaOperationResult(success=True, media_asset_id=asset.id)


def reject_media(db: Session, media_asset_id: int) -> MediaOperationResult:
    _require_pipeline()
    asset = db.get(MediaAsset, media_asset_id)
    if not asset:
        return MediaOperationResult(success=False, error_message="Media asset not found")
    asset.status = "rejected"
    db.commit()
    return MediaOperationResult(success=True, media_asset_id=asset.id)


def resolve_media_file_path(asset: MediaAsset) -> Path | None:
    if not asset.storage_path:
        return None
    settings = get_settings()
    return settings.media_storage_root / asset.storage_path


def build_preview_public_url(asset_id: int) -> str:
    return f"/api/media/assets/{asset_id}/file"


def build_media_block_for_publish(db: Session, document_id: int) -> dict[str, Any]:
    preview = get_approved_preview_asset(db, document_id)
    if not preview:
        generated = db.scalar(
            select(MediaAsset)
            .where(
                MediaAsset.document_id == document_id,
                MediaAsset.media_type == "preview",
                MediaAsset.status.in_(["generated", "approved"]),
            )
            .order_by(MediaAsset.id.desc())
        )
        preview = generated

    if not preview or preview.status == "rejected":
        return {"preview": None}

    url = preview.original_url
    if preview.storage_path:
        url = build_preview_public_url(preview.id)

    return {
        "preview": {
            "url": url,
            "alt_text": preview.alt_text or "",
            "caption": preview.caption or "",
            "media_asset_id": preview.id,
            "revision_id": preview.revision_id,
            "source_type": preview.source_type,
            "status": preview.status,
        }
    }
