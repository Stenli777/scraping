# add-db-migration

## Цель

Изменить схему PostgreSQL безопасно.

## Шаги

1. Изменить модели в `app/models/`.
2. `alembic revision --autogenerate -m "описание"`.
3. Проверить сгенерированный файл в `alembic/versions/`.
4. `alembic upgrade head` на сервере.
5. Обновить `docs/DATABASE.md`.
6. `docs/PROJECT_LOG.md`.

## Проверки

- upgrade/downgrade осмысленны
- API и pipeline не ломаются
- нет потери данных на prod без backup

## Лог

revision id, таблицы, команды alembic.
