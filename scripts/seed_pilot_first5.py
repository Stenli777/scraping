#!/usr/bin/env python3
"""Seed crmflow24-first-5 pilot shell (no items)."""

from app.db.session import SessionLocal
from app.services.pilot_service import ensure_crmflow24_first5_pilot


def main() -> None:
    db = SessionLocal()
    pilot = ensure_crmflow24_first5_pilot(db)
    db.commit()
    print(f"Pilot #{pilot.id} slug={pilot.slug} status={pilot.status}")
    db.close()


if __name__ == "__main__":
    main()
