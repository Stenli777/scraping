#!/usr/bin/env python3
"""Regression: project-scoped and custom agent creation."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "/opt/scrap")

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.project import Project
from app.models.prompt_template import PromptTemplate
from app.services.prompt_override_service import (
    create_project_override_version,
    get_effective_prompt_details,
)
from app.services.project_admin_service import create_project, validate_project_form

TEST_SLUG = "zz-4ab-custom-agent-test"
CUSTOM_KEY = "zz_test_custom_4ab"


def _test_project(db):
    p = db.scalar(select(Project).where(Project.slug == TEST_SLUG))
    if p:
        return p, False
    _, parsed = validate_project_form(
        db,
        slug=TEST_SLUG,
        name="4AB Custom Test",
        default_language="ru",
        domain="",
        allowed_topics_json="[]",
        blocked_topics_json="[]",
    )
    return create_project(db, parsed, enabled=False), True


def main() -> int:
    db = SessionLocal()
    created_project = False
    try:
        project, created_project = _test_project(db)
        pid = project.id
        ts = int(time.time())

        # Scenario 1: existing seo_enrich + project override
        create_project_override_version(
            db,
            pid,
            "seo_enrich",
            version=f"4ab-seo-{ts}",
            system="4ab seo sys",
            user="4ab seo {title}",
            activate=True,
        )
        eff = get_effective_prompt_details(db, "seo_enrich", project_id=pid)
        if eff["source"] != "project_override":
            print(f"FAIL scenario1 source={eff['source']}")
            return 1
        print("PASS scenario1 project override for seo_enrich")

        # Scenario 2: custom agent + project
        ck = f"{CUSTOM_KEY}_{ts}"
        from app.services.prompt_service import create_prompt_version, ensure_prompt_template

        ensure_prompt_template(db, ck, name="4AB Test Custom", task_kind="other")
        import json

        create_prompt_version(
            db,
            ck,
            version="v1",
            content_md=json.dumps({"system": "c", "user": "u {title}"}),
            activate=True,
        )
        create_project_override_version(
            db,
            pid,
            ck,
            version=f"p1-{ts}",
            system="c",
            user="u {title}",
            activate=True,
        )
        tpl = db.scalar(select(PromptTemplate).where(PromptTemplate.key == ck))
        if not tpl:
            print("FAIL scenario2 no template")
            return 1
        print("PASS scenario2 custom/manual with project")

        # Scenario 3: global custom
        gk = f"{CUSTOM_KEY}_global_{ts}"
        ensure_prompt_template(db, gk, name="4AB Global Custom", task_kind="other")
        create_prompt_version(
            db,
            gk,
            version="v1",
            content_md=json.dumps({"system": "g", "user": "g"}),
            activate=True,
        )
        print("PASS scenario3 global custom agent")

        print("All custom agent flow checks passed")
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if created_project:
            project = db.scalar(select(Project).where(Project.slug == TEST_SLUG))
            if project:
                project.enabled = False
                db.commit()
        db.close()


if __name__ == "__main__":
    sys.exit(main())
