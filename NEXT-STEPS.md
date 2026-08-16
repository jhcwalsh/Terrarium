# NEXT-STEPS.md — the spine-conditioned compiler pilot (2026-08-16)

**State of the world:** the single-player game is FINISHED and runs on
`stagflation_1974` world `…603` (toy presets `511–514`), engine `toy-v0.6`,
mappings `v1.1` (`map-2026.08.2`), play alphas **`port-v4-ladder` /
`port-v4-ladder-gen`** (bumped by ER-12 — old leaderboard rows are fenced, not
deleted). The CIO dashboard line has LANDED (`cio-01`…`cio-04`, the inherited
decade included). Everything merged and pushed through `7d4b092`.

## The main line now: the spine-conditioned stress compiler

The design and the plan are both in the repo and both authoritative:
`docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md` and
`docs/superpowers/plans/2026-08-15-spine-conditioned-compiler-pilot.md`
(9 tasks, TDD, **pre-registration before measurement**). L1/L2 slow-state
spines steer which real 6-month chunks the stress stitcher draws, with a
state-dependent correction hazard and a state-severity table, judged against
six pre-sealed bars (B1–B6). Work happens on `spine-01-pilot` in its own
worktree (`../Terrarium-narr`), not on main.

**Where it actually is (2026-08-16):** commits land Tasks 1–4 — the `x_spine`
contract, Layer S (premise-accepted spine sampler with named refusal), the
quadrant clock and per-quadrant correction hazard, and Layer F
(`SpineBootstrap`: quadrant-conditioned pools, era-safe joins) — plus a Task-4
review round. **Task 5 (dispatcher routing and bit-identity guards) is next.**
Read the commit trail, not the plan's checkboxes: the checkboxes are not being
ticked as work lands, so the file reads 0/39 done and is not a progress signal.

Two constraints from the plan that are easy to trip over and expensive to undo:

1. **Commit-order-as-pre-registration.** Task 6's sealed thresholds must be
   committed BEFORE Task 7 or 8 draws any pilot ensemble. Measuring first and
   sealing after destroys the pilot's standing, and no amount of care afterward
   recovers it.
2. **Bit-identity.** Sealed 1.0.x bootstrap worlds AND stress worlds (703) must
   produce byte-identical ensembles after every task; Task 5 pins this with
   digests.

The binding owner rulings (R1 selection-only, R2 hazard-not-schedule, R3 the
four-quadrant clock with no imposed transition matrix) are stated in the plan's
Global Constraints. R3's amendment is on main at `81552eb`.

## Standing owner questions

- **ER-14 — inflation does not reach private markets** (filed 2026-08-16,
  `docs/engine-realism-register.md`; detail in
  `docs/current/private-markets-and-inflation.md`). Status `open`, no fix
  scheduled. Measured: private equity is bit-identical from 1% to 12% declared
  inflation, real estate moves the WRONG way, and the tier-1 linkage cannot see
  inflation by signature. Closing it is a release event — `TOY_ENGINE_VERSION`
  and both play-alpha stamps bump, every RunRecord digest is invalidated, both
  bundles rebuild, the battery re-runs — and a real fix additionally needs an
  amendment to the sealed `mappings/cashflow-tier1-v1.0.yaml` plus a decision
  about the Delta 3 no-regime-label rule. **If it is ever scheduled, batch it
  with F5 below:** both are seal-adjacent, and one reseal is far cheaper than
  two.
- **F5 — calibration drift** (CTA vol, PM betas short of prior, Gaussian PM
  residuals vs sealed SM-8), the one still-open finding of the 2026-08-14
  translation-layer audit
  (`docs/superpowers/specs/2026-08-14-translation-layer-audit.md`).
  Record-only; batch it into the next amendment cycle rather than doing it
  alone.
- **ER-11 route (b)** — routing the sealed per-sleeve kernel live, ~3 working
  days, available as a release event whenever the realism is wanted. Until
  then the shipped reported plane is the ENGINE's filter and **de-smoothing a
  shipped series does not recover truth** (SM-10's inverse property does not
  hold on the shipped path).
- **Toy-engine realism family** (ER-2 / ER-5 / ER-8 remainder / ER-9) —
  deprioritized; decides whether toy presets are ever player-facing.
- **Group play** — back-burnered until reopened.
- **JST commercial use** — the licence registry now says plainly that JST is
  non-commercial (corrected 2026-08-14). Whether a generator trained on
  JST-derived priors may back a commercial play surface is a licensing
  judgment, not an engineering one, and is unanswered.

## What the 2026-08-14 audit settled

Kept short because the detail now lives where it belongs: `CLAUDE.md`'s
engine-realism summary carries ER-11 and ER-12, and
`docs/engine-realism-register.md` carries all of them in full.

The translation-layer audit ran three independent read-only auditors against
the DESIGN documents rather than the test suite. Its verdict — "the numeric
spine is exact; the gaps are dead design, computed-but-invisible, and
calibration drift" — held up. **F1** closed as **ER-11** (owner route (a)),
**F2** put ER-6's expiry line on every surface, **F4** made the scored surface
externally auditable, **F3** accepted the crossover band with its cost stated
(re-measured after ER-12, unchanged at 8.750), and **F5** stays open above.

**ER-12**, which the audit's own F2 column exposed, replaced an opening private
book of three clones of one age-5.25 cohort with a staggered ladder;
`peak_unfunded_ratio` cleared its declared band (1.288 -> 0.716) — the metric
ER-6's close-out could not fix, whose real cause was upstream of everything
ER-6 blamed. `linkage_bite` was the casualty and was restored in a SEPARATE
change so attribution stayed clean (netted by amount, 0.778 median).
`linkage_shortfall` sits at 0.027, below its floor — recorded, not tuned.

## Housekeeping (small, unscheduled)

- Sealed `v1.1` erratum: the DL row's `n_quarters: 195` counts MONTHLY BDC
  observations — fold the correction into the next reseal event, not its own.
- `scripts/gen_bundle_fixtures.py` writes nondeterministic `run_id`/`created_at`
  on regen (exercised again at ER-12); `fixtures/compiler` CRLF churn under
  Windows autocrlf. Both still deferred.
- `origin/wp2-10-ablation` is merged into main and is the last stale REMOTE
  branch. Deleting it is outward-facing, so it is left for the owner.
- Local merged branches were swept 2026-08-16 (15 of them). The main checkout
  still sits on `housekeeping-03-merge-hook`, itself already merged — moving it
  to `main` is the owner's call, since it changes their working tree.
- ~~The probe worktree (`../Terrarium-probe`)~~ — **gone**; no longer present in
  `git worktree list`.
