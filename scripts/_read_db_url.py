#!/usr/bin/env python3
"""Print DATABASE_URL from .env (safe parse, no shell source)."""
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/scrap")
default = "postgresql+psycopg2://scrap:scrap@127.0.0.1:5432/scrap"
env = root / ".env"
if not env.is_file():
    print(default)
    raise SystemExit(0)
for line in env.read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        val = line.split("=", 1)[1].strip().strip('"').strip("'")
        print(val or default)
        raise SystemExit(0)
print(default)
