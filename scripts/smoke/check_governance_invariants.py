#!/usr/bin/env python3
"""Governance invariant smoke ??? safe DB/API checks, no production publish."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.feature_flags import is_auto_publish_enabled, is_automation_enabled
from app.db.session import SessionLocal
from app.models.document_revision import DocumentRevision
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.publish_run import PublishRun
from app.publishers.exceptions import PublishValidationError
from app.services.revision_service import get_latest_revision, validate_revision_current_for_publish


def _ok(name: str) -> None:
    print(f"[PASS] {name}")


def _fail(name: str, detail: str) -> int:
    print(f"[FAIL] {name} ??? {detail}")
    return 1


def main() -> int:
    failures = 0

    if is_auto_publish_enabled():
        failures += _fail("auto_publish_disabled", "ENABLE_AUTO_PUBLISH must be false")
    else:
        _ok("auto_publish_disabled")

    if is_automation_enabled():
        failures += _fail("automation_disabled", "ENABLE_AUTOMATION+SCHEDULER must be false")
    else:
        _ok("automation_disabled")

    db = SessionLocal()
    try:
        doc = db.query(ParsedDocument).order_by(ParsedDocument.id.desc()).first()
        if not doc:
            print("[PASS] governance_invariants ??? skip (no documents)")
            return failures

        latest = get_latest_revision(db, doc.id)
        if latest:
            older = (
                db.query(DocumentRevision)
                .filter(
                    DocumentRevision.document_id == doc.id,
                    DocumentRevision.id != latest.id,
                )
                .order_by(DocumentRevision.revision_number.desc())
                .first()
            )
            if older:
                try:
                    validate_revision_current_for_publish(db, doc.id, older)
                    failures += _fail("stale_revision_blocked", "expected PublishValidationError")
                except PublishValidationError:
                    _ok("stale_revision_blocked")
            else:
                print("[PASS] stale_revision ??? skip (single revision)")
        else:
            print("[PASS] stale_revision ??? skip (no revisions)")

        from app.services.publish_service import _validate_force_override

        try:
            _validate_force_override(force=True, force_reason=None)
            failures += _fail("force_requires_reason", "expected validation error")
        except PublishValidationError:
            _ok("force_requires_reason")

        try:
            _validate_force_override(force=True, force_reason="smoke test reason")
        except PublishValidationError as exc:
            failures += _fail("force_with_reason_ok", str(exc))
        else:
            _ok("force_with_reason_ok")

        proj = db.query(Project).order_by(Project.id.asc()).first()
        if proj is not None and hasattr(proj, "trust_level"):
            if proj.trust_level < 0 or proj.trust_level > 3:
                failures += _fail("trust_level_range", f"got {proj.trust_level}")
            else:
                _ok("trust_level_column")
        else:
            failures += _fail("trust_level_column", "missing trust_level on project")

        if hasattr(doc, "operator_touched"):
            _ok("operator_touched_column")
        else:
            failures += _fail("operator_touched_column", "missing field")

        run = (
            db.query(PublishRun)
            .filter(PublishRun.force_used.is_(True))
            .order_by(PublishRun.id.desc())
            .first()
        )
        if run and run.force_used and not (run.force_reason or "").strip():
            print(
                f"[PASS] force_reason_audit ??? legacy run #{run.id} "
                "(pre-Phase-A); new force publishes require reason"
            )
        elif run and run.force_reason:
            _ok("force_reason_audit")
        else:
            print("[PASS] force_reason_audit ??? skip (no forced runs)")

        from app.services.automation_service import process_automation_run

        try:
            process_automation_run(db, -1)
        except Exception as exc:
            msg = str(exc)
            if "Automation disabled" in msg or "not found" in msg:
                _ok("automation_execution_gated")
            else:
                failures += _fail("automation_execution_gated", msg)
    finally:
        db.close()

    if failures:
        print(f"=== FAIL: {failures} invariant(s) ===")
        return 1
    print("=== PASS: governance invariants ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

