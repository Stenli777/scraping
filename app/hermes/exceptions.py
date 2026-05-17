"""Hermes connector errors — isolated from Scrap pipeline."""


class HermesError(Exception):
    """Base Hermes connector error."""


class HermesDisabledError(HermesError):
    """Hermes integration disabled via feature flags."""


class HermesUnavailableError(HermesError):
    """Hermes HTTP endpoint unreachable or unhealthy."""


class HermesTimeoutError(HermesError):
    """Hermes request timed out."""


class HermesResponseError(HermesError):
    """Hermes returned an error or invalid payload."""
