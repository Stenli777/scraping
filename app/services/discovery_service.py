"""Controlled source discovery — sitemap + HTML links, manual enqueue only."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import DiscoveredUrlStatus, DiscoveryMode, DiscoverySource
from app.core.feature_flags import is_discovery_quality_scoring_enabled, is_source_discovery_enabled
from app.models.discovered_url import DiscoveredUrl
from app.models.parsed_document import ParsedDocument
from app.models.scraping_task import ScrapingTask
from app.models.source_directory import SourceDirectory
from app.services.discovery_extractors import discover_html_links, discover_sitemap_urls
from app.services.pipeline_event_service import emit_pipeline_event
from app.services.task_service import create_task
from app.services.url_normalizer import is_blocked, matches_patterns, normalize_url

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    success: bool
    source_directory_id: int
    discovered_new: int = 0
    duplicates: int = 0
    blocked: int = 0
    failed: int = 0
    total_candidates: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False


def run_discovery(
    db: Session,
    source_directory_id: int,
    *,
    max_urls: int | None = None,
    dry_run: bool = False,
) -> DiscoveryResult:
    if not is_source_discovery_enabled():
        raise ValueError("Source discovery is disabled (ENABLE_SOURCE_DISCOVERY=false)")

    directory = db.get(SourceDirectory, source_directory_id)
    if not directory:
        raise ValueError(f"Source directory {source_directory_id} not found")
    if not directory.enabled:
        raise ValueError("Source directory is disabled")

    settings = get_settings()
    limit = min(
        max_urls or directory.max_urls_per_run,
        settings.discovery_default_max_urls,
    )
    timeout = settings.discovery_default_timeout
    ua = settings.http_user_agent

    candidates: list[tuple[str, str | None, str]] = []
    mode = directory.discovery_mode

    try:
        if mode in (DiscoveryMode.SITEMAP.value, DiscoveryMode.MIXED.value):
            for url, title in discover_sitemap_urls(
                directory.base_url,
                timeout=timeout,
                user_agent=ua,
                max_urls=limit,
                crawl_delay=directory.crawl_delay_seconds,
            ):
                candidates.append((url, title, DiscoverySource.SITEMAP.value))

        if mode in (DiscoveryMode.HTML_LINKS.value, DiscoveryMode.MIXED.value):
            remaining = limit - len(candidates)
            if remaining > 0:
                for url, title in discover_html_links(
                    directory.base_url,
                    timeout=timeout,
                    user_agent=ua,
                    max_urls=remaining,
                    crawl_delay=directory.crawl_delay_seconds,
                ):
                    candidates.append((url, title, DiscoverySource.HTML_LINK.value))
    except Exception as exc:
        logger.exception("Discovery fetch failed for directory %s", source_directory_id)
        return DiscoveryResult(
            success=False,
            source_directory_id=source_directory_id,
            errors=[str(exc)],
        )

    result = DiscoveryResult(
        success=True,
        source_directory_id=source_directory_id,
        total_candidates=len(candidates),
        dry_run=dry_run,
    )

    if dry_run:
        return result

    for raw_url, title, source in candidates[:limit]:
        _process_candidate(db, directory, raw_url, title, source, result)

    directory.last_discovered_at = datetime.now(timezone.utc)
    db.commit()
    return result


def _process_candidate(
    db: Session,
    directory: SourceDirectory,
    raw_url: str,
    title: str | None,
    discovery_source: str,
    result: DiscoveryResult,
) -> None:
    try:
        normalized = normalize_url(raw_url)
    except ValueError as exc:
        result.failed += 1
        result.errors.append(f"{raw_url}: {exc}")
        return

    if is_blocked(normalized, directory.block_patterns_json):
        result.blocked += 1
        if not dry_run_record_exists(db, normalized):
            db.add(
                DiscoveredUrl(
                    project_id=directory.project_id,
                    source_directory_id=directory.id,
                    url=raw_url,
                    normalized_url=normalized,
                    title=title,
                    discovery_source=discovery_source,
                    status=DiscoveredUrlStatus.BLOCKED.value,
                )
            )
        return

    if directory.allow_patterns_json and not matches_patterns(
        normalized, directory.allow_patterns_json
    ):
        result.blocked += 1
        return

    existing_discovered = db.scalar(
        select(DiscoveredUrl).where(DiscoveredUrl.normalized_url == normalized)
    )
    if existing_discovered:
        existing_discovered.updated_at = datetime.now(timezone.utc)
        if existing_discovered.status == DiscoveredUrlStatus.DISCOVERED.value:
            existing_discovered.status = DiscoveredUrlStatus.DUPLICATE.value
        result.duplicates += 1
        return

    existing_task = db.scalar(
        select(ScrapingTask).where(ScrapingTask.source_url == raw_url).limit(1)
    )
    existing_doc = db.scalar(
        select(ParsedDocument).where(ParsedDocument.source_url == raw_url).limit(1)
    )

    status = DiscoveredUrlStatus.DISCOVERED.value
    dup_of = None
    if existing_task or existing_doc:
        status = DiscoveredUrlStatus.DUPLICATE.value
        result.duplicates += 1
    else:
        result.discovered_new += 1

    record = DiscoveredUrl(
        project_id=directory.project_id,
        source_directory_id=directory.id,
        url=raw_url,
        normalized_url=normalized,
        canonical_url=normalized,
        title=title,
        discovery_source=discovery_source,
        status=status,
        duplicate_of_id=dup_of,
        existing_task_id=existing_task.id if existing_task else None,
        existing_document_id=existing_doc.id if existing_doc else None,
    )
    db.add(record)
    db.flush()
    if is_discovery_quality_scoring_enabled() and status == DiscoveredUrlStatus.DISCOVERED.value:
        record.status = DiscoveredUrlStatus.QUALITY_PENDING.value
        try:
            from app.services.source_quality_service import score_discovered_url
            score_discovered_url(db, record.id, fetch_preview=True)
        except Exception as exc:
            logger.warning("quality scoring failed url=%s: %s", record.id, exc)
            record.status = DiscoveredUrlStatus.DISCOVERED.value


def dry_run_record_exists(db: Session, normalized: str) -> bool:
    return (
        db.scalar(select(DiscoveredUrl).where(DiscoveredUrl.normalized_url == normalized))
        is not None
    )


def enqueue_discovered_url(db: Session, discovered_url_id: int) -> DiscoveredUrl:
    if not is_source_discovery_enabled():
        raise ValueError("Source discovery is disabled")

    from app.services.source_quality_service import can_enqueue_by_quality

    record = db.get(DiscoveredUrl, discovered_url_id)
    if not record:
        raise ValueError(f"Discovered URL {discovered_url_id} not found")

    if record.status == DiscoveredUrlStatus.IGNORED.value:
        raise ValueError("Cannot enqueue ignored URL")
    ok, reason = can_enqueue_by_quality(db, record)
    if not ok:
        raise ValueError(f"Quality gate blocked enqueue: {reason}")
    if record.status == DiscoveredUrlStatus.BLOCKED.value:
        raise ValueError("Cannot enqueue blocked URL")
    if record.status == DiscoveredUrlStatus.ENQUEUED.value and record.existing_task_id:
        return record

    if record.existing_task_id:
        record.status = DiscoveredUrlStatus.ENQUEUED.value
        record.enqueued_at = datetime.now(timezone.utc)
        db.commit()
        return record

    existing_task = db.scalar(
        select(ScrapingTask).where(ScrapingTask.source_url == record.url).limit(1)
    )
    if existing_task:
        record.existing_task_id = existing_task.id
        record.status = DiscoveredUrlStatus.DUPLICATE.value
        db.commit()
        return record

    task = create_task(db, record.url, project_id=record.project_id)
    record.existing_task_id = task.id
    record.status = DiscoveredUrlStatus.ENQUEUED.value
    record.enqueued_at = datetime.now(timezone.utc)

    emit_pipeline_event(
        db,
        task.id,
        "discovered",
        status="enqueued",
        payload={
            "discovered_url_id": record.id,
            "source_directory_id": record.source_directory_id,
            "normalized_url": record.normalized_url,
        },
    )
    db.commit()
    db.refresh(record)
    return record


def ignore_discovered_url(db: Session, discovered_url_id: int) -> DiscoveredUrl:
    record = db.get(DiscoveredUrl, discovered_url_id)
    if not record:
        raise ValueError(f"Discovered URL {discovered_url_id} not found")
    record.status = DiscoveredUrlStatus.IGNORED.value
    record.ignored_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record
