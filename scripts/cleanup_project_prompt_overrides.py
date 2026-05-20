#!/usr/bin/env python3
"""De-duplicate project_prompt_overrides: disable extra enabled rows (dry-run by default)."""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "/opt/scrap")

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.project import Project
from app.models.project_prompt_override import ProjectPromptOverride
from app.models.prompt_template import PromptTemplate
from app.services.prompt_override_service import audit_override_integrity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Apply enabled=false to losers")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = audit_override_integrity(db)
        print(f"integrity={report['overall']} dup_groups={report['duplicate_pair_groups']}")
        if report["overall"] == "PASS":
            print("Nothing to clean")
            return 0

        dup_rows = db.execute(
            select(
                ProjectPromptOverride.project_id,
                ProjectPromptOverride.prompt_template_id,
                func.count(),
            )
            .group_by(ProjectPromptOverride.project_id, ProjectPromptOverride.prompt_template_id)
            .having(func.count() > 1)
        ).all()

        for project_id, tpl_id, _ in dup_rows:
            rows = list(
                db.scalars(
                    select(ProjectPromptOverride)
                    .where(
                        ProjectPromptOverride.project_id == project_id,
                        ProjectPromptOverride.prompt_template_id == tpl_id,
                    )
                    .order_by(ProjectPromptOverride.id.desc())
                ).all()
            )
            enabled = [r for r in rows if r.enabled]
            winner = enabled[0] if enabled else rows[0]
            losers = [r for r in rows if r.id != winner.id and r.enabled]
            tpl = db.get(PromptTemplate, tpl_id)
            proj = db.get(Project, project_id)
            print(
                f"project={proj.slug if proj else project_id} key={tpl.key if tpl else tpl_id} "
                f"winner_id={winner.id} disable={[x.id for x in losers]}"
            )
            if args.execute:
                for row in losers:
                    row.enabled = False
        if args.execute and dup_rows:
            db.commit()
            print("EXECUTED: extras disabled")
        elif dup_rows:
            print("DRY-RUN only (use --execute)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
