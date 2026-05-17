"""Structured publish payload validation."""

from dataclasses import dataclass, field
from typing import Any

from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.publish_target import PublishTarget
from app.models.review_result import ReviewResult
from app.models.seo_metadata import SeoMetadata
from app.publishers.exceptions import PublishValidationError

PAYLOAD_VERSION = "article_v1"
MIN_CONTENT_CHARS = 80
MAX_TITLE_LEN = 300


@dataclass
class ValidationIssue:
    field: str
    message: str


@dataclass
class PublishValidationResult:
    valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.valid:
            parts = [f"{e.field}: {e.message}" for e in self.errors]
            raise PublishValidationError("; ".join(parts))


def validate_article_v1_publish(
    *,
    document: ParsedDocument,
    project: Project | None,
    target: PublishTarget,
    seo: SeoMetadata | None,
    payload: dict[str, Any] | None = None,
) -> PublishValidationResult:
    errors: list[ValidationIssue] = []

    if not project:
        errors.append(ValidationIssue("project", "Project is required"))
    elif not project.enabled:
        errors.append(ValidationIssue("project", "Project is disabled"))

    if not target.enabled:
        errors.append(ValidationIssue("target", "Publish target is disabled"))

    if not document.rewritten_text or not document.rewritten_text.strip():
        errors.append(ValidationIssue("rewritten_text", "Rewritten text is required"))
    elif len(document.rewritten_text.strip()) < MIN_CONTENT_CHARS:
        errors.append(
            ValidationIssue(
                "rewritten_text",
                f"Content too short (min {MIN_CONTENT_CHARS} chars)",
            )
        )

    if not seo:
        errors.append(ValidationIssue("seo_metadata", "SEO metadata is required"))
    else:
        if not seo.slug or not str(seo.slug).strip():
            errors.append(ValidationIssue("slug", "Slug must not be empty"))

    title = (payload or {}).get("title") or (seo.seo_title if seo else "") or ""
    if not str(title).strip():
        errors.append(ValidationIssue("title", "Title must not be empty"))
    elif len(str(title)) > MAX_TITLE_LEN:
        errors.append(ValidationIssue("title", f"Title exceeds {MAX_TITLE_LEN} characters"))

    md = (payload or {}).get("content_markdown") or document.rewritten_text or ""
    if not str(md).strip():
        errors.append(ValidationIssue("content_markdown", "Markdown content must not be empty"))

    if payload and payload.get("payload_version") != PAYLOAD_VERSION:
        errors.append(
            ValidationIssue("payload_version", f"Expected {PAYLOAD_VERSION}")
        )

    return PublishValidationResult(valid=len(errors) == 0, errors=errors)


def validate_review_for_publish(
    *,
    project: Project,
    review: ReviewResult | None,
    review_meta: dict[str, Any],
    force: bool,
) -> PublishValidationResult:
    errors: list[ValidationIssue] = []
    min_score = project.minimum_review_score_for_publish or 60
    require_take = project.require_review_take_for_publish

    take = review.take if review is not None else review_meta.get("take")
    score = review.score if review is not None else review_meta.get("score")

    if require_take and not force:
        if take is False:
            errors.append(ValidationIssue("review_take", "Review rejected (take=false)"))
        elif take is None and not review and not review_meta:
            errors.append(ValidationIssue("review_take", "Review result required before publish"))

    if score is not None and not force:
        try:
            if int(score) < min_score:
                errors.append(
                    ValidationIssue(
                        "review_score",
                        f"Score {score} below minimum {min_score}",
                    )
                )
        except (TypeError, ValueError):
            errors.append(ValidationIssue("review_score", "Invalid review score"))

    return PublishValidationResult(valid=len(errors) == 0, errors=errors)


def validate_quality_for_publish(
    *,
    quality_enabled: bool,
    quality_score: Any | None,
    min_score: int,
    max_spamminess: int = 70,
    force: bool,
) -> PublishValidationResult:
    errors: list[ValidationIssue] = []
    if not quality_enabled or force:
        return PublishValidationResult(valid=True, errors=errors)

    if not quality_score:
        errors.append(
            ValidationIssue("quality_score", "Quality review required before publish")
        )
        return PublishValidationResult(valid=False, errors=errors)

    verdict = getattr(quality_score, "verdict", None) or ""
    if verdict != "approved":
        errors.append(
            ValidationIssue(
                "quality_verdict",
                f"Quality verdict is {verdict!r}, expected approved",
            )
        )

    overall = getattr(quality_score, "overall_score", None)
    if overall is not None:
        try:
            if int(overall) < min_score:
                errors.append(
                    ValidationIssue(
                        "quality_overall_score",
                        f"Overall score {overall} below minimum {min_score}",
                    )
                )
        except (TypeError, ValueError):
            errors.append(ValidationIssue("quality_overall_score", "Invalid overall score"))

    spam = getattr(quality_score, "spamminess_score", None)
    if spam is not None:
        try:
            if int(spam) > max_spamminess:
                errors.append(
                    ValidationIssue(
                        "quality_spamminess",
                        f"Spamminess {spam} exceeds maximum {max_spamminess}",
                    )
                )
        except (TypeError, ValueError):
            pass

    return PublishValidationResult(valid=len(errors) == 0, errors=errors)
