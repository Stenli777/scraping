# System Invariants — Scrap

Глобальные инварианты платформы. Нарушение = bug, policy breach, или blocked action (когда enforcement существует). **Current:** часть enforced в коде; часть — governance-only до реализации.

Связанные документы: [HUMAN_OVERRIDE_POLICY.md](HUMAN_OVERRIDE_POLICY.md), [PUBLISH_POLICY.md](PUBLISH_POLICY.md), [PROVENANCE_MODEL.md](PROVENANCE_MODEL.md).

## Content invariants

| ID | Invariant | Current enforcement |
|----|-----------|---------------------|
| C1 | `document_revision` records are **immutable** (new version = new row) | **Current** — revisions table |
| C2 | Raw scraped material is not silently overwritten on rewrite rerun | **Current** — rerun uses clean_text |
| C3 | `release_candidate` binds exactly one `document_revision_id` snapshot | **Current** — RC model |
| C4 | Revision change after RC creation requires **new** RC (not in-place mutation) | **Current** — operator workflow |
| C5 | Generated content **must** carry provenance (`source_type=generated`, topic/brief/llm_runs) | **Target** — Stage 5 |
| C6 | Generated content **must not** pose as scraped URL source | **Target** — payload contract |

## Publish invariants

| ID | Invariant | Current enforcement |
|----|-----------|---------------------|
| P1 | Every `publish_run` references the `document_revision_id` (and payload `revision_id`) actually sent | **Current** |
| P2 | `publication_record` means **draft delivered** to external system, not public live article | **Current** — ops/docs |
| P3 | Scrap does **not** perform CRMFlow24 public publish | **Current** |
| P4 | Production path: RC → QA → approve → `publish-draft` | **Current** — recommended |
| P5 | `ENABLE_PUBLISHING` enables mechanism, not public visibility | **Current** — env semantics |
| P6 | Auto-public requires Level 3 + separate flag + future implementation | **Forbidden** today |

## AI invariants

| ID | Invariant | Current enforcement |
|----|-----------|---------------------|
| A1 | All production LLM calls go through **CLIProxyAPI** | **Current** — rewriter path |
| A2 | **Hermes** is optional; pipeline runs if Hermes down | **Current** — `ENABLE_HERMES=false` default |
| A3 | No AI agent is **autonomous decision owner** for publish/editorial | **Current** — manual gates |
| A4 | Significant LLM calls leave **`llm_runs`** audit | **Current** |
| A5 | Explicit model alias; no provider default | **Current** — policy in code/docs |
| A6 | AI cannot bypass `rejected` / `needs_revision` without force + audit | **Current** — publish gating |

## Automation invariants

| ID | Invariant | Current enforcement |
|----|-----------|---------------------|
| M1 | Automation is **kill-switchable** (`ENABLE_AUTOMATION`, `ENABLE_SCHEDULER`, disable rules, cancel runs) | **Current** |
| M2 | `ENABLE_AUTO_PUBLISH=false` in production until approved | **Current** default |
| M3 | No autonomous infinite generation loops | **Current** — no Stage 5 batch |
| M4 | Source discovery does not auto-enqueue scrape | **Current** |
| M5 | trust_level **never auto-increases** | **Target** policy — [TRUST_POLICY.md](TRUST_POLICY.md) |
| M6 | Auto-draft only at trust ≥ 2 with all gates | **Target** |

## Audit invariants

| ID | Invariant |
|----|-----------|
| U1 | `pipeline_events` for stage transitions where pipeline applies |
| U2 | `automation_runs` for scheduler/rule execution |
| U3 | `publish_runs` retain force flag, dry_run, errors |
| U4 | Secrets never in logs/DB/git |

## Human override invariants

| ID | Invariant | Current enforcement |
|----|-----------|---------------------|
| H1 | Operator decision **overrides** AI recommendation | **Current** — workflow |
| H2 | Manual edits must not be **silently** overwritten by scheduler | **Current** — no auto rerun on edited docs without command |
| H3 | Force actions require audit (`force_used`, reason where possible) | **Current** — publish |
| H4 | Rerun rewrite/SEO/quality creates **new** revision | **Current** |

## Forbidden states (must not exist in consistent system)

| State | Why invalid |
|-------|-------------|
| `publish_run` without `document_revision_id` on success path | P1 broken |
| RC approved but pointing to superseded revision without re-QA | C3/C4 broken |
| `publication_record` treated as «live blog post» without CRMFlow24 public step | P2 broken |
| LLM rewrite with no `llm_run` | A4 broken |
| Generated article in payload with `source_url` copied from unrelated scrape | C6 broken |
| Automation enabled with no way to disable within 1 operator action | M1 broken |
| trust_level 3 in production config today | P6 / TRUST_POLICY |

## Future target invariants (Stage 5+)

| ID | Invariant |
|----|-----------|
| F1 | Brief exists before outline/article enqueue |
| F2 | Outline `llm_run` exists before article_writer |
| F3 | `article_v2.source.type` ∈ {`scraped`, `generated`, `manual`} |
| F4 | Batch jobs respect `max_topics` and daily caps |

## Invalid state examples

**Example 1 — Stale RC publish**

- Revision 5 created after RC approved on revision 4.
- **Violation:** C4, P1 if publish still uses rev 4 without new RC.
- **Expected:** Block publish or require new RC + QA; operator sees mismatch in admin.

**Example 2 — Fake scrape provenance**

- Generated article published with `source_url` from unrelated saltpro article.
- **Violation:** C6, P2 semantic trust.
- **Expected:** QA/payload validator reject (Target); manual catch (Current).

**Example 3 — Silent overwrite**

- Operator edits `rewritten_text`; night automation reruns rewrite without explicit command.
- **Violation:** H2.
- **Expected:** No auto rerun on «operator touched» flag (Target); Current relies on automation off.

## On violation

| Severity | Response |
|----------|----------|
| Blocking (enforced) | API/worker returns error; publish skipped |
| Detected post-fact | Operator incident; document/RC quarantine; PROJECT_LOG |
| Trust/policy | Emergency downgrade to L0; disable automation ([TRUST_POLICY.md](TRUST_POLICY.md)) |
| Invariant gap (not enforced) | File bug; align code with SYSTEM_INVARIANTS; ADR if schema change |

## Cross-reference matrix

| Invariant | Doc |
|-----------|-----|
| C1–C6 | CONTENT_MODEL, PROVENANCE_MODEL |
| P1–P6 | PUBLISH_POLICY |
| A1–A6 | AI_POLICY |
| M1–M6 | AUTOMATION_POLICY, TRUST_POLICY |
| H1–H4 | HUMAN_OVERRIDE_POLICY |
