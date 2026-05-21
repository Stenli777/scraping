# База данных

PostgreSQL / Supabase-compatible schema.

## Таблицы

- `sources` — уникальные URL источников
- `scraping_tasks` — задачи и статусы pipeline
- `parsed_documents` — результат парсинга; Phase A: `operator_touched`, `operator_touched_at`, `operator_touched_by`
- `publish_runs` — audit публикаций; Phase A: `force_reason` (с `force_used`)
- `projects` — Phase A: `trust_level` (int, default 0)
- `document_versions` — история версий текста
- `task_logs` — логи по задаче
- `exports` — записи экспорта (путь к файлу)

## Миграции

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Дедупликация

- `sources.source_url` — UNIQUE
- `parsed_documents.content_hash` + `source_url` — проверка в pipeline
