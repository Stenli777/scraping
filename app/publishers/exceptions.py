class PublishError(Exception):
    """Base publish layer error."""


class PublishValidationError(PublishError):
    """Pre-flight validation failed — no HTTP attempt."""


class PublishAuthError(PublishError):
    """Missing or invalid auth configuration."""


class PublishTransportError(PublishError):
    """Network/timeout — retryable."""


class PublishClientError(PublishError):
    """HTTP 4xx — terminal."""


class PublishServerError(PublishError):
    """HTTP 5xx — retryable."""


class PublishDuplicateError(PublishError):
    """Successful publish already exists for document+target+payload version."""

    def __init__(self, message: str, *, existing_publish_run_id: int | None = None):
        super().__init__(message)
        self.existing_publish_run_id = existing_publish_run_id



class PublishUnsupportedPayloadError(PublishError):
    """Target does not support requested payload version ? terminal."""
