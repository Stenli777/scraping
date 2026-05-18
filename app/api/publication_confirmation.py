"""Public publication confirmation API — manual operator boundary."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.publication_confirmation_service import (
    PublicationConfirmationError,
    check_public_visibility,
    confirm_publication,
    get_publication_confirmation_status,
    mark_not_public,
)

router = APIRouter(tags=["publication-confirmation"])


class ConfirmPublicBody(BaseModel):
    confirmed_by: str = "operator"
    notes: str | None = None
    force: bool = False


class MarkNotPublicBody(BaseModel):
    notes: str | None = None


@router.post("/api/publications/{publication_id}/check-public-status")
def api_check_public_status(publication_id: int, db: Session = Depends(get_db)):
    try:
        result = check_public_visibility(db, publication_id)
        db.commit()
        return result
    except PublicationConfirmationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/publications/{publication_id}/public-status")
def api_get_public_status(publication_id: int, db: Session = Depends(get_db)):
    try:
        return get_publication_confirmation_status(db, publication_id)
    except PublicationConfirmationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/publications/{publication_id}/confirm-public")
def api_confirm_public(
    publication_id: int,
    body: ConfirmPublicBody,
    db: Session = Depends(get_db),
):
    try:
        result = confirm_publication(
            db,
            publication_id,
            confirmed_by=body.confirmed_by,
            notes=body.notes,
            force=body.force,
        )
        db.commit()
        return result
    except PublicationConfirmationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/publications/{publication_id}/mark-not-public")
def api_mark_not_public(
    publication_id: int,
    body: MarkNotPublicBody | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = mark_not_public(db, publication_id, notes=body.notes if body else None)
        db.commit()
        return result
    except PublicationConfirmationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
