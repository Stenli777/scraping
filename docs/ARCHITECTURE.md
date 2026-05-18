# ARCHITECTURE.md

# Scrap Platform — Architecture

## 1. System Overview

Scrap — production-oriented AI-powered scraping and content pipeline platform.

**Primary goals:**

- scrape content;
- extract structured information;
- clean noisy HTML;
- orchestrate AI workflows;
- rewrite/enrich content;
- publish drafts to external projects;
- support multi-project content operations.

---

## 2. Current Production Environment

### Server

```text
Host: hermes
Path: /opt/scrap
Domain: https://scrap.crmflow24.ru
```

### Existing Services

| Service | Purpose |
|---|---|
| scrap-api | FastAPI backend |
| scrap-worker | DB polling worker |
| nginx | reverse proxy + HTTPS |
| PostgreSQL | storage |
| CLIProxyAPI | unified LLM gateway |
| LM Studio | local inference |
| Hermes | future orchestration layer |

Hermes is already installed on the same server, but it is not part of Scrap runtime yet.

Paths:

- Scrap: `/opt/scrap`
- Hermes: `/hermes`
- CLIProxyAPI: `/opt/cliproxyapi`

Rules:

- Scrap may call CLIProxyAPI via API.
- Scrap must not modify Hermes files.
- Scrap must not modify CLIProxyAPI files.
- Hermes integration is future-stage only.
- Scrap must remain fully operational if Hermes is unavailable.
- Hermes must be treated as optional orchestration infrastructure.
- Any Hermes integration must be done through explicit API contracts and model routing policy.

---

## 3. Core Philosophy

### IMPORTANT

**Scrap is NOT:**

- an AI monolith;
- a fully autonomous system;
- Hermes-dependent runtime;
- tightly coupled to one LLM provider.

**Scrap IS:**

- modular;
- task-oriented;
- provider-agnostic;
- multi-project ready;
- API-driven;
- AI-enhanced;
- production-oriented.

---

## 4. High-Level Architecture

```text
                ┌────────────────────┐
                │      Admin UI      │
                │   Jinja2 / FastAPI │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │      FastAPI       │
                │       API          │
                └─────────┬──────────┘
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼

 ┌────────────────┐ ┌──────────────┐ ┌────────────────┐
 │ Task Scheduler │ │ Project Core │ │ Publisher Core │
 └──────┬─────────┘ └──────┬───────┘ └──────┬─────────┘
        │                  │                 │
        ▼                  ▼                 ▼

 ┌─────────────────────────────────────────────────────┐
 │                    Worker Layer                     │
 └─────────────────────────────────────────────────────┘
        │
        ▼

 ┌─────────────────────────────────────────────────────┐
 │                  Pipeline Engine                    │
 │                                                     │
 │ fetch → parse → clean → review → rewrite → SEO     │
 │ → validate → publish → backup                       │
 └─────────────────────────────────────────────────────┘
        │
        ▼

 ┌─────────────────────────────────────────────────────┐
 │                AI Orchestration Layer               │
 │                     (Hermes)                        │
 └─────────────────────────────────────────────────────┘
        │
        ▼

 ┌─────────────────────────────────────────────────────┐
 │                CLIProxyAPI Gateway                  │
 └─────────────────────────────────────────────────────┘
        │
        ▼

 ┌─────────────────────────────────────────────────────┐
 │                 LLM Providers Layer                 │
 │                                                     │
 │  LM Studio / OpenAI / OpenRouter / Local Models     │
 └─────────────────────────────────────────────────────┘
```

---

## 5. Project Structure

```text
/opt/scrap
├── app/
│   ├── admin/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── exporters/
│   ├── llm/
│   ├── models/
│   ├── parsers/
│   ├── publishers/
│   ├── rewriters/
│   ├── services/
│   ├── tasks/
│   ├── workflows/
│   └── workers/
│
├── alembic/
├── docs/
├── scripts/
├── storage/
│   ├── backups/
│   ├── logs/
│   └── exports/
│
├── tests/
├── .env
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 6. Core Modules

### 6.1 app/api

**Responsibilities:**

- REST API;
- admin endpoints;
- project management;
- task creation;
- status endpoints;
- publish endpoints;
- internal APIs.

### 6.2 app/admin

Simple Jinja2 admin.

**Responsibilities:**

- tasks dashboard;
- documents dashboard;
- projects;
- sources;
- review queue;
- logs;
- retry actions;
- pipeline visibility.

No frontend SPA required at MVP stage.

### 6.3 app/parsers

**Responsibilities:**

- Scrapling fetch;
- HTML extraction;
- article extraction;
- domain-specific parsers;
- anti-noise cleanup.

**Current:**

- generic article parser;
- saltpro parser;
- sotbit parser;
- habr parser.

**Architecture:**

- parser registry;
- parser auto-routing;
- fallback parser.

### 6.4 app/rewriters

**Responsibilities:**

- rewrite orchestration;
- prompt generation;
- provider abstraction;
- LLM communication.

**Providers:**

- mock
- cliproxy
- local
- future providers

MUST remain provider-agnostic.

### 6.5 app/llm

Dedicated AI abstraction layer.

**Responsibilities:**

- request schemas;
- response schemas;
- model routing;
- retries;
- token accounting;
- quality scoring.

NO business logic here.

### 6.6 app/publishers

**Responsibilities:**

- external publication;
- webhook publishing;
- draft creation;
- adapter system.

**Architecture:**

```text
BasePublisher
 ├── Crmflow24Publisher
 ├── AggregatorPublisher
 └── WebhookPublisher
```

### 6.7 app/workflows

Future Hermes-compatible workflows.

**Responsibilities:**

- AI chains;
- review chains;
- rewrite chains;
- orchestration schemas.

### 6.8 app/workers

**Responsibilities:**

- task execution;
- retries;
- timeouts;
- locking;
- polling.

**Current:**

- DB polling worker.

**Future:**

- Redis/Celery/ARQ compatible.

---

## 7. Multi-Project Architecture

### IMPORTANT

System must support multiple independent projects.

**Example:**

- crmflow24.ru
- future aggregators
- SEO satellites
- niche content portals

### 7.1 Project Entity

Each project stores:

- name;
- domain;
- categories;
- content rules;
- SEO profile;
- tone of voice;
- rewrite profile;
- publication config;
- LLM instructions.

### 7.2 Source Entity

Each source stores:

- source domain;
- allowed directories;
- crawl rules;
- parser mapping;
- rate limits;
- trust score.

## 7.3 Source Discovery Rules

Crawler must support:

- sitemap discovery;
- category crawling;
- pagination;
- URL normalization;
- robots-aware mode;
- max depth;
- crawl limits;
- recrawl intervals;
- blacklist rules;
- duplicate URL prevention.

---

## 8. AI Pipeline Architecture

### 8.1 Main Content Pipeline

```text
DISCOVER
  ↓
FETCH
  ↓
PARSE
  ↓
CLEAN
  ↓
DEDUPLICATE
  ↓
LLM REVIEW
  ↓
CONTENT PLAN
  ↓
REWRITE
  ↓
SEO ENRICH
  ↓
QUALITY REVIEW
  ↓
PUBLISH DRAFT
  ↓
BACKUP
```

## 8.2 Pipeline State Machine

Every task/document must have explicit pipeline state.

Example states:

- discovered
- queued
- fetching
- fetched
- parsing
- parsed
- cleaning
- cleaned
- deduplicated
- review_pending
- review_rejected
- rewrite_pending
- rewriting
- seo_enrich_pending
- publishing
- published_draft
- failed_retryable
- failed_terminal

Rules:

- all transitions must be explicit;
- workers must be idempotent;
- retries must not duplicate documents;
- failed stages must preserve artifacts/logs;
- each stage must store timestamps and duration.

---

## 9. LLM Review Layer

### Goal

Determine:

- should content be used;
- which project it belongs to;
- what rewrite strategy should be applied.

### Example Review Output

```json
{
  "take": true,
  "score": 87,
  "reason": "Good CRM implementation article",
  "content_type": "article",
  "target_project": "crmflow24",
  "recommended_angle": "Practical implementation guide"
}
```

## 9.1 LLM Audit Logging

Every LLM interaction must store:

- task_id
- project_id
- model_alias
- upstream_model
- prompt_template
- input_tokens
- output_tokens
- latency
- finish_reason
- fallback_used
- success/failure
- created_at

This is required for:
- debugging;
- quality analysis;
- routing optimization;
- provider comparison;
- cost monitoring.

---

## 10. Rewrite Strategy

### IMPORTANT

System should NOT perform naive synonym replacement.

**Correct approach:**

```text
extract facts
  ↓
extract structure
  ↓
determine intent
  ↓
build new outline
  ↓
generate original article
  ↓
SEO enrich
  ↓
review quality
```

**Goal:**

- original article inspired by source;
- not copied article.

## 10.1 Immutable Source and Derived Content Model

Original scraped content must be treated as immutable source material.

Model:

```text
source document
  ↓
derived project document
```

Rules:

raw source content is never overwritten;
every project-specific rewrite creates a derived document;
one source document may produce multiple project documents;
rewrites must reference the original source document;
project documents may have independent status, SEO metadata and publish state.

---

## 11. SEO Enrichment Layer

**Generated:**

- SEO title;
- meta description;
- H1;
- slug;
- tags;
- categories;
- FAQ;
- CTA blocks;
- internal linking hints;
- excerpts.

## 11.1 Content Quality Layer

Every rewritten article should receive quality scoring:

- readability;
- SEO quality;
- uniqueness;
- factual consistency;
- spamminess;
- structure quality;
- commercial usefulness.

Low-quality content must not auto-publish.

---

## 12. AI Orchestration (Hermes)

### CURRENT STATUS

Hermes is NOT runtime-critical.

Hermes is future orchestration layer.

### Hermes Responsibilities

**ONLY:**

- reasoning orchestration;
- agent workflows;
- AI chains;
- review chains;
- model routing.

### Hermes MUST NOT

- scrape websites;
- replace workers;
- replace queues;
- replace FastAPI;
- replace storage;
- replace PostgreSQL.

---

## 13. CLIProxyAPI Integration

### CRITICAL RULE

ALL LLM calls go through CLIProxyAPI.

**Workers MUST NOT call:**

- LM Studio directly;
- OpenAI directly;
- providers directly.

### Correct Flow

```text
Scrap
  ↓
CLIProxyAPI
  ↓
LM Studio / OpenAI / OpenRouter
```

### Benefits

- unified API;
- provider abstraction;
- centralized auth;
- fallback support;
- model routing;
- easier migration.

## 13.1 Hermes Integration Boundary

На текущем этапе Hermes НЕ подключается в runtime.

Scrap должен сначала получить стабильный LLM abstraction layer через CLIProxyAPI.

Hermes можно подключать только после появления:
- typed LLM contracts;
- workflow schemas;
- task statuses;
- llm_runs audit log;
- stable retry/error handling.

Первый Hermes-compatible слой:
- `app/workflows/`
- workflow definitions в YAML/JSON;
- request/response contracts;
- без прямого вызова Hermes из парсеров или worker core.

Запрещено:
- вызывать Hermes из fetch/parse/clean stages;
- делать Hermes обязательной зависимостью запуска scrap-api;
- ломать pipeline, если Hermes недоступен;
- блокировать scraping pipeline, если Hermes недоступен.

---

## 14. Model Routing

### Cheap Models

**Tasks:**

- classification;
- extraction;
- scoring;
- metadata generation;
- dedupe.

**Examples:**

- qwen3-coder-next

### Expensive Models

**Tasks:**

- rewrite;
- SEO optimization;
- final polish;
- editorial review.

**Examples:**

- hermes-4-70b

## 14.1 Explicit Model Routing Policy

Hermes and Scrap MUST NOT rely on provider default model selection.

Every AI task must explicitly define:
- task kind;
- agent role;
- required model alias;
- fallback model alias;
- max tokens;
- temperature;
- timeout;
- expected output schema.

CLIProxyAPI may expose one OpenAI-compatible endpoint, but model selection must be explicit through model aliases.

### Generic task aliases

- `local/classifier-fast`
- `local/extractor-fast`
- `local/rewrite-main`
- `local/seo-main`
- `local/qc-reviewer`
- `local/code-agent`
- `cloud/rewrite-fallback`

### Hermes-compatible aliases

- `hermes-default`
- `hermes-cheap`
- `hermes-code`
- `hermes-smart`
- `hermes-long`
- `hermes-long-smart`

Example task routing:

| Task | Agent role | Primary model | Fallback |
|---|---|---|---|
| classify_source | classifier | local/classifier-fast | local/rewrite-main |
| extract_facts | extractor | local/extractor-fast | local/rewrite-main |
| rewrite_article | writer | local/rewrite-main | cloud/rewrite-fallback |
| seo_enrich | seo_specialist | local/seo-main | local/rewrite-main |
| quality_review | critic | local/qc-reviewer | cloud/rewrite-fallback |
| code_generation | coder | local/code-agent | cloud/code-fallback |
| architecture_reasoning | architect | local/reasoning-main | cloud/reasoning-fallback |

Rules:
- no task may call CLIProxyAPI without explicit `model`;
- no Hermes agent may use provider default model;
- all model aliases must be configured in one registry;
- task results must store `model_used`;
- fallback events must be logged.
- Hermes must call CLIProxyAPI only through `/v1/*` Model API;
- Hermes must not use CLIProxyAPI Management API;
- Hermes config must not contain direct `api.openai.com`, `api.deepseek.com`, or other provider chat endpoints;
- DeepSeek aliases must not be smoke-tested with tiny `max_tokens`; use at least `512`;
- Scrap must remain operational if Hermes is unavailable.

## 14.2 Prompt Management

Prompts must not be hardcoded inside workers.

System must support:
- prompt templates;
- prompt versions;
- project-specific overrides;
- role-based prompts;
- rollback to previous prompt versions.

Prompt changes must be auditable.

---

## 15. Queue Strategy

### Current

DB polling.

### Future

Potential migration:

- Redis;
- ARQ;
- Celery;
- Dramatiq.

Architecture must remain compatible.

---

## 16. Reliability Strategy

### MUST HAVE

- retries;
- timeouts;
- idempotency;
- task locking;
- dedupe;
- content hashing;
- safe rollback;
- backup integrity.

---

## 17. Deduplication Strategy

### Current

- content_hash.

### Future

- normalized_url;
- canonical_url;
- title similarity;
- semantic dedupe;
- embedding similarity.

---

## 18. Backups

### Storage

`storage/backups/YYYY/MM/DD/<task_id>/`

**Store:**

- raw HTML;
- raw text;
- cleaned markdown;
- rewritten markdown;
- metadata;
- logs;
- future screenshots.

---

## 19. Git Strategy

**Repository:**

`git@github.com:Stenli777/scraping.git`

**Git root:**

`/opt/scrap/.git`

### Rules

Every stage:

- clean git status;
- isolated commits;
- rollback safety;
- no secrets in git.

### MUST IGNORE

- `.env`
- `storage/`
- `logs/`
- `*.db`
- `*.sqlite3`

---

## 20. Deployment Strategy

### Production

**Current:**

- systemd services;
- nginx reverse proxy;
- Let's Encrypt HTTPS.

### Services

- scrap-api
- scrap-worker

## 20.1 Feature Flags

Runtime feature flags must be supported through environment variables.

Examples:

```env
ENABLE_HERMES=false
ENABLE_AUTO_PUBLISH=false
ENABLE_SEO_ENRICH=true
ENABLE_LLM_REVIEW=true
ENABLE_SOURCE_DISCOVERY=true
DISCOVERY_DEFAULT_MAX_URLS=50
DISCOVERY_DEFAULT_TIMEOUT=30
```

### Source discovery (Stage 2E)

Controlled URL discovery from `source_directories` → `discovered_urls` → manual enqueue → existing scraping pipeline.

- Modes: `sitemap`, `html_links`, `mixed`, `manual`
- Safety: `max_urls_per_run`, same-host only, allow/block patterns, crawl delay, no headless browser
- **No** auto enqueue, scheduler, or deep crawl

### Operations layer (Stage 2F)

- Admin dashboard with task/discovered/failure metrics
- Pipeline summary on task/document detail
- `get_publish_readiness()` before publish draft
- Failed-items view; safe skip/stale reset
- See `docs/OPERATIONS.md`

### Hermes optional orchestration (Stage 3A)

- HTTP-only connector in `app/hermes/` — no imports from `/hermes`
- `hermes_runs` audit; failures isolated from pipeline/worker
- `ENABLE_HERMES=false` by default; readiness unaffected when disabled
- Contract `POST /v1/orchestrate`; CLIProxy fallback when orchestrate API not deployed

### Editorial workflow + revisions (Stage 2I)

- `editorial_status` on documents; operator approval separate from LLM quality verdict
- `document_revisions` immutable snapshots (rewrite/seo/quality/publish)
- `publish_runs.document_revision_id` audit trail
- `ENABLE_EDITORIAL_WORKFLOW` feature flag

### Prompt management + editorial QC (Stage 2H)

- Tables: `prompt_templates`, `prompt_versions`, `project_prompt_overrides`, `content_quality_scores`
- `prompt_service`: active version from DB; project override; code fallback; audit `key:version` in `llm_runs`
- `quality_service`: post-rewrite JSON scoring; verdict `approved` | `needs_revision` | `rejected`
- Publish gating when `ENABLE_QUALITY_REVIEW=true`; `force=true` bypass with `publish_runs.force_used`
- Admin: prompts, quality scores, editorial queue

### Production publishing (Stage 2G)

- `article_v1` payload with `payload_version`
- Validators + project review thresholds
- Idempotent publish (duplicate → 409 unless `force=true`)
- WebhookPublisher → crmflow24 via env `CRMFLOW24_PUBLISH_*`
- Tokens only in env, never in DB/logs

### Production-safe defaults

- Hermes disabled;
- auto publish disabled;
- destructive operations disabled;
- mock rewrite disabled unless explicitly configured.

## 20.2 Environment Strategy

Supported environments:

- local;
- development;
- staging;
- production.

Production-safe defaults:
- auto publish disabled;
- destructive operations disabled;
- debug logs disabled;
- secrets loaded only from environment;
- `.env` files must never be committed.

---

## 21. Admin Philosophy

Admin should remain:

- simple;
- lightweight;
- operational;
- debugging-friendly.

**NOT:**

- enterprise frontend;
- SPA-heavy;
- microfrontend system.

---

## 22. MVP Boundaries

### INCLUDED

- scraping;
- extraction;
- rewrite;
- SEO enrich;
- review queue;
- draft publishing;
- multi-project support;
- CLIProxyAPI integration;
- Git-safe development.

### EXCLUDED (for now)

- image generation;
- auto publishing;
- vector DB;
- RAG memory;
- autonomous browsing agents;
- advanced analytics;
- Kubernetes;
- distributed workers.

---

## 23. Long-Term Scaling Vision

**Target:**

- reusable content factory;
- reusable AI workflows;
- reusable publishing infrastructure;
- launch multiple projects rapidly;
- AI-assisted SEO operations.

---

## 24. Golden Rule

- FastAPI controls the platform.
- Workers execute operations.
- CLIProxyAPI abstracts inference.
- Hermes orchestrates reasoning.
- LLMs remain replaceable.
- Everything communicates through stable contracts.


## Media pipeline (optional, Stage 3B)

```text
document → media_prompt (LLM, llm_runs) → media_job → provider → media_asset
  → editorial approve → publish payload media.preview
```

- Не блокирует publish; readiness warning если нет approved preview
- Storage: local only, `storage/media/`, не в Git
- Provider abstraction: `placeholder` default; future AI providers


## Operations & resilience (Stage 3C)

- Manual backups: PostgreSQL + storage archives + JSON manifests
- Smoke checks: read-only by default (`scripts/smoke/run_all.py`)
- Config validation at startup (non-fatal) + `/health/config`
- Readiness: storage, media_storage, config checks


## Analytics feedback loop (Stage 3D)

```text
publish_run (success, not dry) → publication_record → manual import → analytics_snapshot
  → content_performance (score, trend, status) → editorial insights
```

- `performance_feedback_json` — future AI hook (not used automatically)
- No live tracking / no GA clone

## Scheduler and controlled automation (Stage 4A)

- **scrap-scheduler** — отдельный systemd-процесс, single-process loop (`app/scheduler/engine.py`).
- **Locks** — `scheduler_state` (`scheduler_lock`, `scheduler_heartbeat`), stale lock recovery 300s.
- **Automation rules** — `automation_rules` + `automation_runs` (audit).
- **Feature flags:** `ENABLE_SCHEDULER`, `ENABLE_AUTOMATION` (default false).
- **Limits:** global hourly, per-rule hourly/daily, max concurrent runs.
- **Manual gates:** editorial, publish, media approval — не автоматизируются.
- **NO:** auto-publish, autonomous AI loops, Celery/Redis/K8s cron.

## Async automation lifecycle (Stage 4B)

- `POST /api/automation/rules/{id}/run` creates `automation_run` with `status=queued` and returns immediately.
- `scrap-scheduler` picks queued runs first, then enqueues due scheduled rules.
- Run statuses: `queued`, `running`, `cancel_requested`, `cancelled`, `completed`, `failed`, `skipped`.
- `progress_json` and structured `logs_json` events for operator visibility.
- `POST /api/automation/runs/{id}/cancel` — queued→cancelled, running→cancel_requested.
- Stale `running` (heartbeat timeout) → `failed` via scheduler recovery or `POST .../mark-failed`.
- **Production default:** `ENABLE_SCHEDULER=false`, `ENABLE_AUTOMATION=false` (rules remain disabled in DB).

## Workspace guardrails (Stage 4C)

- Expected production workspace: hostname contains `hermes`, path `/opt/scrap`
- Startup logs warnings on mismatch (non-blocking)
- `/api/system/workspace` for operator verification

### Stage 4D ? crmflow24 inbound

HTTP-only integration; Scrap builds `article_v2`, receives acknowledgment, tracks `PublicationRecord`. Mock receiver for tests. See `docs/CRMFLOW24_INTEGRATION.md`.

### Stage 4E ? content strategy layer

Topics ? clusters ? campaigns ? coverage ? analytics feedback. Deterministic heuristics only.


### Strategy quality gate (4G)

Pipeline: deterministic topic_v2 → optional LLM `topic_cleanup_v1` → server-side `apply_strategy_gate`. Smoke/test/internal documents blocked from campaign/cluster coverage and suggestions.

### Deterministic-first + async enrichment (4H)

Strategy uses deterministic extraction immediately; LLM topic_cleanup runs in `llm_enrichment_jobs` queue with isolated scheduler tick and per-task timeouts.


## Deterministic-first orchestration (4I — see ARCHITECTURE.md)

```text
Core pipeline (scrape → rewrite → publish)
        ↓
Deterministic extraction (sync, <3s) → strategy gate → topics in metadata
        ↓
Optional async enrichment (llm_enrichment_jobs) → conservative merge → topics enriched
        ↓
Editorial intelligence (review, quality)
        ↓
Campaign intelligence (coverage, clusters) — uses deterministic-first topics
```

### Boundaries

- Enrichment is **optional**; failures do not block publish/rewrite/scraping.
- Worker processes **scraping batch first**, then max 1 enrichment job per poll.
- Scheduler runs enrichment tick **before** automation tick (isolated limits).
- Campaign intelligence ignores failed/stale enrichment; uses `deterministic_result` until merge completes.

### Enrichment job states

`queued` → `running` → `completed` | `failed_retryable` | `failed_terminal` | `cancelled` | `skipped`

Stale `running` jobs (heartbeat timeout) → `failed_retryable` with `[stale recovery]`.

### Merge policy

See `app/services/enrichment_merge_policy.py` — deterministic source-of-truth.

## Source quality intelligence (4J)

```text
discovery → deterministic quality scoring → quality_scored | quality_blocked
         → manual approve OR enqueue (never auto-enqueue blocked)
```

Deterministic-first; no embeddings. Optional LLM review via `ENABLE_SOURCE_QUALITY_LLM_REVIEW` (off by default).

Guarantees: core pipeline never waits on quality scoring; URLs never deleted.

## Canonical content intelligence (4K)

- **Canonical groups** — кластер похожих документов (suggestion-only, без auto-delete).
- **Similarity links** — детерминированные пары A↔B: `same_source`, `near_duplicate`, `topic_overlap`, `rewrite_family`, `campaign_overlap`, `cross_source_overlap`.
- **Rewrite lineage** — immutable цепочка source → rewrite → revision.
- **Cannibalization** — warnings при overlapping keywords/slug/published cluster; publish не блокируется.
- **Coverage** — duplicate-adjusted count для кампаний.

## Release candidate workflow (4L)

Document → QA checks → Release Candidate → operator approval → publish draft to CRMFlow24.

**QA score (deterministic, 0–100):**
- Base = `RELEASE_QA_REQUIRED_PASS_BASE` (default 70) × (required checks passed / total required).
- Bonus: up to +10 from quality score, +10 from review score.
- Penalty: canonical duplicate (−15), source quality block (−10), smoke/test (−30), warnings (−2 each, max −10).
- No ML / embeddings.

Candidate snapshot is bound to `document_revision_id`; revision change requires new candidate.

## Post-publish draft review (4N)

После `publish_draft` в CRMFlow24 оператор проверяет draft в админке CRMFlow24 и фиксирует результат в Scrap:

`CRMFlow24 draft` → `draft_review_feedback` → `draft_review_status` на candidate/publication → optional `editorial_status` / `pipeline_event`.

Нет webhook, нет двусторонней синхронизации, нет public publish из Scrap.

## 2026-05-18 — этап 4Q — Public publication confirmation

После ручной публикации в CRMFlow24 admin Scrap проверяет публичную видимость (blog, sitemap, rss) и по команде оператора подтверждает `publication_status=published`. Public URL: `https://crmflow24.ru/blog/<slug>` (из SEO slug). Admin/draft URL не считается public. `analytics_ready` = published + visibility public + `public_confirmed_at` set.
- **4R flow:** public confirmed → analytics_ready → manual snapshot import → content_performance + campaign/cluster summaries (read-time).
