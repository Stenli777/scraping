from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import ParserType
from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.services.task_service import create_task, get_task, list_tasks

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    tasks = list_tasks(db, limit=50)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"request": request, "tasks": tasks, "title": "Dashboard"},
    )


@router.get("/admin/tasks/new", response_class=HTMLResponse)
def admin_new_task_form(request: Request):
    return templates.TemplateResponse(
        request,
        "task_new.html",
        {
            "request": request,
            "title": "Добавить URL",
            "parser_types": [p.value for p in ParserType],
        },
    )


@router.post("/admin/tasks/new")
def admin_create_task(
    source_url: str = Form(...),
    parser_type: str = Form(ParserType.GENERIC_ARTICLE.value),
    db: Session = Depends(get_db),
):
    task = create_task(db, source_url.strip(), parser_type)
    return RedirectResponse(url=f"/admin/tasks/{task.id}", status_code=303)


@router.get("/admin/tasks/{task_id}", response_class=HTMLResponse)
def admin_task_detail(task_id: int, request: Request, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    if not task:
        return RedirectResponse("/admin", status_code=302)
    logs = sorted(task.logs, key=lambda x: x.created_at)
    return templates.TemplateResponse(
        request,
        "task_detail.html",
        {"request": request, "task": task, "logs": logs, "title": f"Задача #{task_id}"},
    )


@router.get("/admin/documents/{document_id}", response_class=HTMLResponse)
def admin_document_detail(document_id: int, request: Request, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse(
        request,
        "document_detail.html",
        {"request": request, "document": document, "title": f"Документ #{document_id}"},
    )


@router.get("/admin/settings", response_class=HTMLResponse)
def admin_settings(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "title": "Настройки",
            "settings": settings,
        },
    )
