from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin.routes import router as admin_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.llm import router as llm_router
from app.api.review import router as review_router
from app.api.rewrite import router as rewrite_router
from app.api.seo import router as seo_router
from app.api.tasks import router as tasks_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging

settings = get_settings()
setup_logging()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(documents_router)
app.include_router(rewrite_router)
app.include_router(review_router)
app.include_router(seo_router)
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
