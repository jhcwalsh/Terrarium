# Campaign-3 training — runbook (K4 ruled: the local RTX 3080)

*Started 2026-08-10 on the owner's "3080 — record the ruling and start
training". The ruling is AM-2026-08-10-002. Cells run STRICTLY SEQUENTIALLY
(one GPU — the measured lesson: concurrency turned a 90-minute battery into
nine hours). The sealed grid is `ablation_systems` A–F, `hier-flow-v2` the
one trained sampler (hier-diffusion does not race).*

## Stages, in dependency order

1. **L1 climate refit** — `scripts/fit_climate.py` (numpyro/JAX, CPU; defaults
   already point at the live vintage `2026-08-10.1`, seed 20260726 kept).
   **MUST pass `--exp-root experiments/campaign3`**: the exp-id is
   config+seed only (no vintage component), so the default root writes INTO
   the campaign-2 artifact directory and would overwrite the PINNED posterior
   at fit end, breaking every campaign-2 checkpoint replay. Caught before the
   write on the first launch, stopped, relaunched isolated. `--created-at` is
   required (the no-clock-reads invariant).
   → `experiments/campaign3/climate-l1-<cfg>-s20260726/climate-posterior.npz`.
   STARTED 2026-08-10 16:27 (background).
2. **L2 regimes refit** — `scripts/fit_regimes.py` (seed 20260727 kept,
   same `--exp-root experiments/campaign3` + `--created-at` discipline), after
   stage 1 completes (CPU contention, not data dependency).
3. **Campaign-3 artifact pins** — the joinery pins the L1/L2 shas
   (`assemble.py::PINNED_CLIMATE_SHA256` / `PINNED_REGIMES_SHA256`). The
   campaign-2 pins move to `CAMPAIGN2_*` names (the CAMPAIGN2_FACTOR_SET
   split, third application) and the campaign-3 shas become the live pins.
   gen/joinery is NOT lock-hashed — no re-seal.
4. **System F (har-masked)** — DONE (commit `1d76c34`, TDD): the mask is the
   row restriction it is provably equivalent to under the complete-case
   block rule; F composes exactly as D-flow differing only in checkpoint;
   flow config/space/selection/seeds verbatim; every F index resolves
   through the manifest.
5. **hier-flow-v2 training — DESIGN DECIDED, NOT YET WIRED.** The sealed grid
   names D's campaign-3 sampler `hier-flow-v2`; `hier-flow-v1` freezes as the
   campaign-2 replay surface (its DEFAULT_CHECKPOINT/pins untouched). THE
   TRAP FOUND WHILE WIRING: retraining B/C/D at campaign-3 under the
   existing manifest keys (`flow:<k>` in `configs/wp210-seed-checkpoints.json`)
   would OVERWRITE the campaign-2 entries and break B/C/D seed replays — the
   same class as the exp-root trap in stage 1. The split therefore applies to
   the whole namespace, not just the D id: a NEW campaign-3 manifest
   (`configs/campaign3-seed-checkpoints.json`), keys `hier-flow-v2:<k>`,
   `abl-b-…-flow@c3:<k>` (exact key shape at implementation), and
   `har-masked:<k>` MOVES THERE TOO (F is campaign-3-only, no collision, but
   one manifest per campaign is the rule); `systems.build` resolves
   campaign-3 ids against the campaign-3 manifest and never falls back
   silently. `hier-flow-v2` registers as its own id (subclassing the flow
   composition with `generator_id = "hier-flow-v2"`), config
   `cfg:5943f6cd2f6f1048` retrained, never re-searched; 3 training seeds =
   flow's own. WIRED (with F; traps 3+4 closed): B/C train NOTHING of their
   own — they compose the same flow checkpoints as D — so campaign-3 trains
   SIX checkpoints (v2 ×3, F ×3), evaluated across 12 neural cells; the grid
   root moved to `experiments/campaign3/grid` (at the wp210 root the resume
   logic would silently skip every A/B/C/E cell). Launch, after the pins
   stage: `uv run python -u scripts/train_ablation_seeds.py --device cuda
   --created-at <ts>`, then `uv run python -u scripts/run_ablation_grid.py
   --block-batch 128 --sampler-device cuda`.
6. **The battery grid** — `scripts/run_ablation_grid.py` pattern over the
   campaign-3 cells (~23 min/flow cell with the GPU sampler at campaign-2;
   re-measure and record). Reference computed once and reused.
7. **ABLATION.md** — DONE (CAMPAIGN3-ABLATION.md, 18/18 cells; system A fixed
   mid-grid: raw-space Gaussians -> the constraints' unconstrained
   coordinates, regression-tested). Headline: v2 pooled d = -0.137 (sd
   0.161, does NOT clear clause 1); har-masked d = -0.223 (sd 0.041, the
   ONLY system clearing the pooled beat) -- the K3 question answered sharply.
8. **The severe legs — IN PROGRESS.** Severe L1 DONE (126 min, 0 div,
   rhat 1.0030) and severe L2 DONE (0.3 min, 18/18 bands), both under
   `experiments/campaign3/`. NEXT: `scripts/run_severe_test.py` needs the
   FIFTH campaign-split adaptation before running -- its OUT_ROOT is the
   frozen wp211 record, SEVERE_CLIMATE_ARTIFACT points at the campaign-2
   severe fit (root `experiments/climate-l1-severe-…`), its FAMILIES are the
   campaign-2 co-primaries (campaign-3: flow-only v2; decide whether F poses
   the leg -- the sealed criterion says "a system that cannot pose the leg
   FAILS it", and F is a system in the sealed grid), and THE BENCHMARK'S
   SEVERE ARM IS NEW WIRING (never posable before AM-2026-08-10-001; the
   blocks-exclusion machinery exists -- test_severe_blocks -- but no
   bootstrap arm in the runner). Campaign-3 severe outputs go under
   `experiments/campaign3/severe/`.
9. **The race** — the verdict through the sealed four-clause rule computed by
   the promotion machinery (campaign2_promotion.py's successor), the K3
   demotion determination on its sealed decision-alpha terms, evidence doc
   with proxy_share_disclosure in every table, CHANGELOG, full gate, merge.

## Standing constraints

- One GPU job at a time, checkpoint after every cell, failures cost one cell.
- Nothing re-searches or re-selects: configs are the sealed selections.
- Every ensemble's lineage records device and block_batch.
- The K3 masked cell ships in the same grid, sealed before any result.
- Proxy shares reported per factor in every verdict table; equity_vol's HAR
  share separately from its VXO share.
