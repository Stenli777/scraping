# Архитектурные решения — индекс

<!--
HISTORICAL ROLE: MVP-era decisions (2026-05-17 scaffold).
NOT: Stage 5 / trust / publish policy ADRs.
CANONICAL ADRs: docs/adr/README.md (ADR-001..003 proposed)
-->

## Historical decisions (MVP — implemented)

Эти записи описывают **ранний scaffold**. Нумерация **не совпадает** с `docs/adr/ADR-001..003` (Content Studio / trust / auto-draft).

| ID | Topic | Status |
|----|-------|--------|
| MVP-001 | FastAPI + Jinja admin | **IMPLEMENTED** |
| MVP-002 | DB-polling worker | **IMPLEMENTED** |
| MVP-003 | Scrapling + trafilatura fallback | **IMPLEMENTED** |
| MVP-004 | Mock rewriter default in early env | **IMPLEMENTED** (prod typically `cliproxy`) |
| MVP-005 | Dedup `content_hash` | **IMPLEMENTED** |
| MVP-006 | Disk backups | **IMPLEMENTED** |
| MVP-007 | Domain parsers (saltpro, sotbit, habr) | **IMPLEMENTED** |

## Platform ADRs (governance — proposed)

| ADR | Topic | Status |
|-----|-------|--------|
| [ADR-001](adr/ADR-001-generated-content-model.md) | Generated content storage | **proposed** |
| [ADR-002](adr/ADR-002-trust-level-storage.md) | `trust_level` storage & audit | **proposed** (column shipped; engine TARGET) |
| [ADR-003](adr/ADR-003-auto-draft-vs-auto-public.md) | Auto-draft vs auto-public | **proposed** |

Lifecycle: [adr/ADR_LIFECYCLE.md](adr/ADR_LIFECYCLE.md).

## Truth alignment

Runtime vs policy gaps: [governance/ENFORCEMENT_MATRIX.md](governance/ENFORCEMENT_MATRIX.md), [CONSOLIDATION_INVENTORY.md](CONSOLIDATION_INVENTORY.md).
