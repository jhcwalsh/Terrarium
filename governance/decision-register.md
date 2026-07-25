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

## Step 2 decisions (STEP2-GENERATOR-PLAN / WP2.1b)

Decisions taken during Step 2's generator work, tracked separately from the platform
table above because one of them reuses an id already spoken for (see footnote). Same
status conventions as the table above.

| ID | Decision | Status | What was recorded | Blocks |
| --- | --- | --- | --- | --- |
| S2-D4 | Benchmark-strategy set for tail fidelity | CLOSED | Redefined over generator outputs (factors) only, per WP2.1b Item 1. Five strategies: `eqw_factors`, `sixty_forty`, `endowment_proxy`, `momentum`, `carry`. Strategies are defined over generated factors **and** their declared derived series (`govt_tr_10y`, `credit_xs_hy`, `cash_tr_1m` -- see `pre-registration.yaml`'s `derived_series` block, WP2.1b Task 2). Definitions live in `pre-registration.yaml` under `d4_strategies` and are reconstructible from it alone. | none |
| R5 | FX / non-US factors | CLOSED-deferred | "Institutions with material unhedged foreign-currency exposure are out of scope for v1. Adding FX later requires a block_addition amendment and retraining the generator, since cross-block correlation cannot be added to trained weights." (verbatim from `pre-registration.yaml`'s `decisions:` key; pinned by `tests/test_prereg.py::test_decision_consequence_text_is_verbatim`) | none |
| J3 | UK factor block | CLOSED-deferred | "UK-domiciled institution twins are blocked until a block_addition amendment; the InstitutionProfile interface accommodates them without rework. Same retraining consequence applies." (verbatim from `pre-registration.yaml`'s `decisions:` key; same test as R5). The InstitutionProfile interface referenced here is defined in `Instructions/DN4-jurisdiction-and-institution-plugin.md` §6. | none |
| S2-SEAL | Pre-registration seal scope | CLOSED | Widened beyond STEP2-GENERATOR-PLAN §WP2.3's wording ("the YAML plus the source of every enforce-tier metric plus `g2.py`") to match CLAUDE.md's stated invariant ("thresholds **and the code that judges them** are hashed together"). `ah.eval.prereg.seal()` now also hashes `eval/reference.py`, `eval/prereg.py` itself, `strategies.py`, `factors.py`, `battery/report.py` and `battery/stylized.py` -- every module that can move a pass/fail verdict. Consequence: **after WP2.3 seals, an edit to any judging module requires an amendment, including a refactor that changes no behaviour.** See `src/ah/eval/prereg.py`'s module docstring ("What the seal covers") and `pre-registration.yaml`'s header for the full accounting. | none |

R5 and J3 close with `active_blocks: [global, us]` sealed in `pre-registration.yaml` --
i.e. neither FX nor the UK block is active in the v1 campaign. R5's resolution **moved**
from Step2R §WP2R.4 (where STEP2R-CONSOLIDATION-PLAN originally scoped it) to WP2.1b,
because the FX decision sits inside the pre-registration seal's blast radius and had to
be settled before WP2.3, not after Step 3 planning begins. STEP2R-CONSOLIDATION-PLAN.md
§WP2R.4 has been updated to reflect this (dated note there points back here).

**Footnote -- "D4" is overloaded.** The `D4` in the platform table above (this file's
first table) is the **correlation regime model** decision. STEP2-GENERATOR-PLAN §WP2.3
and WP2.1b use "D4" for an unrelated thing: the **benchmark-strategy set** that VaR/ES
tail fidelity is computed on. To avoid ambiguity this section's row for the
strategy-set decision is filed under the id `S2-D4`, not `D4`. Both decisions are real,
both are named "D4" in their respective source documents, and neither renames the
other -- a later reader who sees "D4" in a Step 2 document should understand it means
the benchmark-strategy set, and "D4" in this file's first table means the correlation
regime model.
