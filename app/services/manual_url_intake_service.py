"""Controlled manual trusted URL intake into discovered_urls."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DiscoveredUrlStatus
from app.core.feature_flags import is_discovery_quality_scoring_enabled
from app.models.discovered_url import DiscoveredUrl
from app.models.source_directory import SourceDirectory
from app.services.article_url_classifier import classify_article_url
from app.services.source_quality_service import score_discovered_url
from app.services.url_normalizer import normalize_url

logger = logging.getLogger(__name__)


@dataclass
class IntakeResult:
    url: str
    discovered_url_id: int | None
    status: str
    duplicate: bool
    article_likelihood: int
    is_article: bool
    error: str | None = None


def _resolve_directory(
    db: Session,
    *,
    project_id: int,
    source_directory_id: int | None,
    url: str,
) -> SourceDirectory | None:
    if source_directory_id:
        return db.get(SourceDirectory, source_directory_id)
    host = (urlparse_hostname(url) or "").lower()
    if "autobit24.ru" in host:
        return db.scalar(
            select(SourceDirectory).where(
                SourceDirectory.project_id == project_id,
                SourceDirectory.name == "autobit24-blog",
            )
        )
    return db.scalar(
        select(SourceDirectory).where(
            SourceDirectory.project_id == project_id,
            SourceDirectory.enabled.is_(True),
        ).order_by(SourceDirectory.id.asc())
    )


def urlparse_hostname(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").lower()


def intake_manual_url(
    db: Session,
    *,
    project_id: int,
    url: str,
    source_directory_id: int | None = None,
    notes: str | None = None,
    score_quality: bool = True,
    enqueue: bool = False,
) -> IntakeResult:
    raw = url.strip()
    if not raw:
        raise ValueError("URL is required")

    classification = classify_article_url(raw)
    if not classification.is_article:
        return IntakeResult(
            url=raw,
            discovered_url_id=None,
            status="rejected",
            duplicate=False,
            article_likelihood=classification.article_likelihood,
            is_article=False,
            error=f"not_article: {','.join(classification.reasons)}",
        )

    try:
        normalized = normalize_url(raw)
    except ValueError as exc:
        return IntakeResult(
            url=raw,
            discovered_url_id=None,
            status="error",
            duplicate=False,
            article_likelihood=classification.article_likelihood,
            is_article=classification.is_article,
            error=str(exc),
        )

    existing = db.scalar(select(DiscoveredUrl).where(DiscoveredUrl.normalized_url == normalized))
    if existing:
        if score_quality and is_discovery_quality_scoring_enabled():
            try:
                score_discovered_url(db, existing.id, fetch_preview=True)
            except Exception as exc:
                logger.warning("quality rescore failed id=%s: %s", existing.id, exc)
        return IntakeResult(
            url=raw,
            discovered_url_id=existing.id,
            status=existing.status,
            duplicate=True,
            article_likelihood=classification.article_likelihood,
            is_article=True,
        )

    directory = _resolve_directory(db, project_id=project_id, source_directory_id=source_directory_id, url=raw)
    if not directory:
        raise ValueError("No source directory for manual intake; create autobit24-blog first")

    record = DiscoveredUrl(
        project_id=project_id,
        source_directory_id=directory.id,
        url=raw,
        normalized_url=normalized,
        canonical_url=normalized,
        title=notes[:512] if notes else None,
        discovery_source="manual",
        status=DiscoveredUrlStatus.DISCOVERED.value,
    )
    db.add(record)
    db.flush()

    if score_quality and is_discovery_quality_scoring_enabled():
        record.status = DiscoveredUrlStatus.QUALITY_PENDING.value
        try:
            row = score_discovered_url(db, record.id, fetch_preview=True)
            details = dict(row.scoring_details_json or {})
            details["article_likelihood"] = classification.article_likelihood
            details["article_reasons"] = classification.reasons
            if notes:
                details["manual_intake_notes"] = notes
            row.scoring_details_json = details
        except Exception as exc:
            logger.warning("manual intake quality failed id=%s: %s", record.id, exc)
            record.status = DiscoveredUrlStatus.DISCOVERED.value

    if enqueue:
        from app.services.discovery_service import enqueue_discovered_url

        enqueue_discovered_url(db, record.id)

    return IntakeResult(
        url=raw,
        discovered_url_id=record.id,
        status=record.status,
        duplicate=False,
        article_likelihood=classification.article_likelihood,
        is_article=True,
    )


def intake_manual_urls_bulk(
    db: Session,
    *,
    project_id: int,
    urls: list[str],
    source_directory_id: int | None = None,
    score_quality: bool = True,
    enqueue: bool = False,
) -> list[IntakeResult]:
    results: list[IntakeResult] = []
    for url in urls:
        line = (url or "").strip()
        if not line or line.startswith("#"):
            continue
        try:
            results.append(
                intake_manual_url(
                    db,
                    project_id=project_id,
                    url=line,
                    source_directory_id=source_directory_id,
                    score_quality=score_quality,
                    enqueue=enqueue,
                )
            )
        except Exception as exc:
            results.append(
                IntakeResult(
                    url=line,
                    discovered_url_id=None,
                    status="error",
                    duplicate=False,
                    article_likelihood=0,
                    is_article=False,
                    error=str(exc),
                )
            )
    return results
