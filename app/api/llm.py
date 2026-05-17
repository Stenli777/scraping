from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm.routing import list_aliases
from app.llm.schemas import RewriteRequest
from app.services.llm_tasks import execute_rewrite

router = APIRouter(prefix="/api/llm", tags=["llm"])


class SmokeTestRequest(BaseModel):
    model_alias: str = Field(default="local/rewrite-main")
    content: str = Field(default="Напиши одно предложение: Scrap LLM smoke test OK.")


@router.get("/aliases")
def api_list_aliases():
    return {"aliases": list_aliases()}


@router.post("/smoke")
def api_llm_smoke(payload: SmokeTestRequest, db: Session = Depends(get_db)):
    request = RewriteRequest(
        content=payload.content,
        model_alias=payload.model_alias,
        metadata={"smoke_test": True},
    )
    response = execute_rewrite(db, request)
    return {
        "status": response.status,
        "rewritten_text": response.rewritten_text,
        "warnings": response.warnings,
        "metadata": response.metadata,
    }
