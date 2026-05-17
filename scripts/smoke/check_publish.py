"""Publish pipeline smoke checks (targets, health, mock receiver, v2 validation)."""

import json
import os
import sys

from scripts.smoke._common import BASE, check, get_json

ROOT = os.environ.get("SCRAP_ROOT", "/opt/scrap")


def main() -> int:
    failures = 0

    ok, data, err = get_json("/api/publish-targets")
    failures += check("publish_targets", ok, err or "")

    ok, health, err = get_json("/api/publish-targets/health")
    failures += check("publish_targets_health", ok, err or "")
    if ok and health:
        failures += check(
            "publish_targets_health_payload",
            "targets" in health,
            str(health.get("healthy")),
        )

    ok, mock_list, err = get_json("/api/mock-crmflow24/articles")
    failures += check("mock_crmflow24_list", ok, err or "")
    if ok and mock_list:
        failures += check(
            "mock_crmflow24_testing_flag",
            mock_list.get("testing_only") is True,
            "testing_only missing",
        )

    # minimal article_v2 validation via mock import (invalid payload -> 400)
    import urllib.error
    import urllib.request

    bad_payload = {"payload_version": "article_v2", "title": ""}
    req = urllib.request.Request(
        BASE + "/api/mock-crmflow24/articles/import",
        data=json.dumps(bad_payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        failures += check("mock_v2_validation_rejects", False, "expected 400")
    except urllib.error.HTTPError as exc:
        failures += check("mock_v2_validation_rejects", exc.code == 400, f"HTTP {exc.code}")
    except Exception as exc:
        failures += check("mock_v2_validation_rejects", False, str(exc))

    return failures


if __name__ == "__main__":
    sys.exit(main())
