"""Human override markers ??? operator ownership boundary."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.parsed_document import ParsedDocument


def mark_operator_touched(
    db: Session,
    document_id: int,
    *,
    operator: str | None = None,
) -> None:
    """Mark document as operator-modified; automation must not silently overwrite."""
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return
    doc.operator_touched = True
    doc.operator_touched_at = datetime.now(timezone.utc)
    if operator:
        doc.operator_touched_by = operator[:255]
    db.flush()
