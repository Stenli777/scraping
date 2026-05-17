#!/usr/bin/env python3
"""
import sys
from pathlib import Path
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
Repository safety checks — read-only."""
import sys

from repo_checks import (
    ROOT,
    find_large_tracked_files,
    find_tmp_artifacts,
    find_tracked_secrets,
    git_clean,
)

def main() -> int:
    errors: list[str] = []
    warns: list[str] = []

    tmp = find_tmp_artifacts()
    for t in tmp:
        warns.append(f"deploy/tmp artifact: {t}")

    secrets = find_tracked_secrets()
    errors.extend(secrets)

    large = find_large_tracked_files()
    warns.extend(large)

    if not git_clean():
        warns.append("git working tree not clean")

    if errors:
        print("ERROR: repo safety failed")
        for e in errors:
            print(f"  ERROR: {e}")
        for w in warns:
            print(f"  WARN: {w}")
        return 2
    if warns:
        print("WARN: repo safety warnings")
        for w in warns:
            print(f"  WARN: {w}")
        return 1
    print(f"PASS: repo safe ({ROOT})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
