# Does private equity ride through the stress worlds too serenely? — finding

**Date:** 2026-08-19 · **Branch:** `pe-serenity-01` (from `main` `c54c373`)
**Probe:** `scripts/pe_serenity_probe.py` (read-only; `data/ah.db` opened `mode=ro`)
**Trigger:** The Gulf Decade (world `…712`, severe `all_down`, equity **-45.5%** in
year 5) compounds PE true to **+532%** over the decade.

---

## Verdict — MIXED, with one confirmed structural defect and one worse one beside it

**Confirmed, and it is a structural property of the sealed mapping, not a seed:**
the generated plane's PE row **cannot fall harder than its average beta**. Its
crisis beta *is* its calm beta, to three decimal places, because the row is a
linear function of the equity factor and nothing else conditions on state. The
suspicion in the brief is correct as stated.

**But that is not the main reason The Gulf Decade prints +532%.** The larger
cause is a term the brief only mentions in passing: the sealed row carries an
**unconditional intercept of 8.06% a year**, paid in every month of every
world including the crash months. Over ten months of a market collapse it hands
PE **exactly +8.06pp** — the same number on every path of every stress world,
because it does not depend on anything. It is the single largest contributor to
the decade, and it is what turns a -39pp beta hit in year 5 into a -30pp
realised year.

**Not confirmed — the part of the suspicion that does not survive measurement:**
"PE is calm in drawdown" is *not* true across seeds. Median PE max drawdown over
200 severe Gulf-Decade paths is **-31.52%** against equity's **-32.11%** — nearly
identical. PE is not systematically smoother than equity here; the fat-tailed
residual (12.25%/yr, Student-t df 5) puts back roughly what beta < 1 takes out.
The serenity is in the *level* PE compounds to, and in the *shape* of its
drawdowns (idiosyncratic, not crisis-driven), not in their size.

**And a gap that is itself a finding:** the repository holds **no empirical
anchor at all** for how real buyout behaved in a crisis. Not one number, in any
document. So the size of the missing convexity cannot be quantified from inside
this repo — only its existence, and its sign.

Verdict in one line: **STRUCTURAL DEFECT on the crash channel (no convexity, by
seal), compounded by an unconditional 8%/yr premium that is paid hardest exactly
when it is least believable; the observed +532% is ~84th percentile luck on top
of both.**

---

## 0. How the number is built — the code, read before it is measured

`ah/serve.py::_resolve_engine` routes every world whose `generator_id` is not
`toy-v0` to `ah.port.adapter.run_gen_path`; `ah/bundle.py::build_bundle` takes
the identical branch for the `revealed` tape the browser is sent. All three
stress worlds are `bootstrap-stratified`. So the PE tape a player sees is built
by `adapter._pm_true_monthly_path` (`src/ah/port/adapter.py:252-327`), and by
nothing else.

For PE (`pm_buyout`) that function computes, per month, in decimal, then ×100:

```
r_pe(t) =   alpha_quarterly / 3                                  # a constant
          + 0.8362 · equity_mkt(t)                               # the equity beta
          - 0.0279 · d_ig(t)                                     # IG spread CHANGE
          - 0.35   · (cpi_trail_excess(t)/12)/100                # C1, ER-14 close-out
          + eps(t) · 0.1225/sqrt(12)                             # t(5), rescaled
```

Two properties are visible without running anything:

1. **It is affine in the factors.** There is no `max(·,0)`, no squared term, no
   regime label, no interaction. A linear map has one beta. It has the same beta
   in a boom and in a collapse *by construction*.
2. **`_pm_true_monthly_path(ensemble, rows, series, seed)` never receives the
   WorldSpec.** So no world-declared structural field can reach PE's returns
   even in principle — the same argument the `pe-drift-01` finding made for
   `entry_multiple_drift_annual_pct`, and it generalises.

That second point has a sharper consequence than the drift case. World 712's
`structural.private_equity` block declares:

```json
{"entry_multiple_drift_annual_pct": -2.0,
 "illiquidity_premium_annual_pct": 2.0,
 "leverage_turns": 5.5}
```

and `schemas/worldspec-v1.2.schema.json:508-513` describes `leverage_turns` as

> "Net debt / EBITDA at entry; **scales the equity-factor beta in the mapping**."

**Measured** (probe §F, all three worlds): varying `leverage_turns` across its
full schema range 2.0 / 5.5 / 8.0 moves the PE tape by `max |Δ| = 0.0` percentage
points — exactly zero, not small. Same for `illiquidity_premium_annual_pct` over
0.0 / 2.0 / 5.0. A repo-wide grep finds `leverage_turns` in
`src/ah/core/worldspec.py:316` (the pydantic field), nine preset files and three
schema files — **and in no engine, adapter, validator or mapping module at all.**

So the schema promises the exact mechanism whose absence this finding is about —
leverage scaling the equity beta — and nothing implements it, on either plane.

---

## 1. Where The Gulf Decade's +532% comes from

The five terms above are **additive in monthly return space**, so the arithmetic
sum of monthly PE returns decomposes exactly. The probe rebuilds each term
independently and asserts the sum is bit-identical to
`run_gen_path(nw, 202608).returns["pe"]` before reporting anything; that
assertion passes (`atol=1e-12`).

World `…712`, seed `202608`, 120 months. Sum of monthly PE returns = **+200.074pp**:

| term | Σ monthly (pp) | share | compounded alone | decade WITHOUT this term |
|---|---:|---:|---:|---:|
| **alpha** (intercept) | **+77.764** | **38.9%** | **+117.09%** | +192.94% |
| beta × equity_mkt | +73.703 | 36.8% | +88.04% | +233.62% |
| **residual** (this seed's luck) | **+63.330** | **31.7%** | +78.72% | +252.55% |
| beta × d_ig (credit) | +6.278 | 3.1% | +6.43% | +493.56% |
| inflation channel (C1) | -21.000 | -10.5% | -18.96% | +677.43% |
| **total** | **+200.074** | 100% | **+532.15%** | — |

*(The "compounded alone" column does not multiply out to +532.15% — monthly
returns add, annual compounds do not. The Σ column is the exact decomposition;
the compound column is an interpretive aid.)*

Three readings, each with its own arithmetic:

**(a) The intercept alone out-earns the entire equity market.** The sealed
`alpha_quarterly = 0.019441` is applied as `alpha/3` per month. Compounded:
`(1 + 0.019441/3)^12 - 1 = ` **8.06%/yr**, and over 120 months
`(1.00648033)^120 - 1 = ` **+117.09%**. The Gulf Decade's equity market returned
**+107.51%** over the same ten years. A term that is a *constant* beats the
market this world was built to crash.

**(b) The residual carried a third of it, and this seed is lucky.** The residual
draw averaged **+0.528 pp/month** against a zero-mean distribution
(sd 2.94pp realised, t = 1.97 over 120 months). Removing it takes the decade from
+532.15% to +252.55%. Across 200 paths of this same world, +532.15% sits at the
**84th percentile** (median +257.66%, p95 +792.86%). So the trigger tape is a
favourable draw — but the *median* severe path still compounds PE to +257.66%
against equity's +149.91%.

**(c) Strip the two non-factor terms and PE is ordinary.** Median across 200
Gulf-Decade paths:

| | median decade PE |
|---|---:|
| as shipped | **+257.66%** |
| intercept removed | **+65.07%** |
| residual removed | +290.95% |
| both removed (pure factor tape) | **+80.58%** |
| *equity, for reference* | +149.91% |

The level is an intercept story. Remove the intercept and PE in a severe decade
returns +65%, well under the equity market.

### Year 5 — the crash year, exactly

Months 48-59. Sum of monthly PE returns = **-33.176pp**, compounding to
**-30.09%** against equity's **-45.54%**:

| term | Σ monthly (pp), year 5 |
|---|---:|
| beta × equity_mkt | **-47.120** |
| alpha | **+7.776** |
| residual | +8.742 |
| inflation channel | -2.100 |
| beta × d_ig | -0.474 |
| **sum** | **-33.176** |

The beta term alone, compounded over year 5, is **-39.43%** — which is what a
0.8362 beta on a -45.54% equity year should give (and does: 39.43/45.54 = 0.866,
the small excess being monthly compounding). PE's realised **-30.09%** is that
-39.43% plus **+8.06pp of intercept** and **+8.92pp of residual luck**.

Over the whole decade the same shows up in drawdown:

| series | max drawdown | trough |
|---|---:|---|
| equity | **-50.93%** | month 59 |
| PE's beta×equity term alone | -44.28% | month 59 |
| **PE true, as shipped** | **-30.09%** | month 59 |
| PE reported (appraisal plane, what the app shows) | **-12.46%** | month 59 |

**The always-on intercept shaves ~14pp off the crash-year drawdown that PE's own
beta produces, and the appraisal filter shaves another ~18pp off what remains.**
A player watching the default surface sees private equity lose 12.5% in a decade
whose equity market halved.

---

## 2. Crisis beta = calm beta. Measured, not asserted.

### 2.1 The sealed row's own declaration

`mappings/sleeve-mappings-v1.2.yaml`, `pm_sleeves.pm_buyout`, verbatim:

```yaml
family: glm
n_quarters: 125
route: sum-beta(4)
alpha_quarterly: 0.019441
loadings: {equity_mkt: 0.8362, smb: 0.0, hml: 0.0, mom: 0.0,
           d_level: 0.0, d_slope: 0.0, d_ig: -0.0279}
residual_sigma_annual: 0.1225
r2_train_val: 0.269
inflation_passthrough: {b_infl: 0.35, k_quarters: 8, c_anchor: 0.03068}
```

One beta. One intercept. One homoskedastic residual σ. `r2_train_val` of 0.269
means the equity factor explains 27% of quarterly buyout variance and the other
73% is the residual — which, being iid, arrives with equal force in booms and
crashes.

Note also what the artifact *declares missing*
(`structural_omissions`, verbatim): `hy_spread` is a **"sealed missing_factor on
this vintage — DN-5 HY loadings unestimable, NOT zero"**. DN-5's own buyout row
wanted `○− HY (financing cost)` — the financing channel. It is not in the sealed
object, so the generated plane's PE has **no funding-stress channel of any kind**.

### 2.2 Window betas, three worlds × 20 seeds each (60 fits per window)

OLS of monthly PE true on monthly equity true. Declared beta: **0.8362**.

| window | mean β | min | max | sd |
|---|---:|---:|---:|---:|
| full decade | **0.8436** | 0.712 | 0.941 | 0.055 |
| declared crisis quarters | 0.7749 | 0.240 | 1.194 | 0.197 |
| equity in >10% drawdown | 0.8520 | 0.414 | 1.518 | 0.155 |
| equity in >20% drawdown | **0.8843** | 0.542 | 1.054 | 0.112 |
| worst rolling 12m of equity | 0.8936 | 0.461 | 1.420 | 0.179 |
| equity down-months only | 0.8252 | 0.416 | 1.234 | 0.171 |
| equity up-months only | 0.8569 | 0.464 | 1.291 | 0.145 |
| equity worst-decile months | 0.8632 | -0.655 | 1.908 | 0.430 |

Every window mean sits within ±0.06 of the declared 0.8362, and the spread is
sampling noise from the residual (which is *larger* than the signal — see the
0.269 R²). **There is no window in which PE's beta rises.**

### 2.3 The pooled convexity test — the decisive number

Pool every month of 200 paths (**24,000 observations** per world) and fit

```
r_pe = a + b·r_eq + c·r_eq·1{r_eq<0} + d·1{r_eq<0}
```

`c` is the **downside kink**: a real levered portfolio should show `c > 0` (it
falls more than its average beta predicts). A linear construction must give
`c = 0` up to noise.

| world | β (up) | **kink c** | t(c) | implied down-beta |
|---|---:|---:|---:|---:|
| gulf_decade | 0.8187 | **+0.0214** | 1.62 | 0.8402 |
| stress_1974_successor | 0.8154 | **+0.0411** | 2.69 | 0.8565 |
| stress_1990_successor | 0.8194 | **+0.0398** | 2.85 | 0.8592 |

A small but statistically real kink — so the honest answer is "almost zero, not
exactly zero". **Where does it come from?** Re-fit the same regression on the PE
tape with the credit term `-0.0279·d_ig` subtracted out (the only other channel
that co-moves with equity down-months, since IG spreads widen when equities
fall):

| world | β (up) | **kink c, credit term removed** | t(c) |
|---|---:|---:|---:|
| gulf_decade | 0.8475 | **-0.0233** | -1.77 |
| stress_1974_successor | 0.8385 | **-0.0007** | -0.05 |
| stress_1990_successor | 0.8501 | **-0.0196** | -1.41 |

The kink collapses to zero and the up-beta lands on the declared 0.8362.
**Every scrap of crisis convexity the generated plane's PE has comes from a
-0.0279 loading on the IG spread change, and it is worth about 0.04 of beta** —
i.e. in a -20% equity month, PE gets an extra **-0.8pp**. That is the model's
entire answer to a credit crisis.

Distributionally, over 200 paths per world, downside beta minus upside beta:

| world | median | mean | p05 | p95 |
|---|---:|---:|---:|---:|
| gulf_decade | **+0.01** | +0.02 | -0.33 | +0.34 |
| stress_1974_successor | +0.02 | +0.04 | -0.32 | +0.41 |
| stress_1990_successor | +0.04 | +0.04 | -0.32 | +0.38 |

Centred on zero, symmetric. Confirmed: **no crisis convexity.**

### 2.4 One structural note that cuts the other way

`0.8362` is a **Dimson sum-beta over 4 quarterly lags** (`route: sum-beta(4)`;
per-lag values `[0.144, 0.103, 0.089, 0.125]` on top of a contemporaneous
≈0.375, `MAPPINGS-v1.1.md:9`). The estimate says: *over five quarters*, buyout
cumulatively absorbs 0.836 of an equity move; only ~0.375 lands in the same
quarter.

The adapter applies the whole sum **contemporaneously, at monthly frequency**
(`adapter.py:292-295`; the module docstring states the choice — "applied at
MONTHLY frequency"). So the generated plane's PE actually responds to a crash
*faster* than the fit implies, not slower. PE's serenity is therefore **not** a
lagged-transmission artefact — it is beta magnitude plus the intercept. This is
worth stating because it is the obvious alternative explanation and it is wrong.

---

## 3. The historical anchor — what the repo can and cannot support

### 3.1 What the row was fitted on

- **Series:** Albourne PriMaRS index `547791`, *"AW Buy-Outs/Growth Index (USD)"*
  (`src/ah/data/connectors/albourne_primars.py:68`) — a quarterly, **appraisal /
  NAV-marked** blended buyout+growth index.
- **Window:** `access.train_val(...)` only, i.e. `1989Q4 … 2020Q4` = **exactly
  125 quarters**, matching `n_quarters: 125` (`src/ah/splits.py:36-38`;
  cross-checked in `artifacts/c1/passthrough-rent-crosscheck.json`,
  `"train_val_end": "2020-12-31"`).
- **Crises inside the window:** 1990-91 ✓, 2000-02 ✓, 2008-09 ✓, 2020 ✓.
  **1974 ✗** (series begins 1989Q4). **2021-23 ✗** (holdout).

So the crises *are in the sample*. **Nothing in the estimator conditions on
them.** Reading the fit function (`scripts/estimate_sleeve_mappings_v1_1.py:68-115`,
reproduced verbatim in `_v1_2.py:193-223`) it contains: 7 contemporaneous
regressors, 4 Dimson lags on equity only, sign constraints, ridge shrinkage
toward DN-5 priors, one intercept, one homoskedastic σ. It contains **no** regime
split, **no** crisis dummy, **no** downside/upside split, **no** convexity or
quadratic term, **no** interaction, **no** rolling beta, **no** leverage scaling,
and **no** HY/financing loading.

This is not an oversight. `Instructions/DN5-factor-sleeve-mapping.md:200`,
verbatim:

> | **SM-5** | State-dependent (asymmetric) betas in v0 | **Out** of v0; in scope for WP3.2 with its own gate. See §7 | **Seal** | Post-Phase-A (own gate) |

and DN-5 §7:161, verbatim:

> **The generator is scored on tail fidelity in sleeve space, using a mapping that cannot produce tails.**

The design document said this in advance. This finding measures the consequence
on shipped stress worlds.

### 3.2 Why the beta came out below its own prior

DN-5's buyout row expects `○+ MKT ~1.1–1.3`, annotated *"Levered beta"*
(`DN5:92`). The measured 0.8362 sits below it. The estimation script records the
refusal to close the gap (`estimate_sleeve_mappings_v1_2.py:31-34`, verbatim):

> F5b: v1.1's PM betas sit short of the DN-5 priors (pm_buyout's 0.8362 against
> 1.1-1.3). Adjusting a MEASURED beta toward a prior is exactly the tuning the
> seal exists to prevent, so nothing moves here.

That refusal is correct discipline. But the repo also records *why* the measured
value is probably too low — `MAPPINGS.md:56-62`, verbatim:

> That ordering is the signature of RESIDUAL SMOOTHING surviving the de-smoothing
> operator, not of private equity genuinely having a third of the market beta its
> economics imply. It is corroborated by the smoothing kernel fitted alongside:
> the Geltner phi for the appraisal sleeves is only 0.18 over the full sample,
> while the stress-state refit puts it at 0.47 — the full-sample operator is weak
> precisely because the smoothing is state-dependent and the calm majority
> dominates the fit.

And the de-smoothing barely moves buyout at all
(`docs/data/DESMOOTHING-VALIDATION.md:23`): quarterly σ **5.87% → 6.78%**
(ratio **1.155**), ACF1 **+0.216 → +0.027**. A 15% volatility uplift on an
appraisal-marked index.

The circularity is worth naming plainly: **the beta is low because the index is
smoothed; the de-smoother is weak because it was fitted unconditionally on a
sample the calm quarters dominate; and the sealed stickiness parameter that
would have corrected for exactly this excludes buyout.** The sealed kernel
carries `stickiness: 0.4508` — *"marks become roughly twice as sticky when
markets fall"* (`docs/notes/desmoothing-coefficient.md:51-65`; calm `a` 0.9643,
stress `a` 0.5296) — but `n_sleeves_pooled: 2`, and those two are `pm_infra` and
`pm_re_value_add`. `scripts/estimate_smoothing_kernel.py:194` writes the PM
quarterly sleeves under the comment *"excluded from the stickiness pool"*.
Buyout is not in the one crisis-conditional private-markets estimate this repo
owns.

### 3.3 What the repo holds as a real crisis-PE number: **nothing**

Searched `docs/`, `Instructions/`, `governance/`, root `*.md`, `artifacts/**/*.json`.
There is **no statement anywhere** of the form "buyout fell X% in 2008" — no
peak-to-trough figure for any PE index, no de-smoothed PE crisis volatility, no
reported-PE drawdown from any vendor or paper. No Cambridge Associates, Burgiss,
Preqin, PitchBook or State Street PE data is registered or held (they appear only
as unfulfilled alternatives in `docs/data-requirements-register.md:37`). No PE
return series is tracked in git at all (`/data/` is gitignored; `git ls-files data`
is empty).

**That absence is a finding in its own right.** The magnitude of the missing
convexity cannot be established from inside this repository. Only its sign can.

Four adjacent numbers the repo *does* hold, offered as the honest best available:

1. **Secondary-market pricing as % of NAV** (`docs/data/secondaries.md:8-16`) —
   GFC: 2008-H2 **0.70**, 2009-H1 **0.60**, 2009-H2 0.75; COVID 2020-H1 0.85;
   2022-23 rates 2022-H2 0.81. Carrying its own caveat at `:5-6`: *"Values are
   illustrative episode anchors; replace with the exact figures from the cited
   reports when finalizing Gate G1 evidence."* Read carefully, a 0.60 clearing
   price is a **40% discount to a carrying value that had itself already been
   marked down** — i.e. the market's view of true buyout NAV in 2009-H1 was far
   below both the reported mark and anything a 0.84 beta produces.
2. **The buyout index's own outlier record** (`docs/data/DATA-REVIEW-2026-08-08.md:72`):
   across 146 quarters the only |z| ≥ 6 observations are **two positive quarters,
   1990-07 (+31.9%) and 1991-10 (+29.6%)**. Neither 2008-09 nor 2020 registers as
   an outlier at all — while `hf_distressed` shows 2020-03 at z = -12.7 and
   2008-10 at z = -7.3, and `pm_re_va` shows 2008-10 at z = -6.7. **The buyout
   index the mapping was fitted on does not contain a visible GFC.** Any
   downside-beta estimated from it will inherit that.
3. **The repo's own sharpest "privates don't fall enough" number**
   (`docs/data/CAMPAIGN-R1-TRANSLATION.md:83-84`): over 146 quarters of observed
   factor history, the fitted mapping produces a `pm_buyout` max drawdown of
   **-9.88% measured** against **-53.15% under the DN-5 prior**. Summarised in
   `CHANGELOG.md:2390`. That is a property of the mapping, not an observation —
   but it is the same defect this finding measures, recorded a campaign earlier
   and never carried into the register.
4. **The one GFC acceptance test that exists** is
   `scripts/fit_credit_loss_theta.py:41`, `GFC_WINDOW = ("2008-01-01", "2010-12-31")` —
   for private **credit**, and blocked on an undelivered Cliffwater CDLI export
   (`sleeve-mappings-v1.2.yaml`: `c2_status: "deferred: awaiting Cliffwater CDLI
   export"`). It has never run.

**Conclusion for §3:** the repository can prove the mapping has no crisis
convexity and can explain why (smoothed index, unconditional de-smoother,
buyout excluded from the stickiness pool, SM-5 sealed out of scope). It **cannot
say by how much PE should have fallen**, because it holds no such number.

---

## 4. The reported plane — the appraisal filter makes it worse

The shipped reported plane is `ah/core/engine.py::_reported_marks`, not the
sealed per-sleeve kernel (**ER-11**, closed by decision). It is a Geltner partial
adjustment on the quarter's compounded true return, `rep_q = w·q_true +
(1-w)·rep_{q-1}`, with `w = 0.35` for PE. All three stress worlds leave
`structural.smoothing` unset, so all three take that default.

Measured on the three live tapes:

| world | PE reported ACF1 (Q) | PE true ACF1 (Q) | reported σ (Q) | true σ (Q) | reported maxDD | true maxDD | equity maxDD |
|---|---:|---:|---:|---:|---:|---:|---:|
| gulf_decade | **0.709** | 0.049 | 4.49% | 8.87% | **-12.46%** | -30.09% | -50.93% |
| stress_1974_successor | **0.647** | 0.103 | 5.03% | 11.36% | **-15.03%** | -41.98% | -45.13% |
| stress_1990_successor | **0.519** | 0.101 | 4.17% | 10.25% | **-15.18%** | -35.69% | -45.19% |

Worst single quarter, PE: true **-21.00 / -18.78 / -20.98%**, reported
**-6.16 / -5.78 / -5.57%**.

Two things to say about this, one exculpatory and one not.

**Exculpatory:** the reported ACF of ~0.52-0.71 is *consistent with what ER-11
already records* — the register cites 0.55 for buyout under the engine filter
(against 0.06 under the sealed kernel). Nothing new is broken here; the filter
behaves as documented. And a `w = 0.35` filter is not obviously wrong as a
statement about appraisal lag.

**Not exculpatory:** the filter is **unconditional**, and DN-5 §5.3 says in
terms that this is the wrong shape, verbatim:

> Marks get stickier when markets fall. Appraisers anchor harder, GPs defer
> write-downs, and the gap between reported and true widens precisely in the
> drawdown. **A constant kernel understates the denominator effect**

So the two failures compose in the same direction. The true plane cannot fall
more than beta; then a constant-`w` filter takes a further ~60% off what does
fall. The surface a player actually looks at shows **private equity down 12.5%
in a decade whose equity market fell 50.9%**, against a repo-cited GFC anchor of
secondaries clearing at **0.60 of NAV**. Whatever the right number is, -12.5%
reported is not in its neighbourhood.

Note this is *not* the "reported plane is calm" complaint being new — it is that
in a **stress** world the two effects multiply, and no evidence in the repo
covers that composition.

---

## 5. Is +532% an outlier seed, or the model's ordinary output?

200 paths per world at the platform stride `base_seed + 7919·k`, so path k=0 is
the live RunRecord's own tape.

**gulf_decade (`…712`, base seed 202608)** — decade PE true, %:

| min | p05 | p25 | median | p75 | p95 | max | mean |
|---:|---:|---:|---:|---:|---:|---:|---:|
| -64.85 | +39.89 | +139.93 | **+257.66** | +450.44 | +792.86 | +1540.54 | +321.97 |

The observed **+532.15%** sits at the **84th percentile** of its own world's
distribution. Lucky, but well inside. Equity over the same 200 paths: median
**+149.91%**.

| world | median PE | median equity | paths where PE decade beats equity decade | paths with NEGATIVE decade PE |
|---|---:|---:|---:|---:|
| gulf_decade | +257.66% | +149.91% | **169 / 200** | 4 / 200 |
| stress_1974_successor | +337.13% | +183.24% | **169 / 200** | 2 / 200 |
| stress_1990_successor | +203.29% | +82.21% | **180 / 200** | 11 / 200 |

**In a world dialled to worst-decile severity, private equity loses money over
the decade on 1-5.5% of paths and beats the stock market on 85-90% of them.**
That is the finding in one row, and it is not seed luck — it is the median.

### The crash-year cushion is a constant

Inside each path's **worst rolling 12-month equity window** (median across 200
paths per world):

| world | equity | PE true | PE's beta×equity term alone | **alpha term** | residual term |
|---|---:|---:|---:|---:|---:|
| gulf_decade | -26.22% | **-19.00%** | -22.25% | **+8.06%** | -0.91% |
| stress_1974_successor | -20.87% | -17.20% | -17.48% | **+8.06%** | -2.97% |
| stress_1990_successor | -28.35% | **-22.16%** | -23.99% | **+8.06%** | +0.95% |

The alpha column's p05 and p95 are **+8.06 and +8.06** — identical to the median,
on every path of every world. It is a constant, by construction. **Private equity
is paid 8.06% during the worst twelve months of a severe decade, whether equity
fell 8% or 55%.** That is the single most decisive number in this document.

### The drawdown counter-evidence, stated fairly

Across 200 paths, max drawdown:

| world | median PE maxDD | median equity maxDD |
|---|---:|---:|
| gulf_decade | **-31.52%** | -32.11% |
| stress_1974_successor | -27.73% | -29.85% |
| stress_1990_successor | -33.41% | -36.16% |

PE's *typical* drawdown is close to equity's. So "PE rides through serenely" is
not universally true and should not be claimed. What is true is that PE's
drawdowns are the wrong **shape**: with R² of 0.269, most of PE's drawdown is
its own iid residual, arriving at random times, not the world's crisis. The
Gulf Decade tape happens to be one where the residual was kind during the crash
(+8.9pp in year 5), which is why *that* tape reads as serene.

---

## 6. Proposed engine-realism register entry (ER-16 candidate — DRAFT, not applied)

> The register has not been edited. This is a proposal for the owner to accept,
> amend or decline. It is drafted in the register's own format (`## ER-N — …`,
> Status / Found / What happens / evidence tables / What a fix looks like /
> Consequences).

```markdown
## ER-16 — Private equity cannot fall harder than its average beta, and is paid an 8%/yr premium while it falls

**Status:** open (structural; a fix touches the sealed mapping artifact)
**Found:** 2026-08-19, `pe-serenity-01`, investigating why The Gulf Decade
(world 712, severe `all_down`, equity -45.5% in year 5) compounds PE true to
+532% over the decade. Probe: `scripts/pe_serenity_probe.py`.

**Scope note.** This is about the GENERATED plane's private-market return
process — `ah/port/adapter.py::_pm_true_monthly_path` reading
`mappings/sleeve-mappings-v1.2.yaml` — not the `toy-v0` engine. No
`TOY_ENGINE_VERSION` change; the affected stamp is `GEN_PLAY_ALPHA_VERSION`.
The toy plane has its own version of the first half (`pe = 1.4*eq + …`, a
constant 1.4) and, unlike `re` and `pc`, carries no crisis term for PE at all.

**What happens.** The generated plane builds PE as an affine function of the
factor path:

```
r_pe(t) = alpha_q/3 + 0.8362·equity_mkt(t) - 0.0279·d_ig(t)
          - 0.35·(cpi_trail_excess(t)/12)/100 + eps(t)·0.1225/sqrt(12)
```

There is no `max(·,0)`, no regime term, no interaction, no leverage scaling. A
linear map has one beta, so **the crisis beta is the calm beta**. Pooled over
24,000 monthly observations per world, fitting
`r_pe = a + b·r_eq + c·r_eq·1{r_eq<0} + d·1{r_eq<0}`:

| world | β (up) | kink c | t(c) | c with the credit term removed |
|---|---:|---:|---:|---:|
| gulf_decade | 0.8187 | +0.0214 | 1.62 | **-0.0233** |
| stress_1974_successor | 0.8154 | +0.0411 | 2.69 | **-0.0007** |
| stress_1990_successor | 0.8194 | +0.0398 | 2.85 | **-0.0196** |

The entire measured downside kink is the -0.0279 loading on the IG spread
CHANGE; removing it leaves zero. **The model's whole answer to a credit crisis
is about -0.8pp of PE return in a -20% equity month.** `hy_spread` — DN-5's
financing channel for buyout — is a declared `structural_omission` in the sealed
artifact, so there is no funding-stress channel of any kind.

**A second term, layered on it, and the larger contributor.** The sealed row's
intercept `alpha_quarterly = 0.019441` is applied as `alpha/3` every month:
`(1+0.019441/3)^12 - 1 =` **8.06%/yr**, state-independent. Measured inside each
path's WORST rolling 12-month equity window, 200 paths × 3 worlds, the alpha
term contributes **+8.06%** at the median, at p05 AND at p95 — a constant,
paid at full rate through a collapse.

| world (median of 200 paths) | equity, worst 12m | PE true | PE's beta×equity alone | alpha term |
|---|---:|---:|---:|---:|
| gulf_decade | -26.22% | -19.00% | -22.25% | **+8.06%** |
| stress_1974_successor | -20.87% | -17.20% | -17.48% | **+8.06%** |
| stress_1990_successor | -28.35% | -22.16% | -23.99% | **+8.06%** |

**Magnitude on the shipped worlds.** In a world dialled to worst-decile
severity, over 200 paths each: PE's decade return beats the equity market on
**169/200, 169/200 and 180/200** paths, and is negative on only **4, 2 and 11**.
On The Gulf Decade's own live tape (seed 202608) the exact term decomposition of
the +532.15% decade is: intercept **+77.76pp** (38.9% of the arithmetic sum),
beta×equity +73.70pp, residual +63.33pp, credit +6.28pp, inflation -21.00pp.
**The intercept alone compounds to +117.09% over the decade, against the equity
market's +107.51%.** Year 5, the crash year: beta×equity -47.12pp, intercept
**+7.78pp**, residual +8.74pp — a realised -30.09% where the beta term alone
gives -39.43% and equity gives -45.54%.

**A third field the schema promises and nothing implements.**
`schemas/worldspec-v1.2.schema.json:508-513` describes
`structural.private_equity.leverage_turns` as *"Net debt / EBITDA at entry;
scales the equity-factor beta in the mapping."* All nine presets set it to 5.5.
Measured: varying it across its full schema range (2.0/5.5/8.0) moves the
generated PE tape by **exactly 0.0pp**, and a repo-wide grep finds no consumer
outside `worldspec.py`'s field declaration. Same for
`illiquidity_premium_annual_pct`. (The toy plane reads the illiquidity premium
but applies a hard-coded 1.4 beta, so leverage is inert there too.)

**Why this is not a defect against the plan.** DN-5 sealed it out in advance —
SM-5, *"State-dependent (asymmetric) betas in v0: **Out** of v0; in scope for
WP3.2 with its own gate"* — and DN-5 §7 states the consequence directly: *"The
generator is scored on tail fidelity in sleeve space, using a mapping that
cannot produce tails."* This entry records what that costs on shipped stress
worlds, which no document previously did.

**Why the beta is probably too low as well as too flat.** The row was fitted on
the Albourne AW Buy-Outs/Growth index (`547791`), 1989Q4-2020Q4, appraisal-marked.
De-smoothing lifts its quarterly σ only 5.87% → 6.78% (ratio 1.155). The index's
only |z|≥6 quarters across 146 observations are two POSITIVE quarters in 1990-91;
2008-09 and 2020 do not register as outliers at all, while `hf_distressed` shows
2020-03 at z=-12.7. The one crisis-conditional smoothing estimate the repo owns
(`stickiness: 0.4508`, marks ~2× stickier in stress) has `n_sleeves_pooled: 2`
and **buyout is not one of them**. `MAPPINGS.md:56-62` already diagnosed the
mechanism: *"the signature of RESIDUAL SMOOTHING surviving the de-smoothing
operator ... the full-sample operator is weak precisely because the smoothing is
state-dependent and the calm majority dominates the fit."*

**The anchor gap, stated plainly.** The repository holds **no** empirical value
for a real buyout crisis drawdown — no index peak-to-trough, no de-smoothed
crisis vol, no vendor figure, in any document. The nearest repo-cited anchor is
secondary-market pricing at **0.60 of NAV in 2009-H1**
(`docs/data/secondaries.md`, itself flagged "illustrative"). So the SIGN of this
defect is established and its MAGNITUDE cannot be, from inside this repo. Any
fix therefore needs new data or an explicitly-chosen (not measured) parameter.

**Composition with the reported plane.** The shipped appraisal filter (ER-11,
`w = 0.35`, unconditional) takes a further ~60% off what does fall: PE reported
max drawdown is **-12.46%** on The Gulf Decade against -30.09% true and -50.93%
equity, with a worst reported quarter of -6.16% against -21.00% true. DN-5 §5.3
says the constant kernel is the wrong shape in exactly this state — *"Marks get
stickier when markets fall ... A constant kernel understates the denominator
effect"* — so the two effects run the same way. **A player on the default
surface watches private equity lose 12.5% in a decade whose stock market halved.**

**What a fix looks like.** Three routes, in increasing cost:

1. *Downside-beta term in the sealed mapping* (DN-5 SM-5's own route, already
   scoped to WP3.2 "with its own gate"): refit `pm_buyout` with an asymmetric
   equity loading on the same 125 quarters. The data supports the fit
   mechanically — 1990-91, 2000-02, 2008-09 and 2020 are all inside the window —
   but see the outlier record above: the appraisal index may not contain enough
   visible crash to identify a downside beta, in which case the fit will honestly
   return "no asymmetry" and the problem moves to the de-smoother.
2. *Extend the sealed stickiness pool to buyout*, so the de-smoother is
   state-dependent for PE as it already is for RE/infra. This attacks the cause
   rather than the symptom (a state-dependent de-smoother would raise the fitted
   crisis beta on its own) but needs its own estimation and amendment.
3. *A stated adapter-level convexity constant*, the way `_HY_EQUITY_BETA = 0.4`
   is a stated choice. Cheapest, and the least defensible: it introduces an
   unestimated parameter onto the scored plane, which is the tuning the seal
   exists to prevent.

Doing nothing is also a position, and a defensible one given the anchor gap —
but then the stress worlds should say so where a player can see it.

**Consequences.** Routes 1 and 2 edit `mappings/sleeve-mappings-v1.2.yaml`,
which is a **sealed artifact inside the pre-registration lock** — an
amendment-log event, not a cleanup, and an owner decision. Then the cascade:
`GEN_PLAY_ALPHA_VERSION` bump (`port-v5-inflation-gen` → v6), every generated
RunRecord's digest invalidated, new `world_id` blocks for 711/712/713 so no
leaderboard row mixes mappings, in-flight sessions demoted, `app/fixtures/*.bundle.gz`
and the generated goldens regenerated, and a battery revalidation (the PM-plane
tail statistics and every `pm_*` drawdown figure in
`docs/data/CAMPAIGN-R1-TRANSLATION.md` move). Route 3 skips the seal but not the
version bump or the rebuilds. **A release event and the owner's call.**
```

---

## 7. Decision options for the owner

**A. Record only — accept ER-16 as `open`, change no code.**
Cost: zero engineering. Consequence: the three severe worlds keep telling a
story in which private equity earns 8%/yr through a market collapse and beats
equities on ~85% of severe paths. Defensible *given* §3.3 — we have no number to
fix it to — but the register entry then has to be read by anyone interpreting a
stress world's PE line.

**B. Record + a display/narration honesty fix (no numeric change).**
Say in the world's own surfaces that PE's crash behaviour is beta-only and its
premium is unconditional. Cheap, no seal, no digest move, no rebuild. Does not
change a single score. This is the smallest thing that stops the surface being
misleading, and it composes with A.

**C. Route 2 — extend the sealed stickiness pool to buyout (attack the cause).**
The most principled option: the repo already believes marks get ~2× stickier in
stress (`stickiness: 0.4508`) and already excludes buyout from that belief for no
stated reason beyond frequency. Fixing the de-smoother would raise the fitted
crisis beta *as a measured consequence*, not a chosen one. Needs: an estimation
run, an amendment against the mapping seal, then the full cascade in §6.

**D. Route 1 — refit `pm_buyout` with an asymmetric equity loading (DN-5 SM-5).**
Already scoped by the design note "with its own gate". Honest risk, stated up
front: the index may not contain enough visible 2008 to identify the asymmetry
(§3.3 item 2), in which case the fit returns "no asymmetry" and the answer is C
anyway. Consider running D as a *measurement* first, before deciding to ship it.

**E. Separate and smaller — decide what `leverage_turns` is for.**
It is in `schemas/`, in nine presets at 5.5, described as scaling the mapping's
equity beta, and read by nothing on either plane. Either wire it (which is
route 3 with a schema-blessed name) or mark it explicitly inert the way the
`pe-drift-01` finding handled `entry_multiple_drift_annual_pct`. This one does
not require touching the seal and can be decided independently of A-D.

**F. Acquire an anchor.**
`docs/data-requirements-register.md:37` already lists Burgiss/Cambridge
composites as the alternative to Albourne. Until something market-priced or
crisis-visible arrives, every option above is calibrated against a smoothed
index and an "illustrative" secondaries table. Worth putting a number on the
value of that data before spending a release on C or D.

**Recommendation, offered not assumed:** A + B + E now (they are cheap, honest,
and require no seal), then D **as a measurement only** to find out whether the
data can support C or D at all. Do not ship a numeric change to a sealed mapping
on the strength of an anchor the repo does not have.

---

## 8. Caveats on this finding's own numbers

1. **Nothing was written to the shared store.** `data/ah.db` was opened
   `mode=ro`; no run was created; no preset, mapping or source file was edited.
   The probe is a pure recomputation from each world's stored spec + seed.
2. **The decomposition is asserted, not asserted-to.** `pe_terms` rebuilds the
   five terms independently of `_pm_true_monthly_path` and the probe raises
   rather than reports if their sum is not bit-identical to
   `run_gen_path(...).returns["pe"]` (`atol = 1e-12`). It passes on all three
   worlds.
3. **"Compounded alone" columns do not multiply out.** Monthly returns add;
   annual compounds do not. Where exactness matters (year 5, the decade total)
   the arithmetic Σ of monthly terms is quoted, and it sums exactly.
4. **200 paths per world, at the platform stride `base_seed + 7919·k`** — so
   path k=0 IS the live RunRecord's tape and the percentile is measured within
   the same world, not across worlds. `run_gen_path` draws one path per seed;
   there is no separate ensemble-member choice.
5. **The pooled convexity t-statistics are heteroskedasticity-naive** and pool
   months across paths, so they overstate precision somewhat. They are used only
   to establish that the kink is small and credit-sourced, which the
   credit-removed refit confirms by construction rather than by inference.
6. **The `-9.88% vs -53.15%` figure in §3.3 is from the v1.0 mapping era**
   (β 0.348), quoted because it is the same defect measured a campaign earlier,
   not as a current value. The current β is 0.8362.
7. **The CWBDC index is private *credit*, listed and levered** — it is the repo's
   de-smoothing validation anchor for direct lending, not a buyout proxy, and is
   deliberately not used here as a PE crisis anchor.
8. **`bootstrap-stratified` ignores `factor_conditions` by seal** (the adapter's
   own module docstring). Every number above is read off realised tapes.
9. **The standing caveat applies.** `hier-flow-v1` and everything built on it
   *"is not a convincing model of history — regime persistence undercalled,
   drawdowns understated ~2×"*. This finding names one specific mechanism by
   which private-market drawdowns are understated on the generated plane. It
   does not make anything decision-ready.
