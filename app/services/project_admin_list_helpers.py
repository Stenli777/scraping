"""Project-scoped admin list helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_pilot import ContentPilot, ContentPilotItem
from app.models.content_quality_score import ContentQualityScore
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.review_result import ReviewResult
from app.models.scraping_task import ScrapingTask


def list_project_tasks(
    db: Session,
    project_id: int,
    *,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    q = (
        select(ScrapingTask)
        .where(ScrapingTask.project_id == project_id)
        .order_by(ScrapingTask.id.desc())
        .limit(limit)
    )
    if status:
        q = q.where(ScrapingTask.status == status)
    rows = []
    for task in db.scalars(q).all():
        doc = task.document
        rows.append(
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
    return rows


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
    limit: int = 200,
) -> list[dict]:
    q = (
        select(ParsedDocument)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ScrapingTask.project_id == project_id)
        .order_by(ParsedDocument.id.desc())
        .limit(limit)
    )
    pilot_doc_ids: set[int] = set(
        db.scalars(
            select(ContentPilotItem.document_id)
            .join(ContentPilot, ContentPilotItem.pilot_id == ContentPilot.id)
            .where(ContentPilot.project_id == project_id)
        ).all()
    )

    rows: list[dict] = []
    for doc in db.scalars(q).all():
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
        quality_status = str(quality.overall_score) if quality else "—"
        publication_status = publication.publication_status if publication else "—"
        is_pilot = doc.id in pilot_doc_ids
        if status and doc.editorial_status != status:
            continue
        if has_publication is True and publication_status == "—":
            continue
        if has_publication is False and publication_status != "—":
            continue
        if in_pilot is True and not is_pilot:
            continue
        if in_pilot is False and is_pilot:
            continue
        rows.append(
            {
                "id": doc.id,
                "title": _doc_title(doc),
                "source_url": doc.source_url,
                "review_status": review_status,
                "quality_status": quality_status,
                "editorial_status": doc.editorial_status,
                "publication_status": publication_status,
                "in_pilot": is_pilot,
            }
        )
    return rows
