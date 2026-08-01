# I4 + I6 inspection — the 2021-2023 reference episode

Vintage `2026-08-01.2`; window 2021-12-01..2023-12-31; public trough 2022-09-01. Produced by `scripts/run_inspection_i4_i6.py` (deterministic: observed inputs, frozen artifacts, no RNG). Inspection points are diagnostic with teeth (MPP-A1 standing rule): they cannot pass what a battery failed, and red flags below are recorded as work items before G4 closes.

## I4 — the reported-vs-true toggle (MPP-A1)

HF composite, monthly (equal-weight frozen sleeves; per-sleeve theta):

| month | dd true | dd reported | gap (rep-true) |
|---|---|---|---|
| 2021-12-01 | +0.0000 | +0.0000 | +0.0000 |
| 2022-01-01 | -0.0088 | -0.0034 | +0.0054 |
| 2022-02-01 | -0.0101 | -0.0049 | +0.0052 |
| 2022-03-01 | -0.0036 | -0.0010 | +0.0025 |
| 2022-04-01 | -0.0185 | -0.0108 | +0.0077 |
| 2022-05-01 | -0.0171 | -0.0120 | +0.0051 |
| 2022-06-01 | -0.0303 | -0.0223 | +0.0079 |
| 2022-07-01 | -0.0109 | -0.0109 | -0.0001 |
| 2022-08-01 | -0.0114 | -0.0087 | +0.0026 |
| 2022-09-01 | -0.0255 | -0.0175 | +0.0080 |
| 2022-10-01 | -0.0062 | -0.0063 | -0.0000 |
| 2022-11-01 | +0.0000 | +0.0000 | +0.0000 |
| 2022-12-01 | -0.0074 | -0.0010 | +0.0064 |
| 2023-01-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-02-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-03-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-04-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-05-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-06-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-07-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-08-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-09-01 | -0.0048 | -0.0023 | +0.0025 |
| 2023-10-01 | -0.0066 | -0.0044 | +0.0022 |
| 2023-11-01 | +0.0000 | +0.0000 | +0.0000 |
| 2023-12-01 | +0.0000 | +0.0000 | +0.0000 |

PM cohort plane, quarterly (hf_event theta stand-in — Geltner family is
UNPARAMETERIZED by the sealed PM unavailability, convention stated):

| quarter | dd true | dd reported | w_true | w_reported |
|---|---|---|---|---|
| 2021Q4 | +0.0000 | +0.0000 | 0.3832 | 0.3832 |
| 2022Q1 | -0.0469 | -0.0247 | 0.3852 | 0.3907 |
| 2022Q2 | -0.2392 | -0.1793 | 0.3766 | 0.3946 |
| 2022Q3 | -0.2680 | -0.2377 | 0.3770 | 0.3866 |
| 2022Q4 | -0.1973 | -0.1959 | 0.3838 | 0.3842 |
| 2023Q1 | -0.1456 | -0.1430 | 0.3814 | 0.3821 |
| 2023Q2 | -0.0723 | -0.0728 | 0.3812 | 0.3811 |
| 2023Q3 | -0.1047 | -0.0782 | 0.3805 | 0.3874 |
| 2023Q4 | +0.0000 | +0.0000 | 0.3890 | 0.3870 |

### The three things the protocol says must be visible

1. **Reported materially shallower than true** — VISIBLE. HF: true -0.0303 vs reported -0.0223; PM: true -0.2680 vs reported -0.2377.
2. **Gap widening into the trough** — VISIBLE (gap +0.0025 three months before the true trough -> +0.0079 at it). **Caveat, and it is the point:** this widening comes from the MA kernel alone. SM-11 state-dependent stickiness is MEASURED ZERO on the frozen panel (kernel artifact, stickiness_evidence), so the parameter contributes nothing here; the G1 replay's mark_lag FAIL already recorded that 2022's lag does not fully emerge from MA structure. Standing work item (next generator campaign, with the HY splice): re-estimate stickiness with post-2021 data in view. Recorded against SM-11; not tunable now.
3. **The denominator effect on the private weight** — VISIBLE. On the reported plane the weight rises from 0.3832 to 0.3866 at the public trough; the true plane reads 0.3770 there. With the levered PM beta (1.2) the true weight also drifts up before its deeper marks catch down - the planes DIVERGE (reported above true through the trough), which is the mechanic the toggle exists to show.

## I6 — the liquidity timeline (liquidity-spine v0.2 s12)

Vintage stack 2015-2021, 100 committed each; warm-up at 3%/q calm; observed window states; frozen tier-1 linkage; engine waterfall with spending off trailing REPORTED value (Policy defaults). Book at the door: 1,411 (62% public / 38% private), cash 4%.

| quarter | calls | dists | spending | net cf | cash end | cov true | cov liquid | forced |
|---|---|---|---|---|---|---|---|---|
| 2021Q4 | 12.16 | 0.42 | 16.93 | -28.67 | 27.77 | 0.210 | 0.339 |  |
| 2022Q1 | 11.45 | 0.31 | 16.42 | -27.56 | 0.21 | 0.216 | 0.356 |  |
| 2022Q2 | 10.67 | 0.17 | 15.27 | -25.77 | 0.00 | 0.259 | 0.431 | FORCED |
| 2022Q3 | 10.09 | 0.16 | 14.46 | -24.39 | 0.00 | 0.264 | 0.450 | FORCED |
| 2022Q4 | 6.65 | 0.19 | 14.07 | -20.54 | 0.00 | 0.242 | 0.426 | FORCED |
| 2023Q1 | 6.48 | 0.26 | 13.92 | -20.14 | 0.00 | 0.223 | 0.398 | FORCED |
| 2023Q2 | 6.32 | 0.35 | 13.94 | -19.91 | 0.00 | 0.203 | 0.368 | FORCED |
| 2023Q3 | 6.10 | 0.39 | 13.89 | -19.60 | 0.00 | 0.207 | 0.382 | FORCED |
| 2023Q4 | 4.35 | 0.69 | 14.00 | -17.66 | 0.00 | 0.180 | 0.343 | FORCED |

Vintage stack (true NAV; `#` = stacked area, oldest at left):

```
2021Q4  ##|#|#|#|#|#|  total   570.5
2022Q1  #|#|#|#|#|#|  total   554.9
2022Q2  #|#|#|#|#|#|  total   453.5
2022Q3  #|#|#|#|#|#|  total   446.2
2022Q4  #|#|#|#|#|#|#  total   495.8
2023Q1  #|#|#|#|#|#|#  total   534.0
2023Q2  #|#|#|#|#|#|#  total   585.7
2023Q3  #|#|#|#|#|#|#  total   570.9
2023Q4  ##|#|#|#|#|#|#  total   666.6
```

### What the protocol says this catches, checked

- Calls too smooth: calls range 4.35..12.16 per quarter — VARY (not flat). f_call is near-flat by Delta 3 (measured), so most variation is the age profile, which is the honest shape.
- Drought too shallow/deep: distributions fall from 0.42 to 0.16 at the trough — shape VISIBLE as a RATIO (the G1 replay scored depth 0.544 inside the sealed [0.45, 0.55]) — but see the LEVEL red flag below.
- **Distribution LEVEL implausible — RED FLAG.** The fixture's `yield_rate` (the register's Y, the terminal annual distribution rate) is 1.00%/yr. Real mature buyout distributes roughly 20-30%/yr of NAV; the fixture's own flows snapshot (2.0/q on NAV 71.8, ~11%/yr at age 5.25) contradicts its own parameter by ~40x. The CODE is faithful to the register (`RD(t) = Y*(t/L)^B`, register s1 line-for- line); the fixture VALUE is mis-scaled against the register's Y definition. Consequence in this exhibit: distributions are starved, so spending forces liquid sales nearly every quarter.
- Cohorts never mature: unfunded ordering v2015 30.4 < v2018 35.4 < v2021 45.0 — age profile present. Absolute pace is slow (34% uncalled at age 7 vs ~10% real-world): the rc_curve is the register's kind-C stand-in pending ALB-A; noted, not tuned.
- Forced sales never/constantly: 7 event(s) in 9 quarters, kinds ['liquid_pro_rata'] — 'constantly', which on this exhibit is the DOWNSTREAM of the distribution-level flag (spending is ~4.5%/yr of reported book while distributions run ~0.2%/yr; the gap must come from somewhere, and the engine honestly logs where). No forced secondaries trigger: liquid cover is ample (cov_liquid ~0.4). Re-inspect after the Y fix before treating cadence as a model finding.

## Work items raised (recorded before G4 closes; the standing rule)

1. **WI-I6-1 - fixture `yield_rate` mis-scaled** (register s1, parameter Y;
   D7 row). Re-parameterize the fixture cohort's Y from industry aggregates
   (the register's stated ALB-A fallback), reconcile the fixture's
   performance/flows block to its own parameters, and SENSITIVITY-CHECK the
   G1 drought ratio under corrected Y - as a robustness note on the sealed
   result, not a reseal. Owner sign-off required (fixtures are contract
   surface).
2. **WI-I4-1 - SM-11 stickiness**: the state-dependent parameter is
   measured zero and contributes nothing; 2022's mark lag does not fully
   emerge from MA structure (G1 replay FAIL). Already queued for the next
   generator campaign alongside the HY splice; recorded here so G4 cannot
   close without the register knowing.
3. **WI-I4-2 - PM kernel stand-in**: reported PM planes use hf_event theta
   because Geltner is UNPARAMETERIZED (sealed PM unavailability). First PM
   delivery parameterizes it by amendment before any RE/infra reported
   path is generated - restated so the Step 4 artifact layer (which
   renders reported marks) inherits the caveat.

---

*Not investment advice.*
