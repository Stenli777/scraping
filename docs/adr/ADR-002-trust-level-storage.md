# ADR-002: Trust level storage

| | |
|---|---|
| **Status** | **proposed** |
| **Date** | 2026-05-20 |
| **Context** | [TRUST_POLICY.md](../governance/TRUST_POLICY.md) requires per-project `trust_level` 0–3 with audit trail for changes. |

## Decision drivers

- Admin visibility and editability.
- Automation rule engine read performance.
- History of promotion/demotion.
- Alignment with existing `project` profiles.

## Options

### Option A: DB column `projects.trust_level` (smallint)

| Pros | Cons |
|------|------|
| Simple queries; easy rule guard | No built-in history without separate audit table |
| Fast automation checks | Requires migration on `projects` |

### Option B: `project_profiles` / settings JSON

| Pros | Cons |
|------|------|
| No migration if JSON exists | Weak schema validation; easy to drift |
| Flexible metadata | Harder to index; audit unclear |

### Option C: `project_trust_levels` table (level + effective_at + changed_by)

| Pros | Cons |
|------|------|
| Full history; supports demotion audit | More joins; admin UI for history |
| Matches TRUST_POLICY triggers | Heavier for MVP |

## Proposed direction (not accepted)

**Option C** for production long-term; **Option A** as MVP if history stored in `project_trust_events` append-only table.

**Required policy regardless:** human-only promotion; auto demotion writes event row.

## Migration implications

| Option | Work |
|--------|------|
| A | `ALTER projects ADD trust_level`; default `0` |
| B | Document JSON schema in DECISIONS |
| C | New table(s) + seed defaults |

**Current:** implicit Level 0–1 via flags only — no column.

## Operational implications

- Automation rules read `min_trust_level` from rule metadata vs project level.
- Emergency downgrade: single UPDATE or INSERT event + disable rules.

## Consequences

- Until accepted, [TRUST_POLICY.md](../governance/TRUST_POLICY.md) is policy-only.
- ADR-003 auto-draft depends on readable trust_level at runtime.

## References

- [TRUST_POLICY.md](../governance/TRUST_POLICY.md)
- [AUTOMATION_POLICY.md](../governance/AUTOMATION_POLICY.md)
