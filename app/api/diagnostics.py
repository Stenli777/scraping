"""Operational diagnostics API (safe, no secrets)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.runtime_diagnostics_service import build_runtime_diagnostics

router = APIRouter(tags=["diagnostics"])

_LOCALHOST_CLIENTS = frozenset({"127.0.0.1", "::1"})


def _require_local_ops_client(request: Request) -> None:
    """Ops diagnostics: localhost-only (matches uvicorn --host 127.0.0.1 deployment)."""
    host = request.client.host if request.client else ""
    if host not in _LOCALHOST_CLIENTS:
        raise HTTPException(
            status_code=403,
            detail="Ops diagnostics available on localhost only",
        )


@router.get("/api/ops/diagnostics")
def api_ops_diagnostics(request: Request, db: Session = Depends(get_db)):
    _require_local_ops_client(request)
    payload = build_runtime_diagnostics(db)
    db.commit()
    return payload
