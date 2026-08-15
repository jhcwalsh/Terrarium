# TASK — WP4.2 narration workbench (DN-9 v1.1)

## Context

DN-9 specifies a narration layer. Nothing of it is built. Before any of it ships we need to be able to **generate the narratives for a world, read all forty slates, change the voices, and re-run** — repeatedly, cheaply, and deterministically.

That loop is the deliverable. This is a workbench, not a feature.

Read `DN-9-the-wire-narration-architecture.md` for why. Read `spikes/wire_proto.py` for the pipeline shape — it is a spike, it is not ratified, and its parameters are a first draft. Treat it as a reference for *structure*, never as a source of values.

---

## The rule that matters most

**DN-9 contains thirty-five open decisions. You must not take any of them.**

Every tunable value lives in `voices.yaml`. **A skeleton is provided** — its keys match bucket B of documentation register Amendment A3 one-to-one, and it ships with 40 values set to `UNRESOLVED`. Extend the schema where the build needs keys it lacks; never fill a key it already declares. Nothing tunable is hardcoded, defaulted in Python, or inferred.

If the build needs a parameter that is not in `voices.yaml`:

1. **Stop.** Do not choose a plausible value.
2. Append an entry to `UNRESOLVED.md` — parameter name, where it is needed, what depends on it, and 2–3 candidate values with the trade-off between them.
3. Continue with that code path raising `UnresolvedParameter` at runtime.

A run that hits an unresolved parameter **fails loudly with the list**. It does not proceed on a default. A silently-chosen threshold that later becomes canon is the specific failure this task exists to prevent.

Same rule for copy: if a template bank has no string for a case, emit the marker `[[NO TEMPLATE: class=E0X sev=N]]` in the output. Do not improvise prose.

---

## Scope

### 1. Input adapter

```
narration/adapters/world.py
```

Consume a generated world and expose the monthly series the layer needs. Required, 120 months each:

```
policy_rate  cpi_yoy  equity_index  hy_oas  curve_2s10s  ust_10y
regime       (L2 label, one of EXP SLOW REC CRI STAG REF)
l1_state     (pi_star, r_star, g, v, L)  — needed for the anchor decomposition
```

Optional; if absent the CAPITAL slot is **omitted and the omission stated on the artifact**, never stubbed:

```
cash_pct  private_weight_reported  dpi_vs_plan  calls  distributions
```

Map from whatever the generator actually emits. If a required series is missing, fail with a clear message naming it — do not synthesise it.

**Derived observables** (DN-9 §3.4) are declared in `voices.yaml` with their transform, and each one is stamped in the manifest. Unemployment and payrolls are derived from trend growth; if the map's parameters are not in config, that is an `UNRESOLVED` entry, not a guess.

### 2. Event detection and severity

```
narration/events.py
```

Detect the event classes listed in DN-9 §3.2 for which input exists. Emit a typed event stream to `events.jsonl`.

**Two kinds of class, and this distinction is load-bearing:**

- **Point events** fire on the period they occur (a print, a decision, a monthly move).
- **State events** describe a sustained condition — drawdown, drought, gating, forced sale. These fire on **onset or milestone crossing only**, with consecutive periods grouped into one episode carrying `episode_id` and `episode_month`.

A state event that fires every period it holds is a defect. The spike hit this and it produced 72 severity-3 events per decade against a target of 4–10.

`severity` reads its cut-points, per-class scales and hard overrides from `voices.yaml`. There is no default.

### 3. Slate assembly

```
narration/slate.py
```

Group by quarter, run the slot contest per DN-9 §B.1 — POLICY, DATA, MARKETS, CAPITAL — with contest rules and the three-versus-four-slot threshold read from config. Deterministic: ties resolve by a documented rule, never by dict ordering or set iteration.

Every announcement records the `panel` and `delta` it explains (§B.2). An announcement with no anchor is a defect, not a warning.

### 4. Voices behind one interface

```
narration/voices/base.py      Voice: render(event, context) -> Artifact
narration/voices/fomc.py
narration/voices/columnists.py
narration/voices/economist.py
```

Three voices, each backed by `template` or `llm`, selected per voice in config. **Ship `template` backends for all three in this task.** The `llm` backend is an interface and a stub that raises; wiring it is a later task.

- **FOMC** — decision, statement, statement diff against the previous meeting, dissents, rule-monitor sidebar with the anchor decomposed (§C.5). The narration anchor is smoothed: `ĩ_t = ρ·i_{t−1} + (1−ρ)·anchor_t`. **ρ is unratified — config or `UNRESOLVED`.**
- **Columnists** — speak from the latest print, track consensus, dispersion collapses when consensus is strong and widens at turning points (§D.11).
- **Economist** — templated rationale plus, more importantly, the **strain score** (§D.6) logged per meeting. Strain is the reason this voice is in scope now.

### 5. Template banks as data

```
templates/*.yaml
```

Not Python. A copy change must not be a code change — that is the whole point of the tweak loop.

**Seed the banks from `docs/editorial/voices-golden-set-v0.md`.** That document fixes the cast, the register of each voice, and which blocks are templatable versus which need Tier-2. Expand against it; do not invent a voice. Anything in the banks that cannot be traced to a block there is drift and should be flagged rather than shipped.

Two findings in it change the build and are easy to miss: **the Committee needs no LLM at all** — its register is achieved by removing words, not adding them — and **three of the four columnists template cleanly**, because consensus-hugging voices are formulaic in life. Only the outlier columnist needs Tier-2.

Copy beyond the golden set is placeholder and that is fine. Mark those file headers `STATUS: PLACEHOLDER — not the editorial golden set`.

### 6. Output

```
runs/<run_id>/
  slates.html        all 40 slates, styled, readable end to end in one scroll
  diagnostics.html   §7 below
  events.jsonl       the full event stream
  manifest.json      world id, voices hash, template hash, adapter version,
                     derived-observable register, UNRESOLVED count
```

### 7. Diagnostics — the part that makes this a workbench

`diagnostics.html` must let a reader answer "is this any good?" without reading all forty slates:

| Panel | Shows |
|---|---|
| **Severity calibration** | Distribution; severity-3 count vs the configured target band |
| **Slot contest** | Which class won which slot, how often. Catches one class hogging a slot |
| **Repetition** | Most-frequent phrases and n-grams across the decade. Catches a bank that is too thin |
| **Vocabulary → regime** | Mutual information between copy vocabulary and the L2 label (§3.1 non-injectivity). Precursor to N-2 |
| **Verdict chips** | Distribution of surprise and stance tags |
| **Policy diagnostics** | ε distribution, step-size histogram, **meeting-to-meeting reversal frequency** (DN-9 N-q) |
| **Strain** | Economist strain distribution, and the ten highest-strain meetings linked to their slate |
| **Coverage** | Event classes that never fired; slates that fell below three slots |

**The policy and strain panels are diagnostics on the generator, not on the narration** (§C.6, §D.6). Label them as such. If the generated policy path is unquantised or reverses freely, this report is where it shows up.

### 8. The tweak loop

```
python -m narration build --world <path> --voices voices.yaml --out runs/<id>
python -m narration compare runs/<a> runs/<b>     # manifest + diagnostics delta
```

Editing `voices.yaml` and re-running must be the only step needed to change a voice.

---

## Non-goals — do not build these

- **The Board.** Not in scope, not stubbed, not anticipated in the slate. It depends on the portfolio layer, the minutes, and an open scoring question.
- The peer survey (§6.3) — play-time dependent, unresolved (N-aj)
- Any LLM call. The `llm` backend raises `NotImplementedError`
- Plant-parity harness, bible builder, world compilation
- The leak gate N-1 to N-4 as gates. The vocabulary panel in diagnostics is measurement, not a gate
- Player state, decisions, scoring, RunRecord integration, any UI beyond the two HTML files
- Choosing values for anything in `UNRESOLVED.md`

If a change appears to require touching the generator, the portfolio layer, or WorldSpec, **stop and flag** rather than proceeding.

---

## Acceptance

1. `build` on a world with all required series produces the four output files.
2. **Determinism:** identical world + identical `voices.yaml` → byte-identical `slates.html` and `events.jsonl`. Test this, do not assert it.
3. Changing one value in `voices.yaml` changes the output and the manifest hash, and nothing else.
4. A world missing the optional book series builds successfully, omits CAPITAL, and says so on the artifact.
5. A world missing a required series fails with a message naming the series.
6. An unresolved parameter fails the run and prints the `UNRESOLVED.md` list. **A test asserts that no tunable value is hardcoded** — grep the package for numeric literals outside config loading and justify each survivor.
7. State-event classes produce one event per episode, not one per period. Test with a synthetic 12-month drawdown: exactly one E10 per milestone crossed.
8. Every announcement in `events.jsonl` carries a non-null `panel` and `delta`.
9. `diagnostics.html` renders all nine panels on a real world, with the severity-3 count stated against the configured target.
10. `compare` on two runs differing by one config value reports that value and its downstream effects.

---

## Output

Summarise: package layout, the adapter mapping from generator output to the input contract, **the full `UNRESOLVED.md` list**, and the diagnostics for the first world built — severity-3 count, reversal frequency, and the three highest-repetition phrases.

The `UNRESOLVED` list is the most valuable artifact this task produces. It is the exact set of decisions that must be taken before narration can ship, discovered by building rather than by reading.

---

*Blocks: WP4.2 build, voice tuning ahead of beta. Depends on: a generated world with the §1 required series. Does not depend on: Step 3, the Board, any LLM.*
