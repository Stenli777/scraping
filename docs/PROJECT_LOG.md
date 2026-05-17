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

## 2026-05-17 14:46 UTC — Stage 2A: multiproject foundation

### Pre-check
- pwd: /opt/scrap, branch master
- scrap-api, scrap-worker: active
- /health OK

### Git
- remote: git@github.com:Stenli777/scraping.git
- tag: baseline-pre-multiproject @ faf47d8
- commits: 13d8a43 chore hygiene, dd4af64 feat stage 2A
- push: failed (deploy key read-only)

### Delivered
- app/llm/ abstraction (client, schemas, routing, registry)
- tables: projects, source_directories, llm_runs, pipeline_events
- migration 002 applied
- pipeline_events on legacy status transitions
- /health/ready (db, worker, cliproxyapi)
- admin: Projects, LLM Runs, Pipeline Events, LLM Smoke
- feature flags ENABLE_HERMES=false etc.
- CLIProxy routing uses glm-4.5-air-free, gpt-oss-120b-free aliases

### Verification
- LLM smoke hermes-cheap: success, llm_run id=3
- pipeline_events: emitted on task #7
- project crmflow24 seeded id=1

### Next
- GitHub write access for push
- Wire REWRITER_PROVIDER=cliproxy in pipeline when ready
- Hermes orchestration (not runtime)