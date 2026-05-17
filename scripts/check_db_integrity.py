#!/usr/bin/env python3
"""Read-only DB integrity checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text

from app.core.enums import EditorialStatus
from app.db.session import SessionLocal
from app.models.parsed_document import ParsedDocument


def main() -> int:
    issues: list[str] = []
    warnings: list[str] = []
    valid_editorial = {e.value for e in EditorialStatus}

    with SessionLocal() as db:
        orphans = db.execute(
            text("""
                SELECT pr.id FROM publish_runs pr
                LEFT JOIN parsed_documents d ON d.id = pr.document_id
                WHERE d.id IS NULL LIMIT 20
            """)
        ).all()
        for row in orphans:
            issues.append(f"orphan publish_run #{row[0]}")

        orphans_media = db.execute(
            text("""
                SELECT ma.id FROM media_assets ma
                LEFT JOIN parsed_documents d ON d.id = ma.document_id
                WHERE d.id IS NULL LIMIT 20
            """)
        ).all()
        for row in orphans_media:
            issues.append(f"orphan media_asset #{row[0]}")

        bad_status = db.scalars(
            select(ParsedDocument).where(
                ParsedDocument.editorial_status.notin_(list(valid_editorial))
            ).limit(20)
        ).all()
        for doc in bad_status:
            issues.append(
                f"document #{doc.id} invalid editorial_status={doc.editorial_status}"
            )

        missing_rev = db.execute(
            text("""
                SELECT pr.id FROM publish_runs pr
                WHERE pr.document_revision_id IS NULL
                AND pr.status = 'success' LIMIT 20
            """)
        ).all()
        for row in missing_rev:
            warnings.append(
                f"publish_run #{row[0]} success without document_revision_id (legacy?)"
            )

    if issues:
        print("DB INTEGRITY: FAIL")
        for i in issues:
            print(f"  - {i}")
        for w in warnings:
            print(f"  WARN: {w}")
        return 1
    if warnings:
        print("DB INTEGRITY: OK (warnings)")
        for w in warnings:
            print(f"  WARN: {w}")
        return 0
    print("DB INTEGRITY: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
