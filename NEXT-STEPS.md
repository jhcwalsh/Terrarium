# NEXT-STEPS.md — after campaign-3

## Resuming after a restart (checked 2026-08-11 at close)

Everything is durable — nothing was pending when this was written:

- **Git**: all work committed and pushed; `main` == `origin/main` at
  `656cc66`. The only untracked file is a PowerPoint lock file
  (`presentations/~$…pptx`) — an artifact of the deck being open, ignore it.
- **No background jobs pending**: the H.10 waiter, fits, trainings, grids
  and gates all completed; the Task Scheduler fallback was deleted after
  use. Nothing needs rescue or resumption.
- **Local-only state that survives restart on disk** (gitignored by
  design): the vintage store under `data/`, and the campaign-3 fit/
  checkpoint/grid artifacts under `experiments/campaign3/` (their pins and
  manifests ARE committed — `configs/campaign3-seed-checkpoints.json`,
  `artifacts/campaign3/*.json` — so the committed record verifies the
  local artifacts rather than trusting them).
- **To relaunch the datalab console** (optional):
  `uv run --group console streamlit run apps/datalab/app.py --server.port 8795`
- **To relaunch the session service / app** (product work):
  `uv run uvicorn ah.serve:app --port 8787` and `cd app && npm run dev`.

*Written 2026-08-11 at the campaign-3 close (verdict SHIP-BENCHMARK; K3
demotion fired; severe leg passed by BOTH sides on its first posing). Owner
priorities per standing rulings; nothing here starts without the owner's nod
except where marked.*

## Where campaign-3 left us

- **bootstrap-v1 on the extended span is the generator of record**: resamples
  real 1953–2020 history including stagflation, survived a fair neural
  challenge (clause 1 unmet on both routes), and passed the first-ever
  posable severe test — as did the challenger. `CAMPAIGN3-PROMOTION.md` /
  `artifacts/campaign3/promotion-verdict.json` are the record.
- **The K3 finding is the campaign's discovery**: the har-masked variant
  (no HAR months, 57% fewer training blocks) beat the benchmark's pooled
  tail route while the HAR-fed variant did not; the sealed demotion
  criterion fired on term (b) (0.0867 > 0.0683) and term (a) (the pooled
  clause flips). Standing lesson, now on the record: **reconstructed months
  serve reference bands and evaluation, never neural training data.**
- The campaign-2 record is untouched and replayable (five campaign-split
  freezes: vintage, factor set, checkpoint manifest, grid root, severe root).

## 1. Product track — the main line (single-user first)

Per the owner's sequencing: single-user, then real-time cohort, then
facilitated multiplayer. The campaign strengthened the story under the play
surface ("resamples real history, survived a fair challenge"). First
milestone to pick: next `su-app` increment off
`Instructions/KICKOFF-PRODUCT-SU.md`. **Needs the owner's pick.**

## 2. Cheap research follow-ups (adjacent; run in gaps, not instead)

- **Seed-committee diagnostic (~a day, no seal touched):** ensemble the three
  existing v2 checkpoints into one sampler and re-judge — v2 lost on
  cross-seed dispersion (|mean_d| 0.137 < sd 0.161), so if pooling seeds
  clears clause (1), the gap is variance, not capability. Diagnostic only;
  any promotion claim would need its own sealed campaign.
- **JST cross-country scoping note (design doc, no compute):** the `jst`
  source (18 countries, ~150y) as REAL training data — the honest multiplier
  the HAR lesson says we need. Question for the note: L3 training with a
  country embedding, generating US-conditioned paths; what the uk block
  activation needs (`factors.yaml` uk factors are declared-unavailable).

## 3. Campaign-4 — only when 1–2 say it's worth it

Preconditions before any new campaign seals:
- The seed-committee result (if variance was the whole story, campaign-4 is
  a training-stability campaign, not an architecture campaign).
- The JST note (if real cross-country data is feasible, that beats
  everything else).
- **The re-aimed criterion**: judge "unconditional parity AND conditional
  capability the benchmark structurally lacks" (the conditional tier exists,
  reported-not-gating today). A resampler is near-unbeatable on
  unconditional parity by construction; the hierarchy's value is what-ifs.
- Training data: real months only (the K3 lesson, to be sealed as a rule).
- hier-diffusion stays retired absent a dated amendment.

## 4. Standing owner calls, unchanged by the campaign

- **ER register** (release events): ER-6 — `rc_curve` never fitted, ~29% of
  commitments never called — gates the commitment lever (E1). ER-2, ER-5,
  ER-8 open.
- **Step 3 / G3**: the translation layer's honest G1-completion FAIL stands;
  G3 was never taken. Any product claim resting on the twin inherits it.
- **K1 holdout**: post-2026-08 data accrues untouched; first read 2029-01 at
  the earliest, one read, spec sealed before reading.

## 5. Hygiene (no owner input needed)

- Delete merged local branches; keep the datalab console handy for vintage
  interrogation (port 8795).
- The repo-root `climate-fit-report.md` copy from the campaign-3 L1 refit
  should be committed or removed with the evidence doc — check at merge.
