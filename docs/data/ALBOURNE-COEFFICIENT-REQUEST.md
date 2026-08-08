# Data request: pacing-model coefficients across the private-markets taxonomy

**To:** Albourne
**Re:** Pacing-model parameters in lieu of the ALB-A/C lifecycle datasets
**From:** Terrarium / Alternate Histories platform
**Date:** 2026-08-08

---

## 1. The ask, in one paragraph

We license your PriMaRS index returns already and they work well. What index
returns cannot carry is **cashflow timing** — when a fund calls capital and
when it distributes. Rather than request the ALB-A/C fund-lifecycle datasets,
we are asking for the small **coefficient table your pacing model already
contains**: a handful of numbers per strategy. No fund-level data, no LP
data, no raw matrices.

---

## 2. What we need per strategy

| item | shape | definition we will apply |
|---|---|---|
| **Call-rate curve** | one fraction per fund-age year, age 0 through end of the call period (typically 10–13 values) | expected capital called in year *a* of fund life, as a fraction of **then-unfunded** commitment |
| **Distribution bow** | one number | the shape exponent *B* governing distribution timing over fund life. Equivalently: an expected distribution-rate-by-age curve (one fraction of NAV per age year), from which we fit *B* ourselves |
| **Income yield** | one fraction | expected annual **income** distribution as a fraction of NAV, separate from capital return (zero is a valid answer where a strategy returns capital only) |
| **Fund life** | one number, years, plus typical extension | contractual life *L* assumed by the curve above; the age at which we assume terminal liquidation |

Roughly sixteen numbers per strategy. Quarterly granularity, or pooled
medians with dispersion bands, are equally usable — we will state whatever
transformation we apply.

### 2a. Open-ended and hybrid vehicles need different parameters

Six sleeves in our taxonomy are evergreen or hybrid rather than closed-end
(core and core-plus real estate, core and core-plus infrastructure, the
infrastructure aggregate, specialty/asset-backed finance). Takahashi-Alexander
pacing does not describe them. Where you model these, we would instead want:

- typical **subscription queue** length (months from commitment to funding), and
- typical **redemption terms** — notice period, gate percentage, and whether
  gates have historically bound in stress.

---

## 3. Which strategies — two priority tiers

### Tier A — the nine we model today (needed to close the current gap)

These already map to PriMaRS indices we license, and are the sleeves our
simulation runs:

| our sleeve | PriMaRS index we map | id |
|---|---|---|
| `pm_buyout` | Buy-Outs/Growth | 547791 |
| `pm_growth` | Growth (PE) | 553469 |
| `pm_vc` | Venture Capital | 547813 |
| `pm_secondaries` | Secondaries | 553463 |
| `pm_direct_lending` | Senior Debt | 553475 |
| `pm_mezzanine` | Private Credit *(proxy — see §6)* | 547807 |
| `pm_distressed` | Distressed, Stressed & Special Situations | 547805 |
| `pm_re_value_add` | Real Estate Equity Value-Added | 558969 |
| `pm_infra` | Infrastructure | 553478 |

### Tier B — the rest of our taxonomy (send whatever exists)

Our sleeve taxonomy declares 39 private-markets strategies. The 30 below are
defined in our system but unparameterized; each one you can supply becomes a
strategy we can model rather than approximate. **Where a strategy is not
separately parameterized in your pacing model, saying so is a useful answer**
— it tells us to model it as a variant of its group aggregate rather than
wait for data that does not exist.

**Private equity** — large-cap buyout, mid-market buyout, small buyout,
early-stage venture, late-stage/growth venture
*(PriMaRS carries Middle Market Buy-Outs 553467, Small Market Buy-Outs 553468,
Early Stage VC 553472 — so returns exist for three of these five already.)*

**Private credit** — unitranche, opportunistic/special-situations credit,
specialty & asset-backed finance *(hybrid — see §2a)*, venture debt

**Secondaries** — LP-interest PE secondaries, credit secondaries, GP-led /
continuation vehicles
*(PriMaRS carries Buy-Outs/Growth Secondaries 553464.)*

**Real estate** — core *(evergreen)*, core-plus *(evergreen)*, opportunistic,
real estate debt
*(PriMaRS carries RE Equity Opportunistic 553497, RE Credit 553482,
RE Credit Opportunistic 553495.)*

**Infrastructure** — core *(evergreen)*, core-plus *(hybrid)*, value-add,
greenfield/development, infrastructure debt

**Natural resources** — energy, mining/metals, timberland, agriculture
*(PriMaRS carries a Natural Resources aggregate 553479 and Real Assets 547777;
we have no sub-strategy returns.)*

**Multi-manager** — fund-of-funds, co-investment
*(Fund-of-funds matters to us disproportionately: fee layering and a distinct
call/distribution profile, and no PriMaRS index we can see.)*

**Niche** — pharma royalties, music/media royalties, litigation finance
*(No PriMaRS coverage; pacing parameters alone would still let us model them.)*

---

## 4. What we are **not** asking for

- Fund-level, manager-level or LP-level data of any kind.
- The full ALB-A/C lifecycle or age-by-calendar matrices — **this request
  replaces that ask**.
- Return series — already licensed via the PriMaRS Public Dataservice.
- Fee, carry, hurdle or waterfall conventions — we parameterize those
  contractually ourselves.

---

## 5. How the numbers will be used and governed

They parameterize a Takahashi-Alexander-family commitment / call /
distribution model inside a closed, single-tenant simulation platform; your
data is not redistributed. Each coefficient set is recorded with its source
and date in a version-frozen mapping file under our pre-registration
discipline: a later revision supersedes by dated, logged amendment — never a
silent overwrite. Parameters you supply will be labelled *measured* in our
register; today's values are labelled *chosen* (judgement anchored to
consultant aggregates), which is precisely the state we are trying to leave.

---

## 6. Four questions where your convention decides ours

**1. Call base.** Is your call schedule defined on **committed** or on
**unfunded** capital? The two imply different never-called shares. Our current
placeholder is on unfunded and leaves roughly a third of commitments uncalled
by the end of the call period — a number we believe is an artefact of the
placeholder rather than a fact about buyout funds, and this convention may be
the whole explanation.

**2. Distribution functional form.** We currently apply

```
annual distribution rate = Y · (age / L) ^ B          (multiplicative)
```

whereas Takahashi-Alexander (2002) canonically write

```
annual distribution rate = max( Y , (age / L) ^ B )   (Y as an income floor)
```

Which does your pacing model use? We have deliberately not chosen between
them on judgement; the decision is recorded in our system as blocked pending
your data.

**3. Income vs capital split.** Does your model distinguish an income yield
(cash yield on NAV) from the total distribution rate? Ours currently overloads
a single parameter for both, which degenerates the split at the values we use.
A separate income yield per strategy resolves it.

**4. Mezzanine.** We could not find a mezzanine index in the PriMaRS asset
universe and currently carry mezzanine on the broad Private Credit index as a
declared proxy. If a mezzanine index or mezzanine pacing parameters exist,
they would retire that proxy.

---

## 7. Scope note

Only **one** strategy (buyout) is parameterized in our system today, and every
parameter in it is judgement, not measurement. So for eight of the nine Tier A
strategies — and all thirty in Tier B — this is a *first* parameterization
rather than a refresh of existing numbers.
