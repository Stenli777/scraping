"""Admin UI for manual URL intake."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.source_directory import SourceDirectory
from app.services.manual_url_intake_service import intake_manual_url, intake_manual_urls_bulk

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/admin/manual-urls", response_class=HTMLResponse)
def admin_manual_urls(request: Request, db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.id.asc()).all()
    directories = db.query(SourceDirectory).order_by(SourceDirectory.id.asc()).all()
    return templates.TemplateResponse(
        request,
        "manual_urls.html",
        {"projects": projects, "directories": directories, "results": None},
    )


@router.post("/admin/manual-urls", response_class=HTMLResponse)
def admin_manual_urls_submit(
    request: Request,
    project_id: int = Form(...),
    urls_text: str = Form(""),
    source_directory_id: int | None = Form(None),
    enqueue: bool = Form(False),
    db: Session = Depends(get_db),
):
    projects = db.query(Project).order_by(Project.id.asc()).all()
    directories = db.query(SourceDirectory).order_by(SourceDirectory.id.asc()).all()
    lines = [ln.strip() for ln in (urls_text or "").splitlines() if ln.strip()]
    results = []
    if lines:
        if len(lines) == 1:
            try:
                r = intake_manual_url(
                    db,
                    project_id=project_id,
                    url=lines[0],
                    source_directory_id=source_directory_id or None,
                    score_quality=True,
                    enqueue=enqueue,
                )
                results = [r]
            except ValueError as exc:
                results = []
                request.state.flash = str(exc)
        else:
            results = intake_manual_urls_bulk(
                db,
                project_id=project_id,
                urls=lines,
                source_directory_id=source_directory_id or None,
                score_quality=True,
                enqueue=enqueue,
            )
        db.commit()
    return templates.TemplateResponse(
        request,
        "manual_urls.html",
        {
            "projects": projects,
            "directories": directories,
            "results": results,
            "selected_project_id": project_id,
            "selected_directory_id": source_directory_id,
        },
    )
