"""Production config validation — warnings only at startup."""

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.feature_flags import (
    is_hermes_enabled,
    is_media_generation_enabled,
    is_media_pipeline_enabled,
    is_publishing_enabled,
)
from app.db.session import SessionLocal
from app.models.publish_target import PublishTarget


@dataclass
class ConfigValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _is_valid_url(url: str) -> bool:
    if not url or not url.strip():
        return False
    try:
        p = urlparse(url.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def validate_config(settings: Settings | None = None, *, check_db: bool = True) -> ConfigValidationResult:
    settings = settings or get_settings()
    result = ConfigValidationResult(ok=True)

    if settings.app_secret_key in ("change-me", "", "changeme"):
        result.warnings.append("APP_SECRET_KEY is default — change in production")

    if settings.app_env == "production" and settings.app_debug:
        result.warnings.append("APP_DEBUG=true in production environment")

    # Storage paths
    for label, path in (
        ("storage_root", settings.storage_root),
        ("backups_root", settings.backups_root),
        ("logs_path", settings.logs_path),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
            if not path.is_dir():
                result.errors.append(f"{label} is not a directory: {path}")
        except OSError as exc:
            result.errors.append(f"Cannot create {label}: {exc}")

    if is_media_pipeline_enabled():
        try:
            settings.media_storage_root.mkdir(parents=True, exist_ok=True)
            if not settings.media_storage_root.is_dir():
                result.errors.append(
                    f"media_storage_root is not a directory: {settings.media_storage_root}"
                )
        except OSError as exc:
            result.errors.append(f"Cannot create media_storage_root: {exc}")

    system_backups = settings.storage_root / "system_backups"
    try:
        (system_backups / "postgres").mkdir(parents=True, exist_ok=True)
        (system_backups / "storage").mkdir(parents=True, exist_ok=True)
        (system_backups / "manifests").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result.warnings.append(f"system_backups dirs: {exc}")

    # URLs
    if settings.cliproxyapi_base_url and not _is_valid_url(settings.cliproxyapi_base_url):
        result.errors.append("CLIPROXYAPI_BASE_URL is malformed")

    if is_hermes_enabled():
        if not settings.hermes_base_url.strip():
            result.errors.append("ENABLE_HERMES=true but HERMES_BASE_URL is empty")
        elif not _is_valid_url(settings.hermes_base_url):
            result.errors.append("HERMES_BASE_URL is malformed")

    if is_media_generation_enabled():
        if settings.media_provider == "placeholder":
            result.warnings.append(
                "ENABLE_MEDIA_GENERATION=true but MEDIA_PROVIDER=placeholder (no real AI provider)"
            )

    if is_publishing_enabled() and check_db:
        try:
            with SessionLocal() as db:
                count = db.scalar(
                    select(func.count())
                    .select_from(PublishTarget)
                    .where(PublishTarget.enabled.is_(True))
                )
                if not count:
                    result.warnings.append(
                        "ENABLE_PUBLISHING=true but no enabled publish targets configured"
                    )
                endpoint = (settings.crmflow24_publish_endpoint or "").strip()
                if not endpoint:
                    result.warnings.append(
                        "ENABLE_PUBLISHING=true but CRMFLOW24_PUBLISH_ENDPOINT is empty"
                    )
        except Exception as exc:
            result.warnings.append(f"Could not check publish targets: {exc}")

    if result.errors:
        result.ok = False
    return result


def validate_config_summary() -> dict:
    v = validate_config()
    settings = get_settings()
    return {
        **v.to_dict(),
        "app_env": settings.app_env,
        "feature_flags": {
            "publishing": is_publishing_enabled(),
            "hermes": is_hermes_enabled(),
            "media_pipeline": is_media_pipeline_enabled(),
            "media_generation": is_media_generation_enabled(),
        },
        "paths": {
            "storage_root": str(settings.storage_root),
            "backups_root": str(settings.backups_root),
            "media_storage_root": str(settings.media_storage_root),
            "logs_path": str(settings.logs_path),
            "system_backups": str(settings.storage_root / "system_backups"),
        },
    }
