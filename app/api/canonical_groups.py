from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.canonical_content_service import get_canonical_group_detail, list_canonical_groups

router = APIRouter(prefix="/api/canonical-groups", tags=["canonical-groups"])


@router.get("")
def api_list_canonical_groups(project_id: int | None = None, db: Session = Depends(get_db)):
    return {"groups": list_canonical_groups(db, project_id=project_id)}


@router.get("/{group_id}")
def api_canonical_group_detail(group_id: int, db: Session = Depends(get_db)):
    try:
        return get_canonical_group_detail(db, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
