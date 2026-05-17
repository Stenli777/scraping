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
