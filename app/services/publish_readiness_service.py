"""Publish readiness checks for admin and API."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_publishing_enabled
from app.models.parsed_document import ParsedDocument
from app.models.publish_target import PublishTarget
from app.models.seo_metadata import SeoMetadata
from app.services.project_profile_service import resolve_task_project
from app.services.publish_service import _latest_seo


def get_publish_readiness(db: Session, document_id: int) -> dict:
    missing: list[str] = []
    warnings: list[str] = []

    document = db.get(ParsedDocument, document_id)
    if not document:
        return {"ready": False, "missing": ["document"], "warnings": []}

    task = document.task
    if not task:
        missing.append("task")
        project = None
    else:
        project = resolve_task_project(db, task)
        if not project:
            missing.append("project")

    if not document.rewritten_text or not document.rewritten_text.strip():
        missing.append("rewritten_text")

    seo = _latest_seo(db, document_id)
    if not seo:
        missing.append("seo_metadata")
    elif not seo.slug:
        missing.append("seo_metadata.slug")

    if not is_publishing_enabled():
        missing.append("publishing_enabled")

    enabled_targets: list[PublishTarget] = []
    if project:
        enabled_targets = list(
            db.scalars(
                select(PublishTarget)
                .where(
                    PublishTarget.project_id == project.id,
                    PublishTarget.enabled.is_(True),
                )
                .order_by(PublishTarget.id.asc())
            ).all()
        )
        if not enabled_targets:
            missing.append("publish_target")
    elif "project" not in missing:
        missing.append("publish_target")

    meta = document.metadata_json or {}
    review = meta.get("review") or {}
    if review.get("take") is False:
        warnings.append("review_rejected")
    if meta.get("rewrite", {}).get("success") is False:
        warnings.append("rewrite_failed")
    if not seo and "seo_metadata" not in missing:
        warnings.append("seo_missing")

    for target in enabled_targets:
        status = target.default_status or "draft"
        if status != "draft":
            warnings.append(f"target_{target.id}_status_not_draft")

    ready = len(missing) == 0
    return {"ready": ready, "missing": missing, "warnings": warnings}
