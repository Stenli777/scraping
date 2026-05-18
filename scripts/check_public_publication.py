#!/usr/bin/env python3
"""Check or confirm public CRMFlow24 publication (read-only by default).

Safety:
- read-only by default (check only)
- does not modify CRMFlow24
- does not public-publish
- confirm requires explicit --confirm flag
- does not print secrets
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.services.publication_confirmation_service import (
    check_public_visibility,
    confirm_publication,
    get_publication_confirmation_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Public publication check/confirm")
    parser.add_argument("--publication-id", type=int, required=True)
    parser.add_argument("--confirm", action="store_true", help="Confirm public after check")
    parser.add_argument("--confirmed-by", default="operator")
    parser.add_argument("--notes", default="")
    parser.add_argument("--force", action="store_true", help="Force confirm when not visible")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = check_public_visibility(db, args.publication_id)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        if args.confirm:
            conf = confirm_publication(
                db,
                args.publication_id,
                confirmed_by=args.confirmed_by,
                notes=args.notes or None,
                force=args.force,
            )
            print("--- confirm ---")
            print(json.dumps(conf, indent=2, ensure_ascii=False, default=str))
        db.commit()
        status = get_publication_confirmation_status(db, args.publication_id)
        print("--- status ---")
        print(json.dumps(status, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
