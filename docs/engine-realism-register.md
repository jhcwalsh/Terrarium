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
