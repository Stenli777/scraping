#!/usr/bin/env python3
"""Smoke tests for stage 4N draft review feedback."""

import json
import sys

import httpx

BASE = "https://scrap.crmflow24.ru"
CANDIDATE_ID = 5
PUBLICATION_ID = 7


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=60.0)
    results: dict[str, object] = {}
    ok = True

    r = client.post(
        f"/api/publications/{PUBLICATION_ID}/draft-feedback",
        json={
            "review_status": "accepted",
            "reviewer_name": "operator",
            "notes": "Checked in CRMFlow24 admin, looks good.",
            "required_changes": [],
            "checked_public_visibility": True,
            "checked_seo": True,
            "checked_content": True,
            "checked_media": True,
        },
    )
    results["accepted"] = {"status": r.status_code, "body": r.json() if r.status_code < 500 else r.text}
    ok = ok and r.status_code == 200

    cand = client.get(f"/api/release-candidates/{CANDIDATE_ID}").json()
    results["candidate_after_accept"] = {
        "draft_review_status": cand.get("draft_review_status"),
        "status": cand.get("status"),
    }

    pub_list = client.get("/api/publications").json()
    rec = next((p for p in pub_list.get("publications", []) if p["id"] == PUBLICATION_ID), None)
    results["publication_after_accept"] = rec

    r4 = client.post(f"/api/publications/{PUBLICATION_ID}/check-public-visibility", json={})
    results["visibility"] = {"status": r4.status_code, "body": r4.json() if r4.status_code < 500 else r4.text}
    ok = ok and r4.status_code == 200

    r2 = client.post(
        f"/api/release-candidates/{CANDIDATE_ID}/draft-feedback",
        json={
            "review_status": "needs_edits",
            "notes": "Title tweak needed",
            "required_changes": ["fix H1"],
            "apply_editorial_needs_revision": True,
        },
    )
    results["needs_edits"] = {"status": r2.status_code, "body": r2.json() if r2.status_code < 500 else r2.text}
    ok = ok and r2.status_code == 200

    r3 = client.post(
        f"/api/publications/{PUBLICATION_ID}/draft-feedback",
        json={
            "review_status": "rejected",
            "notes": "Not suitable for publication",
            "apply_editorial_reject": False,
        },
    )
    results["rejected"] = {"status": r3.status_code, "body": r3.json() if r3.status_code < 500 else r3.text}
    ok = ok and r3.status_code == 200

    admin_queue = client.get("/admin/draft-reviews")
    results["admin_queue"] = {"status": admin_queue.status_code, "has_table": "Draft review queue" in admin_queue.text}

    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
