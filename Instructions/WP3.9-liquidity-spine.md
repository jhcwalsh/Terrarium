# WP3.9 — Liquidity Spine
## Cashflow engine, Phase A subset

*Draft v0.1 · July 2026 · New work package. Sits between WP3.7 (portfolio engine) and the Step 4 experience slice. Strict subset of the Step 3 cashflow engine (D7), not a prototype of it.*

---

## 1. Why this exists

Phase A as scoped can show a player that they became overweight private assets. It cannot show them the consequence, because every source of liquidity demand — capital calls, spending, benefit payments — lives in the deferred cashflow engine.

Two things break as a result. The sharing spec puts **forced-sale count** on the outcome card and **forced-sale incidence** on the leaderboard, and as scoped neither has a mechanism behind it. And the more important half of the alternatives lesson goes missing: being notionally overweight is a dull story, having to sell something you didn't want to sell is the story.

This work package builds the minimum that makes forced sales real.

## 2. The subset principle

**Non-negotiable design constraint.** WP3.9 implements the full Takahashi–Alexander recursions with market-linkage coefficients set to zero and a single synthetic cohort per sleeve. Step 3 turns the coefficients on and adds real cohorts. It does not re-implement.

The line between them is sharp and worth stating precisely:

| | Phase A (WP3.9) | Step 3 (D7) |
|---|---|---|
| **NAV growth** | Market-driven — the sleeve's true return | Same |
| **Call rate** | Fixed schedule | Linked to dry-powder covariate |
| **Distribution rate** | Fixed, age-dependent bow | Linked to exit-market state |
| **Cohorts** | One synthetic cohort per sleeve | Real vintage stack |
| **Commitments** | Generic fixed annual schedule | Your commitments, your pacing plan |
| **Secondary sales** | Fixed haircut | Discount linked to liquidity state |

NAV growth being market-driven is not optional even in the thin version. A cashflow engine whose asset values don't move with the simulated world is disconnected from the product. What gets deferred is the linkage of *rates* to market state — which is where D7's real content and real calibration burden sit.

## 3. State

Per private sleeve, per period:

```
commitment       cumulative committed capital
PIC              paid-in capital to date
unfunded         commitment − PIC
NAV_true         current value on the true basis
NAV_reported     current value on the reported basis (WP3.3 kernel)
age              periods since the synthetic cohort's first call
```

Plus one portfolio-level:

```
cash             the account everything settles through
```

## 4. Recursions

Standard TA form, per sleeve:

```
call_t          = RC × unfunded_{t-1}
dist_rate_t     = (age_t / L)^B × Y
dist_t          = dist_rate_t × NAV_true_{t-1} × (1 + r_t)
NAV_true_t      = NAV_true_{t-1} × (1 + r_t) + call_t − dist_t
```

where `r_t` is the sleeve's **true** return from WP3.2. `NAV_reported` is `NAV_true` passed through the WP3.3 smoothing kernel — the same kernel, not a second one.

Public sleeves have no call or distribution machinery; they hold value and grow at their return.

## 5. Spending

The generic endowment spends on a smoothed rule: a fixed rate applied to a trailing twelve-quarter average of **reported** total portfolio value.

**Reported, not true — and this is the point.** Endowments spend off the values in their accounts, and those values contain smoothed private marks. In a drawdown, reported value falls more slowly than real value, so spending stays high in absolute terms exactly when liquid assets are scarcest. That is a genuine and underappreciated amplifier of the liquidity squeeze, it costs one line of code to represent correctly, and getting it wrong makes the whole episode milder than it was.

A hybrid rule (weighted blend of prior-year spending inflated, and a percentage of market value) is a parameter, not a rebuild.

## 6. Cash waterfall and forced sale

Each period, in order:

1. Cash receives distributions and public-sleeve income
2. Cash pays capital calls
3. Cash pays spending
4. If cash < 0 → **forced sale**

Forced-sale priority: liquid public sleeves pro-rata, then — if exhausted — a forced secondary sale of private NAV at a fixed haircut, logged loudly as a distress event.

Every forced sale writes an event with period, amount, cause, and which sleeves were sold. That record is what the outcome card and the leaderboard metric consume, and it's what the post-game annotation screen has to explain.

## 7. The moment this creates

Worth naming because it's the product's best single screen, and it emerges from the pieces rather than being designed.

In a 2022-shaped decade the player sees, simultaneously: a reported private weight *rising* while the true weight falls; spending held up by smoothed values; capital calls arriving on schedule regardless; distributions drying up; and a cash balance heading toward a forced sale of the only assets that can actually be sold.

The reported plane says one thing, the cash account says another, and the cash account is the one that's real. That's the whole argument of the product in a single decade, and none of it exists without this work package.

## 8. Explicitly out of scope

Vintage cohorts. Your commitments and pacing plan. Market-linked call and distribution rates. Liability cashflows, funding ratio, contribution rules. Secondary pricing as a function of liquidity state. Manager-level detail of any kind.

All institutional tier. The free/paid boundary is unchanged: Phase A gives a **generic** liquidity structure that is the same for every player, the institutional tier gives **yours**.

## 9. Parameters to freeze

`RC` call rate · `L` fund life · `B` bow · `Y` yield ceiling · annual commitment rate per sleeve · spending rate · smoothing window · forced-secondary haircut.

Register these in the model parameter register with the same discipline as everything else. Defaults calibrated to index-level pacing, documented as generic and not representative of any institution.

## 10. Acceptance tests

| Test | Expectation |
|---|---|
| Degenerate | Zero commitments, zero spending → portfolio path equals the WP3.7 path exactly |
| Invariants | `unfunded` never negative; `PIC` never exceeds `commitment`; cash reconciles each period |
| Pacing | Calls over a full fund life sum to approximately the committed amount under default parameters |
| Kernel reuse | `NAV_reported` reproducible by applying the WP3.3 kernel to `NAV_true` — no second smoothing path |
| Episode shape | Under a 2022-shaped decade: reported weight rises while true falls; cash declines; forced sale triggers within a plausible parameter range |
| Determinism | Same seed → bit-for-bit identical cashflow path into the RunRecord |

The episode-shape test is the thin analogue of D7's 2022 reproduction criterion. It is **not** that criterion and must not be reported as satisfying it — the market linkage that D7's test is actually about is switched off here.

## 11. Inspection point

Extends Amendment A1 with **I6 · Liquidity inspection**, attached to WP3.9.

Shown: cash balance, calls, distributions and spending on one timeline across a drawdown episode, with forced sales marked.

Catches: calls that arrive too smoothly, distributions that fall away too fast or too slowly, and forced sales that trigger either never or constantly — all of which are parameter errors invisible to the invariant tests and obvious on sight to anyone who has run a pacing model.

## 12. Sequencing

After WP3.7 — portfolio state must exist. After WP3.3 — the reported basis is required for the spending rule and for the toggle. Before the Step 4 experience slice, since the outcome card consumes forced-sale events.

Small package. The engine is a few recursions and a waterfall; the work is in parameter defaults and the test battery.

---

*Not investment advice. Generic parameters; not representative of any institution's pacing or spending policy.*
