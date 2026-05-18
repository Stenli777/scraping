"""Topic extraction orchestration: deterministic -> optional LLM -> strategy gate."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_llm_topic_cleanup_enabled
from app.models.parsed_document import ParsedDocument
from app.models.seo_metadata import SeoMetadata
from app.services.project_profile_service import build_profile_context, resolve_task_project
from app.services.strategy_gate_service import apply_strategy_gate, merge_llm_topic_cleanup
from app.services.topic_quality_service import TOPIC_SCHEMA_VERSION, build_topic_extraction_v2

logger = logging.getLogger(__name__)


def resolve_use_llm_cleanup(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return is_llm_topic_cleanup_enabled()


def run_llm_topic_cleanup(
    db: Session,
    *,
    document: ParsedDocument,
    project_id: int | None,
    deterministic: dict[str, Any],
    title: str,
    seo_title: str,
    seo_description: str,
    tags: list[str],
    content_excerpt: str,
    profile_context: str,
) -> tuple[dict[str, Any] | None, int | None, str, list[str]]:
    from app.services.llm_tasks import run_json_prompt

    settings = get_settings()
    warnings: list[str] = []
    if not is_llm_topic_cleanup_enabled():
        return None, None, "disabled", ["llm_cleanup_disabled"]

    if not settings.cliproxyapi_base_url.strip():
        return None, None, "skipped", ["llm_cleanup_skipped"]

    context = {
        "profile_block": f"Профиль проекта:\n{profile_context.strip()}\n" if profile_context.strip() else "",
        "title": title,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "tags": json.dumps(tags, ensure_ascii=False),
        "content_excerpt": content_excerpt[:3000],
        "deterministic_json": json.dumps(deterministic, ensure_ascii=False),
        "rejected_terms": json.dumps(deterministic.get("rejected_terms") or [], ensure_ascii=False),
    }
    result = run_json_prompt(
        db,
        prompt_key="topic_cleanup_v1",
        model_alias=settings.topic_cleanup_model_alias,
        context=context,
        project_id=project_id,
        task_id=document.task_id,
        document_id=document.id,
    )
    if result.success and result.data:
        return result.data, result.llm_run_id, "applied", ["llm_cleanup_applied"] + list(result.warnings)

    warnings.append("llm_cleanup_failed")
    if result.error_message:
        logger.info("LLM topic cleanup failed doc=%s: %s", document.id, result.error_message)
    return None, result.llm_run_id, "failed", warnings


def extract_topics_for_document(
    db: Session,
    document_id: int,
    *,
    persist_audit: bool = True,
    use_llm_cleanup: bool | None = None,
) -> dict[str, Any]:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")

    seo = db.scalar(
        select(SeoMetadata)
        .where(SeoMetadata.document_id == document_id)
        .order_by(SeoMetadata.id.desc())
    )
    meta = document.metadata_json or {}
    title = (
        (seo.h1 if seo else None)
        or (seo.seo_title if seo else None)
        or meta.get("extracted_title")
        or meta.get("title")
        or ""
    )
    tags = list((seo.tags_json if seo else None) or [])
    text_sample = (document.rewritten_text or document.clean_text or "")[:2000]
    slug = (seo.slug if seo else None) or ""

    project_slug = None
    project_id = None
    profile_context = ""
    if document.task:
        project = resolve_task_project(db, document.task)
        if project:
            project_slug = project.slug
            project_id = project.id
            profile_context = build_profile_context(project)

    use_llm = resolve_use_llm_cleanup(use_llm_cleanup)
    deterministic = build_topic_extraction_v2(
        title=title,
        tags=tags,
        text_sample=text_sample,
        project_slug=project_slug,
        use_llm_cleanup=False,
    )

    llm_data: dict[str, Any] | None = None
    llm_run_id: int | None = None
    llm_status = "skipped"
    warnings = list(deterministic.get("warnings") or [])

    if not use_llm:
        warnings.append("llm_cleanup_disabled")
    else:
        llm_data, llm_run_id, llm_status, llm_warnings = run_llm_topic_cleanup(
            db,
            document=document,
            project_id=project_id,
            deterministic=deterministic,
            title=title,
            seo_title=(seo.seo_title if seo else "") or "",
            seo_description=(seo.seo_description if seo else "") or "",
            tags=tags,
            content_excerpt=text_sample,
            profile_context=profile_context,
        )
        warnings.extend(llm_warnings)

    merged = merge_llm_topic_cleanup(deterministic, llm_data)
    if llm_data:
        if llm_data.get("strategy_allowed") is False:
            merged["strategy_allowed"] = False
            merged["strategy_block_reason"] = llm_data.get("strategy_block_reason")

    final = apply_strategy_gate(
        db,
        document=document,
        extraction=merged,
        title=title,
        text_sample=text_sample,
        slug=slug,
    )
    final["warnings"] = list(dict.fromkeys(warnings + list(final.get("warnings") or [])))
    final["extracted_at"] = datetime.now(timezone.utc).isoformat()
    final["payload_version"] = "topic_v2"
    final["schema_version"] = TOPIC_SCHEMA_VERSION
    final["llm_cleanup_status"] = llm_status
    final["llm_run_id"] = llm_run_id
    final["topic_cleanup_model_alias"] = get_settings().topic_cleanup_model_alias

    if persist_audit:
        meta = dict(document.metadata_json or {})
        audit_entry = {
            "schema_version": TOPIC_SCHEMA_VERSION,
            "deterministic_result": deterministic,
            "llm_cleanup_result": llm_data,
            "final_result": final,
            "llm_run_id": llm_run_id,
            "strategy_allowed": final.get("strategy_allowed"),
            "strategy_block_reason": final.get("strategy_block_reason"),
            "created_at": final["extracted_at"],
        }
        audits = list(meta.get("topic_extractions") or [])
        audits.append(audit_entry)
        meta["topic_extractions"] = audits[-20:]
        meta["topics"] = final
        document.metadata_json = meta
        db.flush()

        if document.task_id:
            from app.services.pipeline_event_service import emit_pipeline_event

            status = "completed"
            emit_pipeline_event(
                db,
                document.task_id,
                "topic_extraction",
                status=status,
                payload={
                    "document_id": document_id,
                    "relevance_score": final.get("relevance_score"),
                    "project_fit": final.get("project_fit"),
                    "strategy_allowed": final.get("strategy_allowed"),
                    "strategy_block_reason": final.get("strategy_block_reason"),
                    "llm_cleanup_status": llm_status,
                },
            )

    return final
