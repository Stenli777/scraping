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
