#!/usr/bin/env python3
"""Production CRMFlow24 publish target check — no publish, no draft creation.

Safety:
- read-only / safe probe only
- does not modify CRMFlow24
- does not publish
- does not print secrets

Run only via: scripts/smoke/run_all.py --include-production
"""

from __future__ import annotations

import os
import sys

ROOT = os.environ.get("SCRAP_ROOT", "/opt/scrap")
sys.path.insert(0, ROOT)

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.publish_target import PublishTarget
from app.services.publish_target_health_service import check_publish_target_health
from app.services.publish_target_safety_service import TARGET_CLASS_PRODUCTION, classify_publish_target
from scripts.smoke._common import check


def main() -> int:
    failures = 0
    with SessionLocal() as db:
        targets = db.scalars(select(PublishTarget).where(PublishTarget.enabled.is_(True))).all()
        prod = [t for t in targets if classify_publish_target(t) == TARGET_CLASS_PRODUCTION]
        failures += check("production_target_exists", bool(prod), "no enabled production target")
        for t in prod:
            failures += check(
                f"production_token_env_{t.name}",
                bool(t.auth_token_env_name and os.environ.get(t.auth_token_env_name, "").strip()),
                f"env {t.auth_token_env_name} missing",
            )
            failures += check(
                f"production_payload_{t.name}",
                (t.payload_format or "") == "article_v2",
                t.payload_format or "missing",
            )
            h = check_publish_target_health(db, t)
            failures += check(
                f"production_reachable_{t.name}",
                h.get("reachable") or h.get("http_status") in (401, 403, 404, 405),
                h.get("reach_detail", ""),
            )
    return failures


if __name__ == "__main__":
    sys.exit(main())
