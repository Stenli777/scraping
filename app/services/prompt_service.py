"""DB-backed prompt templates with code fallback."""

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import prompts as code_prompts
from app.models.project_prompt_override import ProjectPromptOverride
from app.models.prompt_template import PromptTemplate
from app.models.prompt_version import PromptVersion

logger = logging.getLogger(__name__)

PROMPT_KEYS = (
    "review_article",
    "rewrite_article",
    "seo_enrich",
    "quality_review",
    "topic_cleanup_v1",
)

CODE_FALLBACK_BUILDERS = {
    "review_article": lambda ctx: code_prompts.build_review_messages_from_parts(
        ctx.get("system", code_prompts.REVIEW_ARTICLE_V1_SYSTEM),
        ctx.get("user_template", code_prompts.REVIEW_ARTICLE_V1_USER),
        ctx,
    ),
    "rewrite_article": lambda ctx: code_prompts.build_rewrite_messages_from_parts(
        ctx.get("system", code_prompts.REWRITE_ARTICLE_V1_SYSTEM),
        ctx.get("user_template", code_prompts.REWRITE_ARTICLE_V1_USER),
        ctx,
    ),
    "seo_enrich": lambda ctx: code_prompts.build_seo_messages_from_parts(
        ctx.get("system", code_prompts.SEO_ENRICH_V1_SYSTEM),
        ctx.get("user_template", code_prompts.SEO_ENRICH_V1_USER),
        ctx,
    ),
    "quality_review": lambda ctx: code_prompts.build_quality_messages_from_parts(
        ctx.get("system", ""),
        ctx.get("user_template", ""),
        ctx,
    ),
    "topic_cleanup_v1": lambda ctx: code_prompts.build_topic_cleanup_messages(ctx),
}


@dataclass
class ResolvedPrompt:
    key: str
    version: str
    source: str  # db | code_fallback
    system: str
    user_template: str
    prompt_version_id: int | None = None

    @property
    def template_ref(self) -> str:
        return f"{self.key}:{self.version}"


def _parse_content(content_md: str) -> tuple[str, str]:
    try:
        data = json.loads(content_md)
        if isinstance(data, dict) and "system" in data and "user" in data:
            return str(data["system"]), str(data["user"])
    except json.JSONDecodeError:
        pass
    return "", content_md


def get_active_prompt(
    db: Session,
    key: str,
    *,
    project_id: int | None = None,
) -> ResolvedPrompt:
    template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
    if not template or not template.enabled:
        return _code_fallback(key)

    version: PromptVersion | None = None
    if project_id:
        override = db.scalar(
            select(ProjectPromptOverride)
            .where(
                ProjectPromptOverride.project_id == project_id,
                ProjectPromptOverride.prompt_template_id == template.id,
                ProjectPromptOverride.enabled.is_(True),
            )
            .limit(1)
        )
        if override:
            version = db.get(PromptVersion, override.prompt_version_id)
            if not version or version.prompt_template_id != template.id:
                logger.warning(
                    "Broken project prompt override project=%s key=%s — using global active",
                    project_id,
                    key,
                )
                version = None

    if not version:
        version = db.scalar(
            select(PromptVersion)
            .where(
                PromptVersion.prompt_template_id == template.id,
                PromptVersion.is_active.is_(True),
            )
            .order_by(PromptVersion.id.desc())
        )

    if not version:
        logger.warning("No active prompt version for key=%s — code fallback", key)
        return _code_fallback(key)

    system, user_tpl = _parse_content(version.content_md)
    logger.info("Using prompt %s:%s (source=db)", key, version.version)
    return ResolvedPrompt(
        key=key,
        version=version.version,
        source="db",
        system=system,
        user_template=user_tpl,
        prompt_version_id=version.id,
    )


def _code_fallback(key: str) -> ResolvedPrompt:
    logger.info("Using prompt %s:v1 (source=code_fallback)", key)
    if key == "review_article":
        return ResolvedPrompt(
            key=key,
            version="v1",
            source="code_fallback",
            system=code_prompts.REVIEW_ARTICLE_V1_SYSTEM,
            user_template=code_prompts.REVIEW_ARTICLE_V1_USER,
        )
    if key == "rewrite_article":
        return ResolvedPrompt(
            key=key,
            version="v1",
            source="code_fallback",
            system=code_prompts.REWRITE_ARTICLE_V1_SYSTEM,
            user_template=code_prompts.REWRITE_ARTICLE_V1_USER,
        )
    if key == "seo_enrich":
        return ResolvedPrompt(
            key=key,
            version="v1",
            source="code_fallback",
            system=code_prompts.SEO_ENRICH_V1_SYSTEM,
            user_template=code_prompts.SEO_ENRICH_V1_USER,
        )
    if key == "quality_review":
        return ResolvedPrompt(
            key=key,
            version="v1",
            source="code_fallback",
            system=code_prompts.QUALITY_REVIEW_V1_SYSTEM,
            user_template=code_prompts.QUALITY_REVIEW_V1_USER,
        )
    if key == "topic_cleanup_v1":
        return ResolvedPrompt(
            key=key,
            version="v1",
            source="code_fallback",
            system=code_prompts.TOPIC_CLEANUP_V1_SYSTEM,
            user_template=code_prompts.TOPIC_CLEANUP_V1_USER,
        )
    raise ValueError(f"Unknown prompt key: {key}")


def render_prompt(
    db: Session,
    key: str,
    context: dict,
    *,
    project_id: int | None = None,
) -> tuple[list[dict[str, str]], ResolvedPrompt]:
    resolved = get_active_prompt(db, key, project_id=project_id)
    ctx = {**context, "system": resolved.system, "user_template": resolved.user_template}
    builder = CODE_FALLBACK_BUILDERS.get(key)
    if builder and resolved.source == "code_fallback" and not resolved.user_template:
        messages = builder(ctx)
    else:
        user_content = resolved.user_template.format_map(_SafeFormat(context))
        messages = [
            {"role": "system", "content": resolved.system},
            {"role": "user", "content": user_content},
        ]
    return messages, resolved


class _SafeFormat(dict):
    def __missing__(self, key: str) -> str:
        return ""


def list_prompt_versions(db: Session, key: str) -> list[PromptVersion]:
    template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
    if not template:
        return []
    return list(
        db.scalars(
            select(PromptVersion)
            .where(PromptVersion.prompt_template_id == template.id)
            .order_by(PromptVersion.id.desc())
        ).all()
    )


def create_prompt_version(
    db: Session,
    key: str,
    *,
    version: str,
    content_md: str,
    created_by: str = "api",
    notes: str | None = None,
    activate: bool = False,
) -> PromptVersion:
    template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
    if not template:
        raise ValueError(f"Prompt template {key} not found")
    existing = db.scalar(
        select(PromptVersion).where(
            PromptVersion.prompt_template_id == template.id,
            PromptVersion.version == version,
        )
    )
    if existing:
        raise ValueError(f"Version {version} already exists for {key}")

    record = PromptVersion(
        prompt_template_id=template.id,
        version=version,
        content_md=content_md,
        is_active=False,
        created_by=created_by,
        notes=notes,
    )
    db.add(record)
    db.flush()
    if activate:
        activate_prompt_version(db, key, record.id)
    else:
        db.commit()
    db.refresh(record)
    return record


def activate_prompt_version(db: Session, key: str, version_id: int) -> PromptVersion:
    template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
    if not template:
        raise ValueError(f"Prompt template {key} not found")
    target = db.get(PromptVersion, version_id)
    if not target or target.prompt_template_id != template.id:
        raise ValueError("Prompt version not found for template")

    for v in db.scalars(
        select(PromptVersion).where(PromptVersion.prompt_template_id == template.id)
    ).all():
        v.is_active = v.id == version_id
    db.commit()
    db.refresh(target)
    return target
