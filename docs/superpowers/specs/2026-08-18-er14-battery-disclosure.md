# ER-14 close-out — battery re-run disclosure (AT-9)

**AT-9, verbatim from the design:** *"The validation battery re-runs on the stagflation
preset; every stylized fact that moves outside its band is disclosed in the close-out,
and no threshold is moved to accommodate it."*

This is a disclosure record, not a pass/fail gate. `src/ah/battery/thresholds.yaml` is
inside `pre-registration.lock` (the main seal) and was **not edited** — grepped before
and after this run; digest unchanged (see the WP `er14-05` Task G3 commit body for the
full three-lock verification).

## Method

`uv run python -m ah.battery.report` on the stagflation preset (64 paths x 120 months,
`active_blocks: global, us, fx, valuation`), run twice on the same branch history:

- **before**: `git checkout` to `main`'s tip (commit `4c00877`, the pre-`er14-02`
  baseline — toy-v0.6, no infra sleeve, no inflation channels), detached HEAD (a scratch
  worktree could not be used here — see the note below).
- **after**: `git checkout` back to `er14-05-release` at the commit that minted the G3
  reseal (`1c72648`) — the full ER-14 mechanism set (M2-M6, C1-C4, S1-S8, G1-G2) plus
  this WP's version/fence moves.

**Deviation from the plan's literal step ("check out `main` into a scratch worktree"):**
`main` was already checked out in another live worktree (`Terrarium-mainmerge`), so
`git worktree add` for `main` would have conflicted (git refuses two worktrees on one
branch). Used an in-place detached-HEAD checkout of `main`'s tip commit instead, in
*this* worktree, then checked back out to `er14-05-release` before continuing — no
other worktree was created or touched, and no uncommitted state existed at any point
(everything through Task G3 was already committed).

## Result

| metric | before (toy-v0.6) | after (toy-v0.7) | band | severity | moved outside? |
|---|---|---|---|---|---|
| `excess_kurtosis` | 1.644 | 1.644 | [0.5, 8.0] | enforce | no |
| `skewness` | 0.02007 | 0.02007 | [-1.5, 0.5] | enforce | no |
| `hill_tail_index` | 4.45 | 4.45 | [2.0, 6.0] | enforce | no |
| `acf_r_lag1` | 0.4111 | 0.4111 | [-0.2, 0.2] | todo (report) | no — but **pre-existing enforce-would-fail**, unchanged by this release (see below) |
| `acf_abs_lag1` | 0.3345 | 0.3345 | [0.05, 0.4] | todo (report) | no |
| `max_drawdown_median` | -0.6015 | -0.6015 | [-0.65, -0.12] | enforce | no |
| `corr_distance` | 4.133 | 4.955 | (none declared) | todo (report) | **moved, no band to be outside of** |

`enforce failures: 0` in both runs (`passed: true` in the JSON rendering, both before
and after). Chased in the sealed JSON (`render_json`), not evidence-doc prose, per the
`sealed-bands-not-prose-anchors` discipline: no `checks[].ok == false` on any
`status: enforce` row, in either run.

## What moved, and why that is expected

**Every public-asset stylized fact (`excess_kurtosis`, `skewness`, `hill_tail_index`,
`acf_r_lag1`, `acf_abs_lag1`, `max_drawdown_median`) is bit-identical before and after.**
This is not a coincidence — it is AT-6b's own guarantee (`tests/test_er14_inflation.py`),
proven independently by this run: the battery's stylized facts are computed over public
equity/bond/credit paths, and ER-14 touches only the private sleeves (`pe`, `pc`, `re`,
`infra`) plus, on the generated plane, the PM residual block. A world's public tape is
structurally untouched by every mechanism this release adds.

**`corr_distance` moved (4.133 -> 4.955).** This is the one metric that reads the full
correlation matrix across all modeled sleeves — including the private ones. Two release
changes reach it directly: the fourth private asset (`infra`) widens the matrix from
8x8 to 9x9, and the inflation channels (M3/M5/M6) change the *systematic* component of
`pe`/`pc`/`re`/`infra`'s returns, which moves their correlation with the public block and
with each other. `corr_distance` carries **no declared band** (`severity: todo`, no
`min`/`max` in `thresholds.yaml`) — it is a reported diagnostic, not an enforced
criterion, so "moved outside its band" does not apply to it literally; it is disclosed
here because it is the one number that moved at all, and AT-9 asks for exactly that.

**`acf_r_lag1` (0.4111, status `todo`, `ok: NO` in the rendered table) is unchanged
across this release** — it was already outside its declared `[-0.2, 0.2]` window before
`er14-02`'s first commit, on the pre-ER14 `main` baseline. It is a pre-existing,
already-disclosed condition (public-path lag-1 return autocorrelation, tracked
separately from this register) and this release neither creates nor worsens it; it is
listed here only because the table would be misleading without it.

## The discipline this record exists to hold

No band in `src/ah/battery/thresholds.yaml` was moved, is proposed to move, or should
move as a result of this run. If a future reader is tempted to widen `corr_distance`'s
(currently absent) band or `acf_r_lag1`'s enforce range to make a red battery run green,
that is the ER-4 mistake this document exists to name in advance: **a flag is a finding,
never something to be edited away.**
