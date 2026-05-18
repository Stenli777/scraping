"""Draft review feedback API — manual CRMFlow24 post-publish loop."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.draft_feedback_service import (
    DraftFeedbackError,
    check_public_visibility,
    create_feedback,
    feedback_to_dict,
    get_feedback_for_candidate,
    get_feedback_for_publication,
    mark_accepted,
    mark_needs_edits,
    mark_rejected,
)

router = APIRouter(tags=["draft-feedback"])


class DraftFeedbackBody(BaseModel):
    review_status: str = "pending"
    reviewer_name: str | None = None
    notes: str | None = None
    required_changes: list = Field(default_factory=list)
    checked_public_visibility: bool = False
    checked_seo: bool = False
    checked_content: bool = False
    checked_media: bool = False
    apply_editorial_needs_revision: bool = True
    apply_editorial_reject: bool = False


class VisibilityCheckBody(BaseModel):
    feedback_id: int | None = None


@router.post("/api/release-candidates/{candidate_id}/draft-feedback")
def api_post_candidate_draft_feedback(
    candidate_id: int,
    body: DraftFeedbackBody,
    db: Session = Depends(get_db),
):
    try:
        fb = create_feedback(
            db,
            release_candidate_id=candidate_id,
            review_status=body.review_status,
            reviewer_name=body.reviewer_name,
            notes=body.notes,
            required_changes=body.required_changes,
            checked_public_visibility=body.checked_public_visibility,
            checked_seo=body.checked_seo,
            checked_content=body.checked_content,
            checked_media=body.checked_media,
            apply_editorial_needs_revision=body.apply_editorial_needs_revision,
            apply_editorial_reject=body.apply_editorial_reject,
        )
        db.commit()
        return feedback_to_dict(fb)
    except DraftFeedbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/release-candidates/{candidate_id}/draft-feedback")
def api_get_candidate_draft_feedback(candidate_id: int, db: Session = Depends(get_db)):
    return {"items": get_feedback_for_candidate(db, candidate_id)}


@router.post("/api/publications/{publication_id}/draft-feedback")
def api_post_publication_draft_feedback(
    publication_id: int,
    body: DraftFeedbackBody,
    db: Session = Depends(get_db),
):
    try:
        fb = create_feedback(
            db,
            publication_record_id=publication_id,
            review_status=body.review_status,
            reviewer_name=body.reviewer_name,
            notes=body.notes,
            required_changes=body.required_changes,
            checked_public_visibility=body.checked_public_visibility,
            checked_seo=body.checked_seo,
            checked_content=body.checked_content,
            checked_media=body.checked_media,
            apply_editorial_needs_revision=body.apply_editorial_needs_revision,
            apply_editorial_reject=body.apply_editorial_reject,
        )
        db.commit()
        return feedback_to_dict(fb)
    except DraftFeedbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/publications/{publication_id}/draft-feedback")
def api_get_publication_draft_feedback(publication_id: int, db: Session = Depends(get_db)):
    return {"items": get_feedback_for_publication(db, publication_id)}


@router.post("/api/publications/{publication_id}/check-public-visibility")
def api_check_public_visibility(
    publication_id: int,
    body: VisibilityCheckBody | None = None,
    db: Session = Depends(get_db),
):
    try:
        feedback_id = body.feedback_id if body else None
        result = check_public_visibility(
            db,
            publication_id,
            save_to_feedback_id=feedback_id,
        )
        db.commit()
        paths = result.get("paths") or {}
        return {
            "publication_id": publication_id,
            "checked_at": result.get("checked_at"),
            "visible_in_blog": bool((paths.get("/blog") or {}).get("visible")),
            "visible_in_sitemap": bool((paths.get("/sitemap.xml") or {}).get("visible")),
            "visible_in_rss": bool((paths.get("/rss.xml") or {}).get("visible")),
            "visible_anywhere": result.get("visible_anywhere"),
            "detail": result,
        }
    except DraftFeedbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
