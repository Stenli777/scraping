"""Admin: projects CRUD, agents UI, project prompt overrides."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.prompt_template import PromptTemplate
from app.services.agent_registry import KNOWN_AGENT_KEYS, get_agent_meta, list_agents
from app.services.project_admin_service import (
    can_delete_project,
    create_project,
    project_usage_counts,
    update_project,
    validate_project_form,
)
from app.services.prompt_override_service import (
    count_project_overrides,
    create_project_override_version,
    disable_project_override,
    get_effective_prompt_details,
    get_project_override,
    list_recent_llm_runs_for_prompt,
    smoke_render_prompt,
)
from app.services.prompt_service import (
    activate_prompt_version,
    create_prompt_version,
    get_active_prompt,
    list_prompt_versions,
)

router = APIRouter()


def _admin_templates(request: Request):
    from app.admin.routes import templates

    return templates


# --- Agents ---


@router.get("/admin/agents", response_class=HTMLResponse)
def admin_agents_list(request: Request, db: Session = Depends(get_db)):
    tpl = _admin_templates(request)
    rows = []
    for meta in list_agents():
        key = meta["key"]
        template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
        active = get_active_prompt(db, key) if template else None
        rows.append(
            {
                **meta,
                "template": template,
                "active_version": active.version if active else "—",
                "active_source": active.source if active else "—",
                "override_count": count_project_overrides(db, key),
            }
        )
    return tpl.TemplateResponse(
        request,
        "agents_list.html",
        {"request": request, "agents": rows, "title": "Агенты (промпты)"},
    )


@router.get("/admin/agents/{key}", response_class=HTMLResponse)
def admin_agent_detail(key: str, request: Request, db: Session = Depends(get_db)):
    tpl = _admin_templates(request)
    template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
    if not template:
        return RedirectResponse("/admin/agents", status_code=302)
    meta = get_agent_meta(key)
    active = get_active_prompt(db, key)
    versions = list_prompt_versions(db, key)
    llm_runs = list_recent_llm_runs_for_prompt(db, key)
    return tpl.TemplateResponse(
        request,
        "agent_detail.html",
        {
            "request": request,
            "template": template,
            "meta": meta,
            "active": active,
            "versions": versions,
            "llm_runs": llm_runs,
            "override_count": count_project_overrides(db, key),
            "title": meta["agent_name"],
        },
    )


@router.get("/admin/prompts", response_class=HTMLResponse)
def admin_prompts_redirect(request: Request):
    return RedirectResponse("/admin/agents", status_code=302)


@router.get("/admin/prompts/{key}", response_class=HTMLResponse)
def admin_prompts_key_redirect(key: str):
    return RedirectResponse(f"/admin/agents/{key}", status_code=302)


# Re-use global version forms (POST stays on /admin/prompts/... in main routes)


# --- Projects list / create / edit ---


@router.get("/admin/projects", response_class=HTMLResponse)
def admin_projects_list(request: Request, db: Session = Depends(get_db)):
    tpl = _admin_templates(request)
    projects = db.query(Project).order_by(Project.id.desc()).limit(100).all()
    metrics = {p.id: project_usage_counts(db, p.id) for p in projects}
    return tpl.TemplateResponse(
        request,
        "projects.html",
        {
            "request": request,
            "projects": projects,
            "metrics": metrics,
            "title": "Проекты",
        },
    )


@router.get("/admin/projects/new", response_class=HTMLResponse)
def admin_project_new(request: Request):
    tpl = _admin_templates(request)
    return tpl.TemplateResponse(
        request,
        "project_form.html",
        {
            "request": request,
            "project": None,
            "errors": {},
            "form": _default_form(),
            "title": "Создать проект",
            "submit_label": "Создать",
        },
    )


@router.post("/admin/projects/new", response_class=HTMLResponse)
def admin_project_create(
    request: Request,
    db: Session = Depends(get_db),
    slug: str = Form(...),
    name: str = Form(...),
    domain: str = Form(""),
    description: str = Form(""),
    default_language: str = Form("ru"),
    tone_of_voice: str = Form(""),
    target_audience: str = Form(""),
    content_rules_md: str = Form(""),
    rewrite_instructions_md: str = Form(""),
    seo_instructions_md: str = Form(""),
    review_instructions_md: str = Form(""),
    allowed_topics_json: str = Form(""),
    blocked_topics_json: str = Form(""),
    enabled: str | None = Form(None),
):
    tpl = _admin_templates(request)
    errors, parsed = validate_project_form(
        db,
        slug=slug,
        name=name,
        default_language=default_language,
        domain=domain,
        allowed_topics_json=allowed_topics_json,
        blocked_topics_json=blocked_topics_json,
    )
    form = _form_from_post(locals())
    if errors:
        return tpl.TemplateResponse(
            request,
            "project_form.html",
            {
                "request": request,
                "project": None,
                "errors": errors,
                "form": form,
                "title": "Создать проект",
                "submit_label": "Создать",
            },
            status_code=400,
        )
    project = create_project(
        db,
        parsed,
        enabled=enabled == "on",
        tone_of_voice=tone_of_voice or None,
        target_audience=target_audience or None,
        content_rules_md=content_rules_md or None,
        rewrite_instructions_md=rewrite_instructions_md or None,
        seo_instructions_md=seo_instructions_md or None,
        review_instructions_md=review_instructions_md or None,
        description=description or None,
    )
    return RedirectResponse(f"/admin/projects/{project.id}", status_code=303)


@router.get("/admin/projects/{project_id}", response_class=HTMLResponse)
def admin_project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(f"/admin/projects/{project_id}/edit", status_code=302)


@router.get("/admin/projects/{project_id}/edit", response_class=HTMLResponse)
def admin_project_edit(project_id: int, request: Request, db: Session = Depends(get_db)):
    tpl = _admin_templates(request)
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/admin/projects", status_code=302)
    metrics = project_usage_counts(db, project_id)
    return tpl.TemplateResponse(
        request,
        "project_form.html",
        {
            "request": request,
            "project": project,
            "errors": {},
            "form": _form_from_project(project),
            "metrics": metrics,
            "title": f"Проект: {project.name}",
            "submit_label": "Сохранить",
        },
    )


@router.post("/admin/projects/{project_id}/edit", response_class=HTMLResponse)
def admin_project_save(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    slug: str = Form(...),
    name: str = Form(...),
    domain: str = Form(""),
    description: str = Form(""),
    default_language: str = Form("ru"),
    tone_of_voice: str = Form(""),
    target_audience: str = Form(""),
    content_rules_md: str = Form(""),
    rewrite_instructions_md: str = Form(""),
    seo_instructions_md: str = Form(""),
    review_instructions_md: str = Form(""),
    allowed_topics_json: str = Form(""),
    blocked_topics_json: str = Form(""),
    enabled: str | None = Form(None),
):
    tpl = _admin_templates(request)
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/admin/projects", status_code=302)
    errors, parsed = validate_project_form(
        db,
        slug=slug,
        name=name,
        default_language=default_language,
        domain=domain,
        allowed_topics_json=allowed_topics_json,
        blocked_topics_json=blocked_topics_json,
        project_id=project_id,
    )
    form = _form_from_post(locals())
    if errors:
        return tpl.TemplateResponse(
            request,
            "project_form.html",
            {
                "request": request,
                "project": project,
                "errors": errors,
                "form": form,
                "metrics": project_usage_counts(db, project_id),
                "title": f"Проект: {project.name}",
                "submit_label": "Сохранить",
            },
            status_code=400,
        )
    update_project(
        db,
        project,
        parsed,
        enabled=enabled == "on",
        tone_of_voice=tone_of_voice or None,
        target_audience=target_audience or None,
        content_rules_md=content_rules_md or None,
        rewrite_instructions_md=rewrite_instructions_md or None,
        seo_instructions_md=seo_instructions_md or None,
        review_instructions_md=review_instructions_md or None,
        description=description or None,
    )
    return RedirectResponse(f"/admin/projects/{project_id}/edit", status_code=303)


@router.post("/admin/projects/{project_id}/disable")
def admin_project_disable(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project:
        project.enabled = False
        db.commit()
    return RedirectResponse(f"/admin/projects/{project_id}/edit", status_code=303)


# --- Project agents ---


@router.get("/admin/projects/{project_id}/agents", response_class=HTMLResponse)
def admin_project_agents(project_id: int, request: Request, db: Session = Depends(get_db)):
    tpl = _admin_templates(request)
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/admin/projects", status_code=302)
    rows = []
    for key in KNOWN_AGENT_KEYS:
        meta = get_agent_meta(key)
        override = get_project_override(db, project_id, key)
        global_active = get_active_prompt(db, key)
        eff = get_active_prompt(db, key, project_id=project_id)
        rows.append(
            {
                "meta": meta,
                "uses_override": bool(override and override.enabled),
                "global_version": global_active.version,
                "effective_source": eff.source,
                "effective_version": eff.version,
                "override": override,
            }
        )
    return tpl.TemplateResponse(
        request,
        "project_agents.html",
        {
            "request": request,
            "project": project,
            "agents": rows,
            "title": f"Агенты проекта — {project.name}",
        },
    )


@router.get("/admin/projects/{project_id}/agents/{key}", response_class=HTMLResponse)
def admin_project_agent_detail(
    project_id: int, key: str, request: Request, db: Session = Depends(get_db)
):
    tpl = _admin_templates(request)
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/admin/projects", status_code=302)
    meta = get_agent_meta(key)
    effective = get_effective_prompt_details(db, key, project_id=project_id)
    global_eff = get_effective_prompt_details(db, key, project_id=None)
    override = get_project_override(db, project_id, key)
    versions = list_prompt_versions(db, key)
    llm_runs = list_recent_llm_runs_for_prompt(db, key, limit=10)
    return tpl.TemplateResponse(
        request,
        "project_agent_detail.html",
        {
            "request": request,
            "project": project,
            "meta": meta,
            "effective": effective,
            "global_eff": global_eff,
            "override": override,
            "versions": versions,
            "llm_runs": llm_runs,
            "title": f"{meta['short_name']} — {project.name}",
        },
    )


@router.post("/admin/projects/{project_id}/agents/{key}/override")
def admin_project_agent_create_override(
    project_id: int,
    key: str,
    version: str = Form(...),
    system: str = Form(""),
    user: str = Form(...),
    notes: str = Form(""),
    activate: str | None = Form(None),
    db: Session = Depends(get_db),
):
    create_project_override_version(
        db,
        project_id,
        key,
        version=version,
        system=system,
        user=user,
        notes=notes or None,
        activate=activate == "on",
    )
    return RedirectResponse(f"/admin/projects/{project_id}/agents/{key}", status_code=303)


@router.post("/admin/projects/{project_id}/agents/{key}/override/disable")
def admin_project_agent_disable_override(
    project_id: int, key: str, db: Session = Depends(get_db)
):
    disable_project_override(db, project_id, key)
    return RedirectResponse(f"/admin/projects/{project_id}/agents/{key}", status_code=303)


@router.post("/admin/projects/{project_id}/agents/{key}/smoke")
def admin_project_agent_smoke(project_id: int, key: str, db: Session = Depends(get_db)):
    smoke_render_prompt(db, project_id, key)
    return RedirectResponse(
        f"/admin/projects/{project_id}/agents/{key}?smoke=1", status_code=303
    )


def _default_form() -> dict:
    return {
        "slug": "",
        "name": "",
        "domain": "",
        "description": "",
        "default_language": "ru",
        "tone_of_voice": "",
        "target_audience": "",
        "content_rules_md": "",
        "rewrite_instructions_md": "",
        "seo_instructions_md": "",
        "review_instructions_md": "",
        "allowed_topics_json": "[]",
        "blocked_topics_json": "[]",
        "enabled": True,
    }


def _form_from_project(project: Project) -> dict:
    return {
        "slug": project.slug,
        "name": project.name,
        "domain": project.domain or "",
        "description": getattr(project, "description", None) or "",
        "default_language": project.default_language,
        "tone_of_voice": project.tone_of_voice or "",
        "target_audience": project.target_audience or "",
        "content_rules_md": project.content_rules_md or "",
        "rewrite_instructions_md": project.rewrite_instructions_md or "",
        "seo_instructions_md": project.seo_instructions_md or "",
        "review_instructions_md": project.review_instructions_md or "",
        "allowed_topics_json": json.dumps(project.allowed_topics_json or [], ensure_ascii=False, indent=2),
        "blocked_topics_json": json.dumps(project.blocked_topics_json or [], ensure_ascii=False, indent=2),
        "enabled": project.enabled,
    }


def _form_from_post(data: dict) -> dict:
    return {
        "slug": data.get("slug", ""),
        "name": data.get("name", ""),
        "domain": data.get("domain", ""),
        "description": data.get("description", ""),
        "default_language": data.get("default_language", "ru"),
        "tone_of_voice": data.get("tone_of_voice", ""),
        "target_audience": data.get("target_audience", ""),
        "content_rules_md": data.get("content_rules_md", ""),
        "rewrite_instructions_md": data.get("rewrite_instructions_md", ""),
        "seo_instructions_md": data.get("seo_instructions_md", ""),
        "review_instructions_md": data.get("review_instructions_md", ""),
        "allowed_topics_json": data.get("allowed_topics_json", "[]"),
        "blocked_topics_json": data.get("blocked_topics_json", "[]"),
        "enabled": data.get("enabled") == "on",
    }
