# ADR Lifecycle — Scrap

Lifecycle for files in `docs/adr/`. Index: [README.md](README.md). Ownership: [CANONICAL_OWNERSHIP.md](../CANONICAL_OWNERSHIP.md).

## ADR states

| State | Meaning | Runtime impact |
|-------|---------|----------------|
| **proposed** | Under review; options documented | **None** — do not implement as decided |
| **accepted** | Decision approved | Implementation allowed per linked phase; update DECISIONS + canonical docs |
| **rejected** | Decision not taken | **None**; ADR kept for history |
| **deprecated** | No longer recommended | **None** for new work; existing code may remain until migration |
| **historical** | Context only; predates current platform | **None** |
| **superseded** | Replaced by newer ADR | Follow **replacement** link only |

**Required:** `proposed` ≠ approved implementation. Cursor/agents must not treat proposed ADR as schema truth.

## State transitions

```text
proposed → accepted | rejected
accepted → deprecated | superseded
deprecated → (immutable record)
superseded → (immutable; link to ADR-NNN)
```

**Forbidden:** Edit accepted ADR body to reverse decision — create superseding ADR.

## Naming convention

```text
docs/adr/ADR-NNN-short-topic.md
```

- `NNN` — zero-padded sequence (001, 002, …)  
- `short-topic` — kebab-case, English  
- Title in file: `# ADR-NNN: Human title`

## Review expectations

| Step | Owner |
|------|--------|
| Draft ADR | Author / Cursor |
| Options + pros/cons | In ADR file |
| Accept/reject | Human (project owner) |
| Record | `status` in ADR + `docs/DECISIONS.md` entry |
| Implementation | ROADMAP phase task, behind flags |

## Implementation linkage

Accepted ADR should reference:

- **ROADMAP** phase (e.g. Phase A, Phase D)  
- **Governance** files to update  
- **ENFORCEMENT_MATRIX** rows to add  
- Migration/API tasks (separate PR; not automatic)

**Forbidden:** Merge runtime code solely because ADR exists in `proposed`.

## Governance linkage

| ADR topic | Governance docs |
|-----------|-----------------|
| Generated model | STAGE5, CONTENT_MODEL, PROVENANCE |
| trust_level storage | TRUST_POLICY, AUTOMATION_POLICY |
| auto-draft vs auto-public | PUBLISH_POLICY, AUTOMATION, ADR-003 |

On **accept:** update canonical governance section if policy changes; do not duplicate full ADR text.

## Current ADRs

| ADR | Status |
|-----|--------|
| [ADR-001](ADR-001-generated-content-model.md) | **proposed** |
| [ADR-002](ADR-002-trust-level-storage.md) | **proposed** |
| [ADR-003](ADR-003-auto-draft-vs-auto-public.md) | **proposed** |

## Supersession template

In superseded ADR header:

```markdown
**Status:** superseded  
**Superseded by:** [ADR-00X](ADR-00X-topic.md)
```
