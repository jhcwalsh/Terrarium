# WP3.9 — Liquidity Spine
## v0.2 · Commitment as decision · vintage cohorts · market-linked rates

*July 2026 · Supersedes v0.1. Changelog at §14. Two parameters are deliberately unfilled and marked ⛔ — they require calibration input and must not be defaulted.*

---

## 1. What changed and why

v0.1 treated commitment as an exogenous schedule and rates as deterministic. Both are now wrong by decision:

- **Commitment is a decision variable, per sleeve.** It is one of the areas allocators get wrong, and a model that cannot pose the question cannot teach it.
- **Call and distribution rates are market-linked.** The consequence for liquidity is the point, not a refinement.
- **Vintage cohorts are structural, not deferred.** This is forced: a commitment decision made in year three creates a pool at a different point on its call schedule and its distribution bow than one made in year one. A single synthetic cohort cannot represent both.

The three changes are one change. Any of them alone is incoherent.

## 2. What this buys — the mechanism the product exists to show

A mature programme is approximately **self-funding**: distributions from older vintages pay calls on newer ones. Net external cash demand is near zero, and this is why programmes feel comfortable in normal conditions.

Stress breaks it from both ends simultaneously. Distributions collapse — exits stop, the IPO window shuts, sponsors hold rather than sell into a bad tape. Calls continue, or fall by less. The shortfall lands on the liquid portfolio at precisely the moment the liquid portfolio is the only thing that can be sold and the worst time to sell it.

**And then the error compounds.** The allocator, seeing coverage deteriorate, cuts commitments. That starves the vintage stack in the years when entry pricing is best, and opens a distribution hole five to seven years later — a *second* liquidity squeeze arriving in a decade that had already recovered.

That consequence is invisible at three years and unmistakable at ten. It is the strongest argument the architecture has for why a decade is the right unit, and it does not exist without this work package.

## 3. State

Per **(sleeve, vintage)**:

```
vintage_year     the period the cohort was committed
commitment       committed capital for this cohort
PIC              paid-in capital to date
unfunded         commitment − PIC
NAV_true         value on the true basis
NAV_reported     value on the reported basis (WP3.3 kernel)
age              periods since first call
```

Aggregated to sleeve and portfolio level for display and scoring. Portfolio-level:

```
cash             the account everything settles through
coverage_true    Σ unfunded / Σ NAV_true
coverage_rep     Σ unfunded / Σ NAV_reported
```

**Both coverage measures are computed and both are shown.** In a drawdown, true NAV falls and reported NAV falls less, so reported coverage looks healthier than true coverage — the denominator effect reappearing in the liquidity metric. This is the toggle extended to the number allocators actually watch, and it costs nothing since both bases already exist.

## 4. Recursions

Per cohort:

```
call_rate_t     = RC_base × f_call(S_t)
call_t          = call_rate_t × unfunded_{t-1}

dist_rate_t     = (age_t / L)^B × Y × f_dist(S_t)
dist_t          = dist_rate_t × NAV_true_{t-1} × (1 + r_t)

NAV_true_t      = NAV_true_{t-1} × (1 + r_t) + call_t − dist_t
```

`r_t` is the sleeve's true return from WP3.2. `NAV_reported` is `NAV_true` through the WP3.3 kernel — the same kernel, not a second one.

New cohorts are created by the commitment decision (§5) with `PIC = 0`, `NAV = 0`, `age = 0`.

### 4.1 The linkage functions

`S_t` is the market state: equity drawdown depth, HY spread level, and the WP3.2 exit-market state.

**`f_dist` — the distribution response.** Falls in stress, and this is the load-bearing function in the engine. Two parameters govern it:

⛔ **P-A · Drought depth and duration.** How far the distribution rate falls at the trough of a severe episode, and how long it stays depressed before recovering. *Requires calibration input. Everything about the self-funding breakdown scales with these two numbers, and a plausible-looking default would silently determine the product's central claim.*

**`f_call` — the call response.** Net effect on a multi-vintage stack is what matters, not the behaviour of any single fund. Structure: deployment slows through the acute phase as deal volume collapses and price discovery stalls, then accelerates as pricing resets. Sign is ambiguous at the aggregate level and lag is the substance — a slowdown of two quarters followed by acceleration produces a very different stack profile than a slowdown of six.

Both functions are bounded, monotone in the state, and calibrated on episode data. Their forms are frozen in the parameter register; their coefficients are the calibration work.

## 5. The commitment decision

**Per sleeve, at each annual decision window.** The player sets next year's commitment to each private sleeve. New cohort created, unfunded rises, calls follow the schedule.

Constraints: non-negative; capped at a multiple of portfolio value to keep the decision space sane. The cap is a guardrail, not a policy — over-commitment relative to NAV is the whole point and must be permitted well past comfortable.

### 5.1 The twin's commitment policy — required, not optional

Decision alpha on commitments is undefined unless the hold-course twin has one. **The twin follows the pacing plan set at t = 0, mechanically, regardless of conditions.**

This makes the headline number on commitment decisions exactly what it should be: **the cost of flinching**. The player who cuts commitments in the drawdown is scored against the version of themselves who stuck to the plan. That is the real decision, the real error, and now a measured one.

## 6. Coverage — the metric that gets watched

**Unfunded / NAV**, on both bases, displayed continuously, scored, and warned on.

One property worth surfacing in the interface rather than leaving implicit: **coverage deteriorates in a drawdown without the allocator doing anything**, because the denominator falls while unfunded does not. A player who sees coverage worsen and reacts is often reacting to arithmetic rather than to a change in their position. That is a genuine and common error, it is now representable, and it is a good candidate for the post-game annotation screen.

⛔ **P-B · Danger thresholds.** The coverage level at which a programme is uncomfortable, and the level at which it is genuinely in trouble. *Requires calibration input. Warning bands, scoring, and the help agent's language all key off these; guessing them would mean the product teaches a threshold nobody recognises.*

## 7. Spending

Unchanged from v0.1 and still deliberate: a fixed rate on a trailing twelve-quarter average of **reported** total portfolio value.

Endowments spend off the values in their accounts, and those contain smoothed private marks. In a drawdown reported value falls more slowly than real value, so spending holds up in absolute terms exactly when liquid assets are scarcest. One line of code, and without it the episode is materially milder than the real thing.

## 8. Cash waterfall and forced sale

Each period, in order:

1. Cash receives distributions and public-sleeve income
2. Cash pays capital calls
3. Cash pays spending
4. If cash < 0 → **forced sale**: liquid public sleeves pro-rata, then forced secondary at a fixed haircut, logged as a distress event

Every forced sale writes period, amount, cause, and sleeves sold. That record feeds the outcome card, the leaderboard metric, and the annotation screen.

## 9. Scope boundary — where the institutional tier now sits

v0.2 absorbs a substantial part of what v0.1 deferred to D7. The boundary moves and must be restated:

| | Phase A (WP3.9 v0.2) | Institutional (Step 3) |
|---|---|---|
| Starting stack | Generic steady-state programme | **Your actual vintage stack, with its real age profile** |
| Commitments | Your decisions, generic sleeves | Your decisions, your sleeve structure and manager set |
| Linkage | Calibrated index-level | Same, plus your historical pacing |
| Liabilities | None | Benefit payments, contributions, funding ratio |
| Secondaries | Fixed haircut | Discount as a function of liquidity state |

**The legacy stack is the real institutional asset.** A live endowment's liquidity position is almost entirely determined by vintages it already owns and cannot change. Phase A starts everyone from the same clean steady state; the institutional tier starts you from where you actually are. That is a defensible boundary and arguably a sharper upgrade prompt than the one v0.1 had.

## 10. Parameters

`RC_base` · `L` · `B` · `Y` · `f_call` coefficients and lag · `f_dist` coefficients ⛔P-A · commitment cap · spending rate · smoothing window · secondary haircut · coverage bands ⛔P-B.

Register all of them. The two marked ⛔ are blocking: the package builds without them but must not be calibrated, demoed, or scored until they are set.

## 11. Acceptance tests

| Test | Expectation |
|---|---|
| Degenerate | Zero commitments, zero spending → path equals WP3.7 exactly |
| Invariants | `unfunded` ≥ 0; `PIC` ≤ `commitment`; cash reconciles; cohorts age monotonically |
| Steady state | Constant pacing in benign conditions → coverage converges to a stable ratio |
| **Self-funding** | Mature stack, benign conditions → net external cash demand ≈ 0 |
| **Stress breakdown** | Severe episode → distributions collapse, calls persist, net demand turns sharply negative, coverage rises on both bases |
| Coverage divergence | Reported coverage improves relative to true coverage through the drawdown |
| **The flinch test** | Commitments cut through a drawdown → distribution shortfall appears 5–7 years later; a second squeeze in a recovered decade |
| Determinism | Same seed, same decisions → bit-for-bit identical cashflow path |

The flinch test is the model's central claim about commitment behaviour. If it does not reproduce, the linkage or the cohort ageing is wrong, and no amount of parameter tuning elsewhere fixes it.

## 12. Inspection point I6

Extends Amendment A1. Shown across a drawdown episode on one timeline: cash, calls, distributions, spending, net cashflow, coverage on both bases, forced sales marked, and the vintage stack as a stacked area so the age profile is visible.

Catches: calls too smooth, drought too shallow or too deep, cohorts that never mature, forced sales that trigger never or constantly — all invisible to invariant tests and obvious to anyone who has run a pacing model.

## 13. Sequencing

After WP3.7 and WP3.3. Before the Step 4 slice. **This is no longer a small package** — cohorts, linkage and a new decision surface are real work, and the honest estimate is several times v0.1. That cost is accepted because commitment is where allocators actually err, and a Phase A that cannot pose the question teaches the wrong lesson.

## 14. Changelog

| From v0.1 | To v0.2 | Recorded against |
|---|---|---|
| Commitment exogenous | Decision variable, per sleeve | New — this note |
| Rates deterministic | Market-linked `f_call`, `f_dist` | **D7** — partial absorption into Phase A |
| Single synthetic cohort | Vintage stack | **D7** — forced by the commitment decision |
| Coverage not tracked | Unfunded/NAV on both bases | New |
| Twin commitment policy undefined | Mechanical adherence to t=0 plan | **D9** — decision-alpha definition extended |

The D7 and D9 entries matter: this package moves work across a boundary those decisions defined, and the changelog is where that gets recorded rather than in someone's memory.

---

*Not investment advice. Generic parameters; not representative of any institution's pacing or spending policy.*
