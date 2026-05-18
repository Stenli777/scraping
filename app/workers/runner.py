"""DB-polling worker — processes queued scraping tasks."""

import logging
import time

from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import TaskStatus
from app.core.logging_config import setup_logging
from app.db.session import SessionLocal
from app.models.scraping_task import ScrapingTask
from app.services.pipeline import PipelineService
from app.core.config import get_settings as _get_settings

logger = logging.getLogger(__name__)


# Enrichment runs AFTER scraping batch — scraping queue must not starve.
def process_enrichment_batch() -> int:
    settings = _get_settings()
    if not settings.enable_async_llm_enrichment:
        return 0
    from app.services.enrichment_service import tick_enrichment_jobs
    with SessionLocal() as db:
        result = tick_enrichment_jobs(db, limit=get_settings().worker_enrichment_per_poll)
        if result.get("processed"):
            db.commit()
            return int(result["processed"])
        db.commit()
    return 0


def process_batch() -> int:
    settings = get_settings()
    processed = 0
    with SessionLocal() as db:
        tasks = db.scalars(
            select(ScrapingTask)
            .where(ScrapingTask.status == TaskStatus.QUEUED.value)
            .order_by(ScrapingTask.id.asc())
            .limit(settings.worker_batch_size)
        ).all()
        for task in tasks:
            PipelineService(db).run_task(task.id)
            processed += 1
    return processed


def main() -> None:
    setup_logging()
    settings = get_settings()
    logger.info("Scrap worker started (poll=%ss)", settings.worker_poll_interval_seconds)
    while True:
        try:
            count = process_batch()
            enrich = process_enrichment_batch()
            if count:
                logger.info("Processed %s task(s)", count)
            if enrich:
                logger.info("Processed %s enrichment job(s)", enrich)
        except Exception:
            logger.exception("Worker batch failed")
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
