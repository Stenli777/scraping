import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings


class BackupService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def task_backup_dir(self, task_id: int, finished_at: datetime | None = None) -> Path:
        dt = finished_at or datetime.now(timezone.utc)
        path = (
            self.settings.backups_root
            / f"{dt.year:04d}"
            / f"{dt.month:02d}"
            / f"{dt.day:02d}"
            / str(task_id)
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_task_backup(
        self,
        task_id: int,
        *,
        raw_html: str | None,
        raw_text: str | None,
        clean_text: str | None,
        rewritten_text: str | None,
        metadata: dict,
        finished_at: datetime | None = None,
    ) -> Path:
        backup_dir = self.task_backup_dir(task_id, finished_at)

        if raw_html:
            (backup_dir / "raw.html").write_text(raw_html, encoding="utf-8")
        if raw_text:
            (backup_dir / "raw.txt").write_text(raw_text, encoding="utf-8")
        if clean_text:
            (backup_dir / "clean.md").write_text(clean_text, encoding="utf-8")
        if rewritten_text:
            (backup_dir / "rewritten.md").write_text(rewritten_text, encoding="utf-8")

        meta = {**metadata, "task_id": task_id, "backup_dir": str(backup_dir)}
        (backup_dir / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return backup_dir
