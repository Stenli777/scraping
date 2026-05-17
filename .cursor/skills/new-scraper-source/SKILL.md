# new-scraper-source

## Цель

Добавить новый тип парсера (источник/шаблон страницы).

## Когда использовать

Новый домен или шаблон (bitrix, habr, saltpro и т.д.).

## Шаги

1. Создать класс в `app/parsers/<name>.py`, наследник `BaseParser`.
2. Зарегистрировать в `app/parsers/registry.py`.
3. Добавить значение в `app/core/enums.py` → `ParserType`.
4. Обновить `docs/SCRAPING_PIPELINE.md`.
5. Добавить тестовый URL в admin или API.
6. Запись в `docs/PROJECT_LOG.md`.

## Файлы

- `app/parsers/*`
- `app/parsers/registry.py`
- `app/core/enums.py`
- `docs/SCRAPING_PIPELINE.md`

## Проверки

- `POST /api/tasks` с новым `parser_type`
- worker обрабатывает без error
- backup создан

## Лог

Зафиксировать parser_type, файлы, результат тестового URL.
