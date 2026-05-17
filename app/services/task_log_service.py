from sqlalchemy.orm import Session

from app.core.enums import LogLevel
from app.models.task_log import TaskLog


def add_task_log(
    db: Session,
    task_id: int,
    message: str,
    level: LogLevel = LogLevel.INFO,
    payload: dict | None = None,
) -> TaskLog:
    entry = TaskLog(
        task_id=task_id,
        level=level.value,
        message=message,
        payload_json=payload,
    )
    db.add(entry)
    db.flush()
    return entry
