# app-open-02: bands everywhere, honest labels, ladder tie-out, tabbed book

> **For agentic workers:** execute task-by-task with a review after each task
> and a whole-branch review at the end (the app-open-01 pattern). Branch:
> `app-open-02-bands` off `d50bd9a`. One reviewed commit per task.

**Goal:** the reporting bands the player declares on the opening book become
visible on every surface that shows an allocation (CIO panel, CIO table,
decision windows), the CIO stops showing a hardcoded display band, labels are
spelled out, the private ladder provably ties to the book table, a ladder can
be regenerated for a new value, and the book screen stops scrolling.

**Owner's dictated list this implements (drive session 2, 2026-08-16):**
1. Bands not showing (opening book screen)
2. CIO allocation panel needs bands
3. Decision windows show bands
4. "TGT" → "Target" (and "Dev" → "Deviation")
5. Illiquid NAV ties to the targets-and-bands value + regenerate-ladder button
6. Commitment plan on its own tab; no scrolling
9. Park ranked sessions — "we're not remotely ready for that" (owner ruling
   2026-08-16; the play surface is practice-only until further notice)
10. Opening book gets three NAMED tabs: "Targets and bands" (just the
    sleeves — and rename "sleeve" → "Asset class" in player copy),
    "Historical vintages", "Cashflow projections"
11. Opening book page: a "Play" button at the top for easy move-on
12. Each historical vintage table gains a chart: stacked bar per vintage
    (paid-in + unfunded), with a line for each vintage's NAV
13. The commitment plan grows in line with the expected growth of the plan
    (the served default is currently flat by design)

## Global constraints

- The server is the authority for value and scoring (DN-3 W5). Bands REPORT,
  they never rebalance; band STATUS (ok/watch/breach) is judged server-side
  (`serve.py::_band_report`) — the app never re-derives an alert it can avoid.
- Points remain the scored truth; `usd()` is display-only.
- Player-facing copy: full capitalized names (owner rule from app-open-01).
- ASCII in anything CLI-echoed; the app may use Unicode.
- Never weaken a test. `schemas/` untouched (nothing here goes near it).
- Full gate via `scripts/run_gate.py` before merge; ruff+pyright+vitest+
  typecheck BEFORE the gate (lint-before-the-long-gate).

## Root causes found by inspection (2026-08-16, pre-plan)

- **Item 1 is a stale process, not a code defect.** The 8787 session service
  (PID 74844) started 15:38; the default-bands code landed 19:55 and merged
  21:11 (`d50bd9a`). The live `/book/default` therefore serves a book with
  `ranges=None` → empty band inputs. CLAUDE.md's serve.py gotcha, verbatim.
- **Item 2 is real and structural:** `cioview.py` line 447 sets
  `bandPct: BAND_PCT[cid]` — a hardcoded module-level dict ("declared
  display-policy input"). The book's actual ranges (entered or the ±10%
  defaults) never reach the CIO. The CIO can show a band that contradicts
  the one the player just set.
- **Item 3:** `DecisionWindow.tsx` has no band data at all. The data already
  exists client-side: `session.band_report` (server-judged, last closed
  quarter) — every decision window sits after at least three closed quarters,
  so the report is always present when a window opens on a banded book.
- **Item 5:** BookEntry's private "value" cell is already the client-side
  ladder sum; the CIO's month-0 private value comes from the engine's opening
  state. Nothing asserts they agree.
- **Item 6:** BookEntry is one long column: targets table → three vintage
  ladders → commitment plan → commit footer.

---

### Task 1 — restart the session service; verify item 1 dead (no code)

**Files:** none (operational), plus a CHANGELOG line only if a code defect
is found after all.

- Kill PID 74844 (stale, pre-merge — owner aware via this plan) and restart
  from the merged tree: `uv run uvicorn ah.serve:app --port 8787` in
  `Terrarium-narr` (branch content == main).
- Verify with a direct GET: `/book/default?run_id=<lost-decade-703-run>` —
  `book.ranges` present, 8 sleeves (no cash), each `[lo,hi]` == ±10% of that
  sleeve's target rounded per `default_band`.
- Reload the book screen in the browser: band lo/hi inputs pre-filled.
- If bands STILL missing → the fallback hypothesis is CSS (`.policy-grid`
  column count vs 7 rendered spans); diagnose before writing any fix.
- **Restart discipline for the rest of this plan:** serve.py/cioview.py
  change → kill + restart 8787 before any live check (Tasks 2 and 7).

### Task 2 — the CIO consumes the book's bands (foundation for 2+3)

**Files:** `src/ah/cioview.py`, `app/src/lib/cioView.ts`,
`app/src/components/CioDashboard.tsx`, tests
(`tests/test_cioview.py`, `app/src/lib/cioView.test.ts`,
`app/src/components/CioDashboard.test.tsx` or nearest existing).

**Contract change (the honest one):** classes gain `bandLoPct` / `bandHiPct`
(absolute weights, same `/target_total*100` conversion as `targetPct`, 4dp).
An entered band may be ASYMMETRIC and the target may sit outside it —
`serve.py::_alert_level`'s clamp rule exists for exactly this — so a single
half-width cannot represent it. `bandPct` is REMOVED, not kept alongside
(one contract; `git grep bandPct` must come back empty in app+server when
done). Consumers to update: `cioView.ts` type + validators (lines ~351/368,
rewrite the inside/outside checks on lo/hi with the clamp rule),
`CioDashboard` `alertLevel` calls, `BandBar`, the `max` row-scale expr
(line ~634), and the table's Band column → render `lo–hi` (e.g. "36.0–44.0"),
matching how the owner thinks of it ("upper and lower bands").

**Source of the numbers:** `_allocation()` gains a `ranges` argument fed from
`opening_book.ranges` when a book is present. Fallback when there is no book
or a sleeve has no range: `BAND_PCT[cid]` converted to lo/hi around target —
the dict shrinks to a fallback, its comment updated to say so. Cash: no band
(`bandLoPct`/`bandHiPct` null), validators updated to allow it.

**Tests first (TDD):** server-side — a session with an entered asymmetric
band shows exactly that band at the CIO, and a no-book view falls back;
client — validator accepts null-band cash, rejects lo>hi; alert level at a
band edge for a target-outside-band shape matches serve.py's clamp rule
(port the docstring's own example: lo=10, hi=20, target=30, weight 15 → NOT
watch just for being far from target).

### Task 3 — the CIO allocation panel renders the bands (item 2)

**Files:** `app/src/components/CioDashboard.tsx` (the front-page allocation
panel, the bar rows around lines 490–545), its test file.

- Each class bar gains a band-zone marker: a muted underlay from `bandLoPct`
  to `bandHiPct` beneath the weight bar, with the existing target tick on
  top. Alert colouring unchanged (already `alertLevel`-driven).
- The panel's little legend gains the band swatch; "TGT" here becomes
  "Target" (Task 5 sweeps the rest, but this line is being edited anyway).
- Test: a class whose weight sits outside its band-zone renders the zone at
  the correct offsets (assert on the SVG/div geometry props, not pixels).

### Task 4 — decision windows show the bands (item 3)

**Files:** `app/src/components/DecisionWindow.tsx`, `app/src/Play.tsx`
(pass-through prop), `app/src/Play.cio.test.tsx` or the overlay test file.

- When a window is OPEN, render a compact band strip: one row per sleeve in
  `session.band_report` (server's order, server's alert word — same
  non-recompute discipline as `BandPanel`, whose row shape is reused or
  extracted, not duplicated): name, weight, `lo–hi`, alert badge.
- The four action cards already state their point/dollar impact; the strip
  sits above them so "which band am I about to fix/break" is visible at the
  moment of choice. No new data, no new endpoint: `band_report` is already
  on the session document at every window.
- Closed windows (`open=false`) do not render the strip (the cockpit's
  `BandPanel` already covers between-window reading).
- Test: window open + report present → rows in server order with served
  alerts verbatim; report null (practice session, no ranges) → no strip, no
  crash.

### Task 5 — spell out the labels (item 4)

**Files:** `app/src/components/CioDashboard.tsx` (donut legend line ~541
"TGT"; table headers line ~651 "Tgt" → "Target", "Dev" → "Deviation",
"Wt" → "Weight"), any test asserting those strings.

- Owner named TGT explicitly and asked what Dev meant (answered: deviation =
  current weight − target, in points). "Wt" goes too — same rule, same
  table. "Band" stays "Band".
- Check header widths don't wrap the table at 860px min-width; widen
  `minWidth` if needed rather than abbreviating back.

### Task 6 — prove the ladder ties to the book value (item 5a)

**Files:** `tests/test_serve_book.py` or `tests/test_cioview.py` (new
assertions), `app/src/BookEntry.test.tsx` (one assertion), NO production
code unless the tie-out FAILS.

- Server truth test: for a session created with an entered book, the CIO
  month-0 `value` of each private class equals the sum of that sleeve's rung
  NAVs in the entered book (tolerance: exact float or 1e-9; find out which
  and record it).
- Client display test: BookEntry's `value-<sleeve>` cell equals the sum of
  the rung NAV inputs currently typed (it is derived state — assert the
  derivation, editing a rung NAV moves the cell).
- **If either fails, STOP and report before fixing** — a tie-out failure is
  a finding about the opening state, not a display bug to patch over.

### Task 7 — regenerate a ladder for a new value (item 5b)

**Files:** `src/ah/serve.py` (new endpoint), `src/ah/play.py` (no change
expected — `default_opening_book` already scales `_seed_ladder` by target),
`app/src/BookEntry.tsx`, `tests/test_serve_book.py`,
`app/src/BookEntry.test.tsx`.

- **Server:** `GET /book/ladder?run_id=..&sleeve=pe&value=12.5` → the rungs
  `_seed_ladder` produces for that sleeve at that total (the SAME builder as
  the default book — never a second implementation), 422 on unknown sleeve
  or value <= 0. Deterministic: same inputs, same rungs.
- **Client:** each ladder header gains a small value input + "Rebuild ladder"
  button beside the existing Reset; on response the sleeve's rungs are
  replaced wholesale and the targets-table value cell moves to the new sum.
- **Ruling to carry (not to change):** a rebuilt ladder is still an EDITED
  book → the session demotes to practice-only, per su-app-07/ER-15. That is
  correct today: the demotion guards the un-converged-appraisal/off-shape
  risk. But a ladder built by the server's own seeder at a new total is BY
  CONSTRUCTION on the fitted staggered shape — making server-built ladders
  ranked-eligible is a real option and the OWNER'S call. Flag it in the
  commit body; do not implement it here. (Mooted in practice by item 9 —
  ranked is parked — but the ruling stays on the books for its return.)
- Tests: endpoint determinism + scaling (sum of NAVs == requested value at
  the seeder's own rounding); 422 arms; client replaces rungs and re-derives
  the value cell; an untouched book still posts ranked.

### Task 8 — tab the book screen, "Play" at the top (items 6, 10, 11)

**Files:** `app/src/BookEntry.tsx`, `app/src/styles.css`,
`app/src/BookEntry.test.tsx`.

- Three tabs, the OWNER'S names (item 10 supersedes this plan's first
  draft): **Targets and bands** / **Historical vintages** / **Cashflow
  projections**. Default tab: Targets and bands, holding just the
  asset-class table. The vintage ladders live on Historical vintages; the
  commitment plan on Cashflow projections.
- Player-copy rename on this screen: "sleeve" → "Asset class" (column head
  `sleeve` → "Asset class", section copy "Private sleeves'" → "Private
  asset classes'", aria-labels may keep their keys — flagged judgment
  carried from app-open-01).
- **"Play" at the top (item 11):** the primary commit control moves to a
  top action bar — a button labeled "Play" that does exactly what the
  footer commit does today (same validation gating, same POST, disabled on
  faults). The faults list stays visible beside/below it; a fault on a
  hidden tab must still show there and block. One canonical control — the
  old footer button is removed, not duplicated.
- Tab switching is display state only: no unmount-losing-edits (keep all
  three mounted, `hidden`/CSS, so input state and the derived `book` are
  untouched — and the app-open-01 grid regression tests keep their DOM).
- Tests: edits survive a tab round-trip; a ladder fault entered on tab 2
  blocks Play while tab 1 is shown and the bar names it; keyboard focus
  lands on the tab list sanely (buttons with `aria-selected`).

### Task 9 — park ranked sessions (item 9)

**Files:** `app/src/App.tsx` (the `RankedSetup` step), `app/src/Play.tsx`
(chip copy unchanged — "Practice" is now the only word it prints),
`app/src/BookEntry.tsx` (the `ranked-note`), their tests.

- **Fence, never delete** (the house rule): the app flow SKIPS the
  RankedSetup screen and always creates `ranked: false` sessions; the
  component, its tests, the server's ranked contract, the leaderboard
  store, and the digest/eligibility machinery all stay intact and green —
  re-opening ranked later is deleting one bypass, not rebuilding a feature.
- BookEntry's `ranked-note` (which currently reads "ranked is available" /
  "practice only") is reworded to a neutral practice statement while
  parked — its digest-tracking tests are UPDATED to the new copy, with the
  ruling and date in the test docstring (never weakened: the touched-flag
  behavior they pin stays pinned).
- Record the ruling in `governance/decision-register.md` at close-out.
- Tests: the flow from world pick → book → play never mounts RankedSetup;
  created sessions are `ranked: false`; RankedSetup's own component tests
  still pass untouched.

### Task 10 — vintage charts on Historical vintages (item 12)

**Files:** new `app/src/components/VintageChart.tsx` + test,
`app/src/BookEntry.tsx` (one chart per private asset class, above its
table), `app/src/styles.css`.

- Per vintage rung: a stacked bar — **paid-in** (bottom) + **unfunded**
  (top) — and a line across vintages carrying each rung's **NAV**. X axis:
  vintage index/age (the ladder is one rung per year of contractual life);
  Y: points, with the `usd()` rendering in the tooltip/labels per the $10bn
  rule.
- One axis only (paid-in/unfunded and NAV share the points scale — no dual
  axis, per the dataviz house rules); direct labels sparingly; the two
  stack segments get distinct fills with a 2px gap, the NAV line a marker
  per vintage.
- The chart re-derives from the CURRENT rung inputs (edit a rung → the bar
  moves), same derivation discipline as the value cell; it renders from
  the entered book only — no fetch.
- Tests: geometry from a known 3-rung fixture (bar heights proportional to
  paid_in/unfunded, line hits NAV values); editing a rung input moves the
  chart; a zero-NAV lapsed rung renders without crashing.

### Task 11 — the default commitment plan grows with the plan (item 13)

**Files:** `src/ah/play.py` (`default_commitment_plan`),
`src/ah/serve.py` (no change expected — it already calls the builder),
`tests/test_play.py` / `tests/test_serve_book.py`,
`app/src/BookEntry.test.tsx` (fixture refresh).

- Today's default is FLAT by design (its docstring: a non-flat schedule is
  "explicitly later work" — this task is that work arriving). The dictated
  rule: year k's commitment escalates with the plan's EXPECTED growth, so
  the programme keeps pace with a growing book instead of shrinking
  relative to it.
- **The rate must have one source.** First locate an existing declared
  expected-growth number (the CIO plan chart's forecast is flat/frozen, so
  there may be none). If none exists, STOP and ask the owner for the
  annual rate before implementing — do not invent one silently; it becomes
  a declared display-policy constant next to its kin, applied as
  `base * (1+g)^k` per window-year k.
- The engine's pacing contract is untouched (`CommitmentPlan`'s per-year
  shape already carries a non-flat schedule without a contract change —
  its own docstring says so). The entered-plan path, validation, and
  digest mechanics are unchanged; only the served DEFAULT points change.
- Ranked-eligibility interplay: the served default and the pre-fill move
  together, so an untouched POST still digests as the default (same Ruling
  D invariant app-open-01 preserved) — and ranked is parked anyway
  (Task 9).
- Tests: served default plan points grow at (1+g)^k exactly; POSTing the
  served default back is accepted and digests as untouched; the flat-rule
  engine invariants (`pacing_rule="fixed"` pre-quarter-0) still hold.

---

## Close-out (after Task 11)

- CHANGELOG.md: one entry per task, app-open-01 style.
- Whole-branch adversarial review (opus), findings fixed before the gate.
- ruff + pyright + `cd app && npm run typecheck && npm run test && npm run
  build` FIRST, then the full gate in background:
  `uv run python scripts/run_gate.py gate-app-open-02.log`; read the EXIT
  line and pass count; `check_gate.py` stamps; re-verify HEAD == stamp.
- Merge `--no-ff` in Terrarium-mainmerge (copy `.gate-ok` across), plain
  push (standing authorization). Restart 8787 from the merged tree —
  the same stale-server trap this plan opened with.
