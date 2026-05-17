# API

Base: `https://scrap.crmflow24.ru`

| Method | Path | Описание |
|--------|------|----------|
| GET | `/health` | Healthcheck |
| POST | `/api/tasks` | Создать задачу `{ "source_url": "...", "parser_type": "generic_article" }` |
| GET | `/api/tasks` | Список задач |
| GET | `/api/tasks/{id}` | Детали задачи |
| POST | `/api/tasks/{id}/run` | Вернуть в очередь (`queued`) |
| GET | `/api/documents/{id}` | Документ |
| GET | `/api/documents/{id}/export/json` | JSON export |
| GET | `/api/documents/{id}/export/markdown` | Markdown export |

OpenAPI: `/docs`
