#!/usr/bin/env python3
"""Safe regression: project agent save flow on isolated test project."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "/opt/scrap")

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.project import Project
from app.services.prompt_override_service import (
    create_project_override_version,
    disable_project_override,
    get_effective_prompt_details,
)
from app.services.project_admin_service import create_project, validate_project_form

TEST_SLUG = "zz-4aa-agent-save-test"
TEST_KEY = "review_article"


def main() -> int:
    db = SessionLocal()
    project = db.scalar(select(Project).where(Project.slug == TEST_SLUG))
    created = False
    try:
        if not project:
            errors, parsed = validate_project_form(
                db,
                slug=TEST_SLUG,
                name="4AA Save Test",
                default_language="ru",
                domain="",
                allowed_topics_json="[]",
                blocked_topics_json="[]",
            )
            if errors:
                print(f"FAIL setup: {errors}")
                return 1
            project = create_project(db, parsed, enabled=False)
            created = True
            print(f"created test project id={project.id}")

        pid = project.id
        ver = f"4aa-{int(time.time())}"

        create_project_override_version(
            db,
            pid,
            TEST_KEY,
            version=ver,
            system="4aa test system",
            user="4aa test user {title}",
            notes="4aa regression",
            activate=False,
        )
        eff = get_effective_prompt_details(db, TEST_KEY, project_id=pid)
        print(f"PASS save_version source={eff['source']}")

        create_project_override_version(
            db,
            pid,
            TEST_KEY,
            version=ver + "-act",
            system="4aa test system active",
            user="4aa active {title}",
            activate=True,
        )
        eff2 = get_effective_prompt_details(db, TEST_KEY, project_id=pid)
        if eff2["source"] != "project_override":
            print(f"FAIL activate expected project_override got {eff2['source']}")
            return 1
        print("PASS save_and_activate -> project_override")

        disable_project_override(db, pid, TEST_KEY)
        eff3 = get_effective_prompt_details(db, TEST_KEY, project_id=pid)
        if eff3["source"] == "project_override":
            print("FAIL disable still project_override")
            return 1
        print(f"PASS disable source={eff3['source']}")

        # topic_cleanup must not 500
        create_project_override_version(
            db,
            pid,
            "topic_cleanup_v1",
            version=f"4aa-tc-{int(time.time())}",
            system="tc sys",
            user="tc {title}",
            activate=False,
        )
        print("PASS topic_cleanup_v1 save (template auto-created)")

        print("All agent save-flow checks passed")
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if created and project:
            project.enabled = False
            db.commit()
        db.close()


if __name__ == "__main__":
    sys.exit(main())
