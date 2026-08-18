# Decision register (STEP0-PLAN Â§WP0.9)

Open platform decisions. Each is `OPEN` until ratified at its workshop/gate; the
"recommended default" is the placeholder the code ships with so the rails run today.
Status transitions to `RATIFIED` (or `REPLACED`) with a dated note and a PR link.

| ID | Decision | Options | Recommended default | Status | Owner | Blocks |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | De-smoothing method | geltner_ar1 Â· glm_ma Â· regime_glm | glm_ma | CLOSED 2026-07-31 | research | none (was: Step 1 mappings) |
| D2 | Factor list / regime ruleset | candidate panel vs learned | rule-based regime v1 | CLOSED 2026-07-31 | research | none (was: generator training) |
| D3 | Generator family | toy-v0 Â· bootstrap Â· signature-mmd Â· conditional-diffusion | toy-v0 (Step 0) | CLOSED 2026-07-31 | platform | none (was: Step 2) |
| D4 | Correlation regime model | negative Â· positive Â· inflation_conditional | inflation_conditional | CLOSED 2026-08-01 | research | none (was: mappings) |
| D5 | Structural parameter vintage default | historical_average Â· current Â· custom | current | OPEN | product (Step 3: world authoring) | world authoring |
| D6 | Stylized-fact thresholds | per-metric min/max, enforce vs todo | all `todo` (pre-registration) | RATIFIED 2026-07-31 | research | none (was: battery enforcement) |
| D7 | Albourne cashflow groups A/B intake | schema variants | groups A-E per spec | OPEN | data (Step 3: WP3.4 institutional recalibration per STEP3-amendment-A1 Delta 1) | Step 3 calibration |
| D8 | Persistence backend | SQLite Â· Postgres | SQLite (repository pattern) | OPEN | platform (Step 3+: scale-out) | scale-out |
| D9 | Compiler model + prompt policy | model id, prompt versioning | claude-sonnet-4-6 / compile-world-v1.0 | OPEN | platform (Step 4: live compile) | live compile |
| D10 | Approval workflow | roles, gates before shared library | human approver required | OPEN | product (Step 4: shared library) | shared library |

**WP2R.8 closures (2026-07-31), evidence per row.** **D1**: `glm_ma` primary with
`geltner_ar1` secondary shipped and tested in Step 1 (`ah/data/desmooth.py`,
`tests/test_desmooth.py`); volatility-ratio and beta-shift diagnostics are the
acceptance evidence. One honesty note: **no `DESMOOTHING.md` report was ever
committed** â€” STEP2R-CONSOLIDATION-PLAN Â§WP2R.2 says "regenerate" a file that does not
exist (RFR-77/-78 class); WP2R.2 will *author* it, and its HF sections are blocked on
the undelivered Albourne HF series. **D2**: the sealed 14-factor panel over blocks
`[global, us]` (`factors.yaml`) and `regime_ruleset_v1` (`ah/data/derive.py`), both
inside `pre-registration.lock` since 2026-07-26 â€” the seal, not this register, is the
authority. **D3**: closed by the G2 verdict â€” PROMOTE `hier-flow-v1` over
`bootstrap-v1` (`G2-EVIDENCE.md`, snapshotted in `governance/evidence/`); the options
column above predates the L1â€“L4 hierarchical family and none of its four names is what
shipped, recorded rather than reworded. `toy-v0` remains Step 0's deterministic engine
for the rails. **D6**: RATIFIED by the project owner on 2026-07-31 â€” the provisional
values pre-authorized by `AM-2026-07-26-001`/`-002` (`ensemble_size.n_paths: 1024`,
`bootstrap_v1.mean_block_months`, the `nn_distance_*` margin factor, the
`elicitability_score` bound, the `var_95`/`es_95` three-fold width, `K = 4`,
`tuning_protocol.trial_budget_per_system: 40` with its tie-break) carried the campaign
to a completed, reviewed G2 gate and are ratified as sealed; a future campaign seals
its own values regardless, so this binds nothing forward.

**D4 closed at WP3.2 (2026-08-01).** The regime treatment of the mappings is DN-5
Â§4.3's, adopted deliberately: **betas are constant** â€” regime variation reaches
sleeve returns through the generator's regime-conditioned *factors* (the L2/L3
path every ensemble now carries first-class), never through regime-switching
loadings, and sleeve-space correlation therefore inherits factor-space
correlation plus the estimated cross-sleeve residual correlation
(`mappings/sleeve-mappings-v1.0.yaml`). The `inflation_conditional` default
remains the toy-v0 engine's lever only. What this costs is DN-5 Â§7's tension,
already resolved by the sealed thin-mapping decision (G3-pre): sleeve-space
tails get their own sealed battery instead of regime-varying betas. Re-opening
regime-varying mappings is a Step-3R+ decision with its own evidence bar.

**The 2R plan's D-ids do not all match this table (RFR-78 class, in a plan).**
STEP2R-CONSOLIDATION-PLAN Â§WP2R.8 says to close "D4 (tail objective + strategy set)"
and "D5 (state space)". In this register D4 is the *correlation regime model* and D5
is the *structural parameter vintage default* â€” different decisions. Resolved by the
owner on 2026-07-31: **close by content, not by id.** The strategy set the plan's
"D4" describes is `S2-D4` below, closed since WP2.1b; the state space its "D5"
describes is closed as `S2-D5-STATE-SPACE` below. The register's own D4 and D5 remain
OPEN with Step-3 owners, because nothing has decided them.

## Step 2 decisions (STEP2-GENERATOR-PLAN / WP2.1b)

Decisions taken during Step 2's generator work, tracked separately from the platform
table above because one of them reuses an id already spoken for (see footnote). Same
status conventions as the table above.

| ID | Decision | Status | What was recorded | Blocks |
| --- | --- | --- | --- | --- |
| S2-D4 | Benchmark-strategy set for tail fidelity | CLOSED | Redefined over generator outputs (factors) only, per WP2.1b Item 1. Five strategies: `eqw_factors`, `sixty_forty`, `endowment_proxy`, `momentum`, `carry`. Strategies are defined over generated factors **and** their declared derived series (`govt_tr_10y`, `credit_xs_hy`, `cash_tr_1m` -- see `pre-registration.yaml`'s `derived_series` block, WP2.1b Task 2). Definitions live in `pre-registration.yaml` under `d4_strategies` and are reconstructible from it alone. | none |
| R5 | FX / non-US factors | CLOSED-deferred | "Institutions with material unhedged foreign-currency exposure are out of scope for v1. Adding FX later requires a block_addition amendment and retraining the generator, since cross-block correlation cannot be added to trained weights." (verbatim from `pre-registration.yaml`'s `decisions:` key; pinned by `tests/test_prereg.py::test_decision_consequence_text_is_verbatim`) | none |
| J3 | UK factor block | CLOSED-deferred | "UK-domiciled institution twins are blocked until a block_addition amendment; the InstitutionProfile interface accommodates them without rework. Same retraining consequence applies." (verbatim from `pre-registration.yaml`'s `decisions:` key; same test as R5). The InstitutionProfile interface referenced here is defined in `Instructions/DN4-jurisdiction-and-institution-plugin.md` Â§6. | none |
| S2-NC5-EXEMPTION | The plan's NC5 self-contradiction | CLOSED | **The plan contradicts itself and the owner resolved it.** Â§WP2.2b (line 89) requires every negative control to fail its designated tier **at enforce**; Â§WP2.3 (line 93) makes conditional-tier results non-gating. NC5's designated tier *is* `conditional`, so both cannot hold. The project owner has ruled that **line 93 governs**: the conditional tier stays non-gating, every conditional threshold stays `severity: report`, and NC5's exemption from the enforce criterion is a **named, narrowly-scoped exception** covering exactly one control and exactly its designated cell. It is not a hole: NC5 is still detected substantively there (14 of 16 conditional metrics fire) and is still blocked, by `near_duplicate_fraction` at enforce, because a 24-month-block resampler emits verbatim historical windows. `tests/test_negative_controls.py::test_nc5_is_the_only_control_not_caught_at_enforce_and_only_by_sealed_design` now asserts **which** gate blocks it (WP2.3 strengthened it from a bare `not battery_passed`, which would have kept passing if an unrelated NaN-driven failure replaced the real block). Verbatim in `pre-registration.yaml`'s `decisions.S2-NC5-EXEMPTION`. | none |
| S2-ENSEMBLE-SIZE | The ensemble size the gate bounds are calibrated at | CLOSED | **The owner directed that a specific `n_paths` be sealed.** Every acceptance band is the sampling distribution of a statistic on ONE length-matched series, while the ensemble side averages over `n_paths` paths â€” so the gates' *power* rises without limit in ensemble size and `max: 0.5` at 16 paths is not the same criterion as `max: 0.5` at 1024. Sealed: **`n_paths: 1024`**, `months: 120`. **Two corrections at the re-seal.** (1) The first seal sealed **1000** while the MC-error grid it cited was measured at **1024** â€” a round number standing in for a measured one, which is exactly the substitution this file exists to prevent. 1024 is sealed because 1024 is what was measured. (2) The MC-error grid itself lived **here**, in this unsealed register, editable with no amendment and no lock violation, while a sealed value rested on it; it now lives inside `pre-registration.yaml`'s `ensemble_size.mc_error_grid`, inside the hash, and `scripts/measure_mc_error_grid.py` is its provenance script. A run at any other size **or against any vintage other than the sealed `campaign_vintage_id`** is recorded `criterion_bearing: false` on its `BatteryReport` and may not be cited in `G2-EVIDENCE.md` (the vintage half was added in the WP2.3 final pass -- `ah.eval.battery.criterion_bearing_for`, RFR-71; until then only the size was compared); `ah/eval/g2.py` does **not** reject it today â€” g2.py contains only the holdout-token mint, and that refusal is a sealed *requirement* on WP2.11 (`multi_seed_decision_rule.criterion_bearing_runs_only`), not an existing check. Changing the campaign size is a dated `protocol_change` amendment. **Downstream constraint: WP2.4 and WP2.8â€“2.10 must produce criterion-bearing ensembles at exactly this size, or amend.** | WP2.4, WP2.8â€“2.10 |
| S2-CAMPAIGN-VINTAGE | The campaign vintage moved from `2026-07-24` to `2026-07-26.1` | CLOSED | **A campaign restart, taken deliberately, before any generator existed.** The first seal froze a snapshot taken before `fred.FEDFUNDS` was registered, so `policy_rate` â€” a declared-active factor â€” had no data for reasons unrelated to the data existing. That removed `cash_tr_1m`, the `carry` D4 strategy, `term_premium`, `equity_risk_premium` and `policy_anchor_deviation` from the campaign. A live refresh (`ah data refresh --live`) restored it: 864 monthly observations, 1954-07 â†’ 2026-06, 798 of them in train+validation. Every band, floor, strategy statistic and measured claim in `pre-registration.yaml` was re-derived on `2026-07-26.1`; the per-factor bands for the eleven pre-existing factors are **bit-identical**, which is the expected result and the check that the vintage change moved only what depended on it. Recorded as `AM-2026-07-26-003`. The restart is cost-free precisely because no generator had been fitted and no G2 evidence existed â€” there was nothing to redo and nothing that could have been fitted to the new numbers. **What it did not fix:** `hy_spread` (an ICE licensing limit, not a stale snapshot â€” 37 observations, all inside the holdout), `commodities` (unsourced), and `bootstrap_v1.block_draw_span` (still 1990-2020, because `equity_vol`/VIX binds it). | WP2.4 |
| S2-ENDOWMENT-WEIGHTS | RFR-9: are `endowment_proxy`'s weights capital shares or a risk budget? | CLOSED | **Risk budget, stated in the definition rather than inferred.** `equity_mkt` 0.65 + `govt_tr_10y` 0.10 + `commodities` 0.10 are capital shares summing to 0.85; `credit_xs_hy` 0.15 is a notional/risk budget on a self-financing duration-hedged position, and 0.15 of capital is uninvested and earns nothing (the portfolio-level statement of that is `S2-NUMERAIRE-BIAS`). The alternative â€” a duration-matched government leg at HY spread duration (4.0y), making the credit sleeve a genuine total return â€” was rejected: it authors a **new** sealed derived series, distinct from `govt_tr_10y`'s 8.5y, with no evidence, for a strategy that has **no computable historical path** on this vintage and cannot be validated either way. Consequence: `ah.strategies`' sum-to-1.0 load check is not a full-investment check for this strategy. Verbatim in `pre-registration.yaml`'s `decisions.S2-ENDOWMENT-WEIGHTS`. | none |
| S2-SPREAD-FLOOR | `SPREAD_FLOOR_PCT = 0.0` (RFR-41) | RATIFIED | Ratified at seal time on measured evidence from the sealed campaign vintage: 54.0% of `ig_spread`'s 1224 train+validation observations (min 0.32) and 86.9% of `funding_spread`'s 420 (min 0.118) sit below DN-1.1 Â§II.4's literal 100bp floor; none of either sits below 0.0. At 100bp the gate rejects the historical record itself. `hy_spread`, the third floor factor, has no data on this vintage and could not be checked. The deliberately-not-taken alternative (a per-factor floor from each factor's own observed minimum) is recorded in `pre-registration.yaml`. | none |
| S2-NUMERAIRE-BIAS | RFR-12's uncommitted-capital bias | CLOSED (re-taken at the re-seal) | **Option (b), and the ground has changed.** The first seal chose (b) because option (a) was *impossible*: `cash_tr_1m` derives from `policy_rate`, which the `2026-07-24` vintage did not contain. On `2026-07-26.1` it is fully buildable, so (b) is now a **choice on measured evidence** (`scripts/measure_seal_evidence.py`, `momentum_cash_counterfactual`). `momentum` books 0.0 in 24.6% of its own 1134-month sample (warm-up + flat signal), and in 23.2% of the shorter 1954-2020 span option (a) could cover. Option (a) requires joining `equity_mkt` to `policy_rate`, which **truncates momentum's sample from 1134 to 798 months** (1926-07â†’1954-07, losing 1929-33, 1937 and the pre-war record) and moves its sealed tail statistics: ES99 0.15597 â†’ 0.12923 (âˆ’17%), ES95 0.09102 â†’ 0.07710. Measured on that same truncated span, the cash leg itself changes VaR95/ES95/VaR99/ES99 by **nothing at five decimals** â€” it moves only the mean (+â‰ˆ1.2%/yr). So (a) corrects a mean-level bias invisible to every statistic sealed for `momentum`, at the cost of deleting the worst tail in the record from the one live D4 tail benchmark. Sealed consequence (unchanged): `eqw_factors`, `endowment_proxy` and `momentum` realize zero on uncommitted/unallocated capital. `carry` carries no such bias â€” it is explicitly funded. **Re-entry, now concrete:** apply `ah.data.splice.PROXY_RULES['fedfunds_pre1954']` (backfill from `fred.TB3MS`, which begins 1934-01), shrinking the truncation to â‰ˆ90 months and flipping the trade; that is a `threshold_change` amendment plus recomputed `momentum` bands. | WP2.4 |
| S2-SEAL-SCOPE-2 | RFR-10 and `battery/thresholds.yaml` | CLOSED | **`ah/data/derive.py`: SEALED** â€” it is on the read path (`ah.eval.panel._DERIVED_EXPRS` calls `add`/`difference`/`funding_stress` at panel-read time for `equity_mkt`/`ig_spread`/`funding_spread`), so an edit changes what a sealed band is a band *of*. **`ah/data/splice.py`: NOT sealed** â€” its `PROXY_RULES` are registered but not applied by `ah.data.refresh` and `read_factor_frames` never calls it, which the reference run *demonstrates* (`hy_spread` is in `missing_factors` precisely because the `hy_oas_pre1996` backfill is absent; and `policy_rate`'s train+validation history starts exactly at `fred.FEDFUNDS`'s own first observation, 1954-07, not at the `fedfunds_pre1954` rule's `fred.TB3MS` source, which begins 1934-01 â€” so its *presence* on the new vintage is a second, independent demonstration that the rule is unapplied). RFR-10 also asked WP2.3 to confirm which the campaign vintage contains: **neither backfill**, on either vintage. **`src/ah/battery/thresholds.yaml`: SEALED** â€” every entry is `status: todo` and blocks nothing, but it is read by the already-sealed `ah/battery/report.py`, and a sealed estimator over an unsealed input is the exact failure RFR-33 closed for the conditional worlds. Full argument in `pre-registration.yaml`'s `seal_scope:` block. | none |
| S2-SEAL | Pre-registration seal scope | CLOSED | Widened beyond STEP2-GENERATOR-PLAN Â§WP2.3's wording ("the YAML plus the source of every enforce-tier metric plus `g2.py`") to match CLAUDE.md's stated invariant ("thresholds **and the code that judges them** are hashed together"). `ah.eval.prereg.seal()` now also hashes `eval/reference.py`, `eval/prereg.py` itself, `strategies.py`, `factors.py`, `battery/report.py` and `battery/stylized.py` -- every module that can move a pass/fail verdict. Consequence: **after WP2.3 seals, an edit to any judging module requires an amendment, including a refactor that changes no behaviour.** See `src/ah/eval/prereg.py`'s module docstring ("What the seal covers") and `pre-registration.yaml`'s header for the full accounting. | none |
| S2-SEVERE-GATING | What the severe test's INCONCLUSIVE reading IS, given that the sealed protocol pins no threshold | CLOSED | **Option (a) of three, taken by the owner on 2026-07-30 with the severe-test result already in hand, and the timing is stated rather than smoothed.** `severe_test_protocol` specifies exactly how to run the test and requires the result to be written up either way; it never says what counts as passing. The three routes were: (a) record INCONCLUSIVE as a HUMAN JUDGEMENT, labelled as such, entering `G2-EVIDENCE.md` as evidence and **not** as a gate; (b) write a pass mark now -- rejected, because a threshold authored after the score is the exact substitution the seal exists to prevent; (c) declare the test structurally uninformative -- rejected as overclaiming, since the test did detect a systematic footprint (regime-frequency TV +0.0140, consistent to four decimals across three seeds). **What (a) commits to:** the severe test is NOT one of the sealed rule's four clauses and never was, so nothing about the verdict arithmetic changes; `G2-EVIDENCE.md` must present the severe result as reported evidence, must state in terms that the protocol pinned no threshold, and must not describe INCONCLUSIVE as a computed outcome. **No amendment, no re-seal, no threshold written after the fact** -- that is the substance of the choice, not an omission from it. | none |
| S2-HORIZON-TIER | "the horizon tier" resolves two ways | CLOSED | **Both readings reported; no narrowing.** `severe_test_protocol` says to compare through "the horizon tier"; `TIERS` has no such tier. Reading A (`suite == "horizon"`) selects 110 metrics, reading B (`tier in {1_5yr, 10yr}`) selects 113, differing by `interval_coverage_50_5y`, `interval_coverage_90_5y` and `pit_ks_stat_5y`. Picking one with results in hand is a forking path, and the fact that the two readings agree is not something that could be claimed without first looking -- so **neither is adopted**. Both are reported and every row carries its suite and tier, as WP2.11 part 1 already does. Narrowing to one remains available as a dated `protocol_change` amendment **before the next campaign, when no results are in view** -- not now. Same defect class as `AM-2026-07-29-001`'s (a sealed sentence naming something the code does not define); the general fix is unowned, RFR-78. | none |
| S2-DEFAULT-GENERATOR | If BOTH co-primaries clear the sealed rule, which becomes the default `generator_id` | CLOSED | **Decided blind, on 2026-07-30, BEFORE clauses (2)-(4) were adjudicated and before the holdout was touched -- which is the only reason it is worth anything.** The sealed `rule` is written in the singular ("PROMOTE the challenger over `bootstrap-v1`") while WP2.9 deliberately carried two co-primaries, so a both-pass outcome has no sealed tie-break. Decided: **the challenger that clears clause (1) on the STRICTER route becomes the default** -- i.e. beating `bootstrap-v1` in EVERY seed outranks beating it only pooled-by-more-than-dispersion. The runner-up **stays registered and reachable through `ah.gen.registry`, but is not the default**. On the WP2.10 grid this points at `hier-flow-v1` (every-seed on both routes) over `hier-diffusion-v1` (pooled route only, and clause (ii) fails in every seed) -- but the rule above is what was decided, not the name. If the verdict is SHIP-BENCHMARK the question does not arise: `bootstrap-v1` remains default per the seal. | WP2.11 |
| S2-REVIEWER-OF-RECORD | Who reviews `AM-2026-07-29-001` before the verdict is computed | CLOSED | **The project owner, acting as reviewer of record -- i.e. NO outside party -- and `G2-EVIDENCE.md` must say exactly that rather than let "independent reviewer" imply one.** Sequencing was decided on 2026-07-30 and is binding: the post-hoc amendment and the WP2.10 head-to-head go in front of the reviewer **before** `ah/eval/g2.py` computes any verdict, not alongside it afterwards. STEP2-GENERATOR-PLAN Â§7 treats review of the sealed pre-registration as part of the effective-challenge record; that record is weaker when reviewer and author are the same party, and the honest disclosure is the mitigation available. **Consequence for `G2-EVIDENCE.md`:** it states who reviewed, that they are not independent of the work, and that `AM-2026-07-29-001` is a post-hoc correction made by the beneficiary -- all three, in the same place, not scattered. | WP2.11 |
| S2-VALUATION-FACTOR | Whether to add a valuation factor and retrain, now that RFR-81 shows the data was always registered | CLOSED | **Route (1): complete G2 on the sealed 14 factors.** Taken by the owner on 2026-07-31, closing the decision RFR-81 deliberately left open. The `10yr` tier stays declared UNAVAILABLE exactly as `conventions.ten_year_tier_coverage` seals it, `G2-EVIDENCE.md` may not cite a `10yr` pass, and the valuation factor enters as a **dated factor amendment plus a full L1/L2/L3 retrain for the NEXT campaign** (`WP1.13`, rescoped by RFR-81 to "map `shiller.cape` and retrain", owner: project owner). **Route (2), rejected and recorded because rejecting it is the substance:** retraining at 15 factors now would restart the campaign with the WP2.10 head-to-head already in hand -- the same hazard `AM-2026-07-29-001` already cost once, and a far larger one, since a retrain re-rolls every number the verdict rests on. **What this decision does NOT claim:** that 14 factors is the right panel, or that the decade tier's unavailability is acceptable in the long run. It claims only that the fix does not belong inside the gate it would alter. | none |
| S2-REVIEW-OUTCOME | The reviewer-of-record review required by `S2-REVIEWER-OF-RECORD`, and what its approval does and does not cover | CLOSED | **APPROVED on 2026-07-31, by the project owner as reviewer of record, BEFORE the holdout was opened and before any verdict was computed** -- the sequencing `S2-REVIEWER-OF-RECORD` made binding. Material reviewed: `governance/G2-REVIEWER-PACKET.md` (plain-language, committed at `52c46ba`), which carries `AM-2026-07-29-001` in full including its timing, the head-to-head from `ABLATION.md` Â§6, the sealed draw-span bias and the restricted-window re-run, RFR-76/-80/-81, and the diffusion severe-arm money-pump finding. **WHAT THE APPROVAL COVERS -- three narrow questions, and nothing else:** (1) the field's reading is the correct one and `AM-2026-07-29-001` is a genuine correction rather than a convenient one; (2) the benchmark's 1990-2020 draw-span disadvantage, weighed rather than merely noted, does not undermine the comparison -- the challenger's margin WIDENS under the sealed restricted-window re-run; (3) the one-shot holdout may be spent. **WHAT IT EXPLICITLY DOES NOT COVER, recorded because the distinction is the substance of the review:** it is NOT a judgement that the results are "good enough", and NOT an endorsement of model quality. That question was answered in advance by the sealed rule, and a reviewer approving or declining on their own read of the numbers -- in either direction -- would be doing precisely what the seal exists to prevent. **THE REVIEWER IS NOT INDEPENDENT of the work** (they commissioned it); `G2-EVIDENCE.md` must state that plainly rather than let "independent reviewer" imply an outside party, and must state alongside it that `AM-2026-07-29-001` is a post-hoc correction made by the beneficiary. **BOTH READINGS OF THE EVIDENCE STAND TOGETHER and both must be published:** the challenger beats the benchmark on the pre-registered criterion in every seed and on both routes, AND neither generator is a convincing model of history -- 1966-84 is called a long inflation era under half the time against history's every window, inflation persistence is roughly half its historical half-life, drawdowns are understated about twofold, stagnant decades are invented at 0.29-0.75 against a historical 0.00-0.05, and the `10yr` tier that would catch decade-scale error is 73% structurally unavailable. A PROMOTE verdict changes the default `generator_id` for Step 3's work; it is not a statement of fitness for real decisions, which Step 5's decision-evaluation exists to test. | WP2.11 |
| S2-BRANCH-DEVIATION | WP2.10 and WP2.11 share the branch `wp2-10-ablation`, against the one-work-package-per-branch convention | CLOSED | **Merge as-is and RECORD the deviation; do not split.** Decided 2026-07-31. The branch carries 13 commits ahead of `main`: two of WP2.10 and eleven of WP2.11 plus governance. **THE DECIDING REASON is not tidiness but traceability:** `S2-REVIEW-OUTCOME` in this very file cites commit `52c46ba` BY HASH as the material the reviewer of record reviewed. Splitting the branch rewrites every hash after the split point and turns a committed audit citation into a dangling reference â€” an audit trail pointing at a commit that no longer exists is strictly worse than a branch with an untidy name. Supporting: the branch is already on `origin`, so splitting means rewriting PUBLISHED history and force-pushing, which this repo carries a standing caution about (history was rewritten once, to scrub a secret); and the commits are individually labelled (`WP2.10:`, `WP2.11 part 1/2a/2b`, `AM-â€¦`, `S2-â€¦`) so the history reads as two work packages whatever the branch is called. **What the deviation costs:** nothing touching the seal, the evidence, the numbers or the verdict â€” it is a process-convention breach, and this project's practice for those is to record rather than paper over. **The remedy is PROSPECTIVE:** WP2.12 onward starts on its own branch, which restores the convention in a way retro-splitting would not. **The merge itself is NOT authorized by this row** â€” it waits on the full gate being green (verdict code, `G2-EVIDENCE.md`, model cards), per the standing definition of done. | WP2.11 close-out |
| S2R-FX-NEXT-CAMPAIGN | The FX judgment call DN-5 Â§8 flags as "the item most likely to be regretted" (SM-13), due at the 2R session per STEP3-amendment-A1 housekeeping | CLOSED | **Fold an FX block into the NEXT generator campaign's retrain.** Decided by the project owner on 2026-07-31, at the 2R session as DN-5 asked, rather than being discovered a third time. The next campaign already carries a full L1/L2/L3 retrain for two other reasons â€” `WP1.13` (map `shiller.cape`, revive the `10yr` tier, per `S2-VALUATION-FACTOR`) and the regime-persistence fix the severe test located upstream of L3 â€” so adding the FX block there means ONE retrain buys all three, where adding FX alone would cost the same retrain for one. **What this does and does not change now:** `R5`/`J3` remain CLOSED-deferred for the v1 campaign exactly as sealed (`active_blocks: [global, us]` untouched); the `block_addition` amendment is authored when the next campaign's seal is authored, not today; UK worlds remain blocked until then per J3. SM-13's flag is discharged as a *decision taken*, not as work done. | next campaign seal |
| S2-D5-STATE-SPACE | The slow-state (L1) state space | CLOSED | **The five-state contract DN-1.1 Â§II.2 specifies â€” `(pi_star, r_star, g, v, credit_gap)` â€” implemented as `ah.gen.climate.model.STATE_NAMES`, fitted by WP2.5 (`climate-fit-report.md`, artifact `climate-l1-f7d4119c7101-s20260726` pinned by content SHA-256 in `ah/gen/joinery/assemble.py`), consumed by L2 (`COVARIATE_NAMES` over the states) and by the waypoint layer, and carried on every emitted ensemble since WP2R.4's generator-output contract.** Filed 2026-07-31 under WP2R.8's close-by-content resolution: STEP2R-CONSOLIDATION-PLAN Â§WP2R.8 calls this decision "D5", an id this register had already given to the structural-parameter vintage default (see the platform-table note above). | none |
| S2-HOLDOUT-NOT-SPENT | Whether to spend the one-shot holdout at G2, given that the sealed document never specified what the evaluation computes | CLOSED | **NOT SPENT. The holdout remains unspent and its one permitted use is intact.** Decided 2026-07-31 by the project owner, recorded as `AM-2026-07-31-002` (`protocol_change`, `post_hoc: true`) because the sealed splits block asserts the holdout "is spent EXACTLY ONCE, by WP2.11" and that is no longer an account of events. **The defect behind the decision:** the seal pins the SPAN, the GUARD, the at-most-once budget and an absolute no-tuning prohibition, and never says WHAT THE SINGLE EVALUATION COMPUTES; `STEP2-GENERATOR-PLAN` Â§WP2.11 says only "once, logged, never repeated". **None of `multi_seed_decision_rule`'s four clauses reads the holdout** â€” all four run on the WP2.10 grid against a train+validation reference â€” so the verdict is fully determined without it. **Why declining is conservative rather than negligent:** any procedure run at WP2.11 would have been authored at WP2.11, with the grid, both severe arms, the head-to-head and the restricted-window re-run already visible. That is the forking path the seal exists to close, applied to the one resource that cannot be restored. A number produced that way cannot be distinguished by any reader from "the author chose a procedure that showed what they wanted". Not spending costs the gate nothing and leaves the resource worth what it was. **What a later gate must do to spend it:** write the evaluation down first â€” what is generated, at what size, from what conditioning state, scored on which metrics against which realizations, with what consequence â€” seal that specification BEFORE the campaign it judges, then mint the token. **Both readings of "spent exactly once" are on the record**: as REQUIRING a spend (so this is a dated departure, which the amendment legitimizes) or as BOUNDING spending at one (so zero conforms). The stricter reading is why it was filed as an amendment rather than left as a register row. `G2-EVIDENCE.md` must state plainly that the holdout was not spent and why. | none |

## Step 3 decisions (STEP3-TRANSLATION-PLAN / KICKOFF-STEP3)

| ID | Decision | Status | What was recorded | Blocks |
| --- | --- | --- | --- | --- |
| S3-G3PRE-SEAL | The G3-pre pre-registration: mint approval and what it covers | CLOSED | **APPROVED and MINTED 2026-08-01** (`pre-registration-g3.lock`, `sha256:d21910da5914â€¦`, 13 hashed files). Approved by the project owner as reviewer of record, who commissioned the work and is NOT independent of it â€” stated per the S2-REVIEWER-OF-RECORD discipline. **W11 attendance is NOT evidenced here**: MPP-A1 asks for the independent reviewer at the pre-seal exercise, KICKOFF-STEP3 Â§2 restates it, and the owner's approval did not state whether W11 attended â€” recorded as an open fact rather than implied either way; if W11 review happens after the fact, its outcome joins this register by a dated row, and if it never happens, this row is the honest record that the gate's effective-challenge element is owner-only, exactly as G2's was. **What the approval covers**: the pooling rule (per modeled sleeve, owner's granularity decision), the authored severities (enforce 95s / report 99s), K=4 carried from D6 into a new context, the episode tolerances and their cited anchors, the gate rule's named-limitation clause, and PM sleeves sealed as structurally unavailable. **What it does not cover**: any claim that the thresholds are the right thresholds â€” they are the sealed ones, which is the point; and no Step 3 result exists yet for them to have been tuned toward, which is the entire value of the date on this row. Sealed before any WP3.2 estimation or cashflow code, per Delta 6. | WP3.2+ unblocked |

**D6 status after WP2.3.** The platform table's `D6` (stylized-fact thresholds) is no
longer "all `todo`": `pre-registration.yaml` is **sealed** as of 2026-07-26 with real
thresholds. D6 stays `OPEN` because the seal was taken under the plan's
*pre-authorization* branch, not its ratification branch â€” the human gate reads "merges
only after the D6 workshop ratifies (**or** with provisional values pre-authorized in the
amendment log)", and the owner took the second. `governance/amendment-log.yaml`'s first
entry, `AM-2026-07-26-001` (`post_hoc: false`, dated 2026-07-26), names exactly what is
provisional and what D6 must ratify: `ensemble_size.n_paths`,
`bootstrap_v1.mean_block_months`, the `nn_distance_*` margin factor, the
`elicitability_score` bound, the `var_95`/`es_95` three-fold width, and `K = 4` for the
per-name absurdity bounds. `AM-2026-07-26-002` adds the one item that entry omitted â€”
`tuning_protocol.trial_budget_per_system: 40`, which Â§WP2.8 requires to exist but does
not specify, and its selection-criterion tie-break. `AM-2026-07-26-003` records the
campaign-vintage move and the full re-derivation (see `S2-CAMPAIGN-VINTAGE`);
`AM-2026-07-26-004` records the re-seal's authored and re-taken values, including
`tuning_protocol.selection_lambda: 1.0` â€” a number Â§WP2.8 requires to be pinned, which
the first seal referred to (â€œthe config's own sealed lambdaâ€) without ever sealing.
Everything else in the file is a decision rather than an estimate and may be revised
only by a further amendment.

R5 and J3 close with `active_blocks: [global, us]` sealed in `pre-registration.yaml` --
i.e. neither FX nor the UK block is active in the v1 campaign. R5's resolution **moved**
from Step2R Â§WP2R.4 (where STEP2R-CONSOLIDATION-PLAN originally scoped it) to WP2.1b,
because the FX decision sits inside the pre-registration seal's blast radius and had to
be settled before WP2.3, not after Step 3 planning begins. STEP2R-CONSOLIDATION-PLAN.md
Â§WP2R.4 has been updated to reflect this (dated note there points back here).

**Footnote -- "D9" is overloaded too (added at WP2R.8, 2026-07-31).** This file's D9 is
the **compiler model + prompt policy**. The Phase A / liquidity-spine document set
(`Instructions/WP3.9-liquidity-spine-v0.2.md` Â§14, `Instructions/STEP3-amendment-A1.md`
Delta 5, `Instructions/STEP5-amendment-A1.md`) uses "D9" for the **decision-alpha /
walk-forward evaluation ledger** â€” the thing `STEP5-DECISION-EVALUATION-PLAN.md` Â§WP5.1
calls "walk-forward per D9". Same resolution as the D4 footnote below: neither renames
the other; "D9" in a Phase A or Step 5 document means the decision-evaluation ledger,
"D9" in this file's platform table means the compiler policy.

**Footnote -- "D4" is overloaded.** The `D4` in the platform table above (this file's
first table) is the **correlation regime model** decision. STEP2-GENERATOR-PLAN Â§WP2.3
and WP2.1b use "D4" for an unrelated thing: the **benchmark-strategy set** that VaR/ES
tail fidelity is computed on. To avoid ambiguity this section's row for the
strategy-set decision is filed under the id `S2-D4`, not `D4`. Both decisions are real,
both are named "D4" in their respective source documents, and neither renames the
other -- a later reader who sees "D4" in a Step 2 document should understand it means
the benchmark-strategy set, and "D4" in this file's first table means the correlation
regime model.

**CAMPAIGN-4 GATED OUT (owner decision, 2026-08-14).** The campaign-4 design
(`docs/superpowers/specs/2026-08-13-campaign4-design.md`, approved with its
Phase-0 amendment the same day) never reached a seal: the Phase-0
development gate returned NO-GO â€” conditional delivery fails 2 of 3
scenarios under every conditioning convention tested (the L2 regime label
pins; the trajectories beneath do not follow), and the only tail fix that
met the dev bar collapsed the clause-(i) objective edge ~14x (the edge and
the excess co-movement trade off roughly linearly in the sampling knob).
The owner accepted the NO-GO and shelved the apprentice; reopening
conditions (three named numbers, all architecture-level work) are recorded
in the design note. SHIP-BENCHMARK stands; bootstrap-v1 remains the
product engine. All Phase-0 numbers are dev-grade under provisional
definitions; no sealed file was touched; no campaign-4 block ever entered
`pre-registration.yaml`.

**SM-10 SMOOTHING MODEL â€” ROUTE (a), the engine filter (owner decision,
2026-08-14).** The translation-layer audit
(`docs/superpowers/specs/2026-08-14-translation-layer-audit.md`, F1) found
that the sealed smoothing kernel (`mappings/smoothing-kernel-v1.0.yaml` +
`ah/port/smoothing.py`) has never run on a player-facing path: the reported
plane is produced by the toy engine's own filter throughout. The owner
declared the engine filter the product's smoothing model and recorded the
DN-5 SM-10 divergence rather than routing the kernel live. Grounds: the
filter is validated on its own evidence (ER-10 catch-up invariant, console
catch-up row, per-seed console walks) and is what every shipped score and
committed fixture was built against; routing the kernel live is a ~3-day
release event that moves every engine number again, and the seal does not
cover the per-sleeve-to-aggregate collapse it would require. Full record,
including what the shipped path forgoes and the cost of reopening:
`docs/engine-realism-register.md` ER-11. NO sealed file was touched â€” the
kernel artifact is inside the G3 lock and is unchanged; `ah/port/smoothing.py`
is in no lock scope, and no `ah/eval/` module imports it, so no judged number
could move. The latent 4.47x double-counting defect the audit found in the
unused applier was fixed under the same decision (branch
`f1-01-smoothing-degenerate-theta`); it had never affected a committed number.

**F3 CROSSOVER BAND â€” ACCEPTED AND RECORDED (owner decision, 2026-08-14).**
The translation-layer audit found the calls/distributions crossover running
past its declared 4-8 year band: median 8.875 on the 1974 decades with 3 of 5
seeds never crossing inside the decade, and 8.75 on stagflation with 8 of 20
seeds outside. The owner accepted it rather than opening a design review of
distribution pace. Grounds: the mechanism is the tier-1 stress linkage working
as designed (distributions throttle in drawdowns, and the worlds we ship are
long drawdowns), and age-9 DPI lands inside its own band -- the capital
arrives late, not never. The band was drafted for AVERAGE conditions and the
shipped world class is not average.

**The cost of the acceptance, stated so it is not rediscovered as a surprise.**
A band that flags on 8 of 20 seeds is no longer discriminating. The console
will keep flagging `crossover_years`, and that flag should now be read as
"this world distributes late, as stressed worlds do" -- not as an anomaly to
chase. The band value is deliberately UNCHANGED rather than widened: tuning it
to stop flagging would destroy the only signal it still carries, which is the
comparison between worlds. What this acceptance gives up is the ability to
notice a world that distributes late for some OTHER reason; that case will
look identical on this surface. If distribution pace is ever reviewed on its
merits, this entry is the thing to reopen.

**F3 RE-MEASURED AFTER ladder-01, ACCEPTANCE UNCHANGED (2026-08-14).** The
staggered seed ladder (ER-12) landed hours after F3 was accepted, and it moves
the institution the F3 numbers were measured on â€” so the measurement was
repeated rather than assumed to carry. `crossover_years` reads **8.750 median,
p10-p90 8.250-9.000, 8 of 20 seeds outside the 4-8 band: identical to the
pre-ladder figures**, so the acceptance above stands on its own evidence. The
J-curve crossover is set by the in-play commitment programme, not by the shape
of the opening book. Two neighbouring statistics DID move and are recorded in
ER-12, not here: `peak_unfunded_ratio` cleared its band (1.288 -> 0.716) and
`linkage_bite` became uncomputable under annual wind-ups.

---

## D-SC series â€” the stress-scenario compiler's reserved decisions (2026-08-15)

Raised by the stress-compiler design v0.2 (`docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md` S11) and the Phase 0 attribution note. Owner rulings, 2026-08-15:

**D-SC-1 â€” persistence-rule parameterisation: DECIDED, P1+P2 composed.**
The owner adopted the recommended form: P1 (severe re-entry â€” every block
starting inside a stress segment enters under that segment's percentile,
which IS the shipped sampler's behaviour, pinned by
`test_restarts_land_in_the_severity_pool`) composed with P2 (declared
stress coverage â€” the scenario declares stress occupying most of the
decade, precedented on Japan 1990-2003 and US 1966-1982 in real terms).
P3 (decade-statistic constraint) is HELD BACK until its rule-1 policing is
designed. Consequence: a deeper scenario is authored as a new declared
shape with its precedent, pre-registered by commit order, measured once â€”
the stress-02 work package. Basis: the stress-01 adequacy ladder read 0/20
with depth -29.9% vs cited -48/-50% precedent, recorded untuned as the
spec's reading 1 (rule milder than precedent; the S4.3(d) persistence gap).

**D-SC-4 + JST scope â€” PARKED, 2026-08-15.** The international-panel
licensing question and the upstream JST non-commercial scoping are
deliberately deferred; no Counsel engagement now, no international data
enters the repo. Revisit when depth beyond the US panel's -42.6% worst
twelve months is actually wanted. (D-SC-2 premise compiler and D-SC-3
reverse-search timing remain open, unscheduled.)

**Narration âš– items N-m / N-u / N-d â€” BUILD NOW, COUNSEL AT PRODUCT.**
The three counsel-dependent narration positions (real public institutions
named, real individuals never; verdict tags on two axes with no portfolio
axis; dot-plots calibrated to real projection error) proceed on their
recommended forms. Counsel review is scheduled for when a narration
product exists to review, not before. The recommendations are unchanged
from the register A3 triage; this entry converts them from blocked to
building.

---

## Narration bucket-A ratifications (2026-08-15, owner)

The six open decisions from `docs/documentation-register-A3-narration.md`
S2, ratified on their recommended positions in one batch:

| # | Decision | Ratified position |
|---|---|---|
| N-c | Does the paper ever report the true plane? | **No, in every arm.** The paper sees what a publication sees. Guards DN-6 arm-A integrity |
| N-h | Front page replaces the outcome card | **Yes.** Same renderer, same cache key |
| N-n | Quarterly slate as the turn unit, monthly tape retained | **Yes.** Refines A2 decision 3 |
| N-ac | Board power | **Soft, with early termination** (formalises the S7 instruction) |
| N-ai | Tier-2 narration paid; Tier-1 compilation free | **Yes** |
| N-r | Rationale agent as a fourth LLM role, own boundary note and gate | **Yes, M5** |

(The three counsel-dependent items N-m / N-u / N-d were already ruled
build-now-Counsel-at-product on 2026-08-15, recorded above.)

**Workbench input-contract ruling (2026-08-15, owner):** the narration
workbench's required `l1_state` series stays REQUIRED as the task
specifies. Resolution of the conflict with shipped bootstrap worlds (which
carry no L1 layer): **a hier-flow-v1 world is stood up first** â€” the
G2-promoted generator, whose ensembles carry the slow-state layer â€” and
the workbench's first world is that one. Demoting l1_state to optional
was considered and declined.

---

## SM-RULING-A â€” external-series validation of an authored coefficient (2026-08-15, owner)

Raised by `AM-2026-08-15-001` Â§3.3 (`docs/superpowers/specs/2026-08-15-inflation-passthrough-credit-loss-design.md`). Owner ruling, 2026-08-15, **precedent-setting**:

**SM-RULING-A â€” RATIFIED.** External-series comparison of a pre-committed
authored coefficient against published prints is **validation evidence, not
holdout access**, under four conditions and no wider:

1. **External series only** â€” never a catalog factor read. The compared series
   must sit outside the sealed splits entirely (NPI, in the raising context).
2. **The compared value is committed and hashed before the check runs.** A
   coefficient that could still move is not being validated, it is being fitted.
3. **One execution, result recorded verbatim** in the report â€” including a
   result that embarrasses the coefficient.
4. **Never a calibration input.** A failed check is disclosed and the
   coefficient is revisited only through a further dated amendment whose stated
   trigger is the disclosed failure. Re-running until it passes is the failure
   mode this condition exists to forbid.

Rationale recorded: the inflation channel is too material to the product to
ship unchecked, and the alternative â€” shipping an authored pass-through
coefficient with no external comparison at all â€” is worse than a bounded,
pre-committed one-shot check.

**Scope note.** This ruling is precedent for future authored parameters under
the same four conditions and **no wider**. It is not a general re-opening of
the holdout discipline; the Step-2 holdout was spent at WP5.6 and nothing here
restores it. Condition (1) is what keeps the two questions separate.

**Still âš‘ (unratified until a named owner release event):**

| âš‘ | Item | Upgrade path |
|---|---|---|
| C1 adoption | inflation pass-through term â€” `pm_infra` 0.6, `pm_re_value_add` 0.3, both `chosen` | NPI NOI-growth fit via NCREIF query-tool export (membership; data register P1) â†’ relabel `measured-external` by amendment |
| C2 adoption | credit loss term â€” Î¸ per the declared CDLI match rule, `chosen` | Albourne derived-measures interface (loss dispersion) |
| `re_core` / `infra_core` forms | declared but unparameterized (Tier B, evergreen) | parked until those sleeves are parameterized; links to the Albourne coefficient request Â§2a |

Adoption of C1 or C2 is a named owner release event (`ah/port/mapping.py`
`ARTIFACT_PATH` bump + `world_id` block move for touched presets) â€” the
Campaign R1 rule â€” not a side effect of a report existing.

## D-SP-4 â€” RULED 2026-08-16: PARK â€” superseded same day by D-SP-6

Owner ruling: the spine architecture is parked with its two-round sealed
record (spine-01 f988952, spine-02 deac7fc). The deep repair (L2
generation-time hazard link; B4/B2/B6-weak-transmission residue) is NOT
funded now. Re-opening requires a new owner decision and starts from the
logged v3 judge defects (B1 anti-test, B6 outcome-event match) plus
B5 clustering-aware variance. The product line proceeds on the plain
stress compiler (memo Path A); the disclosure work is the live item.

## D-SP-6 â€” RULED 2026-08-16 (evening): FUND THE DEEP REPAIR (spine v2, stage 1)

Owner ruling, in their words: "go on the engine work, include the
allocation tests." The re-opening decision D-SP-4 reserved is hereby taken;
the deep repair is funded as a staged campaign.

- **Scope (stage 1 only):** the generation-time hazard link (climate states
  drive regime transitions DURING sampling, replacing the post-hoc overlay),
  recovery-duration refit to the historical event chronology, and
  join-constraint tightening. The flesh stays selection-only (R1 stands).
  Model-implied conditional means ("stage 2") and any L3 generator are
  explicitly NOT funded by this ruling.
- **The exam gains two allocation bars** (owner's purpose statement: the
  product tests robust asset ALLOCATION, not lever timing): (i) the
  inflation-hedge spread test â€” real assets vs nominal bonds conditioned on
  the spine's inflation state, banded by the historical episodes; (ii) the
  stockâ€“bond correlation regime-flip test. Both defined on ASSET returns,
  never portfolio outcomes â€” rule 1 (severity never tuned to portfolio
  results) is reaffirmed and is the reason for the asset-level definition.
- **Standing communication rule attached** (owner, same session): plain
  language in owner-facing reporting; every sealed pass/fail bar carries its
  justification â€” what real quantity anchors it and why the tolerance is
  the size it is â€” written before results exist.
- Week-1 deliverables before any fitting: estimation dataset (event
  chronology, transmission lift with its confidence interval, allocation
  episode bands), v3 judges with anti-test sweeps run on the judges
  themselves, sealed prereg. Prior-round verdicts stay frozen; v1/v2 judges
  remain byte-pinned.
- ER-14 (inflation does not reach private markets) is acknowledged as the
  second leg of the owner's allocation thesis â€” surfaced to the owner this
  session, not yet scheduled; batching with F5 remains the standing
  recommendation.

## D-SP-7 â€” RULED 2026-08-16: RANKED PLAY PARKED

Owner ruling, in their words: "Park the ranked sessions for now, we're not
remotely ready for that." The play surface is practice-only until further
notice. Implemented in `app-open-02` as a fenced bypass (one commented
constant in `app/src/App.tsx` plus one `if` branch; the RankedSetup screen,
its tests, the server's ranked contract, the leaderboard store, and the
digest-eligibility machinery are all intact and green). Un-parking is a new
owner decision: delete the bypass and restore the book screen's ranked-note
copy. The rebuilt-ladder ranked-eligibility question (Task 7 flag) is
mooted while this stands and revives with it.

## D-SP-8 - RULED 2026-08-17: FUND THE CURVE-FEEDBACK MECHANISM (narrow stage-2 scope)

Owner ruling ("1" to the two options presented after the week-2 FRONTIER
result): the season-to-curve feedback loop is funded - the yield curve
must respond to the cycle (steepen as seasons contract, invert as
expansions age), the one mechanism the frontier diagnosis identified as
jointly blocking the transmission and ordering bars. Scope is THIS
mechanism only; the full stage-2 program (model-implied conditional means
for asset returns) remains unfunded. Bounded at roughly a week: model
term + refit + re-run of the sealed in-model verification.

Carried obligations: the sealed-construct ambiguity (premise-conditioned
vs unconditional measurement arm for the causal bars) is resolved by
LOGGED AMENDMENT before any re-measurement, on like-for-like grounds
argued independently of either arm's current readings; the week-2
post-hoc specification disclosures stand as disclosures (owner did not
require a re-seal). Executed as `AM-SPV2-2026-08-17-001` (`181c208`),
logged in `spine-v2-prereg.json`'s own `amendments` block: T1 and O1
judged on an unconditional 50-decade batch, no threshold changed, no
hashed file edited, post-hoc-flagged and disclosed as reading more
favourably on both bars.

- **CLOSED 2026-08-17 at the second frontier.** Verdict:
  `docs/superpowers/specs/2026-08-17-spine-v2-results.md` (corrected per
  the 12-finding integrity review, section 8). D1-D4 PASS everywhere;
  T1 a QUALIFIED PASS (1.9131 in band, but the clean counterfactual shows
  the estimator - not the feedback - did the work, and the clearing arm's
  curve is 93.9% exogenous noise); O1 FAIL under the sealed construct
  (0.5118 vs floor 0.5181) - and the construct carries a decade-edge
  censoring asymmetry (0.0124) twice the shortfall (0.0063), so
  "unreachable" is withdrawn; A1/A2/R1/R2 NOT MEASURED (the flesh was
  never built). Housekeeping at close: soft labels stay sensitivity-only,
  the amendment stands with its disclosure, the post-hoc spec choices
  stand as disclosures. The stage-2 coupled-system spec is committed as
  D-SP-9 PROPOSED, not taken.
