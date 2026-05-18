"""Strategy intelligence — deterministic-first topic resolution for campaigns."""

from __future__ import annotations

from typing import Any

from app.models.llm_enrichment_job import EnrichmentJobStatus


def get_effective_strategy_topics(metadata_json: dict | None) -> dict[str, Any]:
    """Topics for campaign/cluster intelligence; ignores failed/stale enrichment."""
    meta = metadata_json or {}
    topics = meta.get("topics") or {}
    enrichment_status = meta.get("topics_enrichment_status") or topics.get("llm_cleanup_status")

    deterministic = topics.get("deterministic_result")
    if isinstance(deterministic, dict) and deterministic:
        base = deterministic
    else:
        base = topics

    # Only prefer merged/enhanced result when enrichment completed successfully
    if enrichment_status == "completed":
        merged = topics.get("merged_result")
        if isinstance(merged, dict) and merged:
            return merged

    if enrichment_status in ("queued", "running", "failed", "skipped", "disabled", "pending"):
        return base

    # Legacy: no enrichment status — use topics if strategy_allowed set
    if topics.get("strategy_allowed") is not None:
        return topics

    return base


def topics_eligible_for_campaign_intelligence(topics: dict[str, Any]) -> bool:
    if not topics:
        return False
    if topics.get("strategy_allowed") is False:
        return False
    if int(topics.get("relevance_score") or 0) < 1:
        return False
    if not topics.get("primary_topic"):
        return False
    return True


def enrichment_status_blocks_intelligence(meta: dict | None) -> bool:
    """Failed/stale enrichment must not drive campaign suggestions."""
    if not meta:
        return True
    status = meta.get("topics_enrichment_status") or (meta.get("topics") or {}).get("llm_cleanup_status")
    if status in ("queued", "running"):
        return False  # use deterministic via get_effective_strategy_topics
    if status in ("failed", "skipped"):
        return False
    return False
