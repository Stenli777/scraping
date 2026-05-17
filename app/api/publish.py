from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.models.publish_run import PublishRun
from app.models.publish_target import PublishTarget
from app.publishers.exceptions import PublishValidationError
from app.services.publish_readiness_service import get_publish_readiness
from app.services.publish_service import publish_draft_for_document

router = APIRouter(tags=["publish"])


class PublishDraftRequest(BaseModel):
    publish_target_id: int | None = None
    dry_run: bool | None = None
    force: bool = False


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
        "runs": [
            {
                "id": r.id,
                "publish_target_id": r.publish_target_id,
                "status": r.status,
                "dry_run": r.dry_run,
                "force_used": r.force_used,
                "payload_version": r.payload_version,
                "response_status_code": r.response_status_code,
                "external_id": r.external_id,
                "draft_url": r.draft_url,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ],
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
