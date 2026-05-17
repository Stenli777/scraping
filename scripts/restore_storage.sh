#!/usr/bin/env bash
# Restore storage archive — overwrites backups/media, requires CONFIRM_RESTORE=YES
set -euo pipefail

SCRAP_ROOT="${SCRAP_ROOT:-/opt/scrap}"
ARCHIVE="${1:-}"

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "ERROR: Set CONFIRM_RESTORE=YES to run restore (destructive)" >&2
  echo "Usage: CONFIRM_RESTORE=YES $0 /path/to/storage-TIMESTAMP.tar.gz" >&2
  exit 1
fi

if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
  echo "ERROR: provide path to .tar.gz archive" >&2
  exit 1
fi

echo "Extracting $ARCHIVE into $SCRAP_ROOT/storage/"
tar -xzf "$ARCHIVE" -C "$SCRAP_ROOT/storage"
echo "OK: storage restore completed"
