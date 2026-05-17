# Scrap — Operations Guide

Руководство для ежедневной ручной работы с контентным конвейером. Без auto-enqueue, auto-publish и scheduler.

## Daily workflow

1. Открыть **Admin → Discovery** (`/admin/source-directories`)
2. Выбрать source directory → **Run discovery** (лимит по умолчанию 20 URL)
3. Открыть **Discovered URLs** (`/admin/discovered-urls`)
4. Просмотреть кандидатов → **Enqueue** по одному URL
5. Дождаться задачи: **Dashboard** или `/admin/tasks/{id}`
6. Открыть **Document** → проверить **Pipeline Summary** и **Review**
7. При необходимости **Rerun rewrite**
8. **Run SEO** если slug/метаданные пустые
9. Проверить **Publish readiness** → **Publish draft** / dry-run
10. Проверить **Publish runs** (`/admin/publish-runs`)

## End-to-end path (entity links)

```
Source Directory → Discovered URL → Task → Document → Review / SEO / Publish
```

В admin на каждой странице есть блок **Links** и **Pipeline Summary**.

## Publish readiness

API: `GET /api/documents/{id}/publish-readiness`

Проверяется:

- project привязан к задаче
- `rewritten_text` не пустой
- `seo_metadata` и `slug`
- `ENABLE_PUBLISHING=true`
- enabled publish target для проекта
- status только `draft`
- review take/score (project thresholds, default score ≥ 60)
- duplicate successful publish (нужен `force=true` для повтора)

Ответ включает `checks`: `review_take`, `review_score`, `seo_exists`, `duplicate_publish`, и т.д.

## Production publish (crmflow24)

1. Заполнить в `.env` (не коммитить):
   - `CRMFLOW24_PUBLISH_ENDPOINT` — URL draft API
   - `CRMFLOW24_PUBLISH_TOKEN` — bearer token
2. Target `crmflow24-draft-webhook` (migration 006): `target_type=webhook`, `auth_token_env_name=CRMFLOW24_PUBLISH_TOKEN`
3. Пока endpoint пуст — target остаётся в **dry-run** (безопасно)
4. `POST /api/documents/{id}/publish-draft` body: `{"publish_target_id": N, "dry_run": false, "force": false}`

**Idempotency:** повторный успешный publish блокируется (HTTP 409). `force=true` — только вручную.

**Rollback publish:**

```env
ENABLE_PUBLISHING=false
```

или очистить `CRMFLOW24_PUBLISH_ENDPOINT` и перезапустить сервисы.

## Failed items

`/admin/failed-items` — failed_retryable tasks, terminal errors, failed LLM runs, failed publish runs.

Безопасные действия:

- **Mark skipped** — только для `failed_retryable` → `error` с пометкой оператора
- **Reset stale** — running-задача без обновления 2+ часа → `failed_retryable`

## Troubleshooting

| Симптом | Действие |
|---------|----------|
| CLIProxy degraded | `/health/ready`, проверить cliproxyapi; временно `REWRITER_PROVIDER=mock` |
| LLM 429 | Подождать; rerun rewrite/review/seo позже |
| `failed_retryable` | Failed items → открыть task → исправить причину или mark skipped |
| Нет SEO slug | Run SEO на document |
| Нет rewritten_text | Rerun rewrite |
| Publish blocked | Publish readiness → missing list |
| Discovery всё blocked | Ослабить allow_patterns или другой source |
| Duplicate URLs | Нормально; enqueue не создаст дубль task |

## Safe rollback (env)

```env
REWRITER_PROVIDER=mock
ENABLE_PUBLISHING=false
ENABLE_SOURCE_DISCOVERY=false
ENABLE_LLM_REVIEW=false
ENABLE_SEO_ENRICH=false
```

После изменений: `sudo systemctl restart scrap-api scrap-worker`

## System commands

```bash
cd /opt/scrap
systemctl status scrap-api scrap-worker --no-pager
curl -s https://scrap.crmflow24.ru/health
curl -s https://scrap.crmflow24.ru/health/ready
journalctl -u scrap-api -n 50 --no-pager
journalctl -u scrap-worker -n 50 --no-pager
.venv/bin/alembic current
```

## E2E test script

```bash
cd /opt/scrap
PYTHONPATH=/opt/scrap .venv/bin/python scripts/test_2f_e2e.py          # read-only check
PYTHONPATH=/opt/scrap .venv/bin/python scripts/test_2f_e2e.py --execute  # limited discovery+enqueue
```

Не использует Hermes, не делает auto-publish.
