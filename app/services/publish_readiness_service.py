"""Publish readiness checks for admin and API."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_publishing_enabled
from app.models.parsed_document import ParsedDocument
from app.models.publish_target import PublishTarget
from app.models.review_result import ReviewResult
from app.services.project_profile_service import resolve_task_project
from app.services.publish_service import _latest_review, _latest_seo, find_duplicate_publish_run
from app.publishers.validators import PAYLOAD_VERSION


def get_publish_readiness(
    db: Session,
    document_id: int,
    *,
    publish_target_id: int | None = None,
) -> dict:
    missing: list[str] = []
    warnings: list[str] = []
    checks: dict = {
        "review_take": None,
        "review_score": None,
        "seo_exists": False,
        "rewritten_exists": False,
        "target_enabled": False,
        "project_enabled": False,
        "publishing_enabled": is_publishing_enabled(),
        "duplicate_publish": False,
        "force_required_for_duplicate": False,
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

    ready = len(missing) == 0
    return {
        "ready": ready,
        "missing": missing,
        "warnings": warnings,
        "checks": checks,
    }
