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

OpenAPI: `/docs`
