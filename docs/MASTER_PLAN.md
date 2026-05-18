# Scrap — Master plan (reconciled)

## Pipeline layers

1. **Core pipeline** (required): scrape → parse → clean → rewrite → review → SEO → publish
2. **Deterministic extraction** (required for strategy): topic_v2 + strategy gate — sync, fast
3. **Async enrichment** (optional): `llm_enrichment_jobs` — improves topics, never blocks core
4. **Editorial intelligence**: review, quality, editorial workflow
5. **Campaign intelligence**: clusters, campaigns, coverage — deterministic-first

## Guarantees

- Core pipeline **NEVER** depends on enrichment completion.
- Enrichment failure **MUST NOT** block publish, rewrite, scraping, discovery.
- Enrichment **MAY** improve campaign quality, topic normalization, cluster suggestions.

## Terminology

| Term | Meaning |
|------|---------|
| deterministic extraction | Rule-based topic_v2 + strategy gate |
| async enrichment | Queued LLM jobs (`llm_enrichment_jobs`) |
| enrichment job | Single queued/running/completed LLM task |
| strategy readiness | Whether document can enter campaign planning |
| campaign intelligence | Coverage, clusters, suggestions (deterministic-first) |

Avoid: autonomous AI agent, self-improving pipeline, autonomous strategy.

## Stage map

- 4G: strategy quality gate
- 4H: async enrichment queue
- 4I: reconciliation, metrics, replay lineage, retention

## Source quality intelligence (4J)

```text
discovery → deterministic quality scoring → quality_scored | quality_blocked
         → manual approve OR enqueue (never auto-enqueue blocked)
```

Deterministic-first; no embeddings. Optional LLM review via `ENABLE_SOURCE_QUALITY_LLM_REVIEW` (off by default).

Guarantees: core pipeline never waits on quality scoring; URLs never deleted.

- [x] **4K** Canonical content intelligence — groups, similarity links, lineage, duplicate-adjusted coverage, admin, API, health `similarity`.

- [x] **4L** Release candidate QA pack — pre-publication checklist, approval, payload preview

- [x] **4M** First CRMFlow24 release candidate production draft + RELEASE_RUNBOOK

- [x] **4N** — CRMFlow24 draft review feedback loop (manual operator layer, visibility check, admin queue).

- [x] **4O** — workspace cleanup, scripts inventory, release state checks, operations checkpoint.

- [x] **4P** — smoke suite repair, publish target safety validation, mock/production isolation.

## 2026-05-18 — этап 4Q — 4Q done

Public publication confirmation + post-publish tracking. Не реализовано: auto-publish, webhooks, CRMFlow24 code changes, scheduled polling.
