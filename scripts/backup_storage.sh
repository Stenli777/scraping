#!/usr/bin/env bash
# Archive storage/backups and storage/media — non-destructive
set -euo pipefail

SCRAP_ROOT="${SCRAP_ROOT:-/opt/scrap}"
cd "$SCRAP_ROOT"
_read_db_url() { "$SCRAP_ROOT/.venv/bin/python" "$SCRAP_ROOT/scripts/_read_db_url.py" "$SCRAP_ROOT"; }

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$SCRAP_ROOT/storage/system_backups/storage"
mkdir -p "$OUT_DIR"
ARCHIVE="$OUT_DIR/storage-${TS}.tar.gz"

echo "Archiving storage/backups and storage/media to $ARCHIVE"
tar -czf "$ARCHIVE" \
  --ignore-failed-read \
  -C "$SCRAP_ROOT/storage" \
  backups media 2>/dev/null || tar -czf "$ARCHIVE" -C "$SCRAP_ROOT/storage" backups

if [[ ! -s "$ARCHIVE" ]]; then
  echo "ERROR: archive empty" >&2
  exit 1
fi

MANIFEST_DIR="$SCRAP_ROOT/storage/system_backups/manifests"
mkdir -p "$MANIFEST_DIR"
GIT_COMMIT="$(git -C "$SCRAP_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
PG_DUMP="$(ls -t "$SCRAP_ROOT/storage/system_backups/postgres"/scrap-*.sql.gz 2>/dev/null | head -1 || echo "")"

DB_URL="$(_read_db_url)"
PG_URL="${DB_URL/postgresql+psycopg2/postgresql}"
DOC_COUNT="$(psql "$PG_URL" -tAc 'SELECT COUNT(*) FROM parsed_documents' 2>/dev/null | tr -d ' ' || echo 0)"
MEDIA_COUNT="$(psql "$PG_URL" -tAc 'SELECT COUNT(*) FROM media_assets' 2>/dev/null | tr -d ' ' || echo 0)"

MANIFEST="$MANIFEST_DIR/manifest-${TS}.json"
cat > "$MANIFEST" <<EOF
{
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "postgres_dump": "${PG_DUMP#$SCRAP_ROOT/}",
  "storage_archive": "${ARCHIVE#$SCRAP_ROOT/}",
  "media_count": ${MEDIA_COUNT:-0},
  "document_count": ${DOC_COUNT:-0},
  "git_commit": "$GIT_COMMIT"
}
EOF

echo "Manifest: $MANIFEST"
echo "OK: $(du -h "$ARCHIVE" | cut -f1) $ARCHIVE"
echo "$ARCHIVE"
