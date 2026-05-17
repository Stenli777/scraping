# Backup and Recovery

## What is backed up

| Component | Location | Script |
|-----------|----------|--------|
| PostgreSQL | `storage/system_backups/postgres/` | `scripts/backup_postgres.sh` |
| Task backups + media | `storage/system_backups/storage/` | `scripts/backup_storage.sh` |
| Manifest | `storage/system_backups/manifests/` | created by `backup_storage.sh` |
| Alembic state | DB + repo `alembic/versions/` | manual git |
| Env templates | `.env.example` in git | manual |
| Nginx | `/etc/nginx/` on server | manual reference |

## What is NOT backed up

- `.venv`, `__pycache__`, tmp files
- Rotated log artifacts (use journald)
- Hermes (`/hermes`) — separate system
- CLIProxyAPI (`/opt/cliproxyapi`) — separate system

## Backup layout

```text
storage/system_backups/
  postgres/scrap-YYYYMMDDTHHMMSSZ.sql.gz
  storage/storage-YYYYMMDDTHHMMSSZ.tar.gz
  manifests/manifest-YYYYMMDDTHHMMSSZ.json
```

## Recovery sequence

1. Stop services: `systemctl stop scrap-api scrap-worker`
2. Restore PostgreSQL: `CONFIRM_RESTORE=YES scripts/restore_postgres.sh <dump>`
3. Restore storage: `CONFIRM_RESTORE=YES scripts/restore_storage.sh <archive>`
4. Verify `.env` matches environment
5. `alembic current` / `alembic upgrade head`
6. `scripts/verify_backup.sh` (on new backups after recovery test)
7. `PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/run_all.py`
8. `curl /health/ready`
9. `systemctl start scrap-api scrap-worker`

## Disaster scenarios

| Scenario | Action |
|----------|--------|
| DB corruption | Restore latest postgres dump; check alembic revision |
| Storage loss | Restore storage archive; run `check_storage_integrity.py` |
| Media loss | Restore archive; re-link or regenerate placeholders |
| Bad deploy | `git checkout` previous commit; restart; smoke |
| Bad migration | Restore DB backup taken before migration; `alembic downgrade` if safe |
| Failed publish loop | Admin failed items; no auto-recovery |
| Broken LLM provider | Readiness degraded; pipeline continues with errors logged |
| Hermes unavailable | Optional — readiness degraded if `ENABLE_HERMES=true` |
