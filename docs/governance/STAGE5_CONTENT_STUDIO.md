# Stage 5 — Content Studio (design)

<!--
TARGET DESIGN ONLY: future Content Studio — not production runtime.
NOT: current pipeline behavior | implemented schema.
CANONICAL FOR STAGE 5: this file (design); ROADMAP Phase D–E for order.
ADR: ../adr/ADR-001-generated-content-model.md (proposed).
-->

**Status: Target / future.** Не production reality. Не меняет Current runtime.

Канонический design doc для topic-driven content pipeline. Связанные политики: [CONTENT_MODEL.md](CONTENT_MODEL.md), [PROVENANCE_MODEL.md](PROVENANCE_MODEL.md), [TRUST_POLICY.md](TRUST_POLICY.md), ADR-001.

## Goals

| | |
|---|---|
| **Target** | Масштабируемое производство **original** статей по темам/кампаниям с полным provenance. |
| **Target** | Outline-first generation; brief обязателен; те же RC/publish gates, что у scraped. |
| **Target** | Automation bounded by trust policy и batch limits. |

## Non-goals

| | |
|---|---|
| **Forbidden** | Притворяться scraped content (fake `source_url`). |
| **Forbidden** | Autonomous infinite topic loops. |
| **Forbidden** | Auto-public publish в первых фазах rollout. |
| **Non-goal** | Замена Hermes; Hermes остаётся optional. |
| **Non-goal** | Public CMS в Scrap — publish draft → CRMFlow24 only (Current). |

## Current vs Target

### Current (production)

```text
source URL → scraping_task → parsed_document → revision → RC → publish_run → publication_record
```

Manual enqueue, rewrite/SEO/quality, operator-driven publish.

### Target (Stage 5)

```text
content_topic_batch
  → content_topic
  → content_brief
  → research_context
  → outline (outline_planner)
  → article_generation (article_writer)
  → seo
  → quality
  → document_revision
  → release_candidate
  → publish_draft (CRMFlow24)
  → [optional future] public publish (CRMFlow24 admin / Level 3 policy only)
```

## Architecture (logical)

```text
Admin / API
    → Topic Studio services (Target)
    → LLM via CLIProxyAPI only
    → Worker jobs (bounded queue)
    → Same editorial / RC / publish_service as scraped
```

| Layer | Target responsibility |
|-------|----------------------|
| Batch orchestration | Create batch, caps, kill switch |
| Brief / research | Structured inputs to writer |
| Generation | outline → draft; `source_type=generated` |
| Quality / RC | Reuse Current services |
| Publish | Same `publish-draft` path |

## Entities (Target)

| Entity | Purpose |
|--------|---------|
| `content_topic_batch` | Operator-initiated run; limits, project_id, status |
| `content_topic` | Single topic/keyword; links strategy/campaign optional |
| `content_brief` | Approved intent, constraints, research refs |
| `research_context` | Citations, notes (JSON); not a substitute for brief |
| `parsed_document` or generated table | `source_type=generated`, FK topic_id, brief_id |
| `document_revision` | Immutable after each AI pass |
| `release_candidate` | Same as Current |
| `media_*` | Optional preview generation |

Schema decision: **proposed** — [ADR-001](../adr/ADR-001-generated-content-model.md).

## Pipeline rules

| | |
|---|---|
| **Required** | Brief must exist before outline/article jobs enqueue. |
| **Required** | **Outline-first** — no full article without stored outline + outline `llm_run`. |
| **Required** | `topic_id`, `brief_id`, outline + writer `llm_run` on document. |
| **Forbidden** | Publish payload with fabricated scraped URL. |
| **Required** | Same RC QA + editorial gates as scraped ([PUBLISH_POLICY.md](PUBLISH_POLICY.md)). |
| **Forbidden** | Batch without `max_topics`, `max_articles_per_day`. |

## Automation (Target)

- Driven by `automation_rules` + `trust_level >= 2` for auto-draft phase only.
- Scheduler ticks isolated from scrape worker (same pattern as enrichment).
- **Forbidden** auto-public in phases 5A–5F.

## Governance

- [AI_POLICY.md](AI_POLICY.md) — roles: `brief_generator`, `outline_planner`, `article_writer`, media roles.
- [TRUST_POLICY.md](TRUST_POLICY.md) — promotion/demotion.
- [SYSTEM_INVARIANTS.md](SYSTEM_INVARIANTS.md) — global rules.

## Media generation (Target, optional)

```text
article draft → image_prompt_generator → image_generator → media_asset → RC payload preview
```

| | |
|---|---|
| **Target** | Media does not block publish by default (Current pattern). |
| **Required** | Media provenance: prompt llm_run, provider, approval state. |

## Rollout phases

| Phase | Scope | Auto-draft | Auto-public |
|-------|--------|------------|-------------|
| **5A Foundation** | Schema/ADR, admin read-only batch UI, trust_level field | **Forbidden** | **Forbidden** |
| **5B Research** | Brief + research_context manual/AI assist | **Forbidden** | **Forbidden** |
| **5C Outline** | outline_planner, stored outline | **Forbidden** | **Forbidden** |
| **5D Writer** | article_writer → revision; provenance complete | **Forbidden** | **Forbidden** |
| **5E Media** | Optional preview pipeline | **Forbidden** | **Forbidden** |
| **5F Auto-draft** | L2 + gates → policy-approved RC publish | **Target** | **Forbidden** |
| **5G Auto-public** | Separate program; Level 3 + flag | Policy only | **Target** (not default) |

**Current:** phases **not started** in production.

## Risks

| Risk | Mitigation |
|------|------------|
| Hallucinated facts | Brief + research audit; quality gate; operator review |
| Duplicate/cannibalization | Same canonical intelligence as scraped |
| Cost runaway | Batch caps, trust demotion, kill switch |
| SEO spam at scale | Trust L0 default; slow promotion |
| Wrong provenance in CRMFlow24 | `source.type=generated` in article_v2 (Target contract) |

## Operator workflow (Target)

1. Create `content_topic_batch` (limits, project).
2. Review/import topics; reject low-quality.
3. Generate or edit **brief**; approve brief.
4. Trigger outline → review outline.
5. Trigger article → review draft (revision).
6. Run SEO/quality (manual or assisted).
7. Create RC → run QA → approve → publish draft.
8. CRMFlow24 draft review (Current process).
9. Public publish **only** in CRMFlow24 admin (Current); Stage 5G exception — future only.

См. [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) for Current production ops.

## Open questions

- Research context: internal KB vs external search API.
- Reuse `campaigns`/`clusters` vs new batch entity only.
- Per-phase feature flags naming.
