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


class DiscoverySource(str, Enum):
    SITEMAP = "sitemap"
    HTML_LINK = "html_link"
    MANUAL = "manual"


class DiscoveryMode(str, Enum):
    SITEMAP = "sitemap"
    HTML_LINKS = "html_links"
    MIXED = "mixed"
    MANUAL = "manual"
