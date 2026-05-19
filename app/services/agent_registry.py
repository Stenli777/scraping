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
        "pipeline_usage": "Этап review после парсинга исходника",
        "accepts": "Заголовок, текст источника, профиль проекта",
        "returns": "Решение take/skip, score, причины и риски",
        "override_effect": "Проектная версия меняет критерии отбора статей только для этого проекта",
    },
    "rewrite_article": {
        "agent_name": "Агент-писатель",
        "short_name": "Писатель",
        "purpose": "Пишет новую статью на основе очищенного источника",
        "stage": "rewrite",
        "pipeline_usage": "Этап rewrite после одобрения рецензии",
        "accepts": "Очищенный текст, URL, профиль и инструкции рерайта",
        "returns": "Новая статья в Markdown",
        "override_effect": "Проектная версия задаёт стиль и правила переписывания для проекта",
    },
    "seo_enrich": {
        "agent_name": "Агент SEO-специалист",
        "short_name": "SEO",
        "purpose": "Готовит title, slug, meta, tags, FAQ",
        "stage": "seo",
        "pipeline_usage": "Этап SEO после рерайта",
        "accepts": "Готовый текст статьи и SEO-инструкции проекта",
        "returns": "SEO-поля и структурированные метаданные",
        "override_effect": "Проектная версия настраивает формат SEO под домен проекта",
    },
    "quality_review": {
        "agent_name": "Агент-редактор качества",
        "short_name": "Редактор качества",
        "purpose": "Оценивает готовую статью перед публикацией",
        "stage": "quality",
        "pipeline_usage": "Этап quality перед editorial/publish",
        "accepts": "Финальный текст, SEO-данные, правила проекта",
        "returns": "Оценки качества, риски и рекомендации",
        "override_effect": "Проектная версия меняет шкалу и фокус проверки качества",
    },
    "topic_cleanup_v1": {
        "agent_name": "Агент тематической чистки",
        "short_name": "Темы",
        "purpose": "Убирает мусорные темы и улучшает topic extraction",
        "stage": "strategy",
        "pipeline_usage": "После deterministic topic_v2, до strategy gate",
        "accepts": "Excerpt, SEO-поля, deterministic JSON, профиль проекта",
        "returns": "JSON с темами, keywords, strategy_allowed",
        "override_effect": "Проектная версия уточняет правила тем и блокировок для проекта",
    },
}

KNOWN_AGENT_KEYS = tuple(AGENT_REGISTRY.keys())

SOURCE_LABELS_RU = {
    "project_override": "Используется проектная версия",
    "global": "Используется глобальный prompt",
    "code_fallback": "Используется fallback из кода",
}


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
        "pipeline_usage": "—",
        "accepts": "—",
        "returns": "—",
        "override_effect": "Проектная настройка заменит глобальный prompt для этого проекта",
    }


def source_label_ru(source: str) -> str:
    return SOURCE_LABELS_RU.get(source, source)


def list_agents() -> list[dict[str, Any]]:
    return [get_agent_meta(k) for k in KNOWN_AGENT_KEYS]
