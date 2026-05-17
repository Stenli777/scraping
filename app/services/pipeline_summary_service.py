"""Compact pipeline stage summary for admin task/document views."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import PublishRunStatus, TaskStatus
from app.core.feature_flags import is_llm_review_enabled, is_seo_enrich_enabled
from app.models.parsed_document import ParsedDocument
from app.models.publish_run import PublishRun
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask
from app.models.seo_metadata import SeoMetadata


def _review_label(db: Session, task: ScrapingTask, document: ParsedDocument | None, meta: dict) -> str:
    review_meta = meta.get("review") or {}
    if review_meta.get("skipped"):
        return "skipped"
    if meta.get("review_error"):
        return "error"
    if review_meta:
        take = review_meta.get("take")
        if take is True:
            return "take"
        if take is False:
            return "reject"
    if document:
        row = db.scalar(
            select(ReviewResult)
            .where(ReviewResult.document_id == document.id)
            .order_by(ReviewResult.id.desc())
        )
        if row:
            return "take" if row.take else "reject"
    if not is_llm_review_enabled():
        return "skipped"
    if task.status in (TaskStatus.REVIEWING.value,):
        return "running"
    if task.status in (TaskStatus.QUEUED.value, TaskStatus.FETCHING.value):
        return "pending"
    return "pending"


def _rewrite_label(meta: dict) -> str:
    rewrite = meta.get("rewrite") or {}
    if meta.get("rewrite_error") and not rewrite:
        return "error"
    if not rewrite:
        return "pending"
    if not rewrite.get("success"):
        return "error"
    provider = (rewrite.get("provider") or "").lower()
    if provider == "mock":
        return "mock"
    if provider in ("cliproxy", "cliproxyapi"):
        return "cliproxy"
    if provider:
        return "done"
    return "done"


def _seo_label(db: Session, document: ParsedDocument | None, meta: dict) -> str:
    if meta.get("seo_error"):
        return "error"
    if document:
        seo = db.scalar(
            select(SeoMetadata)
            .where(SeoMetadata.document_id == document.id)
            .order_by(SeoMetadata.id.desc())
        )
        if seo:
            return "done"
    if not is_seo_enrich_enabled():
        return "skipped"
    if meta.get("seo_skipped"):
        return "skipped"
    return "pending"


def _publish_label(db: Session, document: ParsedDocument | None) -> str:
    if not document:
        return "not_published"
    run = db.scalar(
        select(PublishRun)
        .where(PublishRun.document_id == document.id)
        .order_by(PublishRun.id.desc())
    )
    if not run:
        return "not_published"
    if run.status == PublishRunStatus.DRY_RUN.value:
        return "dry_run"
    if run.status == PublishRunStatus.SUCCESS.value:
        return "success"
    if run.status in (
        PublishRunStatus.FAILED_RETRYABLE.value,
        PublishRunStatus.FAILED_TERMINAL.value,
    ):
        return "error"
    if run.status == PublishRunStatus.PENDING.value:
        return "pending"
    return run.status


def _stage_done_failed(task: ScrapingTask, document: ParsedDocument | None, *, after: str) -> str:
    order = [
        TaskStatus.QUEUED.value,
        TaskStatus.FETCHING.value,
        TaskStatus.PARSING.value,
        TaskStatus.CLEANING.value,
    ]
    if task.status in (TaskStatus.ERROR.value, TaskStatus.FAILED_RETRYABLE.value):
        if not document and task.status == TaskStatus.FAILED_RETRYABLE.value:
            return "failed"
        if not document:
            return "failed"
    try:
        idx = order.index(after)
        current_idx = order.index(task.status) if task.status in order else len(order)
    except ValueError:
        current_idx = len(order)
    if document:
        if after == TaskStatus.FETCHING.value and document.raw_html:
            return "done"
        if after == TaskStatus.PARSING.value and document.raw_text:
            return "done"
        if after == TaskStatus.CLEANING.value and document.clean_text:
            return "done"
    if task.status in (TaskStatus.ERROR.value,) and not document:
        return "failed"
    if task.status in (TaskStatus.DONE.value, TaskStatus.SAVING.value, TaskStatus.SEO_ENRICHING.value,
                       TaskStatus.REWRITING.value, TaskStatus.REVIEWING.value):
        return "done"
    if current_idx > idx:
        return "done"
    if task.status == after:
        return "running"
    return "pending"


def build_pipeline_summary(
    db: Session,
    task: ScrapingTask,
    document: ParsedDocument | None = None,
) -> dict[str, str]:
    document = document or task.document
    meta = (document.metadata_json or {}) if document else {}

    fetch = _stage_done_failed(task, document, after=TaskStatus.FETCHING.value)
    if task.status == TaskStatus.FETCHING.value:
        fetch = "running"
    elif document and document.raw_html:
        fetch = "done"
    elif task.status in (TaskStatus.ERROR.value, TaskStatus.FAILED_RETRYABLE.value) and not document:
        fetch = "failed"

    parse = "pending"
    if document and document.raw_text:
        parse = "done"
    elif task.status in (TaskStatus.ERROR.value,) and task.status not in (TaskStatus.DONE.value,) and not document:
        parse = "failed"
    elif task.status in (TaskStatus.DONE.value, TaskStatus.SAVING.value, TaskStatus.SEO_ENRICHING.value,
                         TaskStatus.REWRITING.value, TaskStatus.REVIEWING.value, TaskStatus.CLEANING.value):
        parse = "done" if document else "failed"

    clean = "done" if document and document.clean_text else (
        "failed" if task.status == TaskStatus.ERROR.value and not (document and document.clean_text) else "pending"
    )
    if document and document.clean_text:
        clean = "done"
    elif task.status in (TaskStatus.DONE.value, TaskStatus.SAVING.value, TaskStatus.SEO_ENRICHING.value,
                         TaskStatus.REWRITING.value, TaskStatus.REVIEWING.value):
        clean = "done" if document and document.clean_text else "failed"

    return {
        "fetch": fetch,
        "parse": parse if document or task.status not in (TaskStatus.QUEUED.value, TaskStatus.FETCHING.value) else "pending",
        "clean": clean,
        "review": _review_label(db, task, document, meta),
        "rewrite": _rewrite_label(meta),
        "seo": _seo_label(db, document, meta),
        "publish": _publish_label(db, document),
    }
