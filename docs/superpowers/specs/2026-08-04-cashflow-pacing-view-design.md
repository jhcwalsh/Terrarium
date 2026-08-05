# The private-programme section of the credibility console

**Date:** 2026-08-04
**Owner ask:** "I need to see the cashflow model and the commitment pacing"
— with the linkage to the market environment shown **explicitly**
**Status:** design approved, awaiting implementation plan

---

## Why

The commitment lever is the next thing to build (`experience-deltas-register`
§E1, §E4). Before a player can be asked to set commitment pacing, the owner
has to be able to see what the pacing model actually does — whether the
programme behaves like a private-markets programme, and whether the market
environment moves the cashflows the way a real one would.

Two things are already true and neither is visible. `ah/port/` runs a genuine
cohort recursion — calls against unfunded on an age curve, distributions on a
bow, terminal liquidation, fees, recycling. And `ah/play.py` runs a **ladder**:
a new vintage committed every year in every private sleeve. Both are correct
as far as any test goes, and nobody has ever looked at their shape.

The linkage is the part that matters most and is least visible. Tier 1's
`f_dist` and `f_call` translate market stress into cashflow behaviour, and the
asymmetry between them is the entire liquidity mechanic: **calls barely slow
while distributions dry up**. That claim is currently a docstring. This
section puts the numbers behind it on a page.

## The constraint that shapes everything

The credibility console's contract, inherited verbatim: **admin tooling and
nothing else.** It reads worlds, computes, and writes nothing. It is not in
the pre-registration seal, it never touches the scored path, and no number it
computes reaches a player. A flagged row is an invitation to look, not a
failure — nothing here can fail a build.

Two facts about the current code shape the design:

1. The market states the linkage consumes (`drawdown_depth`, `spread_ratio`)
   are computed **inside** `simulate_play` and thrown away — they are not on
   `PlayQuarter`, so a diagnostic cannot read them out of a result.
2. There is **no linkage-off switch**. Without one there is nothing to compare
   the linked cashflows against, and "the linkage cost you this much" cannot
   be stated as a number.

Both are fixed additively in `ah/play.py`. Neither changes any arithmetic on
the scored path — see *What this does not touch*.

## Decisions taken

| # | Decision | Choice |
|---|---|---|
| 1 | Where it lives | **A section in `ah credibility`**, not a new command. It is already the "walk a world's numbers before anyone plays it" surface. |
| 2 | Module | **New `src/ah/programme.py`**, computing *and* rendering its own HTML fragment. `credibility.py` is already ~450 lines and about market returns. |
| 3 | Subject | **The hold-course twin** (`simulate_play(paths)` with no decisions) — the counterfactual the product already scores against. |
| 4 | Depth | Detail on **path 0**; summary statistics across **20 sibling paths** (`base_seed + 7919k`). Twenty, not the console's 400, because each path runs the full quarterly waterfall. |
| 5 | Linkage treatment | **Explicit and first-class** — its own block, showing the states, the multipliers, and the realised cost against a linkage-off run of the same tape. |
| 6 | Per-vintage tables | **Out of scope** for v1. A per-vintage NAV stack is in; full quarterly tables per cohort are not. |

## Architecture

```
ah/programme.py                     (new — pure compute + one HTML fragment)
  ProgrammeReport      <- build_programme_report(world, base_seed, n_paths)
  render_programme_section(reports) -> str        (HTML fragment, inline SVG)
  PROGRAMME_PLAUSIBLE  : declared priors, editable

ah/credibility.py                   (+3 lines)
  render_credibility_page()  embeds the fragment

ah/play.py                          (additive only)
  PlayQuarter  gains: drawdown_depth, spread_ratio, f_dist, f_call
  simulate_play(..., linkage: bool = True)
```

Dependencies point downward as the repo requires: `programme.py` imports
`ah.play`, `ah.port.*`, `ah.core.*`. Nothing imports `programme.py` except the
console and its tests.

## Components

### Block A — the model itself (world-independent, rendered once)

The primitives, straight from the frozen artifacts, each an inline SVG with
its parameter values printed beside it:

- **call rate `RC(age)`** — `rc_curve` from the cohort contract document
  (`fixtures/state/closed-end-cohort.example.json`, validated through
  `ah.core.sleevestate`)
- **distribution bow `Y·(age/L)^B`** — `yield_rate`, `bow` and
  `contractual_life_years` from the same document
- **`f_dist(drawdown, spread_ratio)`** — `a_drawdown`, `b_log_spread`,
  `floor`, `ceiling` from `mappings/cashflow-tier1-v1.0.yaml`
- **`f_call(drawdown)`** — `c`, clipped to [0.5, 1.2]

Both linkage curves carry a **rug of the decade's realised quarters**, so the
reader sees not just the response function but where this world actually
landed on it.

This block states, in words, next to the curves: the linkage consumes
**continuous market states only** — drawdown depth and a spread ratio — and
never a regime label (DN-5 Delta 3, structural). The page shows the states
themselves so that claim is checkable rather than asserted.

### Block B — the ladder (per world)

Year by year: committed, unfunded, paid-in, NAV, calls, distributions, net
cashflow. Plus a per-vintage NAV stack, which is where "the programme dies at
year five" was visible the first time and would be visible again.

### Block C — the market linkage, explicitly (per world)

**The block the owner asked for.** Per quarter, four series side by side:

| column | meaning |
|---|---|
| equity drawdown depth | tier 1's first continuous state |
| spread ratio | the second — spread ÷ 400bp reference |
| `f_dist` | the resulting distribution multiplier |
| `f_call` | the resulting call multiplier |

Then the realised consequence: **distributions received vs the same tape run
with the linkage off**, per quarter and cumulative. The gap is the linkage's
bite, in points, not in prose.

The block names the asymmetry in words beside the numbers: `f_call` is bounded
to [0.5, 1.2] and near-flat by design, while `f_dist` can fall to its floor.
Calls keep coming while distributions stop — that asymmetry, not the drawdown
itself, is what empties the cash account. If the numbers on the page do not
show that, the model does not do what the design says it does, and this
section is how we find out.

### Block D — liquidity

Cash across the decade, coverage true vs reported, and every forced sale with
its cause and what was sold. The model's own distinction is preserved:
selling liquid assets to fund a call is ordinary funding; a forced **secondary**
at the policy haircut is distress. Collapsing them is what made the first run
of `ah.play` report 27 alarming quarters.

### Block E — plausibility flags

Declared priors in the console's existing idiom. Editable — that is the point.

Each statistic is computed **per path across all 20** and reported as the
median with its 10th–90th percentile spread; the flag fires on the median, and
path 0's own value is shown alongside so the detail blocks above can be
reconciled against it. One path can be unlucky; a flag should mean the world
does this, not that one decade did.

Every statistic below is defined against **the vintage committed in year 1**
where it concerns a single cohort, and against **the whole private programme**
where it concerns the institution. Stated because "DPI at year 10" is
ambiguous in a ten-year decade: the year-1 vintage only reaches age 9, and
that is the age the band is written for.

| Statistic | Band | The question it asks |
|---|---|---|
| peak unfunded ÷ private NAV, programme | 0.25 – 0.75 | is the ladder over- or under-committed |
| year-1 vintage call rate over its first 3 years, annualised, as a share of its opening unfunded | 0.15 – 0.45 | do funds draw at a realistic speed |
| age at which the year-1 vintage's cumulative distributions first exceed its cumulative calls | 4 – 8 yrs | the J-curve crossover |
| year-1 vintage DPI at age 9 (cumulative distributions ÷ paid-in) | 0.7 – 2.0 | does a fund actually return capital |
| programme distribution **rate** (distributions ÷ opening private NAV) in the worst-drawdown quarter ÷ the same rate at the median quarter | 0.30 – 0.80 | how hard the linkage bites — a rate, not a level, so the ladder's growth cannot masquerade as a linkage effect |
| cumulative distribution shortfall vs the linkage-off run, as a share of that run's cumulative distributions | 0.05 – 0.35 | the linkage's total decade cost |
| forced secondaries per decade, hold course | 0 – 1 | is distress rare enough to mean something |
| true private weight vs policy band, every quarter | inside (0.15, 0.40) | does the twin obey its own policy |
| reported coverage vs true, worst quarter | reported < true | wrong sign means the smoothing is backwards |

## Data flow

```
world (preset or stored run)
  -> run_path(world, base_seed + 7919k)        k = 0 .. 19
       -> simulate_play(paths)                  linked   (detail: k=0)
       -> simulate_play(paths, linkage=False)   unlinked (the counterfactual)
  -> ProgrammeReport   (per-quarter series, per-year ladder, flags)
  -> render_programme_section()  -> HTML fragment
  -> embedded in the credibility page
```

Deterministic throughout: same world, same seed, same bytes. No RNG is drawn
in this module; every path comes from the standard ensemble seed lineage.

## Error handling

- A world whose tape is shorter than one quarter: the section renders a stated
  "not enough tape" note rather than an empty table.
- A missing frozen artifact (`cashflow-tier0/1-v1.0.yaml`): the existing
  `Tier0Error`/`Tier1Error` propagates. The console should fail loudly — a
  credibility page rendered without the parameters it claims to display would
  be worse than no page.
- A forced-sale log entry of an unexpected `kind`: rendered verbatim rather
  than silently dropped, so an unknown cause is visible.

## Testing

- Each statistic against a hand-built cohort with known flows — the arithmetic
  is checked against numbers computed by hand, not against its own output.
- **Determinism**: same world and seed produce byte-identical fragments.
- **Render**: all four presets produce a section without raising.
- **Read-only by construction**: an import-graph test asserting `programme.py`
  imports nothing from `ah.store`, `ah.serve`, or any writer — "writes
  nothing" enforced structurally, in the spirit of the leakage-guard test.
- **`simulate_play` is unchanged by default**: a test pinning that a
  hold-course run's quarters are byte-identical to the committed
  `app/fixtures/toy.bundle.gz` twin ledger, so the additive fields and the new
  keyword are proved inert on the scored path.
- **The linkage-off run is tier 0**: `simulate_play(..., linkage=False)` must
  drive `f_call = f_dist = 1.0`, matching the sealed "tier 1 with the linkage
  off IS tier 0" identity that `cashflow_tier1.py` already asserts.

`dataviz` skill to be loaded before the first line of SVG code.

## Scope

**In:** `src/ah/programme.py`; three lines in `credibility.py`; four additive
fields and one keyword-only parameter in `ah/play.py`; tests as above;
`CHANGELOG.md`.

**Out:** per-vintage quarterly tables; any comparison of pacing *strategies*
(that is the commitment lever's own work, and it wants the lever to exist);
any change to the bundle contract; any change to the app; any change to what a
player sees.

## Consequences the owner has accepted

- The section adds runtime to `ah credibility`: 20 full waterfall simulations
  per world, against the current 400 vectorised return paths. One constant
  (`_PROGRAMME_PATHS`) if it needs to move.
- The declared bands are **one allocator's priors**, not truth. Flags will
  appear on first run and some of them will be the band's fault, not the
  model's. That is the same bargain the existing console makes.
- The section may well show that the programme is *not* behaving like a real
  one. That is the point of building it before the lever, not after.

## What this does not touch

- **No scored-path arithmetic.** The four new `PlayQuarter` fields are records
  of values `simulate_play` already computes and discards; `linkage` defaults
  to `True`, which is exactly today's behaviour. No number a player has seen
  changes.
- **`PLAY_ALPHA_VERSION` is not bumped.** The alpha definition is unchanged.
- **No bundle contract bump.** `ah/bundle.py:_twin_ledger` builds its dict from
  named fields, so additive fields on `PlayQuarter` do not reach
  `world-bundle-0.4`.
- **Not in the pre-registration seal.** `ah/play.py` and `ah/credibility.py`
  are outside `hashed_files`; `programme.py` will be too.
- **`ah.eval.decision_metrics.DECISION_ALPHA_VERSION` is untouched** — that
  names Step 5's research definition and sits inside the G5 seal.

---

*Not investment advice.*
