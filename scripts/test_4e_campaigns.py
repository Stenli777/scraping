#!/usr/bin/env python3
"""Stage 4E manual integration tests."""

import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("SCRAP_TEST_BASE", "http://127.0.0.1:8800")
DOC_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def call(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": "application/json"} if body else {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read() else {}


def main():
    print("=== 4E tests ===")
    code, cluster = call("POST", "/api/clusters", {"project_id": 1, "name": "Bitrix24 telephony", "cluster_type": "integration", "primary_keyword": "bitrix24 telephony", "secondary_keywords": ["WhatsApp integration", "Telegram funnel automation"]})
    print("1 create cluster", code, cluster.get("id"))
    cid = cluster.get("id")
    code, camp = call("POST", "/api/campaigns", {"project_id": 1, "name": "CRM automation Q2", "target_keywords": ["bitrix24", "crm"]})
    print("2 create campaign", code, camp.get("id"))
    camp_id = camp.get("id")
    code, topics = call("POST", f"/api/documents/{DOC_ID}/extract-topics", {})
    print("3 topics", code, topics)
    if cid:
        print("4 assign", call("POST", f"/api/documents/{DOC_ID}/assign-cluster", {"cluster_id": cid}))
        print("5 coverage", call("GET", f"/api/clusters/{cid}/coverage"))
    if camp_id:
        call("POST", f"/api/documents/{DOC_ID}/assign-campaign", {"campaign_id": camp_id})
        print("6 campaign coverage", call("GET", f"/api/campaigns/{camp_id}/coverage"))
        print("7 suggestions", call("GET", f"/api/campaigns/{camp_id}/suggested-articles"))
    print("8 duplicates", call("GET", f"/api/documents/{DOC_ID}/duplicate-warnings"))


if __name__ == "__main__":
    main()
