"""Create publication records after successful non-dry publish."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_publication_tracking_enabled
from app.models.content_performance import ContentPerformance
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun

logger = logging.getLogger(__name__)


def create_publication_from_publish_run(
    db: Session,
    *,
    run: PublishRun,
    external_id: str | None,
    external_url: str | None,
    dry_run: bool,
    publication_status: str = "draft",
    remote_status: str | None = None,
) -> PublicationRecord | None:
    if not is_publication_tracking_enabled():
        return None
    if dry_run:
        return None

    from sqlalchemy import select

    existing = db.scalar(
        select(PublicationRecord).where(PublicationRecord.publish_run_id == run.id)
    )
    if existing:
        if remote_status or run.remote_status:
            meta = dict(existing.metadata_json or {})
            meta["remote_status"] = remote_status or run.remote_status
            existing.metadata_json = meta
        return existing

    record = PublicationRecord(
        project_id=run.project_id,
        document_id=run.document_id,
        revision_id=run.document_revision_id,
        publish_run_id=run.id,
        external_article_id=external_id,
        external_url=external_url,
        publication_status=publication_status,
        published_at=datetime.now(timezone.utc),
        metadata_json={
            "payload_version": run.payload_version,
            "response_schema_version": run.response_schema_version,
            "remote_status": remote_status or run.remote_status,
        },
    )
    db.add(record)
    db.flush()

    perf = ContentPerformance(
        project_id=run.project_id,
        document_id=run.document_id,
        publication_record_id=record.id,
        trend="unknown",
        status="average",
        performance_feedback_json={"formula_version": "v1", "ready_for_ai_optimization": False},
    )
    db.add(perf)
    db.flush()
    logger.info(
        "Publication record #%s created for document=%s publish_run=%s",
        record.id,
        run.document_id,
        run.id,
    )
    return record
