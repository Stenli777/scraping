from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin.routes import router as admin_router
from app.api.editorial import router as editorial_router
from app.api.discovery import router as discovery_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.hermes import router as hermes_router
from app.api.media import router as media_router
from app.api.analytics import router as analytics_router
from app.api.automation import router as automation_router
from app.api.campaigns import router as campaigns_router
from app.api.system import router as system_router
from app.api.llm import router as llm_router
from app.api.prompts import router as prompts_router
from app.api.publish import router as publish_router
from app.api.mock_crmflow24 import router as mock_crmflow24_router
from app.api.quality import router as quality_router
from app.api.review import router as review_router
from app.api.rewrite import router as rewrite_router
from app.api.seo import router as seo_router
from app.api.tasks import router as tasks_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging

settings = get_settings()
setup_logging()

import logging as _logging
from app.core.config_validator import validate_config as _validate_config

_startup_log = _logging.getLogger("scrap.startup")
_cv = _validate_config()
for _w in _cv.warnings:
    _startup_log.warning("Config: %s", _w)
for _e in _cv.errors:
    _startup_log.error("Config: %s", _e)
if not _cv.ok:
    _startup_log.error("Config validation has errors — service continues (check /health/config)")

from app.core.workspace import get_workspace_warnings as _workspace_warnings

for _ww in _workspace_warnings():
    _startup_log.warning("Workspace: %s", _ww)

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(documents_router)
app.include_router(rewrite_router)
app.include_router(review_router)
app.include_router(seo_router)
app.include_router(publish_router)
app.include_router(mock_crmflow24_router)
app.include_router(prompts_router)
app.include_router(quality_router)
app.include_router(editorial_router)
app.include_router(hermes_router)
app.include_router(media_router)
app.include_router(analytics_router)
app.include_router(campaigns_router)
app.include_router(automation_router)
app.include_router(system_router)
app.include_router(discovery_router)
app.include_router(llm_router)
app.include_router(admin_router)

static_dir = Path(__file__).parent / "admin" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }
