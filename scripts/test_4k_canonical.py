#!/usr/bin/env python3
"""Manual smoke tests for stage 4K."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.campaign_document_link import CampaignDocumentLink
from app.models.content_campaign import ContentCampaign
from app.models.llm_enrichment_job import EnrichmentType
from app.models.parsed_document import ParsedDocument
from app.models.scraping_task import ScrapingTask
from app.services.campaign_service import campaign_coverage
from app.services.document_similarity_service import (
    SIMILARITY_CAMPAIGN_OVERLAP,
    SIMILARITY_SAME_SOURCE,
    analyze_document_similarity,
    compare_document_pair,
    get_document_lineage,
    get_document_similarity_summary,
    record_rewrite_lineage,
)
from app.services.enrichment_service import queue_similarity_analysis_job


def main() -> None:
    out: list[str] = []
    with SessionLocal() as db:
        docs = list(
            db.scalars(
                select(ParsedDocument)
                .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
                .order_by(ParsedDocument.id.desc())
                .limit(10)
            ).all()
        )
        if len(docs) < 2:
            print("SKIP: need 2+ documents")
            return
        a, b = docs[0], docs[1]
        project_id = a.task.project_id if a.task else None

        orig_b_url = b.source_url
        b.source_url = a.source_url
        db.flush()
        c1 = compare_document_pair(db, a.id, b.id)
        out.append("OK same_source" if c1["similarity_type"] == SIMILARITY_SAME_SOURCE else f"FAIL same_source {c1}")
        b.source_url = orig_b_url

        ma = dict(a.metadata_json or {})
        mb = dict(b.metadata_json or {})
        ma["title"] = "Stage4K duplicate title probe"
        mb["title"] = "Stage4K duplicate title probe extended"
        a.metadata_json = ma
        b.metadata_json = mb
        db.flush()
        c2 = compare_document_pair(db, a.id, b.id)
        out.append(
            f"OK near/topic check type={c2['similarity_type']} score={c2['similarity_score']}"
            if c2["similarity_score"] >= 50
            else f"WARN low score {c2}"
        )

        camp = db.scalar(select(ContentCampaign).limit(1))
        if camp and project_id:
            for did in (a.id, b.id):
                if not db.scalar(
                    select(CampaignDocumentLink).where(
                        CampaignDocumentLink.campaign_id == camp.id,
                        CampaignDocumentLink.document_id == did,
                    )
                ):
                    db.add(CampaignDocumentLink(campaign_id=camp.id, document_id=did, link_role="test"))
            db.flush()
            c3 = compare_document_pair(db, a.id, b.id)
            out.append(f"OK campaign overlap type={c3['similarity_type']}")
            cov = campaign_coverage(db, camp.id)
            out.append(
                "OK coverage fields"
                if "duplicate_adjusted_coverage" in cov
                else "FAIL coverage fields"
            )

        record_rewrite_lineage(db, a.id)
        db.commit()
        lin = get_document_lineage(db, a.id)
        out.append("OK lineage" if lin.get("lineage_entries") else "FAIL lineage")

        job = queue_similarity_analysis_job(db, document_id=a.id, project_id=project_id)
        db.commit()
        out.append(
            f"OK async job #{job.id}"
            if job and job.enrichment_type == EnrichmentType.SIMILARITY_ANALYSIS
            else "WARN async job"
        )

        summ = get_document_similarity_summary(db, a.id)
        out.append(f"OK summary links={len(summ.get('links', []))}")

        analyze_document_similarity(db, a.id, persist=True, deep=False)
        db.commit()
        out.append("OK sync analyze")

    print("\n".join(out))


if __name__ == "__main__":
    main()
