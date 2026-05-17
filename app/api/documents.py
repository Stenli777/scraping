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
