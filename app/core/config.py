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
    enable_auto_publish: bool = False
    enable_seo_enrich: bool = True
    enable_llm_review: bool = True
    enable_project_profiles: bool = True
    enable_publishing: bool = True

    crmflow24_export_webhook_url: str = ""
    crmflow24_export_api_key: str = ""
    crmflow24_publish_endpoint: str = ""
    crmflow24_publish_token: str = ""
    publish_default_timeout: int = 60

    enable_source_discovery: bool = True
    discovery_default_max_urls: int = 50
    discovery_default_timeout: int = 30

    enable_quality_review: bool = True
    quality_model_alias: str = "local/qc-reviewer"
    min_quality_score_for_publish: int = 70

    enable_editorial_workflow: bool = True

    log_level: str = "INFO"
    log_dir: str = "storage/logs"

    @property
    def storage_root(self) -> Path:
        return PROJECT_ROOT / "storage"

    @property
    def backups_root(self) -> Path:
        return self.storage_root / "backups"

    @property
    def logs_path(self) -> Path:
        return PROJECT_ROOT / self.log_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
