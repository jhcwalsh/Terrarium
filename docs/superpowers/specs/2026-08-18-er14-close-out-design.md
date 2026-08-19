# ER-14 close-out — mechanism design and coefficient ratification package

*Status: **PROPOSAL, AWAITING OWNER RATIFICATION**. Nothing here is sealed,
implemented, or adopted. Written under `D-ER14-1` (owner ruling, 2026-08-18),
which funds the ER-14 close-out, batches it with F5, and requires this
document — mechanism design plus coefficient proposal — before anything is
sealed.*

**What this document is for.** ER-14 says private markets cannot feel
inflation. Closing it means writing three economic channels into the return
process. Each channel needs a coefficient, and a coefficient is a claim about
the world, so the owner ratifies it rather than an implementer choosing it
inside a commit. This document proposes every coefficient with its anchor, says
what the 1970s should then look like so the proposal can be checked against
intuition, states the acceptance tests that would prove the defect inverted,
and prices the work.

**House rule applied throughout:** every number below is traced to something
already declared in this repository — a sealed artifact, an amendment-logged
declaration, an existing engine constant, or an authored preset — or else it is
derived in the open from those. Where a number is genuinely a judgment with no
repo-internal anchor, it says so.

---

## 0. Executive summary

Three mechanisms, nine new coefficients, one new derived state variable, no new
random number stream, no change to any sealed file's *contents*.

| Class | The channel that helps | The channel that hurts | Net, per pp of inflation excess |
|---|---|---|---|
| Real estate | rent/income escalation, λ_RE = 0.30 | cap-rate repricing, γ_RE = 0.50 on a 4.0-year duration | **+0.30 pp/yr steady-state**, with a transient markdown while inflation is *accelerating* |
| Private equity | nominal earnings pass-through, λ_PE = 0.35 | exit-multiple compression, μ_PE = 0.45 | **−0.10 pp/yr** |
| Private credit | floating coupon, φ_PC = 1.0 on within-world inflation deviation | borrower-coverage squeeze, ω_PC = 0.03, plus the C2 convex spread loss θ_toy = 0.10 | **−0.08 pp/yr** with rates held; **strongly positive** in a coherent hot world where rates are authored high |

Two structural recommendations that go with them:

1. **Do not admit inflation to the tier-1 cashflow linkage** (`f_dist`/`f_call`).
   The cashflow layer becomes inflation-sensitive *derivatively* once returns
   respond, without touching the sealed `mappings/cashflow-tier1-v1.0.yaml` and
   without a Delta-3 decision. §3 gives the argument and names the residual gap
   this leaves open.
2. **Do not put a policy reaction function into `_rate_path`.** It would make
   inflation reach private markets through a *public* channel — precisely the
   second-order effect ER-14 exists to complain about — and it moves every
   asset at once, destroying the attribution. §2.4 explains, and §8 keeps it as
   an explicit declinable ask.

---

## 1. Where the channel stops today — located precisely

Read this before the mechanisms; the design is shaped by exactly where the wall
sits.

**The return process (`src/ah/core/engine.py`, `toy-v0.6`).** The three private
returns are, verbatim from `run_path`:

```
pe = 1.4*eq + (pe_illiq + pe_mult)/12 + 2.0*e_pe
pc = (rate + 4.5)/12 - pc_loss_m - 0.8*d_spread + 0.18*eq + 1.45*e_pc
re = 4.5/12 - re_cap/(100*nm)*2.2 - 4.0*d_rate + 0.35*eq + 1.5*e_re - 1.0*crisis
```

Not one of the three reads `inflation`. The simulated inflation path exists
(`_inflation_path`, line 288), is carried on `EnginePaths`, is on the digest,
and is read only by `cioview.py` / `console.py` / `feed.py`. **The carrier is
already built and already free.** That is the single most useful fact in this
design: no new state has to be invented, plumbed through the digest, or added
to `schemas/`.

**The generated path (`src/ah/port/adapter.py`).** `pe`/`pc`/`re` come from the
sealed PM loadings in `mappings/sleeve-mappings-v1.1.yaml` over the regressor
set `equity_mkt, smb, hml, mom, d_level, d_slope, d_ig`. **There is no
inflation regressor in that list.** The adapter *does* already derive a
trailing-inflation series (`_source_series`, `infl_pct`, a 12-month annualised
CPI change) and passes it to `EnginePaths.inflation` — again, display-only. Same
story: carrier built, unused.

**The cashflow linkage (`src/ah/port/cashflow_tier1.py:48-66`).** This is the
hard wall, and it is a *signature*, not an omission:

```python
def f_dist(dd: float, spread_ratio: float, *, artifact_path=None) -> float:
def f_call(dd: float, *, artifact_path=None) -> float:
```

There is no third parameter. Adding one is an API change to a module whose
docstring states the restriction as structural ("no regime label, no recession
dummy reaches this module's API — Delta 3, structural"), and whose parameters
are frozen in `mappings/cashflow-tier1-v1.0.yaml`, a file inside the G3
pre-registration lock. §3 is the decision about whether to go through that wall.

---

## 2. The mechanism, class by class

### 2.0 The shared state variable

One derived series, computed once in `run_path`, consuming no RNG:

```
K            = 24 months (8 quarters)
infl_trail[m] = mean(inflation[max(0, m-K+1) : m+1])     # annual percent
x[m]          = infl_trail[m] - C_ANCHOR                  # "inflation excess", annual pp
```

**K = 24 months** is C1's declared `cpi_trail_k` — 8 quarters — restated at the
engine's monthly resolution. It is not chosen here; it is inherited from
`AM-2026-08-15-001` and from the design note's reasoning (escalator and
lease-reset cycles pass CPI through over one to three years; 8 quarters is the
midpoint, and the committed CPI rent cross-check found 72% of the long-run
pass-through realised by K = 8). K = 4 and K = 12 are recorded as sensitivities
in the implementation report and **never adopted** — the same rule C1 declares.

**Warm-up:** for `m < K-1` the mean is taken over the months available, not
held at zero. A decade world is 120 months; two years of dead channel would be
a fifth of the game, and a step at month 24 would be a visible artefact. The
consequence, stated: a world that opens hot is hot from month 0, which is
correct — the player inherits a book already priced for the inflation that is
running.

**C_ANCHOR = 2.0%.** Justified three ways, all repo-internal:
- it is already the engine's inflation anchor — `_RATE_SHOCK_INFLATION_ANCHOR = 2.0`
  (`engine.py:87`), the threshold above which the rate-shock term switches on;
- it is `_DEF["infl_avg"] = 2.0`, the value the engine substitutes when a world
  declines to declare one;
- it is the declared average of the `goldilocks` and `prehistory` presets, so
  the two "normal" worlds sit at the anchor by construction and the mechanism
  is near-inert in them.

Demeaning at an anchor is C1's declared discipline and it earns the same thing
here: adoption adds *state-dependence*, not *return*. A world at 2% inflation
gets essentially no new drift; hotter worlds get the term positive, colder ones
negative. `deflation_bust` (declared −1.0%) gets `x = −3.0` and its property
book is penalised — which is right, and §4 shows it as the mechanism's mirror
test.

**Units convention throughout:** engine returns are monthly percent (1.5 means
1.5%). A coefficient applied to `x` (annual pp) is divided by 12. A coefficient
applied to `Δx` follows the existing `d_rate` convention (`np.diff(prepend=first)`,
so the first month's change is zero) and is *not* divided by 12 — the same
convention `−4.0*d_rate` already uses.

### 2.1 Real estate — income escalation against valuation pressure

**The economics.** Property is held for inflation linkage because leases
escalate: rents reset to CPI on contractual schedules, so the income stream
grows with the price level with a lag. Against that, the same inflation lifts
nominal discount rates, and property is a long-duration asset, so cap rates rise
and values are marked down. The first effect is *permanent and cumulative*; the
second is a *repricing* — it happens when inflation changes, not for as long as
inflation is high. Modelling them with the same time signature would be the
single most common way to get this wrong.

**The form:**

```
re += λ_RE * x[m] / 12                        # income escalation (level effect)
re += - D_RE * Δ( γ_RE * x[m] )               # cap-rate repricing (change effect)
```

with `D_RE = 4.0` — **not a new constant**: it is the property rate duration the
engine already applies in `−4.0*d_rate`. Only λ_RE and γ_RE are new.

**λ_RE = 0.30 pp of return per pp of inflation excess.** Anchor: this is C1's
declared `b_infl` for `pm_re_value_add`, entered verbatim in
`governance/amendment-log.yaml` under `AM-2026-08-15-001` (`C1_values:
pm_re_value_add: 0.3`, label `chosen`) and in the decision register's unratified
row. The design note anchors it to contract share — the share of revenue with
contractual CPI linkage, from lease-reset structure — with a declared range of
0.15–0.45 and core infrastructure declared at 0.6 for contrast. **Adopting the
number C1 already declares is deliberate**: the research plane and the product
plane must not carry two different beliefs about the same economic quantity.
See §8 ask A4 for the one place the owner may reasonably prefer a different
value (the product's `re` is a blended institutional property allocation, more
core-weighted than "value-add", which argues for something nearer 0.45).

**γ_RE = 0.50 pp of cap rate per pp of inflation excess.** Anchor: partial
Fisher pass-through. Nominal discount rates move one-for-one with *expected*
inflation in the long run; a *trailing realised* proxy captures only part of the
expectation revision. The repo already owns a measurement of exactly that
attenuation — the committed CPI rent-vs-less-shelter cross-check
(`artifacts/c1/passthrough-rent-crosscheck.json`, hashed, quoted in the C1
design note §3.2): long-run pass-through **0.64**, of which **72% is realised by
K = 8 quarters**. 0.64 × 0.72 = **0.46**, rounded to 0.50. Declared range
0.30–0.70. Label `chosen`. Upgrade path: an NCREIF NPI cap-rate (or
income-return) regression on trailing CPI, from the *same* NCREIF export C1's
NOI-growth fit already needs — one data acquisition upgrades two coefficients.

**The net response, derived rather than asserted.** Because the income term is
proportional to `x` and the repricing term to `Δx`:

- In a world whose inflation is *steady* at 6.5% (x = +4.5), `Δx ≈ 0`, so the
  repricing term contributes nothing and real estate earns
  **+0.30 × 4.5 = +1.35 pp/yr** more than it would at the anchor.
- In a world whose inflation *accelerates* by 4.5pp, the repricing term charges
  `4.0 × 0.50 × 4.5 = −9.0%` **once**, spread over the trailing window as the
  average catches up, then stops.
- Inside a stagflation preset the crisis block lifts the inflation target by
  15% (6.5 → 7.475), so `x` rises about +1.0 across the crisis ramp: a
  **−2.0% markdown while inflation accelerates, reversing to +2.0% as it
  recedes**, on top of the standing +1.35 pp/yr of escalated income.

That is the shape an allocator expects: property gets marked down as inflation
surges, then out-earns everything for the rest of the decade.

**Rider R1 — read `structural.real_estate.income_yield_pct`.** The 4.5% income
yield is hardcoded; the field is declared, in the schema, and dead (ER-14's
unconsumed-field map). It should be read in the same release, because the moment
inflation escalation works, the first thing a world author will reach for is the
income level it escalates. **No shipped preset declares it**, so every preset is
numerically unchanged by R1 — the cheapest honest repair in this package.

### 2.2 Private equity — nominal earnings against multiple compression

**The economics.** Portfolio companies bill in nominal currency: revenue rises
with the price level to the extent they have pricing power, and margins compress
to the extent input and wage costs rise faster. Leverage cuts the other way —
inflation erodes the real value of fixed-rate acquisition debt, which accrues to
the equity. Against all of that, exits are priced on multiples, and multiples
compress as nominal discount rates rise.

**The form** — expressed inside the engine's own existing vocabulary rather than
by bolting on a new duration term:

```
pe = 1.4*eq + ( pe_illiq + pe_mult + (λ_PE - μ_PE) * x[m] ) / 12 + 2.0*e_pe
```

The engine already carries `structural.private_equity.entry_multiple_drift_annual_pct`,
schema-described as "annualized valuation-multiple tailwind (+) or drag (−)", and
reads it. μ_PE simply makes that drift *respond to inflation* instead of being
hand-authored. Two coefficients are declared so the owner ratifies two economic
forces; the net is derived.

**λ_PE = 0.35 pp per pp.** Derived in the open from two repo-declared numbers:
- **Unlevered pass-through 0.25.** ER-14's own "what a fix looks like" paragraph
  says buyout should be "partial (revenue pass-through net of input costs)", and
  C1's contract-share ladder puts contractual linkage at 0.6 (regulated infra)
  and 0.3 (lease resets). Buyout has *no* contractual linkage at all — pricing is
  discretionary and competitive — so it belongs below 0.3. 0.25 is the value
  proposed, declared range 0.15–0.35.
- **× 1.4**, the engine's own declared PE leverage beta (`pe = 1.4*eq`). Leverage
  amplifies nominal earnings growth into equity return, and it is also where the
  real-debt-erosion tailwind lives — folded in here rather than modelled
  separately, because modelling it separately would need a debt stock the engine
  does not carry. **Disclosed as a fold-in, not hidden.**

0.25 × 1.4 = **0.35**. Label `chosen`. Upgrade path: an Albourne buyout
revenue/EBITDA panel keyed to trailing CPI → relabel `measured-external`.

**μ_PE = 0.45 pp of annual multiple drift per pp of inflation excess.** Anchor:
**the repository's own authored presets already state this belief.** All six 6.5%
worlds in `src/ah/presets/` (stagflation, stagflation_1974, stress_1974,
stress_1990, narration_1974, spine_pilot) declare
`entry_multiple_drift_annual_pct: -2.0`, and 6.5% is 4.5pp above the anchor. 2.0 ÷ 4.5 = **0.444**, rounded to 0.45. The
world author, writing by hand, priced inflation-driven multiple compression at
exactly this rate. Making it endogenous means the author no longer has to
hand-author it — and means a world *not* written by that author gets it too.
Declared range 0.30–0.60. Label `chosen`.

**A double-count that must be resolved, not glossed.** Those presets *already*
carry the −2.0. If μ_PE is adopted while the field keeps its authored value, the
compression is charged twice. Recommendation: **re-author the affected presets'
`entry_multiple_drift_annual_pct` to 0.0** in the same release, leaving the field
to mean *non-inflation* multiple drift (secular dry-powder effects, sector
re-rating). The presets move to a fresh `world_id` block anyway, so no
leaderboard row can be confused by the change. This is ask A5 in §8.

**Net PE = λ_PE − μ_PE = −0.10 pp/yr per pp of excess.** A 12% world's private
equity runs about **1.1 pp/yr below** a 1% world's.

**The fragility, stated out loud.** −0.10 is a small difference between two
larger declared numbers. If the owner ratifies λ_PE at its top (0.49 levered)
and μ_PE at its bottom (0.30), the net is +0.19 and the *sign flips*. Two
consequences follow, and both are deliberate:
- the acceptance test for PE is a **materiality** test, not a sign test — which
  is exactly what `D-ER14-1` asks for ("PE must differ materially"), and it
  reserves the sign test for real estate, where the economics are unambiguous;
- §8 asks the owner to ratify a **floor on |net|**, not just the two components,
  so that no combination of in-range choices can quietly re-create ER-14 in
  weaker form.

### 2.3 Private credit — floating coupon against the loss cycle

**A finding that changes the design, and that the owner should see first.**
ER-14's probe varied `factor_conditions.inflation.average_pct` while holding
everything else — correctly, to isolate the asset-side channel. But the
WorldSpec's policy rate is *authored*, not generated by a reaction function, and
across the shipped presets the authors already couple the two:

| preset | declared inflation | authored policy rate |
|---|---|---|
| goldilocks | 2.0% | 3.0 → 3.0 |
| reflation_boom | 3.5% | 1.0 → 4.0 |
| stagflation | 6.5% | 5.5 → 7.5 |
| stagflation_1974 | 6.5% | 6.0 → 8.0 |
| deflation_bust | −1.0% | 4.0 → 1.0 |

Private credit's coupon is `(rate + 4.5)/12`. So across the worlds a player
actually plays, **private credit's floating benefit is already there and already
large** — roughly +3.5 pp/yr of extra coupon in stagflation versus goldilocks,
by authorship. What ER-14's probe measured is that the *model* does not enforce
the coupling: an author may declare 12% inflation with 1% rates and nothing
objects. So the private-credit job is not "invent a floating coupon" — it is
(i) make the coupon respond to inflation *within* a world, and (ii) supply the
missing "against" side, which is the loss cycle.

**The form:**

```
pc = (rate + spread_over_base)/12
     + φ_PC * (infl_trail[m] - infl_avg) / 12            # (i) coupon tracks inflation within the world
     - pc_loss_m
     - 0.8*d_spread + 0.18*eq + 1.45*e_pc

pc_loss_m = (pc_loss/12) * (0.7 + 0.6*spread_lagged/400) * loss_amp * (1 + ω_PC*max(0, x[m]))
          + θ_toy * max(spread_lagged - 400, 0)/1200 * loss_amp
```

**φ_PC = 1.0, measured against the world's own declared average, not against
C_ANCHOR.** This asymmetry with real estate and private equity is the whole
point and needs its justification stated plainly: property and buyout have *no*
authored inflation channel anywhere in the WorldSpec, so their excess is measured
against the platform anchor. Private credit's level is *already* authored, through
`factor_conditions.policy_rate`. Measuring its excess against C_ANCHOR would
charge stagflation the inflation benefit twice and print a ~12%/yr private credit
book. Measuring it against `infl_avg` leaves every authored level exactly where
the author put it and makes only the *within-world dynamics* coherent: when
inflation spikes in the crisis block, the loan's reference rate follows it up.
Anchor for the value: Fisher one-for-one on a nominal reference rate. (Taylor's
1.5 includes a real-rate response, which the authored glide already carries.)
Declared range 0.75–1.50, label `chosen`.

**Disclosure this coefficient requires.** φ_PC makes the loan's floating base a
*shadow rate* that can differ from the engine's `rate` path. That is an admitted
approximation. It is defensible — ER-2 already records that the engine's rate is
a continuous drift with no meeting calendar, i.e. a coarse object — and the clean
alternative (a policy reaction term inside `_rate_path`) is declined in §2.4 for
reasons that have nothing to do with elegance. The approximation belongs in the
ER-14 close-out entry, not in a footnote.

**ω_PC = 0.03, fractional uplift in the loss rate per pp of inflation excess.**
Economics: sustained inflation squeezes levered borrowers from both ends — input
and wage costs rise, and their own floating coupons rise with the reference rate
— so interest coverage deteriorates and defaults rise. This is the direct
inflation channel to private credit, and it is why private credit responds
*negatively* to ER-14's rates-held probe, which is correct: a lender whose rate
does not rise while its borrowers' costs do is in trouble.

Value derived from a bounding rule rather than picked: **inflation stress must
never exceed the engine's own declared crisis stress.** `_CRISIS_LOSS_AMPLIFIER
= 1.6`, i.e. a +0.6 uplift, and the WorldSpec schema caps
`inflation.average_pct` at 20 (x_max = 18). So ω_PC ≤ 0.6/18 = 0.033. Proposed
**0.03**, declared range 0.015–0.033, label `chosen`. At 12% inflation the loss
rate is lifted ×1.30; at the schema maximum, ×1.54, still below a crisis month.

**θ_toy = 0.10 — the C2 convexity, adapted to the toy plane.** `D-ER14-1` names
the C2 theta/CDLI rule. C2's declared form is
`loss_q = θ · max(ig_spread_{t−4} − s̄, 0)` — the contribution is **convexity**:
losses accelerate once spreads exceed their normal level. Two adaptations are
needed and both are stated rather than assumed:

1. **Additive, never a replacement.** C2's bare form implies *zero* loss below
   the median spread. Substituting it for the toy engine's through-cycle loss
   would delete ER-1's close-out and hand private credit back the Sharpe near 2
   that ER-1 and ER-4 were written to remove. The convex term is therefore added
   *on top of* the existing linear loss.
2. **s̄ = 400bp**, the engine's existing `_SPREAD_REFERENCE_BPS`, documented in
   place as "the spread a normal credit market prices". No new constant, and it
   plays exactly the role C2's `s̄` plays.

θ_toy anchor, derived from two engine constants: `_HY_LOSS_SHARE = 0.45` is the
declared share of a high-yield spread that is expected loss rather than premium;
the engine's own declared private-credit-versus-high-yield credit sensitivity is
`0.8 / 3.5 = 0.229` (the two `d_spread` coefficients), encoding "senior secured,
so it loses less than high yield for the same cycle". 0.45 × 0.229 = **0.103**,
rounded to 0.10. Declared range 0.05–0.20, label `chosen`. **Upgrade path: the
CDLI match rule itself** — when the Cliffwater export lands, θ is set so that
mean modelled loss over train+validation equals the CDLI mean annualised net
realised-loss rate ÷ 4, with the ±30% GFC cumulative check as acceptance and
never as calibration (C2 §4.1, verbatim).

**Rider R2 — read `structural.private_credit.spread_over_base_bps`.** The +4.5%
spread is hardcoded; the field is declared and dead. Its schema default region
(250–900bp) contains 450bp = exactly the hardcoded 4.5%, and **no shipped preset
declares it**, so R2 changes no preset's numbers. Recommended in, same reasoning
as R1.

**Net private credit, both bases.** Under ER-14's probe (rates held, inflation
1% → 12%): ω_PC alone charges 0.30 × ~2.6 pp/yr of baseline loss ≈ **−0.78 pp/yr**,
partly offset by nothing (φ_PC's argument is ~0 when only the declared average
moves), so **−0.8 pp/yr, negative**. In a coherent hot world (stagflation versus
goldilocks, authored rates): +3.5 pp/yr of coupon against roughly −1 pp/yr of
extra loss, so **strongly positive**. Both are shown in §4, because the pair is
the actual answer and either alone is misleading.

### 2.4 Declined: a policy reaction function in `_rate_path`

The tidiest version of all of this would give the policy rate a Taylor response
to trailing inflation, after which private credit's coupon, real estate's cap
rate and everything else would follow for free and no shadow rate would be
needed. It is declined, for two reasons that are worth more than the elegance:

- **It reintroduces exactly the confound ER-14 is about.** ER-14's sharpest
  finding is that the private book's apparent inflation response was a
  second-order effect of a *liquid* sleeve sitting beside it. Routing the fix
  through a public state variable would make "private markets respond to
  inflation" true again only by transmission. The close-out should be able to
  say the private classes respond *directly*.
- **It moves every asset at once.** Bonds, high yield, REITs and real estate all
  carry `d_rate` terms. Changing the rate path in the same release as three new
  private mechanisms makes the attribution unreadable — the ER-12 lesson
  (the `linkage_bite` redefinition was deliberately split into its own change to
  keep attribution clean) applies directly.

It remains a good idea *as its own later release*, with its own attribution, and
it is left as ask A8 so the owner can overrule.

### 2.5 The generated path

The same three channels must reach `pe`/`pc`/`re` on generated worlds, or a
generated stagflation world stays inflation-blind while a toy one does not. On
that plane the mechanism is not engine code but the sealed mapping artifact:

- **A `cpi_trail` regressor and a `b_infl` loading per PM sleeve** — exactly C1's
  declared form and schema fields (`b_infl`, `cpi_trail_k`, `c_anchor`), landing
  in `mappings/sleeve-mappings-v1.2.yaml`.
- **C1 must be extended to `pm_buyout`.** `AM-2026-08-15-001` scopes C1 to
  `pm_infra` and `pm_re_value_add` only. `PM_SLEEVE_FOR_ASSET` maps the product's
  `pe` to `pm_buyout`, so without an extension the generated path's private
  equity stays bit-identical across inflation — ER-14 half-closed. This is a new
  coefficient on a sealed artifact and needs an amendment that extends
  `AM-2026-08-15-001` (ask A6).
- **The trailing window.** `_source_series` already computes a 12-month
  annualised inflation series for display. A K = 24 series must be derived
  alongside it; the 12-month series is left untouched so nothing display-facing
  moves for an unrelated reason.
- **Generated-plane C2 is blocked.** θ_DL is defined *by* the CDLI match rule, and
  the Cliffwater export is not in hand (`CHANGELOG` records the v1.2 estimator as
  unable to run to completion for this reason). The toy plane is not blocked,
  because it has the WorldSpec's own declared `annual_loss_rate_pct` as its level
  and needs only the convex *shape*. Ask A7 decides whether C1 and C2 may be
  decoupled on the generated plane — `AM-2026-08-15-001` currently declares them
  as one adoption event.

---

## 3. The Delta-3 question, framed for decision

**The rule.** `WP3.10-linkage-estimation.md` §4.2: *"Once the macro variables are
included, the crisis indicator loses significance in every specification except
venture capital calls — crisis-period behaviour is explained by the same
fundamentals that explain normal times. Smooth monotone functions of P/D and the
spread are sufficient."* It is enforced structurally, in the signature of
`f_dist`/`f_call`, and restated in `cashflow-tier1-v1.0.yaml`'s `no_crisis_term`
block: *"both functions consume continuous market states only — no regime label,
no recession dummy, by signature."*

**How the proposed mechanisms comply.** All nine coefficients in §2 read
**continuous state variables** and never a label:

| Mechanism | Reads | Label read? |
|---|---|---|
| λ_RE, γ_RE | `infl_trail` (a rolling mean of a simulated continuous path) | no |
| λ_PE, μ_PE | `infl_trail` | no |
| φ_PC | `infl_trail` and the world's declared average | no |
| ω_PC | `infl_trail` | no |
| θ_toy | `spread_lagged`, a continuous level | no |

Nothing keys on `crisis`, on a regime name, or on a narrative field. The
narrative-blindness invariant is untouched: `NumericWorld` still structurally
omits `narrative`, and none of these terms reaches for it.

**One honest caveat, not a violation.** The toy engine's private returns already
contain crisis terms (`re` carries `−1.0*crisis`; `pc_loss_m` carries the ×1.6
crisis amplifier). Those are pre-existing, and Delta 3 binds the tier-1 linkage
API, not the toy return process — but a reader could be forgiven for thinking
otherwise, so it is said here: **this design adds no new label-reading term, and
removes none of the existing ones.** Whether the toy engine should be held to
Delta 3 at all is a separate question and is not opened here.

**The actual decision: should inflation enter `f_dist`/`f_call`?**

*The case for.* ER-14's own text says a real fix "admits inflation as a third
continuous state to `f_dist`/`f_call`". Without it, the propensity to distribute
is identical in a stagflation drought and a deflation drought at the same equity
drawdown and spread.

*The case against — recommended.* Three arguments, in increasing order of weight:

1. **No evidential anchor exists.** WP3.10's paper evidence covers drawdown and
   spread. There is no comparable finding for inflation. An inflation coefficient
   in `f_dist` would be `chosen` with *no* anchor at all — weaker provenance than
   any of the nine coefficients in §2, all of which trace to something declared.
2. **The response is largely derived anyway.** The cohort recursion is
   `dist_t = Y·(age/L)^B·f_dist·NAV_grown`. Once real estate returns respond
   +1.35 pp/yr and private equity −0.45 pp/yr, NAV moves, and distributions move
   with it — proportionally, without a single change to the sealed linkage. The
   cashflow layer becomes inflation-sensitive as a *consequence* of the return
   fix, which is the correct causal order.
3. **It is the only part of this package that touches a sealed artifact's
   contents.** Leaving `cashflow-tier1-v1.0.yaml` alone keeps Delta 3's
   structural guarantee and its test intact, keeps the "adds-nothing" regression
   evidence valid as recorded, and removes an entire amendment from the release.

*The residual gap, to be recorded rather than closed.* Under the recommendation,
inflation changes the **level** of distributions (through NAV) but never the
**propensity** to distribute. Two worlds with identical equity drawdown and
identical spreads — one at 12% inflation, one at 1% — will have the same
`f_dist`. Proposal: this is written into the ER-14 close-out entry as a named
residual, so the register still says out loud what the platform cannot answer.
Ask A2.

---

## 4. What the 1970s should look like

The point of this table is to be checked against intuition *before* anything is
built. Scenario: `stagflation_1974` — declared inflation 6.5% average / 9.5%
peak at quarter 6, policy rate authored 6.0 → 8.0, equity crashing, a crisis
block, high-yield spreads peaking well above normal.

Two columns, because they answer different questions and only the pair is
honest:
- **Probe basis** — the ER-14 experiment: inflation varied 1% → 12%, *everything
  else held*, including the authored rate path. This is what the acceptance tests
  measure, because it isolates the asset-side channel.
- **World basis** — the coherent hot world (`stagflation_1974` versus
  `goldilocks`), where the author has also raised rates and crashed equities.
  This is what a player actually experiences.

| Class | Probe basis, 1% → 12% | World basis, 1974 vs goldilocks | Shape within the decade | Does it match intuition? |
|---|---|---|---|---|
| **Real estate** | **+3.3 pp/yr** (0.30 × 11) | **+0.5 to +1.4 pp/yr** — escalated income (+1.35) against the authored rate glide's existing −0.8 pp/yr drag | **Down ~2–4% in years 1–2** while inflation accelerates into the Q6 peak, then **+1.35 pp/yr for the rest of the decade**; the markdown reverses as inflation recedes | Yes — this is the standard property experience of the 1970s: marked down hard on the surge, then the best real asset in the book |
| **Private equity** | **−1.1 pp/yr** (−0.10 × 11) | **Heavily negative**, but almost all of it from the 1.4× beta on a crashing equity market; the *inflation channel itself* contributes only about −0.45 pp/yr | Roughly uniform; no transient | Yes, with a caveat worth seeing: the model says inflation is *mildly* bad for buyout and the equity crash is *severely* bad. If the owner's intuition is that inflation itself should be more punishing, that is an argument for a larger μ_PE, and §8 A3 is where to say so |
| **Private credit** | **−0.8 pp/yr** — the borrower-coverage squeeze, with no offsetting coupon because the probe holds rates fixed | **+2 to +3 pp/yr nominal** — roughly +3.5 pp/yr of extra coupon (6→8% base) less about 1 pp/yr of extra loss from the inflation squeeze and the convex spread term | Coupon benefit steady; losses concentrated in the crisis block and the spread peak, lagged one year behind the spread | Yes, and the pair is the insight: floating-rate credit is a *good* place to be when the central bank responds, and a *bad* one when it does not. A model that could not say both would be worth less |
| **Commodities** (unchanged) | +11 pp/yr | already the only asset with explicit pass-through | — | Unchanged by this design; noted so the private numbers are read in proportion |
| **The real-terms line** | — | At 6.5% inflation, +1.35 pp/yr of nominal property escalation is **still a large real loss**. Nothing in this design makes a private book an inflation *hedge* in real terms — it makes it *less bad* than a nominal one | — | Correct, and it should be said in the close-out: closing ER-14 gives private markets a *response*, not a *hedge* |

**The mirror, which matters as much.** `deflation_bust` declares −1.0% inflation,
so `x = −3.0`: real estate loses 0.30 × 3.0 = **−0.9 pp/yr** of income escalation,
private equity gains 0.10 × 3.0 = **+0.3 pp/yr**, private credit's loss uplift is
zero (the `max(0, x)` floor — deflation does not squeeze borrower coverage through
input costs; it squeezes it through revenue, a different channel, deliberately not
modelled here). If any of those signs looks wrong to the owner, the coefficient is
wrong, and it is much cheaper to find out now.

---

## 5. The F5 batch

`D-ER14-1` batches F5 (calibration drift, the last open finding of the
2026-08-14 translation-layer audit) into this reseal. F5 has three items; they
are not equally urgent and they should not be treated as one thing.

**F5a — CTA vol overshoot. Fix, small.** The CTA rule realises 0.1595 annualised
vol against a declared 0.10 target on the 1974 world. Cause, from
`mapping.py::_cta_rule`: position size is `per_inst_target / sigma` where `sigma`
is a trailing 12-month standard deviation computed causally over `[t-12, t)`. When
volatility jumps, the estimator is stale for up to a year and positions are far
too large — a lagging denominator, not a wrong target. Proposed correction, in
`cta_rule` inside the v1.2 artifact: an **EWMA volatility estimate** (declared
half-life) plus a declared **position cap** on `per_inst_target / sigma`.
Acceptance: realised annualised vol within ±0.02 of the 0.10 target on all four
presets. HF-only and not player-facing today, so it rides free rather than
justifying its own release.

**F5b — PM betas short of the DN-5 priors. Record only. Do not "fix".** v1.1's
`pm_buyout` estimated `equity_mkt = 0.8362` against a DN-5 prior of 1.1–1.3 (and
against v1.0's 0.3476 — the sum-beta(4) route already closed most of the gap).
**Adjusting a measured beta toward a prior is precisely the tuning the seal
exists to prevent**, and this package must not do it. What v1.2 *should* do is
make the gap easier to weigh: restore `r2_train_val` to every PM row, which
`AM-2026-08-15-001` already declares as a v1.2 field, and restate the shortfall
in the report. **No coefficient moves.**

**F5c — Gaussian PM residuals against sealed SM-8. Fix, and this one is
player-facing.** DN5 §9 SM-8 seals *"Student-t, df ≈ 5; block correlation within
style family and within PM asset type"*. `adapter.py:199` draws
`rng.standard_normal(...)`, independent across sleeves. Generated worlds' private
returns therefore have thin tails and no cross-sleeve co-movement — on the path
players actually play. Proposed correction: **standardised Student-t draws** (the
`_t_draws` pattern already in `engine.py`, rescaled by `sqrt(df/(df-2))` so unit
variance is preserved and **no declared `residual_sigma_annual` changes** — the
ER-7 precedent verbatim), plus a **PM block correlation** in the artifact
alongside the existing HF `residual_correlation`. df from SM-8's ≈ 5; the toy
engine uses `_INNOVATION_DF = 6.0`, so if the owner prefers one number across both
planes, say so (ask A9).

**How F5 rides the same reseal.** All three items live in
`mappings/sleeve-mappings-v1.2.yaml` and its estimator — the same artifact C1/C2
already claims. One v1.2 artifact, one estimator run, one G3 reseal covers ER-14's
generated plane *and* all of F5. That is the whole economy of the batch, and it is
real: F5 alone would not justify a reseal.

---

## 6. Acceptance tests — the inverted defect

**The design principle for every threshold below.** A threshold is derived from
the **lower bound of the ratified coefficient's declared range**, never from its
central value. A test that only passes when a coefficient happens to sit
mid-range is testing luck; a test set at the range floor fails only when the
*mechanism* is broken. Where that rule cannot be applied — private equity, whose
net is a difference — the ratification is asked to supply a floor on the net
instead (§8 A3).

**The probe is fixed and is ER-14's own**: `stagflation` preset, 200 paths,
`base_seed = 12345`, one field varied (`factor_conditions.inflation.average_pct`),
everything else held. Reusing the exact experiment that found the defect is what
makes "inverted" mean something.

| ID | Test | Threshold | Why this number |
|---|---|---|---|
| **AT-1** | **The literal inversion.** `run_path(world_1pct, seed).returns["pe"]` must **not** equal `run_path(world_12pct, seed).returns["pe"]`, elementwise | any difference | ER-14's headline is "bit-identical across a twelvefold change". This is that sentence negated, and it is break-proof: it cannot be satisfied by a test that restates the implementation |
| **AT-2** | **PE materiality.** \|Δ annualised `pe`\|, 1% → 12% | **≥ 0.65 pp/yr** | Mechanism predicts 1.1 pp/yr. 0.65 = the asked net floor (0.06) × the 11pp probe range. It is ~30× the largest "noise" move ER-14 measured (`pc` at 0.02 pp), and over a decade 0.65 pp/yr compounds to ~6.7% of terminal PE value — visible on the CIO dashboard rather than lost in a quarter's wobble |
| **AT-3** | **RE sign and magnitude.** Δ annualised `re`, 1% → 12%, must be **positive** | **≥ +1.5 pp/yr** | Mechanism predicts +3.3. 1.5 = λ_RE's declared range floor (0.15) × 11pp − rounding. Today's measured value is **−0.12**, so this is a sign flip of ~1.6 pp/yr minimum |
| **AT-4** | **PC loss bite.** Δ annualised `pc`, 1% → 12%, rates held, must be **negative** | **≤ −0.30 pp/yr** | Mechanism predicts −0.8. 0.30 ≈ ω_PC's range floor (0.015) × 10pp of positive excess × ~2.6 pp/yr baseline loss. Today's measured value is **+0.02** |
| **AT-5** | **PC floating benefit.** +2 pp on `policy_rate.end_pct`, all else held ⇒ Δ annualised `pc` | **≥ +0.80 pp/yr** | A glide ending 2 pp higher raises the mean policy rate ~1 pp, which is ~1 pp/yr of coupon; 0.80 leaves room for the loss side to offset. **This test replaces the naive reading of "PC's floating benefit visible"** — measuring the floating benefit by varying *inflation with rates pinned* asks the coupon to respond to something it is not connected to, and would fail a correct model. §2.3 has the argument; this restatement is ask A10 |
| **AT-6a** | **Inflation-channel inertness.** With `_inflation_path` patched to a constant `C_ANCHOR` **and** θ_toy = 0, `pe`/`pc`/`re` are **bit-identical** to `toy-v0.6` on every preset | exact equality | "Zero inflation delta ⇒ bit-unchanged where the mechanism should be inert." θ_toy is excluded because the convex spread term is a *separate* declared change and is not inflation-keyed — saying so is more honest than a test that quietly covers two changes |
| **AT-6b** | **Public assets untouched.** `equity`, `bonds`, `hy`, `commodities`, `reits` are **bit-identical** to `toy-v0.6` on every preset and every compiler fixture, unconditionally | exact equality | Only three return equations move and no RNG draw is added or reordered. If a public asset moves, something was touched that should not have been — this is the STOP condition of the whole implementation |
| **AT-7** | **No new random stream.** The draw order in `run_path` is unchanged; a test asserts it | structural | Determinism invariant. A new `rng.` call would shift every subsequent stream and make AT-6b unachievable |
| **AT-8** | **Deflation mirror.** `deflation_bust` (−1.0%) `re` must sit **below** `goldilocks` (2.0%) `re` | **≥ 0.5 pp/yr below** | λ_RE range floor 0.15 × 3.0pp = 0.45, rounded. The mechanism must be symmetric — an inflation *response*, not a one-sided bonus that only ever pays |
| **AT-9** | **Battery honesty.** The validation battery re-runs on the stagflation preset; every stylized fact that moves outside its band is **disclosed in the close-out**, and **no threshold is moved to accommodate it** | disclosure rule | The ER-4 discipline: flags are never silenced by moving the flag. This is not pass/fail — it is the rule that governs what happens when the battery moves, which it will |
| **AT-10** | **Generated plane parity.** AT-1/2/3/4 re-run through `ah/port/adapter.py` on the 1974 generated world | same thresholds | Otherwise ER-14 closes on one plane and stays open on the one that ships generated worlds |

**Two anti-test guards**, because a defect this old survived five gates:

- Each of AT-2/3/4 must be demonstrated to **fail on `toy-v0.6`** before the
  mechanism lands (they will: measured deltas today are 0.000, −0.117, +0.022).
  A test that never failed against the defect is not evidence.
- AT-1 and AT-6b must survive a **break-and-revert**: set λ_RE to 0 and AT-3
  must go red; add a stray RNG draw and AT-6b must go red.

---

## 7. The release checklist

**Verbatim from `docs/engine-realism-register.md`, ER-14 "Consequences":**

> Large, which is why this is filed rather than fixed. Changing any private
> return bumps **`TOY_ENGINE_VERSION`** and invalidates every existing RunRecord
> digest; changing the institution's response bumps **`PLAY_ALPHA_VERSION`**
> (both stamps — `port-v4-ladder` and `port-v4-ladder-gen`) and restarts
> leaderboards; both committed bundles (`app/fixtures/toy.bundle.gz`,
> `gen.bundle.gz`) rebuild; the validation battery re-runs and its stylized facts
> move. Touching `f_dist`/`f_call` additionally means amending a sealed artifact
> (`mappings/cashflow-tier1-v1.0.yaml`) through the machine-checked log, and
> relaxing the no-regime-label rule far enough to admit a new state is a decision
> about Delta 3, not a parameter change. `decision_alpha_version` inside the G5
> seal is **not** touched — that names Step 5's research definition and would
> mean something different.

Expanded into the checklist, with the design's answers filled in:

| # | Item | This release |
|---|---|---|
| 1 | `TOY_ENGINE_VERSION` | `toy-v0.6` → **`toy-v0.7`** (`src/ah/core/engine.py:56`) |
| 2 | RunRecord digests | **All invalidated.** Existing runs are fenced by world_id, never deleted |
| 3 | World fences | Toy presets `…511` (stagflation), `…512` (goldilocks), `…513` (deflation_bust), `…514` (reflation_boom), `…515` (prehistory) → **`…521-525`** (the `52x` sub-block = toy-v0.7, per `gen_presets.py`'s documented convention). Played generated preset `…603` (stagflation_1974) → **`…604`**. **The `7xx`/`8xx` campaign and spine worlds are a separate decision — see ask A13**: `stress_1974` `…701`, `stress_1990` `…703`, `narration_1974` `…801`, `spine_pilot` `…802` all consume the engine, so their numbers move, but their ids are *records of what a campaign actually ran* and `gen_presets.py`'s own comment says such records "must not be rewritten" |
| 4 | `PLAY_ALPHA_VERSION` | `port-v4-ladder` → **`port-v5-inflation`** (`src/ah/play.py:92`). The institution's *response* changes because its inputs do |
| 5 | `GEN_PLAY_ALPHA_VERSION` | `port-v4-ladder-gen` → **`port-v5-inflation-gen`** (`src/ah/port/adapter.py:108`) — a distinct value, never a shared bump (survey S3) |
| 6 | `decision_alpha_version` | **Untouched.** Step 5's research definition; bumping it would mean something different |
| 7 | Committed bundles | `app/fixtures/toy.bundle.gz` **and** `app/fixtures/gen.bundle.gz` rebuilt via `scripts/gen_bundle_fixtures.py`; both suites verify them |
| 8 | Presets | Re-run `scripts/gen_presets.py`; `entry_multiple_drift_annual_pct` re-authored to 0.0 on the five 6.5% worlds (ask A5) |
| 9 | Compiler fixtures | `scripts/gen_fixtures.py` is validator-level and **must not change**. If it does — STOP |
| 10 | Golden re-pin sweep | Mechanical: full suite to a log, attribute every failure to (a) a value golden, (b) a world_id pin, or (c) **STOP**. Expected files, from the ER-10 precedent: `test_engine`, `test_digest`, `test_cli`, `test_bundle`, `test_play`, `test_play_linkage`, `test_serve`, `test_programme`, `test_credibility`, `test_gen_adapter` |
| 11 | Battery | `uv run python -m ah.battery.report` re-runs; stylized facts **will** move. AT-9 governs: disclose, never re-band |
| 12 | Leaderboard fencing | Board is keyed `(world_id, seed, decision_alpha_version)`. World-id moves are the fence; old rows survive under old ids and can never share a row with new ones |
| 13 | Credibility console walk | `uv run ah credibility --preset stagflation --preset goldilocks --preset deflation_bust --out …` before merge. Memory rule: the console has twice caught adapter defect classes the unit suite missed |
| 14 | Amendment path | A new dated entry in `governance/amendment-log.yaml` **extending** `AM-2026-08-15-001` (C1 to `pm_buyout`; the toy-plane coefficients; F5a/F5c), `post_hoc: true` with the trigger named as ER-14. Ratified coefficients hashed into the entry **before** the estimator runs |
| 15 | Register + docs | ER-14 → **CLOSED** with the §3 residual named; `CLAUDE.md` register line; `CHANGELOG.md`; `docs/current/private-markets-and-inflation.md` re-headed with the post-fix measurements |

**Locks — all three grepped, listed with impact.**

| Lock | Files hashed | Impact |
|---|---|---|
| `pre-registration.lock` (main, 43 files) | `factors.yaml`, `pre-registration.yaml`, 8 conditional worldspec fixtures, `src/ah/battery/{report.py, stylized.py, thresholds.yaml}`, `src/ah/data/{derive, splice, funding_extend, fx_parity, hqm_extend, ust10y_extend, ust2y_extend, vol_backcast, vol_extend}.py` + 2 data JSONs, `src/ah/eval/{ablation, battery, g2, negative_controls, panel, prereg, reference}.py`, all 10 `src/ah/eval/metrics/*`, `src/ah/{factors, splits, strategies}.py` | **UNTOUCHED — required.** `src/ah/core/engine.py` is in no lock, and neither is any `src/ah/port/` module. The battery *runs*; nothing hashed is *edited*. If this digest moves, something sealed was touched — STOP |
| `pre-registration-g3.lock` (26 files) | `factors.yaml`, `mappings/{cashflow-tier0-v1.0, cashflow-tier1-v1.0, sleeve-mappings-v1.0, sleeve-mappings-v1.1, smoothing-kernel-v1.0}.yaml`, `pre-registration-g3.yaml`, `scripts/{estimate_sleeve_mappings, estimate_sleeve_mappings_v1_1, estimate_smoothing_kernel, freeze_tier0_spec, freeze_tier1_linkage, run_2022_replay}.py`, `src/ah/data/{derive, desmooth, taxonomy}.py`, `src/ah/eval/{episode2022, g3seal, prereg, reference, sleevetails}.py` + 2 metrics, `src/ah/splits.py`, `taxonomy/{albourne_mapping, sleeves}.yaml` | **RESEALED**, once, at the generated-plane adoption event. `sleeve-mappings-v1.2.yaml` and `estimate_sleeve_mappings_v1_2.py` join `seal_scope` **together** — the pattern `AM-2026-08-15-001` already declares. **No existing hashed file is edited**: v1.0 and v1.1 are never touched, and `cashflow-tier1-v1.0.yaml` is left alone under §3's recommendation. If §3 is overruled, that file *is* edited and the reseal becomes a materially larger event |
| `pre-registration-g5.lock` (7 files) | `Instructions/holdout-evaluation-spec.md`, `factors.yaml`, `src/ah/eval/{decision_metrics, g5seal, prereg}.py`, `src/ah/splits.py`, `step5-evaluation-protocol.yaml` | **UNTOUCHED — required.** `decision_alpha_version` is not bumped |

Memory rule applies: three locks share `factors.yaml`, `prereg.py` and
`splits.py`. None is edited here — but the digest of all three is checked before
and after, not just G3's.

---

## 8. Cost and sequence

Implementation begins **only after ratification**. Estimates are working days
for one agent, and each work package carries one full CI gate (~38 minutes,
background, log read as its own step).

| WP | Scope | Days |
|---|---|---|
| `er14-02` | Shared state (`infl_trail`, `C_ANCHOR`) + the real estate mechanism, TDD; AT-1, AT-3, AT-6a, AT-8; rider R1 | 0.5 |
| `er14-03` | Private equity and private credit mechanisms; C2 convexity; riders R2; preset `entry_multiple_drift` re-authoring; AT-2, AT-4, AT-5 | 0.5 |
| `er14-04` | `toy-v0.7` bump, world fences `51x`→`52x` and `603`→`604`, both bundles, **the mechanical re-pin sweep**; AT-6b, AT-7 | **1.5** |
| `er14-05` | Generated plane: v1.2 artifact (C1 + C1-extension to `pm_buyout` + F5a + F5c + restored `r2_train_val`), estimator run, amendment entry, **G3 reseal**, `GEN_PLAY_ALPHA_VERSION`; AT-10 | 1.5 |
| `er14-06` | Battery re-run + disclosure (AT-9), credibility console walk, ER-14 close-out entry with the §3 residual, `CLAUDE.md` / `CHANGELOG` / `private-markets-and-inflation.md` | 0.5 |

**Honest total: 4.5 days, and 4.5 is the optimistic read.** Two reasons to hold a
buffer:

- **`er14-04` is the item that overruns.** The ER-10 precedent — a strictly
  smaller change, one function — needed its own dedicated re-pin task and still
  produced a red gate from a missed consumer (the `artifact-repoint-consumer-sweep`
  memory). Three return equations moving at once touches strictly more goldens.
  Budget 1.5 days and do not be surprised by 2.
- **`er14-05` is blocked or reduced** depending on ask A7. If C1 and C2 must
  adopt together, the generated plane cannot proceed at all until the Cliffwater
  CDLI export is in hand, and the release ships toy-plane-only — which is a
  coherent release, but it must be *decided*, not discovered mid-WP.

**Call it 5 working days with the CDLI question resolved, or 3 days for a
toy-plane-only release with `er14-05` deferred.**

---

## 9. Decision block — the ratification asks

Nothing is implemented until these are answered. Recommendations are given for
every one; each can be overruled with a sentence.

**A1 — The nine coefficients.** Ratify, adjust, or reject each:

| # | Coefficient | Proposed | Range | Anchor (short) | Label |
|---|---|---|---|---|---|
| 1 | `C_ANCHOR` | **2.0 %** | — | `_RATE_SHOCK_INFLATION_ANCHOR`; `_DEF["infl_avg"]`; the goldilocks/prehistory declared average | chosen |
| 2 | `K` | **24 months** | 12 / 36 as sensitivities | C1's declared `cpi_trail_k` = 8 quarters | chosen (C1 verbatim) |
| 3 | `λ_RE` | **0.30** | 0.15–0.45 | C1 / `AM-2026-08-15-001` declared `pm_re_value_add: 0.3`, contract-share anchored | chosen |
| 4 | `γ_RE` | **0.50** | 0.30–0.70 | partial Fisher: committed rent cross-check long-run 0.64 × 72% realised at K = 8 = 0.46 | chosen |
| 5 | `λ_PE` | **0.35** | 0.21–0.49 | unlevered pass-through 0.25 (below RE's contractual 0.30, per ER-14 "partial, net of input costs") × the engine's declared 1.4 leverage beta | chosen |
| 6 | `μ_PE` | **0.45** | 0.30–0.60 | the shipped presets' own authored `entry_multiple_drift_annual_pct = −2.0` at 4.5 pp excess ⇒ 0.444 | chosen |
| 7 | `φ_PC` | **1.0** | 0.75–1.50 | Fisher one-for-one on a nominal reference rate (Taylor's extra 0.5 is a real-rate response the authored glide already carries) | chosen |
| 8 | `ω_PC` | **0.03** | 0.015–0.033 | bounded so inflation stress at the schema maximum stays under `_CRISIS_LOSS_AMPLIFIER = 1.6` | chosen |
| 9 | `θ_toy` | **0.10** | 0.05–0.20 | `_HY_LOSS_SHARE` 0.45 × the engine's own pc/hy spread-sensitivity ratio (0.8/3.5 = 0.229) = 0.103 | chosen |

Every one is `chosen`, none is `measured`, and each upgrade path to
`measured-external` is recorded in §2 and inherited from the C1/C2 lineage
(`b_infl` → NCREIF NPI NOI-growth and cap-rate fits; `θ` → the CDLI match rule;
`λ_PE`/`μ_PE` → an Albourne buyout revenue/EBITDA panel). `D_RE = 4.0` and
`s̄ = 400 bp` are **existing engine constants reused**, not new coefficients.

**A2 — Delta 3.** *Recommended: do NOT admit inflation to `f_dist`/`f_call`.*
The cashflow layer becomes inflation-sensitive derivatively; the sealed
`cashflow-tier1-v1.0.yaml` is untouched; an inflation coefficient there would
have no anchor at all. **Ratify the recommendation and the residual note**
("inflation changes the level of distributions, never the propensity") for the
close-out entry — or overrule and fund the linkage amendment.

**A3 — The private equity net floor.** *Recommended: ratify `|λ_PE − μ_PE| ≥ 0.06`
as a declared constraint*, so that no in-range combination can produce a
near-zero net and quietly re-create ER-14. Also: if the owner's intuition is that
inflation should punish buyout harder than −0.10 pp/yr per pp, say so now — it is
a one-line change to μ_PE before anything is built, and an amendment afterwards.

**A4 — `λ_RE`: value-add 0.30 or core-weighted 0.45?** The product's `re` is a
blended institutional property allocation, more core than value-add, and core
leases carry *more* contractual escalation. C1's declared 0.30 is proposed because
it keeps the research and product planes carrying one belief. 0.45 is defensible
and sits inside C1's own declared range. **Owner's call.**

**A5 — Preset re-authoring.** *Recommended: yes, for the live presets.* Set
`entry_multiple_drift_annual_pct` to 0.0 so μ_PE does not double-count the drift
the author already hand-wrote. Six presets declare `−2.0`: `stagflation` (`…511`),
`stagflation_1974` (`…603`), `stress_1974` (`…701`), `stress_1990` (`…703`),
`narration_1974` (`…801`), `spine_pilot` (`…802`). The first two are live product
worlds and should be re-authored; the last four are campaign/spine worlds and
are covered by A13.

**A13 — The campaign and spine worlds (`7xx` / `8xx`).** These consume the toy
engine, so `toy-v0.7` changes their numbers, but their `world_id`s are records of
what a campaign actually executed — `gen_presets.py` states the principle
explicitly for the G0 world ("that is a record of what G0 actually ran, and must
not be rewritten"). Three options: (a) leave them frozen at their current ids and
accept that re-running them under `toy-v0.7` produces different numbers under the
same id — **not acceptable**, it is exactly the leaderboard collision the fences
exist to prevent; (b) move them to a `72x`/`82x` block and annotate every
campaign evidence document that cites the old id; (c) mark them **retired** —
readable, never re-runnable under the new engine — which preserves the record
without inviting a collision. *Recommended: (c)*, with the retirement noted in
the ER-14 close-out entry. **Owner's call**, and it must be made before
`er14-04`, not during it.

**A6 — Extend C1 to `pm_buyout`.** *Recommended: yes.* Without it the generated
path's private equity stays inflation-blind and ER-14 closes on one plane only.
Requires a new amendment extending `AM-2026-08-15-001`'s declared scope.

**A7 — Decouple C1 from C2 on the generated plane?** `AM-2026-08-15-001` declares
them as one adoption event; C2's θ_DL is defined by the CDLI match rule and the
Cliffwater export is not in hand. *Recommended: decouple* — adopt C1 (plus the
buyout extension and F5) now, and adopt C2 on the generated plane when CDLI
lands. The alternative is a toy-plane-only release. **This is the only genuine
blocker in the package.**

**A8 — A policy reaction function in `_rate_path`?** *Recommended: no* (§2.4:
it reintroduces ER-14's own second-order-channel confound and destroys the
attribution). It is a good later release with its own evidence.

**A9 — Residual df.** SM-8 seals ≈ 5; the toy engine uses 6.0. *Recommended: 5,
per SM-8*, with the divergence from the toy engine disclosed — a seal beats a
convenience.

**A10 — The acceptance thresholds**, as tabled in §6: AT-2 ≥ 0.65 pp/yr, AT-3
≥ +1.5 pp/yr, AT-4 ≤ −0.30 pp/yr, AT-5 ≥ +0.80 pp/yr, AT-8 ≥ 0.5 pp/yr, plus the
exact-equality tests AT-1/6a/6b/7 and the disclosure rule AT-9. **Note the
restatement inside AT-5**: `D-ER14-1` asks that "PC's floating benefit be
visible", and measuring that by varying inflation with rates pinned would ask the
coupon to respond to something it is not connected to. The proposed test varies
the *policy rate* instead. Ratify the restatement or reinstate the literal form.

**A11 — Riders.** R1 (read `real_estate.income_yield_pct`) and R2 (read
`private_credit.spread_over_base_bps`): *recommended in* — both repair dead
declared fields and **neither changes a single preset number**, because no preset
declares either field. R3 (read `private_equity.leverage_turns` to scale the 1.4×
beta): *recommended out* — five presets declare 5.5, so it **would** move shipped
numbers and adds a second confound to the same release.

**A12 — Out of scope, confirm.** Spending indexation (`Policy.spending_rate_annual`
charges 4.5% of *nominal* reported value; `ah/port/twin.py` already has the
machinery and the played institution does not use it) is *recommended out*: it
changes the difficulty of the game rather than the realism of the assets, it is
cleanly separable, and it deserves its own attribution. Making
`inflation.peak_pct` live in `_inflation_path` is likewise *recommended out* —
ER-14's close-out does not require it, and it would move the inflation path shape
in every world at once. Both remain open register items either way.

---

## 10. What closing ER-14 does not buy

Stated here so the close-out entry can carry it rather than a reader inferring it:

- **It is a response, not a hedge.** At 6.5% inflation, +1.35 pp/yr of escalated
  property income is still a large real loss. Private markets become
  inflation-*aware*, not inflation-*proof*.
- **The propensity to distribute stays inflation-blind** under the §3
  recommendation — the named residual.
- **The standing caveat is unchanged.** `hier-flow-v1` beats its benchmark on the
  sealed criterion and is not a convincing model of history; regime persistence is
  undercalled and drawdowns understated ~2×. Closing ER-14 removes one specific
  missing channel. It does not make anything built on the generator
  decision-ready.
- **ER-11 still governs the reported plane.** The shipped reported series is the
  engine's own filter, not the sealed per-sleeve kernel, so de-smoothing a shipped
  series does not recover truth. Nothing in this package changes that, and the
  inflation response will therefore reach players through an appraisal filter
  whose inverse property does not hold.

---

*Not investment advice. Simulation calibration; all parameters generic and, where
authored, labelled `chosen` with a recorded upgrade path.*
