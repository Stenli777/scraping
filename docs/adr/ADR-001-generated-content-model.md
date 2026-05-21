# ADR-001: Generated content storage model

| | |
|---|---|
| **Status** | **proposed** |
| **Date** | 2026-05-20 |
| **Context** | Stage 5 Content Studio needs persisted generated articles with provenance distinct from scrape. |

## Decision drivers

- Reuse existing pipeline (revision, RC, publish) vs clean separation.
- Provenance clarity (`source_type=generated`).
- Query/reporting for generated vs scraped.
- Migration and admin UI complexity.

## Options

### Option A: `parsed_documents` + `source_type=generated`

| Pros | Cons |
|------|------|
| Reuse revision, RC, publish, document admin | Table name misleading; wide row with nullable scrape fields |
| One pipeline code path | Risk of mixing scrape invariants with generated |
| Fewer joins | Indexes/filters need `source_type` everywhere |

### Option B: Separate `generated_documents` (or `content_articles`) table

| Pros | Cons |
|------|------|
| Clear domain boundary | Duplicate or bridge to revision/RC FK pattern |
| Safer scrape invariants | More migrations, services, admin pages |
| Explicit provenance columns | Pipeline abstraction layer required |

### Option C: Hybrid — generated table + view/unified `document_id` for RC

| Pros | Cons |
|------|------|
| Best separation + unified RC | Highest implementation cost |

## Proposed direction (not accepted)

Lean **Option A** for Phase 5A–5D if `source_type` + CHECK constraints + admin filters are strict; revisit **Option B** if invariant violations appear in implementation.

**Forbidden regardless:** storing generated rows without `topic_id` / `brief_id` linkage (PROVENANCE_MODEL).

## Migration implications

| Option | Migration |
|--------|-----------|
| A | Add `source_type` enum, nullable scrape fields, FKs `topic_id`, `brief_id` |
| B | New table + FK from `document_revisions.document_id` polymorphic or bridge |
| C | Both A and B pieces |

**Current:** no migration until ADR **accepted**.

## Provenance implications

- `article_v2.source.type = generated` (Target contract).
- No `source_url` unless `manual` citation list in brief metadata.
- `llm_runs` for outline_planner and article_writer mandatory.

## Consequences

- ADR acceptance unlocks Stage 5A schema work.
- Rejection of A in favor of B delays admin reuse but reduces long-term risk.

## References

- [STAGE5_CONTENT_STUDIO.md](../governance/STAGE5_CONTENT_STUDIO.md)
- [PROVENANCE_MODEL.md](../governance/PROVENANCE_MODEL.md)
- [CONTENT_MODEL.md](../governance/CONTENT_MODEL.md)
