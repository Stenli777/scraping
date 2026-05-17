"""Shared smoke check utilities."""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")
ROOT = os.environ.get("SCRAP_ROOT", "/opt/scrap")


def check(name: str, ok: bool, detail: str = "") -> int:
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return 0 if ok else 1


def get_json(path: str, timeout: int = 15) -> tuple[bool, dict | None, str]:
    try:
        req = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode()), ""
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = {}
        return False, body, f"HTTP {exc.code}"
    except Exception as exc:
        return False, None, str(exc)

def main() -> int:
    ok, data, err = get_json("/health/ready")
    if not ok:
        return check("cliproxy", False, err)
    cp = data.get("checks", {}).get("cliproxyapi", "")
    if cp in ("ok", "not_configured"):
        return check("cliproxy", True, cp)
    return check("cliproxy", False, cp)


if __name__ == "__main__":
    sys.exit(main())
