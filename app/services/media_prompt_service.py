"""LLM-based media prompt generation — audit via llm_runs."""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.client import LLMClient
from app.llm.json_utils import parse_llm_json
from app.llm.exceptions import LLMError
from app.models.parsed_document import ParsedDocument
from app.models.seo_metadata import SeoMetadata
from app.media.schemas import MediaPromptBundle
from app.services.llm_run_service import record_llm_run
from app.services.project_profile_service import resolve_task_project, build_seo_context
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _latest_seo(db: Session, document_id: int) -> SeoMetadata | None:
    return db.scalar(
        select(SeoMetadata)
        .where(SeoMetadata.document_id == document_id)
        .order_by(SeoMetadata.id.desc())
    )


MEDIA_PROMPT_SYSTEM = """You help prepare preview image metadata for articles.
Return ONLY valid JSON with keys: prompt, alt_text, caption.
prompt: English image generation prompt, concise, no quotes inside.
alt_text: Russian accessibility text, max 120 chars.
caption: Russian short caption for the preview, max 200 chars."""


@dataclass
class MediaPromptResult:
    success: bool
    bundle: MediaPromptBundle | None = None
    llm_run_id: int | None = None
    error_message: str | None = None


def _fallback_bundle(document: ParsedDocument, seo: SeoMetadata | None) -> MediaPromptBundle:
    title = ""
    if seo:
        title = seo.h1 or seo.seo_title or ""
    if not title and document.rewritten_text:
        for line in document.rewritten_text.splitlines():
            if line.strip().startswith("# "):
                title = line.strip()[2:].strip()
                break
    title = title or "Статья"
    excerpt = (seo.excerpt if seo else "") or title
    return MediaPromptBundle(
        prompt=f"Editorial blog preview image, professional, topic: {title[:80]}",
        alt_text=f"Превью: {title[:100]}",
        caption=excerpt[:200],
    )


def generate_preview_prompts(
    db: Session,
    document_id: int,
    *,
    use_llm: bool = True,
) -> MediaPromptResult:
    document = db.get(ParsedDocument, document_id)
    if not document:
        return MediaPromptResult(success=False, error_message="Document not found")

    seo = _latest_seo(db, document_id)
    if not use_llm:
        return MediaPromptResult(success=True, bundle=_fallback_bundle(document, seo))

    settings = get_settings()
    task = document.task
    project = resolve_task_project(db, task) if task else None
    profile = build_seo_context(project) if project else ""

    content_excerpt = (document.rewritten_text or "")[:4000]
    seo_block = ""
    if seo:
        seo_block = f"SEO title: {seo.seo_title}\nSlug: {seo.slug}\nH1: {seo.h1}\nExcerpt: {seo.excerpt}"

    user_msg = f"""{profile}

Article excerpt:
{content_excerpt}

{seo_block}

Generate preview image metadata JSON."""

    client = LLMClient()
    try:
        result = client.complete(
            model_alias=settings.seo_model_alias,
            messages=[
                {"role": "system", "content": MEDIA_PROMPT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            metadata={"task": "media_prompt", "document_id": document_id},
        )
        run = record_llm_run(
            db,
            model_alias=settings.seo_model_alias,
            upstream_model=result.upstream_model,
            success=result.success,
            task_id=task.id if task else None,
            project_id=project.id if project else None,
            prompt_template="media_preview_prompt",
            result=result,
            error_message=result.error_message,
        )
        if not result.success:
            return MediaPromptResult(
                success=True,
                bundle=_fallback_bundle(document, seo),
                llm_run_id=run.id,
                error_message=result.error_message,
            )
        parsed, _ = parse_llm_json(result.content or "{}")
        bundle = MediaPromptBundle(
            prompt=str(parsed.get("prompt") or "").strip() or _fallback_bundle(document, seo).prompt,
            alt_text=str(parsed.get("alt_text") or "").strip() or _fallback_bundle(document, seo).alt_text,
            caption=str(parsed.get("caption") or "").strip() or _fallback_bundle(document, seo).caption,
        )
        return MediaPromptResult(success=True, bundle=bundle, llm_run_id=run.id)
    except LLMError as exc:
        logger.warning("Media prompt LLM failed doc=%s: %s", document_id, exc)
        return MediaPromptResult(
            success=True,
            bundle=_fallback_bundle(document, seo),
            error_message=str(exc),
        )
