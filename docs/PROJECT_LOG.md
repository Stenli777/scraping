# Project log (Cursor / ops)

Формат записи:

```
## YYYY-MM-DD HH:MM UTC
- **Что изменено:**
- **Файлы:**
- **Команды:**
- **Результат:**
- **Ошибки:**
- **Следующий шаг:**
```

---

## 2026-05-17 09:22 UTC — Initial scaffold + deploy on hermes

- **Что изменено:** Создан и развёрнут MVP Scrap в `/opt/scrap`.
- **Результат:** Task #1 saltpro URL → done, HTTP health ok.
- **Следующий шаг:** HTTPS, прогон 5 URL, domain parsers.

---

## 2026-05-17 09:40 UTC — HTTPS, domain parsers, 5 URL test run

### Предварительная проверка
- `git status`: modified `docs/PROJECT_LOG.md`
- `scrap-api`, `scrap-worker`: **active**
- `curl http://127.0.0.1:8800/health` → ok
- `curl http://scrap.crmflow24.ru/health` → ok

### HTTPS
- **Backup nginx:** `/root/backup-nginx-2026-05-17-0934/scrap.crmflow24.ru.conf`
- **Команда:** `certbot --nginx -d scrap.crmflow24.ru --non-interactive --agree-tos --redirect`
- **Сертификат:** `/etc/letsencrypt/live/scrap.crmflow24.ru/`, expires **2026-08-15**
- **Проверка:** `curl -s https://scrap.crmflow24.ru/health` → ok

### Прогон 5 URL

| # | URL | Task | Parser | Status | Doc |
|---|-----|------|--------|--------|-----|
| 1 | saltpro …kedo-reytinge… | 1 | generic_article | done | 1 |
| 1b | saltpro …kedo… (повтор) | 2 | saltpro_article | error→duplicate skip* | 1 |
| 2 | saltpro …vibecode… | 3 | saltpro_article | done | 2 |
| 3 | saltpro …nalogovaya… | 4 | saltpro_article | done | 3 |
| 4 | sotbit …nastroyka-crm… | 5 | sotbit_article | done | 4 |
| 5 | habr …1031736 | 6 | habr_article | done | 5 |

\*Повтор URL #1: контент уже в doc #1 (hash duplicate). После фикса pipeline — graceful skip.

### Качество парсинга (clean_text length / words)
- doc #2 saltpro vibecode: 5725 chars, 802 words
- doc #3 saltpro nalogovaya: 3119 chars, 426 words
- doc #4 sotbit: 11774 chars, 1490 words
- doc #5 habr: 22062 chars, 2938 words

### Изменённые файлы
- `app/parsers/utils.py`, `saltpro_article.py`, `sotbit_article.py`, `habr_article.py`
- `app/parsers/registry.py`, `generic_article.py`
- `app/services/pipeline.py`, `task_service.py`
- `app/exporters/json_markdown.py`
- `app/admin/templates/*`, `admin.css`
- `app/core/enums.py`
- `scripts/run_test_urls.py`, `validate_tasks.py`
- `docs/*`

### Команды
- `certbot --nginx -d scrap.crmflow24.ru ...`
- `scp` app/scripts/docs → hermes
- `python -m compileall app`
- `systemctl restart scrap-api scrap-worker`
- `python scripts/run_test_urls.py`
- `PYTHONPATH=/opt/scrap python scripts/validate_tasks.py`

### Следующий шаг
- GitHub remote + push
- CLIProxy rewriter
- CRMFlow24 export webhook
- Опционально: доработка habr raw_text noise

---

## 2026-05-17 — Stage 2B: production CLIProxy rewrite in main pipeline

- **Что изменено:** `run_rewrite_stage()` в pipeline; prompt `rewrite_article_v1`; `RewriteRequest`/`RewriteResponse`; rerun rewrite API/admin; `failed_retryable` status; admin rewrite metadata.
- **Файлы:** `app/services/rewrite_service.py`, `app/llm/prompts.py`, `app/services/pipeline.py`, `app/services/llm_tasks.py`, `app/api/rewrite.py`, admin templates, docs.
- **Production switch:** по умолчанию остаётся `REWRITER_PROVIDER=mock`; cliproxy включается явно через env.
- **Не сделано:** Hermes runtime, auto-publish, crawler, RAG, React/SPA.

---

## 2026-05-17 — Stage 2C: project profiles + review + SEO foundation

- **Миграция:** `003` — project profile fields, `review_results`, `seo_metadata`, seed crmflow24
- **Prompts:** `review_article_v1`, `seo_enrich_v1`
- **Pipeline:** optional review → rewrite → seo_enrich
- **Admin:** `/admin/projects/{id}`, `/admin/review-queue`, SEO на document/task

---

## 2026-05-17 — Stage 2D: publish webhook foundation

- **Миграция:** `004` — `publish_targets`, `publish_runs`, seed crmflow24 mock dry-run
- **Publishers:** mock, webhook, payload `article_v1`
- **API:** `POST publish-draft`, `GET publish-runs`, `GET publish-targets`
- **Без auto-publish**; только manual draft

---

## 2026-05-17 — Stage 2E: source discovery foundation

- **Миграция:** `005` — extend `source_directories`, `discovered_urls`, seed crmflow24 blogs
- **Services:** URL normalizer, sitemap + HTML discovery, manual enqueue
- **Без:** auto enqueue, scheduler, headless crawler, distributed crawl

---

## 2026-05-17 — Stage 2F: operational hardening + E2E

- Admin entity links, pipeline summary, operational dashboard
- `/admin/failed-items`, publish readiness checker
- `docs/OPERATIONS.md`, `scripts/test_2f_e2e.py`
- Safe task skip / stale reset (non-destructive)

---

## 2026-05-17 — Stage 2G: crmflow24 publishing integration

- Migration 006: publish thresholds on projects, publish_run audit fields
- Payload `payload_version: article_v1`, validators, idempotency, force publish
- WebhookPublisher hardening (retry, redacted logs, draft_url parsing)
- crmflow24-draft-webhook target (env-driven endpoint, dry-run until ready)

---

## 2026-05-17 — Stage 2H: prompt management + quality scoring + editorial control

- Migration 007: `prompt_templates`, `prompt_versions`, `project_prompt_overrides`, `content_quality_scores`
- Seeded active prompts: `review_article_v1`, `rewrite_article_v1`, `seo_enrich_v1`, `quality_review_v1`
- `prompt_service` (DB active + project override + code fallback); `llm_runs.prompt_template` = `key:version`
- `quality_service` manual review → JSON scores + verdict; does not mutate `rewritten_text`
- Publish readiness + publish validation: quality required when `ENABLE_QUALITY_REVIEW=true`; `force=true` bypass
- API: `/api/prompts`, `/api/documents/{id}/run-quality`, `/api/documents/{id}/quality-scores`
- Admin: `/admin/prompts`, `/admin/quality-scores`, `/admin/editorial-queue`, quality block on document detail
- Env: `ENABLE_QUALITY_REVIEW`, `QUALITY_MODEL_ALIAS`, `MIN_QUALITY_SCORE_FOR_PUBLISH`
- Pipeline stage `quality_review` defined; automatic stage not enabled in worker (manual-first)

---

## 2026-05-17 — Stage 2I: editorial states + revisions + operator approval

- Migration 008: editorial fields on `parsed_documents`, `document_revisions`, `publish_runs.document_revision_id`
- `revision_service` immutable snapshots on rewrite/SEO/quality rerun
- `editorial_service` state machine (approve/reject/needs_revision/operator_review/ready_to_publish)
- Publish gated by `approved_for_publish` + editorial status; `force=true` bypass
- Admin: editorial controls, timeline, `/admin/documents/{id}/revisions`, grouped editorial queue
- API: `/api/documents/{id}/editorial/*`, `GET /api/documents/{id}/revisions`
- `ENABLE_EDITORIAL_WORKFLOW` feature flag

---

## 2026-05-17 — Stage 3A: Hermes optional orchestration layer

- `app/hermes/` HTTP connector (client, health, routing, adapters, schemas)
- Migration 009: `hermes_runs` audit table
- Optional tasks: research_summary, rewrite_critique, campaign_ideas (service)
- Readiness: Hermes check only when `ENABLE_HERMES=true` (degraded if down)
- API: `/api/hermes/health`, `/api/hermes/runs`, document research/critique
- Admin: `/admin/hermes`, document Hermes actions
- Contract: `POST {HERMES_BASE_URL}/v1/orchestrate`; fallback to CLIProxy when endpoint missing
- Discovered Hermes health: `http://127.0.0.1:8000/health`

## 2026-05-17 — Этап 3B: Media pipeline foundation

- Таблицы `media_assets`, `media_jobs`; migration `010`
- Placeholder provider (SVG preview), local storage `storage/media/YYYY/MM/DD/`
- `media_prompt_service` — LLM prompts via `llm_runs` (optional)
- Publish readiness: media warnings (`missing_preview_image`), не блокирует publish
- `article_v1` payload: блок `media.preview`
- Admin: `/admin/media`, `/admin/media-jobs`, блок Media на document detail
- API: generate-preview, approve/reject, list media/jobs, file serve
- Flags: `ENABLE_MEDIA_PIPELINE=true`, `ENABLE_MEDIA_GENERATION=false`, `MEDIA_PROVIDER=placeholder`

## 2026-05-17 — Этап 3C: Production hardening

- Cleanup tmp deploy scripts from repo
- Backup/restore scripts + `storage/system_backups/` manifests
- Smoke framework `scripts/smoke/`
- `config_validator.py`, `/health/config`, extended `/health/ready`
- Admin `/admin/operations`
- Integrity: `check_storage_integrity.py`, `check_db_integrity.py`
- Docs: BACKUP_AND_RECOVERY, DEPLOYMENT_WORKFLOW, LOGGING

## 2026-05-17 — Этап 3D: Analytics & publication feedback

- `publication_records`, `analytics_snapshots`, `content_performance` (migration 011)
- Publication tracking after successful non-dry publish
- Manual analytics import API
- Deterministic performance score (v1 formula) and trends
- Editorial insights service (no LLM)
- Admin: `/admin/publications`, `/admin/analytics`

### 2026-05-17 — Stage 4A: scheduler + controlled automation

- Tables: automation_rules, automation_runs, scheduler_state (migration 012)
- scrap-scheduler systemd service, heartbeat in /health/ready
- Discovery, enqueue, pipeline_progression automations with audit
- Admin /admin/automation, /admin/automation-runs
- API automation + scheduler status
- Smoke check_scheduler.py

### 2026-05-17 — Stage 4B: async automation runs

- Non-blocking manual run API (queued runs)
- Scheduler processes queued runs with locks and progress
- Cancel, mark-failed, run detail admin, extended scheduler status
- Migration 013 lifecycle fields

### 2026-05-17 — Stage 4C: Cursor workflow guardrails

- CURSOR_WORKFLOW.md, hardened .gitignore
- check_repo_safety, check_git_integrity, pre/post deploy checks
- GET /api/system/workspace, /admin/system
- Workspace startup warnings, smoke integration

## 2026-05-17 ? Stage 4D: crmflow24 inbound integration

- `article_v2` payload + `validators_v2.py`; v1 backward compatible
- Payload negotiation via `publish_targets.payload_format`
- Mock receiver `/api/mock-crmflow24/*` (testing only)
- Publication acknowledgment: `external_article_id`, `draft_url`, `remote_status`, `response_schema_version`
- Retry semantics: `failed_retryable` / `failed_terminal`, `retry_count`, `next_retry_at`, retry chains
- `POST /api/publish-runs/{id}/retry`, `GET /api/publish-targets/health`
- Migration `014_publish_retry_chains`
- Admin: publish runs/targets show payload version, retry chain, health
- Docs: `CRMFLOW24_INTEGRATION.md`, API/ARCHITECTURE/OPERATIONS updates



## 2026-05-18 ? Stage 4E: campaign planning and topic clusters

- Models: `content_campaigns`, `topic_clusters`, link tables
- Services: `clustering_service`, `campaign_service` (coverage, duplicates, suggestions)
- API: campaigns/clusters CRUD, topic extraction, assign cluster/campaign, coverage, suggestions
- Admin: `/admin/campaigns`, `/admin/clusters`, document strategy block
- Automation hook: `campaign_analysis` (disabled)
- Smoke: `scripts/smoke/check_campaigns.py`

## 2026-05-18 ? Stage 4F: CRMFlow24 production target + topic extraction v2

- Production target `crmflow24-production-v2` ? `https://crmflow24.ru/api/scrap/articles/import`
- Env: `CRMFLOW24_PUBLISH_ENDPOINT`, `CRMFLOW24_PUBLISH_TOKEN`, aliases `SCRAP_CRMFLOW24_IMPORT_*`
- Health probe: OPTIONS/HEAD (no draft creation on health check)
- Topic extraction v2: `topic_quality_service`, relevance_score, rejected_terms, project_fit
- Admin: topic quality block on document detail
- Seed: `scripts/seed_crmflow24_production_v2_target.py`

## 2026-05-18 — Этап 4G: LLM topic cleanup + strategy quality gate

- `run_json_prompt` в `llm_tasks.py` (CLIProxy, audit `llm_runs`, robust JSON parse).
- Промпт `topic_cleanup_v1` (code fallback + `build_topic_cleanup_messages`).
- Оркестрация: `topic_extraction_service` — deterministic → optional LLM → `apply_strategy_gate`.
- Strategy gate: `strategy_allowed`, `strategy_block_reason`, `strategy_quality_score`, smoke/test detector.
- API: `POST /api/documents/{id}/extract-topics` body `use_llm_cleanup`; `GET .../strategy-readiness`.
- Coverage: `campaign_coverage` / `cluster_coverage` исключают blocked docs (`excluded_strategy_count`).
- Admin: strategy gate, LLM cleanup status, readiness, excluded count на campaign/cluster.
- Env: `ENABLE_LLM_TOPIC_CLEANUP`, `TOPIC_CLEANUP_MODEL_ALIAS`, `MIN_TOPIC_RELEVANCE_FOR_STRATEGY`.
- Reminder: smoke draft CRM https://crmflow24.ru/admin/posts/cmpats92t0006a2316na5xups — удалить вручную в CRM admin.
- Тест doc #7: `strategy_allowed=false`, `strategy_block_reason=smoke_test`.

## 2026-05-18 — Этап 4H: async LLM enrichment + timeout hardening

- Таблица `llm_enrichment_jobs` (миграция 016): queued/running/completed/failed_retryable/failed_terminal/cancelled/skipped.
- `extract-topics`: deterministic sync (<3s), LLM cleanup через очередь (`enrichment_job_id`).
- Scheduler + worker: отдельный tick enrichment (не блокирует automation/scraping).
- Granular timeouts: `TOPIC_CLEANUP_TIMEOUT_SECONDS=25`, SEO 60s, quality 90s.
- API: `/api/enrichment-jobs`, retry/cancel.
- Admin: `/admin/enrichment-jobs`, статус enrichment на document detail.
- CLIProxy degraded: API быстрый, jobs → failed_retryable, strategy/coverage без блокировки.

## 2026-05-18 — Этап 4I: reconcile async enrichment + editorial intelligence stabilization

- Architecture/docs reconciled: deterministic-first, optional async enrichment.
- `enrichment_merge_policy.py`, `strategy_topics_service.py` for campaign intelligence.
- Metrics service + `/admin/enrichment-dashboard`, `/api/enrichment-jobs/metrics`.
- Health `/ready` enrichment section (degraded, not full failure).
- Replay + lineage (`parent_enrichment_job_id`, `root_enrichment_job_id`, migration 017).
- Retention: `scripts/cleanup_enrichment_jobs.py` (dry-run default).
- State machine: failed_terminal after max retries; stale recovery hardened.
- `docs/MASTER_PLAN.md` created.

## 2026-05-18 — Этап 4J: source quality intelligence + discovery hardening

- `source_quality_scores`, `domain_trust_registry` (migration 018).
- Deterministic scoring: thin content, AI-noise heuristics, trust domains, duplicate risk.
- Discovery statuses: quality_pending/scored/blocked, manually_approved.
- `POST /api/discovered-urls/{id}/approve-quality`, score-quality.
- Enqueue quality gate; automation skips blocked URLs.
- Admin: `/admin/source-quality`, quality columns on discovered URLs.
- Health: `source_quality` section in `/health/ready`.

## 2026-05-18 — Этап 4K: canonical content intelligence

- Миграция `019`: `canonical_content_groups`, `document_similarity_links`, `rewrite_lineages`, `parsed_documents.canonical_group_id`.
- `document_similarity_service.py`: deterministic similarity (title/slug/keywords/topics/headings/rewrite), cannibalization warnings, rewrite lineage.
- API: `/api/documents/{id}/similarity`, `/lineage`, `POST .../analyze-similarity`; `/api/canonical-groups`.
- Admin: `/admin/canonical-groups`, блок similarity на document detail.
- Campaign coverage: `documents_unique`, `duplicate_adjusted_coverage`, `near_duplicate_pairs`.
- Enrichment type `similarity_analysis` (async deep analysis).
- Health `/health/ready`: секция `similarity`.
- Env: `SIMILARITY_*_THRESHOLD`, `ENABLE_SIMILARITY_ANALYSIS`.
