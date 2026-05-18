"""Production pilot workflow — candidate scoring, next actions, status refresh."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import EditorialStatus
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.content_pilot import (
    PILOT_ITEM_STATUSES,
    PILOT_STATUSES,
    ContentPilot,
    ContentPilotItem,
)
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.publication_record import PublicationRecord
from app.models.seo_metadata import SeoMetadata
from app.services.publish_readiness_service import get_publish_readiness
from app.services.publication_confirmation_service import analytics_ready
from app.services.publish_service import _latest_review, _latest_seo
from app.services.quality_service import get_latest_quality_score
from app.services.release_candidate_service import (
    RC_APPROVED,
    RC_ARCHIVED,
    RC_DRAFT,
    RC_PUBLISHED_DRAFT,
    RC_QA_FAILED,
    RC_QA_PASSED,
    RC_REJECTED,
    get_latest_candidate_summary,
    list_release_candidates_for_document,
)
from app.services.strategy_gate_service import detect_test_document


class PilotServiceError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _project_by_slug(db: Session, slug: str) -> Project:
    project = db.scalar(select(Project).where(Project.slug == slug))
    if not project:
        raise PilotServiceError(f"Project slug '{slug}' not found")
    return project


def create_pilot(
    db: Session,
    project_id: int,
    name: str,
    *,
    slug: str | None = None,
    target_count: int = 5,
    description: str | None = None,
    status: str = "draft",
) -> ContentPilot:
    if status not in PILOT_STATUSES:
        raise PilotServiceError(f"Invalid pilot status: {status}")
    slug_val = slug or name.lower().replace(" ", "-")[:128]
    existing = db.scalar(
        select(ContentPilot).where(
            ContentPilot.project_id == project_id, ContentPilot.slug == slug_val
        )
    )
    if existing:
        raise PilotServiceError(f"Pilot slug already exists: {slug_val}")
    pilot = ContentPilot(
        project_id=project_id,
        name=name,
        slug=slug_val,
        description=description,
        status=status,
        target_count=target_count,
    )
    db.add(pilot)
    db.flush()
    return pilot


def add_document_to_pilot(
    db: Session,
    pilot_id: int,
    document_id: int,
    *,
    priority: int = 50,
) -> ContentPilotItem:
    pilot = db.get(ContentPilot, pilot_id)
    if not pilot:
        raise PilotServiceError(f"Pilot {pilot_id} not found")
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        raise PilotServiceError(f"Document {document_id} not found")
    dup = db.scalar(
        select(ContentPilotItem).where(
            ContentPilotItem.pilot_id == pilot_id,
            ContentPilotItem.document_id == document_id,
        )
    )
    if dup:
        raise PilotServiceError(f"Document {document_id} already in pilot {pilot_id}")
    scored = score_pilot_candidate(db, document_id, project_id=pilot.project_id)
    item = ContentPilotItem(
        pilot_id=pilot_id,
        document_id=document_id,
        priority=priority,
        status="blocked" if scored["blockers"] else "candidate",
        next_action=scored["next_action"],
        blockers_json={"blockers": scored["blockers"], "warnings": scored["warnings"], "score": scored["score"]},
    )
    _link_item_refs(db, item)
    db.add(item)
    db.flush()
    refresh_pilot_item_status(db, item.id)
    return item


def remove_document_from_pilot(db: Session, pilot_id: int, document_id: int) -> None:
    item = db.scalar(
        select(ContentPilotItem).where(
            ContentPilotItem.pilot_id == pilot_id,
            ContentPilotItem.document_id == document_id,
        )
    )
    if not item:
        raise PilotServiceError(f"Document {document_id} not in pilot {pilot_id}")
    db.delete(item)
    db.flush()
    refresh_pilot_status(db, pilot_id)


def _link_item_refs(db: Session, item: ContentPilotItem) -> None:
    rc = db.scalar(
        select(ContentReleaseCandidate)
        .where(ContentReleaseCandidate.document_id == item.document_id)
        .order_by(ContentReleaseCandidate.id.desc())
    )
    if rc and rc.status != RC_ARCHIVED:
        item.release_candidate_id = rc.id
    pub = db.scalar(
        select(PublicationRecord)
        .where(PublicationRecord.document_id == item.document_id)
        .order_by(PublicationRecord.id.desc())
    )
    if pub:
        item.publication_record_id = pub.id


def score_pilot_candidate(
    db: Session,
    document_id: int,
    *,
    project_id: int | None = None,
) -> dict[str, Any]:
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return {"document_id": document_id, "score": 0, "next_action": "blocked", "blockers": ["document_not_found"], "warnings": []}

    seo = _latest_seo(db, document_id)
    review = _latest_review(db, document_id)
    quality = get_latest_quality_score(db, document_id)
    readiness = get_publish_readiness(db, document_id)
    slug = seo.slug if seo else ""
    title = (seo.seo_title if seo else None) or (doc.metadata_json or {}).get("title") or ""
    is_test, test_reason = detect_test_document(
        title=str(title), text=doc.rewritten_text or doc.clean_text or "", slug=slug
    )

    score = 50
    blockers: list[str] = []
    warnings: list[str] = list(readiness.get("warnings") or [])

    if is_test:
        score -= 50
        blockers.append("smoke_test_document")
        if test_reason:
            warnings.append(test_reason)

    topics = (doc.metadata_json or {}).get("topics") or {}
    if topics.get("strategy_allowed") is False:
        score -= 30
        blockers.append("strategy_blocked")

    if not doc.rewritten_text or not doc.rewritten_text.strip():
        score -= 25
        blockers.append("missing_rewrite")
    else:
        score += 5

    if not seo or not seo.slug:
        score -= 15
        blockers.append("missing_seo")
    else:
        score += 5

    if review:
        if review.take:
            score += 15
        else:
            score -= 20
            blockers.append("review_rejected")
        if review.score is not None:
            if review.score >= 70:
                score += 10
            elif review.score < 50:
                score -= 10
                warnings.append("low_review_score")
    else:
        warnings.append("review_missing")
        score -= 5

    if quality:
        if quality.verdict == "needs_revision":
            score -= 20
            blockers.append("quality_needs_revision")
        elif quality.overall_score is not None:
            if quality.overall_score >= 70:
                score += 15
            elif quality.overall_score < 60:
                score -= 10
                warnings.append("low_quality_score")
    else:
        score -= 10
        warnings.append("quality_missing")

    if doc.editorial_status in (
        EditorialStatus.APPROVED.value,
        EditorialStatus.READY_TO_PUBLISH.value,
        EditorialStatus.PUBLISHED_DRAFT.value,
    ):
        score += 10
    elif doc.editorial_status == EditorialStatus.REJECTED.value:
        blockers.append("editorial_rejected")
        score -= 15
    elif doc.editorial_status == EditorialStatus.NEEDS_REVISION.value:
        blockers.append("editorial_needs_revision")
        score -= 10

    for w in readiness.get("missing") or []:
        if w.startswith("canonical") or "duplicate" in w or "cannibal" in w:
            if "severe" in w or "canonical" in w:
                score -= 25
                blockers.append(w)
            else:
                warnings.append(w)

    pub = db.scalar(
        select(PublicationRecord)
        .where(PublicationRecord.document_id == document_id)
        .order_by(PublicationRecord.id.desc())
    )
    if pub and pub.publication_status == "published" and analytics_ready(pub):
        score += 5

    score = max(0, min(100, score))
    next_action = compute_next_action(db, document_id, blockers=blockers, readiness=readiness)

    return {
        "document_id": document_id,
        "score": score,
        "next_action": next_action,
        "blockers": blockers,
        "warnings": warnings,
    }


def _publication_post_draft_next_action(db: Session, document_id: int) -> str | None:
    """Next step when CRMFlow24 draft already exists (publication record with admin URL)."""
    pub = db.scalar(
        select(PublicationRecord)
        .where(PublicationRecord.document_id == document_id)
        .order_by(PublicationRecord.id.desc())
    )
    if not pub or not pub.external_url:
        return None
    review_st = pub.draft_review_status or "pending"
    if review_st in ("pending", "needs_edits", None):
        return "review_crmflow24_draft"
    if review_st == "rejected":
        return "review_crmflow24_draft"
    if not analytics_ready(pub):
        if pub.public_visibility_status != "public":
            return "manual_publish_in_crmflow24"
        return "check_public_status"
    snap = db.scalar(
        select(AnalyticsSnapshot).where(AnalyticsSnapshot.publication_record_id == pub.id)
    )
    if not snap:
        return "import_analytics"
    return "done"


def compute_next_action(
    db: Session,
    document_id: int,
    *,
    blockers: list[str] | None = None,
    readiness: dict | None = None,
) -> str:
    if blockers is None:
        scored = score_pilot_candidate(db, document_id)
        blockers = scored["blockers"]

    readiness = readiness or get_publish_readiness(db, document_id)
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return "blocked"

    hard_blockers = {"smoke_test_document", "strategy_blocked", "editorial_rejected"}
    if blockers and any(b in hard_blockers for b in blockers):
        return "blocked"
    if blockers and any(b in hard_blockers for b in (readiness.get("missing") or [])):
        return "blocked"

    post_draft = _publication_post_draft_next_action(db, document_id)
    if post_draft:
        return post_draft

    missing = readiness.get("missing") or []
    if "rewritten_text" in missing:
        return "run_rewrite"
    if any(m.startswith("review") for m in missing):
        return "run_review"
    if any(m.startswith("seo") for m in missing):
        return "run_seo"
    if any(m.startswith("quality") for m in missing):
        return "run_quality"
    if any(m.startswith("editorial") for m in missing):
        return "approve_editorial"

    rc_summary = get_latest_candidate_summary(db, document_id)
    rc = None
    if rc_summary and rc_summary.get("id"):
        rc = db.get(ContentReleaseCandidate, rc_summary["id"])

    if not rc or rc.status == RC_ARCHIVED:
        return "create_release_candidate"

    if rc.status == RC_QA_FAILED:
        return "fix_qa_blockers"
    if rc.status in (RC_DRAFT, RC_QA_PASSED):
        return "approve_candidate"
    if rc.status == RC_APPROVED:
        return "publish_draft"
    if rc.status == RC_REJECTED:
        return "create_release_candidate"

    if rc.status == RC_PUBLISHED_DRAFT:
        pub = db.scalar(
            select(PublicationRecord)
            .where(PublicationRecord.document_id == document_id)
            .order_by(PublicationRecord.id.desc())
        )
        if not pub:
            return "publish_draft"
        review_st = pub.draft_review_status or "pending"
        if review_st in ("pending", "needs_edits", None):
            return "review_crmflow24_draft"
        if review_st == "rejected":
            return "review_crmflow24_draft"
        if not analytics_ready(pub):
            if pub.public_visibility_status != "public":
                return "manual_publish_in_crmflow24"
            return "check_public_status"
        snap = db.scalar(
            select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.publication_record_id == pub.id
            )
        )
        if not snap:
            return "import_analytics"
        return "done"

    return "in_progress"


def refresh_pilot_item_status(db: Session, item_id: int) -> ContentPilotItem:
    item = db.get(ContentPilotItem, item_id)
    if not item:
        raise PilotServiceError(f"Pilot item {item_id} not found")
    _link_item_refs(db, item)
    scored = score_pilot_candidate(db, item.document_id, project_id=item.pilot.project_id)
    item.next_action = compute_next_action(db, item.document_id, blockers=scored["blockers"], readiness=None)
    item.blockers_json = {
        "blockers": scored["blockers"],
        "warnings": scored["warnings"],
        "score": scored["score"],
    }
    item.status = _derive_item_status(db, item, scored)
    item.updated_at = _utcnow()
    db.flush()
    return item


def _derive_item_status(db: Session, item: ContentPilotItem, scored: dict[str, Any]) -> str:
    if scored["blockers"] and scored["next_action"] == "blocked":
        return "blocked"
    pub = db.get(PublicationRecord, item.publication_record_id) if item.publication_record_id else None
    if not pub:
        pub = db.scalar(
            select(PublicationRecord)
            .where(PublicationRecord.document_id == item.document_id)
            .order_by(PublicationRecord.id.desc())
        )
    if pub and analytics_ready(pub):
        snap = db.scalar(select(AnalyticsSnapshot).where(AnalyticsSnapshot.publication_record_id == pub.id))
        if snap:
            return "done" if scored["next_action"] == "done" else "analytics_started"
        return "public_confirmed"
    if pub and pub.public_confirmed_at:
        return "public_confirmed"
    rc = db.get(ContentReleaseCandidate, item.release_candidate_id) if item.release_candidate_id else None
    if pub and pub.external_url:
        if pub.draft_review_status == "accepted":
            return "draft_reviewed"
        return "draft_created"
    if rc and rc.status == RC_PUBLISHED_DRAFT:
        if pub and pub.draft_review_status == "accepted":
            return "draft_reviewed"
        return "draft_created"
    if scored["next_action"] in ("create_release_candidate", "run_review", "run_rewrite", "run_seo", "run_quality"):
        return "candidate"
    return "in_progress"


def refresh_pilot_status(db: Session, pilot_id: int) -> ContentPilot:
    pilot = db.get(ContentPilot, pilot_id)
    if not pilot:
        raise PilotServiceError(f"Pilot {pilot_id} not found")
    items = db.scalars(select(ContentPilotItem).where(ContentPilotItem.pilot_id == pilot_id)).all()
    for item in items:
        refresh_pilot_item_status(db, item.id)
    done = sum(1 for i in items if i.status == "done")
    if done >= pilot.target_count and pilot.status == "active":
        pilot.status = "completed"
        pilot.completed_at = _utcnow()
    pilot.updated_at = _utcnow()
    db.flush()
    return pilot


def suggest_pilot_candidates(db: Session, project_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
    in_pilot = set(
        db.scalars(
            select(ContentPilotItem.document_id).join(ContentPilot).where(
                ContentPilot.project_id == project_id
            )
        ).all()
    )
    from app.models.scraping_task import ScrapingTask

    docs = db.scalars(
        select(ParsedDocument)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ScrapingTask.project_id == project_id)
        .order_by(ParsedDocument.id.desc())
        .limit(200)
    ).all()
    scored_list: list[dict[str, Any]] = []
    for doc in docs:
        if doc.id in in_pilot:
            continue
        row = score_pilot_candidate(db, doc.id, project_id=project_id)
        if "smoke_test_document" in row["blockers"]:
            continue
        if row["score"] < 40:
            continue
        seo = _latest_seo(db, doc.id)
        title = (seo.seo_title if seo else None) or doc.source_url or f"Document #{doc.id}"
        row["title"] = title
        scored_list.append(row)
    scored_list.sort(key=lambda x: -x["score"])
    return scored_list[:limit]


def get_pilot_dashboard(db: Session, pilot_id: int) -> dict[str, Any]:
    pilot = db.get(ContentPilot, pilot_id)
    if not pilot:
        raise PilotServiceError(f"Pilot {pilot_id} not found")
    items = db.scalars(
        select(ContentPilotItem)
        .where(ContentPilotItem.pilot_id == pilot_id)
        .order_by(ContentPilotItem.priority.desc(), ContentPilotItem.id.asc())
    ).all()
    rows = []
    for item in items:
        rows.append(build_pilot_item_row(db, item))
    done = sum(1 for r in rows if r["status"] == "done")
    return {
        "pilot": pilot,
        "item_rows": rows,
        "progress": {"done": done, "total": pilot.target_count, "count": len(rows)},
    }


def build_pilot_item_row(db: Session, item: ContentPilotItem) -> dict[str, Any]:
    doc = db.get(ParsedDocument, item.document_id)
    seo = _latest_seo(db, item.document_id)
    title = (seo.seo_title if seo else None) or (doc.source_url if doc else f"Doc #{item.document_id}")
    rc = db.get(ContentReleaseCandidate, item.release_candidate_id) if item.release_candidate_id else None
    pub = db.get(PublicationRecord, item.publication_record_id) if item.publication_record_id else None
    blockers = (item.blockers_json or {}).get("blockers") or []
    warnings = (item.blockers_json or {}).get("warnings") or []
    score = (item.blockers_json or {}).get("score")
    analytics_st = "—"
    if pub:
        if analytics_ready(pub):
            analytics_st = "ready"
        elif pub.public_confirmed_at:
            analytics_st = "confirmed"
        else:
            analytics_st = pub.public_visibility_status or "draft"
    return {
        "item": item,
        "document_id": item.document_id,
        "title": title,
        "score": score,
        "status": item.status,
        "next_action": item.next_action,
        "blockers": blockers,
        "warnings": warnings,
        "rc_status": rc.status if rc else None,
        "draft_review_status": pub.draft_review_status if pub else None,
        "public_status": pub.public_visibility_status if pub else None,
        "analytics_status": analytics_st,
        "publication_id": pub.id if pub else None,
        "release_candidate_id": rc.id if rc else None,
    }


def list_pilots(db: Session, *, project_id: int | None = None) -> list[dict[str, Any]]:
    q = select(ContentPilot).order_by(ContentPilot.id.desc())
    if project_id:
        q = q.where(ContentPilot.project_id == project_id)
    pilots = db.scalars(q).all()
    out = []
    for p in pilots:
        items = db.scalars(select(ContentPilotItem).where(ContentPilotItem.pilot_id == p.id)).all()
        done = sum(1 for i in items if i.status == "done")
        blocked = sum(1 for i in items if i.status == "blocked")
        out.append({
            "pilot": p,
            "item_count": len(items),
            "done_count": done,
            "blocked_count": blocked,
            "progress": f"{done}/{p.target_count}",
        })
    return out


def build_pilot_operations_summary(db: Session) -> dict[str, Any]:
    active = db.scalars(select(ContentPilot).where(ContentPilot.status == "active")).all()
    summaries = []
    for p in active:
        dash = get_pilot_dashboard(db, p.id)
        next_actions: dict[str, int] = {}
        for row in dash["item_rows"]:
            act = row.get("next_action") or "unknown"
            next_actions[act] = next_actions.get(act, 0) + 1
        summaries.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "progress": dash["progress"],
            "blocked": sum(1 for r in dash["item_rows"] if r["status"] == "blocked"),
            "next_actions": next_actions,
        })
    return {"active_pilots": summaries, "active_count": len(active)}


def get_document_pilot_membership(db: Session, document_id: int) -> list[dict[str, Any]]:
    items = db.scalars(
        select(ContentPilotItem).where(ContentPilotItem.document_id == document_id)
    ).all()
    out = []
    for item in items:
        pilot = db.get(ContentPilot, item.pilot_id)
        out.append({
            "pilot_id": pilot.id if pilot else item.pilot_id,
            "pilot_name": pilot.name if pilot else None,
            "pilot_slug": pilot.slug if pilot else None,
            "item_id": item.id,
            "priority": item.priority,
            "status": item.status,
            "next_action": item.next_action,
            "blockers": (item.blockers_json or {}).get("blockers") or [],
        })
    return out


def ensure_crmflow24_first5_pilot(db: Session) -> ContentPilot:
    project = _project_by_slug(db, "crmflow24")
    existing = db.scalar(
        select(ContentPilot).where(
            ContentPilot.project_id == project.id,
            ContentPilot.slug == "crmflow24-first-5",
        )
    )
    if existing:
        if existing.status == "draft":
            existing.status = "active"
            existing.updated_at = _utcnow()
            db.flush()
        return existing
    return create_pilot(
        db,
        project.id,
        "CRMFlow24 First 5",
        slug="crmflow24-first-5",
        description="First production pilot — five articles for CRMFlow24",
        target_count=5,
        status="active",
    )
