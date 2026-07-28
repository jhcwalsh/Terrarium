# Diagnosis: the `ig_spread` reconciliation regression (WP2.8)

**Status: diagnosis only.** Nothing was retrained, no threshold, band or generator
behaviour was changed. Evidence produced by `scripts/diagnose_ig_spread.py`
(read-only; writes only `artifacts/wp28/ig-spread-diagnosis.json`).

## 0. What the metric actually measures

`reconcile.py:369` sets `target = np.clip(z[yends], spread_lo_pct, spread_hi_pct)`.
A year-end value inside the band is its own target, so the Denton adjustment is
exactly zero. `mean_abs_adjustment` for `ig_spread` is therefore **a band-exit
detector**: it is non-zero only when generated year-end spreads fall outside
`[centre - sigma_resid, centre + sigma_resid]`, and its size is the Denton ramp
spread over the year of the year-end excursions. Every number below is stated in
those terms rather than as "adjustment magnitude".

## 1. Reproduction

256 decades x 120 months, seed 20260727, campaign vintage 2026-07-26.1, identical
waypoints for both samplers (the L1/L2 streams are a function of the seed alone),
diffusion at **block width 128 on CUDA** (the committed WP2.8 numbers are width 1
on CPU; cross-width differences are ~1e-5 sd and immaterial here).

| | committed 1024-decade run | this 256-decade run |
|---|---|---|
| bootstrap p50 / p90 | 0.0233 / 0.1402 | 0.0263 / 0.1509 |
| diffusion p50 / p90 | 0.1909 / 0.5583 | 0.2041 / 0.5140 |
| ratio p50 | 8.2x | 7.7x |

The finding reproduces.

## 2. Band-exit rate and signed deviation (the headline answer)

Deviation = raw (pre-reconciliation) year-end `ig_spread` minus the band centre.
Band half-width `sigma_resid` = **0.29200 pct** everywhere (a single pooled
constant); `beta_L` = **0.0011521** (confirmed ~0, so the centre is in practice a
pure regime-conditional historical mean).

| population | n | dev mean | dev sd | **band-exit rate** | mean excursion |
|---|---|---|---|---|---|
| real 1990-2020, all months (in-sample) | 372 | +0.002 | 0.292 | **15.1%** | 0.044 |
| real 1990-2020, Decembers only | 31 | +0.077 | 0.329 | **16.1%** | 0.051 |
| bootstrap year-ends | 2560 | -0.008 | 0.323 | **20.7%** | 0.060 |
| diffusion year-ends | 2560 | **+0.044** | **0.650** | **61.4%** | **0.261** |

By year-end regime:

| regime | share of year-ends | band centre | boot dev mean / sd / exit | **diff dev mean / sd / exit** |
|---|---|---|---|---|
| EXP | 37.1% | 0.831 | +0.032 / 0.204 / 11.7% | **+0.311 / 0.588 / 54.3%** |
| REC | 30.2% | 1.122 | -0.025 / 0.294 / 20.3% | **-0.082 / 0.518 / 63.6%** |
| REF | 10.6% | 0.943 | +0.051 / 0.204 / 9.2% | **+0.123 / 0.580 / 61.6%** |
| SLOW | 9.2% | 0.932 | +0.031 / 0.198 / 11.0% | **+0.143 / 0.533 / 55.5%** |
| CRI | 9.1% | **1.957** | -0.226 / 0.727 / 86.7% | **-0.836 / 0.649 / 90.6%** |
| STAG | 3.7% | 0.974 | +0.007 / 0.186 / 10.5% | **+0.079 / 0.526 / 57.9%** |

Two things are visible at once, and both matter:

1. **The aggregate deviation is unbiased (+0.044) but the conditional deviation is
   strongly one-signed per regime**, in the exact pattern of a generator whose
   spread level ignores the regime. The diffusion raw path level averages **1.084
   pct**; predicted deviation `1.084 - centre(R)` gives EXP +0.253, REC -0.038,
   CRI -0.873 against observed +0.311, -0.082, -0.836. The generated level is
   essentially a constant that the band centre then moves away from.
2. **Within every regime the dispersion is ~2x the band half-width.** RMS
   within-regime deviation sd: diffusion **0.566** vs bootstrap 0.315 vs the band
   half-width 0.292.

Variance decomposition of the year-end deviation:

| | between-regime var | within-regime var | between share |
|---|---|---|---|
| bootstrap | 0.0055 | 0.0991 | **5.3%** |
| diffusion | 0.1034 | 0.3199 | **24.4%** |

Contribution to the 0.261 mean excursion: CRI year-ends are 9.1% of the sample and
**24.0%** of the total excursion. Removing the per-regime mean shift entirely
(EXP: mean 0.311 -> 0, sd held at 0.588) would only cut EXP's excursion from 0.260
to ~0.234; holding the mean and cutting the sd to the bootstrap's 0.204 would cut
it to ~0.091. **Over-dispersion is roughly 2.5x more consequential than the level
shift outside CRI; inside CRI the level shift dominates.**

## 3. Hypotheses: what the evidence supports and what it rules out

- **H1 (level/calibration bias) - PARTLY SUPPORTED, in conditional form only.**
  There is no global level bias: aggregate dev mean +0.044 on a 0.29 band, and the
  sealed battery's `ig_spread.mean` is 1.034 (band [0.628, 2.117]) for diffusion
  vs 1.023 for bootstrap. The bias is *conditional*: the generated level does not
  move with the regime, and the band centre does. Nothing points at the
  softplus/standardization round-trip - that map is exact and the marginal level is
  right.
- **H2 (over-dispersion) - SUPPORTED, and it is the larger term outside CRI.**
  Within-regime deviation sd 0.566 vs band half-width 0.292 (1.94x) and vs the
  bootstrap's 0.315 (1.80x).
- **H3 (under-persistence, `acf_1` 0.651 vs 0.907) - SUPPORTED AS A SYMPTOM, RULED
  OUT AS AN INDEPENDENT MECHANISM.** If the level were an unanchored random walk
  the year-end deviation sd would grow with the year index. Measured by year index
  0..9: 0.456, 0.612, 0.588, 0.669, 0.673, 0.661, 0.686, 0.737, 0.655, 0.702 - it
  rises from year 0 (where `h_t` is pinned to the contract's `h0_spread_level`
  0.958) and then **plateaus by year 3**. The level is mean-reverting to the wrong
  (unconditional) mean, not wandering. The low `acf_1` and the level miss are the
  same defect measured two ways: `h_t` is under-used (Sec. 4).
- **H4 (the band is too tight to be reachable) - RULED OUT for five of six
  regimes, SUPPORTED FOR CRI.** Real 1990-2020 spreads exit their own band 15.1%
  of months (16.1% of Decembers) and the bootstrap exits 20.7% of year-ends; a
  well-calibrated sampler lands inside ~80-85% of the time. But in CRI *even the
  bootstrap*, which draws real CRI blocks, exits 86.7% of the time with mean
  excursion 0.418. The CRI band centre (1.957) is estimated from **17 historical
  months** while the pooled half-width is 0.292 - a band no sampler can hit. That
  is a waypoint-construction defect, not a sampler defect.
- **H5 (the conditioning is not used for this channel) - SUPPORTED, and it is the
  mechanism.** See below. The sampler does use its conditioning; it uses the
  spread-level channels at 2-19% of their historical strength.

**Added hypothesis, H6 - the frozen `cb-v1` contract never carries the band's
level.** `bridge._waypoint_increments` makes all four Delta-w components
*differences* of the target curve. The sampler is told the band's **slope**, never
its **location**. The only level-bearing inputs for `ig_spread` are the regime
one-hot (which is exactly what the centre is a function of), `h_spread_level_pct`
(the assembled path's own previous level, not the target), and the credit-gap
state (genuinely uninformative: `beta_L` = 0.00115). So even a perfect sampler of
`p(x|c)` can only reach the band centre through the regime one-hot, and only if it
has learned the regime->level map.

## 4. The mechanism: channel-by-channel conditioning attenuation

Finite-difference response of the trained sampler (256 historical conditioning
vectors, sampling noise held fixed, one component moved at a time), against the
univariate OLS slope of the same relation on the 367 overlapping historical blocks
(the whole train+validation panel; no holdout is touched):

| channel -> quantity it should steer | historical | model | ratio |
|---|---|---|---|
| `dw_equity_cum_log` -> block cum log equity | +1.009 | +0.789 | **78%** |
| `state_pi_star` -> block mean policy_rate | +1.062 | +0.488 | **46%** |
| `dw_log_cpi` -> within-block log CPI change | +0.804 | +0.310 | **39%** |
| `h_spread_level_pct` -> block mean ig_spread | +0.763 | +0.142 | **19%** |
| `dw_spread_center_pct` -> within-block spread change | +0.850 | +0.116 | **14%** |
| regime one-hot -> block mean ig_spread (range over the 6 labels) | **1.126 pct** | **0.023 pct** | **2%** |

Regime sweep in full - generated block-mean `ig_spread` when only the one-hot moves:
EXP 0.9125, SLOW 0.9070, REC 0.9125, CRI **0.9295**, STAG 0.9067, REF 0.9279,
against band centres 0.831 / 0.932 / 1.122 / **1.957** / 0.974 / 0.943. Asked for a
crisis, the sampler raises the spread by 1.7 basis points.

`state_credit_gap` sweep (-2 -> +2) moves the generated spread 0.901 -> 0.925; that
is *correct* behaviour, because `beta_L` says the credit gap carries no spread
information in this data.

So: **there is a general conditioning attenuation** - every channel is damped,
consistent with ~42 effective training blocks per epoch, `cond_noise_std` 0.05
jitter, and diffusion's conditional-mean shrinkage - **but the two channels that
carry `ig_spread`'s level are damped 4-50x harder than the flow channels.**

### Why `cpi` improved while `ig_spread` got worse, despite both being under-persistent

Their reconciliation targets are structurally different objects:

- `cpi`'s target is `z_log[0] + cum_log_cpi_targets(w)` - **anchored to the
  generator's own month-0 level**. Only the *increments* must match, and the
  increment channel (`dw_log_cpi`, 39% of historical strength) is one of the better
  ones. `cpi` is also in `bridge.CHAINED_FACTORS`, so block-join level jumps are
  removed by construction.
- `policy_rate`'s target is an annual mean level, and the level is determined by
  `s_t` (`pi_star` at 46%), which the sampler does read - hence the halving.
- `ig_spread`'s target is an **absolute level band** whose location is a pure
  function of a channel the sampler reads at 2%, and `ig_spread` is deliberately
  *not* chained. Its level enters raw every block.

Under-persistence is therefore not the discriminator; **whether the target is
relative to the generator's own path or absolute in the world's units is.**

### A second, smaller waypoint/contract mismatch

The band centre uses the regime at the year-end month `m`; the block that
contributes 75% of month `m` after the cross-fade starts at `m-2` and its one-hot
is the regime at `m-2`. Measured over 256 decades: **23.9%** of year-ends have a
different label from the one the dominant block was conditioned on, and **16.3%**
of CRI year-ends were conditioned on a non-CRI label. Real, but far too small to
explain a 90.6% CRI exit rate.

## 5. Sampler defect, waypoint artifact, or both?

**Both, in a roughly 3:1 split.**

- *Sampler defect (dominant).* The trained sampler's `ig_spread` level is
  effectively conditioning-blind (regime channel at 2%, `h_t` at 19%) and its
  conditional dispersion is 1.9x the band half-width. This is a real, measurable
  failure of the conditional generator on this one coordinate, and it is not
  visible in the marginal moments (which pass).
- *Waypoint-construction artifact (secondary but genuine).* A single pooled
  `sigma_resid` = 0.292 is simultaneously too wide for EXP/REF/SLOW/STAG (real
  within-regime residual sd ~0.19-0.20) and unreachably narrow for CRI (real
  within-regime sd 0.727, centre 1.957 from 17 months). The bootstrap's own 86.7%
  CRI exit rate proves the CRI band is unhittable by construction. Additionally,
  `cb-v1` exposes only the band's increment, so nothing in the contract lets a
  sampler be *trained* to hit the level.

An honest framing for G2-EVIDENCE.md: "bootstrap 0.023" is not the standard to
beat - the bootstrap is resampling real blocks stratified on the same regime label
the band centre is a mean of, so it hits the band nearly tautologically. The
defensible statement is that a well-calibrated sampler should exit the band at
roughly the historical 15-20% rate, and the diffusion sampler exits at 61%.

## 6. Does anything sealed depend on this? Is the diagnostic gating?

**No, and no.** Checked, not assumed:

- `pre-registration.yaml` contains no `reconciliation`, `waypoint` or `denton` key
  of any kind (the single grep hit is the ablation-system description "no
  waypoints, no L1 anchor").
- `ah/eval/**` and `ah/battery/**` contain **zero** references to reconciliation or
  waypoints. The diagnostic reaches a reader only through
  `EnsembleMeta.conditioning` and `artifacts/` (the known WP2.7 gap, progress.md
  WP2.7 item 9).
- `prereg._REQUIRED_JUDGED_SOURCES` is `ah/eval/{g2,reference,prereg,battery,panel}.py`,
  `ah/strategies.py`, `ah/factors.py`, `ah/splits.py`, `ah/battery/{report,stylized}.py`,
  `ah/eval/metrics/_pooling.py`, `ah/eval/negative_controls.py`, `ah/data/derive.py`,
  plus `ah/battery/thresholds.yaml` and the metric suites. **Nothing under
  `src/ah/gen/` is inside the seal**, so `waypoints.py`, `reconcile.py` and
  `bridge.py` can be changed without an amendment.
- `flag_spread_pct = 2.0` is a `ReconcileConfig` default (unsealed) and is ~10x
  above the observed p50, which is why both runs flag 0 decades. The flag threshold
  is not the issue.
- The WP2.8 battery passes: 0/5 enforce failures unfiltered and filtered.
  `ig_spread`'s own sealed metrics are *better* under diffusion than under
  bootstrap on shape (`excess_kurtosis` 1.15 in band [-1.01, 6.20] vs bootstrap
  8.996, out of band; `skew` 0.901 in band [0.162, 2.497] vs 2.508, just outside)
  and worse on
  memory (`acf_r_lag1` 0.635 vs band [0.892, 0.975], vs bootstrap 0.862 - both
  below band, report severity).

**Where it does matter.** Two indirect routes, both interpretive rather than
gating:

1. DN-1.1 II.5 / STEP2 section 6 make generator-vs-structure disagreement a
   *finding*. WP2.8's own battery script is written around "the trained sampler's
   adjustments should SHRINK". Two of four channels shrank and one grew 8x; that
   belongs in G2-EVIDENCE.md as stated, with the band-exit reading of Sec. 0.
2. Denton *repairs* the year-ends, so the `ig_spread` column the sealed battery
   judges has had a mean |x-z| of 0.19 pct (~19% of the level) imposed on it. The
   sealed `ig_spread` moment and ACF numbers are therefore partly measuring the
   reconciler, not the generator. This is far more severe for `policy_rate`
   (p50 1.46 pct). WP2.10/2.11 should say so when quoting those rows.

## 7. Candidate remedies, ranked, with trade-offs and seal implications

None of these were implemented. **No option below requires a pre-registration
amendment** - the whole joinery and block stack is outside the seal. What several
of them *do* require is re-running the battery, i.e. WP2.8's numbers move.

1. **Do nothing except report it honestly (recommended for G2).**
   Cost: zero. Keeps WP2.8's numbers, the checkpoint, and the tuning budget intact.
   Buys: the finding is exactly the kind of generator-vs-structure disagreement the
   diagnostic exists to surface, and Sec. 6 shows nothing gating depends on it.
   Against: leaves an 8x regression on the record with no fix path in WP2.8.
   Seal: none.

2. **Make the band width regime-conditional** (`sigma_resid(R)` instead of one
   pooled constant), in `waypoints.source_stats` / `build_waypoints`.
   Cost: ~20 lines, no retraining, no new dependency. Re-assembling the two
   1024-decade ensembles is minutes at width 128 on CUDA (WP2.8b measured 135 s for
   1126 decades); the expensive part is re-running the sealed battery, whose
   conditional tier regenerates the generator ~144 times (~7.6 h at width 1, far
   less batched - WP2.8's cost finding).
   Buys: fixes the demonstrated CRI artifact (a band centred at 1.957 with
   half-width 0.292 built from 17 months is indefensible either way), and tightens
   EXP/REF/SLOW where the pooled width is too generous. Makes the diagnostic mean
   the same thing for every regime.
   Against: CRI's within-regime sd is estimated on 17 months - a wide CRI band is
   honest but nearly vacuous; it also *lowers* the measured adjustment for both
   systems, so it must be applied to bootstrap and diffusion together or the
   comparison is corrupted. Changes WP2.7's published p50 too.
   Seal: none. Records as a WP2.7 correction.

3. **Add the band centre (a level) to the conditioning contract.**
   `cb-v1` -> `cb-v2` with a 19th component `w_spread_center_pct`, then retrain.
   Cost: high - a new contract fingerprint invalidates the WP2.8 checkpoint and
   burns a fresh 40-trial budget (the seal is per system per sampler), and WP2.9's
   flow variant would have to follow. Days, not hours.
   Buys: the only remedy that makes the target *reachable by training* rather than
   by repair. Directly addresses H6, which no amount of retraining on `cb-v1` can.
   Against: breaks the "frozen contract" property WP2.7 established and WP2.8/2.9
   pin; WP2.9 would be comparing samplers across two contracts unless both are
   redone.
   Seal: none, but it is an interface-bearing decision for WP2.9/2.10/2.11 and
   should be an owner call.

4. **Chain `ig_spread` at block joins, or add an inference-time level correction
   through the existing (stubbed) `bridge.GuidanceHook`.**
   Cost: low-to-moderate; the hook already exists and is called per sampled block.
   Buys: closes the level gap without retraining - e.g. shift each block so its
   first month continues the assembled path, or nudge toward the band centre.
   Against: this is *post-hoc repair*, the same category as Denton. It would make
   the reconciliation diagnostic look good while hiding the fact that the sampler
   cannot aim - precisely the "Denton can flatter a weak generator" failure
   `reconcile.py`'s docstring warns about. WP2.7 deliberately did *not* chain
   rates/spreads. If taken, the diagnostic must be reported both with and without.
   Seal: none. DN-1.1 II.5 design note (a) names guidance as a WP2.9 evaluation
   item, so doing it here would pull WP2.9 scope forward.

5. **Attack the attenuation directly: retrain with a stronger conditioning
   signal** (lower/zero `cond_noise_std`, classifier-free guidance at sampling
   time, or an explicit auxiliary loss on the block's mean spread vs the regime
   mean).
   Cost: a retrain (~17 min for the final config) plus a battery re-run; CFG needs
   a new sampling knob and would want its own small search.
   Buys: attacks the general 2-5x attenuation, which also affects `policy_rate` and
   `cpi`; likely the highest-value change for WP2.9/2.10 overall.
   Against: the sealed tuning budget for this sampler is spent (31/40 completed,
   1 abandoned; 8 candidates remain but the seal treats them as spent-per-sampler).
   Re-tuning risks looking like selection after seeing the answer - it must be
   declared. `cond_noise_std > 0` was chosen by the top 6 trials on validation S,
   so reducing it trades a sealed selection criterion for an unsealed diagnostic.
   Seal: no amendment, but a governance note is required.

6. **Add a `report`-severity reconciliation line to the battery.**
   Cost: adding a judged source *inside* `ah/eval/` - this **would** require a seal
   amendment (the module joins `_REQUIRED_JUDGED_SOURCES` and changes the digest).
   Buys: closes the WP2.7 item-9 gap so the diagnostic is not artifact-only.
   Against: the only option here that touches the seal; the diagnostic's meaning is
   currently regime-dependent (Sec. 5), so sealing it before remedy 2 would seal a
   band-exit rate that is partly a construction artifact.
   Seal: **amendment required.** Not recommended before remedy 2.

**Recommended order:** 1 now (report it, with the band-exit framing); 2 as a WP2.7
correction if the owner wants the diagnostic to mean one thing across regimes;
5 folded into WP2.9's own search rather than as a WP2.8 retrofit; 3 only as a
deliberate contract decision taken before WP2.9 trains. Avoid 4 unless reported
both ways; defer 6.

## 8. What was run

- `scripts/diagnose_ig_spread.py --n-decades 256 --block-batch 128 --device cuda`
  (also a 64-decade pass first). Deterministic, offline, `pytest-socket` untouched;
  reads the local catalog, the pinned L1/L2 artifacts and the pinned WP2.8
  checkpoint `f0c79f00...`.
- `uv run ruff check scripts/diagnose_ig_spread.py` - clean;
  `uv run ruff format --check` - clean; `uv run pyright scripts/diagnose_ig_spread.py`
  - 0 errors. No importable code under `src/` was touched, so the full suite was not
  re-run.
- Raw numbers: `artifacts/wp28/ig-spread-diagnosis.json`.
- Reproduction check: the 256-decade run recovers the committed p50s to within
  ~7% (Sec. 1), at block width 128 rather than the committed width 1.
