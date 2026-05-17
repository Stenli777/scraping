import logging

from sqlalchemy.orm import Session

from app.llm.schemas import RewriteRequest
from app.rewriters.base import BaseRewriter
from app.services.llm_tasks import execute_rewrite

logger = logging.getLogger(__name__)

DEFAULT_REWRITE_ALIAS = "local/rewrite-main"


class CLIProxyRewriter(BaseRewriter):
    """Rewrite via LLM layer + CLIProxyAPI."""

    provider_name = "cliproxy"

    def __init__(self, db: Session | None = None, model_alias: str = DEFAULT_REWRITE_ALIAS):
        self.db = db
        self.model_alias = model_alias

    def rewrite(self, text: str, metadata: dict | None = None) -> str:
        if not self.db:
            raise RuntimeError("CLIProxyRewriter requires DB session for llm_runs audit")

        meta = metadata or {}
        request = RewriteRequest(
            task_id=meta.get("task_id"),
            project_id=meta.get("project_id"),
            content=text,
            model_alias=meta.get("model_alias") or self.model_alias,
            metadata=meta,
        )
        response = execute_rewrite(self.db, request)
        if response.status != "ok":
            raise RuntimeError("; ".join(response.warnings) or "Rewrite failed")
        return response.rewritten_text
