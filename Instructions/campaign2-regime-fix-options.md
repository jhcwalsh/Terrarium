# Campaign-2 regime-persistence fix — the options, for owner decision

*The one genuine modeling decision in campaign-2. The severe test (WP2.11)
located the defect UPSTREAM of L3: retraining the flow model cannot fix
what the regime layer feeds it. Drafted 2026-08-02; the promotion training
runs wait on this choice; nothing else does.*

## The defect, from G2-EVIDENCE §7–8 (the acceptance targets, verbatim)

1. **Inflation persistence ~half its historical half-life** — simulated
   inflation eras resolve about twice as fast as history's.
2. **1966–84 called a "long inflation era" under half the time** against
   history's every window: the model can visit the regime but cannot stay.
3. **Stagnant decades invented at 0.29–0.75** against a historical
   0.00–0.05 — fake lost decades, an over-mixing signature.
4. Drawdowns understated ~2× (partly L3's, but persistence feeds it: short
   regimes truncate compounding stress).

Whatever option is chosen, THESE FOUR STATISTICS are the fix's acceptance
measures, evaluated by the same battery cells that measured them — no new
yardstick invented for the occasion.

## Option A — duration-explicit regimes (semi-Markov)

Replace the Markov exit (geometric durations, memoryless) with explicit
per-regime duration distributions (e.g. negative-binomial) fitted to the
labeled historical regimes. **For:** targets the defect exactly — the
memoryless exit IS the mathematical reason durations come out short and
eras fragment. **Against:** a structural change to L2's model class:
refit, new artifact, more surface for new defects; sampling code changes.
**Cost:** days (CPU refit + joinery updates + battery).

## Option B — sticky-transition priors (recommended first move)

Keep the architecture; re-fit L2 with strongly persistent self-transition
priors calibrated to NBER/labeled era durations (a hierarchical
persistence prior rather than a hand-set constant). **For:** minimal
change — same model class, same sampling path, one refit; directly
raises expected durations; measurable against the four targets within a
day. **Against:** fixes MEAN duration but may not reproduce the long-era
tail (a 15-year inflation era needs more than stickiness); if the
defect's root is memorylessness, B under-delivers and we escalate.
**Cost:** hours.

## Option C — era-scale coupling to the climate layer

Condition regime transitions on L1's slow states (pi_star, r_star, ...)
so long eras EMERGE from slow-moving fundamentals rather than being
memorized durations. **For:** the most economically honest account — eras
last because their causes last. **Against:** touches the L1/L2 joinery
contract and the waypoint layer; the largest blast radius and validation
burden; research-grade work inside a delivery campaign. **Cost:** a week+.

## Recommendation

**B now, A if B misses, C recorded for the research track.** Run B's
refit and score the four targets; if persistence and era-calling clear
but the long-era tail still fails, escalate to A (the refits share the
duration-fitting groundwork). Either path lands behind the campaign seal
with the four acceptance statistics pre-stated in it. C goes to the
research backlog with this memo as its record.

**DECISION (owner, 2026-08-02): B then A if needed** — verbatim 'B then A if needed'. Option B's refit proceeds immediately; the four acceptance statistics above are the escalation trigger; C stays on the research backlog with this memo as its record.

---

*Not investment advice.*


---

## DIAGNOSIS UPDATE (2026-08-02, post-decision, pre-implementation)

The mechanism is NOT where the options above located it. Traced:

1. **L1 is healthy**: trend inflation's fitted half-life is ~10 YEARS
   (climate-fit-report: hl_pi median 9.6y, 5%..95% = 5.9..15.5y). The slow
   state wanders on exactly the decade scale history demands.
2. **L2 is already semi-Markov** (NegBin sojourns, priors.yaml) — the
   memo's Option A mischaracterized the current architecture. Fitted
   sojourns at z=0 look plausible (EXP 14.7m, REC 8.5m).
3. **The defect is L3 CONDITIONING ATTENUATION**, measured at WP2.8
   (artifacts/wp28/ig-spread-diagnosis.md §4: "every channel damped") —
   the generated monthly factors under-respond to the L1/L2 conditioning
   and collapse toward the unconditional mean, so a 10-year pi* trend
   becomes a 30-month generated half-life. The flow arm's classifier-free
   guidance was built as the countermeasure, but the SEALED tuning
   criterion (gen + D4 aux) never rewarded era-scale persistence, so the
   search had no pressure to select strong guidance.

**The decided sequence (B then A) maps onto the true mechanism as:**

- **B' (cheap lever first)**: a GUIDANCE SWEEP on the incumbent
  checkpoint — sample at guidance_scale ∈ {1.0, 1.5, 2.0, 3.0}, score the
  four acceptance statistics per level. Sampling only, no retrain. If
  persistence recovers at some level, the campaign pre-states that level
  in its seal as a config choice (legitimate: chosen before the
  promotion seal, against pre-stated statistics).
- **A' (structural, if B' misses)**: residual parameterization — L3
  generates DEVIATIONS around the L1-implied factor means so trend
  tracking is structural rather than learned; retrain required (cheap:
  ~3.5 min/run per the probe).

The owner's B-then-A intent (cheap lever first, structural second) is
preserved exactly; only the mechanism's address changed. The four
acceptance statistics are unchanged and remain the only yardstick.

---

## B' RESULT (2026-08-02): MISS — escalation to A' fires

Sweep executed (scripts/campaign2_guidance_sweep.py, 512 decades x 120
months per level, sample seed 20260802, promoted flow checkpoint seed
index 1; results at artifacts/campaign2/guidance-sweep-results.json,
non-criterion-bearing):

| statistic | history | g=1.0 | g=1.5 | g=2.0 | g=3.0 |
|---|---|---|---|---|---|
| cpi.long_inflation_era_frequency | 1.000 | 0.396 | 0.361 | 0.356 | 0.314 |
| cpi.mean_reversion_halflife (months) | 61.2 | 29.4 | 27.6 | 26.1 | 23.8 |
| lost_decade_frequency (equity) | ~0.00-0.05 | 0.365 | 0.365 | 0.369 | 0.375 |
| equity_mkt.drawdown_median_depth | 0.069 | 0.045 | 0.057 | 0.068 | 0.100 |

Guidance moves persistence MONOTONICALLY THE WRONG WAY: half-life falls
29.4 -> 23.8 and era frequency falls 0.396 -> 0.314 as the scale rises.
Mechanism: classifier-free guidance amplifies the WITHIN-BLOCK conditional
response (hence drawdowns sharpen — 0.068 at g=2.0 matches history's
0.069 almost exactly, overshooting at 3.0) but adds no era-scale memory;
sharper monthly responses mean faster mean-crossings, i.e. SHORTER
measured half-lives. B' is the wrong lever for persistence by
construction, not by tuning.

Per the recorded decision (B then A if needed): **A' — residual
parameterization around the L1-implied factor means, with retrain —
proceeds now.** Secondary finding preserved for the A' acceptance run:
guidance ~2.0 is a candidate drawdown-depth corrector to re-measure on
the A' checkpoint (it may become unnecessary if persistence restores
compounding stress). The commodities lost-decade cell returned nan at
every level (short simulated span vs the decade window; not one of the
four anchors) — to be resolved before the campaign battery.

---

## A' RESULT (2026-08-02): NO MOVEMENT — and the diagnosis that explains it

A' was implemented in full (branch campaign2-02-residual-drift: the
network models deviations around conditioning-implied drift means,
train/sample symmetry tested, sealed-criterion units preserved, 14 new
tests) and the sealed flow selection config retrained under it at the
B'-baseline seed (early-stopped step 4000, checkpoint
35944bededc5face...). Scored on the same 512 decades / seed as B'
(artifacts/campaign2/residual-acceptance.json):

| statistic | history | B' baseline (g=1.0) | A' (g=1.0) |
|---|---|---|---|
| long-inflation-era freq | 1.000 | 0.396 | 0.410 |
| inflation half-life (months) | 61.2 | 29.4 | 30.0 |
| lost-decade freq (equity) | ~0.00-0.05 | 0.365 | 0.375 |
| equity drawdown median depth | 0.069 | 0.045 | 0.044 |

Within seed noise of the baseline on every anchor. The explanation was
found by removing L3 from the experiment entirely
(scripts/campaign2_targets_probe.py — score the L1-IMPLIED TARGET CURVES
themselves, no block generator anywhere):

| quantity | production starts (2020-12 state) | random historical starts |
|---|---|---|
| targets' long-inflation-era freq | **0.447** | **0.504** |
| targets' negative equity decade drift | **0.375** | **0.217** |
| pi_star decade-mean (pct) | 1.62 | 2.37 |

**The targets already score what the ensembles score.** L3 tracks its
conditioning faithfully — WP2.8's attenuation finding, whatever it
measured locally, is NOT the mechanism behind these four statistics, and
neither guidance (B') nor structural trend-tracking (A') can move them.
The gap lives UPSTREAM:

1. **L1's simulated pi_star dynamics make sustained eras a coin flip**
   (~0.45-0.50 of decades contain a 24-month >=4% YoY run) regardless of
   start state. The severe test's anchor — history 1.000 from the 1965
   state, both arms ~0.42 — is the same fact; its INCONCLUSIVE verdict
   (gap pre-exists with the 1970s in-sample) is consistent with this.
2. **The equity lost-decade excess is substantially a conditioning
   artifact**: decades launch from the 2020-12 fitted state (stretched
   valuations -> low expected drift); unconditional starts drop the
   negative-drift fraction from 0.375 to 0.217 against an anchor pooled
   over unconditional history.
3. The half-life gap (30 vs 61.2) is a per-path AR(1) on YoY inflation;
   part of it may be excess monthly noise (choppy YoY) rather than era
   persistence — a separate mechanism from 1 and untested by A'.

**This exhausts the decided escalation ladder (B' then A', both fired,
both measured).**

---

## SEALED-BATTERY RE-EXAMINATION (2026-08-02): the anchors themselves were misread

Chasing the A' null result back to the sealed record
(artifacts/wp211/severe-test.json, primary arm) exposed a framing error
in THIS MEMO'S OWN HEADER: the four "acceptance statistics" quoted from
G2-EVIDENCE §7-8 (era freq 1.000, half-life 61.2, drawdown 0.069,
lost-decade 0.00-0.05) are the SEVERE TEST'S CONDITIONAL values — history's
one 1966-84 realization given the 1965 state — NOT the sealed
unconditional references the battery actually judges against. Under the
sealed battery bands (90%, block bootstrap, 1871-2020):

| statistic | generated | sealed hist point | band | verdict |
|---|---|---|---|---|
| cpi.long_inflation_era_frequency | 0.428 | 0.462 | [0.226, 0.669] | INSIDE |
| cpi.mean_reversion_halflife | 30.1 | 302 (near-unit-root pt) | [13.4, 47.2] | INSIDE |
| equity_mkt.drawdown_median_depth | 0.032 | 0.031 | (degenerate band) | matches point |
| equity_mkt.lost_decade_frequency | 0.242 | 0.049 | [0.000, 0.132] | **OUTSIDE** |
| hml.lost_decade_frequency | 0.807 | 0.087 | [0.003, 0.251] | **OUTSIDE** |
| ig_spread.mean_reversion_halflife | 2.7 | 28.8 | [6.1, 27.8] | **OUTSIDE** |
| ust_10y.mean_reversion_halflife | 6.7 | 100.2 | [8.4, 27.8] | **OUTSIDE** |
| ust_2y.mean_reversion_halflife | 7.5 | 92.7 | [10.4, 58.5] | **OUTSIDE** |
| hqm_curve.mean_reversion_halflife | 5.5 | 45.9 | [8.2, 27.5] | **OUTSIDE** |
| funding_spread.mean_reversion_halflife | 2.1 | 6.1 | [2.5, 6.9] | **OUTSIDE** |
| equity_vol.mean_reversion_halflife | 1.8 | 3.6 | [2.0, 5.3] | **OUTSIDE** |

**So: cpi persistence was never failing the sealed unconditional test.**
The entire B'/A' campaign chased the severe test's n=1 conditional
comparison — which the seal itself classifies as evidence, not a gate
(S2-SEVERE-GATING). The sealed, unconditional, out-of-band defects are:

1. **LEVEL-factor half-lives, uniformly too short — at roughly the BLOCK
   length** (ust_10y 6.7 months, ust_2y 7.5, hqm 5.5, ig 2.7 vs L=6,
   stride 3). This is where WP2.8's conditioning attenuation genuinely
   bites: blocks under-respond to the state conditioning, so each new
   block reverts toward the unconditional mean and the assembled path's
   persistence collapses to the reassembly timescale. A' does NOT touch
   these — it covers the two drift factors only; the level factors have
   no conditioning-implied level anchor recoverable from c_b (the gap
   documented at bridge.DRIFT_MEAN_FACTORS).
2. **equity/hml lost-decade excess.** For equity, substantially a
   start-state artifact (targets probe: 0.375 -> 0.217 under
   unconditional starts, vs band hi 0.132) plus a residual. hml's 0.807
   is far too large to be conditioning alone — its generated
   unconditional drift needs its own small investigation.

## OPTIONS AFTER A' (drafted for owner decision — revised under the sealed framing)

- **C1' — level-factor residualization.** Extend A''s mechanism to the
  level factors: blocks model deviations around a conditioning-implied
  LEVEL. Needs a level anchor per factor in (or derivable from) c_b —
  h_spread_level_pct exists for ig_spread; rates/vol/curve have none, so
  this likely means a cb-v2 conditioning contract (fingerprint bump, full
  retrain, bake-off rerun). The most targeted attack on the largest
  sealed defect class.
- **C2 — start-state conditioning redesign** for acceptance ensembles
  (draw s0 from the fitted-state distribution). Attacks the equity
  lost-decade cell; changes the comparison, not the model; amendment
  required.
- **C3 — accept and document.** The sealed 10yr tier is already recorded
  as claiming no pass (G2-EVIDENCE §5); record this memo as the mechanism
  trace and proceed with the campaign seal. Step 5 is not blocked.
- **hml drift investigation** (small, orthogonal): why generated hml
  decades lose 81% of the time.
- The A' parameterization itself merges as infrastructure (tested,
  hash-stable, off by default) whichever option is chosen.

**DECISION (owner, 2026-08-02): C3 — accept and document, proceed with
the campaign seal** — verbatim "C3 - accept and document, proceed with the
campaign seal". This memo is the recorded mechanism trace; the campaign
seal proceeds on the existing acceptance basis with the sealed 10yr-tier
defects (level-factor half-lives, equity/hml lost-decade excess) accepted
as known, diagnosed limits of the current generator. C1'/C2 and the hml
drift investigation go to the research backlog with this memo as their
record. A' merges as off-by-default infrastructure; the promotion
training runs WITHOUT it (no model change under C3) and at guidance 1.0
(drawdown depth already matches the sealed point, so the B' g~2.0
corrector is unnecessary).
