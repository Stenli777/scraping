from enum import Enum


class TaskStatus(str, Enum):
    QUEUED = "queued"
    FETCHING = "fetching"
    PARSING = "parsing"
    CLEANING = "cleaning"
    REWRITING = "rewriting"
    SAVING = "saving"
    DONE = "done"
    ERROR = "error"


class ParserType(str, Enum):
    GENERIC_ARTICLE = "generic_article"
    BITRIX_ARTICLE = "bitrix_article"
    HABR_ARTICLE = "habr_article"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ExportType(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
