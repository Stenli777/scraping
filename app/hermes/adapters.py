"""Payload builders for Hermes orchestration tasks."""

from typing import Any


def build_research_payload(
    *,
    source_url: str,
    title: str,
    clean_text: str,
    rewritten_text: str | None,
    seo_snapshot: dict | None,
    profile_context: str | None,
) -> dict[str, Any]:
    return {
        "task": "research_summary",
        "source_url": source_url,
        "title": title,
        "clean_excerpt": (clean_text or "")[:8000],
        "rewritten_excerpt": (rewritten_text or "")[:8000] if rewritten_text else "",
        "seo": seo_snapshot or {},
        "profile_context": profile_context or "",
        "instructions": (
            "Produce JSON with keys: summary (string), angle_ideas (array of strings), "
            "audience_notes (string), risks (array of strings)."
        ),
    }


def build_campaign_payload(
    *,
    project_slug: str,
    profile_context: str,
    topics: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "task": "campaign_ideas",
        "project_slug": project_slug,
        "profile_context": profile_context,
        "topics": topics or [],
        "instructions": (
            "Produce JSON with keys: campaign_name (string), ideas (array of objects with "
            "title, angle, target_audience, suggested_format)."
        ),
    }


def build_critique_payload(
    *,
    source_url: str,
    rewritten_text: str,
    seo_snapshot: dict | None,
    quality_snapshot: dict | None,
    profile_context: str | None,
) -> dict[str, Any]:
    return {
        "task": "rewrite_critique",
        "source_url": source_url,
        "content": (rewritten_text or "")[:12000],
        "seo": seo_snapshot or {},
        "quality": quality_snapshot or {},
        "profile_context": profile_context or "",
        "instructions": (
            "Produce JSON with keys: strengths (array), weaknesses (array), "
            "recommendations (array), priority_fixes (array)."
        ),
    }


def cliproxy_system_prompt(task_kind: str) -> str:
    return (
        "You are Hermes-style orchestration assistant for Scrap content factory. "
        f"Task: {task_kind}. Respond ONLY with valid JSON matching the instructions in the user message."
    )
