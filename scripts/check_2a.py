#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.llm_run import LLMRun
from app.models.parsed_document import ParsedDocument

db = SessionLocal()
d = db.get(ParsedDocument, 6)
r = db.query(LLMRun).filter(LLMRun.task_id == 8).order_by(LLMRun.id.desc()).first()
if d:
    text = d.rewritten_text or ""
    print("doc6_has_mock_marker", "mock-rewriter" in text)
    print("doc6_preview", text[:80].replace("\n", " "))
if r:
    print("llm_run_task8", r.model_alias, r.upstream_model, r.success)
db.close()
