"""Project agent prompts API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.services.agent_registry import get_agent_meta
from app.services.prompt_override_service import (
    create_project_override_version,
    disable_project_override,
    get_effective_prompt_details,
    smoke_render_prompt,
)

router = APIRouter(prefix="/api/projects", tags=["project-agents"])


class OverrideBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=48)
    system: str = ""
    user: str = Field(..., min_length=1)
    notes: str | None = None
    activate: bool = True


@router.get("/{project_id}/agents/{key}/effective-prompt")
def api_effective_prompt(project_id: int, key: str, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return get_effective_prompt_details(db, key, project_id=project_id)


@router.post("/{project_id}/agents/{key}/smoke")
def api_agent_smoke(project_id: int, key: str, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    get_agent_meta(key)
    return smoke_render_prompt(db, project_id, key)


@router.post("/{project_id}/agents/{key}/override")
def api_create_override(
    project_id: int, key: str, body: OverrideBody, db: Session = Depends(get_db)
):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        row = create_project_override_version(
            db,
            project_id,
            key,
            version=body.version,
            system=body.system,
            user=body.user,
            notes=body.notes,
            activate=body.activate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"override_id": row.id, "enabled": row.enabled}


@router.post("/{project_id}/agents/{key}/override/disable")
def api_disable_override(project_id: int, key: str, db: Session = Depends(get_db)):
    disable_project_override(db, project_id, key)
    return {"ok": True}
