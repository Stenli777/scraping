from sqlalchemy.orm import Session

from app.scheduler.locks import heartbeat_age_seconds, touch_heartbeat


def update_heartbeat(db: Session) -> None:
    touch_heartbeat(db)


def get_heartbeat_status(db: Session) -> dict:
    age = heartbeat_age_seconds(db)
    if age is None:
        return {"status": "unknown", "last_heartbeat_seconds": None}
    if age > 180:
        return {"status": "stale", "last_heartbeat_seconds": int(age)}
    return {"status": "ok", "last_heartbeat_seconds": int(age)}
