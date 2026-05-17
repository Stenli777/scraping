"""Thin LLM task executors — typed requests, audit logging."""

import logging
import re

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.exceptions import LLMError
from app.llm.prompts import REWRITE_ARTICLE_V1, build_rewrite_messages
from app.llm.schemas import RewriteRequest, RewriteResponse, ReviewRequest, ReviewResponse
from app.services.llm_run_service import record_llm_run

logger = logging.getLogger(__name__)

REWRITE_TEMPLATE = REWRITE_ARTICLE_V1
REVIEW_TEMPLATE = "review_article_v1"


def _extract_title_from_markdown(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def execute_rewrite(db: Session, request: RewriteRequest) -> RewriteResponse:
    if not request.model_alias or not request.model_alias.strip():
        return RewriteResponse(
            success=False,
            status="error",
            error_message="model_alias is required",
            warnings=["model_alias is required"],
            model_alias="",
        )

    client = LLMClient()
    messages = build_rewrite_messages(request)

    try:
        result = client.complete(model_alias=request.model_alias, messages=messages)
        content = result.content.strip()
        title = _extract_title_from_markdown(content) or request.title or ""

        run = record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=result.upstream_model,
            prompt_template=REWRITE_TEMPLATE,
            result=result,
            success=True,
        )
        db.commit()

        return RewriteResponse(
            success=True,
            status="ok",
            content=content,
            rewritten_title=title,
            rewritten_content=content,
            rewritten_text=content,
            model_alias=request.model_alias,
            upstream_model=result.upstream_model,
            fallback_used=result.fallback_used,
            metadata={
                "upstream_model": result.upstream_model,
                "prompt_template": REWRITE_TEMPLATE,
                "finish_reason": result.finish_reason,
                "llm_run_id": run.id,
                **request.metadata,
            },
        )
    except LLMError as exc:
        logger.warning("Rewrite failed task_id=%s: %s", request.task_id, exc)
        record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=request.model_alias,
            prompt_template=REWRITE_TEMPLATE,
            success=False,
            error_message=str(exc),
        )
        db.commit()
        return RewriteResponse(
            success=False,
            status="error",
            model_alias=request.model_alias,
            error_message=str(exc),
            warnings=[str(exc)],
        )


def execute_review(db: Session, request: ReviewRequest) -> ReviewResponse:
    client = LLMClient()
    criteria = request.criteria or "Проверь качество текста для публикации."
    messages = [
        {
            "role": "user",
            "content": f"{criteria}\n\nОтветь JSON: approved, score, notes.\n\n{request.content}",
        }
    ]
    try:
        result = client.complete(model_alias=request.model_alias, messages=messages)
        record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=result.upstream_model,
            prompt_template=REVIEW_TEMPLATE,
            result=result,
            success=True,
        )
        db.commit()
        return ReviewResponse(
            success=True,
            status="ok",
            content=result.content,
            approved=True,
            notes=result.content[:500],
            metadata={"upstream_model": result.upstream_model},
        )
    except LLMError as exc:
        record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=request.model_alias,
            prompt_template=REVIEW_TEMPLATE,
            success=False,
            error_message=str(exc),
        )
        db.commit()
        return ReviewResponse(
            success=False,
            status="error",
            warnings=[str(exc)],
            error_message=str(exc),
        )
