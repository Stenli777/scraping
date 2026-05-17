from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.db.session import get_db
from app.schemas.tasks import TaskCreate, TaskRead
from app.services.task_service import create_task, get_task, list_tasks

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_to_read(task) -> TaskRead:
    return TaskRead(
        id=task.id,
        source_id=task.source_id,
        source_url=task.source_url,
        status=task.status,
        parser_type=task.parser_type,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        document_id=task.document.id if task.document else None,
    )


@router.post("", response_model=TaskRead, status_code=201)
def api_create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = create_task(db, str(payload.source_url), payload.parser_type)
    return _task_to_read(task)


@router.get("", response_model=list[TaskRead])
def api_list_tasks(db: Session = Depends(get_db)):
    return [_task_to_read(t) for t in list_tasks(db)]


@router.get("/{task_id}", response_model=TaskRead)
def api_get_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_read(task)


@router.post("/{task_id}/run", response_model=TaskRead)
def api_run_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in {TaskStatus.QUEUED.value, TaskStatus.ERROR.value}:
        raise HTTPException(status_code=400, detail=f"Task cannot be run in status {task.status}")
    task.status = TaskStatus.QUEUED.value
    task.error_message = None
    db.commit()
    db.refresh(task)
    return _task_to_read(task)
