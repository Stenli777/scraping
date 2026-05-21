from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.models.document_revision import DocumentRevision
from app.models.publish_run import PublishRun
from app.models.publish_target import PublishTarget
from app.publishers.exceptions import PublishValidationError
from app.services.publish_readiness_service import get_publish_readiness
from app.services.publish_retry_service import (
    get_retry_chain,
    is_retryable_publish_run,
    retry_publish_run,
)
from app.services.publish_service import publish_draft_for_document
from app.services.publish_target_health_service import check_all_publish_targets_health

router = APIRouter(tags=["publish"])


class PublishDraftRequest(BaseModel):
    publish_target_id: int | None = None
    dry_run: bool | None = None
    force: bool = False
    force_reason: str | None = None


def _serialize_publish_run(db: Session, r: PublishRun) -> dict:
    rev_no = None
    if r.document_revision_id:
        rev = db.get(DocumentRevision, r.document_revision_id)
        rev_no = rev.revision_number if rev else None
    return {
        "id": r.id,
        "publish_target_id": r.publish_target_id,
        "document_revision_id": r.document_revision_id,
        "revision_number": rev_no,
        "status": r.status,
        "dry_run": r.dry_run,
        "force_used": r.force_used,
        "force_reason": r.force_reason,
        "payload_version": r.payload_version,
        "response_schema_version": r.response_schema_version,
        "response_status_code": r.response_status_code,
        "external_id": r.external_id,
        "draft_url": r.draft_url,
        "remote_status": r.remote_status,
        "error_message": r.error_message,
        "retry_parent_publish_run_id": r.retry_parent_publish_run_id,
        "retry_count": r.retry_count,
        "next_retry_at": r.next_retry_at.isoformat() if r.next_retry_at else None,
        "last_retry_error": r.last_retry_error,
        "retryable": is_retryable_publish_run(r),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/api/publish-targets")
def list_publish_targets(db: Session = Depends(get_db)):
    targets = (
        db.query(PublishTarget)
        .filter(PublishTarget.enabled.is_(True))
        .order_by(PublishTarget.id.asc())
        .all()
    )
    return {
        "targets": [
            {
                "id": t.id,
                "project_id": t.project_id,
                "name": t.name,
                "target_type": t.target_type,
                "endpoint_url": t.endpoint_url,
                "dry_run": t.dry_run,
                "default_status": t.default_status,
                "payload_format": t.payload_format,
            }
            for t in targets
        ]
    }


@router.get("/api/publish-targets/health")
def publish_targets_health(db: Session = Depends(get_db)):
    return check_all_publish_targets_health(db)


@router.get("/api/publish-runs/{publish_run_id}")
def get_publish_run(publish_run_id: int, db: Session = Depends(get_db)):
    run = db.get(PublishRun, publish_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Publish run not found")
    chain = get_retry_chain(db, publish_run_id)
    return {
        "run": _serialize_publish_run(db, run),
        "retry_chain": [_serialize_publish_run(db, c) for c in chain],
    }


@router.post("/api/publish-runs/{publish_run_id}/retry")
def api_retry_publish_run(publish_run_id: int, db: Session = Depends(get_db)):
    try:
        result = retry_publish_run(db, publish_run_id)
    except PublishValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result.success and not result.new_publish_run_id:
        raise HTTPException(
            status_code=400,
            detail=result.error_message or "Retry not allowed",
        )

    chain = []
    if result.new_publish_run_id:
        chain = [
            _serialize_publish_run(db, c)
            for c in get_retry_chain(db, result.new_publish_run_id)
        ]

    return {
        "success": result.success,
        "parent_publish_run_id": result.parent_publish_run_id,
        "new_publish_run_id": result.new_publish_run_id,
        "error_message": result.error_message,
        "retry_chain": chain,
    }


@router.get("/api/documents/{document_id}/publish-runs")
def list_document_publish_runs(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    runs = (
        db.query(PublishRun)
        .filter(PublishRun.document_id == document_id)
        .order_by(PublishRun.id.desc())
        .limit(50)
        .all()
    )
    return {
        "document_id": document_id,
        "runs": [_serialize_publish_run(db, r) for r in runs],
    }


@router.post("/api/documents/{document_id}/publish-draft")
def api_publish_draft(
    document_id: int,
    body: PublishDraftRequest | None = None,
    db: Session = Depends(get_db),
):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    payload = body or PublishDraftRequest()

    if payload.force and not (payload.force_reason or "").strip():
        raise HTTPException(
            status_code=400,
            detail="force=true requires non-empty force_reason",
        )

    if not payload.force:
        readiness = get_publish_readiness(
            db, document_id, publish_target_id=payload.publish_target_id
        )
        if not readiness["ready"]:
            raise HTTPException(
                status_code=400,
                detail={"message": "Document not ready to publish", **readiness},
            )

    try:
        result = publish_draft_for_document(
            db,
            document_id,
            publish_target_id=payload.publish_target_id,
            dry_run=payload.dry_run,
            force=payload.force,
            force_reason=payload.force_reason,
        )
    except PublishValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": result.error_message,
                "existing_publish_run_id": result.existing_publish_run_id,
            },
        )

    if result.validation_error:
        raise HTTPException(status_code=400, detail=result.error_message)

    status_code = 200 if result.success else 502
    return {
        "success": result.success,
        "publish_run_id": result.publish_run_id,
        "status": result.status,
        "dry_run": result.dry_run,
        "force": payload.force,
        "force_reason": payload.force_reason if payload.force else None,
        "external_id": result.external_id,
        "draft_url": result.draft_url,
        "error_message": result.error_message,
        "payload_preview": {
            "payload_version": result.payload.get("payload_version"),
            "title": result.payload.get("title"),
            "slug": result.payload.get("slug"),
            "project_slug": result.payload.get("project_slug"),
        },
    }
