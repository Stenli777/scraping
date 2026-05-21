# ADR-003: Auto-draft vs auto-public

| | |
|---|---|
| **Status** | **proposed** |
| **Date** | 2026-05-20 |
| **Context** | Trust Level 2 allows auto-draft; Level 3 targets auto-public. Need explicit separation of risk and rollout. |

## Decision

**Proposed (not implemented):**

1. **Auto-draft** (CRMFlow24 draft webhook) may be enabled at **trust_level ≥ 2** after gates — **earlier** in roadmap (Stage 5F).
2. **Auto-public** (live blog) remains **Forbidden** until separate program (Stage 5G / Level 3) with new feature flag and CRMFlow24 contract review.

## Why auto-draft is acceptable earlier

| Factor | Rationale |
|--------|-----------|
| Reversibility | Draft in CRMFlow24 admin can be archived before public |
| Existing path | Same `publish-draft` + RC QA already manual-proven |
| Visibility | `draft_url` + `draft_review_feedback` loop exists (4N) |
| Blast radius | No SEO/sitemap impact until human public step in CRMFlow24 |

## Why auto-public is dangerous

| Factor | Rationale |
|--------|-----------|
| Irreversibility | Public URL may be indexed; rollback is social/SEO cost |
| Trust | AI errors become customer-facing immediately |
| Boundary | Scrap explicitly does not own CRMFlow24 public CMS today |
| Compliance | Editorial/legal sign-off traditionally at public step |

| | |
|---|---|
| **Forbidden** | Using `ENABLE_PUBLISHING` or `ENABLE_AUTO_PUBLISH` today to mean public live publish. |
| **Current** | `ENABLE_AUTO_PUBLISH=false`; public only via CRMFlow24 operator. |

## Operational implications

### Auto-draft (Target L2)

- Requires: RC QA, quality, editorial policy (optional auto-approve RC), audit, daily caps.
- Operator still reviews drafts in CRMFlow24 (recommended).
- Failed draft publish: retryable runs; no public harm.

### Auto-public (Target L3 only)

- Requires: new flag (e.g. `ENABLE_AUTO_PUBLIC_PUBLISH`), CRMFlow24 API contract, rollback runbook, legal check.
- **Not production-ready** in Current state.
- Demotion to L0 on single critical incident ([TRUST_POLICY.md](../governance/TRUST_POLICY.md)).

## Rollback complexity

| Action | Complexity |
|--------|------------|
| Undo draft | Low — CRMFlow24 admin delete/archive |
| Undo public | High — unpublish, redirects, sitemap, cache; may need CRMFlow24 features Scrap does not control |
| Scrap-side | `publication_record` / `public_confirmed_at` audit only; Scrap does not unpublish CRMFlow24 |

**Implication:** auto-public needs **paired** rollback design in CRMFlow24 before Scrap automation.

## Consequences

- Stage 5F (auto-draft) can ship without Stage 5G.
- Level 3 must not be enabled in production config until ADR **accepted** + implementation + ops training.

## References

- [PUBLISH_POLICY.md](../governance/PUBLISH_POLICY.md)
- [TRUST_POLICY.md](../governance/TRUST_POLICY.md)
- [STAGE5_CONTENT_STUDIO.md](../governance/STAGE5_CONTENT_STUDIO.md) phases 5F vs 5G
- [CRMFLOW24_INTEGRATION.md](../CRMFLOW24_INTEGRATION.md)
