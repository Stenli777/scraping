from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exporters.json_markdown import document_to_json, document_to_markdown
from app.models.parsed_document import ParsedDocument
from app.schemas.documents import DocumentRead
from app.services.publish_readiness_service import get_publish_readiness

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentRead)
def api_get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/publish-readiness")
def api_publish_readiness(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return get_publish_readiness(db, document_id)


@router.get("/{document_id}/export/json")
def api_export_json(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(
        content=document_to_json(document),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="document_{document_id}.json"'},
    )


@router.get("/{document_id}/export/markdown")
def api_export_markdown(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return PlainTextResponse(
        content=document_to_markdown(document),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="document_{document_id}.md"'},
    )

from pydantic import BaseModel

from app.services.campaign_service import (
    assign_document_to_campaign,
    detect_duplicate_topics,
    document_strategy_context,
)
from app.services.clustering_service import assign_document_to_cluster, extract_topics_for_document


class AssignClusterRequest(BaseModel):
    cluster_id: int
    is_primary: bool = True


class AssignCampaignRequest(BaseModel):
    campaign_id: int
    link_role: str = "planned"


@router.post("/{document_id}/extract-topics")
def api_extract_topics(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = extract_topics_for_document(db, document_id, persist_audit=True)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/{document_id}/assign-cluster")
def api_assign_cluster(
    document_id: int,
    body: AssignClusterRequest,
    db: Session = Depends(get_db),
):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    link = assign_document_to_cluster(
        db,
        document_id=document_id,
        cluster_id=body.cluster_id,
        is_primary=body.is_primary,
    )
    db.commit()
    return {"document_id": document_id, "cluster_id": body.cluster_id, "link_id": link.id}


@router.post("/{document_id}/assign-campaign")
def api_assign_campaign(
    document_id: int,
    body: AssignCampaignRequest,
    db: Session = Depends(get_db),
):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    link = assign_document_to_campaign(
        db,
        document_id=document_id,
        campaign_id=body.campaign_id,
        link_role=body.link_role,
    )
    db.commit()
    return {"document_id": document_id, "campaign_id": body.campaign_id, "link_id": link.id}


@router.get("/{document_id}/strategy")
def api_document_strategy(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_strategy_context(db, document_id)


@router.get("/{document_id}/duplicate-warnings")
def api_duplicate_warnings(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"warnings": detect_duplicate_topics(db, document_id=document_id)}
