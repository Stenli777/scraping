"""Structured validation for article_v2 publish payloads."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.publish_target import PublishTarget
from app.models.seo_metadata import SeoMetadata
from app.publishers.validators import (
    MAX_TITLE_LEN,
    MIN_CONTENT_CHARS,
    PublishValidationResult,
    ValidationIssue,
    validate_article_v1_publish,
)

PAYLOAD_VERSION = "article_v2"
ALLOWED_EDITORIAL_STATUSES = frozenset(
    {"approved", "ready_to_publish", "published_draft", "ready"}
)


def validate_inbound_article_v2_payload(payload: dict[str, Any]) -> PublishValidationResult:
    return _validate_article_v2_core(payload=payload)


def validate_article_v2_publish(
    *,
    document: ParsedDocument,
    project: Project | None,
    target: PublishTarget,
    seo: SeoMetadata | None,
    payload: dict[str, Any] | None = None,
) -> PublishValidationResult:
    errors: list[ValidationIssue] = []
    if document is not None:
        base = validate_article_v1_publish(
            document=document,
            project=project,
            target=target,
            seo=seo,
            payload=None,
        )
        errors = list(base.errors)
    p = payload or {}
    return _validate_article_v2_core(payload=p, errors=errors)


def _validate_article_v2_core(
    *,
    payload: dict[str, Any],
    errors: list[ValidationIssue] | None = None,
) -> PublishValidationResult:
    errors = list(errors or [])
    p = payload or {}
    if p.get("payload_version") != PAYLOAD_VERSION:
        errors.append(
            ValidationIssue("payload_version", f"Expected {PAYLOAD_VERSION}")
        )

    title = str(p.get("title") or "").strip()
    if not title:
        errors.append(ValidationIssue("title", "Title must not be empty"))
    elif len(title) > MAX_TITLE_LEN:
        errors.append(ValidationIssue("title", f"Title exceeds {MAX_TITLE_LEN} characters"))

    slug = str(p.get("slug") or "").strip()
    if not slug:
        errors.append(ValidationIssue("slug", "Slug must not be empty"))

    md = str(p.get("content_markdown") or "").strip()
    if not md:
        errors.append(ValidationIssue("content_markdown", "Markdown content must not be empty"))
    elif len(md) < MIN_CONTENT_CHARS:
        errors.append(
            ValidationIssue(
                "content_markdown",
                f"Content too short (min {MIN_CONTENT_CHARS} chars)",
            )
        )

    seo_block = p.get("seo")
    if not isinstance(seo_block, dict):
        errors.append(ValidationIssue("seo", "SEO block is required"))
    else:
        if not str(seo_block.get("title") or "").strip():
            errors.append(ValidationIssue("seo.title", "SEO title is required"))
        if not str(seo_block.get("description") or "").strip():
            errors.append(ValidationIssue("seo.description", "SEO description is required"))

    source = p.get("source")
    if not isinstance(source, dict):
        errors.append(ValidationIssue("source", "Source block is required"))
    else:
        url = str(source.get("source_url") or source.get("url") or "").strip()
        if not url:
            errors.append(ValidationIssue("source.source_url", "Source URL is required"))
        domain = str(source.get("source_domain") or "").strip()
        if not domain and url:
            try:
                domain = urlparse(url).netloc
            except Exception:
                pass
        if not domain:
            errors.append(ValidationIssue("source.source_domain", "Source domain is required"))
        if not source.get("scraped_at"):
            errors.append(ValidationIssue("source.scraped_at", "scraped_at is required"))
        if source.get("document_id") is None:
            errors.append(ValidationIssue("source.document_id", "document_id is required"))

    editorial = p.get("editorial")
    if not isinstance(editorial, dict):
        errors.append(ValidationIssue("editorial", "Editorial block is required"))
    else:
        status = str(editorial.get("editorial_status") or "").strip()
        if not status:
            errors.append(ValidationIssue("editorial.editorial_status", "editorial_status is required"))
        elif status not in ALLOWED_EDITORIAL_STATUSES:
            errors.append(
                ValidationIssue(
                    "editorial.editorial_status",
                    f"Unsupported editorial_status: {status}",
                )
            )

    media = p.get("media")
    if not isinstance(media, dict):
        errors.append(ValidationIssue("media", "Media block is required"))
    else:
        preview = media.get("preview")
        if preview is not None and not isinstance(preview, dict):
            errors.append(ValidationIssue("media.preview", "Preview must be an object or null"))
        elif isinstance(preview, dict):
            if not str(preview.get("url") or "").strip():
                errors.append(ValidationIssue("media.preview.url", "Preview URL is required when preview set"))

    publication = p.get("publication")
    if not isinstance(publication, dict):
        errors.append(ValidationIssue("publication", "Publication block is required"))
    else:
        if str(publication.get("status") or "") != "draft":
            errors.append(ValidationIssue("publication.status", "Only draft publication status allowed"))
        if not publication.get("requested_at"):
            errors.append(ValidationIssue("publication.requested_at", "requested_at is required"))

    return PublishValidationResult(valid=len(errors) == 0, errors=errors)
