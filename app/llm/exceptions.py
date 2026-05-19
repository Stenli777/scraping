class LLMError(Exception):
    """Base LLM layer error."""


class ModelRoutingError(LLMError):
    """Unknown or invalid model alias."""


class ProviderError(LLMError):
    """Upstream provider failure."""


class RateLimitError(ProviderError):
    """HTTP 429 / rate limit — retry with cooldown."""


class BadRequestError(ProviderError):
    """HTTP 400 — payload/model issue; may need truncation."""
