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
