# Scrap — Operations Guide

Руководство для ежедневной ручной работы с контентным конвейером. **Current:** без auto-enqueue, auto-publish и scheduler (`ENABLE_AUTOMATION=false`, `ENABLE_SCHEDULER=false`).

## Production publish path (Required)

**Preferred (RC-first):**

```text
Document ready → Create RC → Run QA → Operator approve → Publish from RC card
  → POST /api/release-candidates/{id}/publish-draft
```

**Legacy (deprecated):** `POST /api/documents/{id}/publish-draft` и admin form на карточке документа — тот же stale-revision guard, но **без дисциплины RC QA**. Использовать только для smoke/debug.

**`force=true`:** обязателен `force_reason`; обходит review/quality/editorial/duplicate — см. [CONSOLIDATION_INVENTORY.md](CONSOLIDATION_INVENTORY.md).

## Daily workflow

1. Открыть **Admin → Discovery** (`/admin/source-directories`)
2. Выбрать source directory → **Run discovery** (лимит по умолчанию 20 URL)
3. Открыть **Discovered URLs** (`/admin/discovered-urls`)
4. Просмотреть кандидатов → **Enqueue** по одному URL
5. Дождаться задачи: **Dashboard** или `/admin/tasks/{id}`
6. Открыть **Document** → проверить **Pipeline Summary** и **Review**
7. При необходимости **Rerun rewrite**
8. **Run SEO** если slug/метаданные пустые
9. **Release candidate** → QA → approve → **Publish draft** с карточки RC
10. Проверить **Publish runs** (`/admin/publish-runs`)

## Runtime diagnostics (Phase B)

**Current:** операторская visibility без изменения pipeline/publish semantics.

| Surface | URL / command |
|---------|----------------|
| Admin diagnostics | `/admin/diagnostics` — flags, queue/backlog, publish sample, trust, drift warnings |
| API (safe JSON) | `GET /api/ops/diagnostics` — без секретов и raw env |
| Dashboard block | `/admin` — краткий queue/backlog + ссылка на диагностику |
| Smoke | `PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/check_runtime_diagnostics.py` |

**Не показывает:** токены, ключи, полные значения env. **Не включает** automation/scheduler/auto-publish.

### Phase C — safety hardening

| Guard | Detail |
|-------|--------|
| API access | `GET /api/ops/diagnostics` — **localhost only** (403 иначе); совпадает с `uvicorn --host 127.0.0.1` |
| Admin | `/admin/diagnostics` — тот же operator context, что и остальной `/admin` |
| Query limits | publish sample 25, stale RC scan 200, LLM failures 20 — см. `meta.sample_limits` в ответе |
| Drift severity | `info` / `warning` / `critical` — visibility only, без auto-fix |
| Incident triage | Блок top risks, queue pressure, publish/LLM failure samples |

### Reliability Phase (I) — operational confidence & replay safety

| Surface | Detail |
|---------|--------|
| Confidence | `/admin/diagnostics` → **Operational confidence** (deterministic level, not SLO) |
| Replay safety | Per retryable `publish_run`: verdict (`retry_allowed_same_revision`, `blocked_new_revision_required`, …) |
| Smoke | `check_runtime_reliability.py` |

Levels: `high` / `medium` / `low` / `critical` from bounded checks (stale RC, warnings, safety flags).

### Integrity Phase (H) — RC remediation & recovery discipline

| Surface | Detail |
|---------|--------|
| Integrity admin | `/admin/integrity` — stale approved RC list, supersede (archive), batch max 20 |
| Auto-archive | New `document_revision` archives stale open RC (incl. approved) for that document |
| CLI | `scripts/ops_integrity_remediate.py` (dry-run default; `--apply --supersede-stale-approved`) |
| Smoke | `check_runtime_integrity.py` |

**Replay-safe:** supersede не удаляет `publish_runs` / revisions; publish stale guard сохранён.

### Cohesion Phase (G) — authority & boundaries

| Surface | Detail |
|---------|--------|
| Authority map | `/admin/diagnostics` → «Runtime authority» — enforced vs governance-only vs decorative |
| Invariant consistency | Stale approved RC sample, automation/auto-publish flag checks |
| Smoke | `check_runtime_cohesion.py` |

### Operational Stability Phase (F) — incident readiness

| Surface | Detail |
|---------|--------|
| Incident history | `operational_incidents` — kinds: `queue_pressure`, `stale_rc_approved`, `publish_failed`, `force_publish`, `llm_failure_spike`, `drift_critical` |
| Sync | On `/admin/diagnostics` load — `sync_incidents_from_runtime` (dedupe 30m) |
| Snapshot compare | Latest vs previous snapshot deltas in diagnostics |
| Recovery playbook | Read-only scenarios on diagnostics + failed-items |
| Hygiene CLI | `PYTHONPATH=/opt/scrap .venv/bin/python scripts/ops_runtime_hygiene.py` (dry-run); `--apply-snapshots` / `--apply-incidents` optional bounded retention |
| Smoke | `check_operational_incidents.py` |

**Not:** ticketing, alerting, Prometheus, auto-retry orchestration.

### Runtime Safety Phase (E) — operator hardening

| Guard | Detail |
|-------|--------|
| Stale RC approve | `approve_release_candidate` raises; admin buttons disabled when `revision_stale` |
| Stale RC publish | Unchanged from Phase A — blocked at service layer |
| Force publish (admin) | Checkbox `force_confirm` + `force_reason`; errors via `?op_error=` banner |
| Legacy publish UI | Collapsed under «Legacy publish»; RC-first warning above |
| Diagnostics drift | `approved_stale_rc` — sample of approved RCs binding stale revision (visibility only) |
| Publish runs | Rows with `force_used` highlighted |

**Not changed:** `force=true` still bypasses review/quality/editorial/duplicate when reason given; automation/scheduler off.

### Phase D — operational history (bounded snapshots)

| Item | Detail |
|------|--------|
| Storage | `operational_snapshots` — compact `metrics_json` per capture |
| Capture | Auto on `/admin/diagnostics` (throttle 15 min); manual: `PYTHONPATH=/opt/scrap .venv/bin/python scripts/capture_operational_snapshot.py` |
| Retention | 30 days + max 500 rows |
| Trends | Queue, LLM failures, recurring drift IDs, incident episodes (read-only) |
| Not | Prometheus, realtime streaming, incident ticketing |

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
| Backlog / stale | `/admin/diagnostics` → queue section; `/admin/failed-items` для действий |
| Drift warnings | `/admin/diagnostics` → governance/runtime drift (visibility only) |
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

### Post-publish draft review

1. После успешного publish draft открыть CRMFlow24 admin URL из publication/candidate.
2. Проверить контент, SEO, медиа; убедиться, что статья не в blog/sitemap/rss.
3. В Scrap: release candidate → Draft Review → отметить accepted / needs_edits / rejected.
4. При accepted — ручная публикация в CRMFlow24 (вне Scrap).
5. При needs_edits — правки в Scrap, новая revision/candidate; без auto-rerun rewrite.

### Release operations checkpoint

- `PYTHONPATH=/opt/scrap .venv/bin/python scripts/check_release_state.py`
- `docs/SCRIPTS.md` — полный inventory
- `/admin/operations` — release summary (drafts, missing feedback, smoke warnings)

### Smoke (safe default)

```bash
PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/run_all.py
```

Production target probe (no publish):

```bash
PYTHONPATH=/opt/scrap .venv/bin/python scripts/smoke/run_all.py --include-production
```

## 2026-05-18 — этап 4Q — Post-publication tracking

1. Оператор публикует пост в CRMFlow24 admin (вне Scrap).
2. `scripts/check_public_publication.py --publication-id ID` или API check-public-status.
3. При `status=public` — `confirm-public` (или `--confirm --confirmed-by operator`).
4. `analytics_ready` для content_performance (без auto-import метрик).
- After confirm-public: open analytics-ready queue → Import metrics → review `/admin/analytics`.
- Production Pilot block on `/admin/operations` with active pilots and progress.
- **4T:** first 5 pilot run — 1 item (doc #4); discovery needed for 4 more; `run_pilot_first5_check.py`.
- **4U:** trusted discovery → manual enqueue → pipeline; pilot fill 2/5; see PROJECT_LOG.
- **4V:** autobit24-blog discovery + `scripts/intake_urls.py` for trusted manual URLs.

## Historical / test publish failures (4W)

Старые `failed_retryable` publish runs с `Env variable … is not set` — **не production blocker**:
- Run **#17** — до настройки `CRMFLOW24_PUBLISH_TOKEN` (target `crmflow24-mock-v2`).
- Run **#23** — тестовая цель `crmflow24-test-bad-token` (disabled).

В admin (`/admin/publish-runs`, `/admin/failed-items`) отображаются badges: `historical env`, `test target`.

CLIProxy **429** — rate limit, retry с backoff. **400** на rewrite — часто переполнение prompt; rewrite обрезается до 12k символов (`input_truncated` в metadata).
