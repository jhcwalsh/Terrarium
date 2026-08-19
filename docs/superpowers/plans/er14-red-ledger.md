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
| `tests/test_engine.py::test_golden_snapshot` | value-golden — the WP0.4 frozen digest over `run_path`'s full return set; `pe`/`re`/`pc` moved | `er14-05` Task R4 |
| `tests/test_institution.py::test_golden_hold_course_final_value` | value-golden — a pinned final NAV (`GOLDEN_HOLD_FINAL`) computed from engine returns; measured 81.1366 vs pinned 80.8944 | `er14-05` Task R4 |
| `tests/test_play_linkage.py::test_default_run_is_unchanged_by_these_additions` | value-golden — a pinned `final_value` (101.5169845720086), regenerated at every prior engine/port version bump per its own docstring history; measured 106.7285 | `er14-05` Task R4 |

**Reconciled by `er14-03`'s WP close-out (Task C6)**, full-suite run logged to
`er14-03-full.log` (`EXIT: 1`, same 4 failures, 0 errors, no unexplained
failure — the failing SET is unchanged from `er14-02`; only the measured
deltas shifted further, because Tasks C1-C4 (`phi_PC`, `omega_PC`,
`theta_toy`, rider R2) add three more inflation-keyed terms to the `pc`
equation on top of `er14-02`'s `re`/`pe` changes, on the same committed
goldens/fixtures. Current measured values (in place of the `er14-02`-era
numbers above, same cause/clearing-WP): `test_golden_snapshot` digest now
`45569b207d95e25aa948a646632246f354745162d3f4cf8e509831be45e51c63` (was
`61e78e609d2a360b573a641abe0c8a1eea693f8cb527ac3148419280a218d6f5` at
`er14-02` close, itself already moved off the pre-ER14 pin);
`test_golden_hold_course_final_value` measured 80.5250 vs pinned 80.8944;
`test_default_run_is_unchanged_by_these_additions` measured 106.2231 vs
pinned 101.5170; `test_committed_cio_fixtures_match_the_builder`'s reported
plane measured `targetPct 17.1157` vs the committed fixture's `17.1983` (the
`er14-02`-era number quoted above — so this fixture has now moved TWICE
off the true pre-ER14 baseline, once at `er14-02` and again here; still one
`er14-05` Task R4 regeneration clears all of it, since regeneration reads
whatever the tree produces at release time, not any intermediate number).
No new test id joined the failing set; Task M6/S1's `infra` mechanism
contributes nothing here (unwired in this WP, same as `er14-02`).

**`er14-04b`'s WP close-out (Task S9)**: `test_committed_cio_fixtures_match_the_builder`
is **CLEARED ahead of schedule** — Task S8 regenerated
`app/fixtures/cio-sample.{reported,true,decided}.json` against the tree as it
stood after Task S7 (the CIO view carrying infra), so the fixture and the
builder agree again; confirmed green in the S8 commit and again at this
close-out, not merely assumed. Removed from the "still open" set below.

The three remaining `er14-02`/`er14-03` entries (`test_golden_snapshot`,
`test_golden_hold_course_final_value`, `test_default_run_is_unchanged_by_these_additions`)
all moved AGAIN in this WP — Tasks S1 (infra joins ASSETS/REPORTED_SLEEVES)
and S3 (the twin's SLEEVES/START_MIX gain infra) both change the values
these goldens pin, on top of `er14-02`'s/`er14-03`'s own drift. Same cause,
same clearing WP (`er14-05` Task R4); current measured values recorded in
the S1/S3 commit bodies (`test_golden_hold_course_final_value` now
83.40037746399018 vs the original pin 80.8944).

No new test id joined the failing set from this WP's own changes; full-suite
confirmation is in `er14-04b-full.log` (see the S9 close-out commit).
