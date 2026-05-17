"""Media pipeline API — optional manual preview workflow."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_media_pipeline_enabled
from app.db.session import get_db
from app.media.exceptions import MediaDisabledError, MediaGenerationDisabledError
from app.models.media_asset import MediaAsset
from app.models.media_job import MediaJob
from app.models.parsed_document import ParsedDocument
from app.services.media_service import (
    approve_media,
    build_preview_public_url,
    list_document_media,
    reject_media,
    resolve_media_file_path,
    run_preview_generation,
)

router = APIRouter(tags=["media"])


class MediaGenerateBody(BaseModel):
    provider: str | None = "placeholder"
    use_llm_prompt: bool = True


@router.get("/api/documents/{document_id}/media")
def api_document_media(document_id: int, db: Session = Depends(get_db)):
    if not is_media_pipeline_enabled():
        raise HTTPException(status_code=503, detail="Media pipeline disabled")
    if not db.get(ParsedDocument, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    assets = list_document_media(db, document_id)
    return {
        "assets": [
            {
                "id": a.id,
                "media_type": a.media_type,
                "source_type": a.source_type,
                "status": a.status,
                "storage_path": a.storage_path,
                "original_url": a.original_url,
                "prompt_text": (a.prompt_text or "")[:200],
                "alt_text": a.alt_text,
                "caption": a.caption,
                "revision_id": a.revision_id,
                "file_url": build_preview_public_url(a.id) if a.storage_path else a.original_url,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assets
        ]
    }


@router.post("/api/documents/{document_id}/media/generate-preview")
def api_generate_preview(
    document_id: int,
    body: MediaGenerateBody | None = None,
    db: Session = Depends(get_db),
):
    if not is_media_pipeline_enabled():
        raise HTTPException(status_code=503, detail="Media pipeline disabled")
    if not db.get(ParsedDocument, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = run_preview_generation(
            db,
            document_id,
            provider=body.provider if body else "placeholder",
            use_llm_prompt=body.use_llm_prompt if body else True,
        )
    except MediaGenerationDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MediaDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=result.error_message or "Preview generation failed",
        )
    return {
        "success": True,
        "media_asset_id": result.media_asset_id,
        "media_job_id": result.media_job_id,
        "warnings": result.warnings,
    }


@router.post("/api/media/{media_asset_id}/approve")
def api_approve_media(media_asset_id: int, db: Session = Depends(get_db)):
    if not is_media_pipeline_enabled():
        raise HTTPException(status_code=503, detail="Media pipeline disabled")
    try:
        result = approve_media(db, media_asset_id)
    except MediaDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error_message)
    return {"success": True, "media_asset_id": result.media_asset_id}


@router.post("/api/media/{media_asset_id}/reject")
def api_reject_media(media_asset_id: int, db: Session = Depends(get_db)):
    if not is_media_pipeline_enabled():
        raise HTTPException(status_code=503, detail="Media pipeline disabled")
    try:
        result = reject_media(db, media_asset_id)
    except MediaDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error_message)
    return {"success": True, "media_asset_id": result.media_asset_id}


@router.get("/api/media-jobs")
def api_media_jobs(
    document_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    if not is_media_pipeline_enabled():
        raise HTTPException(status_code=503, detail="Media pipeline disabled")
    q = select(MediaJob).order_by(MediaJob.id.desc()).limit(min(limit, 200))
    if document_id is not None:
        q = q.where(MediaJob.document_id == document_id)
    jobs = db.scalars(q).all()
    return {
        "jobs": [
            {
                "id": j.id,
                "document_id": j.document_id,
                "revision_id": j.revision_id,
                "media_asset_id": j.media_asset_id,
                "job_type": j.job_type,
                "provider": j.provider,
                "status": j.status,
                "latency_ms": j.latency_ms,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
    }


@router.get("/api/media/assets/{media_asset_id}/file")
def api_media_file(media_asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(MediaAsset, media_asset_id)
    if not asset or not asset.storage_path:
        raise HTTPException(status_code=404, detail="Media file not found")
    path = resolve_media_file_path(asset)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Media file missing on disk")
    return FileResponse(path, media_type=asset.mime_type or "application/octet-stream")
