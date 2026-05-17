from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import ParserType, TaskStatus
from app.models.project import Project
from app.models.scraping_task import ScrapingTask
from app.models.source import Source
from app.parsers.registry import resolve_parser_type
from app.services.task_log_service import add_task_log


def get_or_create_source(db: Session, source_url: str, parser_type: str) -> Source:
    source = db.scalar(select(Source).where(Source.source_url == source_url))
    if source:
        source.parser_type = parser_type
        return source
    source = Source(
        source_url=source_url,
        domain=Source.domain_from_url(source_url),
        parser_type=parser_type,
    )
    db.add(source)
    db.flush()
    return source


def _default_project_id(db: Session) -> int | None:
    project = db.scalar(
        select(Project).where(Project.slug == "crmflow24", Project.enabled.is_(True))
    )
    return project.id if project else None


def create_task(
    db: Session,
    source_url: str,
    parser_type: str = ParserType.GENERIC_ARTICLE.value,
    *,
    project_id: int | None = None,
) -> ScrapingTask:
    parser_type = resolve_parser_type(source_url, parser_type)
    source = get_or_create_source(db, source_url, parser_type)
    task = ScrapingTask(
        source_id=source.id,
        project_id=project_id or _default_project_id(db),
        source_url=source_url,
        parser_type=parser_type,
        status=TaskStatus.QUEUED.value,
    )
    db.add(task)
    db.flush()
    add_task_log(db, task.id, "Task created", payload={"source_url": source_url})
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, limit: int = 100) -> list[ScrapingTask]:
    stmt = (
        select(ScrapingTask)
        .options(joinedload(ScrapingTask.document))
        .order_by(ScrapingTask.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).unique().all())


def get_task(db: Session, task_id: int) -> ScrapingTask | None:
    return db.scalar(
        select(ScrapingTask)
        .options(joinedload(ScrapingTask.document), joinedload(ScrapingTask.logs))
        .where(ScrapingTask.id == task_id)
    )


STALE_RUNNING_HOURS = 2
RUNNING_STATUSES = frozenset(
    {
        TaskStatus.FETCHING.value,
        TaskStatus.PARSING.value,
        TaskStatus.CLEANING.value,
        TaskStatus.REVIEWING.value,
        TaskStatus.REWRITING.value,
        TaskStatus.SEO_ENRICHING.value,
        TaskStatus.SAVING.value,
    }
)


def mark_task_skipped(db: Session, task_id: int) -> ScrapingTask:
    """Mark failed_retryable task as skipped (terminal error, non-destructive)."""
    task = db.get(ScrapingTask, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    if task.status != TaskStatus.FAILED_RETRYABLE.value:
        raise ValueError("Only failed_retryable tasks can be marked skipped")
    task.status = TaskStatus.ERROR.value
    task.error_message = (task.error_message or "") + " [skipped_by_operator]"
    task.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def reset_stale_running_task(db: Session, task_id: int) -> ScrapingTask:
    """Reset long-running task to failed_retryable if stuck."""
    task = db.get(ScrapingTask, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    if task.status not in RUNNING_STATUSES:
        raise ValueError("Task is not in a running pipeline status")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_RUNNING_HOURS)
    updated = task.updated_at
    if updated and updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    if updated and updated > cutoff:
        raise ValueError("Task was updated recently; not considered stale")
    task.status = TaskStatus.FAILED_RETRYABLE.value
    task.error_message = (task.error_message or "") + " [reset_stale_running]"
    db.commit()
    db.refresh(task)
    return task