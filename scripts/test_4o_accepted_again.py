#!/usr/bin/env python3
"""Verify accepted-again after rejected for candidate #5 / publication #7."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

BASE = "https://scrap.crmflow24.ru"
CANDIDATE_ID = 5
PUBLICATION_ID = 7


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60.0)
    r = c.post(
        f"/api/release-candidates/{CANDIDATE_ID}/draft-feedback",
        json={
            "review_status": "accepted",
            "reviewer_name": "operator",
            "notes": "Re-accepted after 4O checkpoint",
            "checked_public_visibility": True,
            "checked_seo": True,
            "checked_content": True,
            "checked_media": True,
        },
    )
    if r.status_code != 200:
        print("FAIL", r.status_code, r.text[:300])
        return 1
    body = r.json()
    cand = c.get(f"/api/release-candidates/{CANDIDATE_ID}").json()
    pubs = c.get("/api/publications").json()
    pub = next(p for p in pubs["publications"] if p["id"] == PUBLICATION_ID)
    print("feedback", body.get("review_status"), "id", body.get("id"))
    print("candidate draft_review_status", cand.get("draft_review_status"))
    print("publication draft_review_status", pub.get("draft_review_status"))
    ok = (
        body.get("review_status") == "accepted"
        and cand.get("draft_review_status") == "accepted"
        and pub.get("draft_review_status") == "accepted"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
