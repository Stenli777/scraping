"""Production pilot API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.pilot_service import (
    PilotServiceError,
    add_document_to_pilot,
    create_pilot,
    get_pilot_dashboard,
    list_pilots,
    refresh_pilot_status,
    suggest_pilot_candidates,
)

router = APIRouter(tags=["pilots"])


class PilotCreateBody(BaseModel):
    project_id: int
    name: str
    slug: str | None = None
    description: str | None = None
    target_count: int = Field(5, ge=1, le=50)
    status: str = "draft"


class AddDocumentBody(BaseModel):
    document_id: int
    priority: int = Field(50, ge=0, le=100)


@router.get("/api/pilots")
def api_list_pilots(project_id: int | None = None, db: Session = Depends(get_db)):
    rows = list_pilots(db, project_id=project_id)
    return {
        "pilots": [
            {
                "id": r["pilot"].id,
                "project_id": r["pilot"].project_id,
                "name": r["pilot"].name,
                "slug": r["pilot"].slug,
                "status": r["pilot"].status,
                "target_count": r["pilot"].target_count,
                "item_count": r["item_count"],
                "done_count": r["done_count"],
                "progress": r["progress"],
            }
            for r in rows
        ]
    }


@router.post("/api/pilots")
def api_create_pilot(body: PilotCreateBody, db: Session = Depends(get_db)):
    try:
        pilot = create_pilot(
            db,
            body.project_id,
            body.name,
            slug=body.slug,
            description=body.description,
            target_count=body.target_count,
            status=body.status,
        )
        db.commit()
    except PilotServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": pilot.id, "slug": pilot.slug, "status": pilot.status}


@router.get("/api/pilots/{pilot_id}")
def api_get_pilot(pilot_id: int, db: Session = Depends(get_db)):
    try:
        dash = get_pilot_dashboard(db, pilot_id)
    except PilotServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    p = dash["pilot"]
    return {
        "id": p.id,
        "project_id": p.project_id,
        "name": p.name,
        "slug": p.slug,
        "status": p.status,
        "target_count": p.target_count,
        "progress": dash["progress"],
        "items": [
            {
                "id": r["item"].id,
                "document_id": r["document_id"],
                "title": r["title"],
                "score": r["score"],
                "status": r["status"],
                "next_action": r["next_action"],
                "blockers": r["blockers"],
                "warnings": r["warnings"],
            }
            for r in dash["item_rows"]
        ],
    }


@router.post("/api/pilots/{pilot_id}/add-document")
def api_add_document(pilot_id: int, body: AddDocumentBody, db: Session = Depends(get_db)):
    try:
        item = add_document_to_pilot(db, pilot_id, body.document_id, priority=body.priority)
        db.commit()
    except PilotServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"item_id": item.id, "status": item.status, "next_action": item.next_action}


@router.post("/api/pilots/{pilot_id}/refresh")
def api_refresh_pilot(pilot_id: int, db: Session = Depends(get_db)):
    try:
        pilot = refresh_pilot_status(db, pilot_id)
        dash = get_pilot_dashboard(db, pilot_id)
        db.commit()
    except PilotServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "pilot_id": pilot.id,
        "status": pilot.status,
        "progress": dash["progress"],
    }


@router.get("/api/pilots/{pilot_id}/candidates")
def api_pilot_candidates(pilot_id: int, limit: int = 10, db: Session = Depends(get_db)):
    from app.models.content_pilot import ContentPilot

    pilot = db.get(ContentPilot, pilot_id)
    if not pilot:
        raise HTTPException(status_code=404, detail="Pilot not found")
    candidates = suggest_pilot_candidates(db, pilot.project_id, limit=min(limit, 50))
    return {"pilot_id": pilot_id, "candidates": candidates}
