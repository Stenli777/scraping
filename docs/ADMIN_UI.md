# Admin UI

Base: **https://scrap.crmflow24.ru/admin**

| URL | Страница |
|-----|----------|
| `/admin` | Dashboard — ID, URL, статус, парсер, документ |
| `/admin/tasks/new` | Добавить URL (парсер подбирается по домену) |
| `/admin/tasks/{id}` | Статус, парсер, тайминги, ошибки, логи с payload |
| `/admin/documents/{id}` | clean / rewritten / raw, metadata, export |
| `/admin/settings` | заглушка env |

На странице документа: parser_name, word_count, extraction_warnings, ссылки JSON/Markdown export.

Стили: `/static/admin.css`
