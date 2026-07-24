# Decision register (STEP0-PLAN §WP0.9)

Open platform decisions. Each is `OPEN` until ratified at its workshop/gate; the
"recommended default" is the placeholder the code ships with so the rails run today.
Status transitions to `RATIFIED` (or `REPLACED`) with a dated note and a PR link.

| ID | Decision | Options | Recommended default | Status | Owner | Blocks |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | De-smoothing method | geltner_ar1 · glm_ma · regime_glm | glm_ma | OPEN | research | Step 1 mappings |
| D2 | Factor list / regime ruleset | candidate panel vs learned | rule-based regime v1 | OPEN | research | generator training |
| D3 | Generator family | toy-v0 · bootstrap · signature-mmd · conditional-diffusion | toy-v0 (Step 0) | OPEN | platform | Step 2 |
| D4 | Correlation regime model | negative · positive · inflation_conditional | inflation_conditional | OPEN | research | mappings |
| D5 | Structural parameter vintage default | historical_average · current · custom | current | OPEN | product | world authoring |
| D6 | Stylized-fact thresholds | per-metric min/max, enforce vs todo | all `todo` (pre-registration) | OPEN | research | battery enforcement |
| D7 | Albourne cashflow groups A/B intake | schema variants | groups A-E per spec | OPEN | data | Step 1 calibration |
| D8 | Persistence backend | SQLite · Postgres | SQLite (repository pattern) | OPEN | platform | scale-out |
| D9 | Compiler model + prompt policy | model id, prompt versioning | claude-sonnet-4-6 / compile-world-v1.0 | OPEN | platform | live compile |
| D10 | Approval workflow | roles, gates before shared library | human approver required | OPEN | product | shared library |
