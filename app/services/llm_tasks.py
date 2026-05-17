"""Thin LLM task executors — typed requests, audit logging."""

import logging

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.exceptions import LLMError
from app.llm.schemas import RewriteRequest, RewriteResponse, ReviewRequest, ReviewResponse
from app.services.llm_run_service import record_llm_run

logger = logging.getLogger(__name__)

REWRITE_TEMPLATE = "rewrite_article_v1"
REVIEW_TEMPLATE = "review_article_v1"


def execute_rewrite(db: Session, request: RewriteRequest) -> RewriteResponse:
    client = LLMClient()
    messages = [
        {
            "role": "user",
            "content": (
                "Перепиши текст статьи для публикации. Сохрани смысл, улучши структуру.\n\n"
                f"{request.content}"
            ),
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
            prompt_template=REWRITE_TEMPLATE,
            result=result,
            success=True,
        )
        db.commit()
        return RewriteResponse(
            status="ok",
            content=result.content,
            rewritten_text=result.content,
            metadata={"upstream_model": result.upstream_model, **request.metadata},
        )
    except LLMError as exc:
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
        return RewriteResponse(status="error", warnings=[str(exc)])


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
        return ReviewResponse(status="error", warnings=[str(exc)])
