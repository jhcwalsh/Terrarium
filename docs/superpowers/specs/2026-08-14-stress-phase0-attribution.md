# Phase 0 — Attribution test for the 0-of-20 forced-secondary observation

*2026-08-14. Companion to
`docs/superpowers/specs/2026-08-14-stress-scenario-compiler-design.md`. Run
before the v0.2 amendments, because the design's motivating claim — markets
too mild to exhaust liquidity — rested on an observation with three live
mechanical suspects. This note tests the attribution.*

---

## 1. Verdict

**Market severity was, and remains, the binding constraint. The design's
"Why we had to" section stands, and this test is the evidence that makes it
stand.**

Under the fully corrected mechanics — tier-1 linkage live, the ER-12
staggered ladder, and the secondary haircut at its Nadauld crisis bound —
forced secondaries fire in **0 of 20 seeds on every shipped world**,
including deflation_bust, the one world the register still records at 6/20.
Each of the three suspect defects is disposed of individually in §4. A new
finding surfaced in the process (§5): the deflation_bust revival died with
toy-v0.6 and nobody re-measured it until now — the register's ER-8
amendment is stale.

---

## 2. The run configuration identified (task step 1)

The 0-of-20 observation is not one run; it is a family of committed
console measurements sharing one harness.

| Item | Value | Committed source |
|---|---|---|
| Harness | `build_programme_report` — the programme section of the credibility console: 20 full waterfall walks per world | `src/ah/programme.py` (`PROGRAMME_PATHS = 20`) |
| Seed rule | `base_seed + 7919·k`, k = 0…19 | `src/ah/programme.py:772` |
| Preset base seed | 771204 (`ah credibility --seed` default) | `src/ah/cli.py:312` |
| 1974 world base seed | 197400 | RunRecord `895d1ecd-7480-41c1-8610-f0faed5e86da` (world `…603`, bootstrap-v1); audit doc |
| Worlds, 2026-08-12 measurement | presets 0501–0504 (toy-v0.5), world 0602 | ER-8 amendment, `docs/engine-realism-register.md` |
| Worlds, 2026-08-14 measurements | presets 0511–0514 (toy-v0.6), world 0603 | ER-10 fence commit `1dc5f62`; audit; ladder-01 commit `d9a6d1c` |
| Linkage | **LIVE** — tier-1 `f_call(dd)`, `f_dist(dd, sr)`, `linkage_version public-0.1`, on the linked run the statistics are computed from | verified in code at commit `1b586b5` (`fc = tier1_f_call(dd)`, default `linkage=True`); audit B2 measured the multipliers (worst quarter f_call 0.9736, f_dist 0.7969) |
| Secondary haircut | fixed **0.19** (the 2022-H2 public anchor) | `src/ah/port/engine.py:39` |
| Opening book | 2026-08-12: three clones of one age-5.25 cohort. From ladder-01 (2026-08-14): staggered 10-rung ladder | `d9a6d1c` commit body |
| RunRecords | **None for the console measurements** — the programme console is read-only by construction (`tests/test_programme_guard.py` forbids it importing `ah.store`). The reproducible configuration is the tuple above, not a stored run id | `src/ah/programme.py` docstring |

The specific committed readings being attributed:

- **ER-6 close-out, 2026-08-12** (`1b586b5`): deflation_bust 6/20 seeds,
  19 events; stagflation, goldilocks, reflation_boom, world 0602 all 0/20.
- **Ladder-01 re-measure, 2026-08-14** (`d9a6d1c`): stagflation 20-seed
  lineage, `forced_secondaries` unchanged (0/20) under the staggered ladder.
- **Translation-layer audit, 2026-08-14** (`90a74c7`): 1974 world 0/5
  decades, pre-ladder, toy-v0.6.

## 3. The re-run (task step 2)

Same worlds, same seed lineages, same harness functions (`simulate_play` →
`programme_quarters` → `path_stats`), at HEAD (toy-v0.6, mappings v1.1,
staggered ladder, linkage live). Two arms per seed **on the same
`EnginePaths` object**, so any divergence is attributable to the haircut
alone: A = committed 0.19; B = 0.46, the Nadauld et al. crisis-state
discount applied for the entire decade — the severity-maximal bound, chosen
so that a null result cannot be blamed on the haircut being right only
part-time. Script: session scratchpad `phase0_attribution.py`; read-only,
no store writes.

| World (world, base seed) | Arm | Incidence | Events | Worst coverage (unfunded/NAV) med · max | Peak unfunded ratio med · max |
|---|---|---|---|---|---|
| stagflation (0511, 771204) | 0.19 | **0/20** | 0 | 0.261 · 0.398 | 0.716 · 1.120 |
| | 0.46 | **0/20** | 0 | 0.261 · 0.398 | 0.716 · 1.120 |
| goldilocks (0512, 771204) | 0.19 | **0/20** | 0 | 0.205 · 0.281 | 0.599 · 0.914 |
| | 0.46 | **0/20** | 0 | 0.205 · 0.281 | 0.599 · 0.914 |
| reflation_boom (0514, 771204) | 0.19 | **0/20** | 0 | 0.200 · 0.294 | 0.584 · 0.963 |
| | 0.46 | **0/20** | 0 | 0.200 · 0.294 | 0.584 · 0.963 |
| deflation_bust (0513, 771204) | 0.19 | **0/20** | 0 | 0.322 · 0.513 | 0.804 · 1.177 |
| | 0.46 | **0/20** | 0 | 0.322 · 0.513 | 0.804 · 1.177 |
| stagflation_1974 gen (0603, 197400) | 0.19 | **0/20** | 0 | 0.169 · 0.271 | 0.546 · 0.744 |
| | 0.46 | **0/20** | 0 | 0.169 · 0.271 | 0.546 · 0.744 |

The two arms are **bit-identical on 20/20 seeds of all five worlds**.

**Controls (harness fidelity + change attribution):**

| Control | Configuration | Result |
|---|---|---|
| ER-6 close-out replay (`1b586b5`, toy-v0.5, cloned book, 0.19) | deflation_bust 0503, seeds 771204+7919k | **6/20 incidence — reproduces the committed reading exactly.** 24 events vs the register's 19: the register's walk ran on the branch tip before the merge, which is not separately pinned; the incidence statistic, which is what this test turns on, matches |
| Pre-ladder at toy-v0.6 (`2f9b0c6`, cloned book, 0.19) | deflation_bust 0513, same seeds | **0/20** — peak unfunded med 1.482, max 2.413 |

## 4. The three suspects, disposed of individually

| Suspect | Finding | Disposition |
|---|---|---|
| **Linkage zeroed in Phase A** | The premise does not describe these runs. WP3.9's zero-linkage scaffold was superseded by WP3.10 before any of the measurements above; `simulate_play` computes tier-1 `f_call`/`f_dist` with `linkage=True` by default, and the statistics come from the linked run (verified in the code at `1b586b5`). Direction check: live linkage **cuts** distributions in stress (audit-measured f_dist 0.7969 in the worst quarter), i.e. it makes forced sales *more* likely than the zeroed scaffold would — so the measurements were taken under the harsher, corrected configuration already | **Exonerated — not present in the run** |
| **Fixed 0.19 haircut** | Real, but structurally incapable of affecting incidence: the parameter is consumed only *inside* the forced-sale branch (`nav_to_sell = shortfall / (1 − haircut)`, `src/ah/port/engine.py:141`) — it prices distress after the trigger, it cannot create the trigger. Empirically: arms bit-identical on all 100 world-seeds at the 0.46 crisis bound. It DOES understate the cost of each event that fires (0.19 vs ~0.46 in crisis — under-priced roughly 2.4×), which matters for the adequacy ladder's *severity* readings and belongs in the tail register | **Exonerated for incidence; real for severity — carried to the tail register (task A7)** |
| **Cloned opening book (ER-12)** | Real at the 2026-08-12 measurement — but its direction was severity-*inflating*: three mid-life clones concentrated unfunded commitment (peak ratio med 1.482 / max 2.413 on deflation_bust) far above the honest ladder (0.804 / 1.177). Correcting it *reduces* forced-sale pressure. Committed evidence agrees: ladder-01 re-measured stagflation `forced_secondaries` unchanged | **Exonerated — the defect pushed the wrong way to explain 0/20** |

## 5. New finding: the deflation_bust revival is dead, and the register doesn't know

The register's ER-8 amendment (2026-08-12) records deflation_bust at 6/20.
At HEAD it is **0/20**. The controls attribute the flip to **toy-v0.6 —
the ER-10 reported-marks fix** (the only numeric change on the preset play
path between the two configurations; the ladder came later and stagflation
re-measured unchanged across it). Mechanically plausible and now measured:
with reported marks running at ~1/3 of true (the ER-10 defect), the pacing
flex read an understated reported private weight and kept committing into
drawdowns; once reported catches up, the committee sees the true weight and
throttles — fewer calls, no forced sales.

Two consequences:

1. **ER-8 needs a re-amendment** (⚑ owner call, register edit not taken
   here): the forced-secondary mechanic is once again unreachable in
   *every* shipped world, including deflation_bust. The 6/20 revival was
   partly an artefact of the then-open ER-10 defect.
2. **The design's case is stronger than it stated.** Every mechanical
   correction made since the observation — honest reported marks, honest
   ladder — moved incidence *down*, to zero everywhere. The corrected
   institution is harder to break, so the severity gap the compiler exists
   to close is wider than the spec's §2 claimed.

## 6. Outcome, read against the task's table

**Row 2: forced sales still near zero — market severity WAS binding.**
"§Why we had to" stands; this note is the recorded attribution evidence.
The v0.2 amendment cites it rather than rewriting the section.

## 7. Limits of this test

- The 0.46 arm applies the crisis haircut for the whole decade rather than
  state-dependently — deliberate, as the severity-maximal bound for an
  incidence test. It is NOT evidence about what a state-dependent haircut
  does to severity readings on worlds where events fire; that measurement
  belongs to the tail-register row, on a stress world that produces events.
- Event *counts* at the ER-6 close-out control differ from the register
  (24 vs 19) because the register's walk commit is not pinned. Incidence
  reproduces exactly; nothing here turns on the count.
- The console harness stores no RunRecords by design; reproduction is by
  the configuration tuple in §2, not by run id.
