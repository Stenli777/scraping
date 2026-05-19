"""Project create/edit validation and metrics for admin."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.publish_target import PublishTarget
from app.models.scraping_task import ScrapingTask
from app.models.source_directory import SourceDirectory

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    d = domain.strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix) :]
    return d.strip("/") or None


def validate_slug(slug: str) -> str | None:
    s = (slug or "").strip().lower()
    if not s:
        return "Укажите slug проекта"
    if not SLUG_RE.match(s):
        return "Slug: только латиница, цифры и дефис (kebab-case)"
    return None


def validate_json_list(raw: str | None, field_label: str) -> tuple[list | None, str | None]:
    if not raw or not raw.strip():
        return None, None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, f"{field_label}: неверный JSON"
    if not isinstance(data, list):
        return None, f"{field_label}: ожидается JSON-массив"
    return data, None


def validate_project_form(
    db: Session,
    *,
    slug: str,
    name: str,
    default_language: str,
    domain: str | None = None,
    allowed_topics_json: str | None = None,
    blocked_topics_json: str | None = None,
    project_id: int | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    errors: dict[str, str] = {}
    if err := validate_slug(slug):
        errors["slug"] = err
    if not (name or "").strip():
        errors["name"] = "Укажите название проекта"
    if not (default_language or "").strip():
        errors["default_language"] = "Укажите язык по умолчанию"

    slug_norm = (slug or "").strip().lower()
    if slug_norm and not errors.get("slug"):
        q = select(Project).where(Project.slug == slug_norm)
        if project_id:
            q = q.where(Project.id != project_id)
        if db.scalar(q.limit(1)):
            errors["slug"] = "Проект с таким slug уже существует"

    allowed, err = validate_json_list(allowed_topics_json, "Разрешённые темы")
    if err:
        errors["allowed_topics_json"] = err
    blocked, err = validate_json_list(blocked_topics_json, "Запрещённые темы")
    if err:
        errors["blocked_topics_json"] = err

    parsed: dict[str, Any] = {
        "slug": slug_norm,
        "name": (name or "").strip(),
        "domain": normalize_domain(domain),
        "default_language": (default_language or "ru").strip(),
        "allowed_topics_json": allowed,
        "blocked_topics_json": blocked,
    }
    return errors, parsed


def project_usage_counts(db: Session, project_id: int) -> dict[str, int]:
    tasks = db.scalar(
        select(func.count()).select_from(ScrapingTask).where(ScrapingTask.project_id == project_id)
    ) or 0
    docs = db.scalar(
        select(func.count())
        .select_from(ParsedDocument)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ScrapingTask.project_id == project_id)
    ) or 0
    sources = db.scalar(
        select(func.count()).select_from(SourceDirectory).where(SourceDirectory.project_id == project_id)
    ) or 0
    targets = db.scalar(
        select(func.count()).select_from(PublishTarget).where(PublishTarget.project_id == project_id)
    ) or 0
    return {
        "tasks": int(tasks),
        "documents": int(docs),
        "source_directories": int(sources),
        "publish_targets": int(targets),
    }


def can_delete_project(db: Session, project_id: int) -> tuple[bool, str]:
    counts = project_usage_counts(db, project_id)
    if counts["documents"] or counts["tasks"]:
        return False, "Нельзя удалить проект: есть задачи или документы. Отключите проект (enabled=false)."
    return True, ""


def create_project(db: Session, data: dict[str, Any], **extra) -> Project:
    project = Project(
        slug=data["slug"],
        name=data["name"],
        domain=data.get("domain"),
        default_language=data.get("default_language") or "ru",
        allowed_topics_json=data.get("allowed_topics_json"),
        blocked_topics_json=data.get("blocked_topics_json"),
        enabled=extra.get("enabled", True),
        tone_of_voice=extra.get("tone_of_voice"),
        target_audience=extra.get("target_audience"),
        content_rules_md=extra.get("content_rules_md"),
        rewrite_instructions_md=extra.get("rewrite_instructions_md"),
        seo_instructions_md=extra.get("seo_instructions_md"),
        review_instructions_md=extra.get("review_instructions_md"),
        description=extra.get("description"),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, data: dict[str, Any], **extra) -> Project:
    project.slug = data["slug"]
    project.name = data["name"]
    project.domain = data.get("domain")
    project.default_language = data.get("default_language") or "ru"
    project.allowed_topics_json = data.get("allowed_topics_json")
    project.blocked_topics_json = data.get("blocked_topics_json")
    for field in (
        "enabled",
        "tone_of_voice",
        "target_audience",
        "content_rules_md",
        "rewrite_instructions_md",
        "seo_instructions_md",
        "review_instructions_md",
        "description",
    ):
        if field in extra:
            setattr(project, field, extra[field])
    db.commit()
    db.refresh(project)
    return project
