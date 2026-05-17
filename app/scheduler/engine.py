"""Scheduler main loop."""

import logging
import time

from app.core.config import get_settings
from app.core.feature_flags import is_scheduler_enabled
from app.core.logging_config import setup_logging
from app.db.session import SessionLocal
from app.scheduler.locks import acquire_lock, release_lock
from app.scheduler.heartbeat import update_heartbeat
from app.scheduler.services import tick_automation

logger = logging.getLogger(__name__)


class SchedulerEngine:
    def run_forever(self) -> None:
        settings = get_settings()
        logger.info(
            "Scheduler started (interval=%ss, automation=%s)",
            settings.scheduler_interval_seconds,
            is_scheduler_enabled(),
        )
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Scheduler tick failed")
            time.sleep(settings.scheduler_interval_seconds)

    def run_once(self) -> None:
        if not is_scheduler_enabled():
            return
        with SessionLocal() as db:
            if not acquire_lock(db):
                logger.debug("Scheduler lock held by another process")
                return
            try:
                update_heartbeat(db)
                result = tick_automation(db)
                if result.get("started"):
                    logger.info("Automation tick: %s", result)
            finally:
                release_lock(db)


def main() -> None:
    setup_logging()
    SchedulerEngine().run_forever()
