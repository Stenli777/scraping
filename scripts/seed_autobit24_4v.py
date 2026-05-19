#!/usr/bin/env python3
"""Seed autobit24-blog source directory and domain trust (idempotent)."""
import sys

sys.path.insert(0, "/opt/scrap")

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.domain_trust_registry import DomainTrustRegistry
from app.models.project import Project
from app.models.source_directory import SourceDirectory

BLOCK = [
    "/tag/", "/tags/", "/category/", "/author/", "/users/", "/search",
    "/page/", "/?p=", "/feed", "/rss", "#comments",
]
ALLOW = ["/blog/"]

db = SessionLocal()
project = db.scalar(select(Project).where(Project.slug == "crmflow24"))
if not project:
    project = db.get(Project, 1)
pid = project.id

for domain, score, level in [
    ("autobit24.ru", 70, "high"),
    ("www.autobit24.ru", 70, "high"),
]:
    if not db.scalar(select(DomainTrustRegistry).where(DomainTrustRegistry.domain == domain, DomainTrustRegistry.project_id.is_(None))):
        db.add(DomainTrustRegistry(domain=domain, trust_score=score, trust_level=level, project_id=None, notes="Bitrix24/CRM integrator blog, 4V"))
        print("trust", domain)

existing = db.scalar(select(SourceDirectory).where(SourceDirectory.name == "autobit24-blog"))
if not existing:
    d = SourceDirectory(
        project_id=pid,
        name="autobit24-blog",
        base_url="https://autobit24.ru/blog/",
        discovery_mode="html_links",
        enabled=True,
        max_urls_per_run=20,
        max_depth=1,
        crawl_delay_seconds=1,
        allow_patterns_json=ALLOW,
        block_patterns_json=BLOCK,
    )
    db.add(d)
    db.flush()
    print("created autobit24-blog id", d.id)
else:
    existing.base_url = "https://autobit24.ru/blog/"
    existing.allow_patterns_json = ALLOW
    existing.block_patterns_json = BLOCK
    existing.enabled = True
    print("updated autobit24-blog id", existing.id)

db.commit()
db.close()
