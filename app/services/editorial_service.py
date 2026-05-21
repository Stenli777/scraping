"""Editorial state machine — operator decisions (separate from LLM quality verdict)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.enums import EditorialStatus
from app.core.feature_flags import is_editorial_workflow_enabled
from app.models.parsed_document import ParsedDocument
from app.services.human_override_service import mark_operator_touched
from app.services.pipeline_event_service import emit_pipeline_event

EDITORIAL_STAGE = "editorial"

_ALLOWED: dict[EditorialStatus, set[EditorialStatus]] = {
    EditorialStatus.GENERATED: {
        EditorialStatus.OPERATOR_REVIEW,
        EditorialStatus.NEEDS_REVISION,
        EditorialStatus.REJECTED,
    },
    EditorialStatus.NEEDS_REVISION: {
        EditorialStatus.OPERATOR_REVIEW,
        EditorialStatus.GENERATED,
    },
    EditorialStatus.OPERATOR_REVIEW: {
        EditorialStatus.APPROVED,
        EditorialStatus.REJECTED,
        EditorialStatus.NEEDS_REVISION,
    },
    EditorialStatus.APPROVED: {
        EditorialStatus.READY_TO_PUBLISH,
        EditorialStatus.NEEDS_REVISION,
        EditorialStatus.REJECTED,
        EditorialStatus.OPERATOR_REVIEW,
    },
    EditorialStatus.READY_TO_PUBLISH: {
        EditorialStatus.PUBLISHED_DRAFT,
        EditorialStatus.NEEDS_REVISION,
        EditorialStatus.REJECTED,
    },
    EditorialStatus.PUBLISHED_DRAFT: {EditorialStatus.ARCHIVED, EditorialStatus.NEEDS_REVISION, EditorialStatus.REJECTED},
    EditorialStatus.REJECTED: {EditorialStatus.OPERATOR_REVIEW, EditorialStatus.ARCHIVED},
    EditorialStatus.ARCHIVED: set(),
}


class EditorialTransitionError(ValueError):
    pass


def _require_workflow() -> None:
    if not is_editorial_workflow_enabled():
        raise EditorialTransitionError("Editorial workflow is disabled (ENABLE_EDITORIAL_WORKFLOW=false)")


def _parse_status(value: str | None) -> EditorialStatus:
    if not value:
        return EditorialStatus.GENERATED
    try:
        return EditorialStatus(value)
    except ValueError as exc:
        raise EditorialTransitionError(f"Unknown editorial status: {value}") from exc


def can_transition(current: EditorialStatus, target: EditorialStatus) -> bool:
    return target in _ALLOWED.get(current, set())


def _transition(
    db: Session,
    document: ParsedDocument,
    target: EditorialStatus,
    *,
    notes: str | None = None,
    approved_for_publish: bool | None = None,
    set_approved_at: bool = False,
    set_rejected_at: bool = False,
    set_reviewed_at: bool = False,
) -> ParsedDocument:
    _require_workflow()
    current = _parse_status(document.editorial_status)
    if not can_transition(current, target):
        raise EditorialTransitionError(
            f"Invalid editorial transition: {current.value} -> {target.value}"
        )

    now = datetime.now(timezone.utc)
    document.editorial_status = target.value
    if notes is not None:
        document.editorial_notes = notes
    if approved_for_publish is not None:
        document.approved_for_publish = approved_for_publish
    if set_approved_at:
        document.operator_approved_at = now
        document.approved_for_publish = True
    if set_rejected_at:
        document.operator_rejected_at = now
        document.approved_for_publish = False
    if set_reviewed_at:
        document.operator_reviewed_at = now

    task = document.task
    if task:
        emit_pipeline_event(
            db,
            task.id,
            EDITORIAL_STAGE,
            status="transition",
            payload={
                "document_id": document.id,
                "from": current.value,
                "to": target.value,
                "notes": notes,
                "revision_number": document.current_revision_number,
            },
        )
    mark_operator_touched(db, document.id, operator="editorial")
    db.flush()
    return document


def approve_document(db: Session, document_id: int, *, notes: str | None = None) -> ParsedDocument:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    current = _parse_status(document.editorial_status)
    if current == EditorialStatus.GENERATED:
        _transition(db, document, EditorialStatus.OPERATOR_REVIEW, set_reviewed_at=True)
        db.refresh(document)
    return _transition(
        db,
        document,
        EditorialStatus.APPROVED,
        notes=notes,
        set_approved_at=True,
    )


def reject_document(db: Session, document_id: int, *, notes: str | None = None) -> ParsedDocument:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    return _transition(
        db,
        document,
        EditorialStatus.REJECTED,
        notes=notes,
        set_rejected_at=True,
    )


def mark_needs_revision(db: Session, document_id: int, *, notes: str | None = None) -> ParsedDocument:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    return _transition(
        db,
        document,
        EditorialStatus.NEEDS_REVISION,
        notes=notes,
        approved_for_publish=False,
    )


def move_to_operator_review(db: Session, document_id: int, *, notes: str | None = None) -> ParsedDocument:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    return _transition(
        db,
        document,
        EditorialStatus.OPERATOR_REVIEW,
        notes=notes,
        set_reviewed_at=True,
        approved_for_publish=False,
    )


def mark_ready_to_publish(db: Session, document_id: int, *, notes: str | None = None) -> ParsedDocument:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    current = _parse_status(document.editorial_status)
    if current not in (EditorialStatus.APPROVED, EditorialStatus.READY_TO_PUBLISH):
        raise EditorialTransitionError(
            f"Document must be approved before ready_to_publish (current={current.value})"
        )
    return _transition(
        db,
        document,
        EditorialStatus.READY_TO_PUBLISH,
        notes=notes,
        approved_for_publish=True,
    )


def mark_published_draft(db: Session, document_id: int) -> ParsedDocument:
    """Called after successful publish — not exposed as operator action."""
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    if not is_editorial_workflow_enabled():
        return document
    current = _parse_status(document.editorial_status)
    if current == EditorialStatus.PUBLISHED_DRAFT:
        return document
    if can_transition(current, EditorialStatus.PUBLISHED_DRAFT):
        return _transition(db, document, EditorialStatus.PUBLISHED_DRAFT, approved_for_publish=True)
    document.editorial_status = EditorialStatus.PUBLISHED_DRAFT.value
    document.approved_for_publish = True
    db.flush()
    return document


def is_editorially_publishable(document: ParsedDocument) -> bool:
    if not is_editorial_workflow_enabled():
        return True
    status = document.editorial_status or EditorialStatus.GENERATED.value
    if status not in (
        EditorialStatus.APPROVED.value,
        EditorialStatus.READY_TO_PUBLISH.value,
        EditorialStatus.PUBLISHED_DRAFT.value,
    ):
        return False
    return bool(document.approved_for_publish)
