#!/usr/bin/env bash
# Verify latest backup manifest and artifacts
set -euo pipefail

SCRAP_ROOT="${SCRAP_ROOT:-/opt/scrap}"
MANIFEST_DIR="$SCRAP_ROOT/storage/system_backups/manifests"
FAIL=0

latest="$(ls -t "$MANIFEST_DIR"/manifest-*.json 2>/dev/null | head -1 || true)"
if [[ -z "$latest" ]]; then
  echo "FAIL: no manifest found in $MANIFEST_DIR"
  exit 1
fi

echo "Checking manifest: $latest"
python3 -c "import json; json.load(open('$latest'))" || { echo "FAIL: invalid JSON"; exit 1; }

pg="$(python3 -c "import json; print(json.load(open('$latest')).get('postgres_dump',''))")"
st="$(python3 -c "import json; print(json.load(open('$latest')).get('storage_archive',''))")"

for rel in "$pg" "$st"; do
  if [[ -z "$rel" ]]; then
    echo "WARN: missing path in manifest for one artifact"
    FAIL=1
    continue
  fi
  path="$SCRAP_ROOT/$rel"
  if [[ ! -f "$path" ]]; then
    echo "FAIL: missing $path"
    FAIL=1
  elif [[ "$path" == *.gz ]]; then
    gzip -t "$path" 2>/dev/null || { echo "FAIL: corrupt gzip $path"; FAIL=1; }
    echo "OK: $path ($(du -h "$path" | cut -f1))"
  elif [[ "$path" == *.tar.gz ]]; then
    tar -tzf "$path" >/dev/null 2>&1 || { echo "FAIL: corrupt tar $path"; FAIL=1; }
    echo "OK: $path ($(du -h "$path" | cut -f1))"
  fi
done

if [[ "$FAIL" -eq 0 ]]; then
  echo "PASS: backup verification"
  exit 0
fi
echo "FAIL: backup verification"
exit 1
