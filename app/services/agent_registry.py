"""Operator-facing labels for prompt templates (agents)."""

from __future__ import annotations

from typing import Any

# technical key -> UI metadata (does not change DB keys)
AGENT_REGISTRY: dict[str, dict[str, str]] = {
    "review_article": {
        "agent_name": "Агент-рецензент источника",
        "short_name": "Рецензент",
        "purpose": "Решает, брать ли статью в работу",
        "stage": "review",
    },
    "rewrite_article": {
        "agent_name": "Агент-писатель",
        "short_name": "Писатель",
        "purpose": "Пишет новую статью на основе очищенного источника",
        "stage": "rewrite",
    },
    "seo_enrich": {
        "agent_name": "Агент SEO-специалист",
        "short_name": "SEO",
        "purpose": "Готовит title, slug, meta, tags, FAQ",
        "stage": "seo",
    },
    "quality_review": {
        "agent_name": "Агент-редактор качества",
        "short_name": "Редактор качества",
        "purpose": "Оценивает готовую статью перед публикацией",
        "stage": "quality",
    },
    "topic_cleanup_v1": {
        "agent_name": "Агент тематической чистки",
        "short_name": "Темы",
        "purpose": "Убирает мусорные темы и улучшает topic extraction",
        "stage": "strategy",
    },
}

KNOWN_AGENT_KEYS = tuple(AGENT_REGISTRY.keys())


def get_agent_meta(key: str) -> dict[str, str]:
    meta = AGENT_REGISTRY.get(key)
    if meta:
        return {**meta, "key": key}
    return {
        "key": key,
        "agent_name": key,
        "short_name": key,
        "purpose": "Промпт без описания в реестре",
        "stage": "other",
    }


def list_agents() -> list[dict[str, Any]]:
    return [get_agent_meta(k) for k in KNOWN_AGENT_KEYS]
