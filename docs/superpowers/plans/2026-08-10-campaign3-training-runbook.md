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
4. **System F (har-masked)** — new at this seal: system D's architecture,
   hyperparameters and seeds with `equity_vol` treated as MISSING before
   1986-01 in the TRAINING data only (`ah/gen/systems.py` composition +
   dataset masking; the sealed demotion criterion lives in
   `multi_seed_decision_rule.har_masked_ablation`).
5. **hier-flow-v2 training** — the flow family retrained on the extended
   16-factor/813-month panel at the sealed campaign-2 SELECTED config
   (`cfg:5943f6cd2f6f1048` — retrained, never re-searched: the sealed trial
   budget was spent at WP2.9 and nothing here re-selects), 3 training seeds
   via `scripts/train_ablation_seeds.py`'s successor stage. B/C flow-arm
   variants likewise. 12 neural cells total (B, C, D, F × 3 seeds).
6. **The battery grid** — `scripts/run_ablation_grid.py` pattern over the
   campaign-3 cells (~23 min/flow cell with the GPU sampler at campaign-2;
   re-measure and record). Reference computed once and reused.
7. **ABLATION.md + the race** — generated, never hand-assembled; the verdict
   through the sealed four-clause rule with proxy_share_disclosure in every
   table.

## Standing constraints

- One GPU job at a time, checkpoint after every cell, failures cost one cell.
- Nothing re-searches or re-selects: configs are the sealed selections.
- Every ensemble's lineage records device and block_batch.
- The K3 masked cell ships in the same grid, sealed before any result.
- Proxy shares reported per factor in every verdict table; equity_vol's HAR
  share separately from its VXO share.
