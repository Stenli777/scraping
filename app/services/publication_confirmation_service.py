"""Manual public publication confirmation — Scrap records only, no CRMFlow24 writes."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.models.seo_metadata import SeoMetadata
from app.services.pipeline_event_service import emit_pipeline_event

logger = logging.getLogger(__name__)

CONFIRMATION_STAGE = "public_confirmation"
BASE_URL = "https://crmflow24.ru"
BLOG_PATH = "/blog"

VISIBILITY_UNKNOWN = "unknown"
VISIBILITY_NOT_PUBLIC = "not_public"
VISIBILITY_PUBLIC = "public"
VISIBILITY_INCONSISTENT = "inconsistent"

PUBLIC_STATUS_UNKNOWN = "unknown"
PUBLIC_STATUS_NOT_PUBLIC = "not_public"
PUBLIC_STATUS_PUBLIC = "public"


class PublicationConfirmationError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _emit_event(db: Session, document_id: int, action: str, payload: dict[str, Any]) -> None:
    doc = db.get(ParsedDocument, document_id)
    if not doc or not doc.task_id:
        return
    try:
        emit_pipeline_event(db, doc.task_id, CONFIRMATION_STAGE, status=action, payload=payload)
    except Exception as exc:
        logger.warning("public_confirmation pipeline event failed: %s", exc)


def _get_publication(db: Session, publication_record_id: int) -> PublicationRecord:
    pub = db.get(PublicationRecord, publication_record_id)
    if not pub:
        raise PublicationConfirmationError(f"Publication record {publication_record_id} not found")
    return pub


def _slug_for_publication(db: Session, pub: PublicationRecord) -> str | None:
    seo = db.scalar(
        select(SeoMetadata).where(SeoMetadata.document_id == pub.document_id).order_by(SeoMetadata.id.desc())
    )
    if seo and seo.slug:
        return seo.slug.strip()
    meta = pub.metadata_json or {}
    if isinstance(meta.get("slug"), str) and meta["slug"].strip():
        return meta["slug"].strip()
    return None


def resolve_public_url(db: Session, pub: PublicationRecord) -> str | None:
    """Build candidate public URL from slug; never treat CRMFlow24 admin draft URL as public."""
    if pub.public_url and "/admin/" not in pub.public_url:
        return pub.public_url
    slug = _slug_for_publication(db, pub)
    if not slug:
        return None
    return f"{BASE_URL.rstrip('/')}{BLOG_PATH}/{slug}"


def _search_terms(db: Session, pub: PublicationRecord) -> list[str]:
    terms: list[str] = []
    slug = _slug_for_publication(db, pub)
    if slug:
        terms.append(slug)
    seo = db.scalar(
        select(SeoMetadata).where(SeoMetadata.document_id == pub.document_id).order_by(SeoMetadata.id.desc())
    )
    if seo and seo.seo_title and seo.seo_title not in terms:
        terms.append(seo.seo_title)
    if pub.external_url and "/admin/" in (pub.external_url or ""):
        m = re.search(r"/posts/([^/?#]+)", pub.external_url)
        if m:
            terms.append(m.group(1))
    return [t for t in terms if t and len(t) >= 4]


def _derive_visibility_status(blog: bool, sitemap: bool, rss: bool) -> str:
    if blog and sitemap and rss:
        return VISIBILITY_PUBLIC
    if not blog and not sitemap and not rss:
        return VISIBILITY_NOT_PUBLIC
    return VISIBILITY_INCONSISTENT


def analytics_ready(pub: PublicationRecord) -> bool:
    return (
        pub.publication_status == "published"
        and pub.public_visibility_status == VISIBILITY_PUBLIC
        and pub.public_confirmed_at is not None
    )


def _sync_release_candidate(db: Session, pub: PublicationRecord, public_status: str) -> None:
    if not pub.publish_run_id:
        return
    run = db.get(PublishRun, pub.publish_run_id)
    if not run or not run.release_candidate_id:
        return
    cand = db.get(ContentReleaseCandidate, run.release_candidate_id)
    if not cand:
        return
    cand.public_status = public_status
    if public_status == PUBLIC_STATUS_PUBLIC:
        cand.public_confirmed_at = pub.public_confirmed_at or _utcnow()
    cand.updated_at = _utcnow()


def check_public_visibility(db: Session, publication_record_id: int) -> dict[str, Any]:
    """GET-only checks against public CRMFlow24 pages; updates publication_record fields."""
    pub = _get_publication(db, publication_record_id)
    terms = _search_terms(db, pub)
    if not terms:
        raise PublicationConfirmationError("No slug or search terms available for visibility check")

    public_url = resolve_public_url(db, pub)
    paths = [BLOG_PATH, "/sitemap.xml", "/rss.xml"]
    checks: dict[str, bool] = {"blog": False, "sitemap": False, "rss": False}
    detail: dict[str, Any] = {"terms": terms, "paths": {}, "public_url_candidate": public_url}

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for path in paths:
            url = f"{BASE_URL.rstrip('/')}{path}"
            try:
                resp = client.get(url)
                body = (resp.text or "").lower()
            except Exception as exc:
                detail["paths"][path] = {"error": str(exc)[:200], "visible": False}
                continue
            visible = any(term.lower() in body for term in terms)
            key = path.lstrip("/").replace(".xml", "")
            if key == "blog":
                checks["blog"] = visible
            elif key == "sitemap":
                checks["sitemap"] = visible
            elif key == "rss":
                checks["rss"] = visible
            detail["paths"][path] = {"visible": visible, "http_status": resp.status_code}

        if public_url:
            try:
                resp = client.get(public_url)
                detail["public_url_probe"] = {
                    "url": public_url,
                    "http_status": resp.status_code,
                    "ok": resp.status_code == 200,
                }
            except Exception as exc:
                detail["public_url_probe"] = {"url": public_url, "error": str(exc)[:200]}

    status = _derive_visibility_status(checks["blog"], checks["sitemap"], checks["rss"])
    now = _utcnow()
    pub.public_visibility_status = status
    pub.public_visibility_checked_at = now
    pub.public_visible_in_blog = checks["blog"]
    pub.public_visible_in_sitemap = checks["sitemap"]
    pub.public_visible_in_rss = checks["rss"]
    if public_url:
        pub.public_url = public_url
    pub.last_checked_at = now
    pub.updated_at = now

    cand_status = PUBLIC_STATUS_UNKNOWN
    if status == VISIBILITY_PUBLIC:
        cand_status = PUBLIC_STATUS_PUBLIC
    elif status == VISIBILITY_NOT_PUBLIC:
        cand_status = PUBLIC_STATUS_NOT_PUBLIC
    _sync_release_candidate(db, pub, cand_status)

    _emit_event(
        db,
        pub.document_id,
        "visibility_checked",
        {"publication_id": pub.id, "status": status, "checks": checks},
    )

    return {
        "publication_record_id": pub.id,
        "status": status,
        "public_url": pub.public_url,
        "checks": checks,
        "analytics_ready": analytics_ready(pub),
        "detail": detail,
        "checked_at": now.isoformat(),
    }


def get_publication_confirmation_status(db: Session, publication_record_id: int) -> dict[str, Any]:
    pub = _get_publication(db, publication_record_id)
    return {
        "publication_record_id": pub.id,
        "document_id": pub.document_id,
        "publication_status": pub.publication_status,
        "public_visibility_status": pub.public_visibility_status,
        "public_url": pub.public_url,
        "external_url": pub.external_url,
        "public_visible_in_blog": pub.public_visible_in_blog,
        "public_visible_in_sitemap": pub.public_visible_in_sitemap,
        "public_visible_in_rss": pub.public_visible_in_rss,
        "public_visibility_checked_at": pub.public_visibility_checked_at.isoformat()
        if pub.public_visibility_checked_at
        else None,
        "public_confirmed_at": pub.public_confirmed_at.isoformat() if pub.public_confirmed_at else None,
        "public_confirmed_by": pub.public_confirmed_by,
        "public_confirmation_notes": pub.public_confirmation_notes,
        "analytics_ready": analytics_ready(pub),
        "draft_review_status": pub.draft_review_status,
    }


def confirm_publication(
    db: Session,
    publication_record_id: int,
    *,
    confirmed_by: str = "operator",
    notes: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    pub = _get_publication(db, publication_record_id)

    if pub.publication_status == "published" and pub.public_confirmed_at:
        return {
            "idempotent": True,
            **get_publication_confirmation_status(db, publication_record_id),
        }

    check = check_public_visibility(db, publication_record_id)
    if check["status"] != VISIBILITY_PUBLIC and not force:
        if not notes or len(notes.strip()) < 10:
            raise PublicationConfirmationError(
                "Visibility is not public; provide notes (min 10 chars) to force confirm, or run check after manual publish"
            )

    now = _utcnow()
    pub.publication_status = "published"
    if not pub.published_at:
        pub.published_at = now
    pub.public_confirmed_at = now
    pub.public_confirmed_by = confirmed_by
    pub.public_confirmation_notes = notes
    if check["status"] == VISIBILITY_PUBLIC:
        pub.public_visibility_status = VISIBILITY_PUBLIC
    pub.updated_at = now

    _sync_release_candidate(db, pub, PUBLIC_STATUS_PUBLIC)

    _emit_event(
        db,
        pub.document_id,
        "confirmed_public",
        {"publication_id": pub.id, "confirmed_by": confirmed_by, "force": force},
    )

    return {
        "idempotent": False,
        **get_publication_confirmation_status(db, publication_record_id),
    }


def mark_not_public(
    db: Session,
    publication_record_id: int,
    *,
    notes: str | None = None,
) -> dict[str, Any]:
    pub = _get_publication(db, publication_record_id)
    now = _utcnow()
    pub.public_visibility_status = VISIBILITY_NOT_PUBLIC
    pub.public_visible_in_blog = False
    pub.public_visible_in_sitemap = False
    pub.public_visible_in_rss = False
    pub.public_visibility_checked_at = now
    if notes:
        pub.public_confirmation_notes = notes
    pub.updated_at = now
    _sync_release_candidate(db, pub, PUBLIC_STATUS_NOT_PUBLIC)
    _emit_event(db, pub.document_id, "marked_not_public", {"publication_id": pub.id})
    return get_publication_confirmation_status(db, publication_record_id)
