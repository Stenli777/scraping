#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.llm_run import LLMRun
from app.models.pipeline_event import PipelineEvent

db = SessionLocal()
r = db.query(LLMRun).order_by(LLMRun.id.desc()).first()
e = db.query(PipelineEvent).order_by(PipelineEvent.id.desc()).first()
if r:
    print(f"llm_run id={r.id} success={r.success} alias={r.model_alias} upstream={r.upstream_model}")
    print(f"  error={(r.error_message or '')[:120]}")
if e:
    print(f"pipeline_event id={e.id} task={e.task_id} stage={e.stage} status={e.status}")
db.close()
