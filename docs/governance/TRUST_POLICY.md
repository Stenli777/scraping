# Trust Policy — Scrap

Модель доверия **per project** для automation и publish. Дополняет [AUTOMATION_POLICY.md](AUTOMATION_POLICY.md), [PUBLISH_POLICY.md](PUBLISH_POLICY.md). **Current:** `projects.trust_level` (0–3, default **0**) в DB — **visibility-only**; **не** включает automation и **не** разрешает publish. Rule engine — **Target** (ADR-002 proposed). Не путать с `domain_trust_registry.trust_level` (source quality).

## Уровни 0–3

| Level | Generation | RC (create / approve) | Auto Draft | Auto Public |
|-------|------------|------------------------|------------|-------------|
| **0** | Manual / limited batch | Manual create; manual approve | **Forbidden** | **Forbidden** |
| **1** | Allowed + caps | Auto **create** RC allowed; **manual approve** required | **Forbidden** | **Forbidden** |
| **2** | Allowed + caps | Auto create; auto-approve RC **only** if separate policy enabled | **Allowed** after all gates + policy-approved RC path | **Forbidden** |
| **3** | Allowed + caps | Auto per policy | Auto draft after gates | **Target only** — separate flag + gates + operator enable; **not production-ready** |

| | |
|---|---|
| **Current** | Effective behavior ≈ **Level 0–1** (manual publish draft, automation off). |
| **Forbidden** | Treat Level 3 as available in production today. |
| **Forbidden** | Auto-public without ADR-003 approved implementation + PUBLISH_POLICY update. |

## Кто назначает уровень

| | |
|---|---|
| **Current** | Колонка `trust_level` в DB; изменение уровня — manual ops (admin edit Target); default L0. |
| **Target** | **Human only** — role `project_owner` / `platform_admin`; запись в audit (`trust_level_changes`). |
| **Required** | Повышение уровня — только **manual** после review (см. promotion). |
| **Forbidden** | Автоматическое **повышение** trust_level по метрикам без human approval. |

## Gates по уровню (обязательные)

| Gate | L0 | L1 | L2 | L3 |
|------|----|----|----|-----|
| Quality score ≥ threshold | Manual path | Required for auto RC create | Required | Required |
| RC QA score ≥ threshold | Manual | Required | Required | Required |
| Brief exists (Stage 5 generated) | N/A / Target | Target | Required | Required |
| No critical duplicate/cannibalization | Manual review | Block auto RC | Block auto draft | Block all auto publish |
| Daily/hourly generation limits | Required | Required | Required | Required |
| Audit trail (`llm_runs`, `automation_runs`, RC) | Required | Required | Required | Required |
| `ENABLE_AUTOMATION` / scheduler | Off default | Explicit enable | Explicit + L2 | Explicit + L3 + extra flag |

См. [AUTOMATION_POLICY.md](AUTOMATION_POLICY.md), [PROVENANCE_MODEL.md](PROVENANCE_MODEL.md).

## Promotion (повышение)

| | |
|---|---|
| **Required** | Human decision only; documented reason in `DECISIONS.md` or project log. |
| **Required** | **Minimum sample size** before promotion (примерные ориентиры, настраиваемые per project): |
| | L0→L1: ≥ 20 documents through full manual pipeline without critical incidents |
| | L1→L2: ≥ 30 RC with QA pass rate ≥ 90%, 0 critical duplicate publishes, 14 days stable ops |
| | L2→L3: **separate governance review** — not default roadmap |
| **Required** | **Cooldown** after incident: no promotion for 7–30 days depending on severity |
| **Forbidden** | Auto-promotion on score alone |

## Demotion / escalation

| Trigger | Action |
|---------|--------|
| Quality degradation (avg score drop > X% over 7d) | Auto **downgrade** max 1 level OR freeze auto-draft |
| Duplicate / cannibalization spike | Downgrade to L0; disable automation rules |
| Failed publishes (retryable cluster > N/day) | Freeze publish automation; manual only |
| Hallucination / factual incident (operator flagged) | Immediate downgrade to L0 + kill switch |
| Operator override / force publish abuse | Review + downgrade; audit review |
| Automation runaway (queue depth, cost) | `ENABLE_AUTOMATION=false` + cancel runs |
| Trust policy violation (invariant breach) | Emergency downgrade (see SYSTEM_INVARIANTS) |

| | |
|---|---|
| **Required** | **Downgrade** may be **automatic** or **manual**; always audit-logged. |
| **Required** | Emergency downgrade: set project to **L0**, disable rules, `ENABLE_AUTO_PUBLISH=false`. |
| **Forbidden** | Auto-**upgrade** on recovery without human sign-off. |

## Trust evaluation metrics (для review, не auto-promote)

| Metric | Use |
|--------|-----|
| Quality pass rate | Promotion packet only |
| RC QA pass rate | Promotion packet only |
| Publish success rate | Demotion trigger |
| Duplicate/cannibalization critical count | Demotion trigger |
| `llm_runs` error rate | Ops alert |
| Operator override / force count | Trust review |
| Draft rejection rate (CRMFlow24 feedback) | Demotion signal |

**Current:** metrics собираются частично (quality scores, publish_runs, RC QA) — единый trust dashboard **Target**.

## Interaction с automation rules

| | |
|---|---|
| **Current** | Rules disabled by default; manual run only. |
| **Target** | Rule metadata includes `min_trust_level`, `policy_version`; engine refuses run if `project.trust_level < min`. |
| **Required** | Kill switch: global `ENABLE_AUTOMATION=false` overrides any level. |
| **Forbidden** | Rule that bypasses RC QA or editorial when L < 2. |

## Interaction с publish policy

| trust_level | Publish draft | Publish public |
|-------------|---------------|----------------|
| 0–1 | **Manual** RC approve → `publish-draft` | **Forbidden** from Scrap automation |
| 2 | Auto-draft **only** via policy-approved RC path | **Forbidden** |
| 3 | Auto-draft per policy | **Target** — CRMFlow24 still manual public unless future approved |

См. [PUBLISH_POLICY.md](PUBLISH_POLICY.md), ADR [ADR-003](../adr/ADR-003-auto-draft-vs-auto-public.md).

## Storage (open)

Реализация хранения уровня — **proposed** в [ADR-002](../adr/ADR-002-trust-level-storage.md). До принятия ADR — политика без привязки к конкретной таблице.

## Открытые вопросы

- Пороговые числа X%, N failed publishes — per project config.
- RBAC: кто может emergency downgrade на production project.
- Связь `content_pilots` с trust promotion.
