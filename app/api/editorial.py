"""Editorial workflow API — operator decisions."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.services import editorial_service
from app.services.revision_service import list_revisions

router = APIRouter(prefix="/api/documents", tags=["editorial"])


class EditorialNotesBody(BaseModel):
    notes: str | None = None


def _get_document(db: Session, document_id: int) -> ParsedDocument:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _editorial_response(document: ParsedDocument) -> dict:
    return {
        "document_id": document.id,
        "editorial_status": document.editorial_status,
        "approved_for_publish": document.approved_for_publish,
        "editorial_notes": document.editorial_notes,
        "current_revision_number": document.current_revision_number,
        "operator_approved_at": document.operator_approved_at.isoformat()
        if document.operator_approved_at
        else None,
    }


@router.post("/{document_id}/editorial/approve")
def api_editorial_approve(
    document_id: int, body: EditorialNotesBody | None = None, db: Session = Depends(get_db)
):
    _get_document(db, document_id)
    try:
        doc = editorial_service.approve_document(
            db, document_id, notes=body.notes if body else None
        )
        db.commit()
    except editorial_service.EditorialTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _editorial_response(doc)


@router.post("/{document_id}/editorial/reject")
def api_editorial_reject(
    document_id: int, body: EditorialNotesBody | None = None, db: Session = Depends(get_db)
):
    _get_document(db, document_id)
    try:
        doc = editorial_service.reject_document(
            db, document_id, notes=body.notes if body else None
        )
        db.commit()
    except editorial_service.EditorialTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _editorial_response(doc)


@router.post("/{document_id}/editorial/needs-revision")
def api_editorial_needs_revision(
    document_id: int, body: EditorialNotesBody | None = None, db: Session = Depends(get_db)
):
    _get_document(db, document_id)
    try:
        doc = editorial_service.mark_needs_revision(
            db, document_id, notes=body.notes if body else None
        )
        db.commit()
    except editorial_service.EditorialTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _editorial_response(doc)


@router.post("/{document_id}/editorial/operator-review")
def api_editorial_operator_review(
    document_id: int, body: EditorialNotesBody | None = None, db: Session = Depends(get_db)
):
    _get_document(db, document_id)
    try:
        doc = editorial_service.move_to_operator_review(
            db, document_id, notes=body.notes if body else None
        )
        db.commit()
    except editorial_service.EditorialTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _editorial_response(doc)


@router.post("/{document_id}/editorial/ready-to-publish")
def api_editorial_ready_to_publish(
    document_id: int, body: EditorialNotesBody | None = None, db: Session = Depends(get_db)
):
    _get_document(db, document_id)
    try:
        doc = editorial_service.mark_ready_to_publish(
            db, document_id, notes=body.notes if body else None
        )
        db.commit()
    except editorial_service.EditorialTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _editorial_response(doc)


@router.get("/{document_id}/revisions")
def api_list_revisions(document_id: int, db: Session = Depends(get_db)):
    document = _get_document(db, document_id)
    revisions = list_revisions(db, document_id)
    return {
        "document_id": document_id,
        "current_revision_number": document.current_revision_number,
        "revisions": [
            {
                "id": r.id,
                "revision_number": r.revision_number,
                "source_type": r.source_type,
                "source_reference_id": r.source_reference_id,
                "editorial_status": r.editorial_status,
                "rewrite_preview": (r.rewrite_text or "")[:300],
                "seo_snapshot": r.seo_snapshot_json,
                "quality_snapshot": r.quality_snapshot_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in revisions
        ],
    }
