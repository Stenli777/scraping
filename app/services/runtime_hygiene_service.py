"""Runtime hygiene visibility — bounded cleanup reports, no destructive purge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.operational_incident import OperationalIncident
from app.models.operational_snapshot import OperationalSnapshot

ROOT = Path(os.environ.get("SCRAP_ROOT", "/opt/scrap"))


def _dir_size_mb(path: Path) -> float | None:
    if not path.exists():
        return None
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)


def _count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob(pattern)))


def _git_porcelain() -> list[str]:
    import subprocess

    r = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    return [ln for ln in (r.stdout or "").splitlines() if ln.strip()]


def _find_tmp_artifacts() -> list[str]:
    found: list[str] = []
    for pat in ("tmp_*.py", "tmp_*.sh", "deploy*.tar.gz"):
        found.extend(str(p.relative_to(ROOT)) for p in ROOT.glob(pat))
    for d in ("cursor_tmp", "tmp_artifacts"):
        p = ROOT / d
        if p.is_dir() and any(p.iterdir()):
            found.append(f"{d}/")
    return sorted(set(found))


def build_runtime_hygiene_report(db: Session) -> dict[str, Any]:
    porcelain = _git_porcelain()
    git_clean = not porcelain

    snap_total = db.scalar(select(func.count()).select_from(OperationalSnapshot)) or 0
    inc_total = db.scalar(select(func.count()).select_from(OperationalIncident)) or 0

    storage = ROOT / "storage"
    logs = storage / "logs"
    backups = storage / "backups"
    media = storage / "media"

    tmp_artifacts = _find_tmp_artifacts()
    mig_dirty = [ln for ln in porcelain if "alembic/versions" in ln]
    return {
        "read_only": True,
        "no_auto_destructive_cleanup": True,
        "git": {
            "clean": git_clean,
            "changed_files": len(porcelain),
            "uncommitted_migrations": mig_dirty,
            "hint": "Commit or stash on hermes before deploy; smoke git_clean expects clean tree.",
        },
        "tmp_artifacts": tmp_artifacts,
        "tmp_artifact_count": len(tmp_artifacts),
        "storage_mb": {
            "logs": _dir_size_mb(logs),
            "backups": _dir_size_mb(backups),
            "media": _dir_size_mb(media),
        },
        "operational_tables": {
            "snapshots": snap_total,
            "incidents": inc_total,
        },
        "retention_notes": {
            "snapshots": "30d / max 500 rows (operational_snapshot_service)",
            "incidents": "30d / max 300 rows (operational_incident_service)",
            "audit_tables": "publish_runs / revisions — no auto-delete",
        },
        "safe_cleanup_actions": [
            "cleanup_old_snapshots (on snapshot capture)",
            "cleanup_old_incidents (on diagnostics sync)",
            "scripts/ops_runtime_hygiene.py --apply-snapshots (optional)",
        ],
    }


def apply_safe_hygiene(db: Session, *, snapshots: bool = False, incidents: bool = False) -> dict[str, int]:
    """Optional bounded retention only — never touches audit tables."""
    out: dict[str, int] = {}
    if snapshots:
        from app.services.operational_snapshot_service import cleanup_old_snapshots

        out["snapshots_deleted"] = cleanup_old_snapshots(db)
    if incidents:
        from app.services.operational_incident_service import cleanup_old_incidents

        out["incidents_deleted"] = cleanup_old_incidents(db)
    return out
