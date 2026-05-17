"""Draft publish payload builders."""

from typing import Any

from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.publish_target import PublishTarget
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask
from app.models.seo_metadata import SeoMetadata
from app.publishers.exceptions import PublishValidationError
from app.publishers.validators import PAYLOAD_VERSION

PAYLOAD_VERSION_ARTICLE_V1 = PAYLOAD_VERSION


def _extract_h1_from_markdown(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
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
