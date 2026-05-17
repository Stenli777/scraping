# add-exporter

## Цель

Добавить формат экспорта или интеграцию (crmflow24).

## Шаги

1. Логика в `app/exporters/`.
2. API route в `app/api/documents.py` при HTTP export.
3. Запись в таблицу `exports` при сохранении файла.
4. Ссылка в admin document detail.
5. `docs/API.md`, `PROJECT_LOG.md`.

## Проверки

- Download возвращает корректный Content-Type
- Файл валидный JSON/MD

## Лог

export_type, endpoint, пример file_path.
