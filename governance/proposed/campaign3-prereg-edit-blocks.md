# Campaign-3 seal event — prepared `pre-registration.yaml` edit blocks

*Prepared 2026-08-09 evening while waiting on the H.10 release, so tomorrow's
seal event is paste-fill-seal, not composition. Companion to
`PROPOSED-AM-campaign3-prereg.md` (the reviewed intent); THIS file carries the
exact text. Placeholders in `<ANGLE_BRACKETS>` are the only things tomorrow's
run can supply: the vintage id, the coverage table, and every band number.
Nothing here is applied yet — the sealed file is untouched and all three locks
verify against the committed tree.*

## Order of operations (updated: two discoveries tonight)

1. **AQR commodities intake FIRST** (new — K2 needs the series in the vintage
   before the reference run): intake `aqr.cmdty_ew_excess` (and `ew_spot`,
   diagnostics-only) from the workbook at `data/aqr/` through the standard
   manual-intake path (the PriMaRS precedent, AM-2026-08-08-001). Raw AQR
   values enter the LOCAL vintage store only — `data/` is gitignored and the
   REG licence forbids committing them; only derived statistics and bands are
   committed. ATTRIBUTION rides every artifact.
2. Clean refresh (waiter fires ~13:30+ PT) → `<C3_VINTAGE_ID>`.
3. `scripts/compute_campaign_reference.py`: constants → `<C3_VINTAGE_ID>`,
   seed 20260726 kept, other params unchanged → run → `reference-run.json`.
4. Apply the blocks below; fill placeholders from the run.
5. Append the campaign-3 amendment; **re-seal ALL THREE locks** (factors.yaml
   is hashed by main+G3+G5 — the twice-learned lesson); one commit.
6. Full gate → merge `--no-ff` → push on green. Training still gated on K4.

## Block 1 — `campaign_vintage_id` (line ~185)

```yaml
campaign_vintage_id: "<C3_VINTAGE_ID>"
```

Add above it, following the vintage-move precedent comment:

```yaml
# CAMPAIGN-3 (AM-<C3_AM_ID>): the vintage moved deliberately -- the campaign
# restart the paragraph above prices in. The 2026-08-02.4 record is the
# campaign-2 record and is closed; this vintage is the first to carry the
# extension donors (VXO, CPF3M, CP3M, CP3M_NBER, TB3M_SEC, GS1, GS3) and the
# AQR commodities series, so the extended reads of AM-2026-08-09-003 engage
# here for the first time.
```

## Block 2 — `reference_run` (lines ~255–348)

- `vintage_id: "<C3_VINTAGE_ID>"`; `seed`/`n_resamples`/`level`/
  `block_length`/`resample_length` UNCHANGED (comment: "seed kept so any
  factor whose data is genuinely unchanged reproduces its campaign-2 band
  bit-for-bit; every band that moves is attributable to the data").
- `missing_factors: []` — commodities leaves the list (K2 sources it).
  Update the explanatory comment: commodities RESTORED AT CAMPAIGN-3 via
  `aqr.cmdty_ew_excess + french.rf` (expr: add, the equity_mkt pattern);
  RFR-8's "no free connectored series" reason is discharged by the REG-
  licensed manual intake, superseded state kept for the record.
- `uncomputable_d4_strategies: []` — commodities was the last blocker for
  both (hy_spread restored at campaign-2); eqw_factors and endowment_proxy
  become computable. The "LIVE condition" paragraph fires exactly as written
  — quote it in the comment.
- `coverage:` — VERBATIM from the run. Expected firsts (verify, don't
  assume): cape_v 1881-01, cpi 1913-01, ig_spread 1919-01, hy_spread
  1919-01, **hqm_curve 1919-01**, equity_mkt/smb/hml 1926-07,
  **commodities 1926-07**, mom 1927-01, **policy_rate 1934-01**,
  **funding_spread 1934-01**, **equity_vol 1953-04**, **ust_2y 1953-04**,
  **ust_10y 1953-04**, **fx_usd 1953-04**. Every bolded first is an
  extension engaging; if one comes back at its campaign-2 value the wiring
  did not engage and the run stops there.

Add at the end of `reference_run:`:

```yaml
  # THE PINNED EQUITY-VOL ARTIFACTS (AM-2026-08-09-003). equity_vol months
  # before 1986-01 are MODEL OUTPUT: the ONE pinned HAR draw, served from
  # package data, never regenerated at read time. Bands over equity_vol
  # therefore rest partly on model months; the K3 masked ablation cell
  # measures that dependence and har_masked_ablation states the demotion
  # criterion.
  pinned_artifacts:
    equity_vol_pinned_draw:
      path: src/ah/data/equity_vol_pinned_draw.json
      sha256: 53a378a49bfa58f9457698473457f526298efe5454ca9187ff2c35ca3fb50178
      seed: 20260809
      span: ["1953-04", "1985-12"]
    equity_vol_backcast_provenance:
      path: artifacts/volext/equity-vol-backcast-provenance.json
      sha256: f0535582c061cc60ea8605aa9085d457b27dbc12af5e4718aed557146284fc92
```

## Block 3 — `thresholds` (lines ~2413+)

Recipe UNCHANGED and restated in the section header comment: every entry is
`band_midpoint -+ 4 * band_half_width` on the CAMPAIGN-3 reference run's own
band, band quoted per entry, side sealed `null` where 4 half-widths leaves
the structural range (excess_kurtosis min -2; correlations/ACF-derived stats
their own ranges; Hill strictly positive), severity `report` per name. Every
existing entry's numbers and quoted band update in place; entries KEEP their
names (no name is added or removed on the strength of seeing the run, except
the commodities family below, which is added because the factor is newly
sourced — the same footing every campaign-2 block addition had).

New: commodities per-name bounds in `blocks.global` and its cross-block
`correlation`/`crisis_corr_lift`/tail-dependence pairs — carried in the
campaign-3 amendment payload in `apply_block_addition` shape (the K2
"block_addition" ratifies as part of this event; verify the machinery accepts
new names into an existing block, else fold them into the main edit with the
amendment payload as the audit record).

New: `thresholds.strategies` entries for eqw_factors and endowment_proxy —
now computable. Same severity posture as the existing three strategies'
entries; numbers from the run.

## Block 4 — `severe_test_protocol.benchmark_exception` (lines ~4345)

Replace with (old text PRESERVED VERBATIM below the marker, ratification
precedent):

```yaml
  benchmark_exception: >-
    RETIRED AT CAMPAIGN-3 (AM-<C3_AM_ID>): bootstrap-v1 CAN NOW RUN THIS
    TEST. Its block_draw_span is 1953-04..2020-12 (AM-2026-08-09-002), which
    contains the excluded decade AND the 1965 start state; the vacuousness
    that grounded this exception is exactly what the extended span closed
    (tests/test_severe_blocks.py::TestTheExtendedPanelReachesTheDecade pins
    the flip). The severe leg is POSABLE FOR BOTH SIDES and no system holds
    an exception. SUPERSEDED G2 TEXT, verbatim, kept as history: bootstrap-v1
    CANNOT RUN THIS TEST. Its block_draw_span is 1990-2020 (see
    bootstrap_v1.block_draw_span_consequence), which contains neither the
    excluded decade nor the 1965 start state, so "exclude the 1970s" is
    vacuous for it and "regenerate from 1965" is impossible. G2-EVIDENCE.md
    must record the benchmark's severe-test row as NOT POSABLE, with this
    reason, rather than as a pass, a fail, or an omission.
  severe_test_criterion: >-
    SEALED WITH THE PROCEDURE, RFR-77's lesson (a procedure without a
    criterion judges nothing). A system PASSES the severe leg iff its
    excluded-decade regeneration keeps EVERY enforce-tier severe statistic
    inside its sealed band over the 1966-1984 comparison window. A system
    that cannot pose the leg FAILS it -- no exception route exists any more.
    The result reports either way and a failure is a finding, not a tuning
    opportunity (reporting clause above, unchanged).
```

## Block 5 — `multi_seed_decision_rule.benchmark_draw_span_bias` (~4445)

Replace with (old text preserved verbatim as history, same pattern):

```yaml
  benchmark_draw_span_bias: >-
    CLAUSE RETIRED AT CAMPAIGN-3 (AM-<C3_AM_ID>): the mechanism this clause
    disclosed is GONE -- bootstrap-v1 resamples 1953-04..2020-12, so both
    sides of the head-to-head see 1973-74, 1987 and the stagflation decade,
    and no common-window restriction is required. REPLACED BY
    proxy_share_disclosure, the asymmetry the extended span introduces in
    its place. SUPERSEDED G2 TEXT, verbatim, kept as history: [FULL ORIGINAL
    CLAUSE TEXT, UNEDITED -- paste from the sealed file at apply time].
  proxy_share_disclosure: >-
    THE EXTENDED SPAN'S OWN DISCLOSED ASYMMETRY, replacing the retired
    draw-span bias clause (AM-2026-08-09-002's disclosure, promoted to a
    sealed reporting requirement). Every verdict table computed over the
    extended span MUST report, per factor, the proxy share of the months
    that produced it -- and for equity_vol, the HAR share separately from
    the VXO share, because HAR months are MODEL OUTPUT (owner ruling D6
    admitted them as span data; this clause is the standing price). Neither
    number gates -- the sealed rule is the sealed rule -- but a verdict
    whose winning margin concentrates in high-proxy-share months must say
    so in G2-EVIDENCE.md's campaign-3 successor, and the K3 masked cell
    (har_masked_ablation) is the measured check on the equity_vol case.
  har_masked_ablation: >-
    RULING K3, operationalized. The ablation grid carries a MASKED variant
    of the promoted-family system: identical architecture, hyperparameters
    and seeds, with equity_vol treated as MISSING before 1986-01. The
    included-vs-masked comparison is reported in the campaign evidence.
    DEMOTION CRITERION, sealed before any training run: the HAR-included
    variant is DEMOTED to report-only -- the masked variant becomes the
    criterion-bearing configuration -- if (a) masking flips ANY enforce-tier
    clause of this decision rule for that system, or (b) the pooled
    decision-alpha difference between included and masked exceeds half the
    sealed beats-margin (|mean_s(d_s)| of clause (i)'s pooled route). A
    demotion is a finding about learning-from-our-own-reconstruction and
    reports as one.
```

## Block 6 — `ablation_systems` / `ablation_rule` (~4242)

```yaml
ablation_systems:
  A: {id: structure-only, description: "L1 climate + L2 regimes + Gaussian residuals", neural: false}
  B: {id: neural-rollout, description: "L3 chained directly, no waypoints, no L1 anchor", neural: true}
  C: {id: neural-only, description: "L3 blocks + naive chaining, no L1", neural: true}
  D: {id: full-hierarchy, description: "the complete four-layer hierarchy; ONE sampler at campaign-3, hier-flow-v2 (hier-diffusion DOES NOT RACE -- the flow family was the promoted line and a diffusion retrain spends the K4 budget without a decision it would change; racing it later is a dated amendment)", neural: true}
  E: {id: bootstrap-v1, description: "the frozen benchmark on the EXTENDED span (AM-2026-08-09-002)", neural: false}
  F: {id: har-masked, description: "system D's architecture with equity_vol MISSING pre-1986 (ruling K3; see multi_seed_decision_rule.har_masked_ablation)", neural: true}
ablation_rule: >-
  Exactly these six, no more (CAMPAIGN-3, AM-<C3_AM_ID>: F added by ruling
  K3, sealed BEFORE any training run -- the "sixth arm after any result is
  seen" prohibition below is untouched because no result exists). Neural
  systems (B, C, D, F) run >= 3 TRAINING seeds each; deterministic systems
  (A, E) run >= 3 SAMPLING seeds each. Every system is evaluated on the
  identical splits, the identical campaign vintage, and the sealed criterion
  ensemble size. ABLATION.md is generated, not hand-assembled, and shows
  cross-seed dispersion per metric. Adding a further arm after any result is
  seen is a dated, post-hoc-flagged amendment and must be reported as one.
```

## Block 7 — K1, new top-level section (place after `splits:`)

```yaml
# --------------------------------------------------------------------------- #
# future_accruing_holdout -- ruling K1. The one-shot historical holdout was
# SPENT at WP5.6 and no past data can be un-seen; the future is the only
# place a holdout can still come from. Sealed here so the rule predates the
# data it protects, which no historical holdout can ever claim again.
# --------------------------------------------------------------------------- #
future_accruing_holdout:
  accrual_start: "2026-09-01"   # data first PUBLISHED after 2026-08
  earliest_read: "2029-01-01"
  protocol: >-
    Data first published after 2026-08 is UNTOUCHABLE by any fit, tuning
    run, reference derivation or verdict until 2029-01 at the earliest.
    ONE READ, EVER, in WP5.6's protocol shape: the evaluation spec is
    written and sealed BEFORE the read; results publish both ways; nothing
    re-runs. Monthly refreshes continue to STORE accruing data (the vintage
    machinery is append-only and storage is not reading); the read surface
    for every campaign remains train+validation, whose end does not move.
    Operationalizing the fence (a splits-layer accrual boundary and its
    leakage-guard test) is a sealed requirement on the work package that
    first touches post-2026-08 data, in the same posture as
    criterion_bearing_runs_only's requirement on WP2.11.
```

## Block 8 — `decisions:` additions (~2975)

```yaml
  S3-K1-FUTURE-HOLDOUT: {status: SEALED, consequence: "see future_accruing_holdout; the historical holdout remains SPENT and no appeal to it is possible"}
  S3-K2-COMMODITIES-CLOSE: {status: SEALED, consequence: "aqr.cmdty_ew_excess + french.rf sources `commodities` (expr: add); REG licence -- attribution rides every artifact, raw values never committed; eqw_factors and endowment_proxy become computable and carry sealed thresholds"}
  S3-K3-HAR-MASKED-CELL: {status: SEALED, consequence: "ablation system F + multi_seed_decision_rule.har_masked_ablation's demotion criterion"}
  S3-K4-HARDWARE-GATE: {status: OPEN, consequence: "training does not start until the owner picks the host; ~2.2h/flow cell on CPU, grid at 4 neural systems x >=3 seeds; the seal does not wait for this call -- only training does"}
```

(Adapt to the sealed `decisions:` entry shape at apply time — `decision_id`
keys with `status`/`consequence` fields, matching neighbors.)

## Block 9 — `factors.yaml` (all three locks!)

```yaml
  commodities:
    kind: derived
    expr: add
    inputs: [aqr.cmdty_ew_excess, french.rf]
    units: ret
    numeraire: total_return
    notes: >-
      CAMPAIGN-3 (ruling K2, AM-<C3_AM_ID>): AQR "Commodities for the Long
      Run" equal-weight EXCESS return plus the one-month bill -- the exact
      equity_mkt pattern (an excess series restored to the sealed
      total-return numeraire by adding the rate it is quoted net of). Starts
      1926-07 where french.rf starts; the 1877-1926 excess-only era is
      EXCLUDED, never zero-filled (owner ruling C2). REG licence:
      attribution required on every artifact, raw values never committed
      (data/aqr/ is gitignored and a test pins that no committable path
      carries the workbook). Cross-checks and episode readings:
      docs/data/CMDTY-REPORT.md. Supersedes the RFR-8 `unavailable` entry;
      superseded reason kept in the git record.
```

## Block 10 — stale header prose sweep (apply-time checklist)

- Line ~18 of the header ("block_draw_span is still 1990-2020 because
  equity_vol binds it") — verify the ratification already amended it; if any
  stale copy survives, fix it in this event (the claims-sweep discipline:
  same wrong sentence, multiple homes).
- `rationale.d4_commodities_consequence` — both strategies become computable;
  update with the superseded text kept.
- `structurally_unavailable_statistics:` — check whether any entry rests on
  "equity_vol starts 1990" or "no commodities"; update those that fire.
- `claims_with_tests:` — any `covers:` anchor whose quoted line this event
  rewords must move with it, or the claims suite fails the gate.
- `bootstrap_v1.block_draw_span_consequence` "ROUTES OUT" — the route taken
  (extension + ratification) should be recorded as taken.

## Block 11 — code constants at the flip (prepared 2026-08-09 evening)

The split landed ahead of the event (commit e52113f, behavior-preserving):
`bootstrap.CAMPAIGN2_VINTAGE_ID` is the frozen historical id; the three
campaign-2 CHECKPOINT replay surfaces (genconsole decade replays, the
hier-flow-v1 / hier-diffusion-v1 factories) pin it explicitly; and
`campaign_source()` picks its span check per vintage (campaign-2 read →
CAMPAIGN2_DRAW_SPAN; anything else → the live sealed constants). At the
seal event, exactly TWO one-line edits remain, no test edits:

- `scripts/compute_campaign_reference.py::CAMPAIGN_VINTAGE_ID` →
  `<C3_VINTAGE_ID>` (test_prereg's script-agrees test compares it to the
  sealed `reference_run.vintage_id` dynamically — both move in the one
  commit and the test passes untouched).
- `src/ah/gen/bootstrap.py::CAMPAIGN_VINTAGE_ID` → `<C3_VINTAGE_ID>`
  (test_bootstrap compares it to the sealed `campaign_vintage_id`
  dynamically — same one-commit property).

Historical pins deliberately NOT touched, ever: `campaign2_seal_package.py`,
`campaign2_probe.py`, `measure_block_length_window.py`, `flow.py`'s
selection-config note, `splice.py`'s fit-measurement comment,
`test_campaign_r1_generator`'s recorded comparisons — all facts about the
campaign-2 record.

DECISION CARRIED TO THE SEAL, flagged: whether `commodities` joins
`bootstrap_v1.factor_set` / `bootstrap.FACTOR_SET` (K2 says the campaign
sees the factor; the factor SET is sealed in the bootstrap_v1 block and
extending it is part of the same amendment — bands exist either way, the
question is whether the benchmark and the generators emit it).

**RULED 2026-08-10 (owner, pre-seal): YES — commodities joins the factor
set** (`bootstrap_v1.factor_set`, `bootstrap.FACTOR_SET`, and the
hier-flow-v2 training list), in the same amendment. Grounds: `FACTOR_SET`
is the set the battery judges, and the two newly-computable strategies
(eqw_factors 0.20, endowment_proxy 0.10 commodities) are judgeable on
generated paths only if the generators emit the factor; bands-only would
seal thresholds that are structurally unavailable on every ensemble.

## The amendment (payload sketch)

`AM-<C3_AM_ID>` (`protocol_change`, post_hoc false, one commit with every
edit above + all three re-seals): vintage id, reference_run parameters,
"campaign-2 bands are dead letters" statement, the K-clauses by name, both
pinned artifact shas, commodities activation (with its threshold payload in
apply_block_addition shape), superseded digests of ALL THREE locks.
