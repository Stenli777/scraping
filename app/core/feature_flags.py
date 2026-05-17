from functools import lru_cache

from app.core.config import get_settings


@lru_cache
def is_hermes_enabled() -> bool:
  return get_settings().enable_hermes


@lru_cache
def is_auto_publish_enabled() -> bool:
  return get_settings().enable_auto_publish


@lru_cache
def is_seo_enrich_enabled() -> bool:
  return get_settings().enable_seo_enrich


@lru_cache
def is_llm_review_enabled() -> bool:
  return get_settings().enable_llm_review


def all_flags() -> dict[str, bool]:
  return {
    "ENABLE_HERMES": is_hermes_enabled(),
    "ENABLE_AUTO_PUBLISH": is_auto_publish_enabled(),
    "ENABLE_SEO_ENRICH": is_seo_enrich_enabled(),
    "ENABLE_LLM_REVIEW": is_llm_review_enabled(),
  }
