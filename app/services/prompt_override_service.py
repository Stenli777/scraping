"""Project-specific prompt overrides and effective prompt preview."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.llm_run import LLMRun
from app.models.project_prompt_override import ProjectPromptOverride
from app.models.prompt_template import PromptTemplate
from app.models.prompt_version import PromptVersion
from app.services.prompt_service import (
    PROMPT_KEYS,
    ResolvedPrompt,
    _parse_content,
    create_prompt_version,
    get_active_prompt,
    list_prompt_versions,
)


def _template(db: Session, key: str) -> PromptTemplate | None:
    return db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))


def get_project_override(db: Session, project_id: int, key: str) -> ProjectPromptOverride | None:
    template = _template(db, key)
    if not template:
        return None
    return db.scalar(
        select(ProjectPromptOverride)
        .where(
            ProjectPromptOverride.project_id == project_id,
            ProjectPromptOverride.prompt_template_id == template.id,
            ProjectPromptOverride.enabled.is_(True),
        )
        .limit(1)
    )


def count_project_overrides(db: Session, key: str) -> int:
    template = _template(db, key)
    if not template:
        return 0
    return int(
        db.scalar(
            select(func.count())
            .select_from(ProjectPromptOverride)
            .where(
                ProjectPromptOverride.prompt_template_id == template.id,
                ProjectPromptOverride.enabled.is_(True),
            )
        )
        or 0
    )


def get_effective_prompt_details(
    db: Session,
    key: str,
    *,
    project_id: int | None = None,
    sample_context: dict | None = None,
) -> dict[str, Any]:
    global_active = get_active_prompt(db, key, project_id=None)
    project_resolved: ResolvedPrompt | None = None
    override_row = None
    if project_id:
        project_resolved = get_active_prompt(db, key, project_id=project_id)
        override_row = get_project_override(db, project_id, key)

    effective = project_resolved if project_id else global_active
    source = effective.source if effective else "code_fallback"
    if project_id and override_row and project_resolved:
        source = "project_override"

    system, user_tpl = "", ""
    if effective:
        system, user_tpl = effective.system, effective.user_template

    warnings: list[str] = []
    if override_row and project_resolved and project_resolved.source == "code_fallback":
        warnings.append("Override включён, но версия недоступна — используется fallback")

    ctx = sample_context or _sample_context_for_key(key)
    try:
        preview_user = user_tpl.format_map(_SafePreview(ctx)) if user_tpl else ""
    except Exception as exc:
        preview_user = user_tpl
        warnings.append(f"Ошибка подстановки переменных: {exc}")

    return {
        "key": key,
        "source": source,
        "version": effective.version if effective else "v1",
        "prompt_version_id": effective.prompt_version_id if effective else None,
        "global": {
            "version": global_active.version,
            "source": global_active.source,
        },
        "project_override": {
            "enabled": bool(override_row),
            "override_id": override_row.id if override_row else None,
        }
        if project_id
        else None,
        "system": system,
        "user_template": user_tpl,
        "preview_user": preview_user,
        "expected_variables": _expected_variables(key),
        "warnings": warnings,
    }


def create_project_override_version(
    db: Session,
    project_id: int,
    key: str,
    *,
    version: str,
    system: str,
    user: str,
    notes: str | None = None,
    activate: bool = True,
    operator_note: str | None = None,
) -> ProjectPromptOverride:
    content_md = json.dumps({"system": system, "user": user}, ensure_ascii=False)
    version_label = version.strip()
    if not version_label.startswith("p"):
        version_label = f"p{project_id}-{version_label}"

    record = create_prompt_version(
        db,
        key,
        version=version_label,
        content_md=content_md,
        created_by="admin",
        notes=notes or operator_note,
        activate=False,
    )

    template = _template(db, key)
    if not template:
        raise ValueError(f"Prompt {key} not found")

    existing = db.scalar(
        select(ProjectPromptOverride).where(
            ProjectPromptOverride.project_id == project_id,
            ProjectPromptOverride.prompt_template_id == template.id,
        )
    )
    if existing:
        existing.prompt_version_id = record.id
        existing.enabled = activate
    else:
        existing = ProjectPromptOverride(
            project_id=project_id,
            prompt_template_id=template.id,
            prompt_version_id=record.id,
            enabled=activate,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def disable_project_override(db: Session, project_id: int, key: str) -> None:
    template = _template(db, key)
    if not template:
        return
    row = db.scalar(
        select(ProjectPromptOverride).where(
            ProjectPromptOverride.project_id == project_id,
            ProjectPromptOverride.prompt_template_id == template.id,
        )
    )
    if row:
        row.enabled = False
        db.commit()


def list_recent_llm_runs_for_prompt(
    db: Session, key: str, *, limit: int = 15
) -> list[LLMRun]:
    prefix = f"{key}:"
    return list(
        db.scalars(
            select(LLMRun)
            .where(LLMRun.prompt_template.isnot(None))
            .where(LLMRun.prompt_template.like(f"{prefix}%"))
            .order_by(LLMRun.id.desc())
            .limit(limit)
        ).all()
    )


def smoke_render_prompt(
    db: Session,
    project_id: int,
    key: str,
) -> dict[str, Any]:
    details = get_effective_prompt_details(db, key, project_id=project_id)
    issues: list[str] = []
    if not details.get("system") and not details.get("user_template"):
        issues.append("Пустой system и user — будет code fallback")
    try:
        json.loads(json.dumps({"system": details["system"], "user": details["user_template"]}))
    except Exception as exc:
        issues.append(f"JSON structure issue: {exc}")
    for var in details.get("expected_variables") or []:
        if var not in _sample_context_for_key(key):
            issues.append(f"Нет примера переменной: {var}")
    return {"ok": not issues, "issues": issues, "effective": details}


def _expected_variables(key: str) -> list[str]:
    common = ["profile_block", "source_url", "title", "content"]
    if key == "rewrite_article":
        return ["language", "profile_block", "source_url", "title", "content"]
    if key == "seo_enrich":
        return ["profile_block", "title", "content", "rewritten_text"]
    if key == "quality_review":
        return ["title", "content", "rewritten_text", "seo_title"]
    return common


def _sample_context_for_key(key: str) -> dict[str, str]:
    base = {
        "language": "ru",
        "profile_block": "Профиль: CRMFlow24, B2B, тон деловой.",
        "source_url": "https://example.com/article",
        "title": "Пример заголовка статьи",
        "content": "Пример очищенного текста статьи для проверки промпта.",
        "rewritten_text": "Пример переписанного текста.",
        "seo_title": "Пример SEO title",
    }
    return base


class _SafePreview(dict):
    def __missing__(self, key: str) -> str:
        return f"[{key}]"
