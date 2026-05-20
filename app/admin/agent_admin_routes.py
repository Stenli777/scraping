"""Admin: projects CRUD, agents UI, project prompt overrides."""

from __future__ import annotations

import json

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.prompt_template import PromptTemplate
from app.services.agent_registry import (
    KNOWN_AGENT_KEYS,
    get_agent_meta,
    list_agents,
    source_label_ru,
)
from app.services.project_admin_list_helpers import (
    PAGE_SIZE_CHOICES,
    list_project_documents,
    list_project_tasks,
    normalize_page_size,
)
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
    get_override_edit_defaults,
    list_recent_llm_runs_for_prompt,
    smoke_render_prompt,
)
from app.services.prompt_service import (
    ensure_prompt_template,
    activate_prompt_version,
    create_prompt_version,
    get_active_prompt,
    list_prompt_versions,
)

router = APIRouter()


def _admin_templates(request: Request):
    from app.admin.routes import templates

    return templates


def _project_nav(project: Project, *, agent_key: str | None = None) -> dict:
    agents_url = f"/admin/projects/{project.id}/agents"
    agent_url = f"{agents_url}/{agent_key}" if agent_key else None
    return {
        "project": project,
        "agents_url": agents_url,
        "agent_url": agent_url,
        "project_edit_url": f"/admin/projects/{project.id}/edit",
        "projects_url": "/admin/projects",
        "tasks_url": f"/admin/projects/{project.id}/tasks",
        "documents_url": f"/admin/projects/{project.id}/documents",
    }


# --- Agents ---


@router.get("/admin/agents", response_class=HTMLResponse)
def admin_agents_list(request: Request, db: Session = Depends(get_db)):
    tpl = _admin_templates(request)
    rows = []
    seen: set[str] = set()
    for meta in list_agents():
        key = meta["key"]
        seen.add(key)
        template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
        active = get_active_prompt(db, key) if template else None
        rows.append(
            {
                **meta,
                "template": template,
                "active_version": active.version if active else "—",
                "active_source": active.source if active else "code_fallback",
                "override_count": count_project_overrides(db, key),
                "pipeline_agent": True,
            }
        )
    for template in db.scalars(select(PromptTemplate).order_by(PromptTemplate.key)).all():
        if template.key in seen:
            continue
        meta = get_agent_meta(template.key)
        active = get_active_prompt(db, template.key)
        rows.append(
            {
                **meta,
                "template": template,
                "active_version": active.version if active else "—",
                "active_source": active.source if active else "—",
                "override_count": count_project_overrides(db, template.key),
                "pipeline_agent": False,
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
                "nav": _project_nav(project),
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
    seen_pa: set[str] = set()
    for key in KNOWN_AGENT_KEYS:
        seen_pa.add(key)
        meta = get_agent_meta(key)
        override = get_project_override(db, project_id, key)
        global_active = get_active_prompt(db, key)
        eff = get_active_prompt(db, key, project_id=project_id)
        rows.append(
            {
                "meta": meta,
                "uses_override": bool(override and override.enabled),
                "global_version": global_active.version if global_active else "—",
                "global_source": global_active.source if global_active else "—",
                "effective_source": eff.source,
                "effective_version": eff.version,
                "override": override,
                "pipeline_agent": True,
            }
        )
    for template in db.scalars(
        select(PromptTemplate).where(PromptTemplate.key.not_in(list(KNOWN_AGENT_KEYS)))
    ).all():
        key = template.key
        meta = get_agent_meta(key)
        override = get_project_override(db, project_id, key)
        global_active = get_active_prompt(db, key)
        eff = get_active_prompt(db, key, project_id=project_id)
        rows.append(
            {
                "meta": meta,
                "uses_override": bool(override and override.enabled),
                "global_version": global_active.version if global_active else "—",
                "global_source": global_active.source if global_active else "—",
                "effective_source": eff.source,
                "effective_version": eff.version,
                "override": override,
                "pipeline_agent": False,
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
            "nav": _project_nav(project),
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
    edit_form = get_override_edit_defaults(db, project_id, key)
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
            "edit_form": edit_form,
            "versions": versions,
            "llm_runs": llm_runs,
            "source_badge": source_label_ru(effective.get("source", "")),
            "title": f"{meta['agent_name']} — {project.name}",
            "nav": _project_nav(project, agent_key=key),
        },
    )




@router.get("/admin/projects/{project_id}/tasks", response_class=HTMLResponse)
def admin_project_tasks(
    project_id: int,
    request: Request,
    status: str | None = None,
    page_size: int | None = None,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    tpl = _admin_templates(request)
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/admin/projects", status_code=302)
    ps = normalize_page_size(page_size)
    off = max(0, int(offset or 0))
    result = list_project_tasks(db, project_id, status=status or None, page_size=ps, offset=off)
    return tpl.TemplateResponse(
        request,
        "project_tasks.html",
        {
            "request": request,
            "project": project,
            "tasks": result["items"],
            "total": result["total"],
            "page_size": result["page_size"],
            "offset": result["offset"],
            "page_size_choices": PAGE_SIZE_CHOICES,
            "filter_status": status or "",
            "title": f"Задачи проекта — {project.name}",
            "nav": _project_nav(project),
        },
    )


@router.get("/admin/projects/{project_id}/documents", response_class=HTMLResponse)
def admin_project_documents(
    project_id: int,
    request: Request,
    status: str | None = None,
    has_publication: str | None = None,
    in_pilot: str | None = None,
    page_size: int | None = None,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    tpl = _admin_templates(request)
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/admin/projects", status_code=302)
    pub_filter = None
    if has_publication == "yes":
        pub_filter = True
    elif has_publication == "no":
        pub_filter = False
    pilot_filter = None
    if in_pilot == "yes":
        pilot_filter = True
    elif in_pilot == "no":
        pilot_filter = False
    ps = normalize_page_size(page_size)
    off = max(0, int(offset or 0))
    result = list_project_documents(
        db,
        project_id,
        status=status or None,
        has_publication=pub_filter,
        in_pilot=pilot_filter,
        page_size=ps,
        offset=off,
    )
    return tpl.TemplateResponse(
        request,
        "project_documents.html",
        {
            "request": request,
            "project": project,
            "documents": result["items"],
            "total": result["total"],
            "page_size": result["page_size"],
            "offset": result["offset"],
            "page_size_choices": PAGE_SIZE_CHOICES,
            "filter_status": status or "",
            "filter_publication": has_publication or "",
            "filter_pilot": in_pilot or "",
            "title": f"Документы проекта — {project.name}",
            "nav": _project_nav(project),
        },
    )




CORE_AGENT_KEYS = frozenset(KNOWN_AGENT_KEYS)


@router.get("/admin/agents/new", response_class=HTMLResponse)
def admin_agent_new_form(request: Request):
    tpl = _admin_templates(request)
    return tpl.TemplateResponse(
        request,
        "agent_new.html",
        {
            "request": request,
            "errors": {},
            "form": {
                "agent_name": "",
                "key": "",
                "stage": "other",
                "purpose": "",
                "system": "",
                "user": "",
                "version": "v1",
                "schema_notes": "",
                "enabled": True,
            },
            "title": "Создать custom-агента",
        },
    )


@router.post("/admin/agents/new", response_class=HTMLResponse)
def admin_agent_new_create(
    request: Request,
    db: Session = Depends(get_db),
    agent_name: str = Form(...),
    key: str = Form(...),
    stage: str = Form("other"),
    purpose: str = Form(""),
    system: str = Form(...),
    user: str = Form(...),
    version: str = Form("v1"),
    schema_notes: str = Form(""),
    enabled: str | None = Form(None),
):
    tpl = _admin_templates(request)
    form = {
        "agent_name": agent_name,
        "key": key.strip(),
        "stage": stage,
        "purpose": purpose,
        "system": system,
        "user": user,
        "version": version,
        "schema_notes": schema_notes,
        "enabled": enabled == "on",
    }
    errors: dict[str, str] = {}
    k = form["key"]
    if not k or k != k.lower() or not k.replace("_", "").isalnum():
        errors["key"] = "Ключ: snake_case, латиница, цифры, underscore"
    if k in CORE_AGENT_KEYS:
        errors["key"] = "Ключ зарезервирован для pipeline-агента"
    if db.scalar(select(PromptTemplate).where(PromptTemplate.key == k)):
        errors["key"] = "Ключ уже существует"
    if errors:
        return tpl.TemplateResponse(
            request,
            "agent_new.html",
            {"request": request, "errors": errors, "form": form, "title": "Создать custom-агента"},
            status_code=400,
        )
    import json

    template = ensure_prompt_template(
        db,
        k,
        name=agent_name,
        description=purpose or schema_notes or None,
        task_kind=stage,
        enabled=form["enabled"],
    )
    content_md = json.dumps({"system": system, "user": user}, ensure_ascii=False)
    create_prompt_version(
        db,
        k,
        version=version.strip() or "v1",
        content_md=content_md,
        created_by="admin",
        notes=schema_notes or purpose or None,
        activate=True,
    )
    return RedirectResponse(f"/admin/agents/{template.key}?created=1", status_code=303)


@router.post("/admin/projects/{project_id}/agents/{key}/override")
def admin_project_agent_create_override(
    project_id: int,
    key: str,
    version: str = Form(...),
    system: str = Form(""),
    user: str = Form(...),
    notes: str = Form(""),
    action: str = Form("save_and_activate"),
    db: Session = Depends(get_db),
):
    try:
        create_project_override_version(
            db,
            project_id,
            key,
            version=version,
            system=system,
            user=user,
            notes=notes or None,
            activate=action == "save_and_activate",
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/admin/projects/{project_id}/agents/{key}?error={quote(str(exc))}",
            status_code=303,
        )
    qs = "saved=1"
    if action == "save_and_activate":
        qs += "&activated=1"
    return RedirectResponse(
        f"/admin/projects/{project_id}/agents/{key}?{qs}", status_code=303
    )


@router.post("/admin/projects/{project_id}/agents/{key}/override/disable")
def admin_project_agent_disable_override(
    project_id: int, key: str, db: Session = Depends(get_db)
):
    disable_project_override(db, project_id, key)
    return RedirectResponse(
        f"/admin/projects/{project_id}/agents/{key}?disabled=1", status_code=303
    )


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
