"""Aggregate source quality metrics."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import DiscoveredUrlStatus
from app.models.discovered_url import DiscoveredUrl
from app.models.domain_trust_registry import DomainTrustRegistry
from app.models.source_quality_score import SourceQualityScore


def get_source_quality_metrics(db: Session) -> dict[str, Any]:
    total_scored = db.scalar(select(func.count()).select_from(SourceQualityScore)) or 0
    blocked = db.scalar(
        select(func.count()).select_from(SourceQualityScore).where(SourceQualityScore.strategy_allowed.is_(False))
    ) or 0
    avg_quality = db.scalar(select(func.avg(SourceQualityScore.quality_score))) or 0
    avg_relevance = db.scalar(select(func.avg(SourceQualityScore.relevance_score))) or 0
    dup_high = db.scalar(
        select(func.count()).select_from(SourceQualityScore).where(SourceQualityScore.duplicate_risk_score >= 85)
    ) or 0
    ai_warn = db.scalar(
        select(func.count()).select_from(SourceQualityScore).where(SourceQualityScore.ai_noise_score >= 50)
    ) or 0
    trusted_domains = db.scalar(select(func.count()).select_from(DomainTrustRegistry)) or 0
    pending = db.scalar(
        select(func.count()).select_from(DiscoveredUrl).where(
            DiscoveredUrl.status == DiscoveredUrlStatus.QUALITY_PENDING.value
        )
    ) or 0
    quality_blocked_urls = db.scalar(
        select(func.count()).select_from(DiscoveredUrl).where(
            DiscoveredUrl.status == DiscoveredUrlStatus.QUALITY_BLOCKED.value
        )
    ) or 0
    blocked_pct = round(100.0 * blocked / total_scored, 1) if total_scored else 0.0
    return {
        "total_scored_urls": total_scored,
        "blocked_pct": blocked_pct,
        "trusted_domains_count": trusted_domains,
        "duplicate_high_risk_count": dup_high,
        "avg_quality_score": round(float(avg_quality), 1) if avg_quality else None,
        "avg_relevance_score": round(float(avg_relevance), 1) if avg_relevance else None,
        "ai_noise_warnings": ai_warn,
        "quality_pending": pending,
        "quality_blocked_urls": quality_blocked_urls,
    }


def get_source_quality_health(db: Session) -> dict[str, Any]:
    m = get_source_quality_metrics(db)
    status = "ok"
    if m["quality_pending"] > 100:
        status = "degraded"
    return {
        "status": status,
        "blocked_candidates": m["quality_blocked_urls"],
        "avg_quality_score": m["avg_quality_score"],
        "quality_pending": m["quality_pending"],
    }
