"""Pipeline tasks API smoke check."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.smoke._common import check, get_json


def main() -> int:
    ok, data, err = get_json("/api/tasks?limit=1")
    if isinstance(data, list):
        count = len(data)
    elif isinstance(data, dict):
        count = len(data.get("tasks", []))
    else:
        count = 0
    return check("pipeline_tasks", ok, err or f"count={count}")


if __name__ == "__main__":
    sys.exit(main())
