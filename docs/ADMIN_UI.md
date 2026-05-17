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
| `/admin/projects` | Проекты (multiproject foundation) |

На странице **задачи** и **документа**: блок Rewrite metadata — provider, model_alias, upstream_model, fallback_used, ссылка на llm_run; кнопка **Rerun rewrite**.

На странице документа: parser_name, word_count, extraction_warnings, ссылки JSON/Markdown export.

Стили: `/static/admin.css`
