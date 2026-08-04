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

**Status:** open
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

**Consequences.** Changes every world's HY path and therefore every stored
digest, the institution's totals, and the scored path. Needs a
`decision_alpha_version` bump and a full bundle rebuild.

---

## ER-4 — Carry assets earn their carry almost risk-free

**Status:** open
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

**Consequences.** Touches every asset that prices off the rate. Digest-
invalidating; alpha-version-bumping.


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

**Status:** open (partly addressed by the display-only pacing ledger, see
CHANGELOG for the player-portal work)
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
