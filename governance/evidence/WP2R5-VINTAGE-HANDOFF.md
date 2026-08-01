# WP2R.5 — frozen-vintage reproduction and the rolling-refresh handoff

Date: 2026-08-01. Branch `wp2r-05-vintage-handoff`.

## 1. The reproduction: G2's battery numbers re-derive bit-identically

**Claim verified:** re-running the G2 battery on the frozen campaign vintage
(`2026-07-26.1`) reproduces the numbers `G2-EVIDENCE.md` rests on.

**Method.** A pinned git worktree at `v0.2.0-g2` (merge `02ed4cc`) with its own
`uv sync` environment and junctions to the shared `data/` and `experiments/`
stores — so nothing from the live Step 2R branches could reach the run. The
verdict-bearing subset of the WP2.10 grid was re-run end to end via
`scripts/run_ablation_grid.py` into a fresh out-root: the promoted system
(`D:hier-flow-v1`, seeds 0/1/2, **retrained from the sealed training seeds**,
sampled, and judged by the sealed battery) and the benchmark
(`E:bootstrap-v1`, seeds 0/1/2). 165.8 minutes, 6/6 completed, GPU
(`--block-batch 128 --sampler-device cuda`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`),
matching the campaign's recorded configuration.

**Result.** NaN-aware structural comparison of every `battery.json` and
`summary.json` against the campaign originals (`experiments/wp210/cells/`):

| Cell | battery.json | summary.json |
|---|---|---|
| E:bootstrap-v1 s0/s1/s2 | 0 differences | 0 differences |
| D:hier-flow-v1 s0/s1/s2 | 0 differences | 0 differences |

Every metric value, band, band distance, `mc_error` and pass/fail bit agrees,
including the retrained neural cells — training determinism holds end to end,
not merely sampling determinism.

**The two benign difference families, stated so no one rediscovers them:**
1. `prereg_digest` — the campaign cells recorded the lock digest current at
   their run date; the reproduction records `v0.2.0-g2`'s
   (`sha256:99ab3f772be6…`, 33 files). The lock legitimately re-sealed between
   those dates (`AM-2026-07-31-001/-003`); the *judged inputs* are the sealed
   set both times.
2. `timings.*` — wall clock.
3. A first-pass comparator counted ~720 "differences" per cell that were all
   `nan` vs `nan` on the structurally-unavailable `10yr` tier — a comparator
   bug (`nan != nan`), not a divergence. Recorded because the wrong count was
   briefly on screen and this file is the record of what was actually true.

**Scope, stated:** `D:hier-diffusion-v1` cells were not re-run (≈4.6× flow
cost; not verdict-bearing for the promotion — diffusion returns
SHIP-BENCHMARK under the sealed rule). The ablation systems A/B/C were not
re-run for the same reason. What was re-run is exactly what `PROMOTE` rests on.

Raw outputs: `experiments/wp2r5-repro/` (gitignored, on the workstation);
this document is the committed record.

## 2. The rolling-refresh handoff

- **The "monthly cron" never stopped.** `.github/workflows/data-monthly.yml`
  has been scheduled (06:00 UTC, 2nd of month) throughout Step 2 — it runs
  against a runner-temp volume on origin and cannot touch the local store, so
  the campaign freeze was purely local (the local store was simply not
  refreshed). Nothing to re-enable; recorded so the plan's clause has a
  truthful answer.
- **Local handoff executed:** `ah data refresh --live` on 2026-08-01 wrote
  vintage `2026-08-01` (37 series fetched, 1 carried forward) and **QC
  quarantined it**: the five `french.*` series were 61 days old against their
  60-day SLA. The `current` pointer correctly did not advance and remains
  `2026-07-26.1`. This is the pipeline working, not failing — and the SLA miss
  is a calendar-phase artifact (the French library publishes with ~1-month
  lag; at a month boundary the age crests 60d; the 2026-07-26 refresh passed
  at ~56d). **Deliberately not "fixed" here:** widening `sla_days` to green
  the acceptance in the same WP that is judged by it is the conflict this
  repo's governance exists to prevent. The SLA-vs-cadence question is RFR-86,
  owner's call.
- **Gap register current:** 63 required series, 37 present, 25 COMM/manual
  awaiting delivery — and the one non-license gap is `fred.SAHMREALTIME`
  itself, which tells the quarantine story precisely: the live refresh fetched
  it in full (798 rows, 1959-12 → 2026-06 — its registered `min_start`,
  marked "unverified offline" at registration, is now verified live), wrote it
  into vintage `2026-08-01`, and the *whole vintage* quarantined on the French
  staleness — so the register honestly reports it absent, because `present`
  reads through the current pointer and quarantined data is not current data.
  It advances with the next QC-passing refresh, together with everything else
  in the vintage.
- **Campaign vintage in the model inventory:** every Step-2 component card
  already pins `training_vintage: 2026-07-26.1` (done at WP2.11); verified,
  nothing added.
