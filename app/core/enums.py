from enum import Enum


class TaskStatus(str, Enum):
    QUEUED = "queued"
    FETCHING = "fetching"
    PARSING = "parsing"
    CLEANING = "cleaning"
    REWRITING = "rewriting"
    SAVING = "saving"
    DONE = "done"
    FAILED_RETRYABLE = "failed_retryable"
    ERROR = "error"


class ParserType(str, Enum):
    GENERIC_ARTICLE = "generic_article"
    SALTPRO_ARTICLE = "saltpro_article"
    SOTBIT_ARTICLE = "sotbit_article"
    HABR_ARTICLE = "habr_article"
    BITRIX_ARTICLE = "bitrix_article"  # alias → sotbit


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ExportType(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
