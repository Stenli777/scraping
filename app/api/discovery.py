from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.discovered_url import DiscoveredUrl
from app.models.source_directory import SourceDirectory
from app.services.discovery_service import (
    enqueue_discovered_url,
    ignore_discovered_url,
    run_discovery,
)

router = APIRouter(tags=["discovery"])


class DiscoverRequest(BaseModel):
    max_urls: int | None = None
    dry_run: bool = False


@router.get("/api/source-directories")
def list_source_directories(db: Session = Depends(get_db)):
    rows = db.query(SourceDirectory).order_by(SourceDirectory.id.asc()).all()
    return {
        "directories": [
            {
                "id": d.id,
                "project_id": d.project_id,
                "name": d.name,
                "base_url": d.base_url,
                "discovery_mode": d.discovery_mode,
                "enabled": d.enabled,
                "max_urls_per_run": d.max_urls_per_run,
                "max_depth": d.max_depth,
                "crawl_delay_seconds": d.crawl_delay_seconds,
                "allow_patterns_json": d.allow_patterns_json,
                "block_patterns_json": d.block_patterns_json,
                "last_discovered_at": d.last_discovered_at.isoformat()
                if d.last_discovered_at
                else None,
            }
            for d in rows
        ]
    }


@router.post("/api/source-directories/{directory_id}/discover")
def api_run_discovery(
    directory_id: int,
    body: DiscoverRequest | None = None,
    db: Session = Depends(get_db),
):
    payload = body or DiscoverRequest()
    try:
        result = run_discovery(
            db,
            directory_id,
            max_urls=payload.max_urls,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": result.success,
        "source_directory_id": result.source_directory_id,
        "discovered_new": result.discovered_new,
        "duplicates": result.duplicates,
        "blocked": result.blocked,
        "failed": result.failed,
        "total_candidates": result.total_candidates,
        "dry_run": result.dry_run,
        "errors": result.errors[:20],
    }


@router.get("/api/discovered-urls")
def list_discovered_urls(
    project_id: int | None = Query(None),
    source_directory_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(DiscoveredUrl).order_by(DiscoveredUrl.id.desc())
    if project_id is not None:
        q = q.filter(DiscoveredUrl.project_id == project_id)
    if source_directory_id is not None:
        q = q.filter(DiscoveredUrl.source_directory_id == source_directory_id)
    if status is not None:
        q = q.filter(DiscoveredUrl.status == status)
    rows = q.limit(limit).all()
    return {
        "urls": [
            {
                "id": r.id,
                "url": r.url,
                "normalized_url": r.normalized_url,
                "project_id": r.project_id,
                "source_directory_id": r.source_directory_id,
                "status": r.status,
                "discovery_source": r.discovery_source,
                "existing_task_id": r.existing_task_id,
                "existing_document_id": r.existing_document_id,
                "discovered_at": r.discovered_at.isoformat() if r.discovered_at else None,
            }
            for r in rows
        ]
    }


@router.post("/api/discovered-urls/{discovered_url_id}/enqueue")
def api_enqueue_discovered_url(discovered_url_id: int, db: Session = Depends(get_db)):
    try:
        record = enqueue_discovered_url(db, discovered_url_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "id": record.id,
        "status": record.status,
        "existing_task_id": record.existing_task_id,
    }


@router.post("/api/discovered-urls/{discovered_url_id}/ignore")
def api_ignore_discovered_url(discovered_url_id: int, db: Session = Depends(get_db)):
    try:
        record = ignore_discovered_url(db, discovered_url_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "id": record.id, "status": record.status}
