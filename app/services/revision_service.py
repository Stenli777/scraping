"""Immutable document revision snapshots for rewrite/SEO/quality/publish."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import EditorialStatus, RevisionSourceType
from app.models.content_quality_score import ContentQualityScore
from app.models.document_revision import DocumentRevision
from app.models.parsed_document import ParsedDocument
from app.models.seo_metadata import SeoMetadata


from app.publishers.exceptions import PublishValidationError


def validate_revision_current_for_publish(
    db: Session,
    document_id: int,
    revision: DocumentRevision,
) -> None:
    """Block publish when revision is not the document latest (governance C4/P4)."""
    latest = get_latest_revision(db, document_id)
    if latest and revision and latest.id != revision.id:
        raise PublishValidationError(
            f"Revision #{revision.revision_number} is stale; "
            f"latest is #{latest.revision_number}. "
            "Create a new release candidate or re-run QA on the latest revision."
        )



def _seo_snapshot(seo: SeoMetadata | None) -> dict | None:
    if not seo:
        return None
    return {
        "id": seo.id,
        "seo_title": seo.seo_title,
        "seo_description": seo.seo_description,
        "h1": seo.h1,
        "slug": seo.slug,
        "excerpt": seo.excerpt,
        "tags": seo.tags_json,
        "faq": seo.faq_json,
        "suggested_category": seo.suggested_category,
    }


def _quality_snapshot(quality: ContentQualityScore | None) -> dict | None:
    if not quality:
        return None
    return {
        "id": quality.id,
        "overall_score": quality.overall_score,
        "verdict": quality.verdict,
        "readability_score": quality.readability_score,
        "seo_score": quality.seo_score,
        "spamminess_score": quality.spamminess_score,
        "risks": quality.risks_json,
        "recommendations": quality.recommendations_json,
    }


def _latest_seo(db: Session, document_id: int) -> SeoMetadata | None:
    return db.scalar(
        select(SeoMetadata)
        .where(SeoMetadata.document_id == document_id)
        .order_by(SeoMetadata.id.desc())
    )


def _latest_quality(db: Session, document_id: int) -> ContentQualityScore | None:
    return db.scalar(
        select(ContentQualityScore)
        .where(ContentQualityScore.document_id == document_id)
        .order_by(ContentQualityScore.id.desc())
    )


def create_revision_snapshot(
    db: Session,
    document: ParsedDocument,
    *,
    source_type: str,
    source_reference_id: int | None = None,
    rewrite_text: str | None = None,
    seo: SeoMetadata | None = None,
    quality: ContentQualityScore | None = None,
    editorial_status: str | None = None,
) -> DocumentRevision:
    """Create immutable revision; increment document.current_revision_number."""
    next_num = (document.current_revision_number or 0) + 1
    if seo is None:
        seo = _latest_seo(db, document.id)
    if quality is None:
        quality = _latest_quality(db, document.id)

    record = DocumentRevision(
        document_id=document.id,
        revision_number=next_num,
        source_type=source_type,
        source_reference_id=source_reference_id,
        rewrite_text=rewrite_text if rewrite_text is not None else document.rewritten_text,
        seo_snapshot_json=_seo_snapshot(seo),
        quality_snapshot_json=_quality_snapshot(quality),
        editorial_status=editorial_status or document.editorial_status or EditorialStatus.GENERATED.value,
    )
    db.add(record)
    document.current_revision_number = next_num
    meta = dict(document.metadata_json or {})
    meta["current_revision_id"] = None
    document.metadata_json = meta
    db.flush()
    meta["current_revision_id"] = record.id
    document.metadata_json = meta
    db.flush()
    from app.services.runtime_integrity_service import archive_stale_open_rc_for_document

    archive_stale_open_rc_for_document(db, document.id, record.id, source="new_revision")
    return record


def get_latest_revision(db: Session, document_id: int) -> DocumentRevision | None:
    return db.scalar(
        select(DocumentRevision)
        .where(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.revision_number.desc())
    )


def get_revision_by_number(
    db: Session, document_id: int, revision_number: int
) -> DocumentRevision | None:
    return db.scalar(
        select(DocumentRevision).where(
            DocumentRevision.document_id == document_id,
            DocumentRevision.revision_number == revision_number,
        )
    )


def list_revisions(db: Session, document_id: int, *, limit: int = 50) -> list[DocumentRevision]:
    return list(
        db.scalars(
            select(DocumentRevision)
            .where(DocumentRevision.document_id == document_id)
            .order_by(DocumentRevision.revision_number.desc())
            .limit(limit)
        ).all()
    )


def ensure_revision_for_publish(db: Session, document: ParsedDocument) -> DocumentRevision:
    """Return latest revision or create publish_snapshot from current state."""
    latest = get_latest_revision(db, document.id)
    if latest:
        return latest
    return create_revision_snapshot(
        db,
        document,
        source_type=RevisionSourceType.PUBLISH_SNAPSHOT.value,
        rewrite_text=document.rewritten_text,
    )
