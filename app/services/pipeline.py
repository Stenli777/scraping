import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import LogLevel, TaskStatus
from app.models.document_version import DocumentVersion
from app.models.parsed_document import ParsedDocument
from app.models.scraping_task import ScrapingTask
from app.parsers.fetcher import fetch_url
from app.parsers.registry import get_parser_for_url, resolve_parser_type
from app.services.backup_service import BackupService
from app.services.hashing import content_hash
from app.services.pipeline_event_service import emit_pipeline_event, map_legacy_task_status_to_stage
from app.services.project_profile_service import resolve_task_project
from app.services.review_service import run_review_stage
from app.services.rewrite_service import run_rewrite_stage
from app.services.seo_service import run_seo_stage
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

        parsed = None
        doc_hash = None
        review_result = None
        rewrite_result = None
        seo_result = None

        try:
            project = resolve_task_project(self.db, task)
            if project and not task.project_id:
                task.project_id = project.id
                self.db.commit()

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
                    return
                raise ValueError(
                    f"Duplicate content detected (document_id={existing.id}, hash={doc_hash})"
                )

            self._set_status(task, TaskStatus.REVIEWING)
            review_result = run_review_stage(
                self.db, task, clean_text=parsed.clean_text, parsed_metadata=parsed.metadata
            )
            if review_result.success and not review_result.skipped:
                parsed.metadata["review"] = {
                    "take": review_result.take,
                    "score": review_result.score,
                    "reason": review_result.reason,
                    "content_type": review_result.content_type,
                    "recommended_angle": review_result.recommended_angle,
                    "llm_run_id": review_result.llm_run_id,
                    "review_result_id": review_result.review_result_id,
                }
            elif not review_result.success and not review_result.skipped:
                add_task_log(
                    self.db,
                    task.id,
                    "Review failed — continuing pipeline",
                    LogLevel.WARNING,
                    {"error": review_result.error_message},
                )
                parsed.metadata["review_error"] = review_result.error_message

            self._set_status(task, TaskStatus.REWRITING)
            rewrite_result = run_rewrite_stage(
                self.db, task, clean_text=parsed.clean_text, parsed_metadata=parsed.metadata
            )

            parsed.metadata["rewrite"] = {
                "provider": rewrite_result.provider,
                "model_alias": rewrite_result.model_alias,
                "upstream_model": rewrite_result.upstream_model,
                "fallback_used": rewrite_result.fallback_used,
                "success": rewrite_result.success,
            }
            if rewrite_result.llm_run_id:
                parsed.metadata["rewrite"]["llm_run_id"] = rewrite_result.llm_run_id

            rewritten = rewrite_result.rewritten_text if rewrite_result.success else ""

            if not rewrite_result.success:
                add_task_log(
                    self.db,
                    task.id,
                    "Rewrite failed — saving clean_text only",
                    LogLevel.WARNING,
                    {
                        "error": rewrite_result.error_message,
                        "warnings": rewrite_result.warnings,
                    },
                )
                task.error_message = rewrite_result.error_message

            self._set_status(task, TaskStatus.SAVING)
            document = self._upsert_document(task, parsed, doc_hash, rewritten)
            self._create_version(document)

            self._set_status(task, TaskStatus.SEO_ENRICHING)
            seo_content = rewritten or parsed.clean_text
            seo_result = run_seo_stage(
                self.db,
                task,
                content=seo_content,
                parsed_metadata=parsed.metadata,
                document_id=document.id,
            )
            if seo_result.success and not seo_result.skipped:
                parsed.metadata["seo"] = {
                    "seo_metadata_id": seo_result.seo_metadata_id,
                    "seo_title": seo_result.seo_title,
                    "slug": seo_result.slug,
                    "llm_run_id": seo_result.llm_run_id,
                }
                document.metadata_json = parsed.metadata
            elif not seo_result.success and not seo_result.skipped:
                add_task_log(
                    self.db,
                    task.id,
                    "SEO enrich failed — document saved without SEO",
                    LogLevel.WARNING,
                    {"error": seo_result.error_message},
                )
                parsed.metadata["seo_error"] = seo_result.error_message
                document.metadata_json = parsed.metadata

            backup_dir = self.backup.save_task_backup(
                task.id,
                raw_html=parsed.raw_html,
                raw_text=parsed.raw_text,
                clean_text=parsed.clean_text,
                rewritten_text=rewritten or None,
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

            stage_failed = (
                (rewrite_result and not rewrite_result.success)
                or (review_result and not review_result.success and not review_result.skipped)
                or (seo_result and not seo_result.success and not seo_result.skipped)
            )

            if rewrite_result.success and not stage_failed:
                self._set_status(task, TaskStatus.DONE)
            elif rewrite_result.success and stage_failed:
                task.status = TaskStatus.FAILED_RETRYABLE.value
                emit_pipeline_event(
                    self.db,
                    task.id,
                    map_legacy_task_status_to_stage(TaskStatus.FAILED_RETRYABLE.value),
                    status="entered",
                    payload={"reason": "optional_stage_failed"},
                )
                self.db.commit()
                add_task_log(self.db, task.id, "Task failed_retryable (optional stage)", LogLevel.WARNING)
            else:
                task.status = TaskStatus.FAILED_RETRYABLE.value
                emit_pipeline_event(
                    self.db,
                    task.id,
                    map_legacy_task_status_to_stage(TaskStatus.FAILED_RETRYABLE.value),
                    status="entered",
                    payload={"reason": "rewrite_failed"},
                )
                self.db.commit()
                add_task_log(self.db, task.id, "Task failed_retryable (rewrite)", LogLevel.WARNING)

            task.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info("Task %s completed status=%s", task.id, task.status)
        except Exception as exc:
            logger.exception("Task %s failed", task_id)
            self.db.rollback()
            task = self.db.get(ScrapingTask, task_id)
            if task:
                if parsed and doc_hash:
                    try:
                        document = self._upsert_document(task, parsed, doc_hash, "")
                        parsed.metadata["partial_save"] = True
                        document.metadata_json = parsed.metadata
                        self.db.commit()
                    except Exception:
                        self.db.rollback()
                task = self.db.get(ScrapingTask, task_id)
                if task:
                    task.status = TaskStatus.ERROR.value
                    task.error_message = str(exc)
                    task.finished_at = datetime.now(timezone.utc)
                    add_task_log(self.db, task.id, str(exc), LogLevel.ERROR)
                    emit_pipeline_event(
                        self.db,
                        task.id,
                        map_legacy_task_status_to_stage(TaskStatus.ERROR.value),
                        status="failed",
                        payload={"error": str(exc)},
                    )
                    self.db.commit()

    def _set_status(self, task: ScrapingTask, status: TaskStatus) -> None:
        task.status = status.value
        emit_pipeline_event(
            self.db,
            task.id,
            map_legacy_task_status_to_stage(status.value),
            status="entered",
            payload={"legacy_status": status.value},
        )
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
            document = ParsedDocument(
                task_id=task.id, source_url=task.source_url, content_hash=doc_hash
            )
            self.db.add(document)

        document.source_url = task.source_url
        document.content_hash = doc_hash
        document.raw_html = parsed.raw_html
        document.raw_text = parsed.raw_text
        document.clean_text = parsed.clean_text
        document.rewritten_text = rewritten or None
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
