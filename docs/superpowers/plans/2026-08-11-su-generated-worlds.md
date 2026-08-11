# SU generated worlds — draft plan (PD-2 phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans,
> task by task. DRAFT — owner review before any code.

**Goal:** playable worlds whose paths come from **bootstrap-v1 on the
extended span** (campaign-3's generator of record: real 1953–2020 blocks,
stagflation reachable, severe-tested) instead of toy-v0 presets — flowing
through the EXISTING world → bundle → session → app chain, changing as
little of it as possible.

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

### Task 0: survey (no code) — answer in the plan before building
- [ ] How `ah world build` resolves `bootstrap-stratified` today: what
      `run_ensemble` does with a non-toy generator, what breaks (the
      engine/institution layer expects toy `NumericWorld` paths — does the
      generator ensemble slot in, or is an adapter needed?).
- [ ] What the bundle must carry for a generated world that it doesn't
      today (factor set 16 vs the toy factor list; per-month proxy shares
      for the display surfaces — the proxy_share_disclosure posture reaches
      the PLAYER here).
- [ ] Institution/twin mapping: `ah/port` factor→sleeve mappings against the
      16-factor set (commodities sleeve exists in D4; does the twin's
      mapping table need a commodities row, and does ER-6 bite?).
- [ ] Artifact authoring (PD-4) over generated paths: tier-1 templates take
      which inputs; what a "briefing" reads on a bootstrap world.

### Task 1: `su-gen-01 — the generated WorldSpec`
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
