from enum import Enum


class TaskStatus(str, Enum):
    QUEUED = "queued"
    FETCHING = "fetching"
    PARSING = "parsing"
    CLEANING = "cleaning"
    REVIEWING = "reviewing"
    REWRITING = "rewriting"
    SEO_ENRICHING = "seo_enriching"
    SAVING = "saving"
    DONE = "done"
    FAILED_RETRYABLE = "failed_retryable"
    ERROR = "error"


class ParserType(str, Enum):
    GENERIC_ARTICLE = "generic_article"
    SALTPRO_ARTICLE = "saltpro_article"
    SOTBIT_ARTICLE = "sotbit_article"
    HABR_ARTICLE = "habr_article"
    BITRIX_ARTICLE = "bitrix_article"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ExportType(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


class PublishRunStatus(str, Enum):
    PENDING = "pending"
    DRY_RUN = "dry_run"
    SUCCESS = "success"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


class DiscoveredUrlStatus(str, Enum):
    DISCOVERED = "discovered"
    DUPLICATE = "duplicate"
    IGNORED = "ignored"
    ENQUEUED = "enqueued"
    FAILED = "failed"
    BLOCKED = "blocked"
    QUALITY_PENDING = "quality_pending"
    QUALITY_SCORED = "quality_scored"
    QUALITY_BLOCKED = "quality_blocked"
    MANUALLY_APPROVED = "manually_approved"


class DiscoverySource(str, Enum):
    SITEMAP = "sitemap"
    HTML_LINK = "html_link"
    MANUAL = "manual"


class DiscoveryMode(str, Enum):
    SITEMAP = "sitemap"
    HTML_LINKS = "html_links"
    MIXED = "mixed"
    MANUAL = "manual"


class QualityVerdict(str, Enum):
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class EditorialStatus(str, Enum):
    GENERATED = "generated"
    NEEDS_REVISION = "needs_revision"
    OPERATOR_REVIEW = "operator_review"
    APPROVED = "approved"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED_DRAFT = "published_draft"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class RevisionSourceType(str, Enum):
    REWRITE = "rewrite"
    MANUAL = "manual"
    SEO_UPDATE = "seo_update"
    QUALITY_UPDATE = "quality_update"
    PUBLISH_SNAPSHOT = "publish_snapshot"
