import logging
import subprocess

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health/ready")
def health_ready():
    settings = get_settings()
    checks: dict[str, str] = {}
    ok = True

    # Database
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        ok = False

    # Worker (process-level: service expected running; lightweight signal)
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

    # CLIProxyAPI
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

    return {
        "status": "ready" if ok else "degraded",
        "checks": checks,
        "hermes_checked": False,
    }
