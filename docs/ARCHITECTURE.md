# Архитектура Scrap

## Обзор

Scrap — отдельный сервис в `/opt/scrap`. Hermes (`/hermes`) не используется на текущем этапе.

```
Admin UI (Jinja) ──┐
                   ├── FastAPI app ── API (/api/*)
Worker (poll DB) ──┘         │
                             ▼
                    PipelineService
         fetch → parse → clean → rewrite → save → backup
                             │
                    PostgreSQL + storage/backups
```

## Модули

| Каталог | Назначение |
|---------|------------|
| `app/api` | REST API |
| `app/admin` | Веб-админка |
| `app/core` | Конфиг, enums, логирование |
| `app/db`, `app/models` | SQLAlchemy |
| `app/parsers` | Scrapling + generic article |
| `app/rewriters` | mock / CLIProxy / LM Studio |
| `app/services` | pipeline, backup, tasks |
| `app/workers` | DB-polling worker |
| `app/exporters` | JSON/Markdown |
| `storage/` | backups, runtime logs |

## Расширение

- Новый парсер: `app/parsers/` + registry
- Новый rewriter: `app/rewriters/` + `REWRITER_PROVIDER`
- Очередь: заменить worker на ARQ/Celery без смены pipeline
- Экспорт в crmflow24.ru: webhook в `services/export_crmflow.py` (этап 2)
