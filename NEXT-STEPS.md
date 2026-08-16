# NEXT-STEPS.md — the spine-conditioned compiler pilot (2026-08-16)

**State of the world:** the single-player game is FINISHED and runs on
`stagflation_1974` world `…603` (toy presets `511–514`), engine `toy-v0.6`,
mappings `v1.1` (`map-2026.08.2`), play alphas **`port-v4-ladder` /
`port-v4-ladder-gen`** (bumped by ER-12 — old leaderboard rows are fenced, not
deleted). The CIO dashboard line has LANDED (`cio-01`…`cio-04`, the inherited
decade included). Everything merged and pushed through `7d4b092`.

## The main line now: the spine-conditioned compiler — pilot DONE, spine-02 authorized

**The pilot is complete and merged** (`f988952`, gate 2770 passed). All nine
tasks ran: the `x_spine` contract, the premise-accepted spine sampler, the
four-quadrant clock with its per-quadrant correction hazard, `SpineBootstrap`,
the seal-safe dispatcher (registration hook, boundary pinned by two tests),
world 802 "The Hard Landing", a pre-registration sealed before measurement and
never touched after, and the measurement itself — committed verbatim. Both
plan constraints held: commit-order-as-pre-registration honored, bit-identity
of 1.0.x and stress worlds pinned green throughout.

**The verdicts, in plain English (full record:
`docs/superpowers/specs/2026-08-15-spine-pilot-results.md`; certified by an
independent review that reproduced every sealed number):**

- **Two real weaknesses.** Recoveries run ~half history's length (B4 — the
  same persistence flaw that sank hier-flow at G2, now located to one
  quadrant); stitched decades still jump inflation eras slightly too often at
  the aggregate p95 level (B2), even though the per-join era filter itself was
  airtight (0 violations in ~734 ordinary joins).
- **One economic surprise.** Conditioning months on the storyline made decades
  MILDER: the over-committed 55% book never breaches under world 802 (0/20)
  where the plain stress compiler's family breached (B3). Coherence currently
  costs severity.
- **Two wiring faults, not model faults.** The spine's policy anchor was fed
  trend inflation as actual inflation, so the reaction term it was tested on
  was identically zero (B1 unwinnable as wired; B6's tightness construct had
  no inflation content for the same reason). Named repair: one argument.
- **One empty bar.** B5's design would fail a perfect machine ~99% of the
  time (six historical crisis onsets is too thin a target for a ±50% band).
- **One disclosure.** The B3 ladder's 20 seeds carried only ~2 distinct macro
  spines (a stride collision); disclosed everywhere, repair in spine-02.

**Options, as put to the owner (2026-08-16):** (1) fix the wiring and re-run
under a fresh seal — days; (2) ship the trainer on the plain stress compiler
now (memo Path A) — nothing this week blocks it; (3) fund the deep
persistence repair — weeks, campaign-scale, D-SP-4. They compose: 2 now, 1
next, 3 only if 1's residue justifies it.

**RULED: option 1 is authorized and spine-02 is the live line.** Scope: feed
`pi_actual` into the policy anchor (using only the fitted observation-noise
parameter — no new knobs), fix the attempt-stride collision, respecify B1/B6
at the model's actual (contemporaneous) lag structure, redesign B5 to be
decidable, reseal, re-run. B2/B3/B4 unchanged — whatever still fails after
the wiring fixes is genuinely the model, and prices option 3. Unblocked in
parallel regardless: the memo's Path-A honesty work (the "how this world was
made" disclosure moving onto the play surface).

## Standing owner questions

- **D-SP series (spine pilot, all proposed-never-taken):** D-SP-1 the
  severity table's sealed values (kept-for-pilot; its inflation condition
  duplicates the quadrant hot bit — revisit here); D-SP-2 the hazard's state
  vector; D-SP-3 the premise vocabulary; D-SP-4 what a future PASS buys
  (option 3's gate); D-SP-5 refitting L2 natively on the four quadrants.
  Plus one small carry: world 703's precedent line says "9 level factors" but
  its declared join tolerances cover 2 — 802's was corrected; amending a
  shipped world's disclosure is the owner's call.
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
