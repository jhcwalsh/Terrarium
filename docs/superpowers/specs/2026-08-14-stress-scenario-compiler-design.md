# Stress-Scenario Compiler — Design

*2026-08-14 · Owner-directed. A generator whose job is prescribed severity, not
prediction. Sits beside `bootstrap-v1`, which is sealed, judged, and untouched.*

---

## 1. What this is, and what it never claims

A **stress-scenario compiler**. It takes a declared scenario — a regime shape plus
a severity draw rule per segment — and produces a deterministic ensemble of decades
in which every month is a real historical month and cross-asset co-movement is real.

**It claims:** severe, coherent, composed entirely of precedented months, disclosed.

**It never claims:** probable, typical, representative, or a forecast. It therefore
does not enter the sealed realism battery and does not take a G-gate. Judging a
deliberately severe scenario against "is this the typical distribution of futures"
would be answering the wrong question — the scenario is *atypical by construction*,
which is the point.

Its peer group is supervisory stress testing (CCAR/EBA severely-adverse scenarios),
where the scenario is prescribed, published and argued about on grounds of coherence
and severity — never probability-weighted.

---

## 2. The defect this exists to fix, in arithmetic

Measured on the live panel, 2026-08-14:

- Draw span **1953-04 → 2020-12**, 813 months.
- Regime counts: EXP 405 · REC 159 · REF 111 · SLOW 69 · **CRI 38** · STAG 31.
- Crisis months average **−1.79%** on equities (p5 −11.3%, min −17.1%).

`stagflation_1974` declares a crisis regime for four quarters. `bootstrap-v1` draws
those twelve months from the crisis stratum at its historical average:

> **12 months × −1.79% = −19.5% cumulative.**

A 20% drawdown does not exhaust a liquid leg. That is the whole reason
`forced_secondaries` reads **0 of 20 seeds** on the shipped worlds — not a tuning
miss but a structural consequence of drawing the *average of a regime label*.

**The label is the problem.** "Crisis" is a classification, not a severity measure:
the CRI stratum contains October 2008 and also months that merely satisfied the rule.

The material for a severe scenario exists; it is simply not what the label selects:

| pool | months | mean/month | compounds over 12m |
|---|---|---|---|
| CRI label (today) | 38 | −1.79% | **−19.5%** |
| worst 20% of all months | 163 | −5.25% | **−47.7%** |
| worst 10% of all months | 82 | −7.37% | **−60.1%** |

Ranking by severity rather than by label both reaches the declared depth **and
enlarges** the pool of real material (82–163 months against 38).

Ceiling, stated: worst rolling 12 months in the panel is **−42.6%**; 1929–32 is
outside the sealed draw span. Extending the span is out of scope here (§9).

---

## 3. Decisions taken

| # | Decision | Choice |
|---|---|---|
| D1 | Source of plausibility | Declared waypoints, real texture |
| D2 | Binding across the ensemble | Ensemble-level, not per-path. Seeds differ in depth and timing; some will be materially milder than others, and luck stays part of the game. No path is forced to hit a number — see D4, which supersedes the "declared median" phrasing this decision was first taken under |
| D3 | Governance status | Declared scenario, disclosed. Not battery-judged, no G-gate |
| D4 | Success bar | Graded ladder — **measured, never targeted** (§6.2) |
| D5 | Severity functional | `all_down` default; the menu stays declarable |
| D6 | Generator id | `bootstrap-stratified` (unused slot in the sealed enum) |

### D4 is the one that could have gone wrong

An earlier draft of this design proposed calibrating the severity rule until the
institution broke in a declared fraction of seeds. **That is circular** — a world
tuned until the book breaks, followed by the discovery that the book breaks. Any
conclusion would have been guaranteed by construction.

The direction is therefore inverted, and this is the governing principle of the
whole design:

> **Declare the sampling rule → observe the outcome → check it against precedent.**
> Never: choose the outcome → fit the sampler.

The severity rule is declared in terms that are meaningful without reference to any
portfolio result ("crisis quarters draw from the worst decile of months"). Drawdown
depth is **emergent**. The institution's response is **measured**. §7 is the
mechanism that proves nobody worked backwards.

---

## 4. The mechanism

### 4.1 Shape — unchanged, already exists

The WorldSpec regime sequence continues to say *when* stress arrives and how long it
lasts. `stagflation_1974` already declares: stagflation q0–15, crisis q16–19,
stagflation q20–31, recovery q32–39. Nothing here changes that.

### 4.2 Severity — a tilt on block ENTRY, never a filter on months

Each segment gains a declared draw rule:

```yaml
x_stress:
  functional: all_down            # equity | joint_risk | all_down
  segments:                       # entry_percentile 100 == unrestricted
    - {from_quarter: 16, to_quarter: 19, entry_percentile: 10, mean_block_months: 18}
    - {from_quarter: 0,  to_quarter: 15, entry_percentile: 35, mean_block_months: 18}
    - {from_quarter: 32, to_quarter: 39, entry_percentile: 100, mean_block_months: 12}
  join_tolerance: {hy_spread: 1.5, policy_rate: 1.0}   # level distance, in the factor's own units
  precedent:                      # §7 — argued on history, not on sampler code
    - "crisis entry at the worst decile: 2007-09 ran -50% over 17 months"
    - "1973-74 ran -48% over 21 months with inflation above 10%"
    - "all_down: 2022 ran equities and bonds down together, no flight-to-quality bid"
```

**The severity functional** ranks months, and is declared per scenario because it
determines whether the scenario bites for the right reason:

| functional | ranks by | scenario it expresses |
|---|---|---|
| `equity` | equity return alone | a pure market crash; bonds may rally |
| `joint_risk` | equity down *and* credit widening | a credit-led break |
| **`all_down`** | worst simultaneous move across equity, credit and bonds | **no hiding place — the shape that breaks an illiquid book** |

`all_down` is the default because flight-to-quality is the escape valve a stress test
must be able to close: ranking by equity alone would happily draw October 2008, when
Treasuries rallied hard and handed the institution a liquid leg to sell. Declaring
the functional makes "no flight-to-quality bid" a **stated scenario property a
practitioner can argue with**, rather than a hidden consequence of ranking code.

### 4.3 Coherence — the part that makes this history rather than a shuffle

**History is autocorrelated. A bag of the worst months, shuffled, is not a stress
scenario — it is noise with a severe mean.** Three rules keep the output coherent.

**(a) Severity applies to block ENTRY ONLY.** The percentile restricts which rows may
*start* a block. Once started, the block runs forward through real history
**unfiltered** — including the aftershocks, the policy response and the partial
recovery that actually followed. The autocorrelation is not modelled or imposed: it
is the real subsequent path. A row-by-row severity filter is explicitly forbidden;
it would destroy exactly the structure the compiler exists to preserve.

**(b) Block length is the coherence dial, and stress segments run long.** Every join
is a discontinuity, so fewer joins means more coherence at the cost of variety.
Stress segments declare their own mean block length, longer than the benchmark's
(which was calibrated for ensemble variety, a different objective). Blocks remain
contiguous runs of **whole rows** — one shared index across all fourteen factors —
so equities, credit, rates and inflation move together as they actually did.

**(c) Join discipline on level factors.** Of the sealed 14-factor panel, **nine are
levels rather than returns** — `equity_vol`, `ig_spread`, `hy_spread`, `policy_rate`,
`ust_2y`, `ust_10y`, `cpi`, `hqm_curve`, `funding_spread`. Only five are increments
(`equity_mkt`, `smb`, `hml`, `mom`, `commodities`). Splicing returns is harmless;
splicing levels teleports the credit spread from 300bp to 1400bp in a single month,
which is both implausible and a visible tell.

Candidate entry rows are therefore additionally restricted to those whose **level
state is within a declared distance of the current state** — a nearest-state match on
the level block, standard practice for block bootstrapping level series. The distance
metric and tolerance are declared in the scenario and disclosed.

This interacts with (a): severity picks *which* severe entries are eligible, join
discipline picks *which of those* can be reached from here. Where the two cannot both
be satisfied, the join discipline wins and the block continues rather than re-seeding
— severity is a preference over entries, never a licence to teleport.

---

## 5. Contracts and placement

- **`generator_id: bootstrap-stratified`** — an unused slot in the sealed schema
  enum, so no schema change. Accurate (this *is* a stratified bootstrap; the stratum
  is severity), with the noted confusion risk that `bootstrap-v1` also stratifies.
- **Scenario declared in `extensions.x_stress`** — the schema's namespaced escape
  hatch. Precedent already exists: `stagflation_1974` carries a load-bearing
  `x_campaign_vintage_id`. An engine that does not recognise the extension ignores it,
  per the schema; the stress generator does recognise it.
- **New module `src/ah/gen/stress.py`**, registered through `ah/gen/registry.py`.
  `bootstrap-v1` is not modified, not subclassed, and its sampling logic is not
  imported.
- **Same source panel** via `campaign_source()` — the sealed 1953-04→2020-12 span.
  Reusing the panel loader is data access, not judged code, and it keeps "every month
  is real" verifiable against a disclosed source.
- **New `world_id` block**, so stress worlds can never share a leaderboard row with
  existing ones.
- **RunRecord stamps**: scenario id and version, the functional, per-segment entry
  percentiles and mean block lengths, the join tolerance, the resulting pool sizes,
  and the realised depth — so a run is auditable and replayable without the scenario
  file.
- **No sealed file is touched.** Verify against all three locks before implementing
  (`pre-registration.lock`, `-g3`, `-g5`) — this has cost the project twice.

---

## 6. Acceptance

### 6.1 Properties — these carry the central claim

1. **Every emitted month is a real panel row**, bit-exact on the whole fourteen-factor
   vector. Not approximately, not statistically. This is the test that backs
   "composed entirely of precedented months".
2. **Blocks are whole contiguous rows** — one shared index across factors, so
   co-movement is real. Tested exactly, using a source whose columns are injective in
   the row index (the technique `tests/test_bootstrap.py` already uses), not
   statistically.
3. **Determinism** — same seed, same tape; `ah replay` prints MATCH.
4. **Coherence, measured against the panel itself** — autocorrelation and
   cross-correlation of the generated ensemble compared with the source panel's own,
   plus the count and size of level discontinuities at joins. A scenario whose
   autocorrelation is materially below the panel's has failed (b)/(c) and is a defect,
   not a taste question.

### 6.2 Reports — measured, never targeted

- **Emergent depth.** What the declared rule actually produced: ensemble median
  peak-to-trough, duration, credit-spread peak — printed alongside the historical
  episodes it is comparable to. Plausibility is argued here, after the fact, in the
  open.
- **The adequacy ladder.** Coverage breaches, forced secondaries, ruinous seeds —
  the reference shape being 20/20 coverage breached, 4–8/20 forced secondary, 1+
  ruinous. **Measured once, after the rule is fixed.**

**If the ladder disappoints, the response is to re-examine the severity rule against
historical precedent — never to dial until it passes.** A 0/20 reading has two honest
readings and both are findings: the declared rule is milder than the precedent cited
for it, or the institution is genuinely robust.

---

## 7. The honesty mechanism: commit order

The scenario file — severity rule **plus the historical precedent cited for each
waypoint** — is committed in one commit. The institutional run happens in a later
one.

**Git history is the pre-registration, and it costs nothing.** It is what converts
"we built a world that breaks the book" into "we declared a world, and then found the
book broke". Every scenario carries its precedent citations inline, e.g. *"crisis
entry at the worst decile: 2007-09 ran −50% over 17 months, 1973-74 ran −48% over
21"*, so a reader can dispute the severity on historical grounds rather than
inspecting sampler code.

---

## 8. Disclosure

Every surface that shows a stress world states what it is:

- **Methodology note** — a section stating plainly that these worlds are prescribed
  and severe, not predicted or probability-weighted; that severity is a declared
  sampling rule; and that depth is an emergent consequence reported after the fact.
- **Credibility console** — the scenario's declared rule, its precedent citations,
  the emergent-depth report, and the coherence measurements.
- **The app's provenance surface** — the world is labelled a declared stress scenario
  rather than left to imply a forecast.

---

## 9. Out of scope

- **Extending the draw span** to 1929–1953 for depression-class material. A
  data-layer project with its own splice/proxy and amendment consequences; worth its
  own spec if severity beyond the panel's −42.6% worst 12 months is ever wanted.
- **Any change to `bootstrap-v1`,** the toy engine, or any sealed artifact.
- **Cross-country panels** (JST) — separately scoped, and non-commercially licensed.
- **A generative model with mechanism.** This compiler deliberately has no reaction
  function and no causal structure; it does not attempt to be one and must not be
  described as one.

---

## 10. Open questions

1. **Mean block length for stress segments** — the coherence/variety trade. Start at
   roughly double the benchmark's and measure §6.1.4 rather than guessing.
2. **Join distance metric and tolerance** — which level factors enter the match, and
   how close is close enough. Likely credit spreads and policy rate weighted highest,
   since those are where a teleport is most visible.
3. **Whether recovery segments should be unrestricted or floored.** An unrestricted
   recovery draw can produce a recovery milder than the stagflation that preceded it,
   which may be realistic and may read as broken.
