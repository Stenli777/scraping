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

## 2026-05-17 09:22 UTC — Initial scaffold + deploy on hermes

- **Что изменено:** Создан и развёрнут MVP Scrap в `/opt/scrap`.
- **Результат:** Task #1 saltpro URL → done, HTTP health ok.
- **Следующий шаг:** HTTPS, прогон 5 URL, domain parsers.

---

## 2026-05-17 09:40 UTC — HTTPS, domain parsers, 5 URL test run

### Предварительная проверка
- `git status`: modified `docs/PROJECT_LOG.md`
- `scrap-api`, `scrap-worker`: **active**
- `curl http://127.0.0.1:8800/health` → ok
- `curl http://scrap.crmflow24.ru/health` → ok

### HTTPS
- **Backup nginx:** `/root/backup-nginx-2026-05-17-0934/scrap.crmflow24.ru.conf`
- **Команда:** `certbot --nginx -d scrap.crmflow24.ru --non-interactive --agree-tos --redirect`
- **Сертификат:** `/etc/letsencrypt/live/scrap.crmflow24.ru/`, expires **2026-08-15**
- **Проверка:** `curl -s https://scrap.crmflow24.ru/health` → ok

### Прогон 5 URL

| # | URL | Task | Parser | Status | Doc |
|---|-----|------|--------|--------|-----|
| 1 | saltpro …kedo-reytinge… | 1 | generic_article | done | 1 |
| 1b | saltpro …kedo… (повтор) | 2 | saltpro_article | error→duplicate skip* | 1 |
| 2 | saltpro …vibecode… | 3 | saltpro_article | done | 2 |
| 3 | saltpro …nalogovaya… | 4 | saltpro_article | done | 3 |
| 4 | sotbit …nastroyka-crm… | 5 | sotbit_article | done | 4 |
| 5 | habr …1031736 | 6 | habr_article | done | 5 |

\*Повтор URL #1: контент уже в doc #1 (hash duplicate). После фикса pipeline — graceful skip.

### Качество парсинга (clean_text length / words)
- doc #2 saltpro vibecode: 5725 chars, 802 words
- doc #3 saltpro nalogovaya: 3119 chars, 426 words
- doc #4 sotbit: 11774 chars, 1490 words
- doc #5 habr: 22062 chars, 2938 words

### Изменённые файлы
- `app/parsers/utils.py`, `saltpro_article.py`, `sotbit_article.py`, `habr_article.py`
- `app/parsers/registry.py`, `generic_article.py`
- `app/services/pipeline.py`, `task_service.py`
- `app/exporters/json_markdown.py`
- `app/admin/templates/*`, `admin.css`
- `app/core/enums.py`
- `scripts/run_test_urls.py`, `validate_tasks.py`
- `docs/*`

### Команды
- `certbot --nginx -d scrap.crmflow24.ru ...`
- `scp` app/scripts/docs → hermes
- `python -m compileall app`
- `systemctl restart scrap-api scrap-worker`
- `python scripts/run_test_urls.py`
- `PYTHONPATH=/opt/scrap python scripts/validate_tasks.py`

### Следующий шаг
- GitHub remote + push
- CLIProxy rewriter
- CRMFlow24 export webhook
- Опционально: доработка habr raw_text noise

---

## 2026-05-17 — Stage 2B: production CLIProxy rewrite in main pipeline

- **Что изменено:** `run_rewrite_stage()` в pipeline; prompt `rewrite_article_v1`; `RewriteRequest`/`RewriteResponse`; rerun rewrite API/admin; `failed_retryable` status; admin rewrite metadata.
- **Файлы:** `app/services/rewrite_service.py`, `app/llm/prompts.py`, `app/services/pipeline.py`, `app/services/llm_tasks.py`, `app/api/rewrite.py`, admin templates, docs.
- **Production switch:** по умолчанию остаётся `REWRITER_PROVIDER=mock`; cliproxy включается явно через env.
- **Не сделано:** Hermes runtime, auto-publish, crawler, RAG, React/SPA.

---

## 2026-05-17 — Stage 2C: project profiles + review + SEO foundation

- **Миграция:** `003` — project profile fields, `review_results`, `seo_metadata`, seed crmflow24
- **Prompts:** `review_article_v1`, `seo_enrich_v1`
- **Pipeline:** optional review → rewrite → seo_enrich
- **Admin:** `/admin/projects/{id}`, `/admin/review-queue`, SEO на document/task
