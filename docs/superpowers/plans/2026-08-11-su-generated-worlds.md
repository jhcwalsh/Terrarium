# SU generated worlds — draft plan (PD-2 phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans,
> task by task.
>
> **APPROVED by the owner 2026-08-11** ("I approve the plan - start with the
> survey, stagflation 1974 first"). **OD-1 = the 1974-start stagflation
> world.** OD-2 (commodities playable vs display-only) deliberately left to
> be informed by the Task 0 survey. Task 0 runs on main (docs-only); Task 1+
> each get their own `su-gen-NN` branch per repo convention.

**Goal:** playable worlds whose paths come from **bootstrap-v1 on the
extended span** (campaign-3's generator of record: real 1953–2020 blocks,
stagflation reachable, severe-tested) instead of toy-v0 presets — flowing
through the EXISTING world → bundle → session → app chain, changing as
little of it as possible.

**What "generated" means here — and what it does not (owner-ratified
distinction, for the plan and all player-facing copy):** these are
**bootstrap-v1 worlds: rearranged truth.** Every month in them is a real
1953–2020 month; what is new is the *sequence* — decades that never happened,
assembled from months that did. That is the campaign-3 generator of record,
and it is why register ER-9 cannot occur in a generated world (no month can
be worse than the worst real month on record). "Generated" does **NOT** mean
the neural family (`hier-flow`): truly-invented months reach a player only
after a re-aimed campaign demonstrates conditional capability the resampler
structurally lacks (the campaign-4 preconditions in `NEXT-STEPS.md` §3). The
player-facing disclosure and the bundle's credibility pointers should draw
exactly this line: *rearranged truth now; invented worlds only when earned.*

**Grounding facts (verified 2026-08-11):**
- `schemas/` enum already admits `generator_id: "bootstrap-stratified"` (the
  sealed alias for bootstrap-v1); schemas stay read-only truth.
- Bundle contract is `world-bundle-0.4`; the app consumes it; the server is
  the sole authority for value/scoring.
- PD-4: artifacts pre-authored at world build (tier-1 deterministic always).
- The campaign-3 record is the credibility story; the credibility console
  should walk a generated world exactly as it walks a preset one.

## Constraints (standing, non-negotiable)

- Determinism: one integer seed; ensemble seeds `base + 7919*k`; replay MATCH.
- Narrative-blindness: the engine path stays clean of narrative fields.
- No network at build/test; catalog reads only through sanctioned surfaces.
- `TOY_ENGINE_VERSION` discipline applies in spirit: generated worlds get
  their own `world_id` block — scores from different engines never share a
  leaderboard row.
- The K1 fence: world building reads train+validation surfaces only.

### Task 0: survey (no code) — DONE 2026-08-11; full evidence in
### `2026-08-11-su-generated-worlds-survey.md` (file:line for every claim)
- [x] **Build path: an adapter WP is required.** `ah world build` validates
      a bootstrap world green already (validator never reads generator_id),
      but `ah run` is hardwired toy: `_require_toy` raises on any non-toy
      id, and the RunRecord would stamp `toy-v0.5` regardless. Smallest
      seam: a generator-backed `run_ensemble`/`run_path` returning the
      SAME `EnsembleResult`/`EnginePaths` contracts (16 factors → 8 assets
      + rate/spread/inflation/crisis), so digest/replay/twin/play/bundle
      are untouched. Must reconcile the seed rule (toy strides 7919/path;
      bootstrap draws all paths from one seed) and pin the campaign vintage
      via an `x_` extension (engine_defaults has no vintage field; schemas
      stay read-only).
- [x] **Bundle: 16 concrete gaps recorded** (survey S2). Load-bearing:
      per-series units/kind (only 5 of 16 factors are returns, and DECIMAL
      not percent; 11 are levels the app cannot render today); app version
      allowlist + hardcoded toy asset list (a 16-factor bundle silently
      renders one chart); per-month proxy attribution is UNRECOVERABLE
      post-generation (row indices discarded) so disclosure is per-factor
      shares computed at build; the rebuild-from-RunRecord-alone posture
      breaks (needs the uncommitted vintage store) → OD-4; credibility
      pointers exist to embed (promotion-verdict.json + vintage) but new
      bundle sections need their own integrity story (tape_seal covers only
      the tape). Size is a non-issue (3.1% of budget used). The "both
      suites verify the fixture" acceptance line is NEW work (only vitest
      reads it today — BUILD-SUMMARY already records this contra CLAUDE.md).
- [x] **Twin: the played twin already has a commodities sleeve**; the
      sealed mapping table's commodities omission lives in a layer the play
      surface never calls (HF/PM sleeves; zero callers in src/). Asset
      construction for the adapter is enumerated in S3 — bonds reuses the
      duration-8.5 convention verbatim; ig_spread needs a percent→bps
      conversion; `reits` has NO factor (→ OD-3); `pe/pc/re` come from the
      PM sleeve mappings + smoothing kernel (the real adapter work). ER-6
      is inherited whole (age-driven arithmetic, generator-independent).
      Generated worlds carry a NEW alpha stamp (`port-v1-cashflow-gen`
      style), never a bump of the toy one.
- [x] **Artifacts: templates are generator-agnostic; the feed producer is
      the coupling.** Three derived inputs needed (YoY inflation — the cpi
      factor is a LEVEL, discontinuous at block seams; spread percent→bps;
      crisis mask from RegimeRecord CRI labels). `board_pack` has no
      producer at all today; `committee.py` keys the briefing off tape
      column 0 by POSITION (would silently read cape_v) — must key by name.
      PD-4's "pre-authored at world build" is in practice at BUNDLE build
      from a RunRecord; Task 4 follows that seam.
- [x] **ER-9 moot check: PROVEN.** The bootstrap ensemble is a row-copy of
      the panel; bound exact and attained (verified to the bit at 512×120).
      Worst equity month any generated world can print: **−22.59%
      (Oct 1987)** vs the toy's −86.3% artifact. Qualifiers recorded:
      pre-1986 equity_vol is HAR model output; hy_spread is 100% proxy;
      stratification pins only block STARTS, so the all-months bound is the
      world bound. Feeds the tail bands and the player disclosure.

**New owner decisions surfaced by the survey:**
- **OD-3 (reits):** the 16-factor set has no REIT factor. Options: (a) drop
  the reits sleeve in generated worlds (redistributes its 5 points; twin
  numerics differ from toy worlds — fine, new alpha stamp anyway), or
  (b) a stated construction (e.g. levered equity_mkt + a spread term),
  which is exactly the silent-proxy style RFR-8 refused unless declared
  loudly. Survey lean: (a), honesty first.
- **OD-4 (bundle reproducibility):** bootstrap bundles cannot rebuild from
  a RunRecord alone on a clean checkout (vintage store is local-only).
  Options: (a) require `data/` presence at build and record the vintage
  digest in the bundle, or (b) persist the generated slice the bundle
  needs at build time. Survey lean: (a) build-time requirement + stamped
  lineage, keeping bundles small and the store authoritative.
- **OD-2 (survey recommendation): commodities PLAYABLE** — the sleeve
  exists, the factor is real/sourced/licensed (RFR-8 discharged), binding
  is a units-stated 1:1 with no seal touched; disclose that the sealed PM
  loadings carry no commodities regressor (map-2026.08, vintage
  2026-08-07.5), re-estimation deferred to a named G3 amendment.

### Task 1: `su-gen-01 — the generated WorldSpec + the adapter`

*(Scope grew per survey S1/S3: the factor→asset adapter IS the bulk of this
task — a generator-backed `run_ensemble`/`run_path` returning the toy
contracts, the seed-rule reconciliation, the vintage pin via `x_` extension,
an honest `resolved_engine` stamp, and the OD-3 reits decision applied.
The 1974 scenario (OD-1) is the acceptance vehicle.)*
- [ ] An authored WorldSpec preset (e.g. `stagflation-1974` start-state)
      naming `bootstrap-stratified`, base_seed, n_paths; validator V1–V12
      green; world_id block distinct from toy presets.
- [ ] `ah world build` produces a stored world + RunRecord with
      `resolved_engine` pinning bootstrap-v1's version + campaign vintage.
- [ ] Replay MATCH bit-identical.

### Task 2: `su-gen-02 — bundle 0.5`
- [ ] Bundle carries the generated ensemble slice the app needs, the
      16-factor names, per-factor proxy shares, and the campaign-3
      credibility pointers (verdict + vintage), <1MB gz, mtime=0.
- [ ] `app/fixtures/` gains a committed generated toy-sized bundle; both
      suites verify it.

### Task 3: `su-gen-03 — session + app`
- [ ] Session service serves generated worlds unchanged (server-authority
      audit); app renders the 16-factor world; proxy months disclosed in
      the display surface (the datalab posture, player-facing).
- [ ] The credibility console walks a generated world.

### Task 4: `su-gen-04 — pre-authored artifacts`
- [ ] Tier-1 deterministic artifacts render over generated paths at build;
      recorded in the bundle per PD-4.

**Gate per WP:** plan's acceptance tests + full suite + ruff/pyright +
CHANGELOG; merge `--no-ff` on green.

**Owner decisions needed before Task 1:**
- OD-1: which authored scenario ships first (a 1974-start stagflation world
  is the campaign-3 showcase; a 1965-start severe-style world is the boldest).
- OD-2: whether commodities appears as a playable sleeve now (ER-6's shadow)
  or factor-display-only until ER-6 closes.
