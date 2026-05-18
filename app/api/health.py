import logging
import subprocess

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.config_validator import validate_config
from app.core.feature_flags import is_hermes_enabled, is_scheduler_enabled
from app.db.session import SessionLocal
from app.hermes.health import check_hermes_health

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


def collect_readiness_checks() -> dict:
    """Build readiness checks dict (shared with admin operations)."""
    settings = get_settings()
    checks: dict[str, str] = {}
    ok = True

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        ok = False

    try:
        proc = subprocess.run(
            ["systemctl", "is-active", "scrap-worker"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        worker_state = proc.stdout.strip()
        if worker_state == "active":
            checks["worker"] = "ok"
        else:
            checks["worker"] = worker_state or "inactive"
            ok = False
    except Exception as exc:
        checks["worker"] = f"error: {type(exc).__name__}"
        ok = False

    if settings.cliproxyapi_base_url:
        try:
            url = f"{settings.cliproxyapi_base_url.rstrip('/')}/v1/models"
            headers = {}
            if settings.cliproxyapi_api_key:
                headers["Authorization"] = f"Bearer {settings.cliproxyapi_api_key}"
            with httpx.Client(timeout=5) as client:
                resp = client.get(url, headers=headers)
            if resp.status_code < 500:
                checks["cliproxyapi"] = "ok"
            else:
                checks["cliproxyapi"] = f"http_{resp.status_code}"
                ok = False
        except Exception as exc:
            checks["cliproxyapi"] = f"error: {type(exc).__name__}"
            ok = False
    else:
        checks["cliproxyapi"] = "not_configured"

    # Local storage
    try:
        settings.storage_root.mkdir(parents=True, exist_ok=True)
        test_file = settings.storage_root / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        checks["storage"] = "ok"
    except Exception as exc:
        checks["storage"] = f"error: {exc}"
        ok = False

    try:
        settings.media_storage_root.mkdir(parents=True, exist_ok=True)
        if not settings.media_storage_root.is_dir():
            checks["media_storage"] = "not_a_directory"
            ok = False
        else:
            checks["media_storage"] = "ok"
    except Exception as exc:
        checks["media_storage"] = f"error: {exc}"
        ok = False

    validation = validate_config(check_db=False)
    if validation.errors:
        checks["config"] = f"errors:{len(validation.errors)}"
        ok = False
    elif validation.warnings:
        checks["config"] = "warnings"
    else:
        checks["config"] = "ok"

    hermes_checked = False
    if is_hermes_enabled():
        hermes_checked = True
        h = check_hermes_health()
        if h.available:
            checks["hermes"] = "ok"
        else:
            checks["hermes"] = h.detail or h.status or "unavailable"
            ok = False
    else:
        checks["hermes"] = "disabled"

    scheduler_info: dict | None = None
    if is_scheduler_enabled():
        from app.scheduler.heartbeat import get_heartbeat_status

        try:
            with SessionLocal() as db:
                scheduler_info = get_heartbeat_status(db)
            if scheduler_info.get("status") == "stale":
                checks["scheduler"] = f"stale:{scheduler_info.get('last_heartbeat_seconds')}s"
                ok = False
            elif scheduler_info.get("status") == "unknown":
                checks["scheduler"] = "no_heartbeat"
                ok = False
            else:
                checks["scheduler"] = "ok"
        except Exception as exc:
            checks["scheduler"] = f"error: {exc}"
            ok = False

    result = {
        "status": "ready" if ok else "degraded",
        "checks": checks,
        "hermes_checked": hermes_checked,
        "ok": ok,
    }
    if scheduler_info is not None:
        result["scheduler"] = scheduler_info

    try:
        from app.services.enrichment_metrics_service import get_enrichment_health
        with SessionLocal() as db:
            enrichment_info = get_enrichment_health(db)
        result["enrichment"] = enrichment_info
        if enrichment_info.get("status") == "degraded":
            ok = False
    except Exception as exc:
        result["enrichment"] = {"status": "error", "detail": str(exc)[:200]}

    try:
        from app.services.source_quality_metrics_service import get_source_quality_health
        with SessionLocal() as db:
            result["source_quality"] = get_source_quality_health(db)
    except Exception as exc:
        result["source_quality"] = {"status": "error", "detail": str(exc)[:200]}
    try:
        from app.services.similarity_metrics_service import get_similarity_health

        with SessionLocal() as sim_db:
            result["similarity"] = get_similarity_health(sim_db)
    except Exception as exc:
        result["similarity"] = {"status": "error", "detail": str(exc)[:200]}

    return result


@router.get("/health/ready")
def health_ready():
    data = collect_readiness_checks()
    out = {
        "status": data["status"],
        "checks": data["checks"],
        "hermes_checked": data["hermes_checked"],
    }
    if "scheduler" in data:
        out["scheduler"] = data["scheduler"]
    if "enrichment" in data:
        out["enrichment"] = data["enrichment"]
    if "source_quality" in data:
        out["source_quality"] = data["source_quality"]
    if "similarity" in data:
        out["similarity"] = data["similarity"]
    return out


@router.get("/health/config")
def health_config():
    validation = validate_config()
    settings = get_settings()
    return {
        "ok": validation.ok,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "app_env": settings.app_env,
        "app_debug": settings.app_debug,
    }
