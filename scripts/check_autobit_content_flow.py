#!/usr/bin/env python3
"""Read-only: Autobit-related documents/tasks pipeline status for pilot planning."""

from __future__ import annotations

import sys

sys.path.insert(0, "/opt/scrap")

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.parsed_document import ParsedDocument
from app.models.scraping_task import ScrapingTask
from app.models.source_directory import SourceDirectory

# Known Autobit intake from prior stages (crmflow24 project_id=1)
AUTOBIT_DOC_IDS = (10, 11, 13)
AUTOBIT_TASK_IDS = (14, 15, 16, 17)
PROJECT_ID = 1


def _doc_row(db, doc_id: int) -> dict | None:
    doc = db.get(ParsedDocument, doc_id)
    if not doc:
        return None
    task = db.get(ScrapingTask, doc.task_id)
    meta = doc.metadata_json or {}
    return {
        "document_id": doc.id,
        "task_id": doc.task_id,
        "title": (meta.get("title") or doc.source_url or "")[:80],
        "editorial_status": doc.editorial_status,
        "task_status": task.status if task else None,
        "rewritten_len": len(doc.rewritten_text or ""),
        "has_clean": bool(doc.clean_text),
        "source_url": doc.source_url[:100] if doc.source_url else "",
    }


def main() -> int:
    db = SessionLocal()
    try:
        src = db.scalar(select(SourceDirectory).where(SourceDirectory.name == "autobit24-blog"))
        print("=== AUTOBIT SOURCE ===")
        if src:
            print(f"id={src.id} name={src.name} project_id={src.project_id} base_url={src.base_url}")
        else:
            print("autobit24-blog source: NOT FOUND")

        print("\n=== AUTOBIT DOCUMENTS (known ids) ===")
        print(
            "document_id\ttitle\teditorial\ttask_status\trewrite_len\tmissing_steps\t"
            "should_add_to_pilot\treason"
        )
        for did in AUTOBIT_DOC_IDS:
            row = _doc_row(db, did)
            if not row:
                print(f"{did}\t—\tMISSING\t—\t—\t—\tfalse\tno document")
                continue
            missing: list[str] = []
            if not row["has_clean"]:
                missing.append("clean")
            if row["rewritten_len"] < 500:
                missing.append("rewrite")
            if row["editorial_status"] not in ("approved", "published", "ready_for_publish"):
                missing.append(f"editorial:{row['editorial_status']}")
            # heuristic next_action
            if "rewrite" in missing:
                next_action = "run_rewrite"
            elif "editorial" in "".join(missing):
                next_action = "review_quality_strategy"
            else:
                next_action = "rc_pilot_candidate"
            pilot = row["editorial_status"] in ("approved", "ready_for_publish") and row["rewritten_len"] >= 500
            reason = "ready" if pilot else f"blocked: {','.join(missing) or 'checks'}"
            print(
                f"{row['document_id']}\t{row['title'][:40]}\t{row['editorial_status']}\t"
                f"{row['task_status']}\t{row['rewritten_len']}\t{','.join(missing) or '—'}\t"
                f"{str(pilot).lower()}\t{reason} (next: {next_action})"
            )

        print("\n=== AUTOBIT TASKS (known ids) ===")
        for tid in AUTOBIT_TASK_IDS:
            t = db.get(ScrapingTask, tid)
            if not t:
                print(f"task {tid}: MISSING")
                continue
            print(f"task {tid}: status={t.status} project_id={t.project_id} url={str(t.source_url or '')[:80]}")
    finally:
        db.close()
    print("\nPASS autobit content flow check (read-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
