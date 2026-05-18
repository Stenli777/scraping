#!/usr/bin/env python3
"""Seed crmflow24-production-v2 publish target."""

import os
import sys

sys.path.insert(0, os.environ.get("SCRAP_ROOT", "/opt/scrap"))

from app.core.config import get_crmflow24_publish_endpoint, get_crmflow24_publish_token_env_names
from app.db.session import SessionLocal
from app.models.project import Project
from app.models.publish_target import PublishTarget
from app.publishers.validators_v2 import PAYLOAD_VERSION as ARTICLE_V2

TARGET_NAME = "crmflow24-production-v2"
ENDPOINT = os.environ.get(
    "SCRAP_CRMFLOW24_IMPORT_URL",
    os.environ.get("CRMFLOW24_PUBLISH_ENDPOINT", get_crmflow24_publish_endpoint()),
)
AUTH_ENV = "CRMFLOW24_PUBLISH_TOKEN"


def _token_configured() -> bool:
    from app.core.config import get_settings
    s = get_settings()
    if (s.crmflow24_publish_token or s.scrap_crmflow24_import_token or "").strip():
        return True
    for name in get_crmflow24_publish_token_env_names():
        if os.environ.get(name, "").strip():
            return True
    return False


def main() -> int:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.enabled.is_(True)).order_by(Project.id.asc()).first()
        if not project:
            print("No enabled project")
            return 1
        has_token = _token_configured()
        existing = (
            db.query(PublishTarget)
            .filter(PublishTarget.name == TARGET_NAME, PublishTarget.project_id == project.id)
            .first()
        )
        fields = dict(
            target_type="webhook",
            endpoint_url=ENDPOINT or None,
            payload_format=ARTICLE_V2,
            auth_type="bearer",
            auth_token_env_name=AUTH_ENV,
            dry_run=False,
            enabled=bool(has_token and ENDPOINT),
            default_status="draft",
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            db.commit()
            print(f"Updated #{existing.id} {TARGET_NAME} enabled={existing.enabled}")
            return 0
        target = PublishTarget(project_id=project.id, name=TARGET_NAME, **fields)
        db.add(target)
        db.commit()
        print(f"Created #{target.id} {TARGET_NAME} enabled={target.enabled}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
