"""Content quality review — manual-first editorial scoring."""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import QualityVerdict
from app.core.feature_flags import is_quality_review_enabled
from app.core.pipeline_states import PipelineStage
from app.llm.client import LLMClient
from app.llm.exceptions import LLMError
from app.llm.json_utils import parse_llm_json
from app.models.content_quality_score import ContentQualityScore
from app.models.parsed_document import ParsedDocument
from app.models.seo_metadata import SeoMetadata
from app.services.llm_run_service import record_llm_run
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.project_profile_service import build_review_context, resolve_task_project
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)

MAX_SPAM_SCORE = 70


@dataclass
class QualityStageResult:
    success: bool
    skipped: bool = False
    quality_score_id: int | None = None
    llm_run_id: int | None = None
    overall_score: int = 0
    verdict: str = ""
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)


def _latest_seo(db: Session, document_id: int) -> SeoMetadata | None:
    return db.scalar(
        select(SeoMetadata)
        .where(SeoMetadata.document_id == document_id)
        .order_by(SeoMetadata.id.desc())
    )


def get_latest_quality_score(db: Session, document_id: int) -> ContentQualityScore | None:
    return db.scalar(
        select(ContentQualityScore)
        .where(ContentQualityScore.document_id == document_id)
        .order_by(ContentQualityScore.id.desc())
    )


def run_quality_for_document(db: Session, document_id: int) -> QualityStageResult:
    if not is_quality_review_enabled():
        return QualityStageResult(
            success=False,
            skipped=True,
            error_message="Quality review is disabled (ENABLE_QUALITY_REVIEW=false)",
        )

    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    if not document.rewritten_text or not document.rewritten_text.strip():
        raise ValueError("Document has no rewritten_text for quality review")

    task = document.task
    if not task:
        raise ValueError("Document has no associated task")

    project = resolve_task_project(db, task)
    seo = _latest_seo(db, document_id)

    emit_pipeline_event(
        db,
        task.id,
        PipelineStage.QUALITY_REVIEW,
        status="entered",
        payload={"document_id": document_id},
    )

    settings = get_settings()
    model_alias = settings.quality_model_alias
    profile_block = build_review_context(project) if project else ""
    if profile_block:
        profile_block = f"Профиль проекта:\n{profile_block.strip()}\n"

    context = {
        "profile_block": profile_block,
        "source_url": document.source_url or "не указан",
        "seo_title": (seo.seo_title if seo else "") or "",
        "slug": (seo.slug if seo else "") or "",
        "content": document.rewritten_text.strip()[:16000],
    }

    messages, resolved = render_prompt(
        db, "quality_review", context, project_id=task.project_id
    )
    client = LLMClient()

    try:
        result = client.complete(model_alias=model_alias, messages=messages)
        data = parse_llm_json(result.content)
        verdict = str(data.get("verdict", QualityVerdict.NEEDS_REVISION.value))
        if verdict not in {v.value for v in QualityVerdict}:
            verdict = QualityVerdict.NEEDS_REVISION.value

        run = record_llm_run(
            db,
            task_id=task.id,
            project_id=task.project_id,
            model_alias=model_alias,
            upstream_model=result.upstream_model,
            prompt_template=resolved.template_ref,
            result=result,
            success=True,
        )

        record = ContentQualityScore(
            document_id=document.id,
            task_id=task.id,
            project_id=task.project_id,
            llm_run_id=run.id,
            overall_score=int(data.get("overall_score", 0)),
            readability_score=_int_or_none(data.get("readability_score")),
            seo_score=_int_or_none(data.get("seo_score")),
            factual_consistency_score=_int_or_none(data.get("factual_consistency_score")),
            structure_score=_int_or_none(data.get("structure_score")),
            usefulness_score=_int_or_none(data.get("usefulness_score")),
            spamminess_score=_int_or_none(data.get("spamminess_score")),
            risks_json=_as_list(data.get("risks")),
            recommendations_json=_as_list(data.get("recommendations")),
            verdict=verdict,
        )
        db.add(record)
        meta = dict(document.metadata_json or {})
        meta["quality"] = {
            "quality_score_id": None,
            "overall_score": record.overall_score,
            "verdict": record.verdict,
            "llm_run_id": run.id,
            "prompt_template": resolved.template_ref,
        }
        document.metadata_json = meta
        db.flush()
        meta["quality"]["quality_score_id"] = record.id
        document.metadata_json = meta

        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.QUALITY_REVIEW,
            status="completed",
            payload={
                "quality_score_id": record.id,
                "verdict": record.verdict,
                "overall_score": record.overall_score,
            },
        )
        db.commit()
        db.refresh(record)

        return QualityStageResult(
            success=True,
            quality_score_id=record.id,
            llm_run_id=run.id,
            overall_score=record.overall_score,
            verdict=record.verdict,
            risks=record.risks_json or [],
            recommendations=record.recommendations_json or [],
            metadata={"prompt_template": resolved.template_ref},
        )

    except (LLMError, ValueError) as exc:
        logger.warning("Quality review failed document=%s: %s", document_id, exc)
        record_llm_run(
            db,
            task_id=task.id,
            project_id=task.project_id,
            model_alias=model_alias,
            upstream_model=model_alias,
            prompt_template=resolved.template_ref,
            success=False,
            error_message=str(exc),
        )
        emit_pipeline_event(
            db,
            task.id,
            PipelineStage.FAILED_RETRYABLE,
            status="entered",
            payload={"reason": "quality_review", "error": str(exc)},
        )
        db.commit()
        return QualityStageResult(
            success=False,
            error_message=str(exc),
            metadata={"retryable": True},
        )


def _int_or_none(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _as_list(val) -> list:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    return [str(val)]
