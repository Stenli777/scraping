#!/usr/bin/env python3
"""Smoke tests for stage 4H async enrichment."""
import json
import os
import sys
import time

sys.path.insert(0, "/opt/scrap")
os.chdir("/opt/scrap")

from app.db.session import SessionLocal
from app.services.topic_extraction_service import extract_topics_for_document
from app.services.enrichment_service import tick_enrichment_jobs, cancel_enrichment_job, retry_enrichment_job
from app.models.llm_enrichment_job import EnrichmentJobStatus


def main():
    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        r = extract_topics_for_document(db, 7, persist_audit=True, use_llm_cleanup=True, async_llm=True)
        db.commit()
        elapsed = time.perf_counter() - t0
        print("extract-topics elapsed_s=", round(elapsed, 3))
        print(json.dumps({
            "deterministic_complete": r.get("deterministic_complete"),
            "llm_cleanup_queued": r.get("llm_cleanup_queued"),
            "enrichment_job_id": r.get("enrichment_job_id"),
            "strategy_allowed": r.get("topics", {}).get("strategy_allowed") if isinstance(r.get("topics"), dict) else r.get("strategy_allowed"),
        }, indent=2))
        assert elapsed < 3.0, "extract-topics should be fast"
        job_id = r.get("enrichment_job_id")
        if job_id:
            tick_enrichment_jobs(db, limit=1)
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
