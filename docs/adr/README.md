# Architecture Decision Records (ADR)

Краткие решения по спорным design-вопросам Scrap.

**Lifecycle:** [ADR_LIFECYCLE.md](ADR_LIFECYCLE.md) — states, transitions, `proposed` ≠ implementation.

**Status** в каждом ADR: `proposed` | `accepted` | `rejected` | `deprecated` | `superseded` | `historical`.

| ADR | Topic | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-generated-content-model.md) | Generated content storage model | **proposed** |
| [ADR-002](ADR-002-trust-level-storage.md) | Where to store `trust_level` | **proposed** |
| [ADR-003](ADR-003-auto-draft-vs-auto-public.md) | Auto-draft vs auto-public timing | **proposed** |

Принятые ADR → запись в `docs/DECISIONS.md`. Governance ссылается на ADR, но ADR не меняет runtime до implementation.
