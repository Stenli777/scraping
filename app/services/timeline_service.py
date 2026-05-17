"""Simple document timeline from pipeline events, editorial, publish."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.discovered_url import DiscoveredUrl
from app.models.document_revision import DocumentRevision
from app.models.parsed_document import ParsedDocument
from app.models.pipeline_event import PipelineEvent
from app.models.publish_run import PublishRun


def build_document_timeline(db: Session, document: ParsedDocument) -> list[dict]:
    task = document.task
    if not task:
        return []

    events: list[dict] = []

    discovered = db.scalar(
        select(DiscoveredUrl)
        .where(DiscoveredUrl.existing_task_id == task.id)
        .order_by(DiscoveredUrl.id.desc())
    )
    if discovered:
        events.append(
            {
                "kind": "discovery",
                "label": "URL discovered",
                "at": discovered.created_at.isoformat() if discovered.created_at else None,
                "detail": discovered.url,
            }
        )

    events.append(
        {
            "kind": "task",
            "label": "Task created",
            "at": task.created_at.isoformat() if task.created_at else None,
            "detail": f"task #{task.id}",
        }
    )

    pipeline = db.scalars(
        select(PipelineEvent)
        .where(PipelineEvent.task_id == task.id)
        .order_by(PipelineEvent.id.asc())
    ).all()
    stage_labels = {
        "rewriting": "Rewrite",
        "seo_enrich_pending": "SEO enrich",
        "quality_review": "Quality review",
        "publishing": "Publish",
        "published_draft": "Published draft",
        "editorial": "Editorial",
    }
    for pe in pipeline:
        label = stage_labels.get(pe.stage, pe.stage)
        if pe.stage == "editorial" and pe.payload_json:
            payload = pe.payload_json
            label = f"Editorial: {payload.get('from')} → {payload.get('to')}"
        events.append(
            {
                "kind": "pipeline",
                "label": label,
                "at": pe.created_at.isoformat() if pe.created_at else None,
                "detail": pe.status,
                "stage": pe.stage,
            }
        )

    revisions = db.scalars(
        select(DocumentRevision)
        .where(DocumentRevision.document_id == document.id)
        .order_by(DocumentRevision.revision_number.asc())
    ).all()
    for rev in revisions:
        events.append(
            {
                "kind": "revision",
                "label": f"Revision #{rev.revision_number}",
                "at": rev.created_at.isoformat() if rev.created_at else None,
                "detail": rev.source_type,
                "revision_number": rev.revision_number,
            }
        )

    runs = db.scalars(
        select(PublishRun)
        .where(PublishRun.document_id == document.id)
        .order_by(PublishRun.id.asc())
    ).all()
    for run in runs:
        rev_no = None
        if run.document_revision_id:
            rev = db.get(DocumentRevision, run.document_revision_id)
            rev_no = rev.revision_number if rev else None
        events.append(
            {
                "kind": "publish",
                "label": "Publish dry-run" if run.dry_run else "Publish",
                "at": run.created_at.isoformat() if run.created_at else None,
                "detail": f"run #{run.id} status={run.status}",
                "revision_number": rev_no,
                "force_used": run.force_used,
            }
        )

    events.sort(key=lambda e: e.get("at") or "")
    return events
