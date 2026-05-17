"""Operational context for /admin/operations."""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_validator import validate_config_summary
from app.api.health import collect_readiness_checks
from app.scheduler.status import build_scheduler_status
from app.services.operations_service import get_dashboard_stats


def _latest_backup_manifest() -> dict | None:
    settings = get_settings()
    manifests_dir = settings.storage_root / "system_backups" / "manifests"
    if not manifests_dir.is_dir():
        return None
    files = sorted(manifests_dir.glob("manifest-*.json"), reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"error": "invalid manifest", "path": str(files[0])}


def build_operations_context(db: Session) -> dict:
    settings = get_settings()
    readiness = collect_readiness_checks()
    config = validate_config_summary()
    return {
        "stats": get_dashboard_stats(db),
        "readiness": readiness,
        "config": config,
        "latest_manifest": _latest_backup_manifest(),
        "smoke_hint": "PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/run_all.py",
        "backup_hint": "bash scripts/backup_postgres.sh && bash scripts/backup_storage.sh",
        "paths": config.get("paths", {}),
    }
