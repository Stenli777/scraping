class LLMError(Exception):
    """Base LLM layer error."""


class ModelRoutingError(LLMError):
    """Unknown or invalid model alias."""


class ProviderError(LLMError):
    """Upstream provider failure."""
