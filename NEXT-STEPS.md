# NEXT-STEPS.md — after the campaign-4 NO-GO (2026-08-14)

**State of the world:** the single-player game is FINISHED and runs on
`stagflation_1974` world `…603` (toy presets `511–514`), engine `toy-v0.6`,
mappings `v1.1` (`map-2026.08.2`). Everything merged and pushed through
`f192a8b`+; the write-up (docs/alternate-histories-audited.md + published
artifact) is current through the 13-Aug returns audit.

## What just closed (2026-08-12 → 08-14)

- **The returns audit** — both owner-found defects fixed and guarded:
  PM loadings re-estimated with Dimson sum-betas under `AM-2026-08-12-001`
  (PE beta 0.35→0.84, DL re-anchored to the BDC index); the ER-10
  reported-marks fix (`toy-v0.6`, catch-up invariant + console
  reported-plane row). The parked "PE sealed alpha" question is CLOSED.
- **Both research probes** — seed-committee diagnostic (clause-i failure
  was variance, 80x dispersion collapse; clause-ii tail failure is
  architectural) and the JST scoping note (annual data; no honest monthly
  multiplier; a cheap research-only widening of the existing connector is
  the only GO inside it).
- **Campaign-4 — CLOSED, NO-GO at the Phase-0 gate** (owner accepted
  2026-08-14). Two architecture-level walls: conditioning is skin-deep
  (pinned regime labels, non-following trajectories) and the tail/edge
  trade-off is coupled in sampling. Design + reopening conditions:
  `docs/superpowers/specs/2026-08-13-campaign4-design.md`. SHIP-BENCHMARK
  stands; the collagist is the product engine. The apprentice shelf is not
  ambiguous: three named numbers must move, all architecture work.

## The main line now: collagist product

Owner directives standing: group play BACK-BURNERED; toy-engine realism
family (ER-2/ER-5/ER-8-remainder/ER-9) DEPRIORITIZED. Candidate next
builds, owner's pick:

1. **A second playable world** — the 1965 start ("the boldest" per the
   su-gen survey) or a second 1974-class seed; the adapter/bundle/session
   path is proven, so each new world is mostly preset + console walk +
   fixtures.
2. **World variety within a scenario** — surfacing sibling seeds of 1974
   as selectable runs (leaderboards already fence per (world_id, seed)).
3. **JST research-only widening** (from the scoping note): unfilter the
   17 non-US countries for L1 partial pooling + held-out-regime backtests;
   fix the LICENSE-REGISTRY.md misclassification (JST is CC BY-NC-SA,
   NON-commercial — flagged 2026-08-13, still open).

## Housekeeping (small, unscheduled)

- `docs/data/LICENSE-REGISTRY.md` JST row — misclassified as
  commercial-free; correct to CC BY-NC-SA (see scoping note §1).
- Sealed v1.1 erratum: DL row's `n_quarters: 195` counts MONTHLY BDC obs —
  fold the correction into the next reseal event, not its own.
- `scripts/gen_bundle_fixtures.py` writes nondeterministic
  run_id/created_at on regen; `fixtures/compiler` CRLF churn under Windows
  autocrlf — both deferred, one small WP if they annoy again.
- The probe worktree (`../Terrarium-probe`) is removable once the Phase-0
  artifacts have been reviewed (they live in the real `experiments/`
  store via junction; nothing is lost with the worktree).

## Standing owner questions

- **Which product build next** (§ above, 1/2/3 or something else).
- **Group play** — stays back-burnered until reopened.
- **Toy presets player-facing?** — unchanged; decides whether the
  ER-5/ER-8 family ever gets scheduled.
