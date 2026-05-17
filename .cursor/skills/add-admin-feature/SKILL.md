# add-admin-feature

## Цель

Добавить страницу или действие в веб-админку.

## Шаги

1. Route в `app/admin/routes.py`.
2. Template в `app/admin/templates/`.
3. Ссылка в `base.html` nav при необходимости.
4. Стили в `app/admin/static/admin.css`.
5. Обновить `docs/ADMIN_UI.md`.
6. `docs/PROJECT_LOG.md`.

## Проверки

- Страница открывается без 500
- Формы POST работают
- Нет утечки секретов в HTML

## Лог

URL страницы, файлы, скриншот/описание UX.
