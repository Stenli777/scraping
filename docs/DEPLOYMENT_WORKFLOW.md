# Deployment Workflow

## Safe deploy sequence

1. `cd /opt/scrap && git status` (must be clean)
2. `git pull`
3. Review `.env` changes against `.env.example`
4. **Backup before migrations:** `bash scripts/backup_postgres.sh && bash scripts/backup_storage.sh`
5. `.venv/bin/alembic upgrade head`
6. `PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/run_all.py`
7. `systemctl restart scrap-api scrap-worker`
8. `curl -s https://scrap.crmflow24.ru/health/ready`

## Rollback sequence

1. `git log --oneline -5` — identify good commit
2. `git checkout <commit>` (or `git revert`)
3. If migration was applied: `alembic downgrade -1` **only if safe**
4. `systemctl restart scrap-api scrap-worker`
5. Smoke + readiness checks

## Migration safety

- Always backup PostgreSQL before `alembic upgrade`
- Verify `alembic current` shows expected head
- Never run destructive downgrades on production without DB backup
