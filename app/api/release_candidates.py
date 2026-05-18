from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.services.release_candidate_service import (
    ReleaseCandidateError,
    approve_release_candidate,
    build_payload_preview,
    create_release_candidate,
    get_candidate_status,
    list_release_candidates_for_document,
    publish_draft_from_candidate,
    reject_release_candidate,
    run_release_qa,
)

router = APIRouter(tags=["release-candidates"])


class CreateReleaseCandidateBody(BaseModel):
    revision_id: int | None = None
    publish_target_id: int | None = None
    notes: str | None = None


class RejectBody(BaseModel):
    reason: str


class ApproveBody(BaseModel):
    notes: str | None = None


@router.post("/api/documents/{document_id}/release-candidates")
def api_create_release_candidate(
    document_id: int,
    body: CreateReleaseCandidateBody | None = None,
    db: Session = Depends(get_db),
):
    if not db.get(ParsedDocument, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        candidate = create_release_candidate(
            db,
            document_id,
            revision_id=body.revision_id if body else None,
            publish_target_id=body.publish_target_id if body else None,
            notes=body.notes if body else None,
        )
        db.commit()
        return get_candidate_status(db, candidate.id)
    except ReleaseCandidateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/documents/{document_id}/release-candidates")
def api_list_document_release_candidates(document_id: int, db: Session = Depends(get_db)):
    if not db.get(ParsedDocument, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"candidates": list_release_candidates_for_document(db, document_id)}


@router.get("/api/release-candidates/{candidate_id}")
def api_get_release_candidate(candidate_id: int, db: Session = Depends(get_db)):
    try:
        return get_candidate_status(db, candidate_id)
    except ReleaseCandidateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/release-candidates/{candidate_id}/run-qa")
def api_run_release_qa(candidate_id: int, db: Session = Depends(get_db)):
    try:
        result = run_release_qa(db, candidate_id)
        db.commit()
        return result
    except ReleaseCandidateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/release-candidates/{candidate_id}/approve")
def api_approve_release_candidate(
    candidate_id: int,
    body: ApproveBody | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = approve_release_candidate(db, candidate_id, notes=body.notes if body else None)
        db.commit()
        return result
    except ReleaseCandidateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/release-candidates/{candidate_id}/reject")
def api_reject_release_candidate(
    candidate_id: int,
    body: RejectBody,
    db: Session = Depends(get_db),
):
    try:
        result = reject_release_candidate(db, candidate_id, body.reason)
        db.commit()
        return result
    except ReleaseCandidateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/release-candidates/{candidate_id}/publish-draft")
def api_publish_draft_from_candidate(candidate_id: int, db: Session = Depends(get_db)):
    try:
        result = publish_draft_from_candidate(db, candidate_id)
        db.commit()
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error_message") or "Publish failed")
        return result
    except ReleaseCandidateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/release-candidates/{candidate_id}/payload-preview")
def api_payload_preview(candidate_id: int, db: Session = Depends(get_db)):
    try:
        return build_payload_preview(db, candidate_id)
    except ReleaseCandidateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
