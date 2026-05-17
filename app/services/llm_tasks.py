"""Thin LLM task executors — typed requests, audit logging."""

import logging

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.exceptions import LLMError
from app.llm.json_utils import parse_llm_json
from app.llm.schemas import (
    ReviewRequest,
    ReviewResponse,
    RewriteRequest,
    RewriteResponse,
    SeoEnrichRequest,
    SeoEnrichResponse,
)
from app.services.llm_run_service import record_llm_run
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)


def _extract_title_from_markdown(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _profile_block(profile_context: str | None) -> str:
    if not profile_context or not profile_context.strip():
        return ""
    return f"Профиль проекта:\n{profile_context.strip()}\n"


def execute_rewrite(
    db: Session, request: RewriteRequest, profile_context: str | None = None
) -> RewriteResponse:
    if not request.model_alias or not request.model_alias.strip():
        return RewriteResponse(
            success=False,
            status="error",
            error_message="model_alias is required",
            warnings=["model_alias is required"],
            model_alias="",
        )

    ctx = profile_context or request.metadata.get("profile_context")
    context = {
        "language": request.language,
        "profile_block": _profile_block(ctx),
        "source_url": request.source_url or "не указан",
        "title": request.title or "Без названия",
        "content": request.content.strip(),
    }
    messages, resolved = render_prompt(
        db, "rewrite_article", context, project_id=request.project_id
    )
    client = LLMClient()

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
            prompt_template=resolved.template_ref,
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
                "llm_run_id": run.id,
                "prompt_template": resolved.template_ref,
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
            prompt_template=resolved.template_ref,
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
    if not request.model_alias:
        return ReviewResponse(
            success=False,
            error_message="model_alias is required",
            warnings=["model_alias is required"],
        )

    ctx = request.profile_context or request.metadata.get("profile_context")
    context = {
        "profile_block": _profile_block(ctx),
        "source_url": request.source_url or "не указан",
        "title": request.title or "Без названия",
        "content": request.content.strip()[:12000],
    }
    messages, resolved = render_prompt(
        db, "review_article", context, project_id=request.project_id
    )
    client = LLMClient()

    try:
        result = client.complete(model_alias=request.model_alias, messages=messages)
        data = parse_llm_json(result.content)
        take = bool(data.get("take", data.get("approved", False)))
        score = int(data.get("score", 0))
        risks = data.get("risks") or []
        if not isinstance(risks, list):
            risks = [str(risks)]

        run = record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=result.upstream_model,
            prompt_template=resolved.template_ref,
            result=result,
            success=True,
        )
        db.commit()

        return ReviewResponse(
            success=True,
            status="ok",
            take=take,
            score=score,
            reason=str(data.get("reason", "")),
            target_project=data.get("target_project"),
            recommended_angle=data.get("recommended_angle"),
            content_type=data.get("content_type"),
            risks=[str(r) for r in risks],
            model_alias=request.model_alias,
            upstream_model=result.upstream_model,
            fallback_used=result.fallback_used,
            metadata={"llm_run_id": run.id, "raw": data, "prompt_template": resolved.template_ref},
        )
    except (LLMError, ValueError) as exc:
        logger.warning("Review failed task_id=%s: %s", request.task_id, exc)
        record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=request.model_alias,
            prompt_template=resolved.template_ref,
            success=False,
            error_message=str(exc),
        )
        db.commit()
        return ReviewResponse(
            success=False,
            status="error",
            model_alias=request.model_alias,
            error_message=str(exc),
            warnings=[str(exc)],
        )


def execute_seo_enrich(db: Session, request: SeoEnrichRequest) -> SeoEnrichResponse:
    if not request.model_alias:
        return SeoEnrichResponse(
            success=False,
            error_message="model_alias is required",
            warnings=["model_alias is required"],
        )

    ctx = request.profile_context or request.metadata.get("profile_context")
    context = {
        "profile_block": _profile_block(ctx),
        "source_url": request.source_url or "не указан",
        "title": request.title or "Без названия",
        "content": request.content.strip()[:12000],
    }
    messages, resolved = render_prompt(
        db, "seo_enrich", context, project_id=request.project_id
    )
    client = LLMClient()

    try:
        result = client.complete(model_alias=request.model_alias, messages=messages)
        data = parse_llm_json(result.content)
        faq = data.get("faq") or []
        if not isinstance(faq, list):
            faq = []
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]

        run = record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=result.upstream_model,
            prompt_template=resolved.template_ref,
            result=result,
            success=True,
        )
        db.commit()

        return SeoEnrichResponse(
            success=True,
            status="ok",
            seo_title=str(data.get("seo_title") or ""),
            seo_description=str(data.get("seo_description") or ""),
            h1=str(data.get("h1") or ""),
            slug=str(data.get("slug") or ""),
            excerpt=str(data.get("excerpt") or ""),
            tags=[str(t) for t in tags],
            faq=faq,
            suggested_category=str(data.get("suggested_category") or ""),
            model_alias=request.model_alias,
            upstream_model=result.upstream_model,
            fallback_used=result.fallback_used,
            metadata={"llm_run_id": run.id, "prompt_template": resolved.template_ref},
        )
    except (LLMError, ValueError) as exc:
        logger.warning("SEO enrich failed task_id=%s: %s", request.task_id, exc)
        record_llm_run(
            db,
            task_id=request.task_id,
            project_id=request.project_id,
            model_alias=request.model_alias,
            upstream_model=request.model_alias,
            prompt_template=resolved.template_ref,
            success=False,
            error_message=str(exc),
        )
        db.commit()
        return SeoEnrichResponse(
            success=False,
            status="error",
            model_alias=request.model_alias,
            error_message=str(exc),
            warnings=[str(exc)],
        )
