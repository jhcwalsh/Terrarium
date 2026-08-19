# ER-14 red ledger — transient, deleted in `er14-05`

The suite is legitimately red between the first mechanism commit
(`er14-02` Task M2) and the golden re-pin sweep (`er14-05` Task R4).
Changing return equations invalidates value goldens, run digests and
committed bundles across every world.

**Rules** (`docs/superpowers/plans/2026-08-18-er14-implementation.md`,
branch-strategy section):

- A failure **not** on this ledger is a **STOP** — diagnose before proceeding.
- Every WP close-out task appends its new expected-red entries and re-runs
  the full suite to confirm the failing set equals this ledger exactly.
- `er14-05` Task R4 drives the ledger to empty and **deletes this file** in
  that commit. The ledger never reaches `main`.

## Entries

Opened by `er14-02`'s WP close-out (Task M7), full-suite run logged to
`er14-02-full.log` (`EXIT: 1`, 4 failures, 0 errors, all clean
`AssertionError`s traced individually — no unexplained failure). All four
are direct consequences of the Task M3 (`re`) and Task M5 (`pe`) return-
equation changes propagating into committed goldens/fixtures; Task M6
(infra) added no new call site into `run_path`, so it contributes nothing
here.

| test id | cause | cleared by |
|---|---|---|
| `tests/test_cioview.py::test_committed_cio_fixtures_match_the_builder` | bundle-fixture — `app/fixtures/cio-sample.{reported,true}.json` embed pre-ER14 `pe`/`re` numbers (e.g. `targetPct` 17.079 -> 17.1983); the builder now legitimately disagrees | `er14-05` Task R4 |
| `tests/test_engine.py::test_golden_snapshot` | value-golden — the WP0.4 frozen digest over `run_path`'s full return set; `pe`/`re` moved | `er14-05` Task R4 |
| `tests/test_institution.py::test_golden_hold_course_final_value` | value-golden — a pinned final NAV (`GOLDEN_HOLD_FINAL`) computed from engine returns; measured 81.1366 vs pinned 80.8944 | `er14-05` Task R4 |
| `tests/test_play_linkage.py::test_default_run_is_unchanged_by_these_additions` | value-golden — a pinned `final_value` (101.5169845720086), regenerated at every prior engine/port version bump per its own docstring history; measured 106.7285 | `er14-05` Task R4 |
