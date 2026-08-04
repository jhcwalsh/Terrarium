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
