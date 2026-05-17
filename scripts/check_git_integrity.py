#!/usr/bin/env python3
"""
import sys
from pathlib import Path
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
Git integrity checks — read-only."""
import sys

from repo_checks import (
    ROOT,
    detached_head,
    find_tmp_artifacts,
    git_branch,
    git_clean,
    git_head,
    origin_configured,
    uncommitted_migrations,
)


def main() -> int:
    errors: list[str] = []
    warns: list[str] = []

    if not origin_configured():
        errors.append("git remote 'origin' not configured")
    if detached_head():
        errors.append("detached HEAD")
    if not git_clean():
        warns.append("working tree not clean")
    mig = uncommitted_migrations()
    if mig:
        warns.append(f"uncommitted migration files: {len(mig)}")

    tmp = find_tmp_artifacts()
    for t in tmp:
        warns.append(f"tmp artifact present: {t}")

    branch = git_branch()
    head = git_head()
    print(f"branch={branch} head={head} root={ROOT}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 2
    if warns:
        for w in warns:
            print(f"WARN: {w}")
        return 1
    print("PASS: git integrity OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
