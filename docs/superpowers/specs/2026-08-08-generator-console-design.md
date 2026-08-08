# Generator console — watch a decade get built (design)

**Date:** 2026-08-08 · **Port:** 8797 · **Status:** approved by owner in session

## Owner decisions (2026-08-08)

1. **Both instruments, one console:** a layer-by-layer step-through of one
   decade being built, plus a live monitor of real campaign runs.
2. **The real generator:** the step-through samples `hier-flow-v1` from the
   campaign-2 checkpoints (hash-verified), never a toy stand-in.

## What it is

An internal, read-only console in the house family (hub 8795, data 8796,
**generator 8797**, build 8798, QA 8799): FastAPI + inline HTML/SVG, no build
step, no writes, served as a card on the hub. It answers two questions:

- *"What do the four layers actually produce?"* — pick a seed, watch climate,
  seasons, weather, joinery land one after another for a single decade.
- *"How is tonight's run going?"* — cells of a campaign appearing as their
  artifacts land, with timings and pass flags.

Nothing the console shows is a score; the server-authority rule is untouched.

## Feasibility facts the design leans on (verified in-repo)

- `campaign2_promotion._build_campaign_flow` shows the exact assembly: <br>
  `load_checkpoint` + hash check against `configs/campaign2-checkpoints.json`,
  `load_climate`/`load_regimes` with the WP2.7 sha pins, `campaign_source()`,
  `FlowBlockSampler(model, std, factor_names, trained_fingerprint=…,
  device=…, block_batch=…)`.
- `ah.gen.joinery.assemble` factors the pipeline per decade:
  `_DecadeFactory.prepare(m)` returns the skeleton (`sim`, `waypoints`,
  `targets`) and `factory.assemble([prep])` returns `_DecadeResult`
  (`path`, `waypoints`, `reconciliation`, `support`, `states`).
- The platform seed rule (`seed + LAYER_SEED_OFFSETS[layer] + SEED_STRIDE*m`)
  makes a single-decade rebuild **bit-identical** to the same decade inside a
  batched campaign ensemble.

**Named dependency (recorded, deliberate):** the console reads the joinery's
underscore-private per-decade classes (`_DecadeFactory`, `_DecadePrep`,
`_DecadeResult`, `_FilterScorer`'s stat helpers) read-only. A future gen
refactor may break the console; the console must never push back on the
generator. A comment in the console module and one in `assemble.py`'s
docstring... no — **`assemble.py` is NOT edited** (nothing in `ah/gen/` is);
the dependency is recorded here and in the console module only.

## Tab 1 — Build a decade (the step-through)

Controls: `seed` (int, default 0), `checkpoint` (flow:0/1/2). Months fixed at
120. POST starts a run in a background thread; the page polls
`/api/decade/{run_id}` and stages fill in as they complete (seconds apart on
CPU):

1. **Climate (L1)** — the slow-state paths from `prep.sim` / `result.states`
   (`STATE_NAMES` order) as line SVGs over 120 months.
2. **Seasons (L2)** — the regime ribbon from `waypoints.labels` (the operative
   crisis-overlaid monthly labels): 120 colored cells + a durations table.
3. **Weather (L3)** — the stitched monthly factor returns segmented at block
   boundaries (`JoineryConfig.block_months`), each block annotated with its
   conditioning regime. Stated honestly in the UI: the pipeline does not
   retain raw pre-stitch blocks, so the seams and conditioning are shown on
   the stitched stream; the stitching corrections themselves are the next
   panel.
4. **Joinery (L4)** — the waypoint targets vs delivered (annual means, spread
   bands; from `waypoints`/`reconciliation`), per-factor reconciliation
   deltas, the final decade chart, and the decade's **filter statistics**
   (skew, excess kurtosis, Hill tail index per filtered factor) with the
   plain-English caveat that accept/reject is an ensemble-relative decision —
   a single decade has statistics, not a verdict.

Same seed -> identical page. The checkpoint hash and artifact sha pins are
displayed. A run that trips any pin check dies loudly on the page.

## Tab 2 — Live runs (the monitor)

Artifact-based, no log tailing: scans `experiments/*/cells/*` under the repo
root. A cell directory without `summary.json` renders as RUNNING; with it,
DONE — showing `system_id`, `seed_index`, per-stage timings
(`timings.build_s/assemble_*/battery_s/total_s`), `criterion_bearing`,
`passed_unfiltered`. Campaign groups sorted newest-first. Page auto-refreshes
every 30s (meta refresh; no websockets). Read-only; unreadable/partial JSON
renders as UNREADABLE rather than crashing the page.

## Architecture

- `src/ah/genconsole.py` — the FastAPI app (the `dataconsole.py` shape):
  module-level `app`, `_page()` HTML helper, small SVG helpers, one background
  thread per step-through run in a bounded in-memory dict (last 8 runs kept).
- Stage runner: `build_decade(seed, checkpoint_index, on_stage)` — assembles
  the pieces exactly as `_build_campaign_flow` does, constructs
  `_DecadeFactory`, calls `prepare`/`assemble`, invokes `on_stage(name,
  payload)` after each of the four stages. Pure-computation core split from
  the app so tests drive it without HTTP.
- Hub: one `DOCS`-style card + the port table entry.
- No new dependencies. CLI-echoed strings ASCII.

## Error handling

- Checkpoint/artifact pin mismatch, missing `experiments/` checkpoints, or an
  absent catalog -> the run record carries `error` and the page shows it;
  the server never 500s on a bad run, and never falls back to a different
  checkpoint.
- The monitor treats every filesystem read as fallible (cells vanish, JSON is
  mid-write): failures render as states, not exceptions.

## Testing

- Stage runner: monkeypatched fakes for climate/regimes/sampler are NOT used —
  the real artifacts are committed and small enough; one test builds a decade
  at a fixed seed and asserts stage order, shapes (120 months, `states`
  non-empty, labels length 120), and determinism (two runs, identical
  digests). Marked with the suite's normal (non-network) discipline;
  TestClient tests use `pytest.mark.enable_socket` (the dataconsole pattern).
- Monitor: `tmp_path` fixture cells (done/running/corrupt) -> states render.
- Hub test extends the allowlist check.
- The one genuinely slow piece (flow sampling of a full decade) gets a single
  test with a small `block_batch`; if wall-clock proves unreasonable for the
  suite, the sampler-bearing test is the ONLY place a bootstrap block sampler
  substitution is allowed, with the substitution stated in the test docstring
  (the layer structure above it stays real).

## Out of scope

Editing anything in `ah/gen/`; showing scores or leaderboards; multi-decade
ensembles in the step-through (one decade is the teaching unit); WorldSpec
regime overrides (v2 candidate); authentication (internal console family).

## Work package

`genconsole-01`, branched from main after `campaign-r1-b-generator` merges
(both touch the hub allowlist). One WP: module, script-free (console only),
tests, hub card, changelog. Full gate green -> merge `--no-ff` -> push.
