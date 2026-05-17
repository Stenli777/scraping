# Admin UI

Base: **https://scrap.crmflow24.ru/admin**

| URL | Страница |
|-----|----------|
| `/admin` | Dashboard — ID, URL, статус, парсер, документ |
| `/admin/tasks/new` | Добавить URL (парсер подбирается по домену) |
| `/admin/tasks/{id}` | Статус, парсер, тайминги, ошибки, логи с payload |
| `/admin/documents/{id}` | clean / rewritten / raw, metadata, export |
| `/admin/settings` | env flags (без секретов) |
| `/admin/llm-runs` | Аудит LLM: task_id, project_id, alias, upstream, tokens, latency, success, fallback |
| `/admin/pipeline-events` | События pipeline по стадиям |
| `/admin/llm/smoke` | Ручной smoke test LLM |
| `/admin/projects` | Список проектов |
| `/admin/projects/{id}` | Профиль проекта (read-only): instructions, topics, tone |
| `/admin/review-queue` | Очередь review: take/reject, score, risks |
| `/admin/publish-targets` | Publish targets (read-only) |
| `/admin/publish-runs` | Аудит попыток публикации |
| `/admin/source-directories` | Список discovery sources |
| `/admin/source-directories/{id}` | Детали + Run discovery |
| `/admin/discovered-urls` | Очередь URL: Enqueue / Ignore (по одному) |
| `/admin/failed-items` | Failed tasks, LLM, publish + stale running |
| Dashboard | Operational metrics, recent failures, pipeline events |
| Task/Document detail | Pipeline Summary, entity links, publish readiness |

На странице **задачи** и **документа**: блок Rewrite metadata — provider, model_alias, upstream_model, fallback_used, ссылка на llm_run; кнопка **Rerun rewrite**.

На странице документа: parser_name, word_count, extraction_warnings, ссылки JSON/Markdown export.

Стили: `/static/admin.css`
