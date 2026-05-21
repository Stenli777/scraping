# feature-flagged-change

## Цель

Внедрить **опасное** изменение за feature flag: default OFF, kill-switch, audit.

## Когда использовать

- automation enablement paths
- auto-draft (Target)
- новые LLM stages
- publish path changes

## Workflow

1. **Flag strategy** — env name; default `false` in production template
2. **Governance** — `governance-alignment` skill
3. **Implementation** — code path only when flag true
4. **Kill-switch** — document env + admin steps (OPERATOR_RUNBOOK)
5. **Audit** — `llm_runs` / `publish_runs` / `pipeline_events`
6. **Rollout** — ROADMAP phase; gradual per project
7. **PROJECT_LOG** — включение flag на prod только после checklist

## Checks

- [ ] Default OFF on deploy
- [ ] Flag off = identical to pre-change behavior
- [ ] Rollback = set flag false + restart (no data delete)
- [ ] No bypass RC/audit when flag on

## Doc touch

- ROADMAP task status
- ENFORCEMENT_MATRIX
- OPERATIONS or `.env.example` comment (no secrets)
