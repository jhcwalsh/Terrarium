# Campaign R1 — the 2026-08 re-run campaign (design)

**Date:** 2026-08-08 · **Owner decisions:** recorded below · **Status:** approved by owner in session

## The four scoping decisions (owner, 2026-08-08)

1. **Objective:** translation-first, plus a generator vintage-robustness refresh.
   Track A re-runs the twin/decision surface where the new PM data actually bites;
   Track B re-runs the six campaign cells from existing checkpoints as a robustness
   exhibit, not a gate.
2. **Vintage:** the campaign freezes on `2026-08-07.5` — the vintage
   AM-2026-08-08-002 already names. Everything added since (CWBDC, CP-bill legs,
   commodity price indices) is consumed by no model, so nothing is lost and no
   further amendment is spent.
3. **Seal scope:** sealed-surface changes are OUT of scope. CP-bill into
   `funding_spread` and PM series into the factor set stay documented follow-ons.
4. **PM loadings:** the scored twin keeps the priors; the measured loadings run as
   a side-by-side diagnostic. Adoption remains a named release event, not a swap
   inside a campaign.

## The framing that makes it honest

The holdout was spent at WP5.6 and the G2/G5 verdicts are historical facts. So
**every output of this campaign is an exhibit** — the `DESMOOTHING-VALIDATION.md`
pattern, outside the seals by design — and **zero seal events are planned**: no
amendments, no re-seals, no sealed artifact re-emitted, no frozen spec re-dated.
Sealed artifacts are read, never written. If any judged quantity drifts outside a
sealed band on the new vintage, that is a **finding brought to the owner** (an
ER-register-style entry), never something the campaign fixes silently.

Both locks are checked before touching any file: `pre-registration.lock` hashes
`eval/*`, `factors.py`, `splits.py`, `strategies.py`, battery and derive/splice;
`pre-registration-g3.lock` hashes `taxonomy/` and the Step-3 judged set. The new
code lives entirely outside both hashed scopes (new scripts + one new module +
report docs + hub allowlist entries).

## Track A — translation layer

**What it demonstrates:** how the institutional twin behaves under the AM-002
re-estimated artifacts (`mappings/smoothing-kernel-v1.0.yaml`,
`mappings/sleeve-mappings-v1.0.yaml`, vintage `2026-08-07.5`), and what would
change if the measured PM loadings were adopted.

**Design correction (2026-08-08, same day):** the first draft said "the four
presets over toy-v0.5 paths". That is not wireable as a re-run: the toy engine
emits asset-class returns (`equity … pe, pc, re`, `ah/core/engine.py` ASSETS)
while the mapping artifact consumes seven regressors
(`equity_mkt, smb, hml, mom, d_level, d_slope, d_ig`) — a preset-driven track
would never touch the new mappings, and bridging assets to regressors would be
new modeling, not a re-run. Track A therefore drives the twin with **observed
factor history from the campaign vintage** — the exact wiring of the G1 replay
(`run_2022_replay.py`) and the I4/I6 inspection, extended from one episode to
the full span. Deterministic end to end: observed inputs, frozen artifacts,
no RNG.

**Design.**

- New module `src/ah/port/campaign_exhibit.py` (pure, testable) + thin script
  `scripts/campaign_r1_translation.py` — the `desmooth_validation.py` +
  `validate_desmoothing.py` split.
- Windows: the full common regressor span on `2026-08-07.5`, plus the three
  named episode windows (2007-07..2009-12, 2020-01..2020-12, 2021-12..2023-12)
  reported separately.
- Observed regressor series → sleeve return paths via
  `ah.port.mapping.load_artifact()`: HF sleeves from the `sleeves:` block
  (monthly), PM sleeves from the `pm_sleeves:` block (quarterly), reported
  planes via the smoothing kernel (`ah.port.smoothing.smooth` / `theta_for`;
  Geltner family for `pm_re`/`pm_infra` per the AM-002 kernel).
- **The loadings toggle is the experiment:** `loadings_source="prior"` uses each
  PM sleeve's `prior_superseded` row (the frozen `cashflow-tier1-v1.0.yaml`
  `pm_growth_loadings` values); `loadings_source="measured"` uses the fitted
  `loadings:` row. Prior is the scored baseline; measured is the diagnostic,
  labelled **NOT ADOPTED** in every table that shows it.
- Twin loop: `Portfolio`/`PortfolioEngine`/`Policy` with a mid-life closed-end
  cohort (the committed fixture cohort), quarterly steps, the wiring of
  `scripts/run_inspection_i4_i6.py`. Per-window metrics: end NAV, max drawdown
  on the true and reported planes, calls met vs missed, forced-sale incidence,
  minimum coverage ratio, private-weight peak (denominator effect).
- **Second correction (found on the first real run):** the twin loop refuses
  windows longer than the fixture cohort's remaining contract. `full_span`
  (146 quarters) through a single non-recommitting mid-life cohort drained the
  book negative and printed drawdowns of −994% — domain artifacts, not
  results. Long spans report **sleeve-plane statistics** instead (per-sleeve
  true vs reported volatility and drawdown, prior vs measured), which is the
  adoption-relevant long-horizon content; the episode windows keep the full
  twin loop. The refusal is tested, and the report states it.
- Report `docs/data/CAMPAIGN-R1-TRANSLATION.md`: per-window summaries,
  prior-vs-measured delta tables, and a **named exclusion** section
  stating that cashflow tier-0/tier-1 remain pinned to `2026-08-01.2` and ER-6's
  `rc_curve` remains unfitted — no Albourne data arrived, unchanged by design.
- Hub `DOCS` allowlist entry so the report is served on 8795.

**Error handling.** A missing series or absent vintage is a hard `SystemExit`
naming the series and vintage — never an empty-frame fallback in an exhibit
(contrast `run_ablation_grid.catalog_access`, which is judged code with its own
contract). A preset that fails to compile fails the whole run.

**Cost:** minutes of compute.

## Track B — generator vintage-robustness

**What it demonstrates:** that the campaign-2 promotion evidence is not fragile
to the data refresh — same checkpoints, same sealed arithmetic, new vintage.

**Design.**

- New script `scripts/campaign_r1_generator.py`, mirroring
  `campaign2_promotion.py --phase battery` with the vintage passed explicitly
  (the `compute_campaign_reference.py --vintage` precedent). No sealed constant
  is edited; `CAMPAIGN_VINTAGE_ID` stays what it is.
- Checkpoints resolve through `configs/campaign2-checkpoints.json` with
  `checkpoint_hash` verified before sampling — identical to campaign-2's own
  battery phase. Systems: `bootstrap-v1` and `hier-flow-v1` (campaign-2
  checkpoints), three seeds each from `systems.SEED_PLAN` — six cells.
- Reference computed on `2026-08-07.5` with the sealed reference-run parameters;
  cells run through `run_ablation_grid.run_cell` **verbatim** (same judged code
  path); artifacts under `experiments/campaign-r1/` (gitignored, as always).
- Compare step: new cell summaries against the committed
  `artifacts/campaign2/promotion-verdict.json` — cell-by-cell metric deltas and
  sealed-band status. Rendered to `docs/data/CAMPAIGN-R1-GENERATOR.md`.
- **The guard header, verbatim in the report:** this is not a gate; it cannot
  re-judge promotion (the holdout is spent); the sealed verdicts remain the
  verdicts; the standing caveat on `hier-flow-v1` (regime persistence
  undercalled, drawdowns understated ~2x, decade tier structurally unavailable)
  carries forward unchanged.
- Hub `DOCS` allowlist entry.

**Cost:** ~3.5 h wall-clock (measured: 11 min/bootstrap cell, 23 min/hier-flow
cell; the battery is 88–99% of it). Runs in the background.

## Explicitly out of scope — each a named follow-on

- CP-bill → `funding_spread` (sealed factor; amendment + re-seal + retrain implication).
- PM series → factor set (same machinery, same implication).
- PM tail thresholds (AM-002: "need pre-registration before anyone looks").
- L3 retraining (needs the Linux/GPU host this machine doesn't have).
- Anything touching the spent holdout.

## Testing

- Module-level tests for Track A's pure helpers: the loadings toggle produces
  different PM sleeve paths and identical HF paths; determinism (same seed, same
  digest); the report renderer pins the NOT-ADOPTED label and the named-exclusion
  text.
- Track B's compare/render step is tested on synthetic cell dicts (no 3.5 h run
  in tests); the script's argument plumbing is tested pure.
- Report-presence tests pin the guard header and key claims, the
  `DESMOOTHING-VALIDATION.md` test pattern.
- No network, no new dependencies, full gate green per WP.

## Work packages

- `campaign-r1-a-translation` — Track A end to end (module, script, report, hub,
  tests, changelog).
- `campaign-r1-b-generator` — Track B end to end (script, compare module, the
  3.5 h run, report, hub, tests, changelog).

One branch per WP, merged `--no-ff` when the full gate is green, then pushed.
