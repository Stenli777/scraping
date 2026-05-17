import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.schemas import RewriteRequest
from app.rewriters.base import BaseRewriter
from app.services.llm_tasks import execute_rewrite

logger = logging.getLogger(__name__)


class CLIProxyRewriter(BaseRewriter):
    """Rewrite via LLM layer + CLIProxyAPI (OpenAI-compatible only)."""

    provider_name = "cliproxy"

    def __init__(self, db: Session | None = None, model_alias: str | None = None):
        self.db = db
        self.model_alias = model_alias or get_settings().rewrite_model_alias

    def rewrite(self, text: str, metadata: dict | None = None) -> str:
        if not self.db:
            raise RuntimeError("CLIProxyRewriter requires DB session for llm_runs audit")

        meta = metadata or {}
        request = RewriteRequest(
            task_id=meta.get("task_id"),
            project_id=meta.get("project_id"),
            source_url=meta.get("source_url"),
            title=meta.get("title") or meta.get("extracted_title"),
            content=text,
            model_alias=meta.get("model_alias") or self.model_alias,
            language=meta.get("language", "ru"),
            metadata=meta,
        )
        response = execute_rewrite(self.db, request)
        if not response.success:
            msg = response.error_message or "; ".join(response.warnings) or "Rewrite failed"
            raise RuntimeError(msg)
        return response.rewritten_content
