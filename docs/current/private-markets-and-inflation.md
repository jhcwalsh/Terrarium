# Private markets and inflation pass-through

*Status: GOVERNING (2026-08-15). A technical account of how the private market
asset classes are modeled across the three layers that model them, and of what
happens to a private book when the world's inflation changes.*

**The short version.** Private markets are modeled in three separate places
that agree on the state contract and disagree on almost everything else: the
`toy-v0` engine's three levered/spread/rate-linked return streams, the
generator adapter's sealed factor loadings, and `ah/port/`'s cohort cashflow
model that sits on top of either tape. The cashflow layer is the detailed one —
commitments, calls, a staggered vintage ladder, distributions on a bow,
terminal lapse, appraisal-smoothed marks, and a forced-secondary waterfall.

**Inflation does not reach any of it.** On the shipped player-facing path,
moving a world's average inflation from 1% to 12% changes the private equity
return by **exactly zero**, changes private credit by +0.02pp/yr and real estate
by **−0.12pp/yr**. Every apparent inflation sensitivity in the private
programme is a second-order consequence of holding five points of commodities
next to it: remove that sleeve and higher inflation makes the private book
slightly *smaller*. There is one field in the whole WorldSpec contract that
expresses asset-side inflation linkage — `structural.infrastructure.
inflation_linkage` — and it belongs to an asset class the engine does not
simulate. Measured numbers and the commands that produce them are in §4 and §7.

---

## 1. Three layers, and which one is live

| Layer | Module | What it produces | On the player-facing path? |
|---|---|---|---|
| **Return process (toy)** | `ah/core/engine.py` | monthly `pe`/`pc`/`re` true + reported returns | **yes** — `toy-v0.6`, the shipped tape |
| **Return process (generated)** | `ah/port/adapter.py` | the same three streams from sealed factor loadings | **yes** — for generated worlds |
| **Cashflow / institution** | `ah/port/` + `ah/play.py` | commitments, calls, distributions, NAV, forced sales | **yes** — `port-v4-ladder` |
| **Sealed sleeve mappings (9 sleeves)** | `ah/port/mapping.py` | HF + PM sleeve panels for research | research only |
| **Forward smoothing kernel** | `ah/port/smoothing.py` | fitted per-sleeve reported marks | **no** — ER-11 |

The last two matter for reading the evidence documents but do not touch a
score. `ah/port/smoothing.py`'s own header says so: the product's reported
plane is the toy engine's filter, not the fitted kernel, and that divergence is
recorded as ER-11.

---

## 2. How the return process models each class

### 2.1 The toy engine (`ah/core/engine.py`, `toy-v0.6`)

Three private streams, each a monthly percent return built from the same
market state as the public assets. `ASSETS` is
`(equity, bonds, hy, commodities, reits, pe, pc, re)` — **there is no
infrastructure asset**, and `reits` is dropped on generated worlds (OD-3).

**Private equity** is levered public equity plus a fixed carry:

```
pe = 1.4 * eq + (illiquidity_premium + entry_multiple_drift) / 12 + 2.0 * e_pe
```

A 1.4× beta to the equity stream, an annual illiquidity premium and a
valuation-multiple drift taken from `structural.private_equity` (defaults 2.0
and 0.0), and an idiosyncratic Student-t innovation. The equity beta is a
constant: `structural.private_equity.leverage_turns` is in the schema and in
four presets, and **no engine reads it**, so the leverage a world declares does
not change the beta the engine applies.

**Private credit** is a spread-earning book with a lagged, spread-scaled loss
rate:

```
pc = (rate + 4.5)/12 − pc_loss_m − 0.8*d_spread + 0.18*eq + 1.45*e_pc
pc_loss_m = (annual_loss_rate/12) * (0.7 + 0.6 * spread_lagged/400) * crisis_amp
```

Losses key on the HY spread as it stood twelve months earlier and are amplified
1.6× inside crisis months (ER-1's close-out). `recovery_rate_pct` and
`spread_over_base_bps` are in the schema and unread; the +4.5% credit spread
over base is a hardcoded constant.

**Real estate** is an income stream that reprices on rates:

```
re = 4.5/12 − cap_rate_shift/(100*nm)*2.2 − 4.0*d_rate + 0.35*eq + 1.5*e_re − 1.0*crisis
```

`cap_rate_shift_bps` is read; `income_yield_pct` is **not** — the 4.5% income
yield is hardcoded, so a world declaring 8% property income gets 4.5%.

Every monthly return is floored at −99% (limited liability, ER-7's close-out).

### 2.2 The generated path (`ah/port/adapter.py`)

For generated worlds the same three streams come from the sealed
`mappings/sleeve-mappings-v1.0.yaml` PM loadings applied monthly, via
`PM_SLEEVE_FOR_ASSET = {pe: pm_buyout, pc: pm_direct_lending, re:
pm_re_value_add}`. The regressor set is fixed and is worth reading closely:

```
equity_mkt, smb, hml, mom, d_level, d_slope, d_ig
```

**There is no inflation regressor and no commodity regressor.** The estimated
loadings are also far smaller than the priors they superseded — `pm_buyout`
came out at `equity_mkt` 0.348 against a 1.2 prior, and `pm_direct_lending`
estimated to *all-zero loadings* with `r2_train_val = −0.0` on 39 quarters, so
generated-world private credit is alpha plus noise. `pm_re_value_add` is
`equity_mkt` 0.087 with r² 0.013. These are recorded honestly in the artifact
(each carries its `prior_superseded` block and its own r²); the point here is
what they imply — on the generated path, two of the three private sleeves are
very nearly independent of everything the world does.

### 2.3 Reported marks

Both paths share `engine._reported_marks`: a Geltner partial adjustment applied
at quarter ends only, to the **whole quarter's compounded true return**:

```
rep_q = w * q_true + (1 − w) * rep_{q−1}
```

with `w` per sleeve from `structural.smoothing.weights_on_truth` (defaults
0.35 / 0.30 / 0.35). Unit DC gain, so cumulative reported catches cumulative
true. Until `toy-v0.6` this filtered only the closing month and reported PM
cumulated about a third of truth — that is ER-10, and it was found by reading a
chart, not by a test.

---

## 3. How the cashflow layer models a private programme

This is where the modeling actually lives, in `ah/port/` driven by
`ah/play.py`. It is the same object model for all three sleeves — the sleeves
differ only in their return stream and their target weight, not in their
mechanics.

**The cohort recursion** (`ah/port/cohort.py`) is the model-parameter-register
form, quarterly:

```
call_t = RC(age) * f_call * unfunded          (capped at unfunded)
dist_t = Y * (age/L)^B * f_dist * NAV_grown   (bounded [0, 1])
NAV_t  = NAV*(1+r) + call_t − dist_t          (floored at 0)
```

At `age >= L` (extensions excluded) the fund liquidates in full and the
residual unfunded commitment **expires** and is ledgered as `expired_undrawn` —
ER-6's close-out, chosen over silently retaining it forever.

**Market linkage** is tier 1 (`ah/port/cashflow_tier1.py`), frozen in
`mappings/cashflow-tier1-v1.0.yaml` before any replay existed:

```
f_dist = clip(exp(−1.541*dd − 1.377*ln(spread_ratio)), 0.3, 1.5)
f_call = clip(1 − 0.1*dd, 0.5, 1.2)
```

`dd` is equity drawdown depth, `spread_ratio` the HY spread over a 400bp
reference. Both consume **continuous market states only** — no regime label, no
recession dummy, enforced by signature (Delta 3). Distributions dry up hard in
stress; calls barely slow. Note what the two arguments are: equity drawdown and
credit spread. **Inflation is not an input to either function**, so a
stagflation world starves distributions only to the extent that it also crashes
equities or widens spreads.

Running the same recursion with `f_call = f_dist = 1` and fees off *is* tier 0,
the constant-G Takahashi–Alexander benchmark — asserted by test, so there are
never two models that can disagree about anything except the linkage.

**The opening book** is a staggered ladder (`play._seed_ladder`): one rung per
year of the ten-year contractual life, each warmed forward by the model itself
at the rate that reproduces the fixture's own TVPI at its own age, then scaled
so the sleeve opens at the intended NAV. Before this (ER-12, closed
2026-08-14) all three sleeves were clones of one age-5.25 cohort and lapsed in
the *same quarter*, expiring 17% of the decade's calls at once. A new vintage
is committed annually at 18% of the sleeve's target NAV, flexed by the pacing
rule toward the policy private weight on **reported** marks.

**The institution** (`ah/port/engine.py`) runs a quarterly waterfall: cash
receives distributions, pays calls, then pays spending at 4.5%/yr on the
trailing twelve-quarter average of **reported** total value — so spending holds
up in absolute terms exactly when liquid assets are scarcest. If cash goes
negative, liquid sleeves sell pro-rata first, then private interests at a 19%
secondary haircut, every event logged. Private weight is checked against a
(0.15, 0.40) policy band on both the true and the reported basis.

---

## 4. Inflation pass-through: the measured answer

### 4.1 Where inflation exists in the contract

`factor_conditions.inflation` carries `average_pct`, `peak_pct`,
`peak_quarter`. On the asset side, the **only** field in the entire WorldSpec
that expresses inflation linkage is:

```
structural.infrastructure.inflation_linkage   # "Share of revenues contractually inflation-linked", 0..1
```

Infrastructure is not in `ASSETS`. The field is reachable by the compiler and
the validator's sleeve list and is consumed by no engine. The one place the
contract knows how to say "this asset class passes inflation through" is
attached to the one private class that is not simulated.

### 4.2 Where inflation enters the toy engine

Exactly three channels, all keyed on the world's declared **average**, none on
the simulated path:

1. **Policy-rate shock size** — `shock = 0.22 * (1 + 0.10 * max(0, infl_avg − 2.0))`. Below 2% inflation this term is identically zero.
2. **Equity–bond correlation sign** — `corr_eb = 0.35 if infl_avg > 3.5 else −0.30`. A step function, and it enters only the bond innovation.
3. **Commodity drift** — `com_drift/12 + max(0, infl_avg − 2.5)/12`.

The simulated inflation *path* (`EnginePaths.inflation`) is generated, carried
on the digest, and read only by display surfaces — `cioview.py`, `console.py`,
`feed.py`. **No return equation reads it.** Nor does `ah/play.py`, nor any
`ah/port/` module.

### 4.3 Measured: annualized return by declared inflation

Stagflation preset, 200 paths, `base_seed=12345`, one field varied
(`factor_conditions.inflation.average_pct`), everything else held:

| infl % | equity | bonds | hy | commodities | reits | **pe** | **pc** | **re** |
|---|---|---|---|---|---|---|---|---|
| 1.0 | −0.997 | 5.314 | 9.352 | 11.322 | −1.051 | **−1.772** | **7.369** | **1.839** |
| 2.0 | −0.997 | 5.314 | 9.352 | 11.322 | −1.051 | **−1.772** | **7.369** | **1.839** |
| 3.4 | −0.997 | 5.288 | 9.356 | 12.319 | −1.054 | **−1.772** | **7.372** | **1.829** |
| 3.6 | −0.997 | 5.304 | 9.356 | 12.542 | −1.055 | **−1.772** | **7.372** | **1.827** |
| 6.5 | −0.997 | 5.236 | 9.363 | 15.817 | −1.064 | **−1.772** | **7.378** | **1.798** |
| 12.0 | −0.997 | 5.059 | 9.378 | 22.271 | −1.089 | **−1.772** | **7.391** | **1.722** |

Read the columns:

- **Private equity is bit-identical across a twelvefold change in inflation.** `pe = 1.4*eq + const`, and equity itself carries no inflation term, so the pass-through is not small — it is zero by construction.
- **Private credit gains 0.02pp** over the whole range, via the rate level and the spread-change term. Noise.
- **Real estate *loses* 0.12pp** — the wrong sign for the asset class most often held as an inflation hedge.
- **Commodities is the only asset with material pass-through**, +11pp across the range, and the only one where the mechanism is explicit.

The negative signs on bonds, real estate and REITs are **volatility drag, not
repricing** — worth stating precisely, because the intuitive reading (higher
inflation raises rates, which marks property down) is not what the code does.
The realized rate path is almost unmoved by declared inflation (mean policy
rate 6.342 → 6.358 from 1% to 12%; start-to-end change actually *falls*,
1.774 → 1.741). What rises is the rate-shock magnitude, and each asset's
compounded return falls in proportion to its own `d_rate` coefficient while its
arithmetic mean rises slightly:

| asset | `d_rate` coefficient | Δ compounded | Δ arithmetic | Δ vol |
|---|---|---|---|---|
| bonds | −6.0 | −0.255 | +0.055 | +4.313 |
| re | −4.0 | −0.117 | +0.013 | +1.367 |
| reits | −2.5 | −0.038 | +0.008 | +0.331 |
| pc | 0.0 | +0.022 | +0.015 | +0.006 |
| **pe** | **0.0** | **0.000** | **0.000** | **0.000** |

So inflation reaches real estate only as extra noise on a duration term, and
reaches private equity not at all — zero on the mean, zero on the volatility,
zero on the compounded return.
- **Rows 1.0 and 2.0 are identical in every column** — below the 2% anchor the rate-shock term is inert, so a deflationary world and a target world are the same world to this engine.
- **`peak_pct` changes nothing at all.** Holding the average at 6.5 and moving the declared peak from 7.0 to 20.0 leaves every asset's return unchanged to three decimals. `_inflation_path` reads only `average_pct`; `peak_pct` is consumed solely by the generator's joinery waypoints.

### 4.4 Measured: the institution

`simulate_play` on the same tape, no player decisions, `seed=12345`, summed
over the decade:

| infl % | calls | distributions | spending | final NAV | forced-sale quarters |
|---|---|---|---|---|---|
| 1.0 | 45.478 | 46.325 | 38.444 | 72.058 | 28 |
| 2.0 | 45.478 | 46.325 | 38.444 | 72.058 | 28 |
| 6.5 | 46.487 | 46.344 | 39.156 | 76.012 | 28 |
| 12.0 | 48.292 | 46.390 | 40.417 | 84.677 | 28 |

Final NAV rises 17% from the coldest world to the hottest, which looks like
inflation sensitivity. It is not. Move the five points of commodities into
equity and re-run:

| infl % | private NAV (with commodities) | private NAV (commodities → equity) |
|---|---|---|
| 1.0 | 34.982 | 31.066 |
| 6.5 | 36.016 | 30.953 |
| 12.0 | 37.917 | **30.702** |

**Without the commodity sleeve, the private book gets smaller as inflation
rises.** The entire positive inflation response of the private programme is an
indirect effect of a liquid sleeve sitting next to it in the same portfolio,
transmitted through total NAV → reported private weight → the pacing multiplier
→ commitments → calls. Nothing in the private model itself responds.

Distributions are near-flat across all four worlds (46.33 → 46.39) because the
tier-1 linkage reads only equity drawdown and credit spread, and neither moves
with declared inflation on this preset.

---

## 5. What is declared but not consumed

Fields that exist in `schemas/`, are carried in presets, and reach no engine:

| Field | Where it is declared | Status |
|---|---|---|
| `structural.private_equity.leverage_turns` | schema + 4 presets | unread; the 1.4× beta is a constant |
| `structural.private_credit.recovery_rate_pct` | schema | unread |
| `structural.private_credit.spread_over_base_bps` | schema | unread; +4.5% is hardcoded |
| `structural.real_estate.income_yield_pct` | schema | unread; 4.5% is hardcoded |
| `structural.infrastructure.*` (both fields) | schema, validator sleeve list | unread; no infra asset exists |
| `structural.smoothing.weights_on_truth.infrastructure` | schema | unread; no infra asset exists |
| `factor_conditions.inflation.peak_pct` | schema + every preset | unread by `toy-v0`; generator joinery only |

This is not a defect list — `schemas/` is vendored read-only truth and is
allowed to describe more than any one engine implements. It is a map of where
a world author's intent currently stops at the contract boundary. A player or
an author who sets `income_yield_pct: 8.0` and `leverage_turns: 7.0` will see
no change in any number.

---

## 6. What this means, and what it does not

**It does not invalidate anything.** Every mechanism above is faithful to its
plan, and several of them (ER-1, ER-6, ER-7, ER-10, ER-12) are close-outs of
defects that were found and fixed. The cashflow layer in particular is
detailed, honest about its own choices, and the part of the system most worth
trusting.

**It does mean the platform cannot currently answer an inflation question about
private markets.** The stagflation preset is one of the four shipped worlds and
the one the validation battery runs on. A player allocating in it, or a reader
of a stagflation chronicle, will see a private book that is — measurably —
indifferent to the defining feature of that world. Real allocators hold
infrastructure and real estate *specifically* for inflation linkage; here that
linkage is absent in the returns, absent in the cashflows, absent in the
distribution response, and inverted in sign for property.

**Spending is nominal too.** The institution spends 4.5% of nominal reported
value with no CPI indexation, so a stagflation world silently erodes real
spending power rather than forcing the liquidity squeeze a real
inflation-indexed payout would. Note that `ah/port/twin.py` — the *pension*
twin, off the play path — does index: `inflation_linked_share` defaults to 0.7
and `inflation_shock()` moves liability PV with an
`inflation_hedge_ratio` offset. The machinery exists; the played institution
does not use it.

**Recommended, and explicitly the owner's call:** this is register-shaped —
faithful to plan, not faithful to an allocator's expectations — and belongs in
`docs/engine-realism-register.md` as **ER-14**, not in a side document. It is
not filed here because CLAUDE.md makes register entries a release event and the
owner's decision, and because a fix would move every private return in every
world: new `TOY_ENGINE_VERSION`, a new play-alpha stamp, both committed bundles
rebuilt, and the battery re-run. The `structural.infrastructure.inflation_linkage`
field is the natural hook if it is ever taken up — the contract already knows
how to express the thing.

---

## 7. Reproducing the numbers

Every figure above comes from three short probes against committed presets and
artifacts; no fixtures, no network. From the repo root:

```python
# §4.3 — return by declared inflation
import copy, json, numpy as np
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.engine import run_ensemble, ASSETS

base = json.load(open("src/ah/presets/stagflation.json", encoding="utf-8"))
for infl in (1.0, 2.0, 6.5, 12.0):
    d = copy.deepcopy(base)
    d["factor_conditions"]["inflation"]["average_pct"] = infl
    ens = run_ensemble(project_numeric(load_worldspec(d)), 200, base_seed=12345)
    for a in ASSETS:
        r = ens.returns[a] / 100.0
        print(infl, a, (np.prod(1 + r, axis=1).mean() ** (12 / r.shape[1]) - 1) * 100)

# §4.4 — the institution, and the commodity attribution
from ah.core.engine import run_path
from ah.play import simulate_play, PRIVATE_ASSETS, START_TARGETS

targets = dict(START_TARGETS)                 # drop the commodity sleeve
targets["equity"] += targets["commodities"]; targets["commodities"] = 0.0
for infl in (1.0, 6.5, 12.0):
    d = copy.deepcopy(base)
    d["factor_conditions"]["inflation"]["average_pct"] = infl
    tape = run_path(project_numeric(load_worldspec(d)), 12345)
    for label, tg in (("with", None), ("without", targets)):
        res = simulate_play(tape, {}, start_targets=tg)
        last = res.quarters[-1]
        print(infl, label, sum(last.private_true[a] for a in PRIVATE_ASSETS))
```

Reading, rather than running: `ah/core/engine.py:405-448` (the return block),
`:288-296` (`_inflation_path`), `:451-485` (`_reported_marks`);
`ah/port/cohort.py:163-227` (the recursion); `ah/port/cashflow_tier1.py:48-66`
(the linkage); `ah/port/engine.py:86-183` (the waterfall);
`ah/play.py:594-677` (the quarterly loop);
`mappings/cashflow-tier1-v1.0.yaml` and `mappings/sleeve-mappings-v1.0.yaml`
(the frozen parameters).

---

## Related

- `docs/engine-realism-register.md` — ER-1, ER-3, ER-6, ER-7, ER-10, ER-11, ER-12 all touch this surface directly. ER-3's "what is still open" note is the closest existing statement of the boundary described here.
- `Instructions/DN1.1-multiyear-generator-design-note.md`, DN-5 §3.3 — the PM growth-loading priors that `sleeve-mappings-v1.0.yaml` superseded.
- `G1-EVIDENCE.md` — the Step 3 completion gate, an honest FAIL, with tier 1 beaten by tier 0 on the 2022 episode.
