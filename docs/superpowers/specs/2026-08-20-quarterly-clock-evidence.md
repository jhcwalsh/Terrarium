# Quarterly clock, annual vintages — release evidence

**Date:** 2026-08-21 · **Branch:** `qc-01-clock` (all eleven implementation tasks —
S0-S7, A1-A3 — plus this WP's two tasks, E1-E2, land as commits on this one branch;
the plan's three-branch split (`qc-02-server`/`qc-03-app`/`qc-04-evidence`) was
collapsed to one branch for this release, per this WP's own task framing)
**Decision this evidences:** D-QC-1 (`governance/decision-register.md`), ratified
2026-08-20, "quarterly clock, annual vintages" — declared before implementation in
`AM-2026-08-20-001` (`governance/amendment-log.yaml`).
**Spec:** `docs/superpowers/specs/2026-08-19-quarterly-clock-design.md`
**Plan:** `docs/superpowers/plans/2026-08-20-quarterly-clock.md`

---

## What changed for the player, in one paragraph

The game used to stop nine times a decade — once a year, at months 11, 23, ...
107 — and each stop carried everything at once: a stance for the whole coming
year plus the commitment that became an entire vintage year. It now stops
**thirty-nine times, every quarter-close from month 2 through month 116**. Each
stop still carries a stance, now for the coming quarter, plus an *editable*
commitment figure for whichever vintage year is currently forming — a figure
that can be revised at each of that year's remaining windows before it
**locks** at the year-close (the same months 11, 23, ... 107 where the engine
has always fired a vintage). A crash year that used to be one stop with no
chance to react inside it is now four. New sessions score under a new
play-alpha version (`port-v7-quarterly` / `port-v7-quarterly-gen`) so a
39-window decision skill is never compared against a 9-window one.

## What did NOT change

- **The engine.** `src/ah/core/engine.py`, `src/ah/port/engine.py`
  (`run_quarter`), the cashflow tiers, the ladder, `sleevestate.py` are
  byte-untouched across every commit on this branch (verified per-task and
  re-verified below). `TOY_ENGINE_VERSION` did not move.
- **The pacing model and the annual vintage ladder.** `CommitmentPlan` still
  carries exactly nine entries per decade, one per vintage year; the engine
  still fires one vintage per year, at the same months.
- **Annual history stays intact and ranked in its own era.** A session created
  before this release carries no `decision_windows`/`play_alpha_version`
  (NULL on both columns). It resolves to the old 9-window
  `decision_months` grid and to the FROZEN legacy alpha literals
  (`port-v5-inflation` / `port-v6-chosen-pe-gen`, never the live constants),
  so it replays bit-identically, completes as annual if it was in flight at
  deploy, and ranks only against other annual-era rows — proven live below,
  not only under unit test.
- **The three seal locks.** main/G3/G5 digests are unchanged from before the
  first commit on this branch to this evidence commit (below). No file this
  release touches is hashed in any lock.
- **`decision_alpha_version`** (the G5-sealed research definition,
  `ah.eval.decision_metrics`) did not move — it names Step 5's sealed
  research grid, a different thing from the product's `PLAY_ALPHA_VERSION`.

## The three seal locks, unchanged start to finish

Verified before Task S0's first edit (recorded in the S0/S1 report) and
re-verified now, at the head of this WP, with the identical values both times:

| Lock | Digest |
|---|---|
| G3 | `sha256:9689d5008f0ae0b271e08ee298dfd611b590dd52a1c5d95e42bf8d15c04a47f5` |
| G5 | `sha256:0596b861f56a0490ccca75ca96ff775543947c3bbd0b788173a5152e559a25e7` |
| main (`pre-registration.lock`) | OK |

---

## Criteria 1-7, each against its proof

| # | Criterion | Task | Proof | Verdict |
|---|---|---|---|---|
| 1 | 39 windows, never the final close, general across horizons | S2 | `tests/test_qc_windows.py` — 6 functions / 14 parametrized cases: the decade grid, the final-close exclusion property (nm in 12/60/118/120/240), the too-short-horizon empty case, the year-close subset matching `decision_months`, the full-following-quarter precondition, and a pin that `decision_months` itself did not move. **14/14 passed**, re-run fresh at this evidence commit. | **PASS** |
| 2 | A stance at window m governs exactly months m+1..m+3 | S4 | `tests/test_qc_regression.py::TestQuarterlySemantics::test_stance_at_a_window_governs_exactly_the_following_quarter` — a decision at month 2 leaves quarter 0 untouched and moves quarter 1; the same stance one window later (month 5) starts one quarter later. Live-walk confirmation below (all four stances exercised in rotation across the 39 windows, no unexpected 4xx). | **PASS** |
| 3 | A commitment edited at any window of a vintage year, left untouched afterward, locks at the last-edited figure; untouched all year locks at the plan figure; the no-decision tape is IDENTICAL to before this release | S1+S4 | `tests/test_qc_regression.py::TestAnnualEraIsBitIdentical` (12 tests: 4 worlds x {flat_play, flat_play_true_basis, annual_decisions}) generated from the pre-change code at commit `deebe1e` (second commit on this branch, before any behavior change) and **still green at every subsequent commit through the branch head** — never regenerated, never touched. `TestQuarterlySemantics::test_untouched_year_locks_at_plan` and `::test_last_edit_wins_at_the_year_close` (per-sleeve independence, revision-of-a-revision). **Live-walk proof** (below): month 14's edit (`pe: 6.005`) survived untouched to the month-23 lock; month 26's edit (`pe: 4.2, pc: 1.1`) was partially superseded by month 32's revision (`pe: 2.75`) and locked at month 35 as `{pe: 2.75, pc: 1.1}` — the untouched sleeve (`pc`) kept its earlier edit, the revised one (`pe`) took the latest. `tests/test_qc_regression.py` whole file: **15/15 passed**, re-run fresh. | **PASS** |
| 4 | New sessions stamp the new version; old sessions replay MATCH bit-identical | S5+S6 | `tests/test_qc_versions.py::test_new_sessions_stamp_the_quarterly_version`, `::test_legacy_session_replays_and_scores_under_its_own_version` (a store-constructed NULL-stamped row resolves to the annual grid AND scores `port-v5-inflation`, not the live constant, with 9 review windows not 39). `tests/test_qc_versions.py` whole file: **6/6 passed**, re-run fresh. `uv run ah replay` on the walk's own run (`3bcc5f5c-d1ff-4fb7-8043-e492b086184c`) printed **MATCH** live (stored and replay digests both `sha256:a4b7fe97...` — bit-identical), confirming the engine-untouched half of this criterion end to end, not just from the fixture. | **PASS** |
| 5 | No leaderboard surface ever renders two versions in one ranking | S6 | `tests/test_qc_versions.py::test_quarterly_and_legacy_rows_never_share_a_board` (HTTP layer: `/leaderboard/{world_id}` requires `alpha_version`, a legacy and a quarterly ranked session on the same world/seed never appear on each other's board, and the unversioned query is a 422), `::test_no_ranking_surface_can_aggregate_across_versions` (repository layer), `::test_g5_research_definition_did_not_move` (the sealed research grid's constant is unchanged), `::test_frozen_legacy_literals_are_not_the_live_constants`. The plan's own surface enumeration (six surfaces, S6's task text) needed no `serve.py` edit — every surface was already version-keyed. | **PASS** |
| 6 | App green; a full quarterly decade walked | A1-A3, E2 | `cd app && npm run typecheck && npm run test && npm run build`: **18 files, 269 tests passed, build succeeds** (QC-2 close-out). Two live walks, not one: QC-2's Task A3 walked the browser UI quarter-by-quarter across the Y1->Y2 boundary (windows 2/5/8/11/14/17, a genuine mid-year revision, the lock sentence flipping, the CIO dashboard/bands/vintage ladder confirmed cadence-agnostic) and flagged the stance-only tail and full completion for this WP's fuller pass. This WP's live walk (below) completed that: all 39 windows end to end against the HTTP API, the three stance-only tail windows including a live 422 at the dead lever, a full `complete`/`outcome`, and `ah replay` MATCH. | **PASS** |
| 7 | Amendment lands before the implementation commit | S0 | `git log` on `qc-01-clock`: commit `98a302c` ("governance: D-QC-1 + AM-2026-08-20-001...") touches only `governance/amendment-log.yaml` and `governance/decision-register.md` (`git show --stat` confirms — 2 files, 86 insertions, no `src/`). The first commit touching `src/` is `fc55abc` (Task S2, `quarterly_decision_months`), four commits later. `98a302c` is an ancestor of `fc55abc` on this branch (`git log --oneline deebe1e..fc55abc` shows the direct chain). | **PASS** |

All seven criteria PASS. No criterion required a deviation from its own definition to reach that verdict.

---

## The live walk (Task E2)

Run against this branch's own server (`uv run uvicorn ah.serve:app --port 8787`),
following the repo's 8787 protocol: stopped the released (pre-quarterly) service
that normally lives there (confirmed with the coordinator first — no agent was
using it), ran this branch's instance, walked the decade, stopped it, confirmed
the port free, handed it back for the coordinator to restart the released
service. Total outage window: about ten minutes.

**World, run, session (all append-only rows in the shared `data/ah.db`; none
deleted or repaired):**

- World `00000000-0000-4000-9000-000000000521` (toy stagflation, pinned
  explicitly by id — `ah run` with no `world_id` argument resolves to
  whatever is *latest* in the shared store, which is not safe to assume in a
  multi-agent session).
- Run `3bcc5f5c-d1ff-4fb7-8043-e492b086184c`.
- Main walk session `89f1cb5e-da54-4b3b-98f4-6fc7d7bcd88f` (unranked
  practice — never touches a leaderboard row).
- Dead-lever probe session `6e282a13-452d-42b3-80c4-9098e712a1c5` (a second,
  deliberately incomplete session, since decisions on the main walk are final
  once recorded — probing the 422 without disturbing the main walk).

**What was driven, all 39 windows, over the HTTP API:**

- `decision_windows` on the created session: length 39, first window month 2,
  last window month 116 — matches criterion 1 exactly.
- All four stances (`hold`, `derisk`, `leanin`, `secondary`) exercised in
  rotation across the windows; no unexpected non-200/422 response at any of
  the 39 decisions.
- **A mid-year edit left untouched to its lock:** month 14 posted
  `commitments: {pe: 6.005}`; months 17 and 20 were plain holds; the month-23
  lock recorded `{pe: 6.005}` — the year's one edit, carried forward.
- **A mid-year edit revised again before its lock, per sleeve:** month 26
  posted `{pe: 4.2, pc: 1.1}`; month 32 posted `{pe: 2.75}` (touching only
  `pe`); the month-35 lock recorded `{pe: 2.75, pc: 1.1}` — `pe` took the
  later (month 32) figure, `pc` kept its earlier (month 26) edit untouched.
  This is the per-sleeve last-edit-wins merge (S4), proved end to end against
  a live server, not only under `simulate_play` unit test.
- **The dead lever, live:** on the probe session, advancing to month 111 and
  posting `{"month": 110, "action": "hold", "commitments": {"pe": 1.0}}`
  returned **HTTP 422**, detail: *"month 110: no vintage year is forming at
  this window (the last vintage locked at the final year-close); the
  commitment lever is stance-only here"* — the R-5 door refusal, live.
- **Completion and outcome:** `POST /sessions/{sid}/complete` ->
  `{"status": "completed"}`. `GET /sessions/{sid}/outcome` ->
  `decision_alpha_version: "port-v7-quarterly"`, 39 review windows,
  `final_value 93.27` vs `twin_final_value 106.98`.
- **`ah replay 3bcc5f5c-...`** printed:
  ```
  stored : sha256:a4b7fe974613ef5e46db5100b83190dc63ee2bca1a5a0c0a0fcccaf3ac4aafc5
  replay : sha256:a4b7fe974613ef5e46db5100b83190dc63ee2bca1a5a0c0a0fcccaf3ac4aafc5
  MATCH
  ```
  (Confirmation, not discovery — the engine is untouched by this release, so
  this is exactly the result the design predicts, walked rather than assumed.)
- **`ah credibility --preset stagflation --preset goldilocks`** generated
  cleanly: 2 worlds, 17 flags, no exception. D-QC-1 touches no
  engine/portfolio code, so no new flag was expected or seen; this walks the
  adapter surfaces per the standing console-walk rule for a release adjacent
  to numeric surfaces, and finds them unchanged.

**R-4, outcome latency (the plan's named risk — 39-window attribution is
K+1=40 `simulate_play` runs plus active/twin/drift, about 43 total, versus
about 13 for the old 9-window annual outcome):** the walk's own
`GET /sessions/{sid}/outcome` call measured **15.1-15.4 seconds** across two
runs (client-side wall clock, including HTTP + this sandboxed environment's
own overhead — not a bare-metal number, and not controlled for machine load
from other concurrent agents in this session). This is a real, felt latency
increase over the annual game's outcome screen and is recorded as an
observation for the owner, per the plan's own framing of R-4 ("if
unacceptable, that is an owner decision — batching/caching, never a silent
change to the attribution definition"). No batching or caching was added by
this WP.

**R-6, feed/wire density (spec §4.4: verify, don't re-author):** recorded by
QC-2's Task A3 walk and carried here unchanged — the wire is not empty
between quarterly stops for the shipped presets (roughly 4-6 entries observed
per quarter-step: three monthly `DATA` releases, one quarterly `CENTRAL BANK`
statement, one quarterly `BENCHMARK BOOK` statement, occasionally a `PRESS`
item). The content repeats structurally within a year (an annually-authored
pack), so quarter-*specific* wire content remains a possible follow-up WP,
not acted on here.

---

## Test evidence, counts from the runner's own output lines

| Suite | Count |
|---|---|
| `tests/test_qc_windows.py` | 14 passed |
| `tests/test_qc_regression.py` | 15 passed (12 annual-era baseline, unmoved since `deebe1e`, + 3 quarterly-semantics) |
| `tests/test_qc_versions.py` | 6 passed |
| `tests/test_qc_windows.py` + `test_qc_regression.py` + `test_qc_versions.py` together | 35 passed in 79.09s (fresh combined run, this WP) |
| `tests/test_serve.py -k "TestQuarterlyService or TestGeneratedSessions"` | **11 passed** (fresh re-run, this WP — see correction below) |
| App: `npm run typecheck && npm run test && npm run build` | 18 test files, 269 tests passed, build succeeds |
| Full suite (`uv run pytest -q`, Task S7) | green; this environment's `-q` mode prints no final summary line (confirmed a `-q`-specific quirk, not a broken run — the same command with `-v` prints the summary normally), so the verified signal is exit code 0 plus the absence of any `FAILED` line in the log, not a fabricated pass count |

**Honest correction carried forward from the S5/S6 report.** That report's
evidence line originally claimed `test_serve.py -k "TestQuarterlyService or
TestGeneratedSessions"` was 11/11 and a four-file combination was 74/75; a
post-report review re-ran both and found the true numbers at that point in
the branch's history were **8 passed / 3 failed** and **56 passed / 1
failed** (57 tests, not the claimed 75) — the three failures being exactly
the Task-S7 migration-scoped reds the same report's own "left red on
purpose" section named. The qualitative claim (one pre-existing-shape red in
the four-file case) was correct; the counts were wrong. Task S7 then
migrated every one of those reds. **Re-verified fresh for this evidence
doc**, at the branch's current head: the `TestQuarterlyService or
TestGeneratedSessions` subset is genuinely **11 passed, 0 failed** now — S7's
fix holds. Lesson already filed in the S7 report and repeated here because
this evidence doc is exactly the place a wrong count would do the most
damage: counts in this table come from a runner's own output line, re-run at
this commit, never from an earlier report's arithmetic.

**IMPORTANT-1 (S4 review finding, closed in S5/S6).** The no-plan flinch
counterfactual originally stripped only the LOCK month's commitment from the
counterfactual decision map, not every window of the locked vintage year;
fixed in `src/ah/annotations.py` to strip every window of the year, with two
regression tests in `tests/test_annotations.py` reproducing the review's
exact probe shape plus a monkeypatch proving a prior year's edit reaches
`simulate_play` untouched.

---

## Open items, with reasons

1. **The last three windows (110, 113, 116) are stance-only.** No vintage
   forms after the month-107 lock (the engine's last commitment event is
   q=36 of 40 quarters), so the spec's "the commitment lever is live at every
   window" is implemented as "live at every window of a forming vintage
   year"; the served pre-fill is `null` there (the app hides the lever) and a
   posted commitment is a 422 at the door — proven live in this walk, not
   only under unit test. One-line reversal if the owner prefers a
   visible-but-disabled lever with different copy. (Plan risk R-5, Post-
   release note 1.)
2. **The wire's board packs remain annual.** `feed.py`'s content does not
   vary by quarter within a year; density was verified adequate (above), not
   re-authored, per spec §4.4's explicit instruction. A quarter-*specific*
   wire is a possible future WP, not a defect in this one. (Plan risk R-6,
   Post-release note 2.)
3. **Outcome latency roughly triples** (about 13 -> about 43 `simulate_play`
   runs per outcome), measured live at 15.1-15.4 seconds in this environment
   (above). Batching or caching is an explicit owner call, not made here.
   (Plan risk R-4, Post-release note 3.)
4. **The flinch annotation prices the LOCK, not the revision.** A mid-year
   commitment revision produces no annotation of its own; its effect shows up
   only in the locked figure and the window attribution, because the flinch
   cost is defined against what the year's plan would have committed at the
   lock, not against every intermediate edit. This is the plan's own
   post-release note 4 and is stated in `annotations.py`'s docstring at the
   flinch-gating change (`month % 12 == 11`). It is a genuine limitation of
   what the annotation can price, not a bug: pricing every revision would
   require deciding what a "flinch" means for a figure that was never final,
   which the spec does not define and this release does not invent an answer
   for.
5. **The evidence branch structure deviates from the plan's literal text.**
   The plan calls for three branches (`qc-02-server`, `qc-03-app`,
   `qc-04-evidence`), each merged into `main` behind its own gate. This
   release landed all eleven implementation tasks plus this WP's two tasks as
   commits on the single branch `qc-01-clock`, per this session's explicit
   task framing at every phase (recorded in each phase's own report). The
   full `run_gate.py` -> `check_gate.py` -> `--no-ff` merge -> push sequence
   the plan specifies for every WP boundary has **not** been run in this
   release; each phase instead ran its own narrower, stated verification
   (`test_qc_regression.py`, the relevant suites, `npm run` triad). **The
   full gate and the merge into `main` remain outstanding** and are the next
   step before this branch is actually released.

---

## What this evidences, and what it does not

This document evidences that the seven acceptance criteria in
`docs/superpowers/specs/2026-08-19-quarterly-clock-design.md` §7 are met by
the code on `qc-01-clock` as of this commit, with the proof named per
criterion and the walk's live numbers alongside the unit tests. It does
**not** evidence that the full CI gate is green (the gate has not been run
on this branch as a whole) or that the branch has merged into `main` — both
are the next, explicitly outstanding step, not implied by anything above.
