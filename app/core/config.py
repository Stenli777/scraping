from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "scrap"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8800
    app_secret_key: str = "change-me"

    database_url: str = "postgresql+psycopg2://scrap:scrap@127.0.0.1:5432/scrap"

    worker_poll_interval_seconds: int = 2
    worker_batch_size: int = 5

    http_timeout_seconds: int = 60
    http_user_agent: str = "Mozilla/5.0 (compatible; ScrapBot/0.1)"

    cliproxyapi_base_url: str = ""
    cliproxyapi_api_key: str = ""
    cliproxyapi_default_timeout: int = 120
    cliproxyapi_max_retries: int = 2
    rewriter_provider: str = "mock"
    rewrite_model_alias: str = "local/rewrite-main"
    review_model_alias: str = "local/classifier-fast"
    seo_model_alias: str = "local/seo-main"

    enable_hermes: bool = False
    hermes_base_url: str = ""
    hermes_orchestrate_url: str = ""
    hermes_api_key: str = ""
    hermes_timeout: int = 120
    hermes_max_retries: int = 1
    hermes_default_agent: str = "hermes-smart"
    hermes_allow_cliproxy_fallback: bool = True
    enable_hermes_reasoning: bool = False
    enable_hermes_campaigns: bool = False
    enable_hermes_research: bool = False
    enable_auto_publish: bool = False
    enable_seo_enrich: bool = True
    enable_llm_review: bool = True
    enable_llm_topic_cleanup: bool = True
    topic_cleanup_model_alias: str = "local/classifier-fast"
    min_topic_relevance_for_strategy: int = 60
    enable_async_llm_enrichment: bool = True
    enrichment_max_retries: int = 3
    enrichment_stale_seconds: int = 180
    enrichment_max_concurrent: int = 2
    enrichment_batch_size: int = 3
    enrichment_retention_days: int = 90
    enrichment_degraded_queue_threshold: int = 50
    enrichment_severe_stale_threshold: int = 3
    worker_enrichment_per_poll: int = 1
    topic_cleanup_timeout_seconds: int = 25
    seo_enrich_timeout_seconds: int = 60
    quality_review_timeout_seconds: int = 90
    enable_project_profiles: bool = True
    enable_publishing: bool = True

    crmflow24_export_webhook_url: str = ""
    crmflow24_export_api_key: str = ""
    crmflow24_publish_endpoint: str = ""
    crmflow24_publish_token: str = ""
    scrap_crmflow24_import_url: str = ""
    scrap_crmflow24_import_token: str = ""
    publish_default_timeout: int = 60

    enable_source_discovery: bool = True
    enable_discovery_quality_scoring: bool = True
    discovery_quality_fetch_preview: bool = True
    discovery_quality_fetch_timeout: int = 15
    min_source_quality_score: int = 50
    min_source_relevance_score: int = 40
    max_spam_score_block: int = 70
    max_thin_content_score_block: int = 75
    max_duplicate_risk_block: int = 85
    enable_source_quality_llm_review: bool = False
    discovery_default_max_urls: int = 50
    discovery_default_timeout: int = 30

    enable_quality_review: bool = True
    quality_model_alias: str = "local/qc-reviewer"
    min_quality_score_for_publish: int = 70

    enable_editorial_workflow: bool = True

    enable_media_pipeline: bool = True
    enable_media_generation: bool = False
    media_provider: str = "placeholder"
    media_storage_path: str = "/opt/scrap/storage/media"

    enable_analytics: bool = True
    enable_publication_tracking: bool = True

    enable_scheduler: bool = False
    enable_automation: bool = False
    scheduler_interval_seconds: int = 60
    automation_max_concurrent_runs: int = 1
    automation_global_hourly_limit: int = 50
    automation_run_stale_seconds: int = 600
    automation_run_lock_seconds: int = 1800

    expected_hostname: str = "hermes,psychedelic"
    expected_project_path: str = "/opt/scrap"

    log_level: str = "INFO"
    log_dir: str = "storage/logs"

    @property
    def storage_root(self) -> Path:
        return PROJECT_ROOT / "storage"

    @property
    def backups_root(self) -> Path:
        return self.storage_root / "backups"

    @property
    def media_storage_root(self) -> Path:
        p = Path(self.media_storage_path)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def logs_path(self) -> Path:
        return PROJECT_ROOT / self.log_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_crmflow24_publish_endpoint() -> str:
    s = get_settings()
    return (s.scrap_crmflow24_import_url or s.crmflow24_publish_endpoint or "").strip()


def get_crmflow24_publish_token_env_names() -> tuple[str, ...]:
    """Env var names tried for bearer token (first match wins)."""
    return ("SCRAP_CRMFLOW24_IMPORT_TOKEN", "CRMFLOW24_PUBLISH_TOKEN")
