from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import ParserType
from app.core.feature_flags import all_flags
from app.db.session import get_db
from app.llm.routing import list_aliases
from app.llm.schemas import RewriteRequest
from app.models.llm_run import LLMRun
from app.models.parsed_document import ParsedDocument
from app.models.pipeline_event import PipelineEvent
from app.models.project import Project
from app.services.llm_tasks import execute_rewrite
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
            "feature_flags": all_flags(),
        },
    )


@router.get("/admin/projects", response_class=HTMLResponse)
def admin_projects(request: Request, db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "projects.html",
        {"request": request, "projects": projects, "title": "Projects"},
    )


@router.get("/admin/llm-runs", response_class=HTMLResponse)
def admin_llm_runs(request: Request, db: Session = Depends(get_db)):
    runs = db.query(LLMRun).order_by(LLMRun.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "llm_runs.html",
        {"request": request, "runs": runs, "title": "LLM Runs"},
    )


@router.get("/admin/pipeline-events", response_class=HTMLResponse)
def admin_pipeline_events(request: Request, db: Session = Depends(get_db)):
    events = db.query(PipelineEvent).order_by(PipelineEvent.id.desc()).limit(200).all()
    return templates.TemplateResponse(
        request,
        "pipeline_events.html",
        {"request": request, "events": events, "title": "Pipeline Events"},
    )


@router.get("/admin/llm/smoke", response_class=HTMLResponse)
def admin_llm_smoke_form(request: Request):
    return templates.TemplateResponse(
        request,
        "llm_smoke.html",
        {
            "request": request,
            "title": "LLM Smoke Test",
            "aliases": list_aliases(),
            "result": None,
        },
    )


@router.post("/admin/llm/smoke", response_class=HTMLResponse)
def admin_llm_smoke_run(
    request: Request,
    model_alias: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    response = execute_rewrite(
        db,
        RewriteRequest(content=content, model_alias=model_alias, metadata={"smoke_test": True}),
    )
    return templates.TemplateResponse(
        request,
        "llm_smoke.html",
        {
            "request": request,
            "title": "LLM Smoke Test",
            "aliases": list_aliases(),
            "result": response,
            "model_alias": model_alias,
            "content": content,
        },
    )
