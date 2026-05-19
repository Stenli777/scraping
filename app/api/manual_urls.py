"""Manual trusted URL intake API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.manual_url_intake_service import intake_manual_url, intake_manual_urls_bulk

router = APIRouter(tags=["manual-urls"])


class ManualUrlBody(BaseModel):
    project_id: int
    url: str
    source_directory_id: int | None = None
    notes: str | None = None
    score_quality: bool = True
    enqueue: bool = False


class ManualUrlBulkBody(BaseModel):
    project_id: int
    urls: list[str] = Field(min_length=1)
    source_directory_id: int | None = None
    score_quality: bool = True
    enqueue: bool = False


@router.post("/api/manual-urls")
def api_intake_manual_url(body: ManualUrlBody, db: Session = Depends(get_db)):
    try:
        result = intake_manual_url(
            db,
            project_id=body.project_id,
            url=body.url,
            source_directory_id=body.source_directory_id,
            notes=body.notes,
            score_quality=body.score_quality,
            enqueue=body.enqueue,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "url": result.url,
        "discovered_url_id": result.discovered_url_id,
        "status": result.status,
        "duplicate": result.duplicate,
        "article_likelihood": result.article_likelihood,
        "is_article": result.is_article,
        "error": result.error,
    }


@router.post("/api/manual-urls/bulk")
def api_intake_manual_urls_bulk(body: ManualUrlBulkBody, db: Session = Depends(get_db)):
    try:
        results = intake_manual_urls_bulk(
            db,
            project_id=body.project_id,
            urls=body.urls,
            source_directory_id=body.source_directory_id,
            score_quality=body.score_quality,
            enqueue=body.enqueue,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "count": len(results),
        "results": [
            {
                "url": r.url,
                "discovered_url_id": r.discovered_url_id,
                "status": r.status,
                "duplicate": r.duplicate,
                "article_likelihood": r.article_likelihood,
                "is_article": r.is_article,
                "error": r.error,
            }
            for r in results
        ],
    }
