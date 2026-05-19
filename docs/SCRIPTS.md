# Scripts inventory

Все команды — с сервера `/opt/scrap`, venv: `.venv/bin/python` или `PYTHONPATH=/opt/scrap .venv/bin/python`.

Легенда: **safe** = read-only по умолчанию; **destructive** = меняет БД/внешние системы (только с явным флагом).

## Repository & integrity

| Path | Purpose | Safety | Example |
|------|---------|--------|---------|
| `scripts/check_repo_safety.py` | Tracked secrets, tmp artifacts, large files | safe | `PYTHONPATH=/opt/scrap .venv/bin/python scripts/check_repo_safety.py` |
| `scripts/check_git_integrity.py` | Git branch, clean tree, migrations | safe | `PYTHONPATH=/opt/scrap .venv/bin/python scripts/check_git_integrity.py` |
| `scripts/check_db_integrity.py` | DB schema sanity | safe | `.venv/bin/python scripts/check_db_integrity.py` |
| `scripts/check_storage_integrity.py` | Storage paths | safe | `.venv/bin/python scripts/check_storage_integrity.py` |
| `scripts/check_release_state.py` | Release/draft-review consistency | safe | `PYTHONPATH=/opt/scrap .venv/bin/python scripts/check_release_state.py` |

## Backup & restore

| Path | Purpose | Safety | Example |
|------|---------|--------|---------|
| `scripts/backup_postgres.sh` | PostgreSQL dump | destructive (writes backup) | `bash scripts/backup_postgres.sh` |
| `scripts/backup_storage.sh` | Storage archive | destructive (writes backup) | `bash scripts/backup_storage.sh` |
| `scripts/restore_postgres.sh` | Restore DB | **destructive** | Только по runbook |
| `scripts/restore_storage.sh` | Restore files | **destructive** | Только по runbook |
| `scripts/verify_backup.sh` | Verify latest manifest | safe | `bash scripts/verify_backup.sh` |

## Deploy & post-deploy

| Path | Purpose | Safety | Example |
|------|---------|--------|---------|
| `scripts/pre_deploy_check.py` | Pre-deploy gates | safe | `.venv/bin/python scripts/pre_deploy_check.py` |
| `scripts/post_deploy_check.py` | Post-deploy smoke hooks | safe | `.venv/bin/python scripts/post_deploy_check.py` |
| `scripts/smoke/run_all.py` | Full smoke suite | safe (HTTP/DB reads) | `PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/run_all.py` |

## Release operations

| Path | Purpose | Safety | Example |
|------|---------|--------|---------|
| `scripts/find_safe_doc.py` | List production-suitable documents | safe | `PYTHONPATH=/opt/scrap .venv/bin/python scripts/find_safe_doc.py` |
| `scripts/run_4m_ops.py` | RC create → QA → approve → optional draft publish | destructive with `--publish` | `... run_4m_ops.py` (dry) / `... --publish` |
| `scripts/test_4m_release_run.py` | Stage 4M release regression | destructive with `--publish` | `... test_4m_release_run.py` |
| `scripts/test_4n_draft_feedback.py` | Draft feedback API smoke | writes feedback | `... test_4n_draft_feedback.py` |
| `scripts/report_publish.py` | Publish run report | safe | `.venv/bin/python scripts/report_publish.py` |

## Cleanup & maintenance

| Path | Purpose | Safety | Example |
|------|---------|--------|---------|
| `scripts/cleanup_enrichment_jobs.py` | Enrichment retention report/cleanup | dry-run default | `... cleanup_enrichment_jobs.py` / `--apply` |

## Runtime helpers

| Path | Purpose | Safety | Example |
|------|---------|--------|---------|
| `scripts/run_api.sh` | Start API locally | — | `bash scripts/run_api.sh` |
| `scripts/run_worker.sh` | Start worker | — | `bash scripts/run_worker.sh` |
| `scripts/init_db.sh` | DB init | destructive | Только первичная установка |

## Test scripts (`scripts/test_*.py`)

Stage regression tests (2x–4x). По умолчанию не трогают CRMFlow24 production без явных флагов. См. docstring каждого файла.

**Prerequisites:** `.env` на сервере, `systemctl` сервисы active, `alembic upgrade head`.

**Граница:** Scrap **никогда** не публикует публично. Public publish — только вручную в CRMFlow24 admin.

### Smoke safety mode (4P)

| Script | Default | Production |
|--------|---------|------------|
| `scripts/smoke/run_all.py` | mock-only, no production publish | `--include-production` adds `check_crmflow24_production_target.py` |
| `scripts/smoke/check_crmflow24_production_target.py` | not in default suite | OPTIONS/HEAD probe, token env check, no draft |

## check_public_publication.py

```bash
PYTHONPATH=/opt/scrap .venv/bin/python scripts/check_public_publication.py --publication-id 7
PYTHONPATH=/opt/scrap .venv/bin/python scripts/check_public_publication.py --publication-id 7 --confirm --confirmed-by operator
```

По умолчанию только check; `--confirm` требует явного флага.
- `import_analytics_snapshot.py --publication-id ID --views N ...` ; `--sample` for test data.
- `scripts/check_pilot_state.py` (read-only); `scripts/seed_pilot_first5.py`.
- `run_pilot_first5_check.py` — read-only pilot report; `--refresh` updates statuses.
- Discovery: `run_discovery_test.py`; ops `/tmp/run_4u_ops.py` (discover|enqueue|pilot).
- `intake_urls.py` — bulk manual URL intake (--file, --enqueue optional).

## 4W audit (ops, on-server)
- `/tmp/4w_full_audit.py`, `/tmp/4w_ops.py` — одноразовые; удалять после ops.
- Регрессия: `scripts/run_pilot_first5_check.py --refresh`, `scripts/smoke/run_all.py`.
