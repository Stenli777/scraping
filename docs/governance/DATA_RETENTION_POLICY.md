# Data Retention Policy — Scrap

Сроки и правила хранения данных. **Current** = ops defaults + disk on hermes. **Target** = formal retention jobs (not necessarily implemented).

## Principles

| | |
|---|---|
| **Required** | Audit records (`llm_runs`, `publish_runs`, `document_revisions`) retained longer than ephemeral queues |
| **Required** | Secrets **never** in logs, DB content, or Git |
| **Forbidden** | Silent deletion of audit-critical rows |
| **Required** | `document_revision` rows immutable — no hard-delete in normal ops |
| **Forbidden** | Retain API keys in `storage/logs/app.log` |

## Retention table

| Data type | Retention (policy) | Reason | Current / Target |
|-----------|-------------------|--------|------------------|
| `raw_html` / fetch artifacts | 90–365d per project; then archive | provenance, re-parse | **Current** — disk; no auto purge |
| `clean_text` (on document) | life of document + 1y after archive | rewrite input | **Current** |
| `document_revisions` | **indefinite** (min 7y audit) | legal/editorial audit | **Current** — append-only |
| `parsed_documents` (active) | while active + archive flag | operations | **Current** |
| `llm_runs` | **min 2y**; prefer indefinite | model/prompt audit | **Current** — DB growth |
| `pipeline_events` | 1–2y online; archive older | debugging | **Current** partial |
| `publish_runs` | **min 7y** | compliance, retry audit | **Current** |
| `publication_records` | **min 7y** | draft delivery proof | **Current** |
| `automation_runs` | 1y online; archive | automation audit | **Current** |
| `scraping_tasks` | 1y online; archive terminal | ops metrics | **Current** |
| `task_logs` | 90d–1y | verbose debug | **Current** |
| `content_quality_scores` | life of document | quality gate history | **Current** |
| media files (`storage/media/`) | 90d after RC publish or reject | disk pressure | **Current** — manual cleanup |
| `storage/backups/` JSON/MD | 30–90d rolling | rerun safety | **Current** — OPERATIONS |
| `storage/logs/app.log` | 14–30d rotate | disk | **Current** — logrotate ops |
| `operational_snapshots` | 30d + max 500 rows | ops trend memory | **Current** — Phase D; auto cleanup on capture |
| `operational_incidents` | 30d + max 300 rows | lightweight incident history | **Current** — Ops Stability F1; diagnostics sync |
| PostgreSQL backups | 30d daily + monthly 12 | disaster recovery | **Current** — BACKUP doc |
| Hermes `hermes_runs` | 1y | optional audit | **Current** if enabled |
| Stage 5 briefs/topics (Target) | life of campaign + 2y | provenance | **Target** |
| Queue dead-letter (Target) | 90d | replay | **Target** |

## Sensitive data

| Data | Handling |
|------|----------|
| `CRMFLOW24_PUBLISH_TOKEN` | env only; rotate on leak |
| `CLIPROXYAPI_API_KEY` | env only |
| PII in scraped content | minimize in logs; operator access only |
| Operator notes | DB; not in public exports |

## GDPR / privacy (high-level)

| | |
|---|---|
| **Required** | Ability to identify document source URL for erasure requests |
| **Current** | No automated erasure API — manual ops + CRMFlow24 |
| **Target** | Erasure runbook: document + revisions + llm_runs anonymize flags |
| **Forbidden** | Delete audit rows without legal review |

## Cleanup strategy

| Tier | Action |
|------|--------|
| Hot | PostgreSQL active rows |
| Warm | Move old tasks/logs to archive tables (Target) |
| Cold | `storage/backups` + pg_dump to offsite |
| Media temp | Delete unreferenced files > 90d (script Target) |

| | |
|---|---|
| **Forbidden** | Cleanup job touching `document_revisions` / `publish_runs` without approval |
| **Required** | Cleanup scripts log counts to PROJECT_LOG |

## Archive strategy

- Monthly pg_dump (see `docs/BACKUP_AND_RECOVERY.md`).
- Export manifest JSON for backup archives.
- **Target:** object storage for raw_html blobs if disk pressure.

## Storage pressure

| Area | Risk | Mitigation |
|------|------|------------|
| raw_html volume | disk full | retention cap; compress; archive |
| media | large files | separate dir; cleanup |
| llm_runs growth | DB size | partition/archive (Target) |
| logs | rotation | logrotate |

## Backup frequency

| Asset | Frequency |
|-------|-----------|
| PostgreSQL | daily (production) |
| `storage/media` | weekly or on-demand |
| governance/docs | git |

## Immutable audit records

**Must not delete** in normal operations:

- `document_revisions`
- `publish_runs` (success and failure)
- `llm_runs` linked to published content
- `publication_records`

## Temp queue data

| Data | Retention |
|------|-----------|
| `automation_run` queued (cancelled) | 90d then archive |
| failed scraping_tasks | 1y for ops review |

## Related

- [PROVENANCE_MODEL.md](PROVENANCE_MODEL.md)
- [ROLLBACK_POLICY.md](ROLLBACK_POLICY.md)
- [../BACKUP_AND_RECOVERY.md](../BACKUP_AND_RECOVERY.md)
