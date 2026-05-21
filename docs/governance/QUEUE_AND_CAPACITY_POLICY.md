# Queue and Capacity Policy — Scrap

Модель очередей, лимитов и защиты ресурсов. **Current** = DB-polling worker + optional scheduler. **Target** = Stage 5 generation at scale.

## Current runtime

| Component | Role |
|-----------|------|
| `scrap-worker` | Poll `scraping_tasks`, pipeline stages |
| `scrap-scheduler` | Automation runs, enrichment tick (if enabled) |
| `llm_enrichment_jobs` | Optional async topic_cleanup |
| LLM | CLIProxyAPI → providers |

| | |
|---|---|
| **Current** | No heavy generation batches |
| **Current** | `ENABLE_SCHEDULER=false`, `ENABLE_AUTOMATION=false` default |
| **Forbidden** | Unbounded queue growth without ops alert |
| **Current (Phase B–D)** | Queue visibility + **bounded snapshot trends** (`operational_snapshots`); diagnostics/history; **visibility only** |

## Target runtime

- Stage 5: topic batch → brief → outline → article jobs
- Media generation queue (isolated)
- Multi-project concurrent automation
- Trust-gated auto-draft

## Queue types

| Queue | Current | Target | Priority |
|-------|---------|--------|----------|
| Scraping (`scraping_tasks`) | **yes** | yes | **high** — revenue content ingest |
| Enrichment (`llm_enrichment_jobs`) | **yes** | yes | **low** — must not starve scrape |
| Automation (`automation_runs`) | **yes** (if enabled) | yes | medium |
| Generation (Stage 5) | no | **yes** | medium — capped |
| Media jobs | optional | **yes** | low — separate worker tick |
| Publish | synchronous API | async optional | high when triggered |

### Priority rule (Required)

```text
scraping batch FIRST → max 1 enrichment per poll → automation tick (scheduler)
```

(ARCHITECTURE 4H / 4B — **partially enforced**.)

## Queue table

| Queue | Priority | Concurrency | Retry | Notes |
|-------|----------|-------------|-------|-------|
| scraping_tasks | P0 | 1 worker poll batch | manual re-queue; `failed_retryable` | Same-host discovery limits |
| enrichment | P2 | max 1/job per worker poll | `failed_retryable` → terminal | Timeouts per job |
| automation_runs | P1 (when on) | max concurrent per config | no infinite re-queue | cancel/mark-failed |
| generation (Target) | P1 | per-project cap | capped backoff | Requires brief gate |
| media (Target) | P3 | separate limit | provider errors | VRAM-sensitive |

## Concurrency

| | |
|---|---|
| **Current** | Single worker process model; scheduler single lock |
| **Required** | Project isolation — one project's runaway must not drain global pool (Target) |
| **Forbidden** | Unlimited parallel LLM calls per poll |

## Retry strategy

| Job type | Max retries | Backoff | Dead-letter |
|----------|-------------|---------|-------------|
| scraping `failed_retryable` | operator-driven | manual | task stays visible in failed view |
| publish `failed_retryable` | API retry chain | manual | `publish_runs` row |
| enrichment | scheduler recovery | stale → failed_retryable | terminal after N |
| automation | rule config | cooldown | `failed` / `skipped` status |
| generation (Target) | 3 default | exponential | `failed_terminal` + alert |

| | |
|---|---|
| **Forbidden** | Infinite retry loops |
| **Required** | `retry_count` visible on publish_run |

## Cooldowns

| Scope | Current | Target |
|-------|---------|--------|
| Per automation rule | hourly/daily limits | policy_version + trust |
| Per project LLM | governance-only | tokens/day cap |
| Post-incident | TRUST_POLICY | 7–30d promotion cooldown |

## Dead-letter approach

| | |
|---|---|
| **Current** | Terminal statuses (`error`, `failed_terminal`) + admin failed views |
| **Target** | DLQ table or `status=dead_letter` with operator replay |
| **Required** | No silent drop — row + logs retained |

## Starvation prevention

- Enrichment never blocks scraping completion (worker ordering).
- Generation (Target) cannot starve scraping P0.
- Scheduler automation tick after enrichment with separate time budget.

## Cost protection

| Job type | Cost risk | Mitigation |
|----------|-----------|------------|
| rewrite (cliproxy) | high | quality manual-first; batch size limits |
| SEO enrich | medium | per-document trigger |
| topic_cleanup LLM | medium | optional; isolated queue |
| article_writer (Target) | **critical** | daily cap per project; trust level |
| image_generator (Target) | high | separate queue; lower concurrency |
| automation mass rules | high | kill switch; rule daily cap |

## Resource assumptions

| Resource | Assumption |
|----------|------------|
| CPU | worker + API on same host; parsing CPU-bound |
| RAM | trafilatura/BS4 per task — bound concurrent tasks |
| VRAM | local LM Studio via CLIProxy — **operator** caps model concurrency |
| Disk | `storage/media`, raw artifacts — retention policy |
| Network | CRMFlow24 webhook timeout — retryable class |

| | |
|---|---|
| **Forbidden** | Assume unlimited provider quota |
| **Required** | Provider degradation → fail fast, no tight retry storm |

## Provider throttling

| Signal | Action |
|--------|--------|
| 429 / rate limit | backoff; mark job retryable |
| CLIProxy down | `failed_retryable`; alert ops |
| Model timeout | log llm_run; do not block scrape queue |

## Batch caps (Required)

| Cap | Scope |
|-----|--------|
| `DISCOVERY_DEFAULT_MAX_URLS` | per discovery run |
| automation rule daily/hourly | per rule + global |
| Target: `max_articles_per_day` | per project |
| Target: `max_topics_per_batch` | per batch |

| | |
|---|---|
| **Forbidden** | Unbounded generation |

## Emergency slowdown mode

| Step | Action |
|------|--------|
| 1 | `ENABLE_AUTOMATION=false`, `ENABLE_SCHEDULER=false` |
| 2 | Pause worker optional (systemctl stop) — scraping stops |
| 3 | Reduce discovery max URLs |
| 4 | Disable cliproxy-heavy rules |
| 5 | PROJECT_LOG incident |

**Target:** `EMERGENCY_SLOWDOWN=true` env flag (planned) — worker processes only P0 scrape, no LLM.

## Kill switch

| | |
|---|---|
| **Required** | Scheduler/automation kill-switchable (M1) |
| **Current** | Documented in OPERATOR_RUNBOOK |

## Target metrics dashboard

| Metric | Indicator |
|--------|-------------|
| queue depth by type | health |
| oldest `queued` task age | starvation |
| LLM error rate 1h | provider issues |
| automation runs `running` > timeout | stale |
| cost proxy: llm_runs/hour/project | runaway |
| enrichment backlog | optional delay OK |

## Runaway automation detection

| Trigger | Response |
|---------|----------|
| runs/hour > 3× baseline | alert; auto-disable rule (Target) |
| llm_runs spike | emergency slowdown |
| publish failures cluster | freeze publish (OPERATOR_RUNBOOK) |

## Related

- [AUTOMATION_POLICY.md](AUTOMATION_POLICY.md)
- [TRUST_POLICY.md](TRUST_POLICY.md)
- [STATE_MACHINES.md](STATE_MACHINES.md)
