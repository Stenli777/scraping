"""Project-scoped admin list helpers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content_pilot import ContentPilot, ContentPilotItem
from app.models.content_quality_score import ContentQualityScore
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask

PAGE_SIZE_CHOICES = (10, 50, 100)


def normalize_page_size(page_size: int | str | None, *, default: int = 50) -> int:
    try:
        n = int(page_size) if page_size is not None else default
    except (TypeError, ValueError):
        n = default
    return n if n in PAGE_SIZE_CHOICES else default


def list_project_tasks(
    db: Session,
    project_id: int,
    *,
    status: str | None = None,
    page_size: int = 50,
    offset: int = 0,
) -> dict:
    filters = [ScrapingTask.project_id == project_id]
    if status:
        filters.append(ScrapingTask.status == status)
    total = int(
        db.scalar(select(func.count()).select_from(ScrapingTask).where(*filters)) or 0
    )
    rows_q = (
        select(ScrapingTask)
        .where(*filters)
        .order_by(ScrapingTask.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = []
    for task in db.scalars(rows_q).all():
        doc = task.document
        items.append(
            {
                "id": task.id,
                "status": task.status,
                "source_url": task.source_url,
                "parser": task.parser_type,
                "document_id": doc.id if doc else None,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }
        )
    return {"items": items, "total": total, "page_size": page_size, "offset": offset}


def _doc_title(document: ParsedDocument) -> str:
    meta = document.metadata_json or {}
    title = meta.get("title") or meta.get("source_title")
    if title:
        return str(title)[:120]
    return (document.source_url or "")[:80]


def list_project_documents(
    db: Session,
    project_id: int,
    *,
    status: str | None = None,
    has_publication: bool | None = None,
    in_pilot: bool | None = None,
    page_size: int = 50,
    offset: int = 0,
) -> dict:
    base = (
        select(ParsedDocument.id)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ScrapingTask.project_id == project_id)
    )
    if status:
        base = base.where(ParsedDocument.editorial_status == status)
    if has_publication is True:
        base = base.where(
            ParsedDocument.id.in_(
                select(PublicationRecord.document_id).where(
                    PublicationRecord.publication_status != "draft"
                )
            )
        )
    elif has_publication is False:
        base = base.where(
            ~ParsedDocument.id.in_(select(PublicationRecord.document_id))
        )
    if in_pilot is True:
        base = base.where(
            ParsedDocument.id.in_(
                select(ContentPilotItem.document_id)
                .join(ContentPilot, ContentPilotItem.pilot_id == ContentPilot.id)
                .where(ContentPilot.project_id == project_id)
            )
        )
    elif in_pilot is False:
        pilot_ids = select(ContentPilotItem.document_id).join(
            ContentPilot, ContentPilotItem.pilot_id == ContentPilot.id
        ).where(ContentPilot.project_id == project_id)
        base = base.where(~ParsedDocument.id.in_(pilot_ids))

    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    doc_ids = list(
        db.scalars(
            base.order_by(ParsedDocument.id.desc()).offset(offset).limit(page_size)
        ).all()
    )
    pilot_doc_ids: set[int] = set(
        db.scalars(
            select(ContentPilotItem.document_id)
            .join(ContentPilot, ContentPilotItem.pilot_id == ContentPilot.id)
            .where(ContentPilot.project_id == project_id)
        ).all()
    )
    items: list[dict] = []
    for doc_id in doc_ids:
        doc = db.get(ParsedDocument, doc_id)
        if not doc:
            continue
        review = db.scalar(
            select(ReviewResult)
            .where(ReviewResult.document_id == doc.id)
            .order_by(ReviewResult.id.desc())
        )
        quality = db.scalar(
            select(ContentQualityScore)
            .where(ContentQualityScore.document_id == doc.id)
            .order_by(ContentQualityScore.id.desc())
        )
        publication = db.scalar(
            select(PublicationRecord)
            .where(PublicationRecord.document_id == doc.id)
            .order_by(PublicationRecord.id.desc())
        )
        review_status = "—"
        if review:
            review_status = f"{'take' if review.take else 'skip'} ({review.score or '—'})"
        items.append(
            {
                "id": doc.id,
                "title": _doc_title(doc),
                "source_url": doc.source_url,
                "review_status": review_status,
                "quality_status": str(quality.overall_score) if quality else "—",
                "editorial_status": doc.editorial_status,
                "publication_status": publication.publication_status if publication else "—",
                "in_pilot": doc.id in pilot_doc_ids,
            }
        )
    return {"items": items, "total": total, "page_size": page_size, "offset": offset}
