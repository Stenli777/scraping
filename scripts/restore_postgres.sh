#!/usr/bin/env bash
# Restore PostgreSQL from gzip dump — DESTRUCTIVE, requires CONFIRM_RESTORE=YES
set -euo pipefail

SCRAP_ROOT="${SCRAP_ROOT:-/opt/scrap}"
DUMP="${1:-}"

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "ERROR: Set CONFIRM_RESTORE=YES to run restore (destructive)" >&2
  echo "Usage: CONFIRM_RESTORE=YES $0 /path/to/scrap-TIMESTAMP.sql.gz" >&2
  exit 1
fi

if [[ -z "$DUMP" || ! -f "$DUMP" ]]; then
  echo "ERROR: provide path to .sql.gz dump" >&2
  exit 1
fi

cd "$SCRAP_ROOT"
_read_db_url() { "$SCRAP_ROOT/.venv/bin/python" "$SCRAP_ROOT/scripts/_read_db_url.py" "$SCRAP_ROOT"; }


DB_URL="$(_read_db_url)"
PG_URL="${DB_URL/postgresql+psycopg2/postgresql}"

echo "Restoring $DUMP into $PG_URL"
gunzip -c "$DUMP" | psql "$PG_URL"
echo "OK: restore completed"
