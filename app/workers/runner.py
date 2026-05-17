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

logger = logging.getLogger(__name__)


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
            if count:
                logger.info("Processed %s task(s)", count)
        except Exception:
            logger.exception("Worker batch failed")
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
