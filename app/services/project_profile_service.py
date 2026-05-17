"""Load project profile context for LLM stages."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_project_profiles_enabled
from app.models.project import Project


def get_project(db: Session, project_id: int | None) -> Project | None:
    if not project_id:
        return None
    return db.get(Project, project_id)


def get_default_project(db: Session, slug: str = "crmflow24") -> Project | None:
    return db.scalar(select(Project).where(Project.slug == slug, Project.enabled.is_(True)))


def resolve_task_project(db: Session, task) -> Project | None:
    if task.project_id:
        return get_project(db, task.project_id)
    return get_default_project(db)


def build_profile_context(project: Project | None) -> str:
    if not project or not is_project_profiles_enabled():
        return ""

    parts: list[str] = [f"Проект: {project.name} ({project.slug})"]
    if project.tone_of_voice:
        parts.append(f"Tone of voice: {project.tone_of_voice}")
    if project.target_audience:
        parts.append(f"Аудитория: {project.target_audience}")
    if project.content_rules_md:
        parts.append(f"Правила контента:\n{project.content_rules_md}")
    if project.allowed_topics_json:
        parts.append("Allowed topics: " + ", ".join(project.allowed_topics_json))
    if project.blocked_topics_json:
        parts.append("Blocked topics: " + ", ".join(project.blocked_topics_json))
    return "\n\n".join(parts)


def build_rewrite_context(project: Project | None) -> str:
    if not project or not is_project_profiles_enabled():
        return ""
    ctx = build_profile_context(project)
    if project.rewrite_instructions_md:
        ctx += f"\n\nИнструкции рерайта:\n{project.rewrite_instructions_md}"
    return ctx


def build_review_context(project: Project | None) -> str:
    if not project or not is_project_profiles_enabled():
        return ""
    ctx = build_profile_context(project)
    if project.review_instructions_md:
        ctx += f"\n\nИнструкции review:\n{project.review_instructions_md}"
    return ctx


def build_seo_context(project: Project | None) -> str:
    if not project or not is_project_profiles_enabled():
        return ""
    ctx = build_profile_context(project)
    if project.seo_instructions_md:
        ctx += f"\n\nИнструкции SEO:\n{project.seo_instructions_md}"
    return ctx
