# Quarterly clock, annual vintages — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking. One reviewed commit per task; a
> review after each task and a whole-WP review before each WP merge.

**Goal:** the game stops thirty-nine times per decade — every quarter-close from month 2
through month 116 — instead of nine. Each stop carries a stance for the coming quarter
plus an editable commitment figure for the vintage year currently forming, which locks at
the year-close stop (months 11, 23, … 107, unchanged). Vintages stay annual; the engine,
the pacing model, the ladder and the vintage charts do not change at all. New sessions
score under a new play-alpha version; every stored session replays and ranks under the
version it was created with. Spec: `docs/superpowers/specs/2026-08-19-quarterly-clock-design.md`
(APPROVED by owner 2026-08-20; registers as **D-QC-1**).

**Architecture:** one new pure function `quarterly_decision_months(nm)` beside the
existing `decision_months(nm)` in `src/ah/core/institution.py` — the old function is NOT
edited or superseded: it remains the toy institution's grid AND the platform's
vintage-year grid (`CommitmentPlan` keeps one entry per year-close). The session row
gains two additive columns: `decision_windows` (the window months, JSON, stamped at
creation) and `play_alpha_version` (stamped at creation); NULL means the legacy annual
session, which replays and ranks exactly as before. `simulate_play`'s commitment
override generalizes to a per-sleeve last-edit-wins merge across the forming year's four
windows — a merge that reduces bit-identically to today's single-month read on every
annual-era decision map (pinned by a baseline fixture committed BEFORE the behavior
change). The app reads its window list from `session.decision_windows` (the server's
authority) instead of the bundle's static annual summary.

**Tech stack:** Python 3.12 (uv), numpy, pydantic + jsonschema, FastAPI, SQLite,
pytest (`--disable-socket`), ruff, pyright; React/TypeScript + Vite + vitest in `app/`.

**Authority documents — read all four before Task S0:**

| Document | What it binds |
|---|---|
| `docs/superpowers/specs/2026-08-19-quarterly-clock-design.md` | the ratified design; §4 the mechanics, §7 acceptance criteria 1–7, §8 the three WPs |
| `governance/decision-register.md` → `D-QC-1` (written by Task S0) | the ruling: quarterly clock, annual vintages |
| `governance/amendment-log.yaml` → `AM-2026-08-20-001` (written by Task S0) | the new play-alpha definition, declared BEFORE implementation |
| `docs/engine-realism-register.md` → ER-2, ER-12, ER-6 | what this partially discharges (the player's meeting calendar) and what it must not disturb (the annual ladder, the commitment lever) |

**One spec correction, grounded (record, not stop):** spec §3 attributes
`decision_months` to `ah/play.py`; it actually lives at
`src/ah/core/institution.py:90` (play.py imports it, line 57) and is consumed by SEVEN
other modules — `serve.py:42`, `store/sessions.py:39`, `annotations.py:26`,
`bundle.py:46`, `density.py:32`, `feed.py:50`, `tournament.py:54` — plus
`gen/recone.py`, whose docstring pins the re-cone grid to the ANNUAL definition
(Step-5 research). Editing `decision_months` in place would therefore change the toy
institution, the bundle's pre-authored twin, the feed's board packs and the sealed-era
research surfaces — all out of scope by the spec's own §4.2. This plan adds a new
function and stores the window set per session instead. Nothing the spec's design asks
for is changed by this correction; it is the file-level route to the same behavior.

---

## The version-awareness decision (spec §4.5 leaves it to implementation)

**Chosen: window months stored on the session document at creation
(`decision_windows` column), plus a `play_alpha_version` stamp column.** The
alternative — a version-aware `decision_months(nm, version)` — was rejected because:

1. **Sessions carry no version today.** The alpha version is resolved LIVE at outcome
   time from module constants (`serve.py:78-81` → `PLAY_ALPHA_VERSION` /
   `GEN_PLAY_ALPHA_VERSION`), exactly what the pe-chosen release re-learned: play-alpha
   stamps live on session outcomes, not RunRecords. A version-aware function would
   still need a new stored field to key off — so both options add a column, and only
   one of them also needs a version→window-rule registry maintained forever.
2. **Self-describing beats derivable.** A stored month list needs no mapping table, is
   general across horizons for free, and makes NULL = "legacy annual" an automatic,
   migration-free upgrade (the exact `_SESSION_STAMPS` additive-column pattern already
   used three times in `store/db.py:100-119`).
3. **The stamp column is needed regardless** for spec §4.3's "in-flight annual sessions
   complete as annual": without it, an annual session completed after deploy would post
   its score under the NEW version — the exact leaderboard mixing criterion 5 forbids.

Legacy fallbacks are FROZEN LITERALS, never the live constants: a NULL-stamped session
resolves to `"port-v5-inflation"` (toy) / `"port-v6-chosen-pe-gen"` (generated) — the
values at `play.py:99` and `port/adapter.py:151` as of this plan's parent commit —
because after the bump the live constants name a different game.

**Proposed new version names** (spec §9 Q3: implementer proposes, amendment fixes):
`PLAY_ALPHA_VERSION` `port-v5-inflation` → **`port-v7-quarterly`**;
`GEN_PLAY_ALPHA_VERSION` `port-v6-chosen-pe-gen` → **`port-v7-quarterly-gen`** (the two
lineages align at v7; distinct strings, never a shared bump — the ER-14 rule).
`TOY_ENGINE_VERSION` does NOT move (no engine edit); `decision_alpha_version`
(`eval/decision_metrics.py`, G5-sealed) does NOT move — a test asserts it.

---

## Global constraints

Every task's requirements implicitly include this section. These are the repo's
standing rules (CLAUDE.md + memory), quoted here so no subagent needs to rediscover
them:

- **The three seal locks — check ALL THREE before the first edit and again before every
  merge** (memory rule: main/G3/G5 share `factors.yaml`, `src/ah/eval/prereg.py`,
  `src/ah/splits.py`; unchecked edits cost gates twice):

  ```bash
  uv run python -c "from ah.eval.g3seal import verify_g3; print(verify_g3())"
  uv run python -c "from ah.eval.g5seal import verify_g5; print(verify_g5())"
  uv run python -c "
  from pathlib import Path; from ah.eval.prereg import load, verify; from ah.factors import load_manifest
  p = load(Path('pre-registration.yaml')); verify(p, load_manifest(), lock_path=Path('pre-registration.lock')); print('main lock OK')"
  ```

  Verified against the lock files at plan time: **none** of the files this release
  touches is hashed in any lock. `src/ah/play.py`, `src/ah/serve.py`,
  `src/ah/core/institution.py`, `src/ah/store/*`, `src/ah/annotations.py` and the app
  are in no lock. `src/ah/eval/counterfactual.py` is in no lock either — and it needs
  no edit (see Task S6's note). `src/ah/eval/decision_metrics.py` IS in the G5 lock and
  is **UNTOUCHED — required**. All three digests must be unchanged at every merge;
  `seal_impact: none` in the amendment entry. If any task finds it needs to edit a
  hashed file — **STOP**, that is an owner event.
- **No engine edits.** `src/ah/core/engine.py` (including `run_quarter` in
  `src/ah/port/engine.py`), the cashflow tiers, the ladder, `sleevestate.py` — all
  byte-untouched. `TOY_ENGINE_VERSION` does not move. If implementation discovers an
  engine edit is required, **STOP and re-ratify** (spec §4.2's own words).
- **No new RNG.** Windows are arithmetic on the calendar. No `numpy.random` call is
  added anywhere; grep the diff for `random` before each merge.
- **Determinism.** Same tape + same decisions = same result, bit-identical. The
  baseline fixture (Task S1) is the mechanical proof for the flat-play path.
- **The server is the authority for value and scoring** (DN-3 W5). The app may mirror
  the window list and target weights (bookkeeping); it never computes value, alpha, the
  pending commitment figure's authority copy, or band alerts client-side.
- **ASCII in anything CLI-echoed or server-logged** (Windows console is cp1252).
  Markdown, docstrings and the app may use Unicode freely.
- **Never weaken a test.** No threshold moves to accommodate a result; no skip/xfail
  without a linked TODO. A test that fails because a defect is fixed is inverted, with
  history kept in its docstring. Reject expected values re-derived from the code under
  test (memory: tests-that-restate-the-implementation) — the baseline fixture is
  generated by code that predates the change, which is the point.
- **Gate discipline.** Lint first (`uv run ruff check . --fix && uv run ruff format .
  && uv run pyright`, and for app tasks `cd app && npm run typecheck && npm run test &&
  npm run build`) BEFORE the ~38-minute gate. The gate runs ONLY via
  `uv run python scripts/run_gate.py gate-<wp>.log` (never bare pytest — the log must
  be sha-bound), in the background, log read as data: the `EXIT:` line and the pass
  count, never a tail. Merge into `main` requires
  `uv run python scripts/check_gate.py <gate-log>` green on the branch, `--no-ff`,
  re-verify HEAD is the stamped commit immediately before merging (the owner commits
  onto branches mid-gate), then plain-push (standing authorization; never force-push).
- **`data/` is the ONE live store behind every worktree junction** (memory rule). All
  tests use tmp-path databases; nothing in this plan writes to `data/ah.db` except the
  live console walk in QC-3, which creates ordinary practice sessions.
- **`schemas/` is read-only vendored truth.** Nothing here touches it: no schema
  enumerates decision windows, the session row, or alpha version names (verified —
  `generator_id` is the enum that pins engines, and it does not move).
- **Dependencies:** none added.
- **One WP per branch, plan order; commit bodies state (a) what was built, (b)
  deviations with reasons, (c) discoveries affecting later WPs. `CHANGELOG.md` updated
  per WP.**

---

## Branch strategy

The spec+plan land on `qc-01-clock` (this branch — merged to `main` first, no gate
needed beyond lint: docs only). Then, per the house one-WP-per-branch rule:

| WP | Branch | Merges into `main` behind |
|---|---|---|
| QC-1 server | `qc-02-server` | full gate via `run_gate.py` + `check_gate.py` |
| QC-2 app | `qc-03-app` | full gate + `npm run typecheck && npm run test && npm run build` |
| QC-3 evidence+docs | `qc-04-evidence` | full gate (mechanical re-check) + the console walk record |

**Governance ordering (spec acceptance criterion 7, NON-NEGOTIABLE):** Task S0's
commit — the D-QC-1 register entry and the AM-2026-08-20-001 amendment entry — is the
FIRST commit on `qc-02-server`, strictly before any implementation commit. Provable
from `git log --follow governance/amendment-log.yaml` vs the first commit touching
`src/`. Task S1 (the baseline fixture) is the second commit and also precedes any
behavior change — its generator runs against unmodified code.

---

## File structure

**Edited:**

| File | Change |
|---|---|
| `governance/decision-register.md` | D-QC-1 entry (Task S0) |
| `governance/amendment-log.yaml` | AM-2026-08-20-001 appended (Task S0) |
| `src/ah/core/institution.py` | `quarterly_decision_months()` ADDED; `decision_months()` byte-untouched |
| `src/ah/store/db.py` | `_SESSION_STAMPS` gains `decision_windows`, `play_alpha_version` |
| `src/ah/store/sessions.py` | create stamps windows+version; `_row_to_doc` materializes `decision_windows`; the three invariant readers consume the doc's own windows |
| `src/ah/play.py` | `PLAY_ALPHA_VERSION` bump; per-sleeve last-edit-wins commitment merge in `simulate_play`; `window_contributions_play(windows=...)` |
| `src/ah/port/adapter.py` | `GEN_PLAY_ALPHA_VERSION` bump (one line + comment) |
| `src/ah/annotations.py` | flinch-cost window indexing goes year-close-ordinal (era-agnostic) |
| `src/ah/serve.py` | stamping at create; `_window_ordinal`→`_vintage_ordinal`; `_plan_window` by ordinal; pending-figure helper; lock-fill at year-close; 422 for commitments past the last lock; session-stamped alpha version with frozen legacy fallback; windows threaded to outcome |
| `app/src/lib/session.ts` | `decision_windows` required on `Session`; `windowLabel` helper |
| `app/src/Play.tsx` | windows from `session.decision_windows`; quarterly copy; stop labels |
| `app/src/components/DecisionWindow.tsx` | quarter-aware header; the lock sentence |
| `app/src/Reckoning.tsx` | per-window review lines gain quarter phrasing |
| `app/src/App.test.tsx`, `Play.cio.test.tsx`, `Play.overlay.test.tsx`, `components/DecisionWindow.test.tsx` | quarterly fixtures |
| `tests/test_sessions.py`, `tests/test_serve.py`, `tests/test_serve_book.py`, `tests/test_annotations.py` | flow migration (Task S7's mechanical rule) |
| `docs/engine-realism-register.md` | ER-2 partial discharge (QC-3) |
| `CLAUDE.md` | play-surface facts (QC-3) |
| `docs/current/METHOD.md`, `docs/current/alternate-histories-audited.md` | "once a year a decision window opens" → quarterly (QC-3) |
| `CHANGELOG.md` | per WP |

**Created:**

| File | Responsibility |
|---|---|
| `scripts/gen_qc_baseline.py` | pins today's flat-play and annual-decision tapes (runs BEFORE any behavior change) |
| `tests/fixtures/qc/annual-era-baseline.json` | the committed digests (criterion 3's anchor) |
| `tests/test_qc_windows.py` | criterion 1: the window arithmetic + properties |
| `tests/test_qc_regression.py` | criteria 2, 3, 4-replay: identity + stance-quarter + lock semantics |
| `tests/test_qc_versions.py` | criteria 4, 5: stamping, legacy fallback, leaderboard separation |
| `docs/superpowers/specs/2026-08-20-quarterly-clock-evidence.md` | QC-3: criteria 1–7 → evidence map |

**Deliberately NOT touched:** `src/ah/core/engine.py`, `src/ah/port/engine.py` and all
of `src/ah/port/` except `adapter.py`'s one version line; `src/ah/core/institution.py`'s
existing `decision_months`/`simulate_institution` (toy plane); `src/ah/bundle.py`
(`summary.decision_months` stays the toy twin's annual display grid — the app stops
reading it as the session window source, Task A1); `src/ah/feed.py` (board packs stay
annual wire beats; density verified, not re-authored — spec §4.4); `src/ah/density.py`,
`src/ah/tournament.py`, `src/ah/gen/recone.py`, all of `src/ah/eval/` (Step-5 research
surfaces under their own sealed definitions); `schemas/`; `app/fixtures/*.bundle.gz`
(the bundle contract does not change).

---

## Plan-level risks

| # | Risk | Handling |
|---|---|---|
| R-1 | **The annual-era flow tests break en masse.** ~146 tests across `test_sessions.py`/`test_serve.py`/`test_serve_book.py` drive sessions through month-11/23 windows; once creation stamps 39 windows, deciding month 11 first is refused (windows decide in order). | Task S7 is a dedicated migration task with ONE mechanical rule and shared helpers (`_play_through` migrated, `_hold_through` added in S5) — never per-test improvisation. Tests asserting LEGACY behavior construct legacy sessions at the store layer (`decision_windows=None`), which stays a first-class shape forever. |
| R-2 | An in-flight annual session scores under the new version (criterion 4/5 breach). | The stamp column + frozen legacy literals (Task S5); `test_qc_versions.py` completes a NULL-stamped session after the bump and asserts the legacy version on its outcome AND its leaderboard row. |
| R-3 | The commitment merge silently changes an annual replay. | The Task S1 baseline is generated from UNMODIFIED code and committed before any behavior change; `test_qc_regression.py` re-derives the same digests after every subsequent task. Bit-identical or the gate is red. |
| R-4 | Outcome latency: 39-window attribution is K+1 = 40 `simulate_play` runs (plus active/twin/drift ≈ 43) vs ~13 today. | Measured in the QC-3 console walk with a stopwatch number in the evidence doc. If unacceptable, that is an owner decision (batching/caching), never a silent change to the attribution definition. |
| R-5 | Windows at months 110/113/116 name no forming vintage (the 9th vintage locks at month 107; the engine's last commitment event is q=36 — `play.py:906`, `q % 4 == 0` with `n_quarters=40` never reaching q=40). Spec §4.1 says "the commitment lever is live at every window". | Resolved as: the lever is live at every window OF A FORMING VINTAGE YEAR; at the last three windows no vintage is forming, the served pre-fill is `null` (the app hides the lever — existing `open && planCommitments &&` guard), and a POSTed commitments map there is a 422 at the door rather than a silently inert store. Flagged to the owner in the plan report; encoded in Task S5. |
| R-6 | The wire's board packs remain annual (`feed.py:308` — bundle-side, pre-authored, toy-twin content). Quarterly steps between year marks can feel empty. | Spec §4.4 says verify density in a console walk, don't re-author. QC-3 Task E2 walks it and RECORDS the verdict; if the owner wants quarterly board packs, that is a follow-up WP against `feed.py`, named in the evidence doc. |
| R-7 | A leaderboard surface mixes versions. | Every ranking surface is enumerated in Task S6 (there are exactly four in-repo readers + one research exporter); each is either triple-keyed already or gets a test. No new surface may be added in this release without joining that list. |
| R-8 | `_window_ordinal` has out-of-module consumers. | Task S5 step 1 greps `_window_ordinal` and `_plan_window` across `src/` and `tests/` before renaming; both are module-private today (verified: only `serve.py` and its tests) but the grep is the guard, not the memory. |

---

## Acceptance-criteria map (spec §7 → this plan)

| Criterion | Task | Named test / check |
|---|---|---|
| 1 — 39 windows, never the final close, general | S2 | `tests/test_qc_windows.py::test_decade_grid_is_the_39_quarter_closes`, `::test_final_quarter_close_is_never_a_window` |
| 2 — stance at m governs months m+1..m+3 | S4 | `tests/test_qc_regression.py::test_stance_at_a_window_governs_exactly_the_following_quarter` |
| 3 — lock semantics; no-edit tape identical to today | S1+S4 | `tests/test_qc_regression.py::test_flat_play_tape_is_bit_identical_to_the_annual_era_baseline`, `::test_untouched_year_locks_at_plan`, `::test_last_edit_wins_at_the_year_close` |
| 4 — new stamp on new sessions; old sessions replay MATCH | S5+S6 | `tests/test_qc_versions.py::test_new_sessions_stamp_the_quarterly_version`, `::test_legacy_session_replays_and_scores_under_its_own_version`; `uv run ah replay` MATCH (engine untouched; walked in QC-3) |
| 5 — no leaderboard surface mixes versions | S6 | `tests/test_qc_versions.py::test_no_ranking_surface_can_aggregate_across_versions` + the surface enumeration |
| 6 — app green; full quarterly decade walked | A1–A3, E2 | `npm run typecheck/test/build`; the QC-3 console walk record |
| 7 — amendment lands before implementation | S0 | git history: S0's commit precedes every `src/` commit on `qc-02-server` |

---

# WP QC-1 — server (branch `qc-02-server`)

**Scope:** governance first, the baseline pin, the window function, the store, the
simulator merge, the service, versions and leaderboards, the test migration.
Discharges criteria 1, 2, 3, 4, 5, 7.

---

### Task S0: GOVERNANCE — the D-QC-1 register entry and the amendment, in a commit of their own

**This commit lands BEFORE any implementation commit on this branch. Criterion 7 is
proven from git history; nothing in `src/` may appear in or before this commit.**

**Files:**
- Edit: `governance/decision-register.md` (append)
- Edit: `governance/amendment-log.yaml` (append)

**Steps:**

- [ ] Verify all three seal locks green (Global constraints command block). Record the
      three digests in the commit body.
- [ ] Append the decision-register entry, following the D-ER16-1 form (ruling, scope,
      considered-and-rejected, status):

      ```markdown
      ## D-QC-1 - RATIFIED 2026-08-20: QUARTERLY CLOCK, ANNUAL VINTAGES

      Owner ruling ("Yes, quarterly clock and annual vintages", 2026-08-19,
      ratified on the approved spec 2026-08-20,
      docs/superpowers/specs/2026-08-19-quarterly-clock-design.md). The play
      surface stops at every quarter-close from month 2 through month 116 -
      39 windows for a 120-month decade, all quarter-closes except the final
      tick (a decision there can affect nothing; the same reasoning that
      gives the annual grid 9 windows, not 10). Each window carries a stance
      for the coming quarter plus an editable commitment figure for the
      vintage year currently forming, locking at the year-close windows
      (months 11, 23, ... 107 - unchanged; the engine still fires one
      vintage per year). CommitmentPlan keeps one entry per vintage year.

      Scope: play surface and scoring only. The engine (run_quarter), the
      pacing model, the ladder (ER-12's one rung per year), the cap
      arithmetic and the vintage charts are untouched; anything requiring an
      engine edit is out of scope by definition. A new play-alpha version
      per plane (AM-2026-08-20-001) separates quarterly scores from annual
      ones; stored sessions replay and rank under the version stamped at
      their creation, in-flight annual sessions complete as annual. No world
      retires (worlds are cadence-agnostic; version keys separate boards).

      Considered and rejected (spec section 6): full quarterly vintages
      (fragments pacing/ladder/charts for no realism gain - real programs
      commit annually); keeping the annual clock (crash years stay
      unplayable, ER-2 stays fully open); a monthly clock (fatigue, and
      stances would out-run the quarterly information the game reveals).

      Status: ADOPTED 2026-08-20, owner-ratified. Executed as the
      qc-02/03/04 release branches under AM-2026-08-20-001 (seal impact:
      none - all three lock digests unchanged). Partially discharges ER-2
      (the PLAYER's meeting calendar now exists; the engine's rate-path
      meeting calendar and 25bp quantisation remain open).
      ```

- [ ] Append the amendment entry. Template: the last entries in the log
      (`AM-2026-08-18-001`, `AM-2026-08-19-001` — same YAML shape: `amendment_id`,
      `date`, `payload`, `post_hoc`, `rationale`, `type`). Write exactly:

      ```yaml
      - amendment_id: AM-2026-08-20-001
        date: '2026-08-20'
        payload:
          artifact: none -- no sealed file is created or edited; this entry declares
            a scoring-definition change on the play surface (the product's
            PLAY_ALPHA_VERSION / GEN_PLAY_ALPHA_VERSION stamps, not the G5-sealed
            decision_alpha_version, which does not move)
          new_versions:
            PLAY_ALPHA_VERSION: port-v5-inflation -> port-v7-quarterly (src/ah/play.py)
            GEN_PLAY_ALPHA_VERSION: port-v6-chosen-pe-gen -> port-v7-quarterly-gen (src/ah/port/adapter.py)
          window_definition: 'quarterly_decision_months(nm): every quarter-close
            month (3q+2) strictly inside the horizon EXCEPT the last one -- for the
            120-month decade, months 2, 5, ..., 116: 39 windows. The final
            quarter-close (month 119) is the decade''s last tick and is not a
            window, the same reasoning that gives the annual grid 9 windows, not
            10. Stances are effective for the FOLLOWING quarter (window m governs
            months m+1..m+3). The commitment figure is per VINTAGE YEAR: editable
            at each of the year''s windows (per-sleeve last edit wins), locking at
            the year-close windows (months 12k+11, k=0..8 -- unchanged); untouched
            all year it locks at the stored plan''s entry (plan-carrying sessions)
            or the pacing rule''s figure (default sessions), exactly today''s
            behaviour. CommitmentPlan keeps 9 entries per decade, one per vintage
            year. Windows after the last year-close (months 110, 113, 116) carry a
            stance only; no vintage is forming there.'
          session_versioning: sessions gain decision_windows (the stamped window
            months) and play_alpha_version columns at creation; NULL means the
            annual era -- such sessions replay under the annual grid and score
            under the frozen legacy stamps (port-v5-inflation /
            port-v6-chosen-pe-gen). Leaderboards remain keyed by
            (world_id, seed, decision_alpha_version); annual-era and
            quarterly-era rows never share a board. No world retires.
          ratification: D-QC-1 (governance/decision-register.md), ratified 2026-08-20
          seal_impact: none. pre-registration.lock, pre-registration-g3.lock and
            pre-registration-g5.lock digests are all unchanged; no hashed file is
            touched. decision_alpha_version (G5) is not bumped.
          trigger: 'owner ruling 2026-08-19 (quarterly clock, annual vintages);
            spec docs/superpowers/specs/2026-08-19-quarterly-clock-design.md;
            partially discharges ER-2 (docs/engine-realism-register.md)'
        post_hoc: false
        rationale: '39 quarterly-effective stances is a DIFFERENT definition of
          decision skill than 9 annual ones, so the play-alpha stamp moves BEFORE
          any implementation lands -- this entry is committed ahead of every code
          change on the release branch and the ordering is provable from git
          history (spec acceptance criterion 7). The counterfactual baselines do
          not change construction: the hold-course twin takes no action at any
          window and re-derives under the new window set by definition; the
          chain-link attribution runs over the session''s own stored windows. The
          sealed research definitions (decision_alpha_version, the re-cone grid,
          the tournament) are untouched and stay on the annual grid they were
          sealed with.'
        type: protocol_change
      ```

- [ ] `uv run ruff check . && uv run pyright` (no code changed — must stay clean);
      re-verify the three lock digests are unchanged.
- [ ] Commit: `governance: D-QC-1 + AM-2026-08-20-001 - quarterly clock declared before implementation (QC-1 Task S0)`.

---

### Task S1: pin the annual era — the baseline fixture, generated from UNMODIFIED code

**This is criterion 3's anchor and R-3's guard. It must be the second commit, before
any behavior change: the generator runs against the parent code, and the fixture is
never regenerated after Task S3 begins (regenerating it later would be comparing the
change to itself).**

**Files:**
- Create: `scripts/gen_qc_baseline.py`
- Create: `tests/fixtures/qc/annual-era-baseline.json`
- Create: `tests/test_qc_regression.py` (the identity test only, in this task)

**Interfaces:**
- The digest method: canonical JSON (sorted keys, compact separators, repr floats —
  the `ah.core.digest` conventions) over the full per-quarter series of
  `simulate_play`, hashed with SHA-256. No rounding beyond repr: "identical" means
  bit-identical.

**Steps:**

- [ ] Write `scripts/gen_qc_baseline.py` (deterministic, no network, no db):

      ```python
      """Pin the ANNUAL-ERA play tapes before the quarterly clock lands (D-QC-1).

      Generated from the pre-change code (parent of the first qc-02-server
      implementation commit) and NEVER regenerated afterward: the committed
      digests are what the quarterly release must reproduce bit-identically on
      (a) the no-decision flat play and (b) a scripted annual decision map --
      spec acceptance criterion 3 and the replay half of criterion 4.
      """

      from __future__ import annotations

      import hashlib
      import json
      from pathlib import Path

      from ah.core.engine import run_path
      from ah.core.numericworld import project_numeric
      from ah.core.worldspec import WorldSpec
      from ah.play import simulate_play

      ROOT = Path(__file__).resolve().parents[1]
      PRESETS = ROOT / "src" / "ah" / "presets"
      OUT = ROOT / "tests" / "fixtures" / "qc" / "annual-era-baseline.json"

      #: The four live toy presets (the shipped decade worlds).
      WORLDS = ("stagflation", "goldilocks", "deflation_bust", "reflation_boom")

      #: A representative annual-era decision map: one of each action, plus a
      #: commitment override at a year-close window, all on the annual grid.
      ANNUAL_DECISIONS = {
          11: "derisk",
          23: {"action": "leanin", "commitments": {"pe": 5.0, "infra": 1.0}},
          35: "secondary",
          47: {"action": "commit", "commitments": {"pc": 0.0}},
          59: "hold",
      }


      def _paths(preset: str):
          doc = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
          nw = project_numeric(WorldSpec.model_validate(doc))
          return run_path(nw, doc["engine_defaults"]["base_seed"])


      def quarter_doc(q) -> dict:
          """Every numeric field a PlayQuarter carries (play.py:415-485), plus
          the per-sleeve maps.

          repr-float canonical JSON: any bit-level drift in any field changes
          the digest.
          """
          return {
              "quarter": q.quarter,
              "month": q.month,
              "cash": q.cash,
              "nav_true": q.nav_true,
              "nav_reported": q.nav_reported,
              "calls_paid": q.calls_paid,
              "distributions_received": q.distributions_received,
              "spending_paid": q.spending_paid,
              "forced_sale_total": q.forced_sale_total,
              "private_weight_true": q.private_weight_true,
              "private_weight_reported": q.private_weight_reported,
              "unfunded_total": q.unfunded_total,
              "drawdown_depth": q.drawdown_depth,
              "spread_ratio": q.spread_ratio,
              "f_dist": q.f_dist,
              "f_call": q.f_call,
              "new_commitments": q.new_commitments,
              "spending_basis": q.spending_basis,
              "spending_rate_annual": q.spending_rate_annual,
              "expired_undrawn": q.expired_undrawn,
              "terminal_distributions": q.terminal_distributions,
              "vintage_nav": dict(q.vintage_nav),
              "liquid_values": dict(q.liquid_values),
              "private_true": dict(q.private_true),
              "private_reported": dict(q.private_reported),
              "private_calls": dict(q.private_calls),
              "private_distributions": dict(q.private_distributions),
              "private_unfunded": dict(q.private_unfunded),
              "private_expired": dict(q.private_expired),
              "nav_true_months": list(q.nav_true_months),
              "nav_reported_months": list(q.nav_reported_months),
          }


      def tape_digest(result) -> str:
          doc = {
              "quarters": [quarter_doc(q) for q in result.quarters],
              "final_value": result.final_value,
              "forced_sale_quarters": result.forced_sale_quarters,
              "total_forced_sales": result.total_forced_sales,
              "forced_secondaries": result.forced_secondaries,
          }
          blob = json.dumps(doc, sort_keys=True, separators=(",", ":"))
          return "sha256:" + hashlib.sha256(blob.encode("ascii")).hexdigest()


      def main() -> None:
          out: dict[str, dict[str, str]] = {}
          for preset in WORLDS:
              paths = _paths(preset)
              out[preset] = {
                  "flat_play": tape_digest(simulate_play(paths, None)),
                  "flat_play_true_basis": tape_digest(
                      simulate_play(paths, None, use_reported=False)
                  ),
                  "annual_decisions": tape_digest(
                      simulate_play(paths, ANNUAL_DECISIONS)
                  ),
              }
          OUT.parent.mkdir(parents=True, exist_ok=True)
          OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="ascii")
          print(f"wrote {OUT}")


      if __name__ == "__main__":
          main()
      ```

- [ ] Run it: `uv run python scripts/gen_qc_baseline.py`. Inspect the JSON: 4 worlds x
      3 digests, all distinct.
- [ ] Write the identity test in `tests/test_qc_regression.py`:

      ```python
      """D-QC-1 regression anchors: the quarterly clock must not move a single
      bit of the annual era.

      The fixture was generated by scripts/gen_qc_baseline.py from the
      PRE-CHANGE code (see the qc-02-server branch history: the fixture commit
      precedes every behavior change) and is never regenerated. If this file
      fails, the quarterly release changed the meaning of a stored annual
      session -- that is a defect in the release, never a reason to re-pin.
      """

      from __future__ import annotations

      import json
      from pathlib import Path

      import pytest

      from scripts.gen_qc_baseline import ANNUAL_DECISIONS, WORLDS, _paths, tape_digest
      from ah.play import simulate_play

      FIXTURE = Path(__file__).parent / "fixtures" / "qc" / "annual-era-baseline.json"


      @pytest.fixture(scope="module")
      def baseline() -> dict:
          return json.loads(FIXTURE.read_text(encoding="ascii"))


      @pytest.mark.parametrize("preset", WORLDS)
      class TestAnnualEraIsBitIdentical:
          def test_flat_play_tape_is_bit_identical_to_the_annual_era_baseline(
              self, baseline, preset
          ):
              paths = _paths(preset)
              assert tape_digest(simulate_play(paths, None)) == baseline[preset]["flat_play"]

          def test_flat_play_true_basis_is_bit_identical(self, baseline, preset):
              paths = _paths(preset)
              got = tape_digest(simulate_play(paths, None, use_reported=False))
              assert got == baseline[preset]["flat_play_true_basis"]

          def test_annual_decision_map_replays_bit_identically(self, baseline, preset):
              paths = _paths(preset)
              got = tape_digest(simulate_play(paths, ANNUAL_DECISIONS))
              assert got == baseline[preset]["annual_decisions"]
      ```

      Note: if `scripts` is not importable from tests in this repo's layout, mirror
      the two helper functions into the test module verbatim with a comment naming
      the script as the source of truth — check how existing tests import from
      `scripts/` first (`grep -rn "from scripts" tests/` — follow the house pattern).
- [ ] `uv run pytest tests/test_qc_regression.py -q` — green (trivially: nothing has
      changed yet). Lint clean.
- [ ] Commit: `test: pin the annual-era play tapes before the quarterly clock (QC-1 Task S1)`.

---

### Task S2: the window grid — `quarterly_decision_months`

**Files:**
- Edit: `src/ah/core/institution.py` (ADD one function; nothing else in the file moves)
- Create: `tests/test_qc_windows.py`

**Interfaces:**
- `quarterly_decision_months(nm: int) -> list[int]` — every quarter-close month
  (`3q + 2 < nm`) EXCEPT the last one. Decade: `[2, 5, ..., 116]`, 39 entries.

**Steps:**

- [ ] Add to `src/ah/core/institution.py`, directly below `decision_months`
      (line 90-92):

      ```python
      def quarterly_decision_months(nm: int) -> list[int]:
          """Quarterly decision points (D-QC-1): every quarter-close month except
          the horizon's final one.

          Quarter q (0-based) closes on month ``3*q + 2``. The LAST quarter-close
          is the horizon's final tick -- a decision taken there can affect
          nothing, so it is not a window (the same reasoning that gives
          :func:`decision_months` 9 windows, not 10). For the 120-month decade:
          months 2, 5, ..., 116 -- 39 windows.

          :func:`decision_months` above is NOT superseded. It remains (a) the toy
          institution's own annual grid (``simulate_institution``, the bundle's
          twin, the feed's board packs, density/tournament/re-cone -- Step-5
          research sealed on the annual definition) and (b) the platform's
          VINTAGE-YEAR grid: ``CommitmentPlan`` carries one entry per year-close
          window and the engine fires one vintage per year, unchanged.
          """
          closes = list(range(2, nm, 3))
          return closes[:-1]
      ```

- [ ] Write `tests/test_qc_windows.py`:

      ```python
      """D-QC-1 acceptance criterion 1: the quarterly window grid."""

      from __future__ import annotations

      import pytest

      from ah.core.institution import decision_months, quarterly_decision_months


      class TestQuarterlyGrid:
          def test_decade_grid_is_the_39_quarter_closes(self):
              got = quarterly_decision_months(120)
              assert got == list(range(2, 117, 3))
              assert len(got) == 39

          @pytest.mark.parametrize("nm", [12, 60, 118, 120, 240])
          def test_final_quarter_close_is_never_a_window(self, nm):
              closes = [m for m in range(nm) if m % 3 == 2]
              got = quarterly_decision_months(nm)
              assert got == closes[:-1]
              assert closes[-1] not in got

          @pytest.mark.parametrize("nm", [0, 1, 2, 3, 5])
          def test_horizons_too_short_for_a_meaningful_window_are_empty(self, nm):
              # one quarter-close or none: that close is the final tick, so no window
              assert quarterly_decision_months(nm) == []

          def test_year_closes_are_a_subset_and_are_the_annual_grid(self):
              q = quarterly_decision_months(120)
              assert [m for m in q if m % 12 == 11] == decision_months(120)

          def test_every_window_has_a_full_following_quarter(self):
              # criterion 2's precondition: window m governs months m+1..m+3,
              # which must exist inside the horizon
              for nm in (120, 240):
                  assert all(m + 3 < nm for m in quarterly_decision_months(nm))

          def test_annual_grid_is_untouched(self):
              # the toy/vintage grid must not have moved with this release
              assert decision_months(120) == [12 * y - 1 for y in range(1, 10)]
      ```

- [ ] `uv run pytest tests/test_qc_windows.py -q` green; lint clean; full quick suite
      spot-check `uv run pytest tests/test_institution.py -q` (if present) untouched.
- [ ] Commit: `feat: quarterly_decision_months - the 39-stop grid beside the annual one (QC-1 Task S2)`.

---

### Task S3: the session store — stamped windows and stamped version

**Files:**
- Edit: `src/ah/store/db.py`
- Edit: `src/ah/store/sessions.py`
- Edit: `tests/test_sessions.py` (new tests only in this task; migration is Task S7)

**Interfaces:**
- `create_session(..., decision_windows: list[int] | None = None,
  play_alpha_version: str | None = None)` — both stored verbatim; `None` = legacy.
- Every doc returned by the store carries `doc["decision_windows"]: list[int]` —
  materialized in `_row_to_doc` (stored list if present, else
  `decision_months(doc["months"])`), so every consumer reads ONE field and legacy
  rows resolve to the annual grid automatically.
- Every doc carries `doc["play_alpha_version"]: str | None` (raw column; the legacy
  fallback to frozen literals is the SERVICE's job — Task S5 — because the store does
  not know the world's engine).

**Steps:**

- [ ] `src/ah/store/db.py`: extend `_SESSION_STAMPS` (line 115) — the established
      additive-column pattern; old rows read back NULL:

      ```python
      # D-QC-1 (qc-02-server): the session's own decision-window months (JSON
      # int list) and the play-alpha version it scores under, both stamped at
      # creation. NULL on rows written before this change means the ANNUAL era:
      # such sessions resolve to decision_months(months) and to the frozen
      # legacy alpha stamps (ah.serve._LEGACY_PLAY_ALPHA) -- they replay and
      # rank exactly as they always did.
      _SESSION_STAMPS = (
          ("rationale_schema_version", "TEXT"),
          ("opening_book", "TEXT"),
          ("commitment_plan", "TEXT"),
          ("decision_windows", "TEXT"),
          ("play_alpha_version", "TEXT"),
      )
      ```

- [ ] `src/ah/store/sessions.py`:
      - `create_session` gains the two keyword params; the INSERT gains the two
        columns (`json.dumps(decision_windows)` when not None, else None; the version
        string verbatim).
      - `_row_to_doc` materializes the windows:

        ```python
        def _row_to_doc(row: sqlite3.Row) -> dict[str, Any]:
            doc = dict(row)
            doc["decisions"] = json.loads(doc["decisions"])
            doc["window_log"] = json.loads(doc["window_log"])
            doc["ranked"] = bool(doc["ranked"])
            # D-QC-1: the session's own window grid. Stored (quarterly era) or
            # derived from the annual definition (legacy NULL) -- ONE field,
            # every consumer reads it, no consumer re-derives the grid.
            stored = doc.get("decision_windows")
            doc["decision_windows"] = (
                json.loads(stored) if stored else decision_months(doc["months"])
            )
            return doc
        ```

      - The three invariant readers switch from `decision_months(doc["months"])` to
        `doc["decision_windows"]`: `_reveal_ceiling` (line 133), `record_decision`
        (line 201), `complete_session` (line 249). The invariants themselves
        (monotonic pointer, ceiling one past the earliest undecided window, decisions
        final and in order) do not change by a word.
- [ ] Add to `tests/test_sessions.py` (tmp-db pattern the file already uses):

      ```python
      class TestQuarterlyStamping:
          """D-QC-1: windows and version are stamped at creation; NULL is legacy."""

          def test_stamped_windows_govern_the_session(self, conn, run_id):
              from ah.core.institution import quarterly_decision_months

              windows = quarterly_decision_months(120)
              doc = ss.create_session(
                  conn, run_id=run_id, months=120,
                  decision_windows=windows, play_alpha_version="port-v7-quarterly",
              )
              assert doc["decision_windows"] == windows
              assert doc["play_alpha_version"] == "port-v7-quarterly"
              sid = doc["session_id"]
              # the first stop is month 2: the ceiling holds there
              with pytest.raises(ss.SessionError, match="undecided"):
                  ss.advance_reveal(conn, sid, 4)
              ss.advance_reveal(conn, sid, 3)
              # decisions go in window order, quarterly
              with pytest.raises(ss.SessionError, match="in order"):
                  ss.record_decision(conn, sid, month=5, action="hold")
              ss.record_decision(conn, sid, month=2, action="hold")

          def test_legacy_null_row_resolves_to_the_annual_grid(self, conn, run_id):
              from ah.core.institution import decision_months

              doc = ss.create_session(conn, run_id=run_id, months=120)
              assert doc["decision_windows"] == decision_months(120)
              assert doc["play_alpha_version"] is None
              # the legacy game is untouched: month 11 is still the first stop
              ss.advance_reveal(conn, doc["session_id"], 12)
              ss.record_decision(conn, doc["session_id"], month=11, action="derisk")

          def test_complete_requires_every_stamped_window(self, conn, run_id):
              from ah.core.institution import quarterly_decision_months

              windows = quarterly_decision_months(120)
              doc = ss.create_session(
                  conn, run_id=run_id, months=120,
                  decision_windows=windows, play_alpha_version="port-v7-quarterly",
              )
              sid = doc["session_id"]
              for m in windows:
                  ss.advance_reveal(conn, sid, m + 1)
                  ss.record_decision(conn, sid, month=m, action="hold")
              ss.advance_reveal(conn, sid, 120)
              assert ss.complete_session(conn, sid)["status"] == "completed"
      ```

      (Match the file's actual fixture names for `conn`/`run_id` — read the module
      header before writing; do not invent a second fixture pattern.)
- [ ] `uv run pytest tests/test_sessions.py -q` — the NEW tests green; pre-existing
      tests in this file are untouched and still green (the store's default path is
      unchanged: no caller passes the new params yet).
- [ ] Lint clean. Commit:
      `feat: sessions stamp decision_windows + play_alpha_version at creation; NULL is the annual era (QC-1 Task S3)`.

---

### Task S4: the simulator — per-sleeve last-edit-wins across the forming year, and the stance proof

**Files:**
- Edit: `src/ah/play.py`
- Edit: `src/ah/annotations.py`
- Edit: `tests/test_qc_regression.py` (add the criterion-2/3 tests)

**Interfaces:**
- `simulate_play` signature UNCHANGED. Its decision-application loop
  (`play.py:879`, `month == q * 3 - 1`) is already month-keyed and quarter-generic —
  a decision at month 2 already lands at the start of quarter 1 (months 3–5). Only
  the commitment-override read (`play.py:913-921`) generalizes.
- `window_contributions_play(..., windows: Sequence[int] | None = None)` — `None`
  keeps `decision_months(paths.months)` (legacy callers byte-identical); the service
  passes the session's stored windows.

**Steps:**

- [ ] In `simulate_play`, replace the override read (currently lines 913-921):

      ```python
      # BEFORE (annual-era single-month read):
      #   override = decisions.get(q * 3 - 1)
      #   override_pts = override.get("commitments") if isinstance(override, Mapping) else None
      #   ... float(override_pts[asset]) if override_pts is not None and asset in override_pts ...

      # AFTER -- D-QC-1: the vintage-year figure is the PER-SLEEVE last edit
      # across the forming year's windows (the four quarter-closes feeding this
      # commitment event: months q*3-10, q*3-7, q*3-4, q*3-1), else the plan
      # pace. An annual-era decision map carries commitments only at q*3-1, so
      # this merge reduces to exactly the old single-month read -- pinned
      # bit-identical by tests/test_qc_regression.py's committed baseline.
      override_pts: dict[str, float] = {}
      for m in (q * 3 - 10, q * 3 - 7, q * 3 - 4, q * 3 - 1):
          d = decisions.get(m)
          pts = d.get("commitments") if isinstance(d, Mapping) else None
          if pts is not None:
              for asset_key, value in pts.items():
                  override_pts[asset_key] = float(value)
      for asset in PRIVATE_ASSETS:
          plan_amount = targets[asset] * _ANNUAL_COMMITMENT_RATE * multiplier
          amount = override_pts.get(asset, plan_amount)
          _commit_new_vintage(portfolio, ladders, base_doc, asset, q // 4, amount)
          committed_this_quarter += amount
      ```

- [ ] `window_contributions_play` (line 1095): add the parameter and thread it:

      ```python
      def window_contributions_play(
          paths, decisions, *, use_reported=True, policy=None,
          start_targets=None, opening_book=None,
          windows: Sequence[int] | None = None,
      ) -> PlayAttribution:
          ...
          # D-QC-1: the session's OWN window grid; None keeps the annual
          # definition for every caller that predates the quarterly clock.
          months_list = list(windows) if windows is not None else decision_months(paths.months)
      ```

      (Add `Sequence` to the existing `collections.abc` import.)
- [ ] Bump the stamp with its lineage comment (`play.py:99`):

      ```python
      # port-v7: the quarterly clock (D-QC-1, AM-2026-08-20-001, 2026-08-20) --
      # 39 quarterly-effective stances and a revisable vintage-year commitment
      # are a different definition of decision skill than 9 annual stances, so
      # the stamp moves and old rows keep their own boards. The engine did NOT
      # change (TOY_ENGINE_VERSION stays): a stored annual decision map replays
      # bit-identically (tests/test_qc_regression.py); only what a NEW session
      # can do moved. (v6 was skipped on the toy lineage so both planes align
      # at v7; the gen stamp moves in the same release.)
      PLAY_ALPHA_VERSION = "port-v7-quarterly"
      ```

      And `src/ah/port/adapter.py:151`: `GEN_PLAY_ALPHA_VERSION = "port-v7-quarterly-gen"`
      with a matching one-paragraph comment citing D-QC-1 (distinct values, never a
      shared bump).
- [ ] `src/ah/annotations.py` — the flinch-cost indexing becomes era-agnostic. In
      `post_game_annotations`: delete the module-grid lookup
      (`windows = decision_months(paths.months)` at line 66 and
      `window = windows.index(month) if month in windows else None` at line ~105) and
      gate the flinch block on the LOCK:

      ```python
      # D-QC-1: the flinch cost prices the LOCKED vintage-year figure, so it
      # fires only at year-close windows (months 12k+11 -- every annual-era
      # window was one, so the legacy behaviour is unchanged; a quarterly
      # mid-year revision is not a lock and produces no flinch note). The plan
      # index is the vintage ordinal month // 12 -- identical to the old
      # windows.index(month) on the annual grid.
      if commit_pts is not None and month % 12 == 11:
          window = month // 12
          ...  # existing body, with `window` bound as above and the same
               # all(window < len(commitment_plan.points[a]) ...) guard
      ```

      Remove the now-unused `decision_months` import if nothing else in the module
      uses it (check `annotations.py:66` was the only site; line 26 import).
      NOTE: `post_game_annotations` also calls `window_contributions_play` — pass
      `windows` through by adding the same optional parameter to
      `post_game_annotations` and forwarding it (default `None`; the service passes
      the session's windows in Task S5).
- [ ] Add to `tests/test_qc_regression.py`:

      ```python
      class TestQuarterlySemantics:
          """D-QC-1 acceptance criteria 2 and 3, at the simulator layer."""

          def test_stance_at_a_window_governs_exactly_the_following_quarter(self):
              paths = _paths("stagflation")
              base = simulate_play(paths, None)
              early = simulate_play(paths, {2: "derisk"})
              # quarter 0 (months 0-2) closed before the decision: untouched
              assert tape_digest_one(early.quarters[0]) == tape_digest_one(base.quarters[0])
              # quarter 1 (months 3-5) is the governed quarter: the 10pt shift
              # moved the liquid book
              assert early.quarters[1].liquid_values != base.quarters[1].liquid_values
              # the same stance one window later starts one quarter later
              late = simulate_play(paths, {5: "derisk"})
              assert tape_digest_one(late.quarters[1]) == tape_digest_one(base.quarters[1])
              assert late.quarters[2].liquid_values != base.quarters[2].liquid_values

          def test_untouched_year_locks_at_plan(self):
              # all-hold quarterly decisions == flat play, bit-identical:
              # hold trades nothing and an untouched figure is the plan figure
              paths = _paths("stagflation")
              from ah.core.institution import quarterly_decision_months

              holds = {m: "hold" for m in quarterly_decision_months(paths.months)}
              assert tape_digest(simulate_play(paths, holds)) == tape_digest(
                  simulate_play(paths, None)
              )

          def test_last_edit_wins_at_the_year_close(self):
              paths = _paths("stagflation")
              # an edit at the year's FIRST window, untouched afterwards, locks
              # at that figure...
              q1_edit = simulate_play(
                  paths, {14: {"action": "hold", "commitments": {"pe": 5.0}}}
              )
              at_close = simulate_play(
                  paths, {23: {"action": "hold", "commitments": {"pe": 5.0}}}
              )
              # ...and is indistinguishable from the same figure entered at the
              # close itself: the lock is the figure, not the keystroke's month
              assert tape_digest(q1_edit) == tape_digest(at_close)
              # a LATER revision inside the same year supersedes the earlier one
              revised = simulate_play(
                  paths,
                  {
                      14: {"action": "hold", "commitments": {"pe": 5.0}},
                      20: {"action": "hold", "commitments": {"pe": 2.0}},
                  },
              )
              final_only = simulate_play(
                  paths, {20: {"action": "hold", "commitments": {"pe": 2.0}}}
              )
              assert tape_digest(revised) == tape_digest(final_only)
              # sleeves are independent: a pe edit at Q1 and a pc edit at Q3
              # both survive to the lock
              two_sleeves = simulate_play(
                  paths,
                  {
                      14: {"action": "hold", "commitments": {"pe": 5.0}},
                      20: {"action": "hold", "commitments": {"pc": 1.0}},
                  },
              )
              both_at_close = simulate_play(
                  paths,
                  {23: {"action": "hold", "commitments": {"pe": 5.0, "pc": 1.0}}},
              )
              assert tape_digest(two_sleeves) == tape_digest(both_at_close)
      ```

      `tape_digest_one` is `tape_digest`'s per-quarter form — add it beside the
      existing helper (canonical JSON of `quarter_doc(q)`, same hashing).
- [ ] Run the WHOLE regression file: `uv run pytest tests/test_qc_regression.py -q`.
      The Task-S1 baseline tests MUST still pass against the committed fixture — this
      is the moment R-3 is discharged or the task is wrong.
- [ ] `uv run pytest tests/test_play.py tests/test_play_linkage.py tests/test_annotations.py -q`
      — existing suites green (the merge is behavior-identical on annual maps; the
      annotations change is behavior-identical on annual maps). The two version-stamp
      constants moved: `grep -rn "port-v5-inflation\|port-v6-chosen-pe-gen" tests/ src/`
      and fix any test asserting the OLD live constant (assertions on the frozen
      legacy literals in serve's fallback map are correct and stay).
- [ ] Lint clean. Commit:
      `feat: vintage-year commitment merges per-sleeve last-edit-wins; play-alpha v7 stamps; attribution takes the session's windows (QC-1 Task S4)`.

---

### Task S5: the service — stamping, the pending figure, the lock, the dead lever

**Files:**
- Edit: `src/ah/serve.py`
- Edit: `tests/test_serve.py` (new tests only; migration is Task S7)

**Interfaces (all internal to `ah.serve`; grep first — R-8):**
- `_alpha_version_for(ws) -> str` — the LIVE stamp for a world's engine (create-time).
- `_session_alpha_version(doc, ws) -> str` — the stamp that governs a session:
  `doc["play_alpha_version"]` if present, else the FROZEN legacy literal for the
  engine.
- `_vintage_ordinal(doc, month) -> int | None` — replaces `_window_ordinal(months,
  month)`: the CommitmentPlan index the window at `month` edits (`month // 12`), or
  `None` when `month` names no window or no vintage is forming there.
- `_pending_commitments(doc, plan: CommitmentPlan | None, month) -> dict[str, float] | None`
  — the figure currently pending at `month`'s window.
- `_plan_window(doc, entries)` — same job, now `undecided[0] // 12` (identical on the
  annual grid, where `windows.index(m) == m // 12`).

**Steps:**

- [ ] `grep -rn "_window_ordinal\|_plan_window" src tests` — confirm both are consumed
      only inside `serve.py` and its tests before renaming (R-8). Record the result in
      the commit body.
- [ ] Version resolution, top of module (after the imports):

      ```python
      #: D-QC-1: the stamp a session row WITHOUT a play_alpha_version was
      #: created under -- every session that predates the quarterly clock.
      #: FROZEN LITERALS, never the live constants: after the v7 bump the live
      #: constants name a different game, and an in-flight annual session must
      #: complete, replay and rank as annual (spec section 4.3).
      _LEGACY_PLAY_ALPHA = {
          "toy": "port-v5-inflation",
          "gen": "port-v6-chosen-pe-gen",
      }


      def _alpha_version_for(ws: WorldSpec) -> str:
          """The LIVE play-alpha stamp for this world's engine (create-time)."""
          if ws.engine_defaults.generator_id == "toy-v0":
              return PLAY_ALPHA_VERSION
          from ah.port.adapter import GEN_PLAY_ALPHA_VERSION

          return GEN_PLAY_ALPHA_VERSION


      def _session_alpha_version(doc: dict[str, Any], ws: WorldSpec) -> str:
          """The stamp that GOVERNS a session: its own, else the frozen legacy
          literal for its engine. Never the live constant for a stampless row."""
          stamped = doc.get("play_alpha_version")
          if stamped:
              return str(stamped)
          key = "toy" if ws.engine_defaults.generator_id == "toy-v0" else "gen"
          return _LEGACY_PLAY_ALPHA[key]
      ```

- [ ] `create_session` (line 575): after `months` is computed, build and pass the
      stamps:

      ```python
      ws = WorldSpec.model_validate(world)
      months = ws.horizon.quarters * 3
      ...
      return session_store.create_session(
          conn,
          run_id=body.run_id,
          months=months,
          ...,
          decision_windows=quarterly_decision_months(months),
          play_alpha_version=_alpha_version_for(ws),
      )
      ```

      Import `quarterly_decision_months` beside `decision_months` (line 42). The
      plan-shape check at line 632 KEEPS `expected = len(decision_months(months))` —
      add the comment: `# one entry per VINTAGE YEAR: the annual grid remains the
      plan's definition (D-QC-1); the quarterly grid is the STOP grid, not the
      vintage grid.` Same for the two `default_commitment_plan(...,
      windows=len(decision_months(months)))` sites (lines 135, 561) — untouched, same
      comment at `_world_book`.
- [ ] Replace `_window_ordinal` (line 305) and `_plan_window` (line 317):

      ```python
      def _vintage_ordinal(doc: dict[str, Any], month: int) -> int | None:
          """The CommitmentPlan index the window at ``month`` edits: the vintage
          year currently forming (``month // 12``), or None.

          None when ``month`` names no window of THIS session, or when no
          vintage is forming there -- the windows after the horizon's last
          year-close (months 110/113/116 on a decade) carry a stance only: the
          engine's final commitment event fired at the last year-close and
          there is no q = n_quarters commitment (play.py's ``q % 4 == 0`` loop
          ends at n_quarters - 1). On the annual grid this is exactly the old
          ``windows.index(month)``: every annual window is a year-close 12k+11,
          and 12k+11 // 12 == k.
          """
          windows = doc["decision_windows"]
          if month not in windows:
              return None
          k = month // 12
          n_vintages = sum(1 for m in windows if m % 12 == 11)
          return k if k < n_vintages else None


      def _plan_window(doc: dict[str, Any], entries: int) -> int:
          """The plan index the lever is pre-filling for: the next undecided
          window's vintage ordinal. (Docstring history from the old
          _plan_window carries over -- the ordinal is a property of the window,
          never of the reveal pointer.) Clamped exactly as before."""
          windows = doc["decision_windows"]
          undecided = [m for m in windows if str(m) not in doc["decisions"]]
          index = (undecided[0] // 12) if undecided else entries - 1
          return max(0, min(index, entries - 1))
      ```

- [ ] The pending figure — new helper below `_plan_window`:

      ```python
      def _pending_commitments(
          doc: dict[str, Any], plan: CommitmentPlan | None, month: int
      ) -> dict[str, float] | None:
          """The vintage-year figure pending at ``month``'s window (D-QC-1).

          Starts from the stored plan's entry for the forming vintage (or empty
          for a session with no stored plan -- the pacing rule remains that
          session's baseline, applied by the engine at the lock), overlaid by
          the commitments the player recorded at EARLIER windows of the same
          vintage year -- per sleeve, last edit wins, the exact merge
          ``simulate_play`` applies at the commitment event. None when no
          vintage is forming at ``month``.
          """
          window = _vintage_ordinal(doc, month)
          if window is None:
              return None
          pending: dict[str, float] = (
              {}
              if plan is None
              else {
                  sleeve: float(points[window])
                  for sleeve, points in plan.points.items()
                  if window < len(points)
              }
          )
          for m in sorted(int(k) for k in doc["decisions"]):
              if m // 12 == month // 12 and m < month:
                  d = doc["decisions"][str(m)]
                  pts = d.get("commitments") if isinstance(d, dict) else None
                  for sleeve, value in (pts or {}).items():
                      pending[sleeve] = float(value)
          return pending
      ```

- [ ] `decide()` (line 896) — three changes, in this order inside the endpoint:

      1. **The dead lever refuses loudly.** Before the fill block:

         ```python
         if body.commitments and _vintage_ordinal(doc, body.month) is None:
             raise HTTPException(
                 status_code=422,
                 detail=(
                     f"month {body.month}: no vintage year is forming at this "
                     "window (the last vintage locked at the final year-close); "
                     "the commitment lever is stance-only here"
                 ),
             )
         ```

      2. **The fill happens at the LOCK, from the pending figure.** Replace the
         `stored_plan` fill block (lines 913-922):

         ```python
         # D-QC-1: the lock. At a year-close window the figure that will drive
         # the vintage is resolved HERE, on the authority -- the pending figure
         # (stored plan overlaid by this year's earlier edits; empty base for a
         # no-plan session) under the sleeves the player sent now. Mid-year
         # windows store exactly what the player edited (sparse): a revision,
         # not a lock. Every annual-era window was a year-close, so legacy
         # sessions keep today's fill behaviour to the byte.
         if body.month % 12 == 11:
             stored_plan = doc.get("commitment_plan")
             plan = (
                 CommitmentPlan.model_validate_json(stored_plan) if stored_plan else None
             )
             pending = _pending_commitments(doc, plan, body.month)
             if pending is not None and (pending or commitments):
                 commitments = {**pending, **(commitments or {})}
         ```

         (Note the guard `pending or commitments`: a no-plan session with no edits
         all year keeps `commitments=None`, so the engine paces at the lock exactly
         as today — the annual-era no-plan path stays byte-identical.)
      3. The existing bounds check (`validate_commitments` against `_policy_basis`)
         is unchanged and now also covers the filled/merged map — same as today.
- [ ] `_mark_to_market` (line 671) — the served pre-fill becomes the pending figure:
      replace the `stored_plan` display block (lines 808-817) with:

      ```python
      # D-QC-1: the lever pre-fills with the PENDING vintage-year figure at the
      # next undecided window -- the stored plan's entry overlaid by this
      # year's earlier edits (plan sessions), or the pacing pre-fill overlaid
      # by this year's edits (no-plan sessions). None past the last year-close:
      # no vintage is forming, the lever hides.
      windows_ = doc["decision_windows"]
      undecided = [m for m in windows_ if str(m) not in doc["decisions"]]
      next_month = undecided[0] if undecided else None
      stored_plan = doc.get("commitment_plan")
      plan_doc = CommitmentPlan.model_validate_json(stored_plan) if stored_plan else None
      pending = (
          _pending_commitments(doc, plan_doc, next_month) if next_month is not None else None
      )
      if next_month is None or _vintage_ordinal(doc, next_month) is None:
          doc["plan_pace"] = None
          doc["next_plan_commitments"] = None
          doc["next_plan_basis"] = None
      elif plan_doc is not None:
          doc["plan_pace"] = doc["next_plan_commitments"]
          doc["next_plan_commitments"] = {
              sleeve: round(v, 4) for sleeve, v in (pending or {}).items()
          }
          doc["next_plan_basis"] = None  # nothing is being approximated
      elif pending:
          # no-plan session with a mid-year revision on record: the pacing
          # pre-fill (already in doc["next_plan_commitments"], with its F4
          # basis) shows the player's own pending edits on top -- what an
          # untouched lock would actually commit.
          doc["next_plan_commitments"] = {
              **doc["next_plan_commitments"],
              **{sleeve: round(v, 4) for sleeve, v in pending.items()},
          }
      ```

      This block REPLACES both the old `stored_plan` block and (for the None case)
      overrides the earlier pacing pre-fill; it runs in both the `revealed < 3` early
      path and the marked path — place it just before each `return doc` or refactor
      the tail so it runs once (implementer's choice; state it in the commit body).
      `_plan_window` remains used only if some caller still needs the clamped index —
      if this refactor leaves it dead, DELETE it and its tests rather than keeping a
      corpse (grep first).
- [ ] `get_session` (line 826): delete the
      `doc["decision_windows"] = decision_months(doc["months"])` line — the store
      materializes the field now, and this line would OVERWRITE a quarterly session's
      stored grid with the annual one (found at plan time; it is the one line that
      would silently break everything). Every session-returning endpoint now carries
      `decision_windows` because the store put it there (create included — verify in
      the test below).
- [ ] `outcome` (line 1007) and `cio_view` (line 832): replace the `_resolve_engine`
      alpha with the session's own stamp:

      ```python
      paths, targets, _live_alpha = _resolve_engine(ws, nw, rec["seed"])
      alpha_version = _session_alpha_version(doc, ws)
      ```

      and thread the windows into the attribution and annotations:

      ```python
      attribution = window_contributions_play(
          paths, decisions, use_reported=use_reported, start_targets=targets,
          opening_book=book, windows=doc["decision_windows"],
      )
      ...
      annotations = post_game_annotations(
          paths, decisions, use_reported=use_reported, start_targets=targets,
          opening_book=book,
          commitment_plan=(
              CommitmentPlan.model_validate_json(stored_plan) if stored_plan else None
          ),
          windows=doc["decision_windows"],
      )
      ```

- [ ] New tests in `tests/test_serve.py`. The file's existing module-scoped
      `service` fixture (line 36) yields `(client, db, rid)` — reuse it; sessions are
      cheap rows, so each test opens its own. Add:

      ```python
      def _hold_through(client, sid: str, month: int) -> None:
          """Hold every window strictly before ``month``, then advance to
          month + 1 -- the state where ``month``'s window is open (D-QC-1)."""
          doc = client.get(f"/sessions/{sid}").json()
          for m in doc["decision_windows"]:
              if m >= month:
                  break
              if str(m) in doc["decisions"]:
                  continue  # decided before this call; decisions are final
              assert (
                  client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1}).status_code
                  == 200
              )
              assert (
                  client.post(
                      f"/sessions/{sid}/decisions", json={"month": m, "action": "hold"}
                  ).status_code
                  == 200
              )
          assert (
              client.post(f"/sessions/{sid}/advance", json={"to_month": month + 1}).status_code
              == 200
          )


      class TestQuarterlyService:
          """D-QC-1 at the HTTP layer (Task S5)."""

          def _open(self, client, rid: str, **kwargs) -> dict:
              r = client.post("/sessions", json={"run_id": rid, **kwargs})
              assert r.status_code == 201, r.text
              return r.json()

          def _open_with_default_plan(self, client, rid: str) -> tuple[dict, dict]:
              """A session carrying the served default book+plan verbatim --
              the plan-carrying shape, still digest-equal to the default."""
              default = client.get(f"/book/default?run_id={rid}").json()
              doc = self._open(client, rid, book=default["book"], plan=default["plan"])
              return doc, default

          def test_created_session_carries_the_39_windows_and_the_v7_stamp(self, service):
              client, _db, rid = service
              doc = self._open(client, rid)
              assert doc["decision_windows"] == list(range(2, 117, 3))
              assert doc["play_alpha_version"] == "port-v7-quarterly"

          def test_advance_stops_at_every_quarter(self, service):
              client, _db, rid = service
              sid = self._open(client, rid)["session_id"]
              # month 3 is one past window 2: allowed; month 4 is past an
              # undecided window: refused (the stop is the mechanic)
              assert (
                  client.post(f"/sessions/{sid}/advance", json={"to_month": 3}).status_code == 200
              )
              assert (
                  client.post(f"/sessions/{sid}/advance", json={"to_month": 4}).status_code == 409
              )

          def test_midyear_edit_is_stored_sparse_and_the_lock_fills(self, service):
              client, _db, rid = service
              doc, default = self._open_with_default_plan(client, rid)
              sid = doc["session_id"]
              # window 0 (month 2): revise pe only
              _hold_through(client, sid, 2)
              r = client.post(
                  f"/sessions/{sid}/decisions",
                  json={"month": 2, "action": "hold", "commitments": {"pe": 1.5}},
              )
              assert r.status_code == 200, r.text
              # stored SPARSE: a revision records exactly what was edited
              assert r.json()["decisions"]["2"]["commitments"] == {"pe": 1.5}
              # months 5, 8: hold, untouched; then the month-11 lock, nothing sent
              _hold_through(client, sid, 11)
              r = client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"})
              assert r.status_code == 200, r.text
              locked = r.json()["decisions"]["11"]["commitments"]
              # the year's last edit survives to the lock; untouched sleeves
              # lock at the plan's window-0 entries
              assert locked["pe"] == pytest.approx(1.5)
              assert locked["pc"] == pytest.approx(default["plan"]["points"]["pc"][0])
              assert locked["infra"] == pytest.approx(default["plan"]["points"]["infra"][0])

          def test_pre_fill_shows_the_pending_figure(self, service):
              client, _db, rid = service
              doc, default = self._open_with_default_plan(client, rid)
              sid = doc["session_id"]
              _hold_through(client, sid, 2)
              assert (
                  client.post(
                      f"/sessions/{sid}/decisions",
                      json={"month": 2, "action": "hold", "commitments": {"pe": 1.5}},
                  ).status_code
                  == 200
              )
              got = client.get(f"/sessions/{sid}").json()
              # the window at month 5 pre-fills the PENDING figure: the edit
              # for pe, the plan's window-0 entry for the untouched sleeves;
              # nothing is approximated on a plan session
              assert got["next_plan_commitments"]["pe"] == pytest.approx(1.5)
              assert got["next_plan_commitments"]["pc"] == pytest.approx(
                  round(default["plan"]["points"]["pc"][0], 4)
              )
              assert got["next_plan_basis"] is None

          def test_commitments_past_the_last_year_close_are_refused(self, service):
              client, _db, rid = service
              sid = self._open(client, rid)["session_id"]
              _hold_through(client, sid, 110)  # the first stance-only window
              r = client.post(
                  f"/sessions/{sid}/decisions",
                  json={"month": 110, "action": "hold", "commitments": {"pe": 1.0}},
              )
              assert r.status_code == 422
              assert "stance-only" in r.json()["detail"]

          def test_lever_is_hidden_past_the_last_lock(self, service):
              client, _db, rid = service
              sid = self._open(client, rid)["session_id"]
              _hold_through(client, sid, 110)
              got = client.get(f"/sessions/{sid}").json()
              assert got["next_plan_commitments"] is None
              assert got["next_plan_basis"] is None
              # the stance itself is still accepted there
              assert (
                  client.post(
                      f"/sessions/{sid}/decisions", json={"month": 110, "action": "derisk"}
                  ).status_code
                  == 200
              )
      ```

      Also add, inside the file's existing generated-world test class (the
      `gen_service` fixture, line 78):

      ```python
      def test_gen_session_stamps_the_gen_quarterly_version(self, gen_service):
          client, _db, rid = gen_service
          r = client.post("/sessions", json={"run_id": rid})
          assert r.status_code == 201, r.text
          assert r.json()["play_alpha_version"] == "port-v7-quarterly-gen"
      ```
- [ ] Lint clean; `uv run pytest tests/test_qc_regression.py tests/test_qc_windows.py tests/test_sessions.py -q`
      green. (`test_serve.py`'s pre-existing flow tests are expected RED at this
      point — they drive annual flows against now-quarterly sessions. That is Task
      S7's scope, in the same WP, before any gate. State this in the commit body.)
- [ ] Commit: `feat: the service stamps, serves and locks the quarterly windows; session-stamped alpha with frozen legacy fallback (QC-1 Task S5)`.

---### Task S6: version separation — every ranking surface, enumerated and tested

**Files:**
- Create: `tests/test_qc_versions.py`
- Edit: `src/ah/serve.py` (only if the enumeration below finds a gap — expected: none)

**The complete enumeration of ranking/score surfaces (grep-verified at plan time;
re-verify with `grep -rn "leaderboard\|alpha_version" src/ah app/src --include="*.py" --include="*.ts*" -l`):**

| Surface | Version key | Status |
|---|---|---|
| `serve.py::leaderboard` (GET `/leaderboard/{world_id}`) | `alpha_version` REQUIRED query param, SQL-filtered | already separated; test pins it |
| `serve.py::outcome` leaderboard INSERT (line 1071-1089) | now `_session_alpha_version(doc, ws)` | Task S5; test pins legacy + new |
| `store/leaderboard.py::submit_score` / `::scores` | `decision_alpha_version` required, no default | already separated by construction |
| `app/src/components/Leaderboard.tsx` via `lib/session.ts::getLeaderboard` | `alphaVersion` from `outcome.decision_alpha_version` (Play.tsx:436) | inherits the session's stamp; no change |
| `tournament.py` cohort export | `DECISION_ALPHA_VERSION` (G5-sealed, research) | untouched by this release; a test asserts the constant did not move |
| DB `leaderboard` table | `UNIQUE (world_id, seed, decision_alpha_version, participant)` | schema untouched |

No other module reads the `leaderboard` table (`grep -rn "FROM leaderboard" src/`).

**The counterfactual note (spec §4.3, discharged without an edit):**
`src/ah/eval/counterfactual.py` is window-agnostic — it scores one decision against
a supplied baseline over a re-cone ensemble and never derives a window grid. The
play surface's no-skill baseline is the hold-course twin (`simulate_play(paths,
None, ...)`), which takes no action at ANY window and therefore re-derives under
the new window set by definition; the chain-link attribution runs over the
session's own stored windows (Task S4/S5). The sealed research grid
(`gen/recone.py`'s annual re-cone, `tournament.py`, `DECISION_ALPHA_VERSION`)
stays on the annual definition it was sealed with — untouched, and the
`test_g5_research_definition_did_not_move` test below stands guard.

**Steps:**

- [ ] Write `tests/test_qc_versions.py` (the gen-plane stamp is asserted in
      `tests/test_serve.py`'s `gen_service` class — Task S5 — so this file stays on
      the cheap toy fixture):

      ```python
      """D-QC-1 acceptance criteria 4 and 5: stamps govern, boards never mix.

      A LEGACY session here is a store-layer row created WITHOUT the two new
      columns -- byte-for-byte what every pre-release session looks like. That
      shape is first-class forever: it resolves to the annual grid and to the
      frozen legacy alpha stamps, and its scores land on the annual board even
      when completed AFTER the quarterly release.
      """

      from __future__ import annotations

      import pytest
      from fastapi.testclient import TestClient
      from typer.testing import CliRunner

      from ah.cli import app as cli_app
      from ah.core.institution import decision_months
      from ah.play import PLAY_ALPHA_VERSION
      from ah.port.adapter import GEN_PLAY_ALPHA_VERSION
      from ah.serve import _LEGACY_PLAY_ALPHA, create_app
      from ah.store import leaderboard
      from ah.store import sessions as session_store
      from ah.store.db import connect

      RUNNER = CliRunner()
      pytestmark = pytest.mark.enable_socket


      @pytest.fixture(scope="module")
      def service(tmp_path_factory):
          tmp = tmp_path_factory.mktemp("qc-versions")
          db = tmp / "ah.db"
          assert (
              RUNNER.invoke(
                  cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation"]
              ).exit_code
              == 0
          )
          run = RUNNER.invoke(cli_app, ["--db", str(db), "run", "--paths", "8"])
          assert run.exit_code == 0
          return TestClient(create_app(db)), db, run.stdout.strip()


      def _finish(client, sid: str) -> dict:
          """Hold every window the session itself declares, reveal the horizon,
          complete, return the outcome."""
          doc = client.get(f"/sessions/{sid}").json()
          for m in doc["decision_windows"]:
              assert (
                  client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1}).status_code
                  == 200
              )
              assert (
                  client.post(
                      f"/sessions/{sid}/decisions", json={"month": m, "action": "hold"}
                  ).status_code
                  == 200
              )
          assert (
              client.post(
                  f"/sessions/{sid}/advance", json={"to_month": doc["months"]}
              ).status_code
              == 200
          )
          assert client.post(f"/sessions/{sid}/complete").status_code == 200
          r = client.get(f"/sessions/{sid}/outcome")
          assert r.status_code == 200, r.text
          return r.json()


      def _legacy_ranked_session(db, rid: str, participant: str) -> str:
          """A pre-release row: no decision_windows, no play_alpha_version."""
          conn = connect(db)
          try:
              doc = session_store.create_session(
                  conn, run_id=rid, months=120, ranked=True, participant=participant
              )
              return doc["session_id"]
          finally:
              conn.close()


      class TestVersionSeparation:
          def test_new_sessions_stamp_the_quarterly_version(self, service):
              client, _db, rid = service
              r = client.post("/sessions", json={"run_id": rid})
              assert r.status_code == 201, r.text
              assert r.json()["play_alpha_version"] == "port-v7-quarterly"

          def test_legacy_session_replays_and_scores_under_its_own_version(self, service):
              client, db, rid = service
              sid = _legacy_ranked_session(db, rid, "legacy-ann")
              doc = client.get(f"/sessions/{sid}").json()
              # the NULL-stamped row resolves to the annual grid...
              assert doc["decision_windows"] == decision_months(120)
              outcome = _finish(client, sid)
              # ...and scores under the frozen legacy stamp, not the live one
              assert outcome["decision_alpha_version"] == "port-v5-inflation"
              assert outcome["decision_alpha_version"] != PLAY_ALPHA_VERSION
              # nine windows in the review, not thirty-nine
              assert len(outcome["windows"]) == 9

          def test_quarterly_and_legacy_rows_never_share_a_board(self, service):
              client, db, rid = service
              conn = connect(db)
              try:
                  rec = conn.execute(
                      "SELECT world_id, seed FROM run_records WHERE run_id = ?", (rid,)
                  ).fetchone()
                  wid, seed = rec["world_id"], rec["seed"]
              finally:
                  conn.close()
              # one legacy ranked session (store-layer row) ...
              legacy_sid = _legacy_ranked_session(db, rid, "board-legacy")
              _finish(client, legacy_sid)
              # ... and one quarterly ranked session on the SAME (world, seed)
              r = client.post(
                  "/sessions",
                  json={"run_id": rid, "ranked": True, "participant": "board-q"},
              )
              assert r.status_code == 201
              _finish(client, r.json()["session_id"])

              def board(version: str) -> list[str]:
                  r = client.get(
                      f"/leaderboard/{wid}", params={"seed": seed, "alpha_version": version}
                  )
                  assert r.status_code == 200
                  return [row["participant"] for row in r.json()["rows"]]

              assert "board-legacy" in board("port-v5-inflation")
              assert "board-q" not in board("port-v5-inflation")
              assert "board-q" in board("port-v7-quarterly")
              assert "board-legacy" not in board("port-v7-quarterly")
              # the version key is REQUIRED: no query path can aggregate
              assert client.get(f"/leaderboard/{wid}", params={"seed": seed}).status_code == 422

          def test_no_ranking_surface_can_aggregate_across_versions(self, service):
              _client, db, rid = service
              conn = connect(db)
              try:
                  rec = conn.execute(
                      "SELECT world_id, seed FROM run_records WHERE run_id = ?", (rid,)
                  ).fetchone()
                  a = leaderboard.scores(
                      conn,
                      world_id=rec["world_id"],
                      seed=rec["seed"],
                      decision_alpha_version="port-v5-inflation",
                  )
                  b = leaderboard.scores(
                      conn,
                      world_id=rec["world_id"],
                      seed=rec["seed"],
                      decision_alpha_version="port-v7-quarterly",
                  )
                  assert not ({r["participant"] for r in a} & {r["participant"] for r in b})
                  with pytest.raises(leaderboard.LeaderboardError, match="required"):
                      leaderboard.submit_score(
                          conn,
                          world_id=rec["world_id"],
                          seed=rec["seed"],
                          decision_alpha_version="",
                          participant="x",
                          score=0.0,
                          created_at="2026-08-20T00:00:00+00:00",
                      )
              finally:
                  conn.close()

          def test_g5_research_definition_did_not_move(self):
              """decision_alpha_version names Step 5's SEALED research
              definition (pre-registration-g5.lock hashes decision_metrics.py);
              the quarterly clock moves the PRODUCT stamps only. If this fails,
              someone bumped the sealed constant -- that needs an amendment,
              not a fix to this test."""
              from ah.eval.decision_metrics import DECISION_ALPHA_VERSION

              assert DECISION_ALPHA_VERSION == "1.0"

          def test_frozen_legacy_literals_are_not_the_live_constants(self):
              """If this fails, someone 'simplified' the legacy fallback to the
              live constants and re-created the exact mixing defect the stamp
              column exists to prevent: a pre-release session completing after
              a future bump would score under the wrong definition."""
              assert _LEGACY_PLAY_ALPHA["toy"] == "port-v5-inflation"
              assert _LEGACY_PLAY_ALPHA["gen"] == "port-v6-chosen-pe-gen"
              assert _LEGACY_PLAY_ALPHA["toy"] != PLAY_ALPHA_VERSION
              assert _LEGACY_PLAY_ALPHA["gen"] != GEN_PLAY_ALPHA_VERSION
      ```
- [ ] `uv run pytest tests/test_qc_versions.py -q` green; lint clean.
- [ ] Commit: `test: version separation - every ranking surface enumerated; legacy sessions score as legacy (QC-1 Task S6)`.

---

### Task S7: migrate the annual-era flow tests, then the WP gate

**Files:**
- Edit: `tests/test_sessions.py`, `tests/test_serve.py`, `tests/test_serve_book.py`
  (and any other file the first red run names)

**The ONE mechanical rule** (never per-test improvisation):

1. A test that exercises the GAME FLOW (create → advance → decide → complete) is
   migrated to the quarterly grid using the session's OWN `decision_windows`. Two
   helpers already exist or arrive in S5 — extend, don't duplicate:
   `tests/test_serve.py::_play_through` (line 53) currently iterates
   `decision_months(months)`; it migrates to iterating the create response's
   `decision_windows` (its `first_commitments` rider then lands on window 0 = month
   2, which is a live vintage-year-0 window — same meaning); `_hold_through` (added
   in Task S5) covers "get me to window m". A store-layer twin of `_hold_through`
   does the same through `session_store` calls for `tests/test_sessions.py`.
2. A test that asserts LEGACY behavior (the annual grid itself, NULL-stamp
   resolution) constructs its session at the STORE layer with the new params omitted
   — that shape is first-class forever, never deprecated.
3. A test that only needs A decided window (not a specific month) uses the session's
   own `decision_windows[0]` (month 2) rather than a literal 11.
4. If a migrated test's ASSERTION was about annual specifics (e.g. "nine windows"),
   the assertion moves to the session's own `decision_windows` length — the test
   keeps testing its original invariant, on the grid the session actually has.

**Steps:**

- [ ] `uv run pytest tests/test_sessions.py tests/test_serve.py tests/test_serve_book.py -q 2>&1 | tee qc-s7-red.log`
      — enumerate every failure; classify each as rule 1/2/3/4. Anything that fits no
      rule is a FINDING (possible behavior break) — stop and characterize before
      touching it (memory: judge the judges).
- [ ] Apply the rules. Keep diffs mechanical; one commit for the migration.
- [ ] `uv run pytest tests/test_sessions.py tests/test_serve.py tests/test_serve_book.py tests/test_play.py tests/test_annotations.py tests/test_qc_windows.py tests/test_qc_regression.py tests/test_qc_versions.py -q`
      — all green.
- [ ] Full-tree lint: `uv run ruff check . --fix && uv run ruff format . && uv run pyright`
      (memory: lint BEFORE the long gate).
- [ ] The gate: `uv run python scripts/run_gate.py gate-qc-02.log` in the background;
      read the `EXIT:` line and pass count from the file. Then
      `uv run python scripts/check_gate.py gate-qc-02.log`, re-verify HEAD equals the
      stamped sha, merge `--no-ff` into `main`, push.
- [ ] Commit (pre-merge): `test: migrate annual flow tests to the quarterly grid; legacy shapes stay store-constructed (QC-1 Task S7)`.
      CHANGELOG entry for the WP: what changed, the stamp bump, the announced
      dead-lever windows, the legacy guarantees.

---

# WP QC-2 — app (branch `qc-03-app`, after QC-1 merges)

**Scope:** the app plays the quarterly game: windows from the session document,
quarterly stepping already in place, window copy, review copy, tests. Discharges
criterion 6's build half. **No client-side game logic is added** — the app mirrors
`session.decision_windows` (bookkeeping) and renders served figures.

---

### Task A1: the window source moves to the session document

**Files:**
- Edit: `app/src/lib/session.ts`
- Edit: `app/src/Play.tsx`
- Edit: `app/src/App.test.tsx`, `app/src/Play.cio.test.tsx`,
  `app/src/Play.overlay.test.tsx`

**Steps:**

- [ ] `lib/session.ts`: `decision_windows?: number[]` (line 24) becomes REQUIRED
      (`decision_windows: number[]`) — the server now materializes it on every
      session response (store-level, Task S3/S5). Add beside `planeForBasis`:

      ```ts
      /** D-QC-1: one place turns a window month into its display label.
       * Month m sits in year floor(m/12)+1, quarter floor((m%12)/3)+1. */
      export function windowLabel(month: number): string {
        return `Y${Math.floor(month / 12) + 1} Q${Math.floor((month % 12) / 3) + 1}`;
      }

      /** A year-close window locks the forming vintage (months 12k+11). */
      export function isYearClose(month: number): boolean {
        return month % 12 === 11;
      }

      /** The month the forming vintage locks at, for the window at `month`. */
      export function lockMonth(month: number): number {
        return Math.floor(month / 12) * 12 + 11;
      }
      ```

- [ ] `Play.tsx:246`: `const windows = bundle.summary.decision_months;` →
      `const windows = session?.decision_windows ?? [];` — and move/keep the
      `nextWindow` memo consistent (it already guards on `session`). The bundle's
      `summary.decision_months` is no longer read here (it remains the toy twin's
      display summary elsewhere — do not delete it from the bundle).
- [ ] `Play.tsx` copy sweep (display only, no logic):
      - `nextYear` (line 470) → `nextStop = nextWindow !== null ? windowLabel(nextWindow) : null` and
        thread through the transport title (line 518: `Play to ${nextStop}`), the
        decision-panel eyebrow (line 692: `next window · ${nextStop ?? "—"}`).
      - The rail (line 603): `annual windows — next stops at year ${nextYear}` →
        `quarterly windows — next stop ${nextStop}`.
      - The stale comment block at lines 354-369 (`DECISIONS stay annual. Moving
        them to quarterly would redefine decision_alpha...`) is REWRITTEN: that
        deferral is exactly what D-QC-1 executed — cite D-QC-1/AM-2026-08-20-001 and
        keep the history ("this comment deferred the change until the version bump
        existed; it now does").
      - `stepQuarter`'s clamp logic is already correct for quarterly stops
        (`Math.min(target, stop, months)`) — verify, don't rewrite.
- [ ] Update the three test files: fixtures that fabricate sessions gain
      `decision_windows` (quarterly grid for new-era fixtures — `Array.from({length: 39}, (_, i) => 2 + 3 * i)`;
      `Play.overlay.test.tsx:83` stops deriving it from `bundle.summary`). Tests
      asserting "annual windows" copy move to the new strings.
- [ ] `cd app && npm run typecheck && npm run test` green.
- [ ] Commit: `feat(app): windows come from the session document; quarterly stop labels (QC-2 Task A1)`.

---

### Task A2: the window UI — quarter framing and the lock sentence

**Files:**
- Edit: `app/src/components/DecisionWindow.tsx`
- Edit: `app/src/components/DecisionWindow.test.tsx`
- Edit: `app/src/Reckoning.tsx`, `app/src/Reckoning.test.tsx` (if present — check)

**Steps:**

- [ ] `DecisionWindow.tsx`:
      - Header (line 155): `Year {year} — the window is open` →
        `{windowLabel(month)} — the window is open` (import from `../lib/session`);
        the `year` prop becomes unused — remove it and fix both call sites and tests
        (grep `year=` in `Play.tsx` and the test file).
      - The `nextYear` prop → `nextStop?: string | null` (the label, not a year
        number); closed-state copy (line 162): `The decade halts at ${nextStop}, and
        one of these is committed there.`
      - The commit-lever heading (line 212): `Next year's commitments` →
        `This year's commitments` — plus the spec's exact copy (§4.4), rendered
        under the heading:

        ```tsx
        <p className="lever-lock">
          {isYearClose(month)
            ? "This year's commitment locks now."
            : `This year's commitment locks at Q4 (month ${lockMonth(month)}); until then you can revise it.`}
        </p>
        ```

      - The stance cards, `_KNOWN_ACTIONS`, the radio/commit flow: UNCHANGED (spec
        §4.1: `_KNOWN_ACTIONS` unchanged; four stances stay — spec §9 Q1).
- [ ] `Reckoning.tsx:31-37` (`annotationLine`): year phrasing gains the quarter —
      `Year ${year}, ${phrase}` → `${windowLabel(w.month)}, ${phrase}` (39 review
      lines for a quarterly session; 9 for a legacy one — the component already maps
      `outcome.windows`, no logic change).
- [ ] Tests: `DecisionWindow.test.tsx` pins BOTH lock sentences (a mid-year month,
      e.g. 14 → "locks at Q4 (month 23)", and a year-close month 23 → "locks now");
      Reckoning's test pins one `Y2 Q1, …` line.
- [ ] `cd app && npm run typecheck && npm run test && npm run build` green.
- [ ] Commit: `feat(app): quarter-framed decision window with the lock sentence; quarterly review lines (QC-2 Task A2)`.

---

### Task A3: WP close-out — live walk, feed density note, gate

**Steps:**

- [ ] Live smoke walk (server + app, per the console-walk memory rule for new
      numeric-adjacent surfaces): `uv run uvicorn ah.serve:app --port 8787` (kill any
      stale listener first — `Get-NetTCPConnection -LocalPort 8787` → `Stop-Process`;
      checking port 8000 tells you nothing), `cd app && npm run dev`, play a toy
      preset at least two full years quarter-by-quarter: verify the stop at every
      quarter, the pending figure revising mid-year, the lock sentence flipping at
      Q4, the CIO dashboard and vintage charts rendering unchanged (they are
      cadence-agnostic — verify, don't rebuild; spec §4.4), and the wire's beat
      density per quarter-step. Record observations (including the R-6 board-pack
      density verdict) in a note for QC-3's evidence doc.
- [ ] `cd app && npm run typecheck && npm run test && npm run build` green; full-tree
      lint; the gate via `run_gate.py` → `check_gate.py` → `--no-ff` merge → push.
      CHANGELOG entry.
- [ ] Commit bodies per house rule.

---

# WP QC-3 — evidence + docs (branch `qc-04-evidence`, after QC-2 merges)

---

### Task E1: the registers and the standing documents

**Files:**
- Edit: `docs/engine-realism-register.md` (ER-2)
- Edit: `CLAUDE.md`
- Edit: `docs/current/METHOD.md`, `docs/current/alternate-histories-audited.md`

**Steps:**

- [ ] ER-2 (`docs/engine-realism-register.md:188`): status stays **open**, amended —
      append to the entry (never rewrite its history):

      ```markdown
      **AMENDED 2026-08-20 (D-QC-1, partial discharge).** The PLAYER's meeting
      calendar now exists: the play surface stops at all 39 quarter-closes
      (D-QC-1, quarterly clock / annual vintages), which is the "actual policy
      moves in steps" half of this register entry as it applies to the
      allocator. What remains open, unchanged: the ENGINE's `_rate_path` is
      still a continuous monthly drift with no meeting calendar and no 25bp
      quantisation -- the world's central bank still glides. A fix there is an
      engine change (TOY_ENGINE_VERSION bump, preset world-id block move) and
      was explicitly out of D-QC-1's scope.
      ```

- [ ] `CLAUDE.md` play-surface facts, each edited in place where the current text
      states the annual game:
      - The SU-track/product-surface description and any "9 windows"/annual-decision
        phrasing → the quarterly clock (39 stops, vintages annual, lock at
        year-close), citing D-QC-1.
      - Environment gotchas: add one line — sessions stamp `decision_windows` +
        `play_alpha_version` at creation; NULL-stamped rows are the annual era and
        must keep resolving to the frozen legacy stamps in `ah.serve`
        (`_LEGACY_PLAY_ALPHA`) — never "simplify" the fallback to the live constants.
      - The ER register digest line for ER-2 gains "(partially discharged by D-QC-1:
        the player's meeting calendar exists; rate-path quantisation still open)".
- [ ] `docs/current/METHOD.md:20` ("once a year a decision window opens") and
      `docs/current/alternate-histories-audited.md:29` (the session description) →
      quarterly description: "once a quarter a decision window opens; commitments
      form annually and lock at year-close". Check `docs/current/README.md`'s
      register — if these documents are listed with a state, note the touch-up there
      per its own conventions.
- [ ] Lint (docs don't lint, but the CLAUDE.md edit must keep ASCII in any
      command-echoed text). Commit:
      `docs: ER-2 partial discharge, CLAUDE.md and the current-docs session description go quarterly (QC-3 Task E1)`.

---

### Task E2: the console walk, the evidence document, release notes

**Files:**
- Create: `docs/superpowers/specs/2026-08-20-quarterly-clock-evidence.md`
- Edit: `CHANGELOG.md`

**Steps:**

- [ ] The full walk (criterion 6): with the merged code, walk ONE FULL quarterly
      decade in the app against a live server — all 39 windows, at least one mid-year
      commitment revision left untouched to its lock, one revision revised again at
      the lock, one stance of each kind, the last three stance-only windows, complete,
      the reckoning with 39 review lines. Then `uv run ah replay` on a stored run —
      MATCH (criterion 4's replay half; the engine is untouched so this is
      confirmation, not discovery). Then `uv run ah credibility --preset stagflation
      --preset goldilocks --out credibility.html` and walk the adapter surfaces
      (console-walk memory rule). Time the outcome computation and record the number
      (R-4).
- [ ] Write the evidence doc mapping criteria 1–7 each to its test/check WITH the
      observed results (test names, gate log names, the walk record, the R-4 timing,
      the R-6 feed-density verdict, the three lock digests unchanged, the git-history
      proof for criterion 7: the S0 commit sha vs the first implementation sha).
      House style: the `2026-08-20-pe-chosen-release-evidence.md` form.
- [ ] CHANGELOG release entry for the whole clock release (the three WPs, the stamp
      bump, the dead-lever ruling, the legacy guarantees, what ER-2 still owes).
- [ ] Full-tree lint; the gate via `run_gate.py` → `check_gate.py` → `--no-ff` merge
      → push.
- [ ] Commit: `docs: quarterly-clock evidence - criteria 1-7 discharged, walk recorded (QC-3 Task E2)`.

---

## Post-release notes for the owner (carried out of scope, on the record)

1. **The last three windows are stance-only** (months 110/113/116; no vintage forms
   after the month-107 lock). The spec's "lever live at every window" is implemented
   as "live at every window of a forming vintage year"; the served pre-fill is null
   there and a posted commitment is a 422. One-line reversal if the owner prefers a
   visible-but-disabled lever with different copy.
2. **The wire's board packs remain annual** (`feed.py` — bundle-side, pre-authored,
   toy-twin content). The QC-2/QC-3 walks record whether quarterly stepping feels
   empty between year marks; re-authoring the wire is its own WP if wanted.
3. **Outcome latency** scales with windows (43 `simulate_play` runs per quarterly
   outcome). The measured number is in the evidence doc; batching is an owner call.
4. **The flinch annotation prices the lock, not the revision** — a mid-year revision
   produces no E4 note of its own; its effect appears in the locked figure and the
   window attribution. Stated in `annotations.py`'s docstring.
