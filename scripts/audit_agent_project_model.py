#!/usr/bin/env python3
"""Read-only audit: projects, prompts, overrides, effective resolution, optional HTTP markers."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from typing import Any

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

sys.path.insert(0, "/opt/scrap")

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.llm_run import LLMRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.project_prompt_override import ProjectPromptOverride
from app.models.prompt_template import PromptTemplate
from app.models.prompt_version import PromptVersion
from app.models.scraping_task import ScrapingTask
from app.services.agent_catalog_service import get_global_agent_catalog, get_project_agent_catalog
from app.services.agent_registry import KNOWN_AGENT_KEYS, get_agent_meta
from app.services.prompt_override_service import audit_override_integrity, get_project_override
from app.services.prompt_service import get_active_prompt


def doc_count(db: Session, project_id: int) -> int:
    q = (
        select(func.count())
        .select_from(ParsedDocument)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ScrapingTask.project_id == project_id)
    )
    return int(db.scalar(q) or 0)


def task_count(db: Session, project_id: int) -> int:
    return int(
        db.scalar(select(func.count()).select_from(ScrapingTask).where(ScrapingTask.project_id == project_id)) or 0
    )


def is_custom_key(key: str) -> bool:
    return key not in KNOWN_AGENT_KEYS


def active_global_version(db: Session, tpl_id: int) -> str | None:
    return db.scalar(
        select(PromptVersion.version)
        .where(PromptVersion.prompt_template_id == tpl_id, PromptVersion.is_active.is_(True))
        .order_by(PromptVersion.id.desc())
        .limit(1)
    )


def print_projects(db: Session) -> None:
    print("\n=== PROJECTS ===")
    rows = db.scalars(select(Project).order_by(Project.id)).all()
    for p in rows:
        print(
            f"id={p.id}\tslug={p.slug}\tname={p.name!r}\tenabled={p.enabled}\t"
            f"documents={doc_count(db, p.id)}\ttasks={task_count(db, p.id)}"
        )


def print_templates(db: Session) -> None:
    print("\n=== PROMPT TEMPLATES ===")
    for tpl in db.scalars(select(PromptTemplate).order_by(PromptTemplate.id)).all():
        gv = active_global_version(db, tpl.id)
        custom = is_custom_key(tpl.key)
        print(
            f"id={tpl.id}\tkey={tpl.key}\tname={tpl.name!r}\tenabled={tpl.enabled}\t"
            f"task_kind={tpl.task_kind}\tis_custom_guess={custom}\tactive_global_version={gv or '—'}"
        )


def print_versions(db: Session) -> None:
    print("\n=== PROMPT VERSIONS (all) ===")
    q = (
        select(PromptTemplate.key, PromptVersion.version, PromptVersion.is_active, PromptVersion.created_at, PromptVersion.id)
        .join(PromptTemplate, PromptVersion.prompt_template_id == PromptTemplate.id)
        .order_by(PromptTemplate.key, PromptVersion.id)
    )
    for key, ver, active, created, vid in db.execute(q).all():
        print(f"template_key={key}\tversion={ver}\tis_active={active}\tid={vid}\tcreated_at={created}")


def print_overrides(db: Session) -> None:
    print("\n=== PROJECT PROMPT OVERRIDES ===")
    q = (
        select(ProjectPromptOverride, Project, PromptTemplate, PromptVersion)
        .join(Project, ProjectPromptOverride.project_id == Project.id)
        .join(PromptTemplate, ProjectPromptOverride.prompt_template_id == PromptTemplate.id)
        .join(PromptVersion, ProjectPromptOverride.prompt_version_id == PromptVersion.id)
        .order_by(Project.id, PromptTemplate.key)
    )
    for ov, proj, tpl, pver in db.execute(q).all():
        notes_safe = (pver.notes or "")[:80].replace("\n", " ").replace("\t", " ")
        print(
            f"project_id={proj.id}\tproject_slug={proj.slug}\tprompt_key={tpl.key}\t"
            f"override_enabled={ov.enabled}\tversion_label={pver.version}\t"
            f"override_id={ov.id}\tcreated_at={ov.created_at}\tnotes_preview={notes_safe!r}"
        )


def applicable_keys_for_project(db: Session, project_id: int) -> set[str]:
    keys: set[str] = set(KNOWN_AGENT_KEYS)
    tpl_ids = db.scalars(
        select(ProjectPromptOverride.prompt_template_id)
        .where(ProjectPromptOverride.project_id == project_id)
        .distinct()
    ).all()
    for tid in tpl_ids:
        t = db.get(PromptTemplate, tid)
        if t:
            keys.add(t.key)
    return keys


def effective_matrix(db: Session) -> None:
    print("\n=== EFFECTIVE PROMPT MATRIX ===")
    print(
        "\t".join(
            [
                "project_id",
                "project_slug",
                "agent_key",
                "agent_label",
                "is_pipeline_agent",
                "effective_source",
                "effective_version",
                "has_enabled_project_override",
                "is_custom",
                "visible_on_project_page_expected",
            ]
        )
    )
    projects = db.scalars(select(Project).order_by(Project.id)).all()
    for proj in projects:
        expected_keys = {r["meta"]["key"] for r in get_project_agent_catalog(db, proj.id)}
        for key in sorted(applicable_keys_for_project(db, proj.id)):
            meta = get_agent_meta(key)
            label = meta.get("agent_name", key)
            pipe = key in KNOWN_AGENT_KEYS
            custom = not pipe
            try:
                eff = get_active_prompt(db, key, project_id=proj.id)
                esrc = eff.source
                evers = eff.version
            except ValueError as e:
                esrc = "value_error"
                evers = str(e)[:60]
            ov = get_project_override(db, proj.id, key)
            has_ov = bool(ov)
            vis = key in expected_keys
            print(
                f"{proj.id}\t{proj.slug}\t{key}\t{label}\t{pipe}\t{esrc}\t{evers}\t{has_ov}\t{custom}\t{vis}"
            )


def llm_audit(db: Session) -> None:
    print("\n=== LLM_RUNS SAMPLE (last 15, prompt_template set) ===")
    runs = db.scalars(
        select(LLMRun)
        .where(LLMRun.prompt_template.isnot(None))
        .order_by(LLMRun.id.desc())
        .limit(15)
    ).all()
    for r in runs:
        pt = (r.prompt_template or "")[:96]
        print(
            f"id={r.id}\tproject_id={r.project_id}\ttask_id={r.task_id}\t"
            f"model_alias={r.model_alias}\tprompt_template={pt!r}"
        )
    print("\n=== LLM_RUNS TOP prompt_template refs (by count) ===")
    rows = db.execute(
        select(LLMRun.prompt_template, func.count().label("c"))
        .where(LLMRun.prompt_template.isnot(None))
        .group_by(LLMRun.prompt_template)
        .order_by(func.count().desc())
        .limit(20)
    ).all()
    for pt, c in rows:
        print(f"count={c}\tref={str(pt)[:120]}")


def db_constraints(db: Session) -> None:
    print("\n=== PG CONSTRAINTS (prompt-related) ===")
    q = text(
        """
        SELECT tc.table_name, tc.constraint_name, tc.constraint_type
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'public'
          AND tc.table_name IN ('prompt_templates','prompt_versions','project_prompt_overrides')
        ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
        """
    )
    for row in db.execute(q).all():
        print(f"table={row[0]}\tconstraint={row[1]}\ttype={row[2]}")




def print_override_integrity(db: Session) -> int:
    print("\n=== Override integrity ===")
    report = audit_override_integrity(db)
    print(f"overall={report['overall']} fail={report['fail_count']} warn={report['warn_count']} "
          f"duplicate_pair_groups={report['duplicate_pair_groups']}")
    for item in report.get("issues", [])[:30]:
        print(f"  {item.get('severity')} {item.get('kind')} project={item.get('project_id')} "
              f"key={item.get('agent_key')} ids={item.get('override_ids')}")
    if report["overall"] == "FAIL":
        return 1
    return 0


def http_check(base: str) -> None:
    try:
        import httpx
    except ImportError:
        print("httpx not installed, skip --http")
        return
    paths = [
        "/admin/agents",
        "/admin/agents/new",
        "/admin/projects/1/agents",
        "/admin/projects/4/agents",
        "/admin/projects/1/agents/seo_enrich",
        "/admin/projects/4/agents/seo_enrich",
    ]
    keys_pat = re.compile(
        r"(review_article|rewrite_article|seo_enrich|quality_review|topic_cleanup_v1|zz_[a-z0-9_]+)",
        re.I,
    )
    print(f"\n=== HTTP CHECK base={base} ===")
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for path in paths:
            url = f"{base.rstrip('/')}{path}"
            r = client.get(url)
            text = r.text
            keys = sorted(set(keys_pat.findall(text)))
            proj_links = sorted(set(re.findall(r"/admin/projects/(\d+)/", text)))
            catalog_marker = "Общий каталог" in text
            project_title = "Агенты проекта" in text
            has_help = "Источник для этого проекта" in text
            print(
                f"URL={url}\tstatus={r.status_code}\tcatalog_marker={catalog_marker}\t"
                f"project_title={project_title}\thelp_marker={has_help}\t"
                f"admin_project_id_links={proj_links}\tkeys_found={len(keys)}"
            )
            if path == "/admin/agents" and not catalog_marker:
                print("  WARN: /admin/agents missing catalog marker")
            if path == "/admin/projects/4/agents":
                foreign = [x for x in proj_links if x != "4"]
                if foreign:
                    print(f"  FAIL: foreign project links {foreign}")
                if not project_title:
                    print("  FAIL: missing project page title marker")
                if "4AC Scope B" in text or "zz-4ac-scope-b" in text:
                    print("  FAIL: leaked test project B name on project 4 page")
                print(f"  sample_keys={keys[:20]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", action="store_true", help="Fetch admin pages (public HTTPS)")
    parser.add_argument("--http-base", default="https://scrap.crmflow24.ru")
    args = parser.parse_args()

    db = SessionLocal()
    integrity_rc = 0
    try:
        db_constraints(db)
        print_projects(db)
        print_templates(db)
        print_versions(db)
        print_overrides(db)
        integrity_rc = print_override_integrity(db)
        effective_matrix(db)
        llm_audit(db)
        g = get_global_agent_catalog(db)
        print(f"\n=== GLOBAL CATALOG ROW COUNT: {len(g)} ===")
        p4: list[dict[str, Any]] = get_project_agent_catalog(db, 4)
        print(f"=== PROJECT 4 CATALOG ROW COUNT: {len(p4)} ===")
        keys_p4 = [r["meta"]["key"] for r in p4]
        print("project_4_keys:", ",".join(keys_p4))
        if args.http:
            http_check(args.http_base)
    finally:
        db.close()
    print("\n=== DONE (read-only) ===")
    return integrity_rc


if __name__ == "__main__":
    raise SystemExit(main())
