from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import ParserType, TaskStatus
from app.models.scraping_task import ScrapingTask
from app.models.source import Source
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


def create_task(db: Session, source_url: str, parser_type: str = ParserType.GENERIC_ARTICLE.value) -> ScrapingTask:
    source = get_or_create_source(db, source_url, parser_type)
    task = ScrapingTask(
        source_id=source.id,
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
