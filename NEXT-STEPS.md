# NEXT-STEPS.md — the spine-conditioned compiler pilot (2026-08-16)

**State of the world:** the single-player game is FINISHED and runs on
`stagflation_1974` world `…603` (toy presets `511–514`), engine `toy-v0.6`,
mappings `v1.1` (`map-2026.08.2`), play alphas **`port-v4-ladder` /
`port-v4-ladder-gen`** (bumped by ER-12 — old leaderboard rows are fenced, not
deleted). The CIO dashboard line has LANDED (`cio-01`…`cio-04`, the inherited
decade included). Everything merged and pushed through `7d4b092`.

## The spine line: FUNDED → **CLOSED 2026-08-17** (D-SP-8, at the second frontier). D-SP-6 (2026-08-16 evening) funded stage 1; the campaign ran two weeks, hit two measured frontiers, and was closed. Verdict: `docs/superpowers/specs/2026-08-17-spine-v2-results.md`. The round-1/round-2 record below stands unchanged.

**The spine v2 close, in four lines.** Sealed exam `2026-08-17-spine-v2-exam.md`
+ `spine-v2-prereg.json` (`5d1a282`), one amendment `AM-SPV2-2026-08-17-001`
(`181c208`). **D1–D4 PASS** everywhere — persistence, the flaw that sank the
pilot and `hier-flow`, is solved. **T1 QUALIFIED PASS** (1.9131 in band, but
most of the movement was the estimator, and the clearing arm's curve is 93.9%
exogenous noise). **O1 FAIL** (0.5118 vs 0.5181) at every feedback strength —
it measures the growth↔inflation phase and the curve is not that channel.
**A1/A2/R1/R2 NOT MEASURED** — they need the flesh, and sampler integration was
never reached. Two named missing mechanisms with measured sizes are on the
record for a **stage-2 spec, which is pending an owner decision** and is not
proposed by the close-out.

Two full pre-registered rounds, both merged: the pilot (`f988952`, gate 2770)
and the owner-authorized wiring-fix re-run **spine-02** (`deac7fc`, gate 2851).
Records: `docs/superpowers/specs/2026-08-15-spine-pilot-results.md` (round 1,
frozen) and `docs/superpowers/specs/2026-08-16-spine02-results.md` (round 2,
with post-measurement characterization corrections from the verdict-integrity
review — verdict values untouched). Every number in both rounds was reproduced
by an independent reviewer before it reached this file.

**Round 2, in plain English — what the wiring fixes changed:**

- **Severity binds after all (B3 PASS on the sealed bars).** With the stride
  collision fixed (20 genuinely distinct decades per ladder, verified — round
  one secretly had 2), the over-committed 55% book breaches (2/20), coverage
  is monotone, and hold-course depth lands in band (by 0.59pp — marginal,
  recorded). Round one's "coherence costs severity" was mostly the 2-spine
  artifact.
- **The true model residue, twice-confirmed (B2 FAIL, B4 FAIL under
  byte-frozen judges both rounds):** stitched decades jump inflation eras a
  bit too often at the p95 level, and recoveries run ~half history's length —
  the same persistence flaw that sank hier-flow at G2.
- **A new economic finding: transmission is present but WEAK.** A tight-policy
  month lifts 12-month downturn odds 1.14x in the spine vs 2.37x in history
  (matched definitions). The sealed B6 verdict reads FAIL, but the review
  proved it compared mismatched crisis codes; under either consistent
  definition the magnitude check passes. B6 v3 (outcome-event match) logged.
- **One exam question was broken and the process caught it:** B1 v2 is an
  anti-test — its pass rate FALLS as the policy response strengthens (a
  no-reaction model scores best; the 0.90 bar is unreachable). The wiring fix
  itself is proven live (recovered phi_pi 0.42–0.85, positive on all 20
  decades). The sealed FAIL carries no information; B1 v3 logged.
- **B5 v2:** one noise-compatible failing seed, but all five seeds over-fire
  by ~+17% pooled — a weak, coherent signal for the redesign.
- Record hygiene: the b3 re-run briefly contaminated round one's frozen
  results file; restored byte-exact with a recurrence guard.

**THE DECISION NOW OPEN (D-SP-4, the owner's):** the spine architecture hurts
properly (B3), tells one story per decade, and refuses impossible premises.
What it cannot yet do is make bad times last (B4), keep era texture fully
smooth at the tails (B2), or transmit policy to the real economy at
historical strength (the B6 finding). That is exactly the scope of the deep
repair the spec named on day one — the L2 generation-time hazard link — now
priced by three numbers instead of a hunch. Options: fund it
(weeks, campaign-scale); or park the spine with its two-round record and ship
the trainer on the plain stress compiler (memo Path A — unblocked, and the
"how this world was made" disclosure work needs no research either way).

## Standing owner questions

- **Default plan vs edited book (app-open-02 branch review, I2)** — the
  served default commitment plan is built from WORLD targets; a player who
  lowers a private target ~21%+ would breach the commitment cap in later
  (6%-escalated) plan years. Shipped remedy: client pre-flights the exact
  server rule and blocks Play with a named fix. Open ruling: should the
  default plan RESCALE to the book's own edited targets instead?
- **Spine v2 exam rulings** (asked 2026-08-16 with measured numbers):
  which tight-policy definition anchors the transmission bar (inverted
  curve recommended); completed-vs-all spells for the dwell bar
  (completed-only recommended); 4% vs 3% high-inflation line (4%
  recommended, 3% sensitivity published). The exam seals after these.

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
