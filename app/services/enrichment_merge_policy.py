"""Deterministic-first enrichment merge policy.

Core pipeline NEVER depends on enrichment completion.
Enrichment failure MUST NOT block publish, rewrite, scraping, or discovery.

Merge: deterministic_result + optional_llm_result -> merged_result

Rules:
- deterministic_result is source-of-truth for strategy gate blocks;
- LLM may enrich phrases/keywords but cannot remove required schema fields;
- malformed LLM fields are ignored;
- strategy_allowed from deterministic wins when deterministic blocked;
- LLM cannot fully replace primary_topic with single-token garbage.
"""

from __future__ import annotations

from typing import Any

from app.services.strategy_gate_service import merge_llm_topic_cleanup

_REQUIRED_FIELDS = frozenset({
    "schema_version",
    "primary_topic",
    "secondary_topics",
    "keywords",
    "search_intent",
    "relevance_score",
    "project_fit",
})


def _is_garbage_phrase(value: str) -> bool:
    parts = value.strip().split()
    return len(parts) < 1 or (len(parts) == 1 and len(parts[0]) < 3)


def apply_enrichment_merge(
    deterministic: dict[str, Any],
    llm_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Conservative merge; returns merged dict without strategy gate re-apply."""
    if not llm_data or not isinstance(llm_data, dict):
        return dict(deterministic)

    merged = merge_llm_topic_cleanup(deterministic, llm_data)

    # Ensure required fields always present from deterministic fallback
    for key in _REQUIRED_FIELDS:
        if not merged.get(key) and deterministic.get(key) is not None:
            merged[key] = deterministic[key]

    primary = str(merged.get("primary_topic") or "")
    if _is_garbage_phrase(primary):
        merged["primary_topic"] = deterministic.get("primary_topic") or primary

    for list_key in ("secondary_topics", "keywords", "entities"):
        val = merged.get(list_key)
        if not isinstance(val, list):
            merged[list_key] = list(deterministic.get(list_key) or [])
        else:
            cleaned = [str(x) for x in val if str(x).strip() and not _is_garbage_phrase(str(x))]
            if len(cleaned) < 2 and list_key == "secondary_topics":
                merged[list_key] = list(deterministic.get(list_key) or [])
            else:
                merged[list_key] = cleaned[:15]

    # Deterministic-first: preserve block from deterministic
    if deterministic.get("strategy_allowed") is False:
        merged["strategy_allowed"] = False
        merged["strategy_block_reason"] = deterministic.get("strategy_block_reason")

    merged["enrichment_merge_policy"] = "deterministic_first_v1"
    return merged
