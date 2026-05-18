"""Async LLM enrichment jobs — queue, process, retry, merge."""

from __future__ import annotations

import json
import logging
import socket
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_llm_topic_cleanup_enabled
from app.llm.exceptions import LLMError
from app.models.llm_enrichment_job import (
    EnrichmentJobStatus,
    EnrichmentType,
    LlmEnrichmentJob,
)
from app.models.parsed_document import ParsedDocument
from app.models.seo_metadata import SeoMetadata
from app.services.project_profile_service import build_profile_context, resolve_task_project
from app.services.strategy_gate_service import apply_strategy_gate, merge_llm_topic_cleanup
from app.services.topic_quality_service import TOPIC_SCHEMA_VERSION

logger = logging.getLogger(__name__)

_WORKER_ID = f"{socket.gethostname()}:enrichment"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_seconds(retry_count: int) -> int:
    return min(300, 5 * (2 ** max(0, retry_count)))


def classify_enrichment_failure(error_message: str | None) -> str:
    msg = (error_message or "").lower()
    if any(x in msg for x in ("unsupported model", "invalid prompt", "unknown prompt", "model_alias is required")):
        return EnrichmentJobStatus.FAILED_TERMINAL
    if "disabled" in msg or "feature" in msg:
        return EnrichmentJobStatus.SKIPPED
    if any(x in msg for x in ("timeout", "429", "502", "503", "network", "http error", "connection")):
        return EnrichmentJobStatus.FAILED_RETRYABLE
    if "json" in msg or "malformed" in msg:
        return EnrichmentJobStatus.FAILED_RETRYABLE
    return EnrichmentJobStatus.FAILED_RETRYABLE


def timeout_for_enrichment(enrichment_type: str) -> int:
    settings = get_settings()
    if enrichment_type == EnrichmentType.TOPIC_CLEANUP:
        return settings.topic_cleanup_timeout_seconds
    if enrichment_type == EnrichmentType.SEO_CLEANUP:
        return settings.seo_enrich_timeout_seconds
    if enrichment_type == EnrichmentType.QUALITY_RECHECK:
        return settings.quality_review_timeout_seconds
    return settings.topic_cleanup_timeout_seconds


def _load_document_context(db: Session, document_id: int) -> dict[str, Any]:
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
    text_sample = (document.rewritten_text or document.clean_text or "")[:3000]
    slug = (seo.slug if seo else None) or ""
    project_id = None
    profile_context = ""
    if document.task:
        project = resolve_task_project(db, document.task)
        if project:
            project_id = project.id
            profile_context = build_profile_context(project)
    return {
        "document": document,
        "seo": seo,
        "title": title,
        "tags": tags,
        "text_sample": text_sample,
        "slug": slug,
        "project_id": project_id,
        "profile_context": profile_context,
    }


def queue_topic_cleanup_job(
    db: Session,
    *,
    document_id: int,
    project_id: int | None,
    deterministic: dict[str, Any],
    requested_by: str = "api",
    model_alias: str | None = None,
) -> LlmEnrichmentJob | None:
    if not is_llm_topic_cleanup_enabled():
        return None
    settings = get_settings()
    if not settings.cliproxyapi_base_url.strip():
        return None

    existing = db.scalar(
        select(LlmEnrichmentJob)
        .where(
            LlmEnrichmentJob.document_id == document_id,
            LlmEnrichmentJob.enrichment_type == EnrichmentType.TOPIC_CLEANUP,
            LlmEnrichmentJob.status.in_(list(EnrichmentJobStatus.ACTIVE)),
        )
        .order_by(LlmEnrichmentJob.id.desc())
        .limit(1)
    )
    if existing:
        return existing

    job = LlmEnrichmentJob(
        document_id=document_id,
        project_id=project_id,
        enrichment_type=EnrichmentType.TOPIC_CLEANUP,
        status=EnrichmentJobStatus.QUEUED,
        requested_by=requested_by,
        model_alias=model_alias or settings.topic_cleanup_model_alias,
        payload_json={"deterministic_snapshot": deterministic},
    )
    db.add(job)
    db.flush()
    return job


def _conservative_merge_topics(
    db: Session,
    *,
    document: ParsedDocument,
    deterministic: dict[str, Any],
    llm_data: dict[str, Any] | None,
    title: str,
    text_sample: str,
    slug: str,
) -> dict[str, Any]:
    merged = merge_llm_topic_cleanup(deterministic, llm_data)
    # deterministic-first strategy gate
    final = apply_strategy_gate(
        db,
        document=document,
        extraction=merged,
        title=title,
        text_sample=text_sample,
        slug=slug,
    )
    det_allowed = deterministic.get("strategy_allowed")
    det_reason = deterministic.get("strategy_block_reason")
    if det_allowed is False:
        final["strategy_allowed"] = False
        final["strategy_block_reason"] = det_reason or final.get("strategy_block_reason")
    return final


def _persist_topic_enrichment_result(
    db: Session,
    *,
    document: ParsedDocument,
    deterministic: dict[str, Any],
    llm_data: dict[str, Any] | None,
    merged: dict[str, Any],
    job_id: int,
    llm_run_id: int | None,
) -> None:
    merged = dict(merged)
    merged["llm_cleanup_status"] = "applied" if llm_data else "failed"
    merged["llm_run_id"] = llm_run_id
    merged["enrichment_job_id"] = job_id
    merged["extracted_at"] = _utcnow().isoformat()
    merged["payload_version"] = "topic_v2"
    merged["schema_version"] = TOPIC_SCHEMA_VERSION

    meta = dict(document.metadata_json or {})
    audit_entry = {
        "schema_version": TOPIC_SCHEMA_VERSION,
        "deterministic_result": deterministic,
        "llm_cleanup_result": llm_data,
        "merged_result": merged,
        "final_result": merged,
        "enrichment_job_id": job_id,
        "llm_run_id": llm_run_id,
        "strategy_allowed": merged.get("strategy_allowed"),
        "strategy_block_reason": merged.get("strategy_block_reason"),
        "created_at": merged["extracted_at"],
    }
    audits = list(meta.get("topic_extractions") or [])
    audits.append(audit_entry)
    meta["topic_extractions"] = audits[-20:]
    meta["topics"] = merged
    meta["topics_enrichment_status"] = "completed"
    document.metadata_json = meta
    db.flush()


def process_topic_cleanup_job(db: Session, job: LlmEnrichmentJob) -> None:
    from app.services.topic_extraction_service import run_llm_topic_cleanup

    ctx = _load_document_context(db, job.document_id)
    document = ctx["document"]
    meta = document.metadata_json or {}
    topics = meta.get("topics") or {}
    deterministic = topics.get("deterministic_result") or job.payload_json.get("deterministic_snapshot") or topics
    if not isinstance(deterministic, dict):
        raise ValueError("missing deterministic snapshot")

    timeout = timeout_for_enrichment(job.enrichment_type)
    llm_data, llm_run_id, status, _warnings = run_llm_topic_cleanup(
        db,
        document=document,
        project_id=ctx["project_id"],
        deterministic=deterministic,
        title=ctx["title"],
        seo_title=(ctx["seo"].seo_title if ctx["seo"] else "") or "",
        seo_description=(ctx["seo"].seo_description if ctx["seo"] else "") or "",
        tags=ctx["tags"],
        content_excerpt=ctx["text_sample"],
        profile_context=ctx["profile_context"],
        timeout_seconds=timeout,
    )
    merged = _conservative_merge_topics(
        db,
        document=document,
        deterministic=deterministic,
        llm_data=llm_data,
        title=ctx["title"],
        text_sample=ctx["text_sample"][:2000],
        slug=ctx["slug"],
    )
    if llm_data:
        job.status = EnrichmentJobStatus.COMPLETED
        job.result_json = {"llm_cleanup": llm_data, "merged": merged}
        job.llm_run_id = llm_run_id
        job.error_message = None
        _persist_topic_enrichment_result(
            db,
            document=document,
            deterministic=deterministic,
            llm_data=llm_data,
            merged=merged,
            job_id=job.id,
            llm_run_id=llm_run_id,
        )
    else:
        raise LLMError(status or "llm_cleanup_failed")


def process_enrichment_job(db: Session, job_id: int) -> None:
    job = db.get(LlmEnrichmentJob, job_id)
    if not job or job.status not in (EnrichmentJobStatus.QUEUED, EnrichmentJobStatus.FAILED_RETRYABLE):
        return
    now = _utcnow()
    job.status = EnrichmentJobStatus.RUNNING
    job.started_at = job.started_at or now
    job.locked_by = _WORKER_ID
    job.heartbeat_at = now
    job.updated_at = now
    db.flush()

    try:
        if job.enrichment_type == EnrichmentType.TOPIC_CLEANUP:
            process_topic_cleanup_job(db, job)
        else:
            job.status = EnrichmentJobStatus.SKIPPED
            job.error_message = f"unsupported enrichment_type: {job.enrichment_type}"
        job.completed_at = _utcnow()
        job.heartbeat_at = _utcnow()
        job.updated_at = _utcnow()
        if job.status == EnrichmentJobStatus.RUNNING:
            job.status = EnrichmentJobStatus.COMPLETED
    except Exception as exc:
        job.error_message = str(exc)[:2000]
        job.updated_at = _utcnow()
        job.completed_at = _utcnow()
        job.status = classify_enrichment_failure(job.error_message)
        if job.status == EnrichmentJobStatus.FAILED_RETRYABLE:
            job.retry_count += 1
        logger.warning("Enrichment job %s failed: %s", job.id, exc)


def recover_stale_enrichment_jobs(db: Session) -> int:
    settings = get_settings()
    cutoff = _utcnow() - timedelta(seconds=settings.enrichment_stale_seconds)
    stale = list(
        db.scalars(
            select(LlmEnrichmentJob).where(
                LlmEnrichmentJob.status == EnrichmentJobStatus.RUNNING,
                LlmEnrichmentJob.heartbeat_at < cutoff,
            )
        ).all()
    )
    for job in stale:
        job.status = EnrichmentJobStatus.FAILED_RETRYABLE
        job.retry_count += 1
        job.error_message = (job.error_message or "") + " [stale recovery]"
        job.locked_by = None
        job.updated_at = _utcnow()
    return len(stale)


def _retry_ready(job: LlmEnrichmentJob) -> bool:
    if job.status != EnrichmentJobStatus.FAILED_RETRYABLE:
        return False
    settings = get_settings()
    if job.retry_count >= settings.enrichment_max_retries:
        return False
    delay = _backoff_seconds(job.retry_count)
    if not job.updated_at:
        return True
    updated = job.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return _utcnow() >= updated + timedelta(seconds=delay)


def pick_jobs_to_run(db: Session, limit: int) -> list[LlmEnrichmentJob]:
    recover_stale_enrichment_jobs(db)
    settings = get_settings()
    from sqlalchemy import func
    running_count = db.scalar(
        select(func.count()).select_from(LlmEnrichmentJob).where(
            LlmEnrichmentJob.status == EnrichmentJobStatus.RUNNING
        )
    ) or 0
    slots = max(0, settings.enrichment_max_concurrent - running_count)
    if slots <= 0:
        return []

    queued = list(
        db.scalars(
            select(LlmEnrichmentJob)
            .where(LlmEnrichmentJob.status == EnrichmentJobStatus.QUEUED)
            .order_by(LlmEnrichmentJob.id.asc())
            .limit(limit)
        ).all()
    )
    retryable = [
        j
        for j in db.scalars(
            select(LlmEnrichmentJob)
            .where(LlmEnrichmentJob.status == EnrichmentJobStatus.FAILED_RETRYABLE)
            .order_by(LlmEnrichmentJob.id.asc())
            .limit(limit)
        ).all()
        if _retry_ready(j)
    ]
    picked: list[LlmEnrichmentJob] = []
    for job in queued + retryable:
        if len(picked) >= min(slots, limit):
            break
        if job.status == EnrichmentJobStatus.FAILED_RETRYABLE:
            job.status = EnrichmentJobStatus.QUEUED
        picked.append(job)
    return picked


def tick_enrichment_jobs(db: Session, *, limit: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.enable_async_llm_enrichment:
        return {"skipped": True, "reason": "async enrichment disabled"}
    lim = limit or settings.enrichment_batch_size
    processed = 0
    for job in pick_jobs_to_run(db, lim):
        try:
            process_enrichment_job(db, job.id)
            db.commit()
            processed += 1
        except Exception:
            logger.exception("Enrichment tick job %s failed", job.id)
            db.rollback()
    return {"processed": processed, "queued_remaining": _count_by_status(db, EnrichmentJobStatus.QUEUED)}


def _count_by_status(db: Session, status: str) -> int:
    from sqlalchemy import func
    return db.scalar(
        select(func.count()).select_from(LlmEnrichmentJob).where(LlmEnrichmentJob.status == status)
    ) or 0


def retry_enrichment_job(db: Session, job_id: int) -> LlmEnrichmentJob:
    job = db.get(LlmEnrichmentJob, job_id)
    if not job:
        raise ValueError("Job not found")
    if job.status == EnrichmentJobStatus.CANCELLED:
        raise ValueError("Cannot retry cancelled job")
    if job.status == EnrichmentJobStatus.COMPLETED:
        raise ValueError("Job already completed")
    job.status = EnrichmentJobStatus.QUEUED
    job.error_message = None
    job.completed_at = None
    job.started_at = None
    job.locked_by = None
    job.updated_at = _utcnow()
    db.flush()
    return job


def cancel_enrichment_job(db: Session, job_id: int) -> LlmEnrichmentJob:
    job = db.get(LlmEnrichmentJob, job_id)
    if not job:
        raise ValueError("Job not found")
    if job.status == EnrichmentJobStatus.RUNNING:
        raise ValueError("Cannot cancel running job")
    if job.status in (EnrichmentJobStatus.COMPLETED, EnrichmentJobStatus.CANCELLED):
        return job
    job.status = EnrichmentJobStatus.CANCELLED
    job.completed_at = _utcnow()
    job.updated_at = _utcnow()
    db.flush()
    return job


def latest_enrichment_for_document(
    db: Session, document_id: int, enrichment_type: str = EnrichmentType.TOPIC_CLEANUP
) -> LlmEnrichmentJob | None:
    return db.scalar(
        select(LlmEnrichmentJob)
        .where(
            LlmEnrichmentJob.document_id == document_id,
            LlmEnrichmentJob.enrichment_type == enrichment_type,
        )
        .order_by(LlmEnrichmentJob.id.desc())
        .limit(1)
    )


def enrichment_history(db: Session, document_id: int, limit: int = 10) -> list[LlmEnrichmentJob]:
    return list(
        db.scalars(
            select(LlmEnrichmentJob)
            .where(LlmEnrichmentJob.document_id == document_id)
            .order_by(LlmEnrichmentJob.id.desc())
            .limit(limit)
        ).all()
    )


def job_to_dict(job: LlmEnrichmentJob) -> dict[str, Any]:
    latency_ms = None
    if job.started_at and job.completed_at:
        s, c = job.started_at, job.completed_at
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        if c.tzinfo is None:
            c = c.replace(tzinfo=timezone.utc)
        latency_ms = int((c - s).total_seconds() * 1000)
    return {
        "id": job.id,
        "document_id": job.document_id,
        "project_id": job.project_id,
        "enrichment_type": job.enrichment_type,
        "status": job.status,
        "requested_by": job.requested_by,
        "model_alias": job.model_alias,
        "llm_run_id": job.llm_run_id,
        "retry_count": job.retry_count,
        "error_message": job.error_message,
        "latency_ms": latency_ms,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
