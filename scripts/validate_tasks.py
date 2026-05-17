#!/usr/bin/env python3
"""Validate scraping tasks and document quality."""

from pathlib import Path

from app.db.session import SessionLocal
from app.models.document_version import DocumentVersion
from app.models.scraping_task import ScrapingTask
from app.models.task_log import TaskLog


def main() -> None:
    db = SessionLocal()
    tasks = db.query(ScrapingTask).order_by(ScrapingTask.id).all()
    for t in tasks:
        doc = t.document
        backup = list(Path("storage/backups").rglob(f"{t.id}/metadata.json"))
        logs = db.query(TaskLog).filter_by(task_id=t.id).count()
        versions = (
            db.query(DocumentVersion).filter_by(document_id=doc.id).count() if doc else 0
        )
        print(f"task={t.id} status={t.status} parser={t.parser_type}")
        if doc:
            print(
                f"  doc={doc.id} clean={len(doc.clean_text or '')} "
                f"rewrite={len(doc.rewritten_text or '')} "
                f"raw_html={bool(doc.raw_html)} versions={versions} logs={logs} "
                f"backup={bool(backup)}"
            )
            meta = doc.metadata_json or {}
            title = (meta.get("extracted_title") or meta.get("title") or "?")[:70]
            print(f"  title={title} words={meta.get('word_count')} warnings={meta.get('extraction_warnings')}")
        else:
            print(f"  error={t.error_message} logs={logs}")
    db.close()


if __name__ == "__main__":
    main()
