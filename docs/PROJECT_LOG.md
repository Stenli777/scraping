# Project log (Cursor / ops)

Формат записи:

```
## YYYY-MM-DD HH:MM UTC
- **Что изменено:**
- **Файлы:**
- **Команды:**
- **Результат:**
- **Ошибки:**
- **Следующий шаг:**
```

---

## 2026-05-17 — Initial scaffold

- **Что изменено:** Создан production scaffold проекта Scrap в `/opt/scrap`: FastAPI, admin UI, модели БД, pipeline, worker, parsers, rewriters, backups, docs, Cursor rules/skills, deploy configs.
- **Файлы:** Полная структура `app/`, `docs/`, `.cursor/`, `alembic/`, `deploy/`, `storage/`, `scripts/`.
- **Команды:** (см. отчёт деплоя на сервере)
- **Результат:** MVP scaffold готов к миграции и запуску.
- **Ошибки:** —
- **Следующий шаг:** HTTPS certbot, тест 5 URL, интеграция crmflow24 export, CLIProxy rewriter.
