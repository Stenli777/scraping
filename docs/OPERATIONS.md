# Scrap — Operations Guide

Руководство для ежедневной ручной работы с контентным конвейером. Без auto-enqueue, auto-publish и scheduler.

## Daily workflow

1. Открыть **Admin → Discovery** (`/admin/source-directories`)
2. Выбрать source directory → **Run discovery** (лимит по умолчанию 20 URL)
3. Открыть **Discovered URLs** (`/admin/discovered-urls`)
4. Просмотреть кандидатов → **Enqueue** по одному URL
5. Дождаться задачи: **Dashboard** или `/admin/tasks/{id}`
6. Открыть **Document** → проверить **Pipeline Summary** и **Review**
7. При необходимости **Rerun rewrite**
8. **Run SEO** если slug/метаданные пустые
9. Проверить **Publish readiness** → **Publish draft** / dry-run
10. Проверить **Publish runs** (`/admin/publish-runs`)

## End-to-end path (entity links)

```
Source Directory → Discovered URL → Task → Document → Review / SEO / Publish
```

В admin на каждой странице есть блок **Links** и **Pipeline Summary**.

## Publish readiness

API: `GET /api/documents/{id}/publish-readiness`

Проверяется:

- project привязан к задаче
- `rewritten_text` не пустой
- `seo_metadata` и `slug`
- `ENABLE_PUBLISHING=true`
- enabled publish target для проекта
- status только `draft`
- review take/score (project thresholds, default score ≥ 60)
- duplicate successful publish (нужен `force=true` для повтора)

Ответ включает `checks`: `review_take`, `review_score`, `seo_exists`, `duplicate_publish`, и т.д.

## Production publish (crmflow24)

1. Заполнить в `.env` (не коммитить):
   - `CRMFLOW24_PUBLISH_ENDPOINT` — URL draft API
   - `CRMFLOW24_PUBLISH_TOKEN` — bearer token
2. Target `crmflow24-draft-webhook` (migration 006): `target_type=webhook`, `auth_token_env_name=CRMFLOW24_PUBLISH_TOKEN`
3. Пока endpoint пуст — target остаётся в **dry-run** (безопасно)
4. `POST /api/documents/{id}/publish-draft` body: `{"publish_target_id": N, "dry_run": false, "force": false}`

**Idempotency:** повторный успешный publish блокируется (HTTP 409). `force=true` — только вручную.

**Rollback publish:**

```env
ENABLE_PUBLISHING=false
```

или очистить `CRMFLOW24_PUBLISH_ENDPOINT` и перезапустить сервисы.

## Failed items

`/admin/failed-items` — failed_retryable tasks, terminal errors, failed LLM runs, failed publish runs.

Безопасные действия:

- **Mark skipped** — только для `failed_retryable` → `error` с пометкой оператора
- **Reset stale** — running-задача без обновления 2+ часа → `failed_retryable`

## Troubleshooting

| Симптом | Действие |
|---------|----------|
| CLIProxy degraded | `/health/ready`, проверить cliproxyapi; временно `REWRITER_PROVIDER=mock` |
| LLM 429 | Подождать; rerun rewrite/review/seo позже |
| `failed_retryable` | Failed items → открыть task → исправить причину или mark skipped |
| Нет SEO slug | Run SEO на document |
| Нет rewritten_text | Rerun rewrite |
| Publish blocked | Publish readiness → missing list |
| Discovery всё blocked | Ослабить allow_patterns или другой source |
| Duplicate URLs | Нормально; enqueue не создаст дубль task |

## Safe rollback (env)

```env
REWRITER_PROVIDER=mock
ENABLE_PUBLISHING=false
ENABLE_SOURCE_DISCOVERY=false
ENABLE_LLM_REVIEW=false
ENABLE_SEO_ENRICH=false
ENABLE_QUALITY_REVIEW=false
```

**Rollback prompt version:** Admin → `/admin/prompts/{key}` → Activate предыдущую версию (или SQL: снять `is_active` у новой, включить у старой).

**Rollback quality gating:** `ENABLE_QUALITY_REVIEW=false` — publish не блокируется по quality; manual endpoint вернёт 503.

**Rollback editorial gating:** `ENABLE_EDITORIAL_WORKFLOW=false` — publish readiness без operator approval; editorial API вернёт 400.

После изменений: `sudo systemctl restart scrap-api scrap-worker`

## System commands

```bash
cd /opt/scrap
systemctl status scrap-api scrap-worker --no-pager
curl -s https://scrap.crmflow24.ru/health
curl -s https://scrap.crmflow24.ru/health/ready
journalctl -u scrap-api -n 50 --no-pager
journalctl -u scrap-worker -n 50 --no-pager
.venv/bin/alembic current
```

## E2E test script

```bash
cd /opt/scrap
PYTHONPATH=/opt/scrap .venv/bin/python scripts/test_2f_e2e.py          # read-only check
PYTHONPATH=/opt/scrap .venv/bin/python scripts/test_2f_e2e.py --execute  # limited discovery+enqueue
```

Не использует Hermes, не делает auto-publish.


## Media storage

- Path: `MEDIA_STORAGE_PATH` (default `/opt/scrap/storage/media`)
- Structure: `YYYY/MM/DD/` unique filenames, immutable
- Rollback: `ENABLE_MEDIA_PIPELINE=false` + restart API

## Media flags

- `ENABLE_MEDIA_PIPELINE` — master switch (API/admin)
- `ENABLE_MEDIA_GENERATION` — real AI providers (off by default)
- `MEDIA_PROVIDER=placeholder` — safe test provider


## Backup (manual)

```bash
cd /opt/scrap
bash scripts/backup_postgres.sh
bash scripts/backup_storage.sh
bash scripts/verify_backup.sh
```

## Smoke tests

```bash
PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/run_all.py
```

## Integrity checks

```bash
.venv/bin/python scripts/check_storage_integrity.py
.venv/bin/python scripts/check_db_integrity.py
```

See `docs/BACKUP_AND_RECOVERY.md`, `docs/DEPLOYMENT_WORKFLOW.md`, `docs/LOGGING.md`.


## Analytics import

```bash
curl -X POST http://127.0.0.1:8800/api/publications/{id}/analytics/import \
  -H 'Content-Type: application/json' \
  -d '{"views":1200,"ctr":0.04,"source":"manual"}'
```

Flags: `ENABLE_ANALYTICS`, `ENABLE_PUBLICATION_TRACKING`.

## Scheduler service

```bash
systemctl status scrap-scheduler
journalctl -u scrap-scheduler -n 50
```

Enable (operator):
```
ENABLE_SCHEDULER=true
ENABLE_AUTOMATION=true
systemctl restart scrap-api scrap-scheduler
```

Readiness при включённом scheduler проверяет heartbeat (<180s).

## Async automation lifecycle (Stage 4B)

- `POST /api/automation/rules/{id}/run` creates `automation_run` with `status=queued` and returns immediately.
- `scrap-scheduler` picks queued runs first, then enqueues due scheduled rules.
- Run statuses: `queued`, `running`, `cancel_requested`, `cancelled`, `completed`, `failed`, `skipped`.
- `progress_json` and structured `logs_json` events for operator visibility.
- `POST /api/automation/runs/{id}/cancel` — queued→cancelled, running→cancel_requested.
- Stale `running` (heartbeat timeout) → `failed` via scheduler recovery or `POST .../mark-failed`.
- **Production default:** `ENABLE_SCHEDULER=false`, `ENABLE_AUTOMATION=false` (rules remain disabled in DB).

## Repository safety (Stage 4C)

```bash
python scripts/check_repo_safety.py
python scripts/check_git_integrity.py
python scripts/pre_deploy_check.py
python scripts/post_deploy_check.py
curl -s http://127.0.0.1:8800/api/system/workspace
```



## Publish operations (4D)

- Health: `curl -s http://127.0.0.1:8800/api/publish-targets/health`
- Retry: `POST /api/publish-runs/{id}/retry` when status is `failed_retryable`
- Mock seed: `PYTHONPATH=/opt/scrap .venv/bin/python scripts/seed_crmflow24_mock_v2_target.py`
- Integration tests: `PYTHONPATH=/opt/scrap .venv/bin/python scripts/test_4d_publish.py [document_id]`

### Campaign operations (4E)

- Tests: `PYTHONPATH=/opt/scrap .venv/bin/python scripts/test_4e_campaigns.py [doc_id]`
- Smoke: `scripts/smoke/check_campaigns.py`

### Production publish (4F)

- Seed: `scripts/seed_crmflow24_production_v2_target.py`
- Env on server only: `CRMFLOW24_PUBLISH_ENDPOINT`, `CRMFLOW24_PUBLISH_TOKEN`
- Health: `GET /api/publish-targets/health`



## CRMFlow24 smoke draft (stage 4F/4G)

После smoke publish в CRMFlow24 остаётся черновик поста — удалить **вручную** в админке CRM:
- https://crmflow24.ru/admin/posts/cmpats92t0006a2316na5xups
- Это не публичный пост; не отображается в `/blog`, sitemap, RSS.
- Из Scrap удалять не нужно.

### LLM enrichment operations (4H)

If CLIProxy slow/dead: enrichment jobs mark `failed_retryable`; retry via API/admin. `extract-topics` stays fast. Tune `TOPIC_CLEANUP_TIMEOUT_SECONDS`.


## Deterministic-first orchestration (4I — see OPERATIONS.md)

```text
Core pipeline (scrape → rewrite → publish)
        ↓
Deterministic extraction (sync, <3s) → strategy gate → topics in metadata
        ↓
Optional async enrichment (llm_enrichment_jobs) → conservative merge → topics enriched
        ↓
Editorial intelligence (review, quality)
        ↓
Campaign intelligence (coverage, clusters) — uses deterministic-first topics
```

### Boundaries

- Enrichment is **optional**; failures do not block publish/rewrite/scraping.
- Worker processes **scraping batch first**, then max 1 enrichment job per poll.
- Scheduler runs enrichment tick **before** automation tick (isolated limits).
- Campaign intelligence ignores failed/stale enrichment; uses `deterministic_result` until merge completes.

### Enrichment job states

`queued` → `running` → `completed` | `failed_retryable` | `failed_terminal` | `cancelled` | `skipped`

Stale `running` jobs (heartbeat timeout) → `failed_retryable` with `[stale recovery]`.

### Merge policy

See `app/services/enrichment_merge_policy.py` — deterministic source-of-truth.

## Source quality intelligence (4J)

```text
discovery → deterministic quality scoring → quality_scored | quality_blocked
         → manual approve OR enqueue (never auto-enqueue blocked)
```

Deterministic-first; no embeddings. Optional LLM review via `ENABLE_SOURCE_QUALITY_LLM_REVIEW` (off by default).

Guarantees: core pipeline never waits on quality scoring; URLs never deleted.

### Similarity analysis ops

- Пороги: `SIMILARITY_NEAR_DUPLICATE_THRESHOLD` (80), `SIMILARITY_TOPIC_OVERLAP_THRESHOLD` (65), `SIMILARITY_CANNIBALIZATION_THRESHOLD` (75).
- Sync quick check в pipeline после rewrite; deep — enrichment job `similarity_analysis`.
- `scripts/test_4k_canonical.py` — ручной smoke.

### Release candidate ops
- `scripts/test_4l_release.py`
- Flow: create → run-qa → approve → publish-draft
- Low-level `POST /api/publish` remains for debug

### Release runbook
См. `docs/RELEASE_RUNBOOK.md`. Smoke: `scripts/test_4m_release_run.py` (без `--publish`).
