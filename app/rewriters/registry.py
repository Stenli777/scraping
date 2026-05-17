from app.core.config import get_settings
from app.rewriters.base import BaseRewriter
from app.rewriters.cliproxy_rewriter import CLIProxyRewriter
from app.rewriters.lm_studio_rewriter import LMStudioRewriter
from app.rewriters.mock_rewriter import MockRewriter


def get_rewriter() -> BaseRewriter:
    provider = get_settings().rewriter_provider.lower()
    mapping: dict[str, BaseRewriter] = {
        "mock": MockRewriter(),
        "cliproxy": CLIProxyRewriter(),
        "lm_studio": LMStudioRewriter(),
    }
    rewriter = mapping.get(provider)
    if not rewriter:
        raise ValueError(f"Unknown rewriter provider: {provider}")
    return rewriter
