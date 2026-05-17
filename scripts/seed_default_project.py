#!/usr/bin/env python3
"""Seed default project for multi-project foundation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.project import Project


def main() -> None:
    db = SessionLocal()
    existing = db.query(Project).filter_by(slug="crmflow24").first()
    if existing:
        print(f"Project already exists: id={existing.id} slug={existing.slug}")
        db.close()
        return
    project = Project(
        slug="crmflow24",
        name="CRMFlow24",
        domain="crmflow24.ru",
        enabled=True,
        rewrite_profile="default",
        seo_profile="default",
        publish_mode="draft",
    )
    db.add(project)
    db.commit()
    print(f"Created project id={project.id} slug={project.slug}")
    db.close()


if __name__ == "__main__":
    main()
