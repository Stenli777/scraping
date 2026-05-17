#!/usr/bin/env python3
"""Seed crmflow24-mock-v2 publish target for integration testing."""

import os
import sys

sys.path.insert(0, os.environ.get("SCRAP_ROOT", "/opt/scrap"))

from app.db.session import SessionLocal
from app.models.project import Project
from app.models.publish_target import PublishTarget
from app.publishers.validators_v2 import PAYLOAD_VERSION as ARTICLE_V2

TARGET_NAME = "crmflow24-mock-v2"
ENDPOINT = os.environ.get(
    "CRMFLOW24_MOCK_ENDPOINT",
    "http://127.0.0.1:8800/api/mock-crmflow24/articles/import",
)


def main() -> int:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.enabled.is_(True)).order_by(Project.id.asc()).first()
        if not project:
            print("No enabled project found")
            return 1

        existing = (
            db.query(PublishTarget)
            .filter(PublishTarget.name == TARGET_NAME, PublishTarget.project_id == project.id)
            .first()
        )
        if existing:
            existing.target_type = "webhook"
            existing.endpoint_url = ENDPOINT
            existing.payload_format = ARTICLE_V2
            existing.dry_run = False
            existing.enabled = True
            existing.auth_type = "none"
            existing.auth_token_env_name = None
            db.commit()
            print(f"Updated target #{existing.id} {TARGET_NAME}")
            return 0

        target = PublishTarget(
            project_id=project.id,
            name=TARGET_NAME,
            target_type="webhook",
            endpoint_url=ENDPOINT,
            auth_type="none",
            auth_token_env_name=None,
            enabled=True,
            dry_run=False,
            default_status="draft",
            payload_format=ARTICLE_V2,
        )
        db.add(target)
        db.commit()
        print(f"Created target #{target.id} {TARGET_NAME}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
