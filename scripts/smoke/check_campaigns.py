"""Campaign planning smoke checks."""

import json
import os
import sys
import urllib.error
import urllib.request

from scripts.smoke._common import BASE, check, get_json

ROOT = os.environ.get("SCRAP_ROOT", "/opt/scrap")


def post_json(path: str, data: dict) -> tuple[bool, dict | None, str]:
    try:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, json.loads(resp.read().decode()), ""
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = {}
        return False, body, f"HTTP {exc.code}"
    except Exception as exc:
        return False, None, str(exc)


def main() -> int:
    failures = 0
    suffix = str(int(__import__("time").time()))

    ok, clusters, err = get_json("/api/clusters?project_id=1")
    failures += check("clusters_list", ok, err)

    ok, created, err = post_json("/api/clusters", {
        "project_id": 1,
        "name": f"Smoke cluster {suffix}",
        "cluster_type": "integration",
        "primary_keyword": "bitrix24 telephony",
        "secondary_keywords": ["WhatsApp integration", "Telegram funnel automation"],
        "search_intent": "commercial",
    })
    failures += check("cluster_create", ok, err)
    cluster_id = (created or {}).get("id") if created else None

    ok, camps, err = get_json("/api/campaigns?project_id=1")
    failures += check("campaigns_list", ok, err)

    ok, camp, err = post_json("/api/campaigns", {
        "project_id": 1,
        "name": f"Smoke campaign {suffix}",
        "campaign_status": "draft",
        "target_keywords": ["bitrix24", "crm automation"],
    })
    failures += check("campaign_create", ok, err)
    campaign_id = (camp or {}).get("id") if camp else None

    doc_id = int(os.environ.get("SMOKE_DOC_ID", "7"))
    ok, topics, err = post_json(f"/api/documents/{doc_id}/extract-topics", {})
    failures += check("topic_extraction", ok, err or str((topics or {}).get("primary_topic", ""))[:40])

    if cluster_id:
        ok, assign, err = post_json(f"/api/documents/{doc_id}/assign-cluster", {"cluster_id": cluster_id})
        failures += check("assign_cluster", ok, err)
        ok, cov, err = get_json(f"/api/clusters/{cluster_id}/coverage")
        failures += check("cluster_coverage", ok and "documents" in (cov or {}), err)

    if campaign_id:
        ok, assign, err = post_json(f"/api/documents/{doc_id}/assign-campaign", {"campaign_id": campaign_id})
        failures += check("assign_campaign", ok, err)
        ok, cov, err = get_json(f"/api/campaigns/{campaign_id}/coverage")
        failures += check("campaign_coverage", ok and "documents" in (cov or {}), err)
        ok, sug, err = get_json(f"/api/campaigns/{campaign_id}/suggested-articles")
        failures += check("suggested_articles", ok and "suggestions" in (sug or {}), err)

    ok, dups, err = get_json(f"/api/documents/{doc_id}/duplicate-warnings")
    failures += check("duplicate_warnings", ok, err)

    return failures


if __name__ == "__main__":
    sys.exit(main())
