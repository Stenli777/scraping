#!/usr/bin/env python3
import sys
sys.path.insert(0, "/opt/scrap")
from app.db.session import SessionLocal
from app.models.domain_trust_registry import DomainTrustRegistry

SEEDS = [
    ("habr.com", 88, "high"),
    ("www.habr.com", 88, "high"),
    ("saltpro.ru", 78, "high"),
    ("www.saltpro.ru", 78, "high"),
    ("crmflow24.ru", 70, "medium"),
    ("autobit24.ru", 70, "high"),
    ("www.autobit24.ru", 70, "high"),
]

db = SessionLocal()
for domain, score, level in SEEDS:
    if not db.query(DomainTrustRegistry).filter_by(domain=domain, project_id=None).first():
        db.add(DomainTrustRegistry(domain=domain, trust_score=score, trust_level=level))
db.commit()
print("seeded", len(SEEDS))
