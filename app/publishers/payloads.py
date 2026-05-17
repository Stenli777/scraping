"""Draft publish payload builders."""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.publish_target import PublishTarget
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask
from app.models.seo_metadata import SeoMetadata
from app.publishers.exceptions import PublishValidationError
from app.publishers.validators import PAYLOAD_VERSION
from app.publishers.validators_v2 import PAYLOAD_VERSION as PAYLOAD_VERSION_V2

PAYLOAD_VERSION_ARTICLE_V1 = PAYLOAD_VERSION
PAYLOAD_VERSION_ARTICLE_V2 = PAYLOAD_VERSION_V2


def _extract_h1_from_markdown(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _source_domain(url: str) -> str:
    try:
        return urlparse(url).netloc or ""
    except Exception:
        return ""


def build_article_v1_payload(
    *,
    document: ParsedDocument,
    task: ScrapingTask,
    project: Project,
    target: PublishTarget,
    seo: SeoMetadata,
    review: ReviewResult | None = None,
    status: str | None = None,
    media: dict | None = None,
    revision_id: int | None = None,
) -> dict[str, Any]:
    if not document.rewritten_text or not document.rewritten_text.strip():
        raise PublishValidationError("rewritten_text is required for publish")

    publish_status = status or target.default_status or "draft"
    if publish_status != "draft":
        raise PublishValidationError("Only draft status is allowed on this stage")

    meta = document.metadata_json or {}
    rewrite_meta = meta.get("rewrite") or {}
    review_meta = meta.get("review") or {}

    title = (
        seo.h1
        or seo.seo_title
        or _extract_h1_from_markdown(document.rewritten_text)
        or meta.get("extracted_title")
        or meta.get("title")
        or "Untitled"
    )

    slug = seo.slug or ""
    if not slug:
        raise PublishValidationError("seo_metadata.slug is required for publish")

    faq = seo.faq_json or []
    if faq and isinstance(faq[0], dict):
        faq_normalized = [
            {"question": str(item.get("question", "")), "answer": str(item.get("answer", ""))}
            for item in faq
        ]
    else:
        faq_normalized = []

    review_score = review.score if review else review_meta.get("score")
    review_take = review.take if review else review_meta.get("take")
    llm_alias = rewrite_meta.get("model_alias")

    quality_meta = meta.get("quality") or {}

    return {
        "payload_version": PAYLOAD_VERSION,
        "external_source": "scrap",
        "project_slug": project.slug,
        "status": publish_status,
        "title": title,
        "slug": slug,
        "excerpt": seo.excerpt or "",
        "content_markdown": document.rewritten_text,
        "seo": {
            "title": seo.seo_title or title,
            "description": seo.seo_description or "",
            "h1": seo.h1 or title,
            "tags": seo.tags_json or [],
            "category": seo.suggested_category or "",
            "faq": faq_normalized,
        },
        "source": {
            "url": document.source_url,
            "title": meta.get("extracted_title") or meta.get("title") or "",
            "content_hash": document.content_hash,
        },
        "media": media or {"preview": None},
        "meta": {
            "scrap_document_id": document.id,
            "scrap_task_id": task.id,
            "review_score": review_score,
            "review_take": review_take,
            "llm_model_alias": llm_alias,
            "publish_target_id": target.id,
        },
    }


def build_article_v2_payload(
    *,
    document: ParsedDocument,
    task: ScrapingTask,
    project: Project,
    target: PublishTarget,
    seo: SeoMetadata,
    review: ReviewResult | None = None,
    status: str | None = None,
    media: dict | None = None,
    revision_id: int | None = None,
) -> dict[str, Any]:
    v1 = build_article_v1_payload(
        document=document,
        task=task,
        project=project,
        target=target,
        seo=seo,
        review=review,
        status=status,
        media=media,
        revision_id=revision_id,
    )

    meta = document.metadata_json or {}
    review_meta = meta.get("review") or {}
    quality_meta = meta.get("quality") or {}

    review_score = review.score if review else review_meta.get("score")
    quality_score = quality_meta.get("overall_score") or quality_meta.get("score")

    editorial_status = getattr(document, "editorial_status", None) or "generated"
    if editorial_status == "approved":
        editorial_status = "ready_to_publish"

    source_url = document.source_url or ""
    now = datetime.now(timezone.utc).isoformat()
    scraped_at = (
        document.updated_at.isoformat()
        if getattr(document, "updated_at", None)
        else now
    )

    media_block = media or {"preview": None}
    preview = media_block.get("preview") if isinstance(media_block, dict) else None
    preview_v2 = None
    if isinstance(preview, dict):
        preview_v2 = {
            "url": preview.get("url"),
            "alt_text": preview.get("alt_text") or preview.get("alt") or "",
            "caption": preview.get("caption") or "",
        }

    return {
        **{k: v for k, v in v1.items() if k not in ("source", "meta")},
        "payload_version": PAYLOAD_VERSION_V2,
        "source": {
            "source_url": source_url,
            "source_domain": _source_domain(source_url),
            "scraped_at": scraped_at,
            "document_id": document.id,
            "revision_id": revision_id,
            "content_hash": document.content_hash,
        },
        "editorial": {
            "review_score": review_score,
            "quality_score": quality_score,
            "editorial_status": editorial_status,
        },
        "media": {"preview": preview_v2},
        "publication": {
            "status": "draft",
            "requested_at": now,
        },
    }


def build_publish_payload(
    payload_format: str,
    **kwargs: Any,
) -> dict[str, Any]:
    if payload_format == PAYLOAD_VERSION_ARTICLE_V2:
        return build_article_v2_payload(**kwargs)
    if payload_format == PAYLOAD_VERSION_ARTICLE_V1:
        return build_article_v1_payload(**kwargs)
    raise PublishValidationError(f"Unsupported payload_format: {payload_format}")
