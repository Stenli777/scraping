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
| GET | `/api/llm/aliases` | Список model aliases (CLIProxy routing) |
| POST | `/api/llm/smoke` | Smoke test LLM `{ "model_alias", "content" }` |
| GET | `/api/llm/rewrite-config` | Текущий `REWRITER_PROVIDER` и aliases из env |
| GET | `/health/ready` | Readiness: DB, worker, CLIProxyAPI `/v1/models` |

## Rewrite API

`POST /api/documents/{id}/rerun-rewrite` — использует существующий `clean_text`, создаёт новый `llm_run`, обновляет `rewritten_text`, пишет `pipeline_event`, сохраняет backup.

Ответ: `success`, `provider`, `model_alias`, `upstream_model`, `fallback_used`, `llm_run_id`, `error_message`, `warnings`.

OpenAPI: `/docs`
