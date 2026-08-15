# NEXT-STEPS.md — after the translation-layer audit (2026-08-14)

**State of the world:** the single-player game is FINISHED and runs on
`stagflation_1974` world `…603` (toy presets `511–514`), engine `toy-v0.6`,
mappings `v1.1` (`map-2026.08.2`), play alphas **`port-v4-ladder` /
`port-v4-ladder-gen`** (bumped by ER-12 — old leaderboard rows are fenced, not
deleted). Everything merged and pushed through `b401425`.

## What closed today (2026-08-14)

The translation-layer audit ran three independent read-only auditors against
the DESIGN documents rather than the test suite
(`docs/superpowers/specs/2026-08-14-translation-layer-audit.md`). Its verdict —
"the numeric spine is exact; the gaps are dead design, computed-but-invisible,
and calibration drift" — held up, and four of its five findings are now closed.

- **F1 — the sealed smoothing kernel never ran.** Owner route (a): the toy
  engine's filter IS the product's smoothing model, recorded as **ER-11** with
  what the shipped path forgoes and a ~3-day price for reversing it. The
  latent 4.47x double-count in the unused applier is fixed; exposure was
  checked consumer by consumer and was nil.
- **F2 — ER-6's expiry line reached no surface.** Now on `PlayQuarter`, the
  console ladder (`expired` column), the session (`expired_undrawn` plus a
  running total) and the app's ledger.
- **F4 — the scored surface could not be audited from outside.** Spending is
  rederivable (`spending_basis` x rate closes to 1e-12); the lever's pre-fill
  declares the state it was computed from, since it CANNOT be made exact
  without leaking unrevealed months; and the lever now sends only the sleeves
  the player touched, so untouched ones hold to plan exactly.
- **F3 — the crossover band.** ACCEPTED AND RECORDED, with its cost stated:
  the band keeps flagging and that flag now means "this world distributes late,
  as stressed worlds do". Re-measured after ER-12 and unchanged at 8.750.
- **F5 — calibration drift** (CTA vol, PM betas short of prior, Gaussian PM
  residuals vs sealed SM-8) is the one still OPEN. Record-only; batch it into
  the next amendment cycle rather than doing it alone.

**ER-12, which the audit's own F2 column exposed:** the opening private book
was three clones of one age-5.25 cohort, so the whole programme lapsed in the
same quarter. It is now a staggered ladder, one rung per year of fund life.
`peak_unfunded_ratio` **cleared its declared band** (1.288 -> 0.716) — the
metric ER-6's close-out could not fix, whose real cause was upstream of
everything ER-6 blamed. `linkage_bite` was the casualty (annual wind-ups broke
its window-exclusion rule) and was restored in a SEPARATE change so attribution
stayed clean: netted by amount, 0.778 median, band unchanged and not needing to
change. `linkage_shortfall` sits at 0.027, below its floor — recorded, not
tuned.

## The main line now: the CIO dashboard

The owner's design spec and implementation plan are in the repo
(`docs/superpowers/specs/2026-08-14-cio-dashboard-design.md`,
`docs/superpowers/plans/2026-08-14-cio-01-view-builder.md`): the dashboard
becomes the play surface, `Play.tsx`'s panels retire after cutover, and
`buildCioView` lives SERVER-side in Python because the server is the authority
for value (DN-3 W5). Work happens on `cio-01-view-builder`, not on main.

Two things to settle inside cio-01 rather than around it:

1. ~~**`docs/CIO Dashboard.zip`**~~ **SETTLED.** Task 1 vendored DN-8 and the
   renderer out of it: `Instructions/DN-8-cio-dashboard-data-contract.md` is the
   citable contract and the renderer lives at `docs/cio-dashboard/`. A binary
   nobody can diff no longer holds the authority, and the zip was filed to
   `docs/historic/` on 2026-08-15 (see `docs/current/README.md`).
2. **What the dashboard renders about the linkage.** `linkage_bite` is alive
   again but `linkage_shortfall` is below its floor; if a panel shows either,
   decide what a flagged band means on a player-facing surface before it ships.

## Standing owner questions

- **Group play** — back-burnered until reopened.
- **Toy-engine realism family** (ER-2 / ER-5 / ER-8 remainder / ER-9) —
  deprioritized; decides whether toy presets are ever player-facing.
- **ER-11 route (b)** — routing the sealed per-sleeve kernel live, ~3 working
  days, available as a release event whenever the realism is wanted.
- **JST commercial use** — the licence registry now says plainly that JST is
  non-commercial (corrected 2026-08-14). Whether a generator trained on
  JST-derived priors may back a commercial play surface is a licensing
  judgment, not an engineering one, and is unanswered.

## Housekeeping (small, unscheduled)

- Sealed `v1.1` erratum: the DL row's `n_quarters: 195` counts MONTHLY BDC
  observations — fold the correction into the next reseal event, not its own.
- `scripts/gen_bundle_fixtures.py` writes nondeterministic `run_id`/`created_at`
  on regen (exercised again at ER-12); `fixtures/compiler` CRLF churn under
  Windows autocrlf. Both still deferred.
- The probe worktree (`../Terrarium-probe`) is removable once the Phase-0
  artifacts have been reviewed.
