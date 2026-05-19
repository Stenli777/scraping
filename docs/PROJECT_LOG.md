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

## 2026-05-18 — Этап 4L: release candidate QA pack

- Migration `020`: `content_release_candidates`, `publish_runs.release_candidate_id`.
- `release_candidate_service.py`: deterministic QA checklist, qa_score, approve/reject, publish-draft (approved only).
- API + admin `/admin/release-candidates`, document detail block, editorial queue RC columns.
- Smoke/test documents blocked in QA; missing media = warning only.
- Preferred production flow: create RC → run QA → approve → publish draft (no auto-publish).

## 2026-05-18 — Этап 4M: первый production release run

- Восстановлен SEO doc #8 (`POST /api/documents/8/run-seo`).
- Production-like выпуск doc #4 через RC #5 → publish_run #25 (`crmflow24-production-v2`, `article_v2`, draft).
- `docs/RELEASE_RUNBOOK.md`, `scripts/test_4m_release_run.py`.
- QA/publish: `needs_revision` при overall_score ≥ порога допускается для operator release.
- Rewriter временно `cliproxy` для doc #4 (без mock-маркера в тексте).

## 2026-05-18 — Этап 4N: CRMFlow24 draft review feedback loop

- Миграция `021`: таблица `draft_review_feedback`, поля `draft_review_status` / `draft_reviewed_at` на `content_release_candidates` и `publication_records`, `final_operator_notes`.
- Сервис `draft_feedback_service.py`: create/update/mark_*, public visibility check (GET `/blog`, `/sitemap.xml`, `/rss.xml`), pipeline events `stage=draft_feedback`.
- API: `POST/GET /api/release-candidates/{id}/draft-feedback`, `POST/GET /api/publications/{id}/draft-feedback`, `POST /api/publications/{id}/check-public-visibility`.
- Admin: панель **CRMFlow24 Draft Review** на release candidate detail, очередь `/admin/draft-reviews`.
- Smoke: publication #7 / candidate #5 — accepted, needs_edits, rejected, visibility not public.
- Граница: Scrap не публикует публично и не меняет CRMFlow24; feedback только вручную в Scrap.

## 2026-05-18 — Этап 4O: workspace cleanup + release ops checkpoint

- Удалены временные debug scripts (`inspect_doc4`, `list_all_docs`, `pick_release_doc`).
- Закоммичены `find_safe_doc.py`, `run_4m_ops.py` с safety headers.
- `scripts/check_release_state.py` — read-only release/draft consistency (PASS/WARN/FAIL).
- `docs/SCRIPTS.md` — inventory scripts.
- `/admin/operations` — блок Release Operations.
- Post-draft review checklist в RELEASE_RUNBOOK.

## 2026-05-18 — Этап 4P: smoke repair + publish target isolation

- Root cause smoke FAIL: mock `/api/mock-crmflow24/articles/import` used `CRMFLOW24_PUBLISH_TOKEN` → HTTP 401 without Bearer.
- Fix: mock auth isolated (`MOCK_CRMFLOW24_PUBLISH_TOKEN` only; open if unset).
- `publish_target_safety_service.py`: mock/test/production classes + validation.
- Smoke default skips production; `--include-production` for safe production probe script.
- Disabled `crmflow24-test-bad-token` target.

## 2026-05-18 — этап 4Q
- **Что изменено:** post-publication confirmation (visibility check, manual confirm, analytics_ready), migration 022, admin + script.
- **Файлы:** migration 022, publication_confirmation_service, publication_confirmation API, admin templates, check_public_publication.py.
- **Команды:** alembic upgrade head; systemctl restart scrap-api; scripts/check_public_publication.py --publication-id 7.
- **Результат:** publication #7 check → not_public (post not public in CRMFlow24 yet); confirm-public idempotent with force; smoke PASS after commit.
- **Граница:** Scrap не публикует public; только GET blog/sitemap/rss + фиксация в PublicationRecord.
- **Следующий шаг:** оператор публикует в CRMFlow24 admin → check → confirm-public → analytics_ready.
- **4R:** analytics ready queue, manual metrics import UI, validation, pipeline audit, performance history, insight labels, import script.
- **4S:** production pilot dashboard (crmflow24-first-5), candidate scoring, next_action engine, check_pilot_state.py.
## 2026-05-18 16:54 UTC — этап 4T (first 5 pilot execution)

- **Pilot:** `crmflow24-first-5` (#1), active, target 5, **items: 1/5** (только doc #4).
- **Почему <5:** `find_safe_doc.py` нашёл **один** non-test документ с rewrite+SEO+review take; остальные — smoke/test или не проходят strategy/quality gate. Нужен discovery + pipeline для ещё 4 статей.
- **Doc #4:** RC #6 approved (QA 79), publish_run #25 success, publication #7, draft_url CRMFlow24 admin, draft_review **accepted**, public **not_public**.
- **Исправлено:** `compute_next_action` — при существующем CRMFlow24 draft не возвращать `run_quality`/`fix_blockers`; next_action → `manual_publish_in_crmflow24`, status `draft_reviewed`.
- **Blockers (информационные):** quality/editorial verdict `needs_revision` в scoring; оператор может rerun quality / approve editorial или оставить как есть — draft уже в CRMFlow24.
- **Скрипт:** `scripts/run_pilot_first5_check.py` (--refresh, --json).
- **Вручную в CRMFlow24:** опубликовать пост публично → в Scrap check-public-status → confirm-public → import metrics.
- **Не делали:** public publish из Scrap, auto-add всех документов, повторный publish draft #4.
## 2026-05-18 18:12 UTC — этап 4U (trusted source expansion + pilot fill)

- **Discovery:** saltpro (#1), sotbit (#2), habr (#3) — max 12 URL/run; **+1** новый URL (habr/otus/1034388).
- **Enqueued:** discovered #9 → task #13 (OTUS structured logging).
- **Pipeline:** doc #5 (Bitrix24 chat-bot, habr/bitrix) — review take, cliproxy rewrite, SEO, quality 82; doc #7 excluded (ONEMIX off-topic); doc #9 excluded (review reject, logging).
- **Pilot crmflow24-first-5:** **2/5** items — doc #4 (draft в CRMFlow24), doc #5 (RC #8 qa_failed — editorial needs_revision).
- **Исключено:** doc #8 thin rewrite (452 chars) — убран из pilot; test URLs; spam/example; quality_blocked discovery rows.
- **Fix:** `detect_test_document` — `debug`/`mock` только в title/slug; pilot relevance exception при review take + CRM topic + rel≥50; `find_safe_doc` расширен.
- **До 5/5:** нужны ещё 3 сильных статьи (discovery даёт мало article URL — много blocked /tag /users).
## 2026-05-19 07:28 UTC — этап 4V (autobit24 + manual URL intake)

- **Source:** `autobit24-blog` (#4) `https://autobit24.ru/blog/`, trust autobit24.ru score 70.
- **Discovery:** 8 new article URLs, 12 blocked (category/listing), 4 enqueued (tasks 14–17).
- **Manual intake:** API `POST /api/manual-urls`, `/api/manual-urls/bulk`; admin `/admin/manual-urls`; script `scripts/intake_urls.py`.
- **Article classifier:** `article_url_classifier.py` — autobit24 `/blog/<slug>` high likelihood; categories blocked.
- **Doc #5:** editorial → ready_to_publish; RC #8 **qa_passed** (score 79).
- **Pilot:** 2/5 stable (#4 draft CRMFlow24, #5 RC qa_passed); autobit pipeline in progress (LLM queue).
- **Excluded:** autobit categories, monitor-crm transfer (quality_blocked), thin/off-topic from 4U.

---

## 2026-05-19 — Admin UI audit + redesign plan (docs only)

- **Что изменено:** Аудит стека Scrap Admin (routes, templates, static); инвентаризация 49 GET + 44 POST admin routes; план поэтапного визуального редизайна (sidebar, UI kit, русификация, help-блоки). Код не менялся.
- **Файлы:** docs/admin-ui-redesign-plan.md, docs/admin-ui-routes-inventory.md
- **Команды:** rg admin routes, curl GET smoke, scripts/smoke/check_health.py
- **Результат:** health PASS. Editorial route: /admin/editorial-queue (не /admin/editorial). Routes без пункта меню: manual-urls, release-candidates, canonical-groups.
- **Ошибки:** нет
- **Следующий шаг:** Этап 1 — sidebar в base.html + admin.css

---

## 2026-05-19 08:20 UTC — Admin UI Этап 1: sidebar layout

- **Ветка:** admin-ui-sidebar-stage-1
- **Что изменено:** Горизонтальный topbar заменён на левый vertical sidebar (9 групп, pipeline-first). Active link по request.url.path. Добавлены пункты manual-urls, release-candidates, canonical-groups. Responsive sidebar на <=900px. Backend/routes/forms не менялись.
- **Файлы:** app/admin/templates/base.html, app/admin/static/admin.css, docs/admin-ui-redesign-plan.md, docs/PROJECT_LOG.md
- **Команды:** curl GET :8800/admin, /admin/tasks/new, /admin/discovered-urls, /admin/editorial-queue; check_health PASS; run_all FAIL только git_clean (dirty tree)
- **Результат:** GET 200; sidebar рендерится; form action=/admin/tasks/new без изменений
- **Ошибки:** run_all git_clean — ожидаемо до commit
- **Следующий шаг:** Этап 2 — UI kit (кнопки, табы, таблицы, бейджи)

---

## 2026-05-19 08:32 UTC — Admin UI Этап 1: финализация docs + smoke

- **Ветка:** admin-ui-sidebar-stage-1
- **Commits:** f69e118 (sidebar layout), 47e6024 (docs inventory + ADMIN_UI links)
- **Что изменено:** Закрыты docs-хвосты этапа 1; обновлена дорожная карта 8 этапов в admin-ui-redesign-plan.md; порт 8800 зафиксирован в документации
- **Файлы:** docs/ADMIN_UI.md, docs/admin-ui-routes-inventory.md, docs/admin-ui-redesign-plan.md, docs/PROJECT_LOG.md
- **Команды:** check_health PASS; run_all PASS (all smoke checks, git clean); curl GET :8800/admin, /tasks/new, /discovered-urls, /editorial-queue — 200
- **Результат:** git tree clean; формы/action URLs не менялись; /admin/editorial не используется
- **Ошибки:** нет
- **Следующий шаг:** merge admin-ui-sidebar-stage-1 в master после ручной визуальной проверки; затем Этап 2 (ветка admin-ui-kit-stage-2)

---

## 2026-05-19 — Admin UI Этап 2: base UI kit styles

- **Ветка:** admin-ui-kit-stage-2
- **Base commit:** eebb951 (merge sidebar stage 1)
- **Что изменено:** UI kit в admin.css (scrollbar sidebar, кнопки, табы, таблицы, бейджи, panel/help-block заготовки, main area typography); частичная русификация labels в base.html; child templates/routes/forms не менялись
- **Файлы:** app/admin/static/admin.css, app/admin/templates/base.html, docs/PROJECT_LOG.md, docs/admin-ui-redesign-plan.md
- **Команды:** check_health PASS; run_all PASS; curl GET :8800/admin, /tasks/new, /discovered-urls, /editorial-queue, /source-quality — 200
- **Результат:** forms/action/method/name без изменений; /admin/editorial не используется
- **Ошибки:** нет
- **Следующий шаг:** Этап 3 — применить UI kit к P0 страницам (task_new, discovered_urls, editorial_queue + partial)

---

## 2026-05-19 — Admin UI Этап 3: P0 pages polish

- **Ветка:** admin-ui-p0-pages-stage-3
- **Base commit:** f87e5c9 (merge UI kit stage 2)
- **Что изменено:** UI kit применён к P0: task_new, discovered_urls, editorial_queue, _editorial_queue_table; help-блоки, tabs фильтров, table-scroll, русские labels колонок/кнопок; точечный CSS (form-grid, section-stack, action-cell)
- **Файлы:** 4 templates, admin.css, PROJECT_LOG, admin-ui-redesign-plan.md
- **Forms сохранены:** action=/admin/tasks/new method=post name=source_url name=parser_type; discovered POST enqueue/approve-quality/ignore; editorial POST RC/QC — без изменений URL/method/name
- **Команды:** check_health PASS; run_all PASS; curl GET :8800 P0 pages — 200
- **Ошибки:** нет
- **Следующий шаг:** Этап 4 — русификация display layer на P1 и остальных страницах

---

## 2026-05-19 — Admin UI Stage 3B: fix discovered-urls status filter

- **Ветка:** admin-ui-p0-pages-stage-3
- **Проблема:** GET `/admin/discovered-urls?status=...` возвращал 500 — `filter()` вызывался после `limit(200)` в SQLAlchemy
- **Исправление:** `app/admin/routes.py` — filter по status до order_by/limit
- **Smoke:** добавлен `scripts/smoke/check_admin_discovered.py` (discovered-urls + status=discovered/enqueued)
- **Команды:** curl GET status filters — 200; check_health PASS; run_all PASS
- **Следующий шаг:** merge admin-ui-p0-pages-stage-3 в master после ручной проверки tabs


---

## 2026-05-19 — Admin UI Этап 4 Batch 1: P1 safe pages i18n

- **Ветка:** admin-ui-i18n-stage-4
- **Base commit:** 5cb33cc (merge stage 3 + 3B в master)
- **Batch:** Stage 4 Batch 1 — display-only русификация safe P1 templates
- **Что изменено:** русские заголовки, колонки, кнопки, empty states, page-header/help-block на dashboard, failed_items, review_queue, source_directories, source_directory_detail, manual_urls; CSS .description-list, .page-title
- **Файлы:** 6 templates, admin.css (append), PROJECT_LOG, admin-ui-redesign-plan.md
- **Forms сохранены:** failed_items POST reset-stale, mark-skipped; source_directory_detail POST discover; manual_urls POST project_id, source_directory_id, urls_text, enqueue=value=true — action/method/name/value без изменений
- **Backend:** не менялся (title в routes остаётся EN — только template display layer)
- **Команды:** check_health PASS; check_admin_discovered PASS; run_all PASS; curl GET :8800 admin, tasks/new, discovered-urls, status filters, editorial-queue, failed-items, review-queue, source-directories, manual-urls — 200
- **Ошибки:** нет
- **Restart/deploy:** не требовался
- **Следующий шаг:** Stage 4 Batch 2 (task_detail, _pipeline_summary, publications, draft_reviews_list, release_candidates_list) или merge Batch 1 после ручной проверки


---

## 2026-05-19 — Admin UI Этап 4 Batch 2: secondary pages i18n

- **Ветка:** admin-ui-i18n-stage-4-batch-2
- **Base commit:** 271ebfa (merge Batch 1 в master)
- **Batch:** Stage 4 Batch 2 — display-only русификация secondary templates
- **Что изменено:** task_detail, _pipeline_summary, publications, draft_reviews_list, release_candidates_list — русские labels, page-header, table-scroll; точечный CSS (.log-block, .status-line); исправлен `</div>` в task_detail (был `</motion>`)
- **Файлы:** 5 templates, admin.css (append), PROJECT_LOG, admin-ui-redesign-plan.md
- **Forms сохранены:** task_detail POST mark-skipped, rerun-rewrite, run-review, run-seo — action/method/name без изменений
- **Backend:** не менялся
- **Команды:** check_health PASS; check_admin_discovered PASS; run_all PASS; curl :8800 admin, discovered, editorial, publications, draft-reviews, release-candidates, tasks/<id> — 200
- **Ошибки:** нет
- **Restart/deploy:** не требовался
- **Следующий шаг:** merge Batch 2 в master или Stage 4 Batch 3 (high-risk отложены)


---

## 2026-05-19 — Admin UI Stage 4B bugfix: task detail NameError

- **Ветка:** admin-ui-i18n-stage-4-batch-2
- **Проблема:** GET `/admin/tasks/{id}` → 500, `NameError: strategy_context is not defined` в `admin_task_detail`
- **Причина:** в context передавались `strategy_context`, `similarity_summary`, `lineage_summary`, `release_candidates` без присвоения (копипаст с document_detail); `task_detail.html` их не использует
- **Исправление:** удалены неиспользуемые ключи из TemplateResponse context
- **Файлы:** `app/admin/routes.py`, `scripts/smoke/check_admin_task_detail.py`, `run_all.py`, docs
- **Команды:** curl `/admin/tasks/17`, `/admin/tasks/1` → 200; smoke PASS
- **Restart:** `systemctl restart scrap-api.service` (uvicorn держал старый код до restart)
- **Следующий шаг:** merge Batch 2 + 4B в master
