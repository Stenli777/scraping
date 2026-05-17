#!/usr/bin/env python3
"""Read-only storage integrity checks."""
import sys
sys.path.insert(0, "/opt/scrap")

from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.media_asset import MediaAsset
from app.services.media_service import resolve_media_file_path


def main() -> int:
    settings = get_settings()
    issues: list[str] = []

    for label, path in (
        ("storage_root", settings.storage_root),
        ("backups_root", settings.backups_root),
        ("media_storage_root", settings.media_storage_root),
        ("system_backups", settings.storage_root / "system_backups"),
    ):
        if not path.exists():
            issues.append(f"missing directory: {label} {path}")

    with SessionLocal() as db:
        assets = db.scalars(
            select(MediaAsset).where(MediaAsset.storage_path.isnot(None))
        ).all()
        for asset in assets:
            fp = resolve_media_file_path(asset)
            if fp and not fp.is_file():
                issues.append(f"media_asset #{asset.id} missing file: {fp}")

    manifests = settings.storage_root / "system_backups" / "manifests"
    if manifests.is_dir():
        for m in manifests.glob("manifest-*.json"):
            if m.stat().st_size == 0:
                issues.append(f"empty manifest: {m}")

    if issues:
        print("STORAGE INTEGRITY: FAIL")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("STORAGE INTEGRITY: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
