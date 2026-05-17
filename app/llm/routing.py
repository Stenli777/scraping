"""Explicit model alias routing — no implicit defaults."""

from app.llm.exceptions import ModelRoutingError
from app.llm.models import ModelRoute

# alias → (upstream CLIProxy model alias, fallback, role)
_ROUTE_TABLE: dict[str, tuple[str, str | None, str]] = {
    "local/classifier-fast": ("glm-4.5-air-free", None, "classifier"),
    "local/extractor-fast": ("glm-4.5-air-free", None, "extractor"),
    "local/rewrite-main": ("gpt-oss-120b-free", "qwen3-coder-next", "rewrite"),
    "local/seo-main": ("glm-4.5-air-free", None, "seo"),
    "local/qc-reviewer": ("glm-4.5-air-free", None, "review"),
    "local/code-agent": ("qwen3-coder-next", None, "code"),
    "local/reasoning-main": ("hermes-4-70b", "gpt-oss-120b-free", "reasoning"),
    "hermes-default": ("gpt-oss-120b-free", "qwen3-coder-next", "default"),
    "hermes-cheap": ("glm-4.5-air-free", None, "cheap"),
    "hermes-code": ("qwen3-coder-next", None, "code"),
    "hermes-smart": ("hermes-4-70b", None, "smart"),
    "hermes-long": ("gpt-oss-120b-free", None, "long"),
    "hermes-long-smart": ("hermes-4-70b", "gpt-oss-120b-free", "long-smart"),
}


def resolve_route(model_alias: str) -> ModelRoute:
    if not model_alias or not model_alias.strip():
        raise ModelRoutingError("model_alias is required — no default model")
    alias = model_alias.strip()
    entry = _ROUTE_TABLE.get(alias)
    if not entry:
        raise ModelRoutingError(f"Unknown model alias: {alias}")
    upstream, fallback, role = entry
    return ModelRoute(
        alias=alias,
        upstream_model=upstream,
        fallback_upstream_model=fallback,
        role=role,
    )


def list_aliases() -> list[str]:
    return sorted(_ROUTE_TABLE.keys())