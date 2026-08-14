# Engine realism register (post-G2)

Things the `toy-v0` engine does that an allocator would not believe, each
found by playing or auditing a built world rather than by reading the spec.
Nothing here is a defect against `STEP0-PLAN` — the plan's formulas are
implemented faithfully. These are places where the *plan itself* buys
determinism and simplicity at the cost of economic credibility, and they are
recorded so the decision to change them is deliberate, owner-made, and taken
after G2 rather than smuggled into an unrelated branch.

**Why post-G2.** Every entry changes the numeric behaviour of built worlds.
Any change to the return process invalidates existing RunRecords (their
digests no longer reproduce) and, where it moves the scored path, requires a
`decision_alpha_version` bump so leaderboards stay comparable. That is a
release event, not a fix.

Status values: `open` (agreed, not scheduled), `scheduled` (has a WP),
`done` (shipped, with the commit).

---

## ER-1 — High yield earns its full spread with no default losses

**Status:** CLOSED in `toy-v0.3` (engine-er1-er4 branch)
**Found:** 2026-08-04, auditing the rebuilt stagflation world after the
unit-coherence fix (the app's new annualized readouts made it visible).

**What happens.** The HY return term is

```
hy = rate/12 + spread/1200 - 3.5*d_spread + 0.5*eq_vol_m*z_hy - 0.6*crisis
```

`spread/1200` books the *current* spread as earned carry every month, with no
offsetting credit-loss term. Private credit has one (`loss_m`, tripled inside
crisis months); high yield does not. Compounding this over a decade against a
spread path that averages 1278bp produces:

| | median %/yr | p5 | p95 | vol %/yr |
|---|---|---|---|---|
| high yield | **18.7** | 12.8 | 25.7 | **12.1** |

A Sharpe above 1.0 on sub-investment-grade debt, in a stagflation, is not a
world any allocator would accept. Spreads that wide *are* the market pricing
defaults; booking them as pure carry is the error.

**Also wrong, and part of the same picture.** `_spread_path` is a triangular
hump between `hy_spread_start_bps` and `hy_spread_peak_bps` at
`peak_quarter`, then a straight line back to `0.9 * start`. In the
stagflation preset that means the spread starts at 401bp, ends at 358bp, and
*averages 1278bp* — years spent at levels that in reality clear in months. A
decade-long plateau at crisis spreads is not a credit cycle.

**What a fix looks like.** Two independent pieces; either helps, both are
needed to make HY credible:

1. A realized-loss term on HY, in the shape private credit already uses —
   a default rate that rises with the spread level and with the crisis mask,
   subtracted from carry. Net spread, not gross.
2. A spread process that mean-reverts on a credit-cycle timescale (spikes
   that decay over quarters, not a decade-long plateau), instead of a
   deterministic triangle.

**Consequences.** Changed every world's HY path and therefore every stored
digest, the institution's totals, and the scored path.

**What shipped.** Both halves, as the entry said were needed:

1. A realized-loss term. `_HY_LOSS_SHARE = 0.45` of the gross spread is booked
   as expected default loss rather than carry, keyed on the spread as it stood
   `_CREDIT_LOSS_LAG_MONTHS = 12` earlier (the market prices the risk about a
   year before the defaults land) and amplified `1.6x` inside crisis months
   because defaults cluster. Private credit gets the same mechanism at a lower
   severity, being senior secured.
2. A credit cycle that clears. `_spread_path` is now a long-run level plus a
   Gaussian pulse centred on `peak_quarter` plus mean-reverting noise, instead
   of a ramp-and-glide triangle. The declared peak is still reached at the
   declared quarter — the WorldSpec fields keep their meaning — but the decade
   no longer sits at crisis spreads.

**Result on the stagflation preset:** high yield **18.7 → 7.5 %/yr** on 14.0%
vol, a decade Sharpe of **1.54 → 0.53**; spread mean **1279 → 626bp** against a
403bp start and 396bp end. No leaderboard implication: the alpha DEFINITION is
unchanged, so `decision_alpha_version` is untouched (it lives in
`eval/decision_metrics.py`, inside the pre-registration seal, and bumping it
would need an amendment). World identity carries the difference instead — the
presets moved to the `3xx` id block so scores made under two engines cannot
share a board.

---

## ER-4 — Carry assets earn their carry almost risk-free

**Status:** CLOSED in `toy-v0.3` (engine-er1-er4 branch)
**Found:** 2026-08-04, first run of the credibility console across all four
presets — it is the same pattern in every world, which is what makes it
structural rather than a preset's fault.

**What happens.** Bonds, private credit and real estate all clear a decade
Sharpe above 1.0, in worlds as different as `goldilocks` and `deflation_bust`:

| preset | bonds med / vol | pc med / vol | re med / vol |
|---|---|---|---|
| stagflation | +5.4 / 2.7 (1.98) | +8.9 / 4.8 (1.88) | — |
| goldilocks | +3.1 / 2.7 (1.12) | +7.7 / 3.5 (2.21) | +7.0 / 6.2 (1.13) |
| deflation_bust | +4.5 / 2.7 (1.63) | — | — |
| reflation_boom | +0.7 / 2.7 (—) | +7.4 / 4.0 (1.82) | +7.6 / 7.3 (1.04) |

The mechanism is the same one as ER-1, generalised: these assets' returns are
dominated by a near-deterministic carry term (`rate/12`, `(rate+4.5)/12`,
`4.5/12`) with only a small idiosyncratic shock on top. Carry arrives every
month; almost nothing takes it away.

**Bond volatility is the sharpest tell.** It is **2.7%/yr in all four
presets** — identical to two significant figures across worlds whose rate
paths differ completely. That number is essentially the fixed `0.7 * z_b`
idiosyncratic term (0.7% monthly ≈ 2.4%/yr); the duration term `-6.0 * d_rate`
contributes almost nothing because the rate path is smooth by construction.
A ten-year government bond with 5-6 years of duration should carry 5-8%
annual volatility. Duration risk is in the formula but not in the numbers.

**What a fix looks like.** Rate paths with real monthly innovation rather
than a smooth glide (ER-2's meeting quantisation would help here too — actual
policy moves in steps), and a loss/default term on the credit assets so that
carry is compensation for something. The two together, not either alone: a
noisier rate path without credit losses just moves the problem.

**Consequences.** Touched every asset that prices off the rate.

**What shipped.**

- The policy rate's monthly innovation went from **6bp to 22bp** with slower
  reversion (`_RATE_KAPPA` 0.15 → 0.08), so duration risk reaches the numbers.
  Crucially the shock now **scales with the inflation regime** — a first pass
  used a global constant and bond volatility came out identical in all four
  presets again, which is the same tell one level down.
- Private credit gained a credit-cycle beta (`-0.8 * d_spread`), a loss rate
  that rises with the spread rather than a flat 0.6x discount outside crisis
  months, and more idiosyncratic risk.
- Real estate gained rate sensitivity (`-4.0 * d_rate`, cap rates move with
  rates), a crisis repricing term, and more idiosyncratic risk.

**Result:** bond volatility **2.7 %/yr in every world → 7.1 / 5.2 / 5.2 / 5.8**
across stagflation / goldilocks / deflation_bust / reflation_boom, and it now
*varies with the world*, which was the diagnostic that opened this entry.
Private credit's decade Sharpe fell from **1.88 / 2.21 / 1.82** to **1.03 /
1.08 / 0.95**. Across all four presets the console's flag count went **24 → 5**.

**Still slightly hot, and left honest.** Private credit sits at ~1.05 in the
two benign worlds, just above the declared 1.0 ceiling. That is a defensible
number for senior secured lending and the flag is left standing rather than
tuned away — moving the threshold to silence a flag we set ourselves would
make the console worthless.


## ER-5 — Equity returns are autocorrelated because the crisis is a block

**Status:** open (pre-existing; observed, not introduced, by the ER-1/ER-4 work)
**Found:** 2026-08-04, running the validation battery before and after the
ER-1/ER-4 change — the value is byte-identical across both, so it predates
them.

**What happens.** The battery's `acf_r_lag1` on pooled equity returns reads
**0.364**, against a declared band of [-0.2, 0.2]. Returns at monthly
frequency should be close to uncorrelated; +0.36 is momentum a real index does
not have.

The cause is `_crisis_mask`: a crisis is a rectangular block of months in
which every path takes the same deterministic `-2.2` hit. Pooled across
paths, that block is a constant shift over a contiguous run of months, which
is exactly what lag-1 autocorrelation measures.

**Why it has not failed anything.** Every battery gate is `status: todo` in
Step 0 by design — "Step 0 ships plumbing only... placeholders documenting
intent, not ratified thresholds" — so this has been recorded and non-blocking
since the battery was written.

**What a fix looks like.** A crisis with an onset and a decay rather than a
step: severity that ramps in over a quarter or two, peaks, and fades, with
per-path timing jitter so the block is not identical across the ensemble.
That also makes crisis onset something a player can see coming, which the
newspaper front pages would benefit from.

**Consequences.** Digest-invalidating. Would move the battery's headline
stylized fact, which is the point.


## ER-2 — The policy rate is a continuous drift, not committee decisions

**Status:** open
**Found:** 2026-08-02, first live play session ("Central banks to change
rates by 0.07%, the smallest increments are 0.25% in the US").

**What happens.** `_rate_path` produces a smooth monthly path. There is no
meeting calendar and no quantisation, so any narration that reports a
"decision" reports a number no committee could have taken.

**Mitigated, not fixed.** `central_bank_statement` no longer announces
decisions; it narrates drift ("policy conditions tightened over the quarter;
the rate stands at 5.74%, up 6bp"), and moves under 5bp read as little
changed. That removes the false artifact without pretending the underlying
process is something it is not.

**What a fix looks like.** A meeting calendar (eight per year for the US
analogue), a target rate that only moves on meeting months, and moves
quantised to 25bp multiples. The continuous path becomes the *policy stance*
the committee is tracking; the quantised rate is what the world actually
prices off. Statements then key on real decisions and can carry a vote
split.

**Consequences.** Changes the rate path, so bonds, HY, REITs and private
credit all move. Digest-invalidating; alpha-version-bumping.

---

## ER-3 — Assets have no cashflow, so private markets have no calls

**Status:** CLOSED in the play surface (wire-play-surface branch)
**Found:** 2026-08-03, owner request for commitments/calls/distributions to
drive secondary sales.

**What happens.** The engine emits returns only. Private equity, private
credit and real estate are held as continuously-valued sleeves with no
commitment, no unfunded balance, no capital calls and no distributions —
so the one decision that makes a secondary sale meaningful (needing cash you
do not have) cannot arise from the numeric path.

**What a fix looks like.** Step 3's institutional twin: a cash account,
commitment schedules, pacing-model calls, distributions keyed to asset age
and realized performance, and forced sales when coverage fails. This is
already Step-3 scope in `CLAUDE.md` (cashflow/TA calibration), and Amendment
A1 Delta 2's artifact classes (capital call, distribution, coverage band,
forced sale, secondary discount) are written and waiting for it.

**Consequences.** Scoring becomes path-dependent on liquidity, which is the
point. Full alpha redefinition.

**What shipped.** The play surface now scores through `ah/play.py`, which
drives Step 3's real institutional twin (`ah/port/`) quarterly off a
toy-engine tape, replacing the display-only pacing ledger entirely
(`ah/pacing.py` is deleted, along with its tests). Capital calls must now be
funded from a real cash account; when cash is short the waterfall sells
liquid holdings first and private interests second, at the policy haircut,
and a forced sale is a logged event that reaches the player on the wire (and
the ticker) rather than a number that only moves in a table. Scoring carries
a distinct `PLAY_ALPHA_VERSION` (`"port-v1-cashflow"`) so cashflow-scored
sessions cannot share a leaderboard row with anything scored before this
work.

**What is still open.** The toy market engine itself still has no cashflow
of its own — it emits returns only, exactly as this entry originally found.
What closed ER-3 is the *institution* consuming the engine's tape and
imposing commitments, calls, distributions and a cash constraint on top of
it, not the engine generating any of that internally. An engine that priced
its own cashflow-bearing instruments (e.g. bonds with coupons and maturities,
private funds with engine-native capital schedules) would be a different,
larger change, and is not what shipped here.

---

## ER-6 — A third of every commitment is never called

**Status:** CLOSED 2026-08-12 (`er6-call-pacing` branch), owner decision D1
"A plus C" (`docs/superpowers/plans/2026-08-12-er6-call-pacing-design.md`).
The placeholder curve is superseded by a DECLARED curve —
`[0.35, 0.40, 0.30, 0.25, 0.20, 0.15]`, class `declared`, landing ~90%
called by year 10 (pinned in-band 85–95% by
`test_called_fraction_lands_in_the_practitioner_band`) — and the residual at
terminal lapse now EXPIRES visibly (`CohortStep.expired_undrawn`; the
unfunded balance zeroes instead of haunting the totals). Both play-alpha
stamps bumped to `port-v2-cashflow` / `port-v2-cashflow-gen`.

**Close-out measurements, honestly stated:** `peak_unfunded_ratio` fell
from 2.4–3.3 to ~0.96–1.29 across worlds — the pathology is gone, but the
declared 0.25–0.75 band still flags because the RESIDUAL overhang belongs
to the hold-course COMMITMENT PACE (18%/yr, the E1 lever's default) plus
the denominator effect in crash decades; neither the band nor the pace was
tuned to quiet it. And the ER-8 interplay paid out: faster calls revived
the forced secondary on deflation_bust (6/20 seeds, 19 events, vs 0/20
under the placeholder) — see ER-8's amendment.

**Found:** 2026-08-05, the first run of the private-programme section of the
credibility console (`ah credibility`) — the surface built specifically to
look at the pacing model before the commitment lever is designed on top of
it. Found by the flags, not by reading the code.

**Scope note.** This entry is about the *cohort cashflow model* in
`ah/port/`, not the `toy-v0` return process. ER-3 already took the register
into this layer; the standing rule is the same — the plan is implemented
faithfully, and what is recorded here is where that costs credibility.

**What happens.** `rc_curve` in `fixtures/state/closed-end-cohort.example.json`
is `[0.25, 0.30, 0.20, 0.12, 0.08, 0.05]`, applied by
`ClosedEndCohort.step` as an annual **rate on the remaining unfunded
balance**, with the age index clamped to the last element
(`rc_index = min(int(age_years), len(rc_curve) - 1)`). From year 5 onward it
therefore draws 5% per year of whatever is left — a declining rate against a
shrinking balance — and converges well short of the full commitment. At
`age >= L` the commitment lapses entirely and no further calls are made.

Measured on a fresh cohort at tier 0's frozen growth, linkage neutral, fees
off, `committed = 1.0`:

| horizon | paid-in | never called |
|---|---|---|
| 10 years (the contractual life) | 0.7075 | **29.2%** |
| 20 years (past life, calls lapse at L) | 0.7355 | **26.4%** |

An allocator's expectation for a drawdown fund is 85–95% called by end of
life. This is a **declared prior**, in the same spirit as the console's
bands, not a citation.

**What it produces downstream.** The institution commits a new vintage every
year (`_ANNUAL_COMMITMENT_RATE = 0.18` of each private sleeve's target, in
`ah/play.py`), so roughly 6.3 points a year are committed against about 35
points of private NAV. If ~29% of each vintage is permanently stranded,
unfunded accumulates instead of clearing, and the console reads:

| statistic | stagflation | goldilocks | deflation_bust | reflation_boom | declared |
|---|---|---|---|---|---|
| `peak_unfunded_ratio` | 3.018 | 2.445 | 3.308 | 2.453 | 0.25–0.75 |
| `crossover_years` | 8.500 | 8.375 | *never* | 8.750 | 4–8 |

`peak_unfunded_ratio` flags on all four worlds. Roughly half of the headline
figure is a one-quarter denominator collapse at the cohort's contractual
wind-up (private NAV falls as the lump pays out while unfunded barely moves);
the steady state is 1.0–1.7, still two to seven times the declared prior.
The J-curve crossover is correspondingly late, and on `deflation_bust` no
path's year-1 vintage crosses over at all within the decade.

**Provenance — this is a placeholder, not an estimate.** `RC(t)` is register
kind **E (estimated)** in `Instructions/model-parameter-register.md` §38,
sourced from **ALB-A item 1** ("call rate on unfunded, by age"), with the
note to "estimate the full age curve, not a 3-point schedule". ALB-A never
arrived — the same sealed PM unavailability recorded in
`mappings/cashflow-tier0-v1.0.yaml` ("UNPARAMETERIZABLE ... needs ALB-A/C,
never delivered"). The six numbers now in the fixture are the example
document's illustrative values, standing in for a parameter that was always
meant to be fitted, and nothing had ever aggregated them until the console
existed.

**Why it has not failed anything.** The twin's absolute private NAV is set by
`START_TARGETS`, not by how much of each commitment gets drawn, so
under-drawing never moved a headline value anybody watched. It surfaced only
as a stock of unfunded commitments that no surface plotted until now. Every
tier-0/tier-1 identity test still passes: this is not a violation of the
recursion, it is the recursion doing exactly what these coefficients say.

**A related observation, possibly the same cause.** `forced_secondaries` is
**0 on all four presets** under hold course — the forced-sale waterfall, the
mechanic that makes liquidity consequential, is never exercised by the base
case. Under-drawing means less cash pressure, so this may resolve on its own
if the call curve is corrected. Worth re-measuring after any fix rather than
treating it as a separate finding.

**What a fix looks like.** Any of:
1. Extend `rc_curve` beyond six entries so late-life draw rates rise rather
   than flatten at 5%;
2. Add a terminal true-up — call the residual unfunded at or near `L`, which
   is what a GP with an expiring investment period actually does;
3. Re-express `RC(t)` as a fraction of **committed** rather than of remaining
   **unfunded**, which makes "call 90% by year 6" directly expressible.

(3) is the cleanest to reason about and the furthest from the frozen spec's
wording (`Call(t) = RC(t) × [CC − PIC(t−1)]`, register §28), so it would need
that formula amended rather than just a vector swapped. (2) is the smallest
change that reaches a credible number. Whichever is chosen, the console's
`peak_unfunded_ratio` band must be re-derived afterwards — 0.25–0.75 was
written for a programme that fully draws, and is not a fair test until one
exists.

**Consequences.** Digest-invalidating for anything private. Calls move, so
NAV, cash, spending, the forced-sale waterfall and every downstream session
value move with them. Specifically:

- `simulate_play` output changes → the play surface's scores change. This
  warrants a **`PLAY_ALPHA_VERSION` bump** (currently `port-v1-cashflow`), on
  the same reasoning that introduced it: rows scored under two different
  cashflow models must not share a leaderboard. **Owner's call.**
- `app/fixtures/toy.bundle.gz` must be rebuilt (`twin_ledger` changes), and
  the golden values in the play/bundle/serve suites move.
- It does **not** touch `schemas/` (the field's shape is unchanged), does
  **not** touch `mappings/` (`rc_curve` is in neither sealed artifact — the
  tier-0 spec carries `g_annual`, the tier-1 artifact the linkage), and is
  **not** inside the pre-registration seal's `hashed_files`.
- `ah.eval.decision_metrics.DECISION_ALPHA_VERSION` stays put: the alpha
  *definition* is unchanged, and it sits inside the G5 seal.

**Why this one is urgent rather than merely recorded.** The commitment lever
(`experience-deltas-register` E1) asks a player to choose how much to commit,
and the post-game review (E4) is meant to teach them what cutting a
commitment in a drawdown cost. Both rest on the arithmetic of commitments
being drawn. While ~29% of any commitment is never called, the flinch cost is
measured against a counterfactual that does not behave like a real programme
— so this is a prerequisite for E1, not a parallel cleanup.


## ER-7 — Monthly returns are near-Gaussian: the engine has no fat tails

**Status:** CLOSED in `toy-v0.5`, 2026-08-08. (First closed in `toy-v0.4` on
2026-08-06, which NEVER MERGED: its own gate run exposed that the new tails
could push a levered stream below −100% in a month — see the close-out below
and ER-8. v0.5 is the tails plus the limited-liability floor.)
**Found:** 2026-08-06, by the first run of the Step-0 stylised battery after its
thresholds were ratified (AM-2026-08-06-001). Found by a gate, which is what the
gate was ratified for.

**What happens.** Pooled equity `excess_kurtosis` reads **0.0853** against a
ratified floor of **0.5** — outside by 0.415. Excess kurtosis is 0 for a normal
distribution, so the toy engine's monthly returns are very close to Gaussian.
Fat tails are the most-cited stylised fact of financial returns (Cont 2001), and
this engine does not have them.

Stable across ensemble size, so it is a property of the process and not of the
sample: 16 paths → −0.027, 32 → 0.085, 64 → 0.085, 128 → 0.033, 256 → 0.018.
Every value is far below the floor.

**Two other gates corroborate.** `hill_tail_index` reads 5.799 against a ceiling
of 6.0 — a *high* alpha means a *thin* tail, so the engine sits just inside the
"too thin" edge. Meanwhile `max_drawdown_median` is −0.5946, comfortably deep.
The picture is coherent: month-to-month the engine is shallow-tailed and
near-Gaussian, and its one large loss is the deterministic crisis block doing
the work fat tails should do. That is the same mechanism ER-5 records for the
autocorrelation defect, seen from another angle.

**Why it was not caught earlier.** Every gate was `status: todo` from WP0.8 until
2026-08-06, so the battery could not fail and the value was never read against
anything. The statistic was computable at any time; nothing was looking.

**Consequences.** CI's `python -m ah.battery.report` step now exits 1, so CI is
red until either the engine gains fat tails or the threshold is amended. Amending
the threshold to clear a failure it was written to catch would be a post-hoc
adjustment of exactly the kind the pre-registration discipline exists to prevent,
and should not be done to make CI green.

**What a fix looks like.** A heavier-tailed innovation in the monthly return
draws — a Student-t or a mixture — in place of the current Gaussian
`standard_normal` streams, or a stochastic-volatility term that produces
clustering endogenously rather than through a scripted crisis block. Either is
digest-invalidating and would move every stylised fact at once, including ER-5's
autocorrelation. **This is a release event and the owner's call.**


### ER-7, closed — what the fix was and what it moved

**The fix.** The market innovations in `run_path` are standardized Student-t
rather than normal, at `_INNOVATION_DF = 6.0`. Dividing the draw by
`sqrt(df/(df-2))` rescales it to unit variance, so a world declaring 16% equity
volatility still gets 16% equity volatility — it simply arrives with occasional
large months instead of uniformly middling ones. The macro state innovations
(rate, spread, inflation) stay Gaussian: the defect was in return tails, and
widening the macro shocks would have been a different change wearing this fix's
clothes.

`df = 6` is CHOSEN from the empirical literature on monthly equity index
returns, which fits degrees of freedom in the 4–8 region. **It was not tuned to
land the gate inside its band.** One value was picked on the literature, run
once, and the result reported wherever it fell.

**Measured, `python -m ah.battery.report`, 64 paths, seed 42:**

| metric | toy-v0.3 | toy-v0.4 | band | verdict |
|---|---|---|---|---|
| `excess_kurtosis` | 0.0853 | **1.644** | [0.5, 8.0] | fail → **pass** |
| `hill_tail_index` | 5.799 | **4.450** | [2.0, 6.0] | pass → pass, off the thin-tail edge |
| `skewness` | −0.0112 | 0.0201 | [−1.5, 0.5] | pass |
| `max_drawdown_median` | −0.5946 | −0.6015 | [−0.65, −0.12] | pass |
| enforce failures | 1 | **0** | | |

**IT MADE ER-5 SLIGHTLY WORSE, and that is reported rather than buried.**
`acf_r_lag1` moved from 0.364 to **0.4111** against its drafted [−0.2, 0.2].
Heavier tails do nothing about a rectangular crisis block — the mechanism ER-5
names — and the larger monthly moves inside that block appear to have
strengthened the pooled lag-1 autocorrelation rather than diluted it. ER-5
remains open and is now the largest stylised-fact defect in the engine. The gate
is `todo` (observed before ratification), so nothing blocked; the number is worse
and is recorded as worse.

**v0.4 DID NOT SURVIVE ITS OWN GATE.** The full-suite run on the v0.4 branch
failed 11 tests, and the diagnosis (2026-08-06) found one real defect among
them: `pe = 1.4 * eq + ...` is levered on equity with **no floor**, and a t(6)
tail month reached equity **−91.7%**, hence pe **−127.7%** — an impossible
return for a long-only holder, and one that NaN-poisons cumulative growth
(`(1 + r/100) < 0` raised to a fractional power). Measured ~2 breaching paths
per 600 on stagflation — an **~18% chance per 60-path ensemble** of a NaN
crash in the credibility console. Under Gaussian innovations the breach needed
a ~16σ month and was unreachable; t(6) made it merely rare. v0.4's numbers
exist only in that branch's diagnosis record.

**The v0.5 close-out: tails + limited liability.** Every monthly return is
floored at **−99%** (`_MONTHLY_RETURN_FLOOR_PCT`, applied uniformly to all
eight streams after construction). −99 rather than −100 so a floored month
leaves a positive growth factor. It truncates the constructed return, not the
innovation, so vol/correlation structure above the floor is untouched; the
floor does not bind on the golden path (the v0.4-regenerated golden digest
carried over unchanged).

**Measured, `python -m ah.battery.report`, operating size, 2026-08-08:**

| metric | toy-v0.3 | toy-v0.5 | band | verdict |
|---|---|---|---|---|
| `excess_kurtosis` | 0.0853 | **2.0919** | [0.5, 8.0] | fail → **pass** |
| `hill_tail_index` | 5.799 | **4.3839** | [2.0, 6.0] | pass → pass, off the thin-tail edge |
| `skewness` | −0.0112 | 0.0221 | [−1.5, 0.5] | pass |
| `max_drawdown_median` | −0.5946 | −0.5976 | [−0.65, −0.12] | pass |
| enforce failures | 1 | **0** | | |

(`acf_r_lag1` reads 0.2682 here vs the 0.4111 quoted above for v0.4 — both on
their own ensembles; AM-2026-08-06-002 records that pooled ACF statistics move
with ensemble size, so treat cross-version ACF comparisons as indicative only.
ER-5 remains open either way.)

**What it invalidated.** `TOY_ENGINE_VERSION` → `toy-v0.5`; presets moved to
the **5xx `world_id` block** (the 4xx block was never published); the engine
golden digest carried over from the v0.4 regeneration (floor non-binding on
that path, prior v0.3 digest still kept in the test); institution golden
57.923474 → **80.894413** and the play-linkage pin 76.712... → **86.890...**
(milder typical months compound better — see ER-8);
`app/fixtures/toy.bundle.gz` rebuilt from a fresh v0.5 stagflation run and
re-verified by the TypeScript seal suite. Any RunRecord made under `toy-v0.3`
or earlier will no longer replay — which the QA console already surfaces on
`/run/<id>`.


## ER-8 — toy-v0.5's typical months are milder, and the forced-secondary mechanic is preset-unreachable

**Status:** OPEN, AMENDED 2026-08-12 — partially closed by the ER-6
close-out: the declared call curve's faster pace revived the forced
secondary on **deflation_bust (6/20 seeds, 19 events, max 4 in one seed)**,
near its pre-v0.5 behaviour (8/20 under v0.3), while stagflation,
goldilocks, reflation_boom and the generated stagflation_1974 remain 0/20 —
distress stays rare enough to mean something, and reachable again in the
harshest playable world. The typical-months-milder half of this entry (the
ER-7 trade) still stands, as does the ER-5 rectangular-crisis root for the
worlds where the mechanic stays dormant.
**Found:** 2026-08-06, by the v0.4 gate diagnosis; confirmed under v0.5.

**What happens.** Variance-normalized Student-t keeps *declared* volatility
fixed while concentrating it into rare large months, so *typical* months are
milder than under Gaussian innovations. Compounding drag falls and hold-course
outcomes rise (the stagflation twin: 57.9 → 80.9 on the same declared
parameters). The A/B on deflation_bust at its base seed: forced secondaries
1 → 0, forced quarters 30 → 20, minimum NAV 19.3 → 41.0.

**The sharp edge:** across 20 seeds of every shipped preset, `forced_secondaries`
is now **zero everywhere** (it fired on 8/20 deflation_bust seeds under v0.3).
The mechanic the play surface calls "the behaviour that makes a VOLUNTARY
secondary a real decision" is dead in every shipped world. The mechanic itself
still works — `tests/test_play.py` now covers it with a schema-bound maximal
world (vol 45, drift −15, 12-quarter severity-1.0 crisis; forced secondaries
on 10 of 11 seeds) — but no *playable* world reaches it.

**What a fix looks like.** Either a preset deliberately calibrated into the
liquidity-stress region (a new world, not a re-parameterization of a published
one), or crisis-block realism (ER-5's fix) restoring clustered sustained
drawdowns that exhaust liquid sleeves organically. Bundling it into ER-5 is
attractive since both trace to "the crisis is a rectangular block".
**A release event and the owner's call.**

---

## ER-9 — Single months larger than whole historical bear markets, with no economic ceiling

**Status:** OPEN — the other face of the ER-7 fix, sibling to ER-8's milder
typical months.
**Found:** 2026-08-11, by the owner reading the credibility console's worst-DD
column on the rebuilt stagflation world and asking how a 96%/100% worst
drawdown is justified as an extreme outcome. It is not.

**What happens.** Variance-normalized Student-t(6) holds *declared* volatility
fixed by concentrating it into rare enormous months, and nothing between the
sampler and the −99% limited-liability floor bounds how large one month can
be. On the stagflation preset at its base seed (400 paths), the worst equity
path's 95.8% drawdown is delivered by a **single −86.3% month** — the whole of
1929–32 (about −89%) compressed into one month, against a worst *recorded* US
equity month of about −30% (September 1931). PE, 0.98-correlated and levered,
prints two months at the −99 floor (the "100%" drawdown, exactly the ~0.3%
binding rate the ER-7 close-out predicted), and HY prints a −25.8% month
against a worst recorded of about −16% (October 2008). The tail's *existence*
is justified — 1 in 400 hostile decades should be terrible; its *anatomy* is
not: no closing, circuit-broken market delivers a Depression in one month.

**This is engine-wide, not a stagflation quirk.** With the tail bands in
place, all four presets flag at 400 paths: **goldilocks — the benign world —
prints a −57.9% equity month and an −80.8% PE month**; reflation_boom a
−74.5% equity month and a floored −99% PE month; deflation_bust puts *equity
itself* on the −99 floor. A world whose narrative is "nothing goes wrong"
should not contain a month twice as bad as any in recorded history.

**A second defect layered on the PE case:** the sleeve is one levered asset,
but the thing it models is a diversified multi-cohort programme. One fund
going to zero in a month is plausible; the whole programme doing so is not —
diversification across funds should bound sleeve-level monthly moves well
above the limited-liability floor.

**Detection shipped with this entry** (console, unsealed, not a fix): the
credibility console's `PLAUSIBLE` bands now declare per-asset tail edges —
worst single month and worst path drawdown — and flag breaches like any other
band (`credibility-tail-bands` branch). The stagflation review that found
this entry now produces flags instead of requiring the owner to squint at a
cell.

**What a fix looks like.** A tempered tail: keep t(6) body behaviour but cap
or exponentially temper single-month moves at an economically defensible
floor per asset class (equity somewhere below the worst recorded month, with
the cap documented as a modelling choice), and give the PE sleeve a
diversification bound so programme-level months cannot reach a single-fund
outcome. Tuning should re-check ER-8's other face: tempering the huge months
pushes variance back into typical months, which may also revive the forced
secondary. The three entries ER-5, ER-8 and ER-9 form one family — the crisis
shape and the tail shape trade against each other under fixed declared vol —
and are best fixed together, not piecemeal.

**What it invalidates.** Any tail change moves every world's digests and the
scored path: new `world_id` block, `TOY_ENGINE_VERSION` bump, and a
`PLAY_ALPHA_VERSION` bump so leaderboards never mix engines. It does NOT
touch `schemas/`, `mappings/`, or any seal. **A release event and the
owner's call.**

---

## ER-10 — Reported PM marks filtered one month in three, not the whole quarter

**Status:** CLOSED 2026-08-13 (`toy-v0.6`, `er10-01-reported-marks` branch)
**Found:** 2026-08-12, the owner reading the 1974 generated world's fan
charts — the reported private-market plane visibly failed to catch up to
the true one over the decade.

**What happens.** `_reported_marks` (`src/ah/core/engine.py`) applies the
appraisal filter `rep = w * true + (1 - w) * prev` at quarter-end months
only, as designed — that part is `emit_reported_marks`/`weights_on_truth`
working as declared. The defect is what `true` meant in that line: until
this fix it was the quarter-end MONTH's own return alone. The two months
either side of it were never read by the filter — not smoothed in, simply
discarded. A unit-DC-gain filter fed one month in three converges to
roughly a third of the signal it was meant to track: cumulative reported
return lands near 1/3 of cumulative true, not delayed-but-equal to it.

**Magnitude, measured on shipped worlds over the full decade:**

| world | sleeve | reported | true |
|---|---|---|---|
| stagflation | pc | 23% | 77% |
| stagflation_1974 (generated) | pe | 27% | 125% |

**What shipped.** The quarter-end mark now compounds the whole quarter's
true return before filtering: `rep_q = w * q_true + (1 - w) * rep_{q-1}`,
where `q_true` is the three months' own compounded return (Geltner partial
adjustment, unit DC gain, applied to the quantity — the quarter — the
filter was always meant to be smoothing, not to one-third of it). Cumulative
reported now catches up to cumulative true over a long horizon: pooled over
a 16-path ensemble, the ratio lands in 0.80–1.20 on both the real-panel
(`stagflation`, `goldilocks`) and generated (`stagflation_1974`) paths,
which share the same `_reported_marks` call via `ah/port/adapter.py`.

**Consequences — what the fix invalidated.**

- `TOY_ENGINE_VERSION` `toy-v0.5` → `toy-v0.6`; the engine golden digest
  re-pinned `6c3f7c896a552b49...` → `61e78e609d2a360b...`.
- Preset world-id fences moved so scores made under the two engines can
  never share a leaderboard row: the shipped presets' 50x sub-block
  `501–504` → the 51x sub-block `511–514`, and the generated
  `stagflation_1974` `602` → `603`. Old rows are FENCED, not deleted —
  the leaderboard key already carries world identity.
- Both committed bundles rebuilt and re-verified (`app/fixtures/toy.bundle.gz`,
  `app/fixtures/gen.bundle.gz`).
- The play-linkage golden moved `86.32350859293307` → `98.04417427685921`
  (`tests/test_play_linkage.py`) — a materially larger move than the fix's
  own description suggests, because reported marks now track the crash
  instead of lagging behind a right-censored one-month sample.
- The ER-6 `peak_unfunded_ratio` acceptance ceiling moved `1.5` → `1.6`
  (`tests/test_programme.py`): crash-responsive reported marks make the
  DN-5 counter-cyclical pacing rule lean harder into the trough, and the
  measured peak on the pinned seed moved `1.22` → `1.52` at quarter 20 (the
  stagflation trough — numerator up via the leaned-in commitment multiplier,
  denominator down via depressed true NAV). The declared pathology band
  `2.4–3.3` stays far away; this is a ceiling re-pin, not a regression
  toward the pathology ER-6 closed.

**Scoring note.** Reported marks feed the DISPLAY plane and the
reported-basis session value, not the alpha computation: alpha is
player-minus-twin, and both sides of that subtraction carried the same
one-month-in-three bias, so it largely cancelled. Levels were wrong — a
player watching the reported PM line over a decade saw roughly a third of
the true cumulative return — but rankings mostly weren't, because the bias
was common to player and twin alike.

**Two permanent guards, so this cannot silently recur.**

1. A catch-up invariant test on both paths that share `_reported_marks` —
   the engine test (`tests/test_engine.py::test_reported_marks_catch_up_to_truth_er10`)
   pools a 16-path ensemble; the generator adapter test
   (`tests/test_gen_adapter.py::TestAgainstTheRealPanel::test_gen_reported_marks_catch_up_to_truth_er10`)
   is a single-path check that runs where the local data catalog is present. Both assert
   cumulative reported/true lands in `0.80–1.20`.
2. The credibility console's reported-plane catch-up row
   (`src/ah/credibility.py`, `SmoothingStats.catchup_ratio`/`catchup_flagged`,
   `CATCHUP_LO/HI = 0.8/1.2`): flags any sleeve outside that band on every
   `ah credibility` run, with a near-zero guard
   (`CATCHUP_NEAR_ZERO_PP = 5.0`) so a deflation-style world whose cumulative
   true return sits near zero reads "n/a" instead of a meaningless ratio.

## ER-11 — The reported plane is the engine's filter, not the sealed per-sleeve kernel

**Status:** CLOSED BY DECISION 2026-08-14 (owner accepted route (a) of the
translation-layer audit's F1). No engine number moved.
**Found:** 2026-08-14, the translation-layer audit
(`docs/superpowers/specs/2026-08-14-translation-layer-audit.md`, finding F1)
— three read-only auditors checking behavior against DESIGN documents.

**What happens.** DN-5 SM-10 requires the reported plane to be "one model,
two views": the sealed smoothing kernel (`mappings/smoothing-kernel-v1.0.yaml`,
inside the G3 lock) paired with the de-smoother that judged the mappings, so
that de-smoothing a reported series recovers the true one exactly. Two
implementations of the forward direction exist:

| | applies | where | granularity |
|---|---|---|---|
| engine filter | `rep_q = w*q_true + (1-w)*rep_{q-1}`, `w` = 0.35/0.30/0.35 | `ah/core/engine.py::_reported_marks` | three aggregates (pe/pc/re) |
| sealed kernel | per-sleeve MA weights θ (buyout 85/15, VC 60/15/25, …) | `ah/port/smoothing.py` + the artifact | nine PM sleeves + seven HF |

**Everything player-facing has always used the first one.** The port kernel
is reached only by its own tests, `campaign_exhibit.pm_plane_stats`, and two
inspection scripts — never by `ah/port/adapter.py`, the session service, the
bundle, or the console. The two disagree materially: quarterly reported
autocorrelation for buyout is **0.55** under the engine filter and **0.06**
under the sealed kernel. The shipped blur is heavier and coarser than the
sealed one.

**The decision (owner, 2026-08-14).** The engine's filter IS the product's
smoothing model. The SM-10 divergence is recorded here rather than closed by
code, on these grounds: the filter is independently validated on its own
evidence (ER-10's catch-up invariant, the console's catch-up row, the console
walks on every shipped seed), and it is the surface every score and every
committed fixture was built against. Routing the sealed kernel live remains
available and is scoped below; it is a release event, not a cleanup.

**What the shipped path does NOT get, stated plainly.** Per-sleeve mark
behavior (a VC mark and a mezzanine mark blur identically today), the sealed
kernel's HF residual-correlation and CTA rules on any player-facing surface,
and the exact SM-10 inverse property — de-smoothing a shipped reported series
does not recover the true series, because the series was not made by the
sealed forward kernel.

**What reopening it would cost** (estimated 2026-08-14, recorded so a future
reader does not re-derive it): the sealed artifact is per-sleeve and the
engine plane is three aggregates, so the first task is a design decision —
how nine θ vectors collapse into three — which needs its own amendment
because the seal does not cover it. Then the standard cascade:
`TOY_ENGINE_VERSION` bump, new preset world-id block, fixture and golden
regeneration, and a full revalidation (the catch-up band, the pacing
counter-cyclicality numbers, and `peak_unfunded` all move, because pacing
keys off the reported plane and less-sticky marks fall faster in a crash —
expect a re-pin of the ER-6 ceiling like ER-10's). **≈3 working days, 4 with
a re-pin cascade.** Applying the kernel per-sleeve at the port layer instead,
and moving the play surface onto it, is a larger track (a week-plus) that also
touches which module the scored surface reads from.

**The bug this uncovered — FIXED, and it never touched a shipped number.**
`ah/port/smoothing.py`'s stickiness branch built a weight vector one element
short of the lag window whenever a sleeve's lag weights were all zero.
NumPy's einsum broadcast that single weight across every lag slot, so each
mark came out `true_t + true_{t-1}` at full weight — the return counted
twice, every period. Only `pm_direct_lending` has such a θ (`[1.0, 0.0]`, a
boundary fallback in the sealed artifact); compounded, its reported
cumulative return ran **4.47x** true (+1126% vs +252%). Exposure, checked
consumer by consumer: no `ah/eval/` module imports the kernel (no judged
number could move); `scripts/run_2022_replay.py` — the G1-era evidence path
— smooths with the non-degenerate `hf_event` θ, so the branch never fired
there; and the one committed artifact that did run it
(`docs/data/CAMPAIGN-R1-TRANSLATION.md`'s PM plane table) carried an
all-zero direct-lending series, so the doubled numbers were zeros. The fix
carries the full lag window explicitly and raises on any weight vector that
does not span it, so a short vector can never be broadcast again.
