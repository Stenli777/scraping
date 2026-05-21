# Publish Policy — Scrap

Политика публикации контента из Scrap во внешние системы. **Current** = только draft в CRMFlow24. **Target** = возможный auto-public через отдельный этап.

## Current — что делает Scrap

| | |
|---|---|
| **Current** | Scrap отправляет **только draft** в CRMFlow24 через HTTP webhook (`article_v1` / `article_v2`). |
| **Current** | Scrap **не** пишет в БД CRMFlow24, **не** выполняет public publish. |
| **Current** | Public URL появляется только после **ручной** публикации оператором в CRMFlow24 admin. |
| **Current** | Scrap может **подтвердить** public visibility (blog/sitemap/rss) и записать `publication_status` — это audit, не publish action. |

См. `docs/CRMFLOW24_INTEGRATION.md`, `docs/ARCHITECTURE.md` §4L, §4N, §4Q.

## Preferred path (Required для production)

```text
document (ready)
  → release_candidate (binds document_revision_id + publish_target)
  → run QA (deterministic checks + warnings; blocking `revision_current` if stale)
  → operator approve (**runtime blocks** if bound revision ≠ document latest)
  → POST /api/release-candidates/{id}/publish-draft (**runtime blocks** stale revision)
  → publish_run → publication_record
  → operator reviews draft in CRMFlow24 admin
  → (optional) draft_review_feedback in Scrap
  → (later) manual public publish in CRMFlow24
  → (optional) public confirmation in Scrap
```

| | |
|---|---|
| **Required** | `publish_runs.release_candidate_id` заполнен на production path. |
| **Forbidden** | Использовать `POST /api/documents/{id}/publish-draft` или raw `/api/publish` как **основной** production path. |
| **Current** | Legacy `POST …/documents/{id}/publish-draft` и admin form — **deprecated** (collapsed `<details>` + RC-first warn); stale revision **блокируется**; `force=true` требует `force_reason` **и** checkbox `force_confirm` в admin. |

## Feature flags — семантика

| Flag | Значение | Misinterpretation |
|------|----------|-------------------|
| `ENABLE_PUBLISHING` | Разрешает **механизм** отправки draft (webhook/mock) | **≠** public publish |
| `ENABLE_AUTO_PUBLISH` | Auto trigger publish | **Must stay `false`** до отдельного approved stage |
| `ENABLE_EDITORIAL_WORKFLOW` | Требует operator approval перед publish | Не заменяет RC QA |
| `ENABLE_QUALITY_REVIEW` | Gating по quality score | Manual-first quality run |

| | |
|---|---|
| **Required** | `ENABLE_AUTO_PUBLISH=false` в production до явного решения в DECISIONS + governance update. |
| **Forbidden** | Включать auto-publish «для теста» на production target `crmflow24-production-v2`. |

## Payload и идемпотентность (Current)

- `publish_targets.payload_format`: `article_v2` preferred.
- Ack: `external_article_id`, `draft_url`, `status: draft`.
- Duplicate protection: 409 без `force=true`; `force` пишет `publish_runs.force_used`.
- Tokens только в env (`CRMFLOW24_PUBLISH_TOKEN`), не в DB/logs.

## Dry-run и mock

| | |
|---|---|
| **Allowed** | `dry_run` на publish для проверки payload без HTTP. |
| **Allowed** | Mock receiver `/api/mock-crmflow24/*` — **testing only**. |
| **Forbidden** | Mock target в production publish runbook без явной маркировки. |

## publication_record ≠ public article

| | |
|---|---|
| **Required** | `publication_record` фиксирует успешную **доставку draft** и метаданные интеграции. |
| **Forbidden** | Считать запись автоматически опубликованной статьёй на сайте. |
| **Current** | `publication.status` в payload v2 — **draft only**. |

## Target — auto-public publish

**Не реализован.** Перед включением потребуется:

| Requirement | |
|-------------|--|
| Отдельный feature flag (не путать с `ENABLE_PUBLISHING`) | e.g. `ENABLE_AUTO_PUBLIC_PUBLISH` |
| Trust Level 3 + AUTOMATION_POLICY gates | |
| Rollback policy (как снять с public, кто отвечает) | |
| Explicit operator enablement per project/target | |
| Audit: publish_run type, operator id, reason | |
| Legal/editorial sign-off в DECISIONS | |

| | |
|---|---|
| **Forbidden** | Auto-public через существующий `ENABLE_PUBLISHING` без нового контракта. |

## Hermes и publish

Hermes не участвует в publish path. Publish — `publish_service` + WebhookPublisher.

## Открытые вопросы

- Webhook acknowledgment v3 (events back from CRMFlow24) — out of scope Current.
- HMAC signing production — documented, not implemented.
- Единый checklist «go live» draft vs public в admin UI.
