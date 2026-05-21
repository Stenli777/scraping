from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.rewriters.base import BaseRewriter
from app.rewriters.cliproxy_rewriter import CLIProxyRewriter
from app.rewriters.mock_rewriter import MockRewriter


def get_rewriter(db: Session | None = None) -> BaseRewriter:
    provider = get_settings().rewriter_provider.lower()
    if provider == "cliproxy":
        if db is None:
            raise ValueError("cliproxy rewriter requires database session")
        return CLIProxyRewriter(db=db)
    if provider == "mock":
        return MockRewriter()
    raise ValueError(
        f"Unknown rewriter provider: {provider}. Use mock or cliproxy. "
        "(lm_studio is deprecated and not registered)."
    )
