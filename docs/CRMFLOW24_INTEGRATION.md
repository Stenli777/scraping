# CRMFlow24 inbound integration

Scrap produces draft content; **crmflow24.ru** receives it via HTTP API. Scrap never writes to the crmflow24 database and does not import crmflow24 code.

## Publish flow

```text
Scrap (publish_service)
  ? build payload (article_v1 | article_v2)
  ? WebhookPublisher HTTP POST
  ? crmflow24 inbound endpoint (or mock receiver)
  ? validation
  ? draft article creation
  ? acknowledgment JSON
  ? PublishRun + PublicationRecord update
```

## Payload versions

| Version | Status | Notes |
|---------|--------|-------|
| `article_v1` | stable | Original draft payload |
| `article_v2` | current | Adds `source`, `editorial`, `media`, `publication` blocks |

Negotiation: `publish_targets.payload_format` selects builder/validator. Unsupported formats ? **terminal** failure (no retry).

### article_v2 extensions

- `source`: `source_url`, `source_domain`, `scraped_at`, `document_id`, `revision_id`
- `editorial`: `review_score`, `quality_score`, `editorial_status`
- `media.preview`: `url`, `alt_text`, `caption`
- `publication`: `status` (draft only), `requested_at`

## Security model

- Bearer token via `CRMFLOW24_PUBLISH_TOKEN` (production targets)
- Mock receiver (`/api/mock-crmflow24/*`) is **testing only** ? isolated, marked `testing_only`
- No anonymous public publish endpoint
- Optional HMAC: not implemented (contract-ready in docs only)
- IP restrictions: optional at nginx (not in Scrap)

## Acknowledgment response (v2)

```json
{
  "success": true,
  "external_article_id": "crmflow24-123",
  "draft_url": "https://crmflow24.ru/drafts/123",
  "status": "draft"
}
```

Stored on `publish_runs`: `external_id`, `draft_url`, `remote_status`, `response_schema_version` (`crmflow24_ack_v2`).

## Failure model

| Class | HTTP / cause | Publish run status | Retry |
|-------|----------------|-------------------|-------|
| Validation | 400, preflight | `failed_terminal` | No |
| Unauthorized | 401/403 | `failed_terminal` | No |
| Unsupported payload | 400 | `failed_terminal` | No |
| Timeout / network | transport | `failed_retryable` | Manual API |
| 502/503/5xx | server | `failed_retryable` | Manual API |

Fields: `retry_count`, `next_retry_at`, `last_retry_error`, `retry_parent_publish_run_id`.

## Manual retry API

`POST /api/publish-runs/{id}/retry` ? only for `failed_retryable`. Creates a new run linked to the parent chain.

## Mock receiver (stage 4D)

- `POST /api/mock-crmflow24/articles/import`
- `GET /api/mock-crmflow24/articles`
- Seed target: `scripts/seed_crmflow24_mock_v2_target.py` ? `crmflow24-mock-v2`

## Health

`GET /api/publish-targets/health` ? endpoint reachability, auth env, payload format support.

## Not in scope (4D)

- Auto-publish to public
- Direct DB writes to crmflow24
- Shared runtime with Hermes
- Event bus / GraphQL / CMS rewrite

## Production target (4F)

| Field | Value |
|-------|-------|
| Name | `crmflow24-production-v2` |
| Endpoint | `https://crmflow24.ru/api/scrap/articles/import` |
| Payload | `article_v2` |
| Auth | Bearer via `CRMFLOW24_PUBLISH_TOKEN` |
| ACK schema | `crmflow24_ack_v2` |

Mock target `crmflow24-mock-v2` remains for local integration tests.

### Idempotency

CRMFlow24 returns stable `external_id` / `draft_url` for same document+revision.
Scrap duplicate protection may block re-publish without `force=true`.

### Smoke publish

```bash
PYTHONPATH=/opt/scrap .venv/bin/python scripts/seed_crmflow24_production_v2_target.py
# manual publish via API with title prefix "Smoke test Scrap to CRMFlow24 production"
```

Delete test draft manually in CRMFlow24 admin after smoke.

### Recommended publish flow (4L)

1. Create release candidate (binds revision + `crmflow24-production-v2` when present).
2. Run QA — validates article_v2 payload, target health, strategy, quality, editorial, smoke guard.
3. Operator approve.
4. `POST /api/release-candidates/{id}/publish-draft` — sets `publish_runs.release_candidate_id`.

Force publish on raw `/api/publish` remains for admin debug only.

### First production draft (4M)

- Document #4, RC #5, publish_run #25.
- ACK: `crmflow24_ack_v2`, draft URL `https://crmflow24.ru/admin/posts/...`
- Публично не индексируется (blog/sitemap/rss check OK).
