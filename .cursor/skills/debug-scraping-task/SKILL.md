# debug-scraping-task

## Цель

Диагностировать failed/stuck задачу scraping.

## Когда использовать

Статус `error`, пустой текст, timeout fetch.

## Шаги

1. `GET /api/tasks/{id}` или `/admin/tasks/{id}`.
2. Проверить `task_logs` и `storage/logs/app.log`.
3. Проверить backup dir `storage/backups/.../<task_id>/`.
4. Воспроизвести fetch: `app/parsers/fetcher.py` для URL.
5. При duplicate hash — сравнить `content_hash` в `parsed_documents`.
6. Исправить parser/fetcher; `POST /api/tasks/{id}/run`.
7. Запись в `docs/PROJECT_LOG.md`.

## Проверки

- Статус доходит до `done`
- `clean_text` не пустой
- backup файлы на месте

## Лог

task_id, URL, error_message, root cause, fix.
