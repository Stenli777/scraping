#!/usr/bin/env bash
# PostgreSQL backup — non-destructive, writes to storage/system_backups/postgres/
set -euo pipefail

SCRAP_ROOT="${SCRAP_ROOT:-/opt/scrap}"
cd "$SCRAP_ROOT"
_read_db_url() { "$SCRAP_ROOT/.venv/bin/python" "$SCRAP_ROOT/scripts/_read_db_url.py" "$SCRAP_ROOT"; }


DB_URL="$(_read_db_url)"
PG_URL="${DB_URL/postgresql+psycopg2/postgresql}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$SCRAP_ROOT/storage/system_backups/postgres"
mkdir -p "$OUT_DIR"
DUMP="$OUT_DIR/scrap-${TS}.sql.gz"

echo "Backing up PostgreSQL to $DUMP"
pg_dump "$PG_URL" | gzip -c > "$DUMP"

if [[ ! -s "$DUMP" ]]; then
  echo "ERROR: dump file empty" >&2
  exit 1
fi

echo "OK: $(du -h "$DUMP" | cut -f1) $DUMP"
echo "$DUMP"
