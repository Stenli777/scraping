import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import LogLevel, TaskStatus
from app.models.document_version import DocumentVersion
from app.models.export import Export
from app.models.parsed_document import ParsedDocument
from app.models.scraping_task import ScrapingTask
from app.models.source import Source
from app.parsers.fetcher import fetch_url
from app.parsers.registry import get_parser_for_url, resolve_parser_type
from app.rewriters.registry import get_rewriter
from app.services.backup_service import BackupService
from app.services.hashing import content_hash
from app.services.task_log_service import add_task_log

logger = logging.getLogger(__name__)


class PipelineService:
    def __init__(self, db: Session):
        self.db = db
        self.backup = BackupService()

    def run_task(self, task_id: int) -> None:
        task = self.db.get(ScrapingTask, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        try:
            task.started_at = datetime.now(timezone.utc)
            self._set_status(task, TaskStatus.FETCHING)
            add_task_log(self.db, task.id, "Fetching URL", LogLevel.INFO, {"url": task.source_url})
            html = fetch_url(task.source_url)

            self._set_status(task, TaskStatus.PARSING)
            resolved_parser = resolve_parser_type(task.source_url, task.parser_type)
            task.parser_type = resolved_parser
            parser = get_parser_for_url(task.source_url, resolved_parser)
            parsed = parser.parse(task.source_url, html)

            self._set_status(task, TaskStatus.CLEANING)
            doc_hash = content_hash(parsed.clean_text)

            existing = self.db.scalar(
                select(ParsedDocument).where(
                    ParsedDocument.source_url == task.source_url,
                    ParsedDocument.content_hash == doc_hash,
                )
            )
            if existing and existing.task_id != task.id:
                if existing.source_url == task.source_url:
                    add_task_log(
                        self.db,
                        task.id,
                        "Duplicate content — document already exists for this URL",
                        LogLevel.INFO,
                        {"document_id": existing.id, "content_hash": doc_hash},
                    )
                    task.status = TaskStatus.DONE.value
                    task.finished_at = datetime.now(timezone.utc)
                    self.db.commit()
                    logger.info(
                        "Task %s skipped duplicate, existing document %s", task.id, existing.id
                    )
                    return
                raise ValueError(
                    f"Duplicate content detected (document_id={existing.id}, hash={doc_hash})"
                )

            self._set_status(task, TaskStatus.REWRITING)
            rewriter = get_rewriter()
            rewritten = rewriter.rewrite(parsed.clean_text, parsed.metadata)

            self._set_status(task, TaskStatus.SAVING)
            document = self._upsert_document(task, parsed, doc_hash, rewritten)
            self._create_version(document)
            backup_dir = self.backup.save_task_backup(
                task.id,
                raw_html=parsed.raw_html,
                raw_text=parsed.raw_text,
                clean_text=parsed.clean_text,
                rewritten_text=rewritten,
                metadata=parsed.metadata,
                finished_at=datetime.now(timezone.utc),
            )
            add_task_log(
                self.db,
                task.id,
                "Backup saved",
                LogLevel.INFO,
                {"backup_dir": str(backup_dir)},
            )

            self._set_status(task, TaskStatus.DONE)
            task.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info("Task %s completed", task.id)
        except Exception as exc:
            logger.exception("Task %s failed", task_id)
            self.db.rollback()
            task = self.db.get(ScrapingTask, task_id)
            if task:
                task.status = TaskStatus.ERROR.value
                task.error_message = str(exc)
                task.finished_at = datetime.now(timezone.utc)
                add_task_log(self.db, task.id, str(exc), LogLevel.ERROR)
                self.db.commit()

    def _set_status(self, task: ScrapingTask, status: TaskStatus) -> None:
        task.status = status.value
        self.db.commit()
        add_task_log(self.db, task.id, f"Status -> {status.value}", LogLevel.DEBUG)

    def _upsert_document(
        self,
        task: ScrapingTask,
        parsed,
        doc_hash: str,
        rewritten: str,
    ) -> ParsedDocument:
        document = task.document
        if document:
            document.version += 1
        else:
            document = ParsedDocument(task_id=task.id, source_url=task.source_url, content_hash=doc_hash)
            self.db.add(document)

        document.source_url = task.source_url
        document.content_hash = doc_hash
        document.raw_html = parsed.raw_html
        document.raw_text = parsed.raw_text
        document.clean_text = parsed.clean_text
        document.rewritten_text = rewritten
        document.metadata_json = parsed.metadata
        self.db.flush()
        return document

    def _create_version(self, document: ParsedDocument) -> None:
        version = DocumentVersion(
            document_id=document.id,
            version=document.version,
            raw_text=document.raw_text,
            clean_text=document.clean_text,
            rewritten_text=document.rewritten_text,
            content_hash=document.content_hash,
        )
        self.db.add(version)
