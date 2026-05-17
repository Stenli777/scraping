from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoute:
    """Resolved route: alias → upstream model + optional fallback."""

    alias: str
    upstream_model: str
    fallback_upstream_model: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class CompletionResult:
    content: str
    upstream_model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    finish_reason: str | None
    fallback_used: bool
