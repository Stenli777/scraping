#!/usr/bin/env python3
"""Regression: project agents page must not leak other projects' custom agents."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "/opt/scrap")

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.project import Project
from app.services.agent_catalog_service import get_project_agent_catalog
from app.services.prompt_override_service import create_project_override_version
from app.services.project_admin_service import create_project, validate_project_form

SLUG_A = "zz-4ac-scope-a"
SLUG_B = "zz-4ac-scope-b"
CUSTOM_KEY = "zz_test_custom_scope"


def _ensure_project(db, slug: str, name: str) -> Project:
    p = db.scalar(select(Project).where(Project.slug == slug))
    if p:
        p.enabled = False
        db.commit()
        return p
    _, parsed = validate_project_form(
        db,
        slug=slug,
        name=name,
        default_language="ru",
        domain="",
        allowed_topics_json="[]",
        blocked_topics_json="[]",
    )
    return create_project(db, parsed, enabled=False)


def main() -> int:
    db = SessionLocal()
    try:
        pa = _ensure_project(db, SLUG_A, "4AC Scope A")
        pb = _ensure_project(db, SLUG_B, "4AC Scope B")
        db.refresh(pa)
        db.refresh(pb)
        ts = int(time.time())
        ck = f"{CUSTOM_KEY}_{ts}"

        from app.services.prompt_service import create_prompt_version, ensure_prompt_template

        import json

        ensure_prompt_template(db, ck, name="Scope Custom", task_kind="other")
        create_prompt_version(
            db,
            ck,
            version="v1",
            content_md=json.dumps({"system": "s", "user": "u"}),
            activate=True,
        )
        create_project_override_version(
            db,
            pa.id,
            ck,
            version=f"p{pa.id}-{ts}",
            system="s",
            user="u",
            activate=True,
        )
        create_project_override_version(
            db,
            pa.id,
            "seo_enrich",
            version=f"p{pa.id}-seo-{ts}",
            system="seo s",
            user="seo u",
            activate=True,
        )

        rows_a = get_project_agent_catalog(db, pa.id)
        keys_a = {r["meta"]["key"] for r in rows_a}
        if ck not in keys_a:
            print(f"FAIL: project A missing custom {ck}")
            return 1
        if "seo_enrich" not in keys_a:
            print("FAIL: project A missing seo_enrich")
            return 1

        rows_b = get_project_agent_catalog(db, pb.id)
        keys_b = {r["meta"]["key"] for r in rows_b}
        if ck in keys_b:
            print("FAIL: project B leaked custom agent from A")
            return 1

        seo_b = next(r for r in rows_b if r["meta"]["key"] == "seo_enrich")
        if seo_b["source_for_project"] == "project_override":
            print("FAIL: project B seo should not be project_override from A")
            return 1

        print("PASS project agent scoping")
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
