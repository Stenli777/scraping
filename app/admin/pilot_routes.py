"""Admin routes for production pilots."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.pilot_service import (
    PilotServiceError,
    add_document_to_pilot,
    get_pilot_dashboard,
    list_pilots,
    refresh_pilot_status,
    remove_document_from_pilot,
    suggest_pilot_candidates,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/admin/pilots", response_class=HTMLResponse)
def admin_pilots_list(request: Request, db: Session = Depends(get_db)):
    rows = list_pilots(db)
    return templates.TemplateResponse(
        request,
        "pilots.html",
        {"request": request, "rows": rows, "title": "Production pilots"},
    )


@router.get("/admin/pilots/{pilot_id}", response_class=HTMLResponse)
def admin_pilot_detail(pilot_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        dash = get_pilot_dashboard(db, pilot_id)
        candidates = suggest_pilot_candidates(db, dash["pilot"].project_id, limit=10)
    except PilotServiceError:
        return RedirectResponse("/admin/pilots", status_code=302)
    return templates.TemplateResponse(
        request,
        "pilot_detail.html",
        {
            "request": request,
            "dash": dash,
            "candidates": candidates,
            "title": dash["pilot"].name,
        },
    )


@router.post("/admin/pilots/{pilot_id}/add-document")
def admin_pilot_add_document(
    pilot_id: int,
    document_id: int = Form(...),
    priority: int = Form(50),
    db: Session = Depends(get_db),
):
    try:
        add_document_to_pilot(db, pilot_id, document_id, priority=priority)
        db.commit()
    except PilotServiceError:
        pass
    return RedirectResponse(f"/admin/pilots/{pilot_id}", status_code=303)


@router.post("/admin/pilots/{pilot_id}/remove-document")
def admin_pilot_remove_document(
    pilot_id: int,
    document_id: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        remove_document_from_pilot(db, pilot_id, document_id)
        db.commit()
    except PilotServiceError:
        pass
    return RedirectResponse(f"/admin/pilots/{pilot_id}", status_code=303)


@router.post("/admin/pilots/{pilot_id}/refresh")
def admin_pilot_refresh(pilot_id: int, db: Session = Depends(get_db)):
    try:
        refresh_pilot_status(db, pilot_id)
        db.commit()
    except PilotServiceError:
        pass
    return RedirectResponse(f"/admin/pilots/{pilot_id}", status_code=303)
