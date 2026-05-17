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
from app.models.content_quality_score import ContentQualityScore
from app.models.publication_record import PublicationRecord
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.content_performance import ContentPerformance
from app.services.analytics_service import summarize_project_metrics
from app.services.editorial_insights_service import (
    content_aging_signals,
    low_performing_content,
    top_performing_content,
)
from app.models.llm_run import LLMRun
from app.models.prompt_template import PromptTemplate
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
from app.services.operations_context_service import build_operations_context
from app.services.pipeline_summary_service import build_pipeline_summary
from app.models.document_revision import DocumentRevision
from app.services import editorial_service
from app.services.editorial_queue_service import list_editorial_queue
from app.services.revision_service import list_revisions
from app.services.timeline_service import build_document_timeline
from app.services.prompt_service import (
    activate_prompt_version,
    create_prompt_version,
    get_active_prompt,
    list_prompt_versions,
)
from app.services.publish_readiness_service import get_publish_readiness
from app.services.quality_service import get_latest_quality_score, run_quality_for_document
from app.hermes.health import check_hermes_health
from app.hermes.routing import list_hermes_aliases
from app.models.hermes_run import HermesRun
from app.models.media_asset import MediaAsset
from app.models.media_job import MediaJob
from app.services.media_service import (
    approve_media,
    list_document_media,
    reject_media,
    run_preview_generation,
)
from app.media.exceptions import MediaDisabledError
from app.services.hermes_service import (
    get_latest_hermes_result,
    run_research_summary,
    run_rewrite_critique,
)
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
    publish_revision_numbers: dict[int, int | None] = {}
    for run in publish_runs:
        if run.document_revision_id:
            rev = db.get(DocumentRevision, run.document_revision_id)
            publish_revision_numbers[run.id] = rev.revision_number if rev else None
    ctx = load_document_context(db, document)
    task = document.task
    pipeline_summary = (
        build_pipeline_summary(db, task, document) if task else None
    )
    publish_readiness = get_publish_readiness(db, document_id)
    quality_record = get_latest_quality_score(db, document_id)
    hermes_research = get_latest_hermes_result(db, document_id, "research_summary")
    hermes_critique = get_latest_hermes_result(db, document_id, "rewrite_critique")
    media_assets = list_document_media(db, document_id) if all_flags().get("ENABLE_MEDIA_PIPELINE") else []
    preview_media = next((a for a in media_assets if a.media_type == "preview"), None)
    doc_publication = None
    doc_performance = None
    doc_analytics_snapshots = []
    if all_flags().get("ENABLE_ANALYTICS"):
        doc_publication = (
            db.query(PublicationRecord)
            .filter(PublicationRecord.document_id == document_id)
            .order_by(PublicationRecord.id.desc())
            .first()
        )
        if doc_publication:
            doc_performance = db.query(ContentPerformance).filter(
                ContentPerformance.publication_record_id == doc_publication.id
            ).first()
            doc_analytics_snapshots = (
                db.query(AnalyticsSnapshot)
                .filter(AnalyticsSnapshot.publication_record_id == doc_publication.id)
                .order_by(AnalyticsSnapshot.snapshot_date.desc())
                .limit(5)
                .all()
            )
    timeline = build_document_timeline(db, document)
    revision_count = document.current_revision_number or 0
    return templates.TemplateResponse(
        request,
        "document_detail.html",
        {
            "request": request,
            "document": document,
            "review_meta": review_meta,
            "rewrite_meta": rewrite_meta,
            "seo_record": seo_record,
            "quality_record": quality_record,
            "hermes_research": hermes_research,
            "hermes_critique": hermes_critique,
            "media_assets": media_assets,
            "preview_media": preview_media,
            "doc_publication": doc_publication,
            "doc_performance": doc_performance,
            "doc_analytics_snapshots": doc_analytics_snapshots,
            "publish_targets": publish_targets,
            "publish_runs": publish_runs,
            "publish_revision_numbers": publish_revision_numbers,
            "publish_readiness": publish_readiness,
            "pipeline_summary": pipeline_summary,
            "timeline": timeline,
            "revision_count": revision_count,
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


@router.post("/admin/documents/{document_id}/run-quality")
def admin_run_quality(document_id: int, db: Session = Depends(get_db)):
    run_quality_for_document(db, document_id)
    return RedirectResponse(f"/admin/documents/{document_id}#quality", status_code=303)


@router.post("/admin/documents/{document_id}/hermes/research")
def admin_hermes_research(document_id: int, db: Session = Depends(get_db)):
    run_research_summary(db, document_id)
    return RedirectResponse(f"/admin/documents/{document_id}#hermes", status_code=303)


@router.post("/admin/documents/{document_id}/hermes/critique")
def admin_hermes_critique(document_id: int, db: Session = Depends(get_db)):
    run_rewrite_critique(db, document_id)
    return RedirectResponse(f"/admin/documents/{document_id}#hermes", status_code=303)


@router.post("/admin/documents/{document_id}/editorial/operator-review")
def admin_editorial_operator_review(document_id: int, db: Session = Depends(get_db)):
    editorial_service.move_to_operator_review(db, document_id)
    db.commit()
    return RedirectResponse(f"/admin/documents/{document_id}#editorial", status_code=303)


@router.post("/admin/documents/{document_id}/editorial/needs-revision")
def admin_editorial_needs_revision(document_id: int, db: Session = Depends(get_db)):
    editorial_service.mark_needs_revision(db, document_id)
    db.commit()
    return RedirectResponse(f"/admin/documents/{document_id}#editorial", status_code=303)


@router.post("/admin/documents/{document_id}/editorial/approve")
def admin_editorial_approve(document_id: int, db: Session = Depends(get_db)):
    editorial_service.approve_document(db, document_id)
    db.commit()
    return RedirectResponse(f"/admin/documents/{document_id}#editorial", status_code=303)


@router.post("/admin/documents/{document_id}/editorial/reject")
def admin_editorial_reject(document_id: int, db: Session = Depends(get_db)):
    editorial_service.reject_document(db, document_id)
    db.commit()
    return RedirectResponse(f"/admin/documents/{document_id}#editorial", status_code=303)


@router.post("/admin/documents/{document_id}/editorial/ready-to-publish")
def admin_editorial_ready(document_id: int, db: Session = Depends(get_db)):
    editorial_service.mark_ready_to_publish(db, document_id)
    db.commit()
    return RedirectResponse(f"/admin/documents/{document_id}#editorial", status_code=303)


@router.get("/admin/documents/{document_id}/revisions", response_class=HTMLResponse)
def admin_document_revisions(document_id: int, request: Request, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        return RedirectResponse("/admin", status_code=302)
    revisions = list_revisions(db, document_id)
    rev_publish = {}
    for rev in revisions:
        runs = (
            db.query(PublishRun)
            .filter(PublishRun.document_revision_id == rev.id)
            .order_by(PublishRun.id.desc())
            .all()
        )
        rev_publish[rev.id] = runs
    return templates.TemplateResponse(
        request,
        "document_revisions.html",
        {
            "request": request,
            "document": document,
            "revisions": revisions,
            "rev_publish": rev_publish,
            "title": f"Revisions — doc #{document_id}",
        },
    )


@router.post("/admin/documents/{document_id}/publish-draft")
def admin_publish_draft(
    document_id: int,
    publish_target_id: int = Form(...),
    dry_run: str | None = Form(None),
    force: str | None = Form(None),
    db: Session = Depends(get_db),
):
    publish_draft_for_document(
        db,
        document_id,
        publish_target_id=publish_target_id,
        dry_run=dry_run == "on",
        force=force == "on",
    )
    return RedirectResponse(f"/admin/documents/{document_id}#publish", status_code=303)


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


@router.get("/admin/prompts", response_class=HTMLResponse)
def admin_prompts(request: Request, db: Session = Depends(get_db)):
    templates_list = db.query(PromptTemplate).order_by(PromptTemplate.key.asc()).all()
    prompts = []
    for t in templates_list:
        active = get_active_prompt(db, t.key)
        prompts.append(
            {
                "key": t.key,
                "name": t.name,
                "task_kind": t.task_kind,
                "active_version": active.version,
                "active_source": active.source,
            }
        )
    return templates.TemplateResponse(
        request,
        "prompts.html",
        {"request": request, "prompts": prompts, "title": "Prompts"},
    )


@router.get("/admin/prompts/{key}", response_class=HTMLResponse)
def admin_prompt_detail(key: str, request: Request, db: Session = Depends(get_db)):
    template = db.query(PromptTemplate).filter(PromptTemplate.key == key).first()
    if not template:
        return RedirectResponse("/admin/prompts", status_code=302)
    active = get_active_prompt(db, key)
    versions = list_prompt_versions(db, key)
    return templates.TemplateResponse(
        request,
        "prompt_detail.html",
        {
            "request": request,
            "template": template,
            "active": active,
            "versions": versions,
            "title": f"Prompt {key}",
        },
    )


@router.post("/admin/prompts/{key}/versions")
def admin_create_prompt_version(
    key: str,
    version: str = Form(...),
    content_md: str = Form(...),
    notes: str | None = Form(None),
    activate: str | None = Form(None),
    db: Session = Depends(get_db),
):
    create_prompt_version(
        db,
        key,
        version=version,
        content_md=content_md,
        created_by="admin",
        notes=notes,
        activate=activate == "on",
    )
    return RedirectResponse(f"/admin/prompts/{key}", status_code=303)


@router.post("/admin/prompts/{key}/versions/{version_id}/activate")
def admin_activate_prompt_version(
    key: str, version_id: int, db: Session = Depends(get_db)
):
    activate_prompt_version(db, key, version_id)
    return RedirectResponse(f"/admin/prompts/{key}", status_code=303)


@router.get("/admin/quality-scores", response_class=HTMLResponse)
def admin_quality_scores(request: Request, db: Session = Depends(get_db)):
    scores = (
        db.query(ContentQualityScore)
        .order_by(ContentQualityScore.id.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "quality_scores.html",
        {"request": request, "scores": scores, "title": "Quality Scores"},
    )




@router.get("/admin/publications", response_class=HTMLResponse)
def admin_publications(request: Request, db: Session = Depends(get_db)):
    if not all_flags().get("ENABLE_ANALYTICS"):
        return RedirectResponse("/admin", status_code=302)
    records = db.query(PublicationRecord).order_by(PublicationRecord.id.desc()).limit(100).all()
    rows = []
    for rec in records:
        perf = db.query(ContentPerformance).filter(
            ContentPerformance.publication_record_id == rec.id
        ).first()
        rows.append({"record": rec, "perf": perf})
    return templates.TemplateResponse(
        request,
        "publications.html",
        {"request": request, "rows": rows, "title": "Publications", "feature_flags": all_flags()},
    )


@router.get("/admin/analytics", response_class=HTMLResponse)
def admin_analytics(request: Request, db: Session = Depends(get_db)):
    from app.models.project import Project

    projects = db.query(Project).all()
    project_summaries = {p.id: summarize_project_metrics(db, p.id) for p in projects}
    top_items = top_performing_content(db, limit=15)
    low_items = low_performing_content(db, limit=15)
    latest_snapshots = (
        db.query(AnalyticsSnapshot)
        .order_by(AnalyticsSnapshot.id.desc())
        .limit(30)
        .all()
    )
    aging = content_aging_signals(db, limit=15)
    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "request": request,
            "project_summaries": project_summaries,
            "top_items": top_items,
            "low_items": low_items,
            "latest_snapshots": latest_snapshots,
            "aging": aging,
            "feature_flags": all_flags(),
            "title": "Analytics",
        },
    )


@router.get("/admin/operations", response_class=HTMLResponse)
def admin_operations(request: Request, db: Session = Depends(get_db)):
    ctx = build_operations_context(db)
    return templates.TemplateResponse(
        request,
        "operations.html",
        {
            "request": request,
            "readiness": ctx["readiness"],
            "config": ctx["config"],
            "paths": ctx["paths"],
            "latest_manifest": ctx["latest_manifest"],
            "smoke_hint": ctx["smoke_hint"],
            "backup_hint": ctx["backup_hint"],
            "title": "Operations",
        },
    )


@router.get("/admin/hermes", response_class=HTMLResponse)
def admin_hermes(request: Request, db: Session = Depends(get_db)):
    health = check_hermes_health() if all_flags().get("ENABLE_HERMES") else None
    runs = db.query(HermesRun).order_by(HermesRun.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "hermes.html",
        {
            "request": request,
            "health": health,
            "aliases": list_hermes_aliases(),
            "runs": runs,
            "feature_flags": all_flags(),
            "settings": get_settings(),
            "title": "Hermes",
        },
    )


@router.get("/admin/editorial-queue", response_class=HTMLResponse)
def admin_editorial_queue(request: Request, db: Session = Depends(get_db)):
    groups = list_editorial_queue(db)
    return templates.TemplateResponse(
        request,
        "editorial_queue.html",
        {
            "request": request,
            "groups": groups,
            "feature_flags": all_flags(),
            "title": "Editorial Queue",
        },
    )




@router.get("/admin/media", response_class=HTMLResponse)
def admin_media(request: Request, db: Session = Depends(get_db)):
    assets = db.query(MediaAsset).order_by(MediaAsset.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "media.html",
        {
            "request": request,
            "assets": assets,
            "feature_flags": all_flags(),
            "settings": get_settings(),
            "title": "Media Assets",
        },
    )


@router.get("/admin/media-jobs", response_class=HTMLResponse)
def admin_media_jobs(request: Request, db: Session = Depends(get_db)):
    jobs = db.query(MediaJob).order_by(MediaJob.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "media_jobs.html",
        {"request": request, "jobs": jobs, "title": "Media Jobs"},
    )


@router.post("/admin/documents/{document_id}/media/generate-preview")
def admin_media_generate_preview(document_id: int, db: Session = Depends(get_db)):
    try:
        run_preview_generation(db, document_id, provider="placeholder")
    except (MediaDisabledError, ValueError) as exc:
        pass
    return RedirectResponse(f"/admin/documents/{document_id}#media", status_code=303)


@router.post("/admin/documents/{document_id}/media/{media_asset_id}/approve")
def admin_media_approve(document_id: int, media_asset_id: int, db: Session = Depends(get_db)):
    try:
        approve_media(db, media_asset_id)
    except MediaDisabledError:
        pass
    return RedirectResponse(f"/admin/documents/{document_id}#media", status_code=303)


@router.post("/admin/documents/{document_id}/media/{media_asset_id}/reject")
def admin_media_reject(document_id: int, media_asset_id: int, db: Session = Depends(get_db)):
    try:
        reject_media(db, media_asset_id)
    except MediaDisabledError:
        pass
    return RedirectResponse(f"/admin/documents/{document_id}#media", status_code=303)


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
