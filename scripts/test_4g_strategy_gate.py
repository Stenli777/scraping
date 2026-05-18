#!/usr/bin/env python3
"""Manual smoke tests for stage 4G strategy gate."""
import json
import os
import sys

sys.path.insert(0, "/opt/scrap")
os.chdir("/opt/scrap")

from app.db.session import SessionLocal
from app.services.topic_extraction_service import extract_topics_for_document
from app.services.strategy_gate_service import get_strategy_readiness
from app.services.campaign_service import campaign_coverage
from app.services.strategy_gate_service import document_strategy_allowed


def run_doc(db, doc_id: int, use_llm=None):
    r = extract_topics_for_document(db, doc_id, persist_audit=True, use_llm_cleanup=use_llm)
    db.commit()
    ready = get_strategy_readiness(db, doc_id)
    allowed, reason, _ = document_strategy_allowed(db, doc_id)
    print(f"--- doc #{doc_id} ---")
    print(json.dumps({
        "strategy_allowed": r.get("strategy_allowed"),
        "strategy_block_reason": r.get("strategy_block_reason"),
        "relevance_score": r.get("relevance_score"),
        "project_fit": r.get("project_fit"),
        "llm_cleanup_status": r.get("llm_cleanup_status"),
        "warnings": r.get("warnings"),
        "readiness_ready": ready.get("ready"),
        "readiness_warnings": ready.get("warnings"),
    }, ensure_ascii=False, indent=2))
    return r


def main():
    db = SessionLocal()
    try:
        print("=== doc 7 smoke ===")
        run_doc(db, 7)
        # find CRM doc - high relevance
        from sqlalchemy import select, text
        row = db.execute(text(
            "SELECT id FROM parsed_documents WHERE rewritten_text IS NOT NULL AND id != 7 ORDER BY id LIMIT 5"
        )).fetchall()
        if row:
            print("=== sample doc", row[0][0], "===")
            run_doc(db, row[0][0])
        # campaign coverage
        from app.models.content_campaign import ContentCampaign
        camp = db.scalars(select(ContentCampaign).limit(1)).first()
        if camp:
            cov = campaign_coverage(db, camp.id)
            print(f"=== campaign {camp.id} coverage excluded={cov.get('excluded_strategy_count')} docs={cov.get('documents')} ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
