from functools import lru_cache

from app.core.config import get_settings


@lru_cache
def is_hermes_enabled() -> bool:
    return get_settings().enable_hermes


@lru_cache
def is_hermes_reasoning_enabled() -> bool:
    return get_settings().enable_hermes and get_settings().enable_hermes_reasoning


@lru_cache
def is_hermes_campaigns_enabled() -> bool:
    return get_settings().enable_hermes and get_settings().enable_hermes_campaigns


@lru_cache
def is_hermes_research_enabled() -> bool:
    return get_settings().enable_hermes and (
        get_settings().enable_hermes_research or get_settings().enable_hermes_reasoning
    )


@lru_cache
def is_auto_publish_enabled() -> bool:
    return get_settings().enable_auto_publish


@lru_cache
def is_seo_enrich_enabled() -> bool:
    return get_settings().enable_seo_enrich


@lru_cache
def is_llm_review_enabled() -> bool:
    return get_settings().enable_llm_review


@lru_cache
def is_project_profiles_enabled() -> bool:
    return get_settings().enable_project_profiles


@lru_cache
def is_publishing_enabled() -> bool:
    return get_settings().enable_publishing


@lru_cache
def is_source_discovery_enabled() -> bool:
    return get_settings().enable_source_discovery


@lru_cache
def is_quality_review_enabled() -> bool:
    return get_settings().enable_quality_review


@lru_cache
def is_editorial_workflow_enabled() -> bool:
    return get_settings().enable_editorial_workflow


def all_flags() -> dict[str, bool]:
    return {
        "ENABLE_HERMES": is_hermes_enabled(),
        "ENABLE_HERMES_REASONING": is_hermes_reasoning_enabled(),
        "ENABLE_HERMES_CAMPAIGNS": is_hermes_campaigns_enabled(),
        "ENABLE_HERMES_RESEARCH": is_hermes_research_enabled(),
        "ENABLE_AUTO_PUBLISH": is_auto_publish_enabled(),
        "ENABLE_SEO_ENRICH": is_seo_enrich_enabled(),
        "ENABLE_LLM_REVIEW": is_llm_review_enabled(),
        "ENABLE_PROJECT_PROFILES": is_project_profiles_enabled(),
        "ENABLE_PUBLISHING": is_publishing_enabled(),
        "ENABLE_SOURCE_DISCOVERY": is_source_discovery_enabled(),
        "ENABLE_QUALITY_REVIEW": is_quality_review_enabled(),
        "ENABLE_EDITORIAL_WORKFLOW": is_editorial_workflow_enabled(),
    }
