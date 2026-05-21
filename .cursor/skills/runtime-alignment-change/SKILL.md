# runtime-alignment-change

## Цель

Реализовать **Phase A** runtime alignment (ROADMAP): guards без смены pipeline semantics.

## Когда использовать

- stale RC protection
- `trust_level` storage (после ADR-002 accepted)
- `operator_touched`
- mandatory `force_reason`
- invariant smoke checks

## Workflow

1. **Governance** — skill `governance-alignment`; ENFORCEMENT_MATRIX row
2. **Enforcement mapping** — обновить matrix после кода (partially → fully где возможно)
3. **Runtime guard** — minimal diff; feature flag if risky; default safe
4. **Smoke** — `scripts/smoke/run_all.py` или targeted check
5. **Rollback** — OPERATOR_RUNBOOK + ROLLBACK_POLICY; flag off = revert behavior

## Запрещено

- Менять pipeline stage order без явной команды
- Включать automation по умолчанию
- Ломать API contracts без необходимости

## Doc touch

- `ENFORCEMENT_MATRIX.md` — status column
- `PROJECT_LOG.md` — что shipped
- Canonical policy only if behavior boundary changed

## Лог

Файлы, флаги, migration id (если есть), smoke команда.
