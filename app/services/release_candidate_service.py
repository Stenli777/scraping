"""Release candidate workflow: pre-publication QA pack (deterministic, no auto-publish)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import (
    is_editorial_workflow_enabled,
    is_publishing_enabled,
    is_quality_review_enabled,
)
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.document_revision import DocumentRevision
from app.models.llm_enrichment_job import EnrichmentJobStatus, LlmEnrichmentJob
from app.models.parsed_document import ParsedDocument
from app.models.publish_run import PublishRun
from app.models.publish_target import PublishTarget
from app.models.scraping_task import ScrapingTask
from app.models.source_quality_score import SourceQualityScore
from app.publishers.payloads import build_publish_payload
from app.publishers.payloads import PAYLOAD_VERSION_ARTICLE_V2
from app.publishers.validators import validate_article_v1_publish
from app.publishers.validators_v2 import validate_article_v2_publish
from app.services.document_similarity_service import get_canonical_strategy_warnings
from app.services.media_service import build_media_block_for_publish, get_approved_preview_asset
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.project_profile_service import resolve_task_project
from app.services.publish_service import _latest_review, _latest_seo, publish_draft_for_document
from app.services.publish_target_health_service import check_publish_target_health
from app.services.quality_service import MAX_SPAM_SCORE, get_latest_quality_score
from app.services.revision_service import ensure_revision_for_publish, get_latest_revision, get_revision_by_number
from app.services.strategy_gate_service import detect_test_document, document_strategy_allowed

logger = logging.getLogger(__name__)

RELEASE_STAGE = "release_candidate"

RC_DRAFT = "draft"
RC_QA_FAILED = "qa_failed"
RC_QA_PASSED = "qa_passed"
RC_APPROVED = "approved"
RC_REJECTED = "rejected"
RC_PUBLISHED_DRAFT = "published_draft"
RC_ARCHIVED = "archived"

OPEN_STATUSES = frozenset({RC_DRAFT, RC_QA_FAILED, RC_QA_PASSED, RC_APPROVED})

PRODUCTION_TARGET_NAME = "crmflow24-production-v2"


@dataclass
class QACheck:
    check_id: str
    label: str
    passed: bool
    blocking: bool
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "label": self.label,
            "passed": self.passed,
            "blocking": self.blocking,
            "detail": self.detail,
        }


class ReleaseCandidateError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _emit_rc_event(db: Session, task_id: int | None, action: str, payload: dict[str, Any]) -> None:
    if not task_id:
        return
    try:
        emit_pipeline_event(
            db,
            task_id,
            RELEASE_STAGE,
            status=action,
            payload=payload,
        )
    except Exception as exc:
        logger.warning("release_candidate pipeline event failed: %s", exc)


def _resolve_revision(db: Session, document: ParsedDocument, revision_id: int | None) -> DocumentRevision:
    if revision_id:
        rev = db.get(DocumentRevision, revision_id)
        if not rev or rev.document_id != document.id:
            raise ReleaseCandidateError(f"Revision {revision_id} not found for document {document.id}")
        return rev
    latest = get_latest_revision(db, document.id)
    if latest:
        return latest
    return ensure_revision_for_publish(db, document)


def resolve_production_publish_target(db: Session, project_id: int) -> PublishTarget | None:
    named = db.scalar(
        select(PublishTarget).where(
            PublishTarget.project_id == project_id,
            PublishTarget.name == PRODUCTION_TARGET_NAME,
        )
    )
    if named and named.enabled:
        return named
    return db.scalar(
        select(PublishTarget)
        .where(
            PublishTarget.project_id == project_id,
            PublishTarget.enabled.is_(True),
            PublishTarget.payload_format == PAYLOAD_VERSION_ARTICLE_V2,
        )
        .order_by(PublishTarget.id.asc())
    )


def _archive_stale_candidates(db: Session, document_id: int, revision_id: int) -> None:
    rows = db.scalars(
        select(ContentReleaseCandidate).where(
            ContentReleaseCandidate.document_id == document_id,
            ContentReleaseCandidate.status.in_(tuple(OPEN_STATUSES)),
        )
    ).all()
    for row in rows:
        if row.document_revision_id != revision_id:
            row.status = RC_ARCHIVED
            row.updated_at = _utcnow()


def create_release_candidate(
    db: Session,
    document_id: int,
    *,
    revision_id: int | None = None,
    publish_target_id: int | None = None,
    notes: str | None = None,
) -> ContentReleaseCandidate:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ReleaseCandidateError(f"Document {document_id} not found")
    task = document.task
    if not task:
        raise ReleaseCandidateError("Document has no task")
    project = resolve_task_project(db, task)
    if not project:
        raise ReleaseCandidateError("Document has no project")

    revision = _resolve_revision(db, document, revision_id)
    _archive_stale_candidates(db, document.id, revision.id)

    if publish_target_id:
        target = db.get(PublishTarget, publish_target_id)
        if not target or target.project_id != project.id:
            raise ReleaseCandidateError("Invalid publish_target_id for project")
    else:
        target = resolve_production_publish_target(db, project.id)

    payload_version = (target.payload_format if target else PAYLOAD_VERSION_ARTICLE_V2) or PAYLOAD_VERSION_ARTICLE_V2

    candidate = ContentReleaseCandidate(
        project_id=project.id,
        document_id=document.id,
        document_revision_id=revision.id,
        status=RC_DRAFT,
        publish_target_id=target.id if target else None,
        payload_version=payload_version,
        notes=notes,
    )
    db.add(candidate)
    db.flush()

    _emit_rc_event(
        db,
        task.id,
        "created",
        {"release_candidate_id": candidate.id, "document_revision_id": revision.id},
    )
    return candidate


def _source_quality_blocked(db: Session, document: ParsedDocument) -> tuple[bool, str | None]:
    if not document.source_url:
        return False, None
    row = db.scalar(
        select(SourceQualityScore)
        .where(SourceQualityScore.url == document.source_url)
        .order_by(SourceQualityScore.id.desc())
    )
    if not row:
        return False, None
    if row.strategy_allowed is False or (row.quality_score is not None and row.quality_score < get_settings().min_source_quality_score):
        return True, f"source_quality_score={row.quality_score}"
    return False, None


def _severe_canonical_duplicate(db: Session, document_id: int, project_id: int) -> tuple[bool, str | None]:
    from app.models.document_similarity_link import DocumentSimilarityLink

    settings = get_settings()
    links = db.scalars(
        select(DocumentSimilarityLink).where(
            DocumentSimilarityLink.project_id == project_id,
            (
                (DocumentSimilarityLink.document_id_a == document_id)
                | (DocumentSimilarityLink.document_id_b == document_id)
            ),
        )
    ).all()
    for link in links:
        if link.duplicate_risk == "critical":
            return True, f"critical duplicate with doc pair score={link.similarity_score}"
        if link.similarity_type in ("near_duplicate", "same_source") and link.similarity_score >= settings.similarity_near_duplicate_threshold:
            return True, f"{link.similarity_type} score={link.similarity_score}"
    return False, None


def _build_qa_checks(db: Session, candidate: ContentReleaseCandidate) -> list[QACheck]:
    checks: list[QACheck] = []
    document = db.get(ParsedDocument, candidate.document_id)
    revision = db.get(DocumentRevision, candidate.document_revision_id)
    task = document.task if document else None
    project = resolve_task_project(db, task) if task else None
    settings = get_settings()

    def add(check_id: str, label: str, passed: bool, blocking: bool, detail: str | None = None) -> None:
        checks.append(QACheck(check_id, label, passed, blocking, detail))

    add("document_exists", "Document exists", document is not None, True)
    add("revision_exists", "Revision exists", revision is not None, True)

    if not document or not revision:
        return checks

    seo = _latest_seo(db, document.id)
    review = _latest_review(db, document.id)
    meta = document.metadata_json or {}
    review_meta = meta.get("review") or {}
    title = (seo.h1 if seo else None) or (seo.seo_title if seo else None) or meta.get("title") or ""
    text_sample = (document.rewritten_text or "")[:2000]
    slug = (seo.slug if seo else "") or ""

    is_test, test_reason = detect_test_document(title=title, text=text_sample, slug=slug)
    add(
        "smoke_test_blocked",
        "Not smoke/test/debug document",
        not is_test,
        True,
        test_reason if is_test else None,
    )

    add("rewritten_text", "Rewritten text present", bool(document.rewritten_text and document.rewritten_text.strip()), True)
    add("seo_metadata", "SEO metadata present", seo is not None, True)
    add("seo_slug", "SEO slug present", bool(seo and seo.slug), True)

    take = review.take if review is not None else review_meta.get("take")
    add("review_take", "Review take approved", take is True, True, f"take={take!r}")

    min_review = (project.minimum_review_score_for_publish if project else None) or 60
    review_score = review.score if review is not None else review_meta.get("score")
    score_ok = False
    if review_score is not None:
        try:
            score_ok = int(review_score) >= min_review
        except (TypeError, ValueError):
            score_ok = False
    add("review_score", f"Review score >= {min_review}", score_ok, True, f"score={review_score!r}")

    quality = get_latest_quality_score(db, document.id)
    quality_enabled = is_quality_review_enabled()
    if quality_enabled:
        q_verdict_ok = False
        if quality:
            if quality.verdict == "approved":
                q_verdict_ok = True
            elif quality.verdict == "needs_revision" and quality.overall_score is not None:
                try:
                    q_verdict_ok = int(quality.overall_score) >= settings.min_quality_score_for_publish
                except (TypeError, ValueError):
                    q_verdict_ok = False
        add(
            "quality_verdict",
            "Quality verdict approved",
            q_verdict_ok,
            True,
            quality.verdict if quality and not q_verdict_ok else None,
        )
        q_ok = False
        if quality and quality.overall_score is not None:
            try:
                q_ok = int(quality.overall_score) >= settings.min_quality_score_for_publish
            except (TypeError, ValueError):
                q_ok = False
        add(
            "quality_score",
            f"Quality score >= {settings.min_quality_score_for_publish}",
            q_ok,
            True,
            f"score={quality.overall_score if quality else None}",
        )
    else:
        add("quality_verdict", "Quality review (optional)", True, False)
        add("quality_score", "Quality score (optional)", True, False)

    editorial_enabled = is_editorial_workflow_enabled()
    if editorial_enabled:
        add(
            "editorial_approved",
            "Editorial approved_for_publish",
            bool(document.approved_for_publish),
            True,
            f"status={document.editorial_status}",
        )
    else:
        add("editorial_approved", "Editorial (disabled)", True, False)

    sq_blocked, sq_detail = _source_quality_blocked(db, document)
    add("source_quality", "Source quality not blocked", not sq_blocked, True, sq_detail)

    strat_ok, strat_reason, _ = document_strategy_allowed(db, document.id)
    add("strategy_allowed", "Strategy allowed", strat_ok, True, strat_reason)

    if project:
        severe, sev_detail = _severe_canonical_duplicate(db, document.id, project.id)
        add("canonical_duplicate", "No severe canonical duplicate", not severe, True, sev_detail)
    else:
        add("canonical_duplicate", "Canonical duplicate check", False, True, "no project")

    target = db.get(PublishTarget, candidate.publish_target_id) if candidate.publish_target_id else None
    add("publish_target", "Publish target configured", target is not None, True)
    if target:
        add("publish_target_enabled", "Publish target enabled", target.enabled, True)
        add(
            "production_target_format",
            "Target payload article_v2",
            (target.payload_format or "").strip() == PAYLOAD_VERSION_ARTICLE_V2,
            True,
            target.payload_format,
        )
        auth_ok = target.auth_type in (None, "none") or bool(target.auth_token_env_name)
        add("production_target_auth", "Target auth configured", auth_ok or target.target_type == "mock", True)
        health = check_publish_target_health(db, target)
        add(
            "crmflow24_target_health",
            "CRMFlow24 target health",
            health.get("healthy") or health.get("dry_run") or target.target_type == "mock",
            False,
            health.get("reach_detail") or health.get("detail"),
        )
        if target.name != PRODUCTION_TARGET_NAME:
            add(
                "production_target_name",
                f"Preferred target {PRODUCTION_TARGET_NAME}",
                False,
                False,
                f"using {target.name}",
            )
    else:
        add("production_target_exists", f"Target {PRODUCTION_TARGET_NAME} exists", False, True)

    payload_ok = False
    payload_detail: str | None = None
    if document and project and target and seo:
        try:
            media_block = build_media_block_for_publish(db, document.id)
            payload = build_publish_payload(
                candidate.payload_version,
                document=document,
                task=task,
                project=project,
                target=target,
                seo=seo,
                review=review,
                media=media_block,
                revision_id=revision.id,
            )
            if candidate.payload_version == PAYLOAD_VERSION_ARTICLE_V2:
                validate_article_v2_publish(
                    document=document, project=project, target=target, seo=seo, payload=payload
                ).raise_if_invalid()
            else:
                validate_article_v1_publish(
                    document=document, project=project, target=target, seo=seo, payload=payload
                ).raise_if_invalid()
            payload_ok = True
        except Exception as exc:
            payload_detail = str(exc)[:300]
    add("payload_validation", "Payload validation passes", payload_ok, True, payload_detail)

    preview = get_approved_preview_asset(db, document.id)
    add("preview_image", "Preview image present", preview is not None, False)
    if preview and preview.status != "approved":
        add("media_approved", "Preview media approved", False, False, preview.status)

    for w in get_canonical_strategy_warnings(db, document.id)[:5]:
        add("canonical_warning", "Canonical similarity", False, False, w)

    from app.models.campaign_document_link import CampaignDocumentLink
    from app.models.document_similarity_link import DocumentSimilarityLink

    camp_overlap = db.scalar(
        select(DocumentSimilarityLink).where(
            DocumentSimilarityLink.similarity_type == "campaign_overlap",
            (
                (DocumentSimilarityLink.document_id_a == document.id)
                | (DocumentSimilarityLink.document_id_b == document.id)
            ),
        ).limit(1)
    )
    if camp_overlap:
        add("campaign_overlap", "Campaign overlap detected", False, False, camp_overlap.similarity_type)

    pending_enrich = db.scalar(
        select(LlmEnrichmentJob).where(
            LlmEnrichmentJob.document_id == document.id,
            LlmEnrichmentJob.status.in_([EnrichmentJobStatus.QUEUED, EnrichmentJobStatus.RUNNING]),
        ).limit(1)
    )
    if pending_enrich:
        add("enrichment_pending", "LLM enrichment pending", False, False, pending_enrich.enrichment_type)

    if not is_publishing_enabled():
        add("publishing_enabled", "Publishing enabled globally", False, True)

    return checks


def compute_qa_score(checks: list[QACheck], *, quality_score: int | None, review_score: int | None) -> int:
    """Deterministic QA score 0-100. See docs/ARCHITECTURE.md for formula."""
    settings = get_settings()
    required = [c for c in checks if c.blocking]
    warnings = [c for c in checks if not c.blocking]
    req_passed = sum(1 for c in required if c.passed)
    req_total = max(len(required), 1)
    base = int(settings.release_qa_required_pass_base * (req_passed / req_total))

    bonus = 0
    if quality_score is not None:
        try:
            bonus += min(10, max(0, (int(quality_score) - 70) // 3))
        except (TypeError, ValueError):
            pass
    if review_score is not None:
        try:
            bonus += min(10, max(0, (int(review_score) - 60) // 4))
        except (TypeError, ValueError):
            pass

    penalty = 0
    for c in checks:
        if c.check_id == "canonical_duplicate" and not c.passed:
            penalty += 15
        elif c.check_id == "canonical_warning" and not c.passed:
            penalty += 5
        elif c.check_id == "source_quality" and not c.passed:
            penalty += 10
        elif c.check_id == "preview_image" and not c.passed:
            penalty += 5
        elif c.check_id == "smoke_test_blocked" and not c.passed:
            penalty += 30

    warn_fail = sum(1 for c in warnings if not c.passed)
    penalty += min(10, warn_fail * 2)

    return max(0, min(100, base + bonus - penalty))


def run_release_qa(db: Session, candidate_id: int) -> dict[str, Any]:
    candidate = db.get(ContentReleaseCandidate, candidate_id)
    if not candidate:
        raise ReleaseCandidateError(f"Release candidate {candidate_id} not found")
    if candidate.status in (RC_PUBLISHED_DRAFT, RC_ARCHIVED, RC_REJECTED):
        raise ReleaseCandidateError(f"Cannot QA candidate in status {candidate.status}")

    checks = _build_qa_checks(db, candidate)
    blocking = [c.as_dict() for c in checks if c.blocking and not c.passed]
    warnings = [c.as_dict() for c in checks if not c.blocking and not c.passed]

    quality = get_latest_quality_score(db, candidate.document_id)
    document = db.get(ParsedDocument, candidate.document_id)
    review = _latest_review(db, candidate.document_id) if document else None
    meta = (document.metadata_json or {}) if document else {}
    review_score = review.score if review else meta.get("review", {}).get("score")

    score = compute_qa_score(
        checks,
        quality_score=quality.overall_score if quality else None,
        review_score=review_score,
    )

    checklist = {c.check_id: c.as_dict() for c in checks}
    candidate.qa_score = score
    candidate.blocking_issues_json = blocking
    candidate.warnings_json = warnings
    candidate.checklist_json = checklist
    candidate.status = RC_QA_PASSED if not blocking else RC_QA_FAILED
    candidate.updated_at = _utcnow()

    task_id = document.task_id if document and document.task else None
    _emit_rc_event(
        db,
        task_id,
        "qa_run",
        {
            "release_candidate_id": candidate.id,
            "qa_score": score,
            "blocking_count": len(blocking),
            "status": candidate.status,
        },
    )

    return get_candidate_status(db, candidate_id)


def approve_release_candidate(db: Session, candidate_id: int, *, notes: str | None = None) -> dict[str, Any]:
    candidate = db.get(ContentReleaseCandidate, candidate_id)
    if not candidate:
        raise ReleaseCandidateError(f"Candidate {candidate_id} not found")
    if candidate.status not in (RC_QA_PASSED, RC_DRAFT):
        raise ReleaseCandidateError(f"Cannot approve from status {candidate.status}")
    if candidate.blocking_issues_json:
        raise ReleaseCandidateError("Candidate has blocking issues; run QA or fix content first")
    if candidate.status == RC_DRAFT:
        run_release_qa(db, candidate_id)
        db.refresh(candidate)
        if candidate.status != RC_QA_PASSED:
            raise ReleaseCandidateError("QA failed; cannot approve")

    candidate.status = RC_APPROVED
    candidate.approved_at = _utcnow()
    candidate.updated_at = _utcnow()
    if notes:
        candidate.notes = (candidate.notes or "") + f"\n[approve] {notes}"

    document = db.get(ParsedDocument, candidate.document_id)
    _emit_rc_event(db, document.task_id if document and document.task else None, "approved", {"release_candidate_id": candidate.id})
    return get_candidate_status(db, candidate_id)


def reject_release_candidate(db: Session, candidate_id: int, reason: str) -> dict[str, Any]:
    candidate = db.get(ContentReleaseCandidate, candidate_id)
    if not candidate:
        raise ReleaseCandidateError(f"Candidate {candidate_id} not found")
    candidate.status = RC_REJECTED
    candidate.rejected_at = _utcnow()
    candidate.updated_at = _utcnow()
    candidate.notes = (candidate.notes or "") + f"\n[reject] {reason}"

    document = db.get(ParsedDocument, candidate.document_id)
    _emit_rc_event(
        db,
        document.task_id if document and document.task else None,
        "rejected",
        {"release_candidate_id": candidate.id, "reason": reason[:200]},
    )
    return get_candidate_status(db, candidate_id)


def get_candidate_status(db: Session, candidate_id: int) -> dict[str, Any]:
    candidate = db.get(ContentReleaseCandidate, candidate_id)
    if not candidate:
        raise ReleaseCandidateError(f"Candidate {candidate_id} not found")
    revision = db.get(DocumentRevision, candidate.document_revision_id)
    latest = get_latest_revision(db, candidate.document_id)
    stale = latest is not None and revision is not None and latest.id != revision.id

    runs = db.scalars(
        select(PublishRun)
        .where(PublishRun.release_candidate_id == candidate.id)
        .order_by(PublishRun.id.desc())
        .limit(5)
    ).all()

    return {
        "id": candidate.id,
        "project_id": candidate.project_id,
        "document_id": candidate.document_id,
        "document_revision_id": candidate.document_revision_id,
        "revision_number": revision.revision_number if revision else None,
        "revision_stale": stale,
        "status": candidate.status,
        "draft_review_status": candidate.draft_review_status,
        "draft_reviewed_at": candidate.draft_reviewed_at.isoformat() if candidate.draft_reviewed_at else None,
        "qa_score": candidate.qa_score,
        "blocking_issues": candidate.blocking_issues_json or [],
        "warnings": candidate.warnings_json or [],
        "checklist": candidate.checklist_json or {},
        "publish_target_id": candidate.publish_target_id,
        "payload_version": candidate.payload_version,
        "notes": candidate.notes,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "approved_at": candidate.approved_at.isoformat() if candidate.approved_at else None,
        "rejected_at": candidate.rejected_at.isoformat() if candidate.rejected_at else None,
        "published_at": candidate.published_at.isoformat() if candidate.published_at else None,
        "publish_runs": [{"id": r.id, "status": r.status, "dry_run": r.dry_run} for r in runs],
    }


def list_release_candidates_for_document(db: Session, document_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.document_id == document_id)
        .order_by(ContentReleaseCandidate.id.desc())
        .limit(limit)
    ).all()
    return [get_candidate_status(db, r.id) for r in rows]


def get_latest_candidate_summary(db: Session, document_id: int) -> dict[str, Any]:
    row = db.scalar(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.document_id == document_id)
        .order_by(ContentReleaseCandidate.id.desc())
    )
    if not row:
        return {"exists": False, "status": None, "qa_score": None, "blocking_issues": []}
    return {
        "exists": True,
        "id": row.id,
        "status": row.status,
        "qa_score": row.qa_score,
        "blocking_issues": row.blocking_issues_json or [],
    }


def build_payload_preview(db: Session, candidate_id: int) -> dict[str, Any]:
    candidate = db.get(ContentReleaseCandidate, candidate_id)
    if not candidate:
        raise ReleaseCandidateError(f"Candidate {candidate_id} not found")

    blocking = list(candidate.blocking_issues_json or [])
    if candidate.status == RC_REJECTED:
        blocking.append({"id": "rejected", "label": "Candidate rejected", "detail": candidate.notes})

    document = db.get(ParsedDocument, candidate.document_id)
    revision = db.get(DocumentRevision, candidate.document_revision_id)
    latest = get_latest_revision(db, candidate.document_id)
    if latest and revision and latest.id != revision.id:
        blocking.append({
            "id": "revision_stale",
            "label": "Revision stale",
            "detail": f"latest revision #{latest.revision_number} differs from candidate snapshot",
        })

    if blocking:
        return {"valid": False, "blocking_issues": blocking, "payload": None}

    if candidate.status not in (RC_QA_PASSED, RC_APPROVED, RC_PUBLISHED_DRAFT):
        run_release_qa(db, candidate_id)
        db.refresh(candidate)
        if candidate.blocking_issues_json:
            return {
                "valid": False,
                "blocking_issues": candidate.blocking_issues_json,
                "payload": None,
            }

    task = document.task if document else None
    project = resolve_task_project(db, task) if task else None
    target = db.get(PublishTarget, candidate.publish_target_id) if candidate.publish_target_id else None
    seo = _latest_seo(db, candidate.document_id)
    review = _latest_review(db, candidate.document_id)

    if not all([document, task, project, target, seo, revision]):
        return {"valid": False, "blocking_issues": [{"id": "missing_context", "label": "Missing publish context"}], "payload": None}

    media_block = build_media_block_for_publish(db, document.id)
    payload = build_publish_payload(
        candidate.payload_version,
        document=document,
        task=task,
        project=project,
        target=target,
        seo=seo,
        review=review,
        media=media_block,
        revision_id=revision.id,
    )
    return {"valid": True, "blocking_issues": [], "payload": payload, "payload_version": candidate.payload_version}


def publish_draft_from_candidate(db: Session, candidate_id: int) -> dict[str, Any]:
    candidate = db.get(ContentReleaseCandidate, candidate_id)
    if not candidate:
        raise ReleaseCandidateError(f"Candidate {candidate_id} not found")
    if candidate.status != RC_APPROVED:
        raise ReleaseCandidateError(f"Publish requires approved status, got {candidate.status}")

    latest = get_latest_revision(db, candidate.document_id)
    revision = db.get(DocumentRevision, candidate.document_revision_id)
    if latest and revision and latest.id != revision.id:
        raise ReleaseCandidateError("Document revision changed; create a new release candidate")

    if not candidate.publish_target_id:
        raise ReleaseCandidateError("No publish target on candidate")

    result = publish_draft_for_document(
        db,
        candidate.document_id,
        publish_target_id=candidate.publish_target_id,
        dry_run=None,
        force=False,
        document_revision_id=candidate.document_revision_id,
        release_candidate_id=candidate.id,
    )

    document = db.get(ParsedDocument, candidate.document_id)
    if result.success:
        candidate.status = RC_PUBLISHED_DRAFT
        candidate.published_at = _utcnow()
        candidate.updated_at = _utcnow()
        _emit_rc_event(
            db,
            document.task_id if document and document.task else None,
            "published",
            {"release_candidate_id": candidate.id, "publish_run_id": result.publish_run_id},
        )
    else:
        _emit_rc_event(
            db,
            document.task_id if document and document.task else None,
            "publish_failed",
            {"release_candidate_id": candidate.id, "error": result.error_message},
        )

    return {
        "candidate_id": candidate.id,
        "success": result.success,
        "publish_run_id": result.publish_run_id,
        "status": result.status,
        "error_message": result.error_message,
        "duplicate": result.duplicate,
        "candidate_status": candidate.status,
    }
