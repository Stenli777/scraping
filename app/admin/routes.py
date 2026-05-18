from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
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
from app.models.content_campaign import ContentCampaign
from app.models.topic_cluster import TopicCluster
from app.models.document_cluster_link import DocumentClusterLink
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
from app.services.publish_target_health_service import check_all_publish_targets_health
from app.services.publish_retry_service import get_retry_chain, is_retryable_publish_run
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
from app.services.campaign_service import (
    campaign_coverage,
    campaign_performance_summary,
    cluster_coverage,
    cluster_performance_summary,
    suggested_articles_for_campaign,
    document_strategy_context,
)
from app.services.quality_service import get_latest_quality_score, run_quality_for_document
from app.hermes.health import check_hermes_health
from app.hermes.routing import list_hermes_aliases
from app.models.hermes_run import HermesRun
from app.models.media_asset import MediaAsset
from app.models.media_job import MediaJob
from app.models.llm_enrichment_job import LlmEnrichmentJob
from app.services.enrichment_service import job_to_dict
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
            "strategy_context": strategy_context,
            "similarity_summary": similarity_summary,
            "lineage_summary": lineage_summary,
            "release_candidates": release_candidates,
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
    strategy_context = document_strategy_context(db, document_id)
    from app.services.document_similarity_service import get_document_lineage, get_document_similarity_summary

    similarity_summary = get_document_similarity_summary(db, document_id)
    lineage_summary = get_document_lineage(db, document_id)
    from app.services.release_candidate_service import list_release_candidates_for_document

    release_candidates = list_release_candidates_for_document(db, document_id, limit=5)
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
            "strategy_context": strategy_context,
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
    from app.services.publish_target_safety_service import validate_publish_target_safety

    targets = db.query(PublishTarget).order_by(PublishTarget.id.asc()).all()
    health = check_all_publish_targets_health(db)
    safety_profiles = [validate_publish_target_safety(t) for t in targets]
    safety_map = {s["target_id"]: s for s in safety_profiles}
    return templates.TemplateResponse(
        request,
        "publish_targets.html",
        {
            "request": request,
            "targets": targets,
            "health": health,
            "safety_profiles": safety_profiles,
            "safety_map": safety_map,
            "title": "Publish Targets",
        },
    )


@router.get("/admin/publish-runs", response_class=HTMLResponse)
def admin_publish_runs(request: Request, db: Session = Depends(get_db)):
    runs = db.query(PublishRun).order_by(PublishRun.id.desc()).limit(100).all()
    retryable = {r.id: is_retryable_publish_run(r) for r in runs}
    chains = {r.id: get_retry_chain(db, r.id) for r in runs[:30]}
    return templates.TemplateResponse(
        request,
        "publish_runs.html",
        {
            "request": request,
            "runs": runs,
            "retryable": retryable,
            "chains": chains,
            "title": "Publish Runs",
        },
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
    from app.services.source_quality_service import latest_quality_for_discovered, quality_to_dict
    quality_map = {u.id: quality_to_dict(latest_quality_for_discovered(db, u.id)) for u in urls if latest_quality_for_discovered(db, u.id)}
    return templates.TemplateResponse(
        request,
        "discovered_urls.html",
        {
            "request": request,
            "urls": urls,
            "filter_status": status,
            "projects": projects,
            "directories": directories,
            "quality_map": quality_map,
            "title": "Discovered URLs",
        },
    )


@router.post("/admin/discovered-urls/{discovered_url_id}/enqueue")
def admin_enqueue_discovered(discovered_url_id: int, db: Session = Depends(get_db)):
    record = enqueue_discovered_url(db, discovered_url_id)
    if record.existing_task_id:
        return RedirectResponse(f"/admin/tasks/{record.existing_task_id}", status_code=303)
    return RedirectResponse("/admin/discovered-urls", status_code=303)


@router.post("/admin/discovered-urls/{discovered_url_id}/approve-quality")
def admin_approve_quality(discovered_url_id: int, db: Session = Depends(get_db)):
    from app.services.source_quality_service import approve_discovered_url_quality
    approve_discovered_url_quality(db, discovered_url_id)
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
        from app.services.publication_confirmation_service import analytics_ready
        rows.append({"record": rec, "perf": perf, "analytics_ready": analytics_ready(rec)})
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
            "release_state_hint": ctx.get("release_state_hint"),
            "release_ops": ctx.get("release_ops"),
            "target_safety": ctx.get("target_safety"),
            "smoke_safe_hint": ctx.get("smoke_safe_hint"),
            "smoke_production_hint": ctx.get("smoke_production_hint"),
            "post_publication": ctx.get("post_publication"),
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


@router.get("/admin/source-quality", response_class=HTMLResponse)
def admin_source_quality(request: Request, db: Session = Depends(get_db)):
    from app.services.source_quality_metrics_service import get_source_quality_metrics
    from app.models.source_quality_score import SourceQualityScore
    from app.models.domain_trust_registry import DomainTrustRegistry
    metrics = get_source_quality_metrics(db)
    trusted = db.query(DomainTrustRegistry).order_by(DomainTrustRegistry.trust_score.desc()).limit(30).all()
    blocked = db.query(SourceQualityScore).filter(SourceQualityScore.strategy_allowed.is_(False)).order_by(SourceQualityScore.id.desc()).limit(20).all()
    high = db.query(SourceQualityScore).filter(SourceQualityScore.quality_score >= 75).order_by(SourceQualityScore.id.desc()).limit(15).all()
    return templates.TemplateResponse(
        request,
        "source_quality_dashboard.html",
        {"request": request, "metrics": metrics, "trusted": trusted, "blocked": blocked, "high": high, "title": "Source Quality"},
    )


@router.get("/admin/enrichment-dashboard", response_class=HTMLResponse)
def admin_enrichment_dashboard(request: Request, db: Session = Depends(get_db)):
    from app.services.enrichment_metrics_service import get_enrichment_metrics, get_enrichment_health
    from app.models.llm_enrichment_job import LlmEnrichmentJob, EnrichmentJobStatus
    metrics = get_enrichment_metrics(db)
    health = get_enrichment_health(db)
    recent = db.query(LlmEnrichmentJob).filter(
        LlmEnrichmentJob.status.in_([EnrichmentJobStatus.FAILED_RETRYABLE, EnrichmentJobStatus.FAILED_TERMINAL])
    ).order_by(LlmEnrichmentJob.id.desc()).limit(15).all()
    from app.services.enrichment_service import job_to_dict
    return templates.TemplateResponse(
        request,
        "enrichment_dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "health": health,
            "recent_failures": [job_to_dict(j) for j in recent],
            "title": "Enrichment Dashboard",
        },
    )


@router.get("/admin/enrichment-jobs", response_class=HTMLResponse)
def admin_enrichment_jobs(request: Request, db: Session = Depends(get_db)):
    jobs = db.query(LlmEnrichmentJob).order_by(LlmEnrichmentJob.id.desc()).limit(150).all()
    items = [job_to_dict(j) for j in jobs]
    return templates.TemplateResponse(
        request,
        "enrichment_jobs.html",
        {"request": request, "jobs": items, "title": "LLM Enrichment Jobs"},
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


# --- Stage 4B automation admin ---
from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
from app.models.automation_rule import AutomationRule
from app.models.automation_run import AutomationRun, AutomationRunStatus
from app.scheduler.status import build_scheduler_status
from app.scheduler.rules import next_run_preview
from app.services.automation_service import (
    AutomationError,
    cancel_automation_run,
    enqueue_automation_run,
    get_rule_rate_usage,
    mark_run_failed,
    set_rule_enabled,
)


@router.get("/admin/automation", response_class=HTMLResponse)
def admin_automation(request: Request, db: Session = Depends(get_db)):
    from types import SimpleNamespace

    rules = list(db.scalars(select(AutomationRule).order_by(AutomationRule.id.asc())).all())
    enriched = []
    for rule in rules:
        active_runs = db.scalar(
            select(func.count())
            .select_from(AutomationRun)
            .where(
                AutomationRun.automation_rule_id == rule.id,
                AutomationRun.status.in_(
                    [
                        AutomationRunStatus.QUEUED,
                        AutomationRunStatus.RUNNING,
                        AutomationRunStatus.CANCEL_REQUESTED,
                    ]
                ),
            )
        ) or 0
        last_fail = db.scalar(
            select(AutomationRun)
            .where(
                AutomationRun.automation_rule_id == rule.id,
                AutomationRun.status == AutomationRunStatus.FAILED,
            )
            .order_by(AutomationRun.id.desc())
        )
        last_run = db.scalar(
            select(AutomationRun)
            .where(AutomationRun.automation_rule_id == rule.id)
            .order_by(AutomationRun.id.desc())
        )
        enriched.append(
            SimpleNamespace(
                id=rule.id,
                name=rule.name,
                automation_type=rule.automation_type,
                enabled=rule.enabled,
                trigger_type=rule.trigger_type,
                schedule_cron=rule.schedule_cron,
                rate_limit_per_hour=rule.rate_limit_per_hour,
                max_daily_runs=rule.max_daily_runs,
                next_run_preview=next_run_preview(rule, db),
                rate_usage=get_rule_rate_usage(db, rule),
                active_runs=active_runs,
                last_run=last_run,
                last_failure=last_fail,
            )
        )
    return templates.TemplateResponse(
        request,
        "automation.html",
        {
            "request": request,
            "title": "Automation",
            "rules": enriched,
            "scheduler_status": build_scheduler_status(db),
            "scheduler_enabled": is_scheduler_enabled(),
            "automation_enabled": is_automation_enabled(),
        },
    )


@router.get("/admin/automation-runs", response_class=HTMLResponse)
def admin_automation_runs(request: Request, db: Session = Depends(get_db), limit: int = 100):
    runs = list(
        db.scalars(select(AutomationRun).order_by(AutomationRun.id.desc()).limit(min(limit, 200))).all()
    )
    rule_names = {r.id: r.name for r in db.scalars(select(AutomationRule)).all()}
    return templates.TemplateResponse(
        request,
        "automation_runs.html",
        {
            "request": request,
            "title": "Automation Runs",
            "runs": runs,
            "rule_names": rule_names,
            "scheduler_status": build_scheduler_status(db),
        },
    )


@router.get("/admin/automation-runs/{run_id}", response_class=HTMLResponse)
def admin_automation_run_detail(run_id: int, request: Request, db: Session = Depends(get_db)):
    run = db.get(AutomationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    rule = db.get(AutomationRule, run.automation_rule_id)
    return templates.TemplateResponse(
        request,
        "automation_run_detail.html",
        {
            "request": request,
            "title": f"Run #{run_id}",
            "run": run,
            "rule": rule,
        },
    )


@router.post("/admin/automation/rules/{rule_id}/run")
def admin_automation_run(rule_id: int, db: Session = Depends(get_db)):
    try:
        run = enqueue_automation_run(db, rule_id, trigger="manual", requested_by="admin")
        return RedirectResponse(f"/admin/automation-runs/{run.id}", status_code=303)
    except AutomationError:
        return RedirectResponse("/admin/automation-runs", status_code=303)


@router.post("/admin/automation/rules/{rule_id}/enable")
def admin_automation_enable(rule_id: int, db: Session = Depends(get_db)):
    try:
        set_rule_enabled(db, rule_id, True)
    except AutomationError:
        pass
    return RedirectResponse("/admin/automation", status_code=303)


@router.post("/admin/automation/rules/{rule_id}/disable")
def admin_automation_disable(rule_id: int, db: Session = Depends(get_db)):
    try:
        set_rule_enabled(db, rule_id, False)
    except AutomationError:
        pass
    return RedirectResponse("/admin/automation", status_code=303)


@router.post("/admin/automation-runs/{run_id}/cancel")
def admin_automation_cancel(run_id: int, db: Session = Depends(get_db)):
    try:
        cancel_automation_run(db, run_id)
    except AutomationError:
        pass
    return RedirectResponse(f"/admin/automation-runs/{run_id}", status_code=303)


@router.post("/admin/automation-runs/{run_id}/mark-failed")
def admin_automation_mark_failed(run_id: int, db: Session = Depends(get_db)):
    try:
        mark_run_failed(db, run_id, reason="marked failed from admin", force=True)
    except AutomationError:
        pass
    return RedirectResponse(f"/admin/automation-runs/{run_id}", status_code=303)

@router.get("/admin/system", response_class=HTMLResponse)
def admin_system(request: Request, db: Session = Depends(get_db)):
    from app.core.config import get_settings
    from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
    from app.core.workspace import get_workspace_info, get_workspace_warnings

    settings = get_settings()
    info = get_workspace_info()
    return templates.TemplateResponse(
        request,
        "system.html",
        {
            "request": request,
            "title": "System",
            "info": info,
            "warnings": get_workspace_warnings(),
            "scheduler_enabled": is_scheduler_enabled(),
            "automation_enabled": is_automation_enabled(),
            "paths": {
                "storage": str(settings.storage_root),
                "media": str(settings.media_storage_root),
                "logs": str(settings.logs_path),
            },
        },
    )

@router.get("/admin/campaigns", response_class=HTMLResponse)
def admin_campaigns(request: Request, db: Session = Depends(get_db)):
    campaigns = db.query(ContentCampaign).order_by(ContentCampaign.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "campaigns.html",
        {"request": request, "campaigns": campaigns, "title": "Campaigns"},
    )


@router.get("/admin/campaigns/{campaign_id}", response_class=HTMLResponse)
def admin_campaign_detail(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    campaign = db.get(ContentCampaign, campaign_id)
    if not campaign:
        return RedirectResponse("/admin/campaigns", status_code=302)
    coverage = campaign_coverage(db, campaign_id)
    suggestions = suggested_articles_for_campaign(db, campaign_id)
    performance = campaign_performance_summary(db, campaign_id)
    return templates.TemplateResponse(
        request,
        "campaign_detail.html",
        {
            "request": request,
            "campaign": campaign,
            "coverage": coverage,
            "suggestions": suggestions,
            "performance": performance,
            "title": f"Campaign {campaign.name}",
        },
    )


@router.get("/admin/clusters", response_class=HTMLResponse)
def admin_clusters(request: Request, db: Session = Depends(get_db)):
    clusters = db.query(TopicCluster).order_by(TopicCluster.priority.desc(), TopicCluster.id.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "clusters.html",
        {"request": request, "clusters": clusters, "title": "Topic Clusters"},
    )


@router.get("/admin/clusters/{cluster_id}", response_class=HTMLResponse)
def admin_cluster_detail(cluster_id: int, request: Request, db: Session = Depends(get_db)):
    cluster = db.get(TopicCluster, cluster_id)
    if not cluster:
        return RedirectResponse("/admin/clusters", status_code=302)
    coverage = cluster_coverage(db, cluster_id)
    perf = cluster_performance_summary(db, project_id=cluster.project_id)
    cluster_perf = next((r for r in perf["clusters"] if r["cluster_id"] == cluster_id), None)
    links = db.query(DocumentClusterLink).filter(DocumentClusterLink.cluster_id == cluster_id).all()
    return templates.TemplateResponse(
        request,
        "cluster_detail.html",
        {
            "request": request,
            "cluster": cluster,
            "coverage": coverage,
            "performance": cluster_perf,
            "links": links,
            "title": f"Cluster {cluster.name}",
        },
    )


@router.get("/admin/canonical-groups", response_class=HTMLResponse)
def admin_canonical_groups(request: Request, db: Session = Depends(get_db)):
    from app.services.canonical_content_service import list_canonical_groups

    groups = list_canonical_groups(db, limit=200)
    return templates.TemplateResponse(
        request,
        "canonical_groups_list.html",
        {"request": request, "groups": groups, "title": "Canonical groups"},
    )


@router.get("/admin/canonical-groups/{group_id}", response_class=HTMLResponse)
def admin_canonical_group_detail(group_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.canonical_content_service import get_canonical_group_detail

    try:
        detail = get_canonical_group_detail(db, group_id)
    except ValueError:
        return RedirectResponse("/admin/canonical-groups", status_code=302)
    return templates.TemplateResponse(
        request,
        "canonical_group_detail.html",
        {"request": request, "detail": detail, "title": f"Canonical #{group_id}"},
    )



def _load_draft_review_context(db: Session, candidate_id: int) -> dict:
    from sqlalchemy import select
    from app.models.content_release_candidate import ContentReleaseCandidate
    from app.models.publication_record import PublicationRecord
    from app.models.publish_run import PublishRun
    from app.services.draft_feedback_service import get_feedback_for_candidate, get_or_create_feedback_for_candidate
    from app.services.release_candidate_service import get_candidate_status

    detail = get_candidate_status(db, candidate_id)
    cand = db.get(ContentReleaseCandidate, candidate_id)
    run = db.scalar(
        select(PublishRun).where(PublishRun.release_candidate_id == candidate_id).order_by(PublishRun.id.desc())
    )
    pub = None
    if run:
        pub = db.scalar(
            select(PublicationRecord).where(PublicationRecord.publish_run_id == run.id).order_by(PublicationRecord.id.desc())
        )
    if not pub and cand:
        pub = db.scalar(
            select(PublicationRecord)
            .where(PublicationRecord.document_id == cand.document_id)
            .order_by(PublicationRecord.id.desc())
        )
    latest = get_or_create_feedback_for_candidate(db, candidate_id)
    history = get_feedback_for_candidate(db, candidate_id)
    visibility = None
    vis_json = latest.visibility_check_json if latest else None
    if not vis_json and pub and pub.metadata_json:
        vis_json = (pub.metadata_json or {}).get("visibility_check")
    if vis_json:
        paths = vis_json.get("paths") or {}
        visibility = {
            "checked_at": vis_json.get("checked_at"),
            "visible_in_blog": bool((paths.get("/blog") or {}).get("visible")),
            "visible_in_sitemap": bool((paths.get("/sitemap.xml") or {}).get("visible")),
            "visible_in_rss": bool((paths.get("/rss.xml") or {}).get("visible")),
        }
    draft_url = (pub.external_url if pub else None) or (run.draft_url if run else None)
    public_info = {"publication_id": pub.id if pub else None, "public_url": None, "public_visibility_status": None, "analytics_ready": False}
    if pub:
        from app.services.publication_confirmation_service import analytics_ready, get_publication_confirmation_status
        st = get_publication_confirmation_status(db, pub.id)
        public_info = {
            "publication_id": pub.id,
            "public_url": st.get("public_url"),
            "public_visibility_status": st.get("public_visibility_status"),
            "analytics_ready": st.get("analytics_ready"),
        }
    return {
        "detail": detail,
        "public_info": public_info,
        "draft_review": {
            "draft_url": draft_url,
            "draft_review_status": cand.draft_review_status if cand else None,
            "draft_reviewed_at": cand.draft_reviewed_at.isoformat() if cand and cand.draft_reviewed_at else None,
            "publication_id": pub.id if pub else None,
            "latest_feedback": latest,
            "feedback_history": history,
            "visibility": visibility,
        },
    }


def _parse_required_changes(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]

@router.get("/admin/release-candidates", response_class=HTMLResponse)
def admin_release_candidates_list(request: Request, db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.models.content_release_candidate import ContentReleaseCandidate

    rows = db.scalars(
        select(ContentReleaseCandidate).order_by(ContentReleaseCandidate.id.desc()).limit(200)
    ).all()
    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "document_id": r.document_id,
            "status": r.status,
            "qa_score": r.qa_score,
            "blocking_count": len(r.blocking_issues_json or []),
            "created_at": r.created_at,
        })
    return templates.TemplateResponse(
        request,
        "release_candidates_list.html",
        {"request": request, "items": items, "title": "Release candidates"},
    )


@router.get("/admin/release-candidates/{candidate_id}", response_class=HTMLResponse)
def admin_release_candidate_detail(candidate_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.release_candidate_service import get_candidate_status

    try:
        ctx = _load_draft_review_context(db, candidate_id)
    except Exception:
        return RedirectResponse("/admin/release-candidates", status_code=302)
    return templates.TemplateResponse(
        request,
        "release_candidate_detail.html",
        {"request": request, "title": f"Release candidate #{candidate_id}", **ctx},
    )


@router.post("/admin/release-candidates/{candidate_id}/run-qa")
def admin_rc_run_qa(candidate_id: int, db: Session = Depends(get_db)):
    from app.services.release_candidate_service import run_release_qa

    run_release_qa(db, candidate_id)
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{candidate_id}", status_code=303)


@router.post("/admin/release-candidates/{candidate_id}/approve")
def admin_rc_approve(candidate_id: int, db: Session = Depends(get_db)):
    from app.services.release_candidate_service import approve_release_candidate

    approve_release_candidate(db, candidate_id)
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{candidate_id}", status_code=303)


@router.post("/admin/release-candidates/{candidate_id}/reject")
def admin_rc_reject(candidate_id: int, db: Session = Depends(get_db)):
    from app.services.release_candidate_service import reject_release_candidate

    reject_release_candidate(db, candidate_id, reason="rejected via admin")
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{candidate_id}", status_code=303)


@router.post("/admin/release-candidates/{candidate_id}/publish-draft")
def admin_rc_publish(candidate_id: int, db: Session = Depends(get_db)):
    from app.services.release_candidate_service import publish_draft_from_candidate

    publish_draft_from_candidate(db, candidate_id)
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{candidate_id}", status_code=303)


@router.post("/admin/documents/{document_id}/release-candidates/create")
def admin_document_create_rc(document_id: int, db: Session = Depends(get_db)):
    from app.services.release_candidate_service import create_release_candidate

    c = create_release_candidate(db, document_id)
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{c.id}", status_code=303)


@router.get("/admin/draft-reviews", response_class=HTMLResponse)
def admin_draft_reviews_list(request: Request, db: Session = Depends(get_db)):
    from app.services.draft_feedback_service import list_draft_review_queue

    items = list_draft_review_queue(db)
    return templates.TemplateResponse(
        request,
        "draft_reviews_list.html",
        {"request": request, "items": items, "title": "Draft reviews"},
    )


@router.post("/admin/release-candidates/{candidate_id}/draft-feedback/accepted")
def admin_draft_feedback_accepted(
    candidate_id: int,
    reviewer_name: str = Form("operator"),
    notes: str = Form(""),
    checked_public_visibility: bool = Form(False),
    checked_seo: bool = Form(False),
    checked_content: bool = Form(False),
    checked_media: bool = Form(False),
    db: Session = Depends(get_db),
):
    from app.services.draft_feedback_service import STATUS_ACCEPTED, create_feedback

    create_feedback(
        db,
        release_candidate_id=candidate_id,
        review_status=STATUS_ACCEPTED,
        reviewer_name=reviewer_name,
        notes=notes or None,
        checked_public_visibility=checked_public_visibility,
        checked_seo=checked_seo,
        checked_content=checked_content,
        checked_media=checked_media,
    )
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{candidate_id}", status_code=303)


@router.post("/admin/release-candidates/{candidate_id}/draft-feedback/needs-edits")
def admin_draft_feedback_needs_edits(
    candidate_id: int,
    notes: str = Form(""),
    required_changes: str = Form(""),
    apply_editorial: bool = Form(True),
    db: Session = Depends(get_db),
):
    from app.services.draft_feedback_service import STATUS_NEEDS_EDITS, create_feedback

    create_feedback(
        db,
        release_candidate_id=candidate_id,
        review_status=STATUS_NEEDS_EDITS,
        notes=notes or None,
        required_changes=_parse_required_changes(required_changes),
        apply_editorial_needs_revision=apply_editorial,
    )
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{candidate_id}", status_code=303)


@router.post("/admin/release-candidates/{candidate_id}/draft-feedback/rejected")
def admin_draft_feedback_rejected(
    candidate_id: int,
    notes: str = Form(""),
    apply_editorial_reject: bool = Form(False),
    db: Session = Depends(get_db),
):
    from app.services.draft_feedback_service import STATUS_REJECTED, create_feedback

    create_feedback(
        db,
        release_candidate_id=candidate_id,
        review_status=STATUS_REJECTED,
        notes=notes or None,
        apply_editorial_reject=apply_editorial_reject,
    )
    db.commit()
    return RedirectResponse(f"/admin/release-candidates/{candidate_id}", status_code=303)


@router.post("/admin/publications/{publication_id}/check-visibility")
def admin_check_public_visibility(publication_id: int, db: Session = Depends(get_db)):
    from app.models.publish_run import PublishRun
    from app.models.publication_record import PublicationRecord
    from app.services.draft_feedback_service import check_public_visibility, get_or_create_feedback_for_candidate

    pub = db.get(PublicationRecord, publication_id)
    feedback_id = None
    redirect_cid = None
    if pub and pub.publish_run_id:
        run = db.get(PublishRun, pub.publish_run_id)
        if run and run.release_candidate_id:
            fb = get_or_create_feedback_for_candidate(db, run.release_candidate_id)
            feedback_id = fb.id
            redirect_cid = run.release_candidate_id
    check_public_visibility(db, publication_id, save_to_feedback_id=feedback_id)
    db.commit()
    if redirect_cid:
        return RedirectResponse(f"/admin/release-candidates/{redirect_cid}", status_code=303)
    return RedirectResponse("/admin/draft-reviews", status_code=303)


@router.get("/admin/publications/{publication_id}", response_class=HTMLResponse)
def admin_publication_detail(publication_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.publication_confirmation_service import get_publication_confirmation_status

    pub = db.get(PublicationRecord, publication_id)
    if not pub:
        return RedirectResponse("/admin/publications", status_code=302)
    status = get_publication_confirmation_status(db, publication_id)
    return templates.TemplateResponse(
        request,
        "publication_detail.html",
        {"request": request, "pub": pub, "status": status, "title": f"Publication #{publication_id}"},
    )


@router.post("/admin/publications/{publication_id}/check-public-status")
def admin_pub_check_public(publication_id: int, db: Session = Depends(get_db)):
    from app.services.publication_confirmation_service import check_public_visibility

    check_public_visibility(db, publication_id)
    db.commit()
    return RedirectResponse(f"/admin/publications/{publication_id}", status_code=303)


@router.post("/admin/publications/{publication_id}/confirm-public")
def admin_pub_confirm_public(
    publication_id: int,
    confirmed_by: str = Form("operator"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.services.publication_confirmation_service import confirm_publication

    confirm_publication(db, publication_id, confirmed_by=confirmed_by, notes=notes or None, force=bool(notes))
    db.commit()
    return RedirectResponse(f"/admin/publications/{publication_id}", status_code=303)


@router.post("/admin/publications/{publication_id}/mark-not-public")
def admin_pub_mark_not_public(publication_id: int, db: Session = Depends(get_db)):
    from app.services.publication_confirmation_service import mark_not_public

    mark_not_public(db, publication_id)
    db.commit()
    return RedirectResponse(f"/admin/publications/{publication_id}", status_code=303)
