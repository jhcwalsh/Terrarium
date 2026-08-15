# Stress-Scenario Compiler — Design

*2026-08-14 · **v0.2** · Owner-directed. A generator whose job is prescribed
severity, not prediction. Sits beside `bootstrap-v1`, which is sealed, judged, and
untouched. v0.2 applies amendments A1–A7 after the Phase 0 attribution test
(`docs/superpowers/specs/2026-08-14-stress-phase0-attribution.md`); changelog in
§12, reserved decisions in §11.*

---

## 1. What this is, and what it never claims

A **stress-scenario compiler**. It takes a declared scenario — a regime shape plus
a severity draw rule per segment — and produces a deterministic ensemble of decades
in which every month is a real historical month and cross-asset co-movement is real.

**It claims:** severe · coherent · **real months, invented sequence, precedented
severity rule** · disclosed.

That middle claim is stated precisely on purpose. Every emitted month is a real
panel row, bit-exact — but the *sequence* is assembled, and a decade spliced from
1974, 2008 and 2020 material is a novel joint configuration across fourteen
factors. Precedent for the parts is not precedent for the whole; what carries the
whole is the **declared severity rule and its cited precedent** (§7), plus a
**measured plausibility statistic** (§6.2) reported with every world. The
implication cuts both ways and licenses the product: plausibility is a property of
the joint configuration, not of literal precedent, so an assembled configuration
that never occurred can be *more* plausible than one that did (Kritzman, Czasonis
& Turkington, MIT Sloan WP 6246-21).

**It never claims:** probable, typical, representative, or a forecast.

### What is exempt, and what never is

Two tiers, and the distinction gates the whole design:

- **Coherence — always gating, no exemption.** Hard constraints a broken world
  fails regardless of intent: schema validity and the validator's blocking rules
  (V10/V11/V12), non-negative prices and levels, sign conditions, no money pump,
  bit-exact real rows (§6.1.1), whole-row blocks (§6.1.2), determinism (§6.1.3),
  and **level continuity at joins** (§6.1.4 — the join discipline of §4.3(c),
  promoted here from sampler implementation detail to a stated gating tier). A
  stress world that violates these is not severe; it is broken.
- **Fidelity — exempt, by construction and by design.** The sealed realism
  battery's distributional-typicality judgments answer the wrong question of a
  deliberately atypical scenario. The exemption is named by test id so it is
  auditable rather than rhetorical: `excess_kurtosis`, `skewness`,
  `hill_tail_index`, `acf_r_lag1`, `acf_abs_lag1`, `max_drawdown_median`,
  `corr_distance` (`src/ah/battery/thresholds.yaml`) are **not gates** for stress
  worlds, and no G-gate is taken. Note the two ACF ids' *content* is not escaped:
  §6.1.4 re-imposes autocorrelation-vs-panel as a gating coherence check inside
  the compiler's own acceptance — what is exempt is the battery's typicality
  band, not the obligation to be coherent.

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

**The attribution has been tested, not assumed.** Three portfolio-side defects
were live in the same period, each independently capable of producing 0/20 in any
world; the Phase 0 test
(`2026-08-14-stress-phase0-attribution.md`) disposed of all three — linkage was
live in every committed measurement, the haircut is consumed only inside the
forced-sale branch (arms bit-identical on 100/100 world-seeds at the Nadauld
crisis bound), and the cloned opening book pushed severity *up*, not down.
Under the fully corrected mechanics every shipped world reads 0/20 — including
deflation_bust, whose 6/20 revival died with toy-v0.6. **Market severity was and
remains the binding constraint, and the gap is wider than v0.1 stated.**

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
outside the sealed draw span. Widening the pool is out of scope here — but see §9
for the remedy ordering, which v0.2 changes.

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

### What rule 1 forbids, and what it does not: reverse stress testing

Rule 1 bans *tuning a world until the book breaks and calling the breakage a
finding*. It does **not** ban the distinct, legitimate operation the supervisory
literature calls **reverse stress testing**: searching a **pre-declared** rule
space for the least-implausible world that breaks a given portfolio, then
*reporting that world's plausibility* (the severity ∩ plausibility ∩ narrative
framing of Budnik et al., ECB WP 2941). The difference is what is fixed and what
is free: circular calibration frees the rule to chase an outcome; reverse search
fixes the rule space first and reports where in it the breakage lives.

The carve-out ships with three conditions, all mandatory:

1. **The rule space is declared and committed before the search** — the grid of
   admissible functionals, percentiles and block lengths, in one commit, per §7.
2. **The search reports the found world's plausibility** (§6.2's Mahalanobis
   statistic and its precedent distance) — never a tuned severity presented as
   declared.
3. **The found world is disclosed as search-derived** in its RunRecord provenance
   field (§5), so it can never masquerade as a hand-declared scenario.

Paired with DN-7, reverse search is how the library *guarantees* coverage of the
decision-relevant tail rather than leaving it to the luck of hand-authored
scenarios. Whether it ships in the institutional tier at M6 or later is a
reserved decision (§11, ⚑ D-SC-3).

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
scenario — it is noise with a severe mean.** Four rules keep the output coherent;
the first three govern where a block may start and how it runs, the fourth governs
how long a stressed *state* persists.

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

**(d) Persistence — the rule the entry rule cannot supply.** Severity-at-entry with
long blocks produces **episodes**. The institutional tail is a sustained **decade**:
twelve severe months inside 120 otherwise-normal ones is a bad year inside an
acceptable decade, and it will not exhaust a liquidity programme however deep the
twelve months run. Rules (a)–(c) constrain where a block may start; a fourth rule
must constrain how long a stressed state persists — and it obeys rule 1 like
everything else: **declare the persistence rule, never the resulting depth.**

Three candidate forms, each with its precedent. **Parameterisation is a reserved
owner decision (§11, ⚑ D-SC-1) — proposed here, not taken:**

| form | declares | precedent | tension to note |
|---|---|---|---|
| **P1 — segment-scoped re-entry** | every block starting inside a stress segment re-enters under that segment's entry percentile, for the segment's whole declared span (persistence = the declared shape, enforced at every join) | US 1973–75: 21 months of sustained decline, multiple failed rallies | weakest form — persistence capped by however long the author declared the segment |
| **P2 — declared stress coverage** | the scenario declares stress segments occupying a stated fraction of the decade (e.g. 24 of 40 quarters), precedented as a *shape* | Japan 1990–2003; US 1966–1982 in real terms — decades where the stressed state WAS the decade | pushes the authoring burden up front; mechanically it is just §4.1 used honestly |
| **P3 — decade-statistic constraint** | a declared bound on a rolling decade-level statistic (e.g. cumulative real drawdown over rolling 60 months must remain beyond a stated level for a stated duration), with resampling until satisfied | UK 1973–75 real terms; Japan post-1990 (real equity below entry level for >150 months) | **closest to the rule-1 line** — a bound on a path statistic is a declared *constraint*, not a targeted *outcome*, but the distinction must be policed: the bound must be precedent-derived and committed before any portfolio measurement, and never adjusted against ladder readings |

P1 and P2 compose (P2 declares the span, P1 enforces re-entry inside it) and are
jointly the recommended starting point; P3 is the strongest and the most dangerous.

---

## 5. Contracts and placement

- **`generator_id: bootstrap-stratified`** — a slot already in the sealed schema
  enum, so no schema change. Accurate (this *is* a stratified bootstrap; the stratum
  is severity), with the noted confusion risk that `bootstrap-v1` also stratifies.
  **Erratum, found at build (2026-08-14):** the slot is NOT unused as v0.1–v0.2
  claimed. `bootstrap.py:1063` registers it as a deprecated ALIAS for
  `bootstrap-v1`, load-bearing for the sealed 1.0.x fixture worlds
  (`fixtures/worlds/conditional/`) and referenced by sealed eval code
  (`ah/eval/metrics/conditional.py`). Resolution, preserving both uses:
  `stress.py` re-registers the id with a **dispatcher** — a world declaring
  `extensions.x_stress` routes to the stress compiler; a world without it routes
  to `bootstrap_v1_factory` exactly as the alias always did, bit-identical.
  Registration order is deterministic (`ah/gen/__init__` imports bootstrap, then
  stress; package init always runs), and a test pins both routes.
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
  the realised depth, **the plausibility statistic (§6.2)**, and a **provenance
  field** distinguishing `declared` from `search-derived` (§3's reverse-search
  carve-out) — so a run is auditable and replayable without the scenario file.
- **No sealed file is touched.** Verify against all three locks before implementing
  (`pre-registration.lock`, `-g3`, `-g5`) — this has cost the project twice.

---

## 6. Acceptance

### 6.1 Properties — these carry the central claim, and they are the gating tier (§1)

1. **Every emitted month is a real panel row**, bit-exact on the whole fourteen-factor
   vector. Not approximately, not statistically. This is the test that backs
   "real months".
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
- **Measured plausibility.** Because "real months" cannot carry the plausibility of
  an invented sequence (§1), every stress world reports the **Mahalanobis distance
  of its joint factor configuration against the historical panel** — on the world
  card and in the RunRecord. **Reported, never gating**: a large distance is
  disclosure, not failure, and the statistic exists precisely so the novelty of the
  assembled sequence is measured rather than waved at (Kritzman, Czasonis &
  Turkington, MIT Sloan WP 6246-21).
- **The adequacy ladder.** Coverage behaviour, forced secondaries, ruinous seeds.
  **Measured once, after the rule is fixed.** *Re-anchored 2026-08-15 (owner
  ruling, on the E1 over-commitment measurement):* the original reference shape
  (20/20 coverage breached, 4–8/20 forced secondary, 1+ ruinous) is RETIRED as a
  drafting artifact — it describes no book reachable from precedented markets ×
  declared-or-precedented allocations. The reference is now **coverage-based,
  per allocation band**, drawn from the measured grid on the deepest declared
  world (`2026-08-15-e1-overcommitment-measurement.md`):

  | opening private allocation | expected worst coverage (unfunded/liquid) | breach (≥1.0) |
  |---|---|---|
  | policy floor (15) | ~0.10–0.16 | not expected |
  | default (35) | ~0.31–0.54 | not expected |
  | policy ceiling (40) | ~0.38–0.69 | not expected |
  | beyond policy (55) | ~0.72–1.57 | expected on some seeds |

  A stress world whose measured coverage falls far outside its band is the
  finding — in either direction. The **forced secondary** is re-classified as
  the catastrophic-tail event beyond the breach line: rare because the model is
  honest, expected only for books beyond the declared policy range, and never a
  target incidence.

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

For search-derived worlds (§3), the same mechanism covers the **rule space**: the
grid is committed before the search runs, and the found world's provenance field
names the search.

---

## 8. Disclosure

Every surface that shows a stress world states what it is:

- **Methodology note** — a section stating plainly that these worlds are prescribed
  and severe, not predicted or probability-weighted; that severity is a declared
  sampling rule; and that depth is an emergent consequence reported after the fact.
- **Credibility console** — the scenario's declared rule, its precedent citations,
  the emergent-depth report, the coherence measurements, and the plausibility
  statistic.
- **The app's provenance surface** — the world is labelled a declared stress scenario
  rather than left to imply a forecast; a search-derived world says so.
- **Severity is estimated; incidence is curated — and the two never merge.** How
  *deep* a scenario runs is a fitted, banded property. How *often* the library
  serves a stressed world is a curation choice (DN-7 action spread, pedagogical
  value) with no probabilistic content. If the library over-serves stressed worlds
  without saying so, the product has attached an implied probability to a scenario
  and broken "not a forecast" by accident. The serving ratio goes in the RunRecord;
  the disclosure goes on the world card. Register row TR-7 (`docs/tail-register.md`)
  carries the test.

---

## 9. Out of scope, and the remedy ordering for the severity ceiling

Two disclosed limits in this design share one cause: the −42.6% ceiling and the
thin-material-at-the-extreme problem are both consequences of drawing from **one
country's record**. One country's history is too short to characterise a disaster
tail — the pooled-disaster literature exists precisely because of this (Barro &
Ursúa; Barro & Jin).

**v0.2 orders the remedies.** The first-choice remedy is the **international
record** — Japan post-1990, the UK 1973–75 in real terms, Germany, and the wider
advanced-economy panel: real months, real precedent, and it attacks thin material
by *widening the eligible pool* rather than cutting a thinner slice from the same
one. The 1929–32 extension is second choice: it deepens one country's tail without
widening the pool, and carries its own splice/proxy burden.

⚖ **Both are licence-blocked pending Counsel, and neither is scoped here.** The
JST non-commercial correction of 2026-08-14 (`requirements.yaml`) is unresolved
and sits upstream of any international-panel work. No international data enters
the repo before Counsel clears it (§11, ⚖ D-SC-4).

Out of scope in full:

- **Extending the draw span or pool** — either direction above. Worth its own spec
  when severity beyond the panel's −42.6% worst 12 months is wanted.
- **Any change to `bootstrap-v1`,** the toy engine, or any sealed artifact.
- **A generative model with mechanism** — see §11's two-compiler split. This
  compiler deliberately has no reaction function and no causal structure; it does
  not attempt to be one and must not be described as one.

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

---

## 11. The two compilers, and the decisions reserved to the owner

### Terrarium has two compilers. Only one exists.

The "no mechanism" limit has a consequence v0.1 left unstated: this compiler
cannot serve a premise like *"a supply shock drives a stagflationary decade"*,
because it has no causal structure to attach a premise to. And the narration
layer has **nothing to narrate from**: a spliced decade has no causal story, so
DN-9's Committee and House Economist would be explaining events for which no
explanation exists in the engine.

| | **Stress compiler** | **Premise compiler** |
|---|---|---|
| Declares | Severity rule | Named shock + attribution |
| Mechanism | None | Structural |
| Narration | Consequences only, no causality | Full causal narration |
| Tier | Institutional / liquidity | Practitioner / decision |
| Status | This document | **Not built** |

**Hard rule, binding on the narration layer and not merely a caveat: nothing
built on the stress compiler may narrate causality it does not contain.** A wire
running over a stress world reports what happened — prices, spreads, the
institution's ledger — and never why. This is an enforced constraint on any
narration work package that consumes stress worlds, to be carried into that WP's
acceptance tests, not a limits-section sentence.

### Reserved decisions — propose, never take

| key | ⚑/⚖ | decision | proposal on the table |
|---|---|---|---|
| **D-SC-1** | ✅ **DECIDED 2026-08-15** | Persistence-rule parameterisation (§4.3(d)) | Owner adopted P1+P2 composed (P3 held back). P1 is the shipped sampler's re-entry behaviour, already pinned by test; P2 is authored per scenario. Ruling recorded in `governance/decision-register.md`; built as stress-02 |
| **D-SC-2** | ⚑ | Premise compiler: scoped now or deferred | Not scoped here, deliberately. The split table above is the placeholder |
| **D-SC-3** | ⚑ | Reverse stress testing (§3) in the institutional tier at M6, or later | Conditions are specified; timing is open |
| **D-SC-4** | ⚖ | International-panel licensing (§9) | Counsel first; the JST non-commercial correction (2026-08-14) is unresolved and upstream |
| **D-SC-5** | ⚑ | ER-8 re-amendment: the deflation_bust 6/20 register reading is stale at HEAD (Phase 0 §5) | Register edit is the owner's; the evidence is committed |

Keys are proposals for the governance decision register; final numbering is
assigned at ratification there, not here.

---

## 12. Changelog

| version | date | change |
|---|---|---|
| v0.1 | 2026-08-14 | Initial design (commit `fa5dbe7`) |
| v0.3 | 2026-08-15 | Owner rulings after the measurement arc: §6.2's adequacy-ladder reference shape RETIRED and re-anchored to coverage-per-allocation-band (the E1 grid); the forced secondary re-classified as the catastrophic-tail event beyond the breach line. Ship ruling: world `…703` (Lost Decade, 6-month blocks) ships to the players' library with its declared-stress disclosure; `…702` retired as a record. Coverage ratio + breach line promoted to the teaching surface (product WP) |
| v0.2 erratum | 2026-08-14 | §5's "unused slot" premise for `bootstrap-stratified` was false — the id is a live deprecated alias for `bootstrap-v1`, load-bearing for sealed 1.0.x fixture worlds. Resolved by dispatch-on-declaration (see §5), preserving legacy behavior bit-identically. Found by the Task 4 implementer during the build |
| v0.2 | 2026-08-14 | Phase 0 attribution test run and cited in §2 (result: the motivating claim stands; the severity gap is wider than v0.1 stated). Amendments: **A1** applied — coherence/fidelity split into gating vs exempt tiers, exemption named by battery test id (§1, §6.1). **A2** applied — claim restated as *real months, invented sequence, precedented severity rule*; Mahalanobis plausibility statistic added, reported never gating (§1, §6.2, §5, §8). **A3** applied as proposal — persistence rule §4.3(d) with three candidate forms; parameterisation reserved ⚑ D-SC-1. **A4** applied — international pool named first-choice remedy ahead of 1929–32, Barro & Ursúa / Barro & Jin cited; licence-blocked ⚖ D-SC-4. **A5** applied — two-compiler split stated with the hard narration rule (§11); premise-compiler scoping reserved ⚑ D-SC-2. **A6** applied — reverse-stress-testing carve-out on rule 1 with three mandatory conditions, ECB WP 2941 cited (§3); ship timing reserved ⚑ D-SC-3. **A7** applied — `docs/tail-register.md` created and seeded; severity/incidence separation stated (§8, register TR-7) |
