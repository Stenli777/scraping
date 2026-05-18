"""CRMFlow24 draft review feedback — manual operator layer (no CRMFlow24 writes)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.draft_review_feedback import DraftReviewFeedback
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.models.seo_metadata import SeoMetadata
from app.services.pipeline_event_service import emit_pipeline_event

logger = logging.getLogger(__name__)

FEEDBACK_STAGE = "draft_feedback"

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_NEEDS_EDITS = "needs_edits"
STATUS_REJECTED = "rejected"
STATUS_ARCHIVED = "archived"

VALID_STATUSES = frozenset({STATUS_PENDING, STATUS_ACCEPTED, STATUS_NEEDS_EDITS, STATUS_REJECTED, STATUS_ARCHIVED})


class DraftFeedbackError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _emit_feedback_event(db: Session, document_id: int, action: str, payload: dict[str, Any]) -> None:
    doc = db.get(ParsedDocument, document_id)
    if not doc or not doc.task_id:
        return
    try:
        emit_pipeline_event(db, doc.task_id, FEEDBACK_STAGE, status=action, payload=payload)
    except Exception as exc:
        logger.warning("draft_feedback pipeline event failed: %s", exc)


def _sync_derived_status(
    db: Session,
    feedback: DraftReviewFeedback,
    *,
    notes_append: str | None = None,
) -> None:
    now = _utcnow()
    if feedback.release_candidate_id:
        cand = db.get(ContentReleaseCandidate, feedback.release_candidate_id)
        if cand:
            cand.draft_review_status = feedback.review_status
            cand.draft_reviewed_at = now
            cand.updated_at = now
    if feedback.publication_record_id:
        pub = db.get(PublicationRecord, feedback.publication_record_id)
        if pub:
            pub.draft_review_status = feedback.review_status
            pub.draft_reviewed_at = now
            if feedback.notes:
                pub.final_operator_notes = feedback.notes
            elif notes_append:
                pub.final_operator_notes = (pub.final_operator_notes or "") + notes_append
            pub.updated_at = now


def _resolve_context(
    db: Session,
    *,
    release_candidate_id: int | None = None,
    publication_record_id: int | None = None,
) -> tuple[ContentReleaseCandidate | None, PublicationRecord | None, PublishRun | None, ParsedDocument]:
    cand = pub = run = None
    document_id: int | None = None
    if release_candidate_id:
        cand = db.get(ContentReleaseCandidate, release_candidate_id)
        if not cand:
            raise DraftFeedbackError(f"Release candidate {release_candidate_id} not found")
        document_id = cand.document_id
        run = db.scalar(
            select(PublishRun)
            .where(PublishRun.release_candidate_id == cand.id)
            .order_by(PublishRun.id.desc())
        )
        pub = db.scalar(
            select(PublicationRecord)
            .where(PublicationRecord.document_id == cand.document_id)
            .order_by(PublicationRecord.id.desc())
        )
    elif publication_record_id:
        pub = db.get(PublicationRecord, publication_record_id)
        if not pub:
            raise DraftFeedbackError(f"Publication record {publication_record_id} not found")
        document_id = pub.document_id
        if pub.publish_run_id:
            run = db.get(PublishRun, pub.publish_run_id)
        if run and run.release_candidate_id:
            cand = db.get(ContentReleaseCandidate, run.release_candidate_id)
    else:
        raise DraftFeedbackError("release_candidate_id or publication_record_id required")

    doc = db.get(ParsedDocument, document_id)
    if not doc:
        raise DraftFeedbackError("Document not found")
    return cand, pub, run, doc


def feedback_to_dict(fb: DraftReviewFeedback) -> dict[str, Any]:
    return {
        "id": fb.id,
        "project_id": fb.project_id,
        "document_id": fb.document_id,
        "release_candidate_id": fb.release_candidate_id,
        "publish_run_id": fb.publish_run_id,
        "publication_record_id": fb.publication_record_id,
        "external_url": fb.external_url,
        "review_status": fb.review_status,
        "reviewer_name": fb.reviewer_name,
        "notes": fb.notes,
        "required_changes": fb.required_changes_json or [],
        "checked_public_visibility": fb.checked_public_visibility,
        "checked_seo": fb.checked_seo,
        "checked_content": fb.checked_content,
        "checked_media": fb.checked_media,
        "visibility_check": fb.visibility_check_json,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
        "updated_at": fb.updated_at.isoformat() if fb.updated_at else None,
    }


def create_feedback(
    db: Session,
    *,
    release_candidate_id: int | None = None,
    publication_record_id: int | None = None,
    review_status: str = STATUS_PENDING,
    reviewer_name: str | None = None,
    notes: str | None = None,
    required_changes: list | None = None,
    checked_public_visibility: bool = False,
    checked_seo: bool = False,
    checked_content: bool = False,
    checked_media: bool = False,
    apply_editorial_needs_revision: bool = False,
    apply_editorial_reject: bool = False,
) -> DraftReviewFeedback:
    if review_status not in VALID_STATUSES:
        raise DraftFeedbackError(f"Invalid review_status: {review_status}")

    cand, pub, run, doc = _resolve_context(
        db, release_candidate_id=release_candidate_id, publication_record_id=publication_record_id
    )
    external_url = (pub.external_url if pub else None) or (run.draft_url if run else None)

    project_id = (
        cand.project_id
        if cand
        else (pub.project_id if pub and pub.project_id else None)
    )
    if project_id is None:
        from app.models.scraping_task import ScrapingTask

        task = db.get(ScrapingTask, doc.task_id) if doc.task_id else None
        project_id = task.project_id if task else 1

    fb = DraftReviewFeedback(
        project_id=project_id,
        document_id=doc.id,
        release_candidate_id=cand.id if cand else None,
        publish_run_id=run.id if run else (pub.publish_run_id if pub else None),
        publication_record_id=pub.id if pub else None,
        external_url=external_url,
        review_status=review_status,
        reviewer_name=reviewer_name,
        notes=notes,
        required_changes_json=required_changes or [],
        checked_public_visibility=checked_public_visibility,
        checked_seo=checked_seo,
        checked_content=checked_content,
        checked_media=checked_media,
    )
    db.add(fb)
    db.flush()
    if review_status != STATUS_PENDING:
        _apply_workflow_side_effects(
            db,
            fb,
            review_status,
            apply_editorial_needs_revision=apply_editorial_needs_revision,
            apply_editorial_reject=apply_editorial_reject,
        )
    _sync_derived_status(db, fb)
    _emit_feedback_event(
        db,
        doc.id,
        "created",
        {"feedback_id": fb.id, "review_status": review_status, "release_candidate_id": fb.release_candidate_id},
    )
    return fb


def update_feedback_status(
    db: Session,
    feedback_id: int,
    review_status: str,
    *,
    notes: str | None = None,
    required_changes: list | None = None,
    apply_editorial_needs_revision: bool = False,
    apply_editorial_reject: bool = False,
) -> DraftReviewFeedback:
    if review_status not in VALID_STATUSES:
        raise DraftFeedbackError(f"Invalid review_status: {review_status}")
    fb = db.get(DraftReviewFeedback, feedback_id)
    if not fb:
        raise DraftFeedbackError(f"Feedback {feedback_id} not found")

    fb.review_status = review_status
    fb.updated_at = _utcnow()
    if notes is not None:
        fb.notes = notes
    if required_changes is not None:
        fb.required_changes_json = required_changes

    _apply_workflow_side_effects(
        db,
        fb,
        review_status,
        apply_editorial_needs_revision=apply_editorial_needs_revision,
        apply_editorial_reject=apply_editorial_reject,
    )
    _sync_derived_status(db, fb)
    _emit_feedback_event(
        db,
        fb.document_id,
        review_status,
        {"feedback_id": fb.id, "review_status": review_status},
    )
    return fb


def _apply_workflow_side_effects(
    db: Session,
    fb: DraftReviewFeedback,
    review_status: str,
    *,
    apply_editorial_needs_revision: bool,
    apply_editorial_reject: bool,
) -> None:
    if review_status == STATUS_NEEDS_EDITS and apply_editorial_needs_revision:
        from app.services import editorial_service
        from app.services.editorial_service import EditorialTransitionError

        try:
            editorial_service.mark_needs_revision(db, fb.document_id, notes=fb.notes)
        except EditorialTransitionError as exc:
            logger.warning("draft_feedback editorial needs_revision skipped: %s", exc)
    if review_status == STATUS_REJECTED and apply_editorial_reject:
        from app.services import editorial_service
        from app.services.editorial_service import EditorialTransitionError

        try:
            editorial_service.reject_document(db, fb.document_id, notes=fb.notes)
        except EditorialTransitionError as exc:
            logger.warning("draft_feedback editorial reject skipped: %s", exc)


def mark_accepted(
    db: Session,
    feedback_id: int,
    *,
    notes: str | None = None,
    reviewer_name: str | None = None,
    checked_public_visibility: bool | None = None,
    checked_seo: bool | None = None,
    checked_content: bool | None = None,
    checked_media: bool | None = None,
) -> DraftReviewFeedback:
    fb = db.get(DraftReviewFeedback, feedback_id)
    if not fb:
        raise DraftFeedbackError(f"Feedback {feedback_id} not found")
    if reviewer_name:
        fb.reviewer_name = reviewer_name
    if checked_public_visibility is not None:
        fb.checked_public_visibility = checked_public_visibility
    if checked_seo is not None:
        fb.checked_seo = checked_seo
    if checked_content is not None:
        fb.checked_content = checked_content
    if checked_media is not None:
        fb.checked_media = checked_media
    return update_feedback_status(db, feedback_id, STATUS_ACCEPTED, notes=notes)


def mark_needs_edits(
    db: Session,
    feedback_id: int,
    *,
    notes: str | None = None,
    required_changes: list | None = None,
    apply_editorial_needs_revision: bool = True,
) -> DraftReviewFeedback:
    return update_feedback_status(
        db,
        feedback_id,
        STATUS_NEEDS_EDITS,
        notes=notes,
        required_changes=required_changes,
        apply_editorial_needs_revision=apply_editorial_needs_revision,
    )


def mark_rejected(
    db: Session,
    feedback_id: int,
    *,
    notes: str | None = None,
    apply_editorial_reject: bool = False,
) -> DraftReviewFeedback:
    return update_feedback_status(
        db,
        feedback_id,
        STATUS_REJECTED,
        notes=notes,
        apply_editorial_reject=apply_editorial_reject,
    )


def get_feedback_for_candidate(db: Session, candidate_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(DraftReviewFeedback)
        .where(DraftReviewFeedback.release_candidate_id == candidate_id)
        .order_by(DraftReviewFeedback.id.desc())
    ).all()
    return [feedback_to_dict(r) for r in rows]


def get_feedback_for_publication(db: Session, publication_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(DraftReviewFeedback)
        .where(DraftReviewFeedback.publication_record_id == publication_id)
        .order_by(DraftReviewFeedback.id.desc())
    ).all()
    return [feedback_to_dict(r) for r in rows]


def get_or_create_feedback_for_candidate(db: Session, candidate_id: int) -> DraftReviewFeedback:
    existing = db.scalar(
        select(DraftReviewFeedback)
        .where(DraftReviewFeedback.release_candidate_id == candidate_id)
        .order_by(DraftReviewFeedback.id.desc())
    )
    if existing:
        return existing
    return create_feedback(db, release_candidate_id=candidate_id, review_status=STATUS_PENDING)


def _search_terms_for_publication(db: Session, publication_id: int) -> list[str]:
    pub = db.get(PublicationRecord, publication_id)
    if not pub:
        return []
    terms: list[str] = []
    seo = db.scalar(
        select(SeoMetadata).where(SeoMetadata.document_id == pub.document_id).order_by(SeoMetadata.id.desc())
    )
    if seo:
        if seo.slug:
            terms.append(seo.slug)
        if seo.seo_title:
            terms.append(seo.seo_title)
    if pub.external_url:
        slug_m = re.search(r"/posts/([^/?#]+)", pub.external_url or "")
        if slug_m:
            terms.append(slug_m.group(1))
    return [t for t in terms if t and len(t) >= 4]


def check_public_visibility(
    db: Session,
    publication_record_id: int,
    *,
    save_to_feedback_id: int | None = None,
    base_url: str = "https://crmflow24.ru",
) -> dict[str, Any]:
    terms = _search_terms_for_publication(db, publication_record_id)
    if not terms:
        raise DraftFeedbackError("No slug/title available for visibility check")

    paths = ["/blog", "/sitemap.xml", "/rss.xml"]
    results: dict[str, Any] = {"terms": terms, "checked_at": _utcnow().isoformat(), "paths": {}}

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for path in paths:
            url = f"{base_url.rstrip('/')}{path}"
            try:
                resp = client.get(url)
                body = (resp.text or "").lower()
            except Exception as exc:
                results["paths"][path] = {"error": str(exc)[:200], "visible": False}
                continue
            visible = False
            matched: list[str] = []
            for term in terms:
                needle = term.lower()
                if needle in body:
                    visible = True
                    matched.append(term)
            results["paths"][path] = {
                "visible": visible,
                "matched_terms": matched,
                "http_status": resp.status_code,
            }

    results["visible_anywhere"] = any(p.get("visible") for p in results["paths"].values() if isinstance(p, dict))

    if save_to_feedback_id:
        fb = db.get(DraftReviewFeedback, save_to_feedback_id)
        if fb:
            fb.visibility_check_json = results
            fb.checked_public_visibility = True
            fb.updated_at = _utcnow()
    else:
        pub = db.get(PublicationRecord, publication_record_id)
        if pub:
            meta = dict(pub.metadata_json or {})
            meta["visibility_check"] = results
            pub.metadata_json = meta
            pub.last_checked_at = _utcnow()

    return results


def list_draft_review_queue(
    db: Session,
    *,
    statuses: tuple[str, ...] = (STATUS_PENDING, STATUS_NEEDS_EDITS),
    limit: int = 100,
) -> list[dict[str, Any]]:
    pubs = db.scalars(
        select(PublicationRecord)
        .where(
            PublicationRecord.publication_status == "draft",
            PublicationRecord.draft_review_status.in_(statuses)
            | PublicationRecord.draft_review_status.is_(None),
        )
        .order_by(PublicationRecord.created_at.desc())
        .limit(limit)
    ).all()
    out: list[dict[str, Any]] = []
    for pub in pubs:
        if pub.draft_review_status and pub.draft_review_status not in statuses:
            continue
        cand = None
        if pub.publish_run_id:
            run = db.get(PublishRun, pub.publish_run_id)
            if run and run.release_candidate_id:
                cand = db.get(ContentReleaseCandidate, run.release_candidate_id)
        fb = db.scalar(
            select(DraftReviewFeedback)
            .where(DraftReviewFeedback.publication_record_id == pub.id)
            .order_by(DraftReviewFeedback.id.desc())
        )
        out.append({
            "publication_id": pub.id,
            "document_id": pub.document_id,
            "draft_url": pub.external_url,
            "draft_review_status": pub.draft_review_status or STATUS_PENDING,
            "release_candidate_id": cand.id if cand else None,
            "publish_run_id": pub.publish_run_id,
            "notes": (fb.notes if fb else None) or pub.final_operator_notes,
            "created_at": pub.created_at.isoformat() if pub.created_at else None,
            "feedback_id": fb.id if fb else None,
        })
    return out
