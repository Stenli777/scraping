"""Prompt template management API (read + version lifecycle)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.prompt_template import PromptTemplate
from app.services.prompt_service import (
    activate_prompt_version,
    create_prompt_version,
    get_active_prompt,
    list_prompt_versions,
)

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class CreatePromptVersionBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=32)
    content_md: str = Field(..., min_length=1)
    notes: str | None = None
    created_by: str = "api"
    activate: bool = False


@router.get("")
def api_list_prompts(db: Session = Depends(get_db)):
    templates = db.scalars(select(PromptTemplate).order_by(PromptTemplate.key.asc())).all()
    items = []
    for t in templates:
        active = get_active_prompt(db, t.key)
        items.append(
            {
                "id": t.id,
                "key": t.key,
                "name": t.name,
                "description": t.description,
                "task_kind": t.task_kind,
                "enabled": t.enabled,
                "active_version": active.version,
                "active_source": active.source,
            }
        )
    return {"prompts": items}


@router.get("/{key}")
def api_get_prompt(key: str, db: Session = Depends(get_db)):
    template = db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    active = get_active_prompt(db, key)
    versions = list_prompt_versions(db, key)
    return {
        "template": {
            "id": template.id,
            "key": template.key,
            "name": template.name,
            "description": template.description,
            "task_kind": template.task_kind,
            "enabled": template.enabled,
        },
        "active": {
            "version": active.version,
            "source": active.source,
            "prompt_version_id": active.prompt_version_id,
        },
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "is_active": v.is_active,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "created_by": v.created_by,
                "notes": v.notes,
                "content_preview": (v.content_md or "")[:500],
            }
            for v in versions
        ],
    }


@router.post("/{key}/versions")
def api_create_prompt_version(
    key: str, body: CreatePromptVersionBody, db: Session = Depends(get_db)
):
    try:
        record = create_prompt_version(
            db,
            key,
            version=body.version,
            content_md=body.content_md,
            created_by=body.created_by,
            notes=body.notes,
            activate=body.activate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": record.id,
        "version": record.version,
        "is_active": record.is_active,
    }


@router.post("/{key}/versions/{version_id}/activate")
def api_activate_prompt_version(key: str, version_id: int, db: Session = Depends(get_db)):
    try:
        record = activate_prompt_version(db, key, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": record.id, "version": record.version, "is_active": record.is_active}
