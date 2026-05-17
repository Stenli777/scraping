from enum import Enum


class PipelineStage(str, Enum):
    """Extended pipeline stages (foundation for multi-stage factory)."""

    DISCOVERED = "discovered"
    QUEUED = "queued"
    FETCHING = "fetching"
    FETCHED = "fetched"
    PARSING = "parsing"
    PARSED = "parsed"
    CLEANING = "cleaning"
    CLEANED = "cleaned"
    REVIEW_PENDING = "review_pending"
    REVIEW_REJECTED = "review_rejected"
    REWRITE_PENDING = "rewrite_pending"
    REWRITING = "rewriting"
    SEO_ENRICH_PENDING = "seo_enrich_pending"
    QUALITY_REVIEW = "quality_review"
    PUBLISHING = "publishing"
    PUBLISHED_DRAFT = "published_draft"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


_TRANSITIONS: dict[PipelineStage, set[PipelineStage]] = {
    PipelineStage.DISCOVERED: {PipelineStage.QUEUED, PipelineStage.FAILED_TERMINAL},
    PipelineStage.QUEUED: {PipelineStage.FETCHING, PipelineStage.FAILED_RETRYABLE},
    PipelineStage.FETCHING: {
        PipelineStage.FETCHED,
        PipelineStage.FAILED_RETRYABLE,
        PipelineStage.FAILED_TERMINAL,
    },
    PipelineStage.FETCHED: {PipelineStage.PARSING, PipelineStage.FAILED_RETRYABLE},
    PipelineStage.PARSING: {PipelineStage.PARSED, PipelineStage.FAILED_RETRYABLE},
    PipelineStage.PARSED: {PipelineStage.CLEANING, PipelineStage.FAILED_RETRYABLE},
    PipelineStage.CLEANING: {PipelineStage.CLEANED, PipelineStage.FAILED_RETRYABLE},
    PipelineStage.CLEANED: {
        PipelineStage.REVIEW_PENDING,
        PipelineStage.REWRITE_PENDING,
        PipelineStage.FAILED_RETRYABLE,
    },
    PipelineStage.REVIEW_PENDING: {
        PipelineStage.REVIEW_REJECTED,
        PipelineStage.REWRITE_PENDING,
        PipelineStage.FAILED_RETRYABLE,
    },
    PipelineStage.REVIEW_REJECTED: {PipelineStage.REWRITE_PENDING, PipelineStage.FAILED_TERMINAL},
    PipelineStage.REWRITE_PENDING: {PipelineStage.REWRITING, PipelineStage.FAILED_RETRYABLE},
    PipelineStage.REWRITING: {PipelineStage.SEO_ENRICH_PENDING, PipelineStage.FAILED_RETRYABLE},
    PipelineStage.SEO_ENRICH_PENDING: {
        PipelineStage.QUALITY_REVIEW,
        PipelineStage.PUBLISHING,
        PipelineStage.FAILED_RETRYABLE,
    },
    PipelineStage.QUALITY_REVIEW: {
        PipelineStage.PUBLISHING,
        PipelineStage.FAILED_RETRYABLE,
        PipelineStage.FAILED_TERMINAL,
    },
    PipelineStage.PUBLISHING: {
        PipelineStage.PUBLISHED_DRAFT,
        PipelineStage.FAILED_RETRYABLE,
        PipelineStage.FAILED_TERMINAL,
    },
    PipelineStage.PUBLISHED_DRAFT: {PipelineStage.FAILED_RETRYABLE},
    PipelineStage.FAILED_RETRYABLE: {
        PipelineStage.QUEUED,
        PipelineStage.FETCHING,
        PipelineStage.FAILED_TERMINAL,
    },
    PipelineStage.FAILED_TERMINAL: set(),
}


def can_transition(current: PipelineStage, target: PipelineStage) -> bool:
    if current == target:
        return True
    allowed = _TRANSITIONS.get(current, set())
    return target in allowed


def assert_transition(current: PipelineStage, target: PipelineStage) -> None:
    if not can_transition(current, target):
        raise ValueError(f"Invalid pipeline transition: {current.value} -> {target.value}")
