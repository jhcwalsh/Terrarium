# Quarterly clock, annual vintages — design spec

**Date:** 2026-08-19 · **Status:** APPROVED by owner 2026-08-20 (ruling: quarterly clock,
annual vintages) · **Ruling being specified:**
"Yes, quarterly clock and annual vintages" (owner, 2026-08-19, after the two-cadence fork was
presented). Registers as D-QC-1 on adoption.

---

## 1. What this changes, in one paragraph

Today the game stops nine times per decade — once a year, at months 11, 23, … 107 — and each stop
carries everything at once: a stance for the whole coming year (hold / lean-in / de-risk /
secondary) and the commitment that becomes an entire vintage year. After this change the game
stops **thirty-nine times — every quarter-close from month 2 through month 116** — and each stop
carries a stance for the coming quarter plus an *editable* commitment figure for the vintage year
currently forming, which **locks at the year-close stop** (the same months 11, 23, … 107 where the
engine fires vintages today). The engine, the pacing model, the annual vintage ladder, and the
vintage charts do not change at all: four quarterly looks feed one annual commitment, exactly the
way a real investment committee revisits its pacing each quarter but still commits into vintage
years.

## 2. Why (and why these numbers)

- **Realism:** allocators act on a quarterly meeting calendar; private marks arrive quarterly; the
  platform's own institutional simulator already advances in quarters (`engine.run_quarter` —
  the annual stop was always a UI bundling, not an engine fact). This partially discharges the
  realism register's **ER-2** ("no meeting calendar").
- **Playability:** a crash year is currently one stop — the player watches 2030 destroy the book
  with no chance to act inside it. Quarterly stops make stress worlds playable as experiences
  rather than replays.
- **Why 39 stops and not 40:** quarter-closes in a 120-month decade are months 2, 5, …, 119. The
  month-119 close is the decade's final tick — a decision taken there can affect nothing, so it is
  not a window (the same reasoning that gives today's decade 9 commitment windows, not 10: a
  vintage committed at the very end has nothing left to fund). 39 = quarter-closes month 2
  through month 116 inclusive.
- **Why vintages stay annual:** the pacing curves, the contractual-life ladder (ER-12's one rung
  per year), the cap arithmetic (`1.06^8` against `COMMIT_CAP_MULTIPLE`), and the vintage charts
  are all built per vintage YEAR, matching how real programs report. Quarterly vintages would
  fragment all of it for no realism gain — real ICs decide quarterly, commit annually.

## 3. Current mechanics being changed (grounded, file-verified)

- `ah/play.py::decision_months` → 9 windows at months 11, 23, … 107; `CommitmentPlan` carries one
  entry per window; window k drives the engine's vintage year k.
- A decision is `{"action": one of hold|derisk|leanin|secondary|commit, "commitments": {sleeve: pts}}`,
  identified by the decision's OWN month (`serve.py::_window_ordinal`); an untouched lever
  auto-commits the stored plan's number server-side (DN-3 W5: the server is the authority).
- `POST /sessions/{sid}/advance` moves a monotonic capped reveal pointer to any month; the APP
  chooses the step size (currently steps year-to-year between windows).
- `decision_alpha_version` names the sealed definition of decision value-add and is stamped on
  every record; the leaderboard compares only within a version.

## 4. The design

### 4.1 Windows
- `decision_months(months)` returns every quarter-close from month 2 to month 116: 39 windows for
  a 120-month decade (the function stays general for other horizons: all quarter-closes except
  the final one).
- Every window accepts a stance action, effective for the FOLLOWING quarter (today's stance is
  effective for the following year). `_KNOWN_ACTIONS` unchanged.
- The **commitment lever is live at every window** but names the vintage year currently forming:
  editing it at a non-year-close window revises the pending figure (visible, revisable); the
  year-close windows (months 11, 23, … 107 — unchanged) are where the figure LOCKS and the engine
  fires the vintage, exactly as today. Between locks, the pending figure defaults to the stored
  commitment plan's entry for that vintage year (the auto-commit-the-plan behaviour generalises:
  an untouched pending figure locks at the plan's number).
- `CommitmentPlan` keeps its 9-entries-per-decade shape (one per vintage year). No cap-math or
  pacing change.

### 4.2 Engine and portfolio: no change
`run_quarter`, the cashflow tiers, the ladder, forced-secondary machinery, sleevestate — all
untouched. The toy and generated planes are untouched. This is a play-surface and scoring change
only. (Anything requiring an engine edit is out of scope by definition; if implementation
discovers one, stop and re-ratify.)

### 4.3 Scoring — the sealed part
39 windows with quarterly-effective stances is a DIFFERENT definition of decision skill than 9
windows with annual stances. Therefore:
- A new `decision_alpha_version` (successor name, e.g. `alpha-2026.08-q`) through the amendment
  log, same discipline as every sealed change: the definition is declared in the amendment BEFORE
  implementation lands, with the window arithmetic above quoted.
- The counterfactual/no-skill baselines (`ah/eval/counterfactual.py` conventions) re-derive under
  the new windows; their construction rule does not change, only the window set it runs over.
- **Leaderboard separation:** rows are already keyed by version; annual-era sessions stay
  readable and ranked within their own version, quarterly sessions rank within theirs. No
  migration, no deletion, no mixed rows. In-flight annual sessions complete as annual (their
  stamped version governs them to the end).

### 4.4 App
- The Play loop advances quarter-to-quarter (advance to next quarter-close, then window UI).
- `DecisionWindow` shows: the quarter's stance choice; the pending current-vintage commitment
  with one plain sentence of copy — "This year's commitment locks at Q4 (month N); until then you
  can revise it." Year-close windows say "locks now".
- The CIO dashboard, bands, and vintage charts are cadence-agnostic already (they render the
  revealed state) — verify, don't rebuild.
- The in-timeline feed (`ah/feed.py`) delivers its dispatches against the reveal pointer already;
  verify beat density per quarter-step feels right in a console walk rather than re-authoring
  the wire.

### 4.5 Determinism
No new randomness anywhere: windows are arithmetic on the calendar; stance/commitment semantics
route through existing deterministic code. Replay (`ah replay` MATCH) must stay bit-identical for
existing stored sessions (their version pins the old window set — `decision_months` becomes
version-aware or the session doc stores its window months at creation; implementation picks the
simpler, records the choice).

## 5. What this invalidates / does not

- **Invalidates nothing stored:** old sessions/records keep their stamped versions and replay
  under them. No store rebuild. No world retirement (worlds are cadence-agnostic; the same
  world_id can host annual-era and quarterly-era sessions because rows never mix versions —
  verify the leaderboard keys on (world, version) before relying on this; if a surface mixes
  them, split by version at that surface, not by retiring worlds).
- **Sealed surface touched:** decision-alpha definition only. The generator/battery/mapping seals
  are untouched. Check ALL THREE locks anyway before merge (standing rule).
- **Docs to update on land:** ER-2 register entry (partially closed: meeting calendar exists;
  25bp quantisation still open), CLAUDE.md play-surface facts, the user-guide paper's session
  description.

## 6. Alternatives considered
- **Full quarterly (vintages too)** — rejected by ruling; costs (pacing/ladder/charts rebuilt,
  cap-math re-derived) bought no realism (real programs commit annually).
- **Keep annual clock** — rejected by ruling; leaves crash years unplayable and ER-2 open.
- **Monthly clock** — not requested; 120 stops per decade is fatigue, and monthly stances would
  out-run the quarterly information cycle the game actually reveals (private marks are quarterly).

## 7. Acceptance criteria (each becomes a test or a walked check)
1. `decision_months(120)` == the 39 quarter-closes 2…116; property: never includes the final
   quarter-close; general across horizons.
2. A stance recorded at window m governs exactly months m+1 … m+3 of the institutional sim.
3. A commitment edited at any window of a vintage year and left untouched afterwards locks at
   that year's close at the last-edited figure; untouched all year locks at the plan figure —
   proven equal to today's behaviour on a no-edit session (the flat-play tape is IDENTICAL
   before/after this release under the old windows' year-close months).
4. New sessions stamp the new decision_alpha_version; old sessions replay MATCH bit-identical.
5. No leaderboard surface ever renders two versions in one ranking.
6. App: typecheck/test/build green; a full quarterly decade walked in the console/app before
   merge (the console-walk rule for new numeric surfaces).
7. Amendment entry lands BEFORE the implementation commit that changes the definition (log
   order provable from git history).

## 8. Work packages (one branch each, plan order)
- **QC-1 server:** decision_months + window semantics + version stamping + counterfactual
  re-derivation + tests (largest; touches sealed-adjacent scoring — amendment first).
- **QC-2 app:** quarterly stepping, window UI copy, feed-density verification, app tests.
- **QC-3 evidence + docs:** ER-2 update, CLAUDE.md, papers touch-up, console walk, release notes.

## 9. Open questions for the owner (each with a recommendation)
1. **Stance granularity:** today's four stances, now quarterly — sufficient? (Recommend: yes for
   this release; richer levers are their own future spec.)
2. **Mid-year commitment visibility:** should the pending figure show its revision history in the
   window UI? (Recommend: no — one current figure + lock date; history is audit-side.)
3. **Naming:** `alpha-2026.08-q` for the new decision-alpha version acceptable? (Cosmetic;
   implementer proposes, amendment fixes it.)

**Sequencing:** starts after the chosen-PE release merges (in flight now). The app-open-03
interface fixes are independent and unaffected.
