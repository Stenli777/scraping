#!/usr/bin/env python3
"""DB connectivity smoke check."""
import sys
sys.path.insert(0, "/opt/scrap")

from sqlalchemy import text
from app.db.session import SessionLocal


def check(name: str, ok: bool, detail: str = "") -> int:
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return 0 if ok else 1


def main() -> int:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return check("database", True)
    except Exception as exc:
        return check("database", False, str(exc))


if __name__ == "__main__":
    sys.exit(main())
