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

---

## 2026-05-19 — Admin UI audit + redesign plan (docs only)

- **Что изменено:** Аудит стека Scrap Admin (routes, templates, static); инвентаризация 49 GET + 44 POST admin routes; план поэтапного визуального редизайна (sidebar, UI kit, русификация, help-блоки). Код не менялся.
- **Файлы:** `docs/admin-ui-redesign-plan.md`, `docs/admin-ui-routes-inventory.md`
- **Команды:** `ssh hermes` — `rg '@router.(get|post)' app/admin`, `curl` GET smoke на `/admin`, `/admin/tasks/new`, `/admin/discovered-urls`, `/admin/editorial-queue`; `scripts/smoke/check_health.py`
- **Результат:** GET smoke 200 на ключевых страницах; health PASS. Маршрут `/admin/editorial` не существует (использовать `/admin/editorial-queue`). Routes без пункта меню: `manual-urls`, `release-candidates`, `canonical-groups`.
- **Ошибки:** нет
- **Следующий шаг:** Этап 1 — sidebar в `base.html` + `admin.css`, smoke checklist из redesign plan

---

## 2026-05-19 08:20 UTC — Admin UI Этап 1: sidebar layout

- **Ветка:** `admin-ui-sidebar-stage-1`
- **Что изменено:** Горизонтальный topbar заменён на левый vertical sidebar (9 групп, pipeline-first). Active link по `request.url.path`. Добавлены ранее отсутствующие пункты: `manual-urls`, `release-candidates`, `canonical-groups`. Responsive: sidebar сверху на ≤900px. Backend/routes/forms не менялись.
- **Файлы:** `app/admin/templates/base.html`, `app/admin/static/admin.css`, `docs/admin-ui-redesign-plan.md`, `docs/PROJECT_LOG.md`
- **Команды:** `git checkout -b admin-ui-sidebar-stage-1`; curl GET `:8800/admin`, `/admin/tasks/new`, `/admin/discovered-urls`, `/admin/editorial-queue`; `scripts/smoke/check_health.py` PASS; `scripts/smoke/run_all.py` — FAIL только `git_clean`/`pre_deploy` (dirty tree); формы не изменены
- **Результат:** GET 200 на ключевых страницах; sidebar рендерится; form `action=/admin/tasks/new` без изменений; `/admin/editorial` не используется
- **Ошибки:** `run_all.py` git_clean — ожидаемо до commit
- **Следующий шаг:** Этап 2 — UI kit (кнопки, табы, таблицы, бейджи, table scroll wrappers)

---

## 2026-05-19 — Admin UI Stage 4 Batch 2: secondary templates i18n

- **Ветка:** `admin-ui-i18n-stage-4-batch-2`
- **Base commit:** `271ebfa` (merge Batch 1 в master)
- **Что изменено:** task_detail, _pipeline_summary, publications, draft_reviews_list, release_candidates_list — русские labels, page-header, table-scroll; точечный CSS
- **Файлы:** 5 templates, admin.css (append), PROJECT_LOG, admin-ui-redesign-plan.md
- **Forms сохранены:** task_detail POST mark-skipped, rerun-rewrite, run-review, run-seo — action/method/name без изменений
- **Команды:** smoke PASS; curl admin pages — 200
- **Следующий шаг:** merge Batch 2 или Batch 3

---

## 2026-05-19 — Admin UI Stage 4B bugfix: task detail NameError

- **Ветка:** `admin-ui-i18n-stage-4-batch-2`
- **Проблема:** GET `/admin/tasks/{id}` → 500, `NameError: strategy_context is not defined`
- **Исправление:** удалены неиспользуемые ключи из TemplateResponse context в `app/admin/routes.py`
- **Команды:** curl `/admin/tasks/17` → 200; smoke PASS; `systemctl restart scrap-api.service`

---

## 2026-05-19 — Admin UI Этап 4 Batch 3: route titles (display)

- **Ветка:** `admin-ui-i18n-stage-4-batch-3`
- **Base commit:** `43db0f5` (merge Batch 2 + Stage 4B)
- **Что изменено:** русские `title` в TemplateResponse context (`routes.py`, `manual_url_routes.py`)
- **Не тронуты:** document_detail, release_candidate_detail, publication detail
- **Merge:** `8f85c42` в master
- **Restart:** `systemctl restart scrap-api.service`

---

## 2026-05-19 — Admin UI Stage 4 Batch 4: high-risk templates audit-only

- **Ветка:** `admin-ui-high-risk-audit-stage-4-batch-4`
- **Base commit:** `8f85c42` (merge Batch 3 route titles)
- **Что изменено:** audit-only для `document_detail.html` (618 строк) и `release_candidate_detail.html` (114 строк); план Batch 5; код/templates/CSS/backend **не менялись**
- **Файлы:** `docs/admin-ui-high-risk-audit.md` (новый), `docs/PROJECT_LOG.md`, `docs/admin-ui-redesign-plan.md`
- **Команды:**
  - `git branch --show-current` → `admin-ui-high-risk-audit-stage-4-batch-4`, clean
  - `wc -l`, `grep` forms/actions в обоих templates
  - `.venv/bin/python scripts/smoke/check_health.py` PASS
  - `.venv/bin/python scripts/smoke/check_admin_discovered.py` PASS
  - `.venv/bin/python scripts/smoke/check_admin_task_detail.py` PASS
  - `.venv/bin/python scripts/smoke/run_all.py` PASS
  - curl `:8800/admin`, `/admin/tasks/17`, `/admin/editorial-queue`, `/admin/release-candidates`, `/admin/release-candidates/9` → 200
  - curl `/admin/documents/13` → **500** (pre-existing)
- **Аудит:** 25 `<form>` в document_detail (дубликаты Media/Hermes); 12 forms в RC detail; секции RC/Canonical **после** `{% endblock %}` (стр. 534); GET document detail 500 — `AttributeError` в `enrichment_service.job_to_dict` при `job is None`
- **Smoke IDs:** document **13** (500), release candidate **9** (200), task **17** (200)
- **Ошибки:** document detail 500 — pre-existing backend, не регрессия Batch 4
- **Следующий шаг:** Batch 5 display-only русификация по `docs/admin-ui-high-risk-audit.md`; предварительно — fix document detail 500 + structural template fixes (endblock/duplicates) отдельным bugfix

---

## 2026-05-19 — Admin UI Stage 4C: document detail backend fix

- **Ветка:** `admin-ui-document-detail-fix-stage-4b`
- **Base commit:** `17a40ea` (merge Batch 4 audit)
- **Проблема:** GET `/admin/documents/{id}` → 500
- **Root cause:** `document_strategy_context` вызывал `job_to_dict(latest_enrichment_for_document(...))`, когда enrichment job отсутствует (`None`); `job_to_dict` обращался к `job.started_at` без guard
- **Исправление (backend):** `enrichment_service.job_to_dict(None)` → `None`; import `get_document_pilot_membership` в `routes.py`; в context добавлены `similarity_summary`, `lineage_summary`, `release_candidates` (вычислялись, но не передавались)
- **Исправление (template syntax hotfix):** `document_detail.html` — закрыт `grid-meta`, удалены дублирующие orphan-блоки analytics/Hermes (без изменения `action`/`method`/`name`/`value`); иначе Jinja `TemplateSyntaxError` / `UndefinedError`
- **Файлы:** `enrichment_service.py`, `routes.py`, `document_detail.html` (syntax only), smoke, docs
- **Не менялось:** `release_candidate_detail.html`, CSS, route paths, form attributes
- **Smoke ID:** document **13** (и любой существующий id из БД)
- **Restart:** `systemctl restart scrap-api.service` (если uvicorn держал старый код)
- **Следующий шаг:** merge Stage 4C → master; финальный Batch 5 high-risk display-only polish

---

## 2026-05-19 — Admin UI Batch 5: high-risk detail pages display-only polish

- **Ветка:** `admin-ui-final-high-risk-polish-stage-5`
- **Base commit:** `7c51b6d` (merge Stage 4C document detail fix)
- **Что изменено:** display-only русификация `document_detail.html`, `release_candidate_detail.html`; help-блоки; секции RC/Canonical перенесены внутрь `{% block content %}` (structural, без изменения forms)
- **Файлы:** `document_detail.html`, `release_candidate_detail.html`, docs
- **Не менялось:** routes, services, models, CSS (не требовался), `action`/`method`/`name`/`value` форм
- **Команды:** smoke PASS; curl `/admin/documents/13`, `/admin/release-candidates/9` → 200
- **Restart:** не потребовался (только templates)
- **Следующий шаг:** merge Batch 5 в master; финальный manual browser check; закрытие UI/UX-задачи

---

## 2026-05-19 — Admin UI: visual polish track closed (Batch 5 merged)

- **Merge:** Batch 5 `admin-ui-final-high-risk-polish-stage-5` → `master`
- **Smoke/curl:** PASS после merge (`/admin/documents/13`, `/admin/release-candidates/9`, task 17)
- **Статус:** UI/UX admin visual polish **завершён**
- **Known technical debt (не блокирует):** дубликат панели Media на document detail; raw enum/status в `<code>`; смещение колонок publish history table

---

## 2026-05-19 — Admin UI: detail operator clarity (`admin-ui-detail-operator-clarity`)

- **Ветка:** `admin-ui-detail-operator-clarity`
- **Base commit:** `b150174` (master, visual polish closed)
- **Цель:** операторская понятность двух high-risk detail pages без изменения backend/forms
- **Шаблоны:** `document_detail.html`, `release_candidate_detail.html`
- **CSS:** минимальные классы (operator-summary, blocker-list, debug-details, danger-zone, code-block, scroll-x, …)
- **Smoke:** `check_admin_document_detail.py` — HTTP 200 + markers; новый `check_admin_release_candidate_detail.py`; оба в `run_all.py`
- **Markers document:** «Операторская сводка»/«Что сейчас», «Следующий шаг», «Блокировки публикации», «Релиз-кандидаты»
- **Markers RC:** «Что сейчас», «Следующий шаг», «Блокирующие проблемы», «Проверка черновика»; убран дубль h1 (title только в layout)
- **Не менялось:** routes, services, models, migrations, `action`/`method`/`name`/`value` форм, enum/status в БД
- **Media duplicate:** вторая панель свёрнута в `<details>` legacy (формы сохранены)
- **Проверки:** smoke detail PASS; curl 200 (doc 13, RC 9, task 17); marker grep PASS

---

## 2026-05-19 — Admin UI: i18n workflow pages (display-only)

- **Ветка:** `admin-ui-i18n-workflow-pages` (от `ad611b4`)
- **Scope:** переводы и help/next-step на task_new, source_directories, discovered_urls, editorial_queue, release_candidates_list, publications, publication_detail, review_queue; правки document_detail/RC detail (display)
- **Не менялось:** routes, services, models, form action/method/name/value
- **Словарь:** `docs/admin-ui-i18n-workflow-pages.md`
- **Smoke:** run_all.py PASS; ветка origin/admin-ui-i18n-workflow-pages

## 2026-05-19 — Admin UI: hybrid operator workflow sidebar + onboarding

- **Ветка:** `admin-ui-sidebar-workflow-hybrid` (от `ad611b4` master)
- **Почему не merge `admin-ui-operator-workflow` as-is:** ветка на `b150174`, без detail clarity; блок «Служебное» ~20 ссылок; конфликты base.html/admin.css
- **Взято из `203248a` (идеи):** pipeline groups 1–4, dashboard «С чего начать», next-step на 6 страницах, CSS workflow
- **Гибрид sidebar:** 9 групп (Обзор, 1–4, Диагностика, Качество и медиа, LLM, Организация/справка); 40 nav_link; href без изменений
- **Не менялось:** routes, services, models, workers, API; form attributes; detail operator clarity
- **Docs:** docs/admin-operator-workflow.md
- **Следующий шаг:** browser QA; merge в master после ручной проверки
---

## 2026-05-19 — Admin UI: integrated workflow (i18n + hybrid sidebar)

- **Merge:** dmin-ui-i18n-workflow-pages → master, затем dmin-ui-sidebar-workflow-hybrid → master (--no-ff)
- **Конфликты:** publications.html,
elease_candidates_list.html, PROJECT_LOG.md — объединены help (i18n) + next-step (hybrid), русский next-step на RC list
- **Не менялось:** routes, services, models, workers, API; form action/method/name/value
- **Smoke:** run_all.py PASS после обоих merge

---

## 2026-05-19 — Этап 4W: reconciliation, Autobit24 audit, CLIProxy stabilization

### UI/UX reconciliation
- **master** @ `6e92b6f`+ (после 4V `9bdfe93`): UI/UX треки **влиты в master** (i18n workflow pages, hybrid sidebar, detail operator clarity, integrated merge `5bebf81`).
- Незакоммиченных UI-файлов нет; отдельная ветка `admin-ui-sidebar-stage-1` (docs-only) не в production.
- Admin smoke: ключевые страницы **200**; `/admin/tasks` и `/admin/documents` — **404** (нет list-route, ожидаемо; детали `/admin/tasks/{id}` работают).

### Autobit24 source (id=4, autobit24-blog)
- `allow_patterns`: `/blog/`; `block_patterns`: category/tag/author/…; **enabled**.
- Discovery: 8 article URLs enqueued (tasks 14–17), 8 category URLs **blocked**.
- **Parser:** `generic_article` достаточен (clean_text 38–46k); специализированный `autobit24_article` **не добавлялся**.
- **Task 14 / doc #10:** rewrite падал на **400** (слишком длинный prompt ~24k chars) → fix truncation 12k; rewrite OK; quality **approved** (85).
- **Task 15 / doc #11, 17 / doc #13:** done, rewrite есть; review/quality — вручную по необходимости.
- **Task 16:** ошибка parse/meta `NoneType.strip` → fix `meta_content`; re-queued → worker.

### CLIProxy errors
- **429:** `RateLimitError`, exponential backoff 5/10/20s (cap 60s), retryable.
- **400:** `BadRequestError`; rewrite input **truncate 12000** chars + log `input_truncated`.
- Review уже ограничен 12k.

### Publish runs historical
- **#17** `crmflow24-mock-v2`: failed_retryable, `CRMFLOW24_PUBLISH_TOKEN` not set — **historical** (до env).
- **#23** `crmflow24-test-bad-token`: target **disabled**, `SCRAP_BAD_TOKEN_PLACEHOLDER` — **test**, badge `test target` / `historical env` в admin.

### Pilot
- **2/5**; doc **#5** `next_action` → **publish_draft** (RC #8 approved; soft quality blocker игнорируется при RC approved).
- Autobit docs **не в pilot** (нет RC / strategy / operator sign-off).

### Код (коммиты 4W)
- `app/llm/exceptions.py`, `client.py` — 429/400 classification + cooldown
- `app/services/llm_tasks.py` — rewrite truncation
- `app/services/pilot_service.py` — RC approved → skip quality next_action
- `app/services/publish_failure_labels.py`, admin badges
- `app/parsers/utils.py` — safe meta_content

### Не делали
- auto/public publish, wide crawl, CRMFlow24/Hermes/cliproxyapi changes, autobit24_article parser, pilot fill «любой ценой».

### Следующие ручные шаги
1. Doc #4 — public publish в CRMFlow24 → check-public-status.
2. Doc #5 — publish_draft по решению оператора (RC approved).
3. Autobit #11/#13 — review + quality; при готовности — RC + pilot review.
4. Doc #10 — strategy/topics/RC перед pilot.

---

## 2026-05-19 — Этап 4X: Projects + Agents (prompt overrides) + RU admin

- **Agent** = UI-абстракция над `prompt_templates` (ключи не менялись).
- Админка: `/admin/projects` (список, создание, редактирование), `/admin/agents`, `/admin/projects/{id}/agents`.
- Backward compat: `/admin/prompts` → redirect `/admin/agents`; POST версий на `/admin/prompts/{key}/versions`.
- API: `GET /api/projects/{id}/agents/{key}/effective-prompt`, smoke/disable override.
- Migration **024**: `projects.description`.
- `prompt_service`: source `global` | `project_override` | `code_fallback`.
- Скрипт: `scripts/check_project_agent_admin.py`.

---

## 2026-05-19 — Этап 4Y: CRMFlow24 agent overrides + LLM proof

### Профиль проекта id=1 (crmflow24)
- Заполнены tone, audience, content/rewrite/seo/review rules, allowed/blocked topics (через admin service).

### Project overrides (version `p1-crmflow24-v1`)
| Agent key | Override |
|-----------|----------|
| review_article | да |
| rewrite_article | да |
| seo_enrich | да |
| quality_review | да |
| topic_cleanup_v1 | global/code_fallback (без override) |

### Effective prompt API
Все 4 ключа: `source=project_override`, system начинается с «Ты Агент-… для проекта CRMFlow24».

### LLM proof
- Документ **#5** (pilot, RC approved), действие: `run_quality_for_document`.
- **llm_run #78**: `quality_review:p1-crmflow24-v1#project_override`, `project_id=1`, model `local/qc-reviewer`, success.
- До override: quality score **82** (needs_revision), рекомендации общие.
- После override: score **6** (needs_revision), рекомендации про бизнес-ценность CRMFlow24 — видно, что промпт применился.

### Pilot
- Doc #5: `next_action=publish_draft` (RC approved).
- Кандидаты: doc #10 score 100, Autobit #11/#13.

### Код
- `prompt_service.template_ref` → `{key}:{version}#{source}` для аудита в `llm_runs`.

### Скрипт настройки (ops)
- `/tmp/4y_setup.py` на сервере (повторяемый сид профиля+override).


## 2026-05-19 — этап 4Z

- UX: редактор агента проекта (textarea, русские кнопки, nav top/bottom).
- Fix:  prompts UTF-8 (убраны  в admin preview).
- Feat: , .
- Compact: форма  (form-row).
- CSS: , , , .
-  — body checks + новые URL.

## 2026-05-19 — этап 4Z

- UX: редактор агента проекта (textarea, русские кнопки, nav top/bottom).
- Fix: topic_cleanup_v1 prompts UTF-8.
- Feat: project tasks/documents admin pages.
- Compact project edit form + inner scroll CSS.
- check_project_agent_admin.py расширен.
