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
from app.models.discovered_url import DiscoveredUrl
from app.models.publish_run import PublishRun
from app.models.publish_target import PublishTarget
from app.models.source_directory import SourceDirectory
from app.models.review_result import ReviewResult
from app.models.seo_metadata import SeoMetadata
from app.services.llm_tasks import execute_rewrite
from app.services.project_profile_service import resolve_task_project
from app.services.discovery_service import (
    enqueue_discovered_url,
    ignore_discovered_url,
    run_discovery,
)
from app.services.publish_service import publish_draft_for_document
from app.services.review_service import run_review_for_document
from app.services.rewrite_service import rerun_rewrite_for_document
from app.services.seo_service import run_seo_for_document
from app.services.admin_context_service import load_document_context, load_task_context
from app.services.operations_service import get_dashboard_stats, get_failed_items, list_stale_running_tasks
from app.services.pipeline_summary_service import build_pipeline_summary
from app.services.publish_readiness_service import get_publish_readiness
from app.services.task_service import (
    create_task,
    get_task,
    list_tasks,
    mark_task_skipped,
    reset_stale_running_task,
)

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    stats = get_dashboard_stats(db)
    recent_tasks = list_tasks(db, limit=15)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "recent_tasks": recent_tasks,
            "title": "Dashboard",
        },
    )


@router.get("/admin/failed-items", response_class=HTMLResponse)
def admin_failed_items(request: Request, db: Session = Depends(get_db)):
    items = get_failed_items(db)
    stale = list_stale_running_tasks(db)
    return templates.TemplateResponse(
        request,
        "failed_items.html",
        {
            "request": request,
            "items": items,
            "stale_tasks": stale,
            "title": "Failed Items",
        },
    )


@router.post("/admin/tasks/{task_id}/mark-skipped")
def admin_mark_task_skipped(task_id: int, db: Session = Depends(get_db)):
    mark_task_skipped(db, task_id)
    return RedirectResponse(f"/admin/tasks/{task_id}", status_code=303)


@router.post("/admin/tasks/{task_id}/reset-stale")
def admin_reset_stale_task(task_id: int, db: Session = Depends(get_db)):
    reset_stale_running_task(db, task_id)
    return RedirectResponse(f"/admin/failed-items", status_code=303)


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
    ctx = load_task_context(db, task)
    document = task.document
    meta = (document.metadata_json or {}) if document else {}
    review_meta = meta.get("review") or {}
    rewrite_meta = meta.get("rewrite") or {}
    seo_record = ctx.get("seo_record")
    pipeline_summary = build_pipeline_summary(db, task, document)
    publish_readiness = (
        get_publish_readiness(db, document.id) if document else None
    )
    return templates.TemplateResponse(
        request,
        "task_detail.html",
        {
            "request": request,
            "task": task,
            "logs": logs,
            "review_meta": review_meta,
            "rewrite_meta": rewrite_meta,
            "seo_record": seo_record,
            "pipeline_summary": pipeline_summary,
            "publish_readiness": publish_readiness,
            "feature_flags": all_flags(),
            "settings": get_settings(),
            "title": f"Задача #{task_id}",
            **ctx,
        },
    )


@router.get("/admin/documents/{document_id}", response_class=HTMLResponse)
def admin_document_detail(document_id: int, request: Request, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        return RedirectResponse("/admin", status_code=302)
    meta = document.metadata_json or {}
    review_meta = meta.get("review") or {}
    rewrite_meta = meta.get("rewrite") or {}
    seo_record = (
        db.query(SeoMetadata)
        .filter(SeoMetadata.document_id == document_id)
        .order_by(SeoMetadata.id.desc())
        .first()
    )
    publish_targets = []
    publish_runs = []
    if document.task:
        project = resolve_task_project(db, document.task)
        if project:
            publish_targets = (
                db.query(PublishTarget)
                .filter(PublishTarget.project_id == project.id)
                .order_by(PublishTarget.id.asc())
                .all()
            )
    publish_runs = (
        db.query(PublishRun)
        .filter(PublishRun.document_id == document_id)
        .order_by(PublishRun.id.desc())
        .limit(20)
        .all()
    )
    ctx = load_document_context(db, document)
    task = document.task
    pipeline_summary = (
        build_pipeline_summary(db, task, document) if task else None
    )
    publish_readiness = get_publish_readiness(db, document_id)
    return templates.TemplateResponse(
        request,
        "document_detail.html",
        {
            "request": request,
            "document": document,
            "review_meta": review_meta,
            "rewrite_meta": rewrite_meta,
            "seo_record": seo_record,
            "publish_targets": publish_targets,
            "publish_runs": publish_runs,
            "publish_readiness": publish_readiness,
            "pipeline_summary": pipeline_summary,
            "feature_flags": all_flags(),
            "settings": get_settings(),
            "title": f"Документ #{document_id}",
            **ctx,
        },
    )


@router.post("/admin/documents/{document_id}/rerun-rewrite")
def admin_rerun_rewrite(document_id: int, db: Session = Depends(get_db)):
    rerun_rewrite_for_document(db, document_id)
    return RedirectResponse(f"/admin/documents/{document_id}", status_code=303)


@router.post("/admin/documents/{document_id}/run-review")
def admin_run_review(document_id: int, db: Session = Depends(get_db)):
    run_review_for_document(db, document_id)
    return RedirectResponse(f"/admin/documents/{document_id}", status_code=303)


@router.post("/admin/documents/{document_id}/run-seo")
def admin_run_seo(document_id: int, db: Session = Depends(get_db)):
    run_seo_for_document(db, document_id)
    return RedirectResponse(f"/admin/documents/{document_id}", status_code=303)


@router.post("/admin/documents/{document_id}/publish-draft")
def admin_publish_draft(
    document_id: int,
    publish_target_id: int = Form(...),
    dry_run: str | None = Form(None),
    db: Session = Depends(get_db),
):
    publish_draft_for_document(
        db,
        document_id,
        publish_target_id=publish_target_id,
        dry_run=dry_run == "on",
    )
    return RedirectResponse(f"/admin/documents/{document_id}", status_code=303)


@router.get("/admin/publish-targets", response_class=HTMLResponse)
def admin_publish_targets(request: Request, db: Session = Depends(get_db)):
    targets = db.query(PublishTarget).order_by(PublishTarget.id.asc()).all()
    return templates.TemplateResponse(
        request,
        "publish_targets.html",
        {"request": request, "targets": targets, "title": "Publish Targets"},
    )


@router.get("/admin/publish-runs", response_class=HTMLResponse)
def admin_publish_runs(request: Request, db: Session = Depends(get_db)):
    runs = db.query(PublishRun).order_by(PublishRun.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "publish_runs.html",
        {"request": request, "runs": runs, "title": "Publish Runs"},
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


@router.get("/admin/projects/{project_id}", response_class=HTMLResponse)
def admin_project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/admin/projects", status_code=302)
    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {"request": request, "project": project, "title": f"Project {project.slug}"},
    )


@router.get("/admin/review-queue", response_class=HTMLResponse)
def admin_review_queue(request: Request, db: Session = Depends(get_db)):
    reviews = db.query(ReviewResult).order_by(ReviewResult.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "review_queue.html",
        {"request": request, "reviews": reviews, "title": "Review Queue"},
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


@router.get("/admin/source-directories", response_class=HTMLResponse)
def admin_source_directories(request: Request, db: Session = Depends(get_db)):
    directories = db.query(SourceDirectory).order_by(SourceDirectory.id.asc()).all()
    return templates.TemplateResponse(
        request,
        "source_directories.html",
        {"request": request, "directories": directories, "title": "Source Directories"},
    )


@router.get("/admin/source-directories/{directory_id}", response_class=HTMLResponse)
def admin_source_directory_detail(
    directory_id: int, request: Request, db: Session = Depends(get_db)
):
    directory = db.get(SourceDirectory, directory_id)
    if not directory:
        return RedirectResponse("/admin/source-directories", status_code=302)
    return templates.TemplateResponse(
        request,
        "source_directory_detail.html",
        {
            "request": request,
            "directory": directory,
            "feature_flags": all_flags(),
            "title": f"Source: {directory.name}",
        },
    )


@router.post("/admin/source-directories/{directory_id}/discover")
def admin_run_discovery(directory_id: int, db: Session = Depends(get_db)):
    run_discovery(db, directory_id)
    return RedirectResponse(f"/admin/source-directories/{directory_id}", status_code=303)


@router.get("/admin/discovered-urls", response_class=HTMLResponse)
def admin_discovered_urls(
    request: Request,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(DiscoveredUrl).order_by(DiscoveredUrl.id.desc()).limit(200)
    if status:
        q = q.filter(DiscoveredUrl.status == status)
    urls = q.limit(200).all()
    projects = {p.id: p for p in db.query(Project).all()}
    directories = {d.id: d for d in db.query(SourceDirectory).all()}
    return templates.TemplateResponse(
        request,
        "discovered_urls.html",
        {
            "request": request,
            "urls": urls,
            "filter_status": status,
            "projects": projects,
            "directories": directories,
            "title": "Discovered URLs",
        },
    )


@router.post("/admin/discovered-urls/{discovered_url_id}/enqueue")
def admin_enqueue_discovered(discovered_url_id: int, db: Session = Depends(get_db)):
    record = enqueue_discovered_url(db, discovered_url_id)
    if record.existing_task_id:
        return RedirectResponse(f"/admin/tasks/{record.existing_task_id}", status_code=303)
    return RedirectResponse("/admin/discovered-urls", status_code=303)


@router.post("/admin/discovered-urls/{discovered_url_id}/ignore")
def admin_ignore_discovered(discovered_url_id: int, db: Session = Depends(get_db)):
    ignore_discovered_url(db, discovered_url_id)
    return RedirectResponse("/admin/discovered-urls", status_code=303)


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
