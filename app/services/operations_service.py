"""Operational metrics and failed-item aggregation for admin."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import PublishRunStatus, TaskStatus
from app.models.discovered_url import DiscoveredUrl
from app.models.llm_run import LLMRun
from app.models.pipeline_event import PipelineEvent
from app.models.project import Project
from app.models.publish_run import PublishRun
from app.models.scraping_task import ScrapingTask
from app.models.source_directory import SourceDirectory

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

STALE_RUNNING_HOURS = 2


def get_dashboard_stats(db: Session) -> dict:
    task_rows = db.execute(
        select(ScrapingTask.status, func.count())
        .group_by(ScrapingTask.status)
    ).all()
    task_counts = {row[0]: row[1] for row in task_rows}

    discovered_rows = db.execute(
        select(DiscoveredUrl.status, func.count())
        .group_by(DiscoveredUrl.status)
    ).all()
    discovered_counts = {row[0]: row[1] for row in discovered_rows}

    failed_tasks = list(
        db.scalars(
            select(ScrapingTask)
            .options(joinedload(ScrapingTask.document))
            .where(
                ScrapingTask.status.in_(
                    [TaskStatus.ERROR.value, TaskStatus.FAILED_RETRYABLE.value]
                )
            )
            .order_by(ScrapingTask.id.desc())
            .limit(10)
        ).unique().all()
    )

    failed_llm = list(
        db.scalars(
            select(LLMRun)
            .where(LLMRun.success.is_(False))
            .order_by(LLMRun.id.desc())
            .limit(10)
        ).all()
    )

    failed_publish = list(
        db.scalars(
            select(PublishRun)
            .where(
                PublishRun.status.in_(
                    [
                        PublishRunStatus.FAILED_RETRYABLE.value,
                        PublishRunStatus.FAILED_TERMINAL.value,
                    ]
                )
            )
            .order_by(PublishRun.id.desc())
            .limit(10)
        ).all()
    )

    events = list(
        db.scalars(
            select(PipelineEvent)
            .order_by(PipelineEvent.id.desc())
            .limit(10)
        ).all()
    )

    projects_count = db.scalar(select(func.count()).select_from(Project)) or 0
    directories_count = db.scalar(select(func.count()).select_from(SourceDirectory)) or 0

    return {
        "task_counts": task_counts,
        "discovered_counts": discovered_counts,
        "failed_tasks": failed_tasks,
        "failed_llm": failed_llm,
        "failed_publish": failed_publish,
        "pipeline_events": events,
        "projects_count": projects_count,
        "source_directories_count": directories_count,
    }


def get_failed_items(db: Session, *, limit: int = 50) -> dict:
    retryable = list(
        db.scalars(
            select(ScrapingTask)
            .where(ScrapingTask.status == TaskStatus.FAILED_RETRYABLE.value)
            .order_by(ScrapingTask.id.desc())
            .limit(limit)
        ).all()
    )
    terminal = list(
        db.scalars(
            select(ScrapingTask)
            .where(ScrapingTask.status == TaskStatus.ERROR.value)
            .order_by(ScrapingTask.id.desc())
            .limit(limit)
        ).all()
    )
    failed_llm = list(
        db.scalars(
            select(LLMRun)
            .where(LLMRun.success.is_(False))
            .order_by(LLMRun.id.desc())
            .limit(limit)
        ).all()
    )
    failed_publish = list(
        db.scalars(
            select(PublishRun)
            .where(
                PublishRun.status.in_(
                    [
                        PublishRunStatus.FAILED_RETRYABLE.value,
                        PublishRunStatus.FAILED_TERMINAL.value,
                    ]
                )
            )
            .order_by(PublishRun.id.desc())
            .limit(limit)
        ).all()
    )
    return {
        "failed_retryable_tasks": retryable,
        "failed_terminal_tasks": terminal,
        "failed_llm_runs": failed_llm,
        "failed_publish_runs": failed_publish,
    }


def list_stale_running_tasks(db: Session) -> list[ScrapingTask]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_RUNNING_HOURS)
    return list(
        db.scalars(
            select(ScrapingTask)
            .where(
                ScrapingTask.status.in_(RUNNING_STATUSES),
                ScrapingTask.updated_at < cutoff,
            )
            .order_by(ScrapingTask.updated_at.asc())
            .limit(50)
        ).all()
    )
