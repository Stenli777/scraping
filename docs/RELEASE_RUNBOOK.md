# Release Runbook — Scrap → CRMFlow24 (draft)

Операторский сценарий первого production-like выпуска через **Release Candidate** (этап 4L/4M).

## Standard article release flow

1. Открыть **Editorial Queue**: `/admin/editorial-queue`
2. Выбрать **safe document** (не smoke/debug, без `mock` в rewrite, strategy allowed)
3. Проверить readiness: strategy, canonical warnings, source quality, publish readiness
4. Довести pipeline при необходимости (API/admin):
   - `POST /api/documents/{id}/run-review`
   - `POST /api/documents/{id}/rerun-rewrite` (provider `cliproxy` для production-текста)
   - `POST /api/documents/{id}/run-seo`
   - `POST /api/documents/{id}/run-quality`
   - `POST /api/documents/{id}/extract-topics`
   - `POST /api/documents/{id}/analyze-similarity`
   - Editorial: `operator-review` → `approve` → `ready-to-publish`
   - Media: `POST .../media/generate-preview` с `{"provider":"placeholder","use_llm_prompt":false}` → approve media
5. **Create Release Candidate**: `POST /api/documents/{id}/release-candidates` или кнопка в document detail
6. **Run QA**: `POST /api/release-candidates/{id}/run-qa` — ожидание `qa_passed`, пустые blockers
7. **Fix blockers** штатными действиями (см. ниже), не force
8. **Payload preview**: `GET /api/release-candidates/{id}/payload-preview` — `valid=true`, `article_v2`, `status=draft`
9. **Approve**: `POST /api/release-candidates/{id}/approve`
10. **Publish draft**: `POST /api/release-candidates/{id}/publish-draft` → target `crmflow24-production-v2`
11. Проверить `publish_runs` (`release_candidate_id` заполнен) и `publication_records`
12. **Public check**: slug/title не в `/blog`, `/sitemap.xml`, `/rss.xml`

## Common blockers

| Blocker | Что делать |
|---------|------------|
| `smoke_test_blocked` | Не публиковать; другой документ или cliproxy rewrite без test markers |
| `seo_metadata` / `seo_slug` | `POST .../run-seo` |
| `quality_verdict` | `POST .../run-quality`; при score ≥ порога и `needs_revision` — operator approve после editorial |
| `editorial_approved` | Editorial workflow до `ready_to_publish` |
| `strategy_allowed` | `POST .../extract-topics`, проверить strategy readiness |
| `canonical_duplicate` | Analyze similarity, merge/другой угол, другой документ |
| `crmflow24_target_health` | Проверить target, токен, endpoint health |
| `payload_validation` | Исправить SEO/rewrite/review, повторить QA |

## Fix actions

- SEO: `POST /api/documents/{id}/run-seo`
- Quality: `POST /api/documents/{id}/run-quality`
- Rewrite (production): `REWRITER_PROVIDER=cliproxy` + `POST .../rerun-rewrite`
- Topics: `POST /api/documents/{id}/extract-topics`
- Similarity: `POST /api/documents/{id}/analyze-similarity`
- Editorial: `/api/documents/{id}/editorial/*`
- Другой документ из editorial queue

## Idempotency

- Повторный `publish-draft` для candidate в статусе `published_draft` → **400** (нужен новый candidate после изменения revision).
- Повторный publish того же `article_v2` на тот же target без force → **duplicate** в `publish_runs` (ожидаемо).

## Never do

- Force publish smoke/test документов
- Прямые правки БД CRMFlow24
- Public publish из Scrap (только draft)
- Удаление audit (`pipeline_events`, `publish_runs`)

## First production run (4M, 2026-05-18)

- **Document #4**: «Настройка CRM Bitrix24: полное руководство»
- **Release candidate #5**: QA score 79, `qa_passed` → `approved` → `published_draft`
- **Publish run #25**: `crmflow24_ack_v2`, draft admin URL на crmflow24.ru
- **Doc #8**: SEO восстановлен через `POST /api/documents/8/run-seo` после теста 4L

## Post-publish phase (CRMFlow24 draft review)

11. Open CRMFlow24 draft URL (from PublicationRecord / publish run).
12. Check content, SEO, media in CRMFlow24 admin.
13. Confirm article is **not** public (`Check public visibility` in Scrap or manual).
14. Mark draft feedback in Scrap (accepted / needs_edits / rejected).
15. If **accepted** — wait for manual public publish in CRMFlow24 (not from Scrap).
16. If **needs_edits** — revise in Scrap, new revision + release candidate; re-publish draft when ready.

## Post-draft review phase (checklist)

1. Open CRMFlow24 draft URL from Scrap publication/candidate.
2. Check content in CRMFlow24 admin.
3. Check SEO (title, slug, meta).
4. Check media.
5. Run **Check public visibility** in Scrap (`POST /api/publications/{id}/check-public-visibility`).
6. Mark **accepted** / **needs edits** / **rejected** in Scrap draft review panel.
7. If **accepted** — public publish **only manually** inside CRMFlow24 admin.
8. If **needs edits** — revise in Scrap, new revision + release candidate, re-publish draft when ready.

> **Warning:** Scrap never publishes publicly. CRMFlow24 admin remains the final public publishing boundary.

## Publish target classes (smoke safety)

| Class | Rules |
|-------|--------|
| **mock** | Local mock receiver only; no production token; default smoke |
| **test** | Failure simulation; disabled by default; ignored in health |
| **production** | Requires env token; never in default smoke; use `--include-production` |

Scrap never public-publishes. Production draft/publish only with explicit operator action.
