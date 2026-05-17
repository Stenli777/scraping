# API

Base: **https://scrap.crmflow24.ru**

| Method | Path | Описание |
|--------|------|----------|
| GET | `/health` | Healthcheck |
| POST | `/api/tasks` | Создать задачу `{ "source_url": "...", "parser_type": "generic_article" }` — parser опционален, auto по домену |
| GET | `/api/tasks` | Список задач |
| GET | `/api/tasks/{id}` | Детали задачи |
| POST | `/api/tasks/{id}/run` | Вернуть в очередь |
| GET | `/api/documents/{id}` | Документ |
| GET | `/api/documents/{id}/export/json` | JSON: title, metadata_json, raw/clean/rewritten |
| GET | `/api/documents/{id}/export/markdown` | Markdown: clean + rewritten + metadata |
| POST | `/api/documents/{id}/rerun-rewrite` | Повторить rewrite по `clean_text` (без повторного fetch) |
| POST | `/api/documents/{id}/run-review` | LLM review по `clean_text` → `review_results` |
| POST | `/api/documents/{id}/run-seo` | SEO enrich по rewritten/clean → `seo_metadata` |
| POST | `/api/documents/{id}/publish-draft` | Отправить draft на publish target `{ "publish_target_id", "dry_run" }` |
| GET | `/api/documents/{id}/publish-runs` | История publish_runs для документа |
| GET | `/api/publish-targets` | Список enabled publish targets |
| GET | `/api/source-directories` | Список source directories |
| POST | `/api/source-directories/{id}/discover` | Controlled discovery `{ "max_urls", "dry_run" }` |
| GET | `/api/discovered-urls` | Очередь URL (filters: project_id, source_directory_id, status) |
| POST | `/api/discovered-urls/{id}/enqueue` | Создать scraping task (manual) |
| POST | `/api/discovered-urls/{id}/ignore` | Игнорировать URL |
| GET | `/api/documents/{id}/publish-readiness` | Readiness + checks (review, SEO, quality, duplicate) |
| POST | `/api/documents/{id}/publish-draft` | Body: `publish_target_id`, `dry_run`, `force` (default false) |
| GET | `/api/prompts` | Список prompt templates + active version |
| GET | `/api/prompts/{key}` | Template + version history |
| POST | `/api/prompts/{key}/versions` | Создать версию `{ "version", "content_md", "notes", "activate" }` |
| POST | `/api/prompts/{key}/versions/{id}/activate` | Активировать версию |
| POST | `/api/documents/{id}/run-quality` | Quality review (rewritten + SEO) → `content_quality_scores` |
| GET | `/api/documents/{id}/quality-scores` | История quality scores |
| POST | `/api/documents/{id}/editorial/approve` | Operator approve → `approved`, `approved_for_publish=true` |
| POST | `/api/documents/{id}/editorial/reject` | Reject document |
| POST | `/api/documents/{id}/editorial/needs-revision` | Mark needs revision |
| POST | `/api/documents/{id}/editorial/operator-review` | Move to operator review |
| POST | `/api/documents/{id}/editorial/ready-to-publish` | Mark ready to publish (after approve) |
| GET | `/api/documents/{id}/revisions` | Immutable revision history |
| GET | `/api/llm/aliases` | Список model aliases (CLIProxy routing) |
| POST | `/api/llm/smoke` | Smoke test LLM `{ "model_alias", "content" }` |
| GET | `/api/llm/rewrite-config` | Текущий `REWRITER_PROVIDER` и aliases из env |
| GET | `/health/ready` | Readiness: DB, worker, CLIProxyAPI; Hermes optional (degraded if down) |
| GET | `/api/hermes/health` | Hermes connector health (when enabled) |
| GET | `/api/hermes/runs` | Audit list (`document_id` filter) |
| POST | `/api/documents/{id}/hermes/research` | Optional research summary |
| POST | `/api/documents/{id}/hermes/critique` | Optional rewrite critique |

## Rewrite API

`POST /api/documents/{id}/rerun-rewrite` — использует существующий `clean_text`, создаёт новый `llm_run`, обновляет `rewritten_text`, пишет `pipeline_event`, сохраняет backup.

Ответ: `success`, `provider`, `model_alias`, `upstream_model`, `fallback_used`, `llm_run_id`, `error_message`, `warnings`.

## Quality review

`POST /api/documents/{id}/run-quality` — только после rewrite + SEO; не меняет текст статьи.

При `ENABLE_QUALITY_REVIEW=false` → HTTP 503 с сообщением о disabled flag.

Ответ: `overall_score`, `verdict` (`approved` | `needs_revision` | `rejected`), `risks`, `recommendations`, `llm_run_id`.

## Publish readiness (quality)

При `ENABLE_QUALITY_REVIEW=true` в `missing` могут быть: `quality_score`, `quality_not_approved`, `quality_score_below_threshold`, `quality_spam_too_high`.

`force=true` на publish-draft обходит quality, editorial (и review/duplicate) — в `publish_runs.force_used=true`.

## Editorial workflow

При `ENABLE_EDITORIAL_WORKFLOW=true` publish требует `editorial_status` ∈ `approved|ready_to_publish` и `approved_for_publish=true`.

Rerun rewrite/SEO/quality создаёт новую запись в `document_revisions` (immutable).

`publish_runs` содержит `document_revision_id` и `revision_number` в API ответе.

OpenAPI: `/docs`
