"""Publish readiness checks for admin and API."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import EditorialStatus
from app.core.feature_flags import (
    is_editorial_workflow_enabled,
    is_publishing_enabled,
    is_quality_review_enabled,
)
from app.services.editorial_service import is_editorially_publishable
from app.models.media_asset import MediaAsset
from app.models.parsed_document import ParsedDocument
from app.models.publish_target import PublishTarget
from app.models.review_result import ReviewResult
from app.services.project_profile_service import resolve_task_project
from app.services.publish_service import _latest_review, _latest_seo, find_duplicate_publish_run
from app.services.media_service import get_approved_preview_asset
from app.services.quality_service import MAX_SPAM_SCORE, get_latest_quality_score
from app.publishers.validators import PAYLOAD_VERSION


def get_publish_readiness(
    db: Session,
    document_id: int,
    *,
    publish_target_id: int | None = None,
) -> dict:
    missing: list[str] = []
    warnings: list[str] = []
    settings = get_settings()
    quality_enabled = is_quality_review_enabled()
    editorial_enabled = is_editorial_workflow_enabled()
    min_quality = settings.min_quality_score_for_publish

    checks: dict = {
        "review_take": None,
        "review_score": None,
        "seo_exists": False,
        "rewritten_exists": False,
        "target_enabled": False,
        "project_enabled": False,
        "publishing_enabled": is_publishing_enabled(),
        "quality_review_enabled": quality_enabled,
        "quality_score_exists": False,
        "quality_overall_score": None,
        "quality_verdict": None,
        "quality_spamminess_score": None,
        "min_quality_score_for_publish": min_quality,
        "duplicate_publish": False,
        "force_required_for_duplicate": False,
        "editorial_workflow_enabled": editorial_enabled,
        "editorial_status": None,
        "approved_for_publish": None,
        "current_revision_number": None,
        "media": {
            "preview_exists": False,
            "approved_preview_exists": False,
            "warnings": [],
        },
    }

    document = db.get(ParsedDocument, document_id)
    if not document:
        return {
            "ready": False,
            "missing": ["document"],
            "warnings": [],
            "checks": checks,
        }

    task = document.task
    if not task:
        missing.append("task")
        project = None
    else:
        project = resolve_task_project(db, task)
        if not project:
            missing.append("project")
        else:
            checks["project_enabled"] = bool(project.enabled)
            if not project.enabled:
                missing.append("project_disabled")

    checks["rewritten_exists"] = bool(
        document.rewritten_text and document.rewritten_text.strip()
    )
    if not checks["rewritten_exists"]:
        missing.append("rewritten_text")

    seo = _latest_seo(db, document_id)
    checks["seo_exists"] = seo is not None and bool(seo.slug)
    if not seo:
        missing.append("seo_metadata")
    elif not seo.slug:
        missing.append("seo_metadata.slug")

    if not is_publishing_enabled():
        missing.append("publishing_enabled")

    review = _latest_review(db, document_id)
    meta = document.metadata_json or {}
    review_meta = meta.get("review") or {}
    take = review.take if review is not None else review_meta.get("take")
    score = review.score if review is not None else review_meta.get("score")
    checks["review_take"] = take
    checks["review_score"] = score

    if project:
        min_score = project.minimum_review_score_for_publish or 60
        if project.require_review_take_for_publish and take is False:
            missing.append("review_rejected")
        elif take is None and project.require_review_take_for_publish:
            warnings.append("review_missing")
        if score is not None:
            try:
                if int(score) < min_score:
                    missing.append("review_score_below_threshold")
            except (TypeError, ValueError):
                warnings.append("review_score_invalid")
        elif project.require_review_take_for_publish:
            warnings.append("review_score_missing")

    quality = get_latest_quality_score(db, document_id)
    if quality:
        checks["quality_score_exists"] = True
        checks["quality_overall_score"] = quality.overall_score
        checks["quality_verdict"] = quality.verdict
        checks["quality_spamminess_score"] = quality.spamminess_score

        if quality_enabled:
            if quality.verdict != "approved":
                missing.append("quality_not_approved")
            if quality.overall_score is not None:
                try:
                    if int(quality.overall_score) < min_quality:
                        missing.append("quality_score_below_threshold")
                except (TypeError, ValueError):
                    warnings.append("quality_score_invalid")
            if quality.spamminess_score is not None:
                try:
                    if int(quality.spamminess_score) > MAX_SPAM_SCORE:
                        missing.append("quality_spam_too_high")
                except (TypeError, ValueError):
                    warnings.append("quality_spamminess_invalid")
    elif quality_enabled:
        missing.append("quality_score")
        warnings.append("quality_review_missing")
    elif not quality_enabled:
        if not quality:
            warnings.append("quality_review_optional")

    checks["editorial_status"] = document.editorial_status
    checks["approved_for_publish"] = document.approved_for_publish
    checks["current_revision_number"] = document.current_revision_number

    if editorial_enabled:
        if not is_editorially_publishable(document):
            if document.editorial_status not in (
                EditorialStatus.APPROVED.value,
                EditorialStatus.READY_TO_PUBLISH.value,
                EditorialStatus.PUBLISHED_DRAFT.value,
            ):
                missing.append("editorial_not_approved")
            elif not document.approved_for_publish:
                missing.append("operator_approval_required")
            else:
                missing.append("editorial_not_publishable")
        if document.editorial_status == EditorialStatus.REJECTED.value:
            missing.append("editorial_rejected")
        if document.editorial_status == EditorialStatus.NEEDS_REVISION.value:
            missing.append("editorial_needs_revision")

    enabled_targets: list[PublishTarget] = []
    if project:
        q = select(PublishTarget).where(PublishTarget.project_id == project.id)
        if publish_target_id:
            q = q.where(PublishTarget.id == publish_target_id)
        enabled_targets = list(
            db.scalars(q.where(PublishTarget.enabled.is_(True)).order_by(PublishTarget.id.asc())).all()
        )
        if not enabled_targets:
            missing.append("publish_target")
        else:
            checks["target_enabled"] = True

    if meta.get("rewrite", {}).get("success") is False:
        warnings.append("rewrite_failed")

    target_for_dup = enabled_targets[0] if enabled_targets else None
    if publish_target_id:
        target_for_dup = db.get(PublishTarget, publish_target_id) or target_for_dup
    if target_for_dup:
        dup = find_duplicate_publish_run(
            db,
            document_id=document_id,
            publish_target_id=target_for_dup.id,
            payload_version=PAYLOAD_VERSION,
        )
        if dup:
            checks["duplicate_publish"] = True
            checks["force_required_for_duplicate"] = True
            warnings.append(f"duplicate_publish_run_{dup.id}")

    for target in enabled_targets:
        status = target.default_status or "draft"
        if status != "draft":
            warnings.append(f"target_{target.id}_status_not_draft")

    preview_asset = get_approved_preview_asset(db, document_id)
    any_preview = db.scalar(
        select(MediaAsset)
        .where(
            MediaAsset.document_id == document_id,
            MediaAsset.media_type == "preview",
            MediaAsset.status.in_(["generated", "approved"]),
        )
        .order_by(MediaAsset.id.desc())
        .limit(1)
    )
    checks["media"]["preview_exists"] = any_preview is not None
    checks["media"]["approved_preview_exists"] = preview_asset is not None
    if not checks["media"]["preview_exists"]:
        checks["media"]["warnings"].append("missing_preview_image")
        warnings.append("missing_preview_image")
    elif not checks["media"]["approved_preview_exists"]:
        checks["media"]["warnings"].append("preview_not_approved")
        warnings.append("preview_not_approved")

    ready = len(missing) == 0
    return {
        "ready": ready,
        "missing": missing,
        "warnings": warnings,
        "checks": checks,
    }
