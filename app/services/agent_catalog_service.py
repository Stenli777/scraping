"""Agent catalog rows for admin UI (global catalog vs project-scoped view)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.llm_run import LLMRun
from app.models.project import Project
from app.models.project_prompt_override import ProjectPromptOverride
from app.models.prompt_template import PromptTemplate
from app.models.prompt_version import PromptVersion
from app.services.agent_registry import KNOWN_AGENT_KEYS, get_agent_meta, list_agents
from app.services.prompt_override_service import count_project_overrides, get_project_override
from app.services.prompt_service import get_active_prompt

STAGE_LABELS: dict[str, str] = {
    "review": "Рецензент",
    "rewrite": "Писатель",
    "seo": "SEO",
    "quality": "Редактор качества",
    "strategy": "Темы",
    "other": "Custom",
}

BASE_AGENT_CHOICES: list[tuple[str, str]] = [
    ("review_article", "Рецензент источника"),
    ("rewrite_article", "Писатель"),
    ("seo_enrich", "SEO-специалист"),
    ("quality_review", "Редактор качества"),
    ("topic_cleanup_v1", "Тематическая чистка"),
    ("__custom__", "Custom / manual"),
]

ROLE_FILTER_MAP: dict[str, str] = {
    "review": "review",
    "rewrite": "rewrite",
    "seo": "seo",
    "quality": "quality",
    "strategy": "strategy",
    "custom": "other",
}


def stage_label(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage)


def _last_llm_run(db: Session, key: str) -> dict[str, Any] | None:
    run = db.scalar(
        select(LLMRun)
        .where(LLMRun.prompt_template.isnot(None))
        .where(LLMRun.prompt_template.like(f"{key}:%"))
        .order_by(LLMRun.id.desc())
        .limit(1)
    )
    if not run:
        return None
    return {
        "id": run.id,
        "success": run.success,
        "model": run.model_alias,
        "at": run.created_at,
        "ref": run.prompt_template,
    }


def _last_llm_run_for_project(db: Session, key: str, project_id: int) -> dict[str, Any] | None:
    run = db.scalar(
        select(LLMRun)
        .where(LLMRun.project_id == project_id)
        .where(LLMRun.prompt_template.isnot(None))
        .where(LLMRun.prompt_template.like(f"{key}:%"))
        .order_by(LLMRun.id.desc())
        .limit(1)
    )
    if run:
        return {
            "id": run.id,
            "success": run.success,
            "model": run.model_alias,
            "at": run.created_at,
            "ref": run.prompt_template,
        }
    return _last_llm_run(db, key)


def _pipeline_label(key: str, meta: dict[str, str]) -> str:
    if key in KNOWN_AGENT_KEYS:
        return f"Да: {meta.get('stage', 'pipeline')}"
    return "Нет: manual/custom"


def _source_display(source: str, *, is_custom: bool) -> str:
    if source == "project_override":
        return "project_override"
    if source == "code_fallback":
        return "code_fallback"
    if is_custom:
        return "custom"
    return "global"


def get_global_agent_catalog(
    db: Session,
    *,
    project_filter: str | None = None,
    role_filter: str | None = None,
    pipeline_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Full catalog for /admin/agents: global rows + all project overrides + custom."""
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def add_template_rows(tpl: PromptTemplate | None, key: str) -> None:
        if key in seen_keys and tpl is None:
            return
        seen_keys.add(key)
        meta = get_agent_meta(key)
        is_pipeline = key in KNOWN_AGENT_KEYS
        is_custom = not is_pipeline
        try:
            active_global = get_active_prompt(db, key, project_id=None) if tpl else None
            if not tpl:
                active_global = get_active_prompt(db, key, project_id=None)
        except ValueError:
            active_global = None

        global_row = {
            "agent_name": meta["agent_name"],
            "type_label": stage_label(meta.get("stage", "other")),
            "key": key,
            "project_name": "Глобальный",
            "project_id": None,
            "source": _source_display(
                active_global.source if active_global else "code_fallback",
                is_custom=is_custom,
            ),
            "active_version": active_global.version if active_global else "—",
            "pipeline_label": _pipeline_label(key, meta),
            "pipeline_agent": is_pipeline,
            "override_count": count_project_overrides(db, key) if tpl else 0,
            "last_run": _last_llm_run(db, key),
            "scope": "global",
            "open_url": f"/admin/agents/{key}",
            "project_url": None,
            "stage": meta.get("stage", "other"),
        }
        rows.append(global_row)

        if not tpl:
            return
        q = (
            select(ProjectPromptOverride, Project, PromptVersion)
            .join(Project, ProjectPromptOverride.project_id == Project.id)
            .join(PromptVersion, ProjectPromptOverride.prompt_version_id == PromptVersion.id)
            .where(
                ProjectPromptOverride.prompt_template_id == tpl.id,
                ProjectPromptOverride.enabled.is_(True),
            )
        )
        for override, project, pver in db.execute(q).all():
            try:
                eff = get_active_prompt(db, key, project_id=project.id)
            except ValueError:
                eff = None
            rows.append(
                {
                    "agent_name": meta["agent_name"],
                    "type_label": stage_label(meta.get("stage", "other")),
                    "key": key,
                    "project_name": project.name,
                    "project_id": project.id,
                    "source": "project_override",
                    "active_version": eff.version if eff else pver.version,
                    "pipeline_label": _pipeline_label(key, meta),
                    "pipeline_agent": is_pipeline,
                    "override_count": 1,
                    "last_run": _last_llm_run(db, key),
                    "scope": "project",
                    "open_url": f"/admin/agents/{key}",
                    "project_url": f"/admin/projects/{project.id}/agents/{key}",
                    "stage": meta.get("stage", "other"),
                    "updated_at": override.updated_at,
                }
            )

    for meta in list_agents():
        key = meta["key"]
        tpl = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
        add_template_rows(tpl, key)

    for tpl in db.scalars(select(PromptTemplate).order_by(PromptTemplate.key)).all():
        if tpl.key not in seen_keys:
            add_template_rows(tpl, tpl.key)

    filtered: list[dict[str, Any]] = []
    for row in rows:
        if project_filter == "global" and row["scope"] != "global":
            continue
        if project_filter and project_filter not in ("global", "") and project_filter.isdigit():
            pid = int(project_filter)
            if row["project_id"] != pid:
                continue
        if role_filter == "custom":
            if row["pipeline_agent"]:
                continue
        elif role_filter:
            want = ROLE_FILTER_MAP.get(role_filter)
            if want and row["stage"] != want:
                continue
        if pipeline_filter == "yes" and not row["pipeline_agent"]:
            continue
        if pipeline_filter == "no" and row["pipeline_agent"]:
            continue
        filtered.append(row)
    return filtered


def build_agent_catalog(
    db: Session,
    *,
    project_filter: str | None = None,
    role_filter: str | None = None,
    pipeline_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible alias for /admin/agents."""
    return get_global_agent_catalog(
        db,
        project_filter=project_filter,
        role_filter=role_filter,
        pipeline_filter=pipeline_filter,
    )


def get_project_agent_catalog(db: Session, project_id: int) -> list[dict[str, Any]]:
    """Rows for /admin/projects/{id}/agents — only this project (no other projects' data)."""
    rows: list[dict[str, Any]] = []

    def _row_for_key(key: str, *, pipeline_agent: bool) -> dict[str, Any]:
        meta = get_agent_meta(key)
        try:
            eff = get_active_prompt(db, key, project_id=project_id)
        except ValueError:
            eff = None
        try:
            ga = get_active_prompt(db, key, project_id=None)
        except ValueError:
            ga = None
        ov = get_project_override(db, project_id, key)
        return {
            "meta": meta,
            "type_label": stage_label(meta.get("stage", "other")),
            "pipeline_label": _pipeline_label(key, meta),
            "pipeline_agent": pipeline_agent,
            "source_for_project": eff.source if eff else "code_fallback",
            "effective_version": eff.version if eff else "—",
            "global_version": ga.version if ga else "—",
            "global_source": ga.source if ga else "—",
            "uses_override": bool(ov),
            "last_run": _last_llm_run_for_project(db, key, project_id),
        }

    for key in KNOWN_AGENT_KEYS:
        rows.append(_row_for_key(key, pipeline_agent=True))

    tpl_ids = (
        select(ProjectPromptOverride.prompt_template_id)
        .where(ProjectPromptOverride.project_id == project_id)
        .distinct()
    )
    custom_templates = db.scalars(
        select(PromptTemplate)
        .where(PromptTemplate.id.in_(tpl_ids))
        .where(PromptTemplate.key.not_in(list(KNOWN_AGENT_KEYS)))
        .order_by(PromptTemplate.key)
    ).all()

    seen_custom: set[str] = set()
    for tpl in custom_templates:
        if tpl.key in seen_custom:
            continue
        seen_custom.add(tpl.key)
        rows.append(_row_for_key(tpl.key, pipeline_agent=False))

    return rows


def list_project_overrides_for_agent(db: Session, key: str) -> list[dict[str, Any]]:
    tpl = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
    if not tpl:
        return []
    q = (
        select(ProjectPromptOverride, Project, PromptVersion)
        .join(Project, ProjectPromptOverride.project_id == Project.id)
        .join(PromptVersion, ProjectPromptOverride.prompt_version_id == PromptVersion.id)
        .where(ProjectPromptOverride.prompt_template_id == tpl.id)
        .order_by(Project.name)
    )
    out = []
    for override, project, pver in db.execute(q).all():
        eff = get_active_prompt(db, key, project_id=project.id)
        out.append(
            {
                "project": project,
                "enabled": override.enabled,
                "version": pver.version,
                "source": eff.source if eff and override.enabled else "disabled",
                "updated_at": override.updated_at,
                "configure_url": f"/admin/projects/{project.id}/agents/{key}",
            }
        )
    return out
