# NEXT-STEPS.md â€” after the ER-14 release (2026-08-19)

**State of the world.** The single-player game is finished and playable, and the
engine underneath it changed twice this week.

- **Engine `toy-v0.7`** (`src/ah/core/engine.py`), play alphas
  **`port-v5-inflation` / `port-v5-inflation-gen`** (`src/ah/play.py`), world
  bundle contract **`world-bundle-0.6`** (`src/ah/bundle.py`). Toy presets sit in
  the `52x` block (`521` stagflation, `522` goldilocks, `523` deflation_bust,
  `524` reflation_boom, `525` prehistory); the played generated preset
  `stagflation_1974` sits at `604`.
- **Release 1 â€” `712f96d`, 2026-08-19: ER-14 closed.** Inflation reaches the
  whole book. Four mechanisms â€” real estate income escalation vs cap-rate
  repricing, private equity nominal earnings vs multiple compression, private
  credit floating coupon vs coverage squeeze vs convex loss â€” plus **`infra`, a
  new fourth private class** whose pass-through is read live from
  `structural.infrastructure.inflation_linkage`. AT-1..14 all verified against
  the ratified thresholds; gate `3081 passed, EXIT: 0`, coverage 97.24%. The
  founding defect is literally inverted: PE now moves with declared inflation
  (âˆ’1.123 pp/yr over the 1%â†’12% probe) where it used to be bit-identical, RE
  moves the right way (+3.353) where it used to move the wrong way, and infra is
  the strongest response in the book (+7.005). Full record:
  `docs/engine-realism-register.md`'s ER-14 close-out.
- **Release 2 â€” `9c15b2b`, 2026-08-19: the picker has worlds again.** Retiring
  `701`/`703` left the app's declared-stress picker matching nothing playable, so
  a new `71x` block was authored: **`711` stress_1974_successor**, **`712` The
  Gulf Decade** (a supply shock into an already-8% world, severe for the whole
  decade rather than one quarter â€” the ER-14 demonstration world), **`713`
  stress_1990_successor**. The retired records stay byte-unchanged and
  permanently fenced (`ah.cli.RETIRED_WORLD_IDS`). The same merge carried
  **`AM-DSP11-2026-08-19-001`**, re-recording two sealed hashes over canonical LF
  bytes (a CRLF-rendering defect at mint; zero content change). Gate
  `3088 passed, EXIT: 0`.
- **Three papers are drafted** and now committed under `docs/papers/` â€” the
  academic write-up, its plain-English companion, and the player-facing user's
  guide. All three are **DRAFT pending owner edits** and govern nothing.
- **The stage-2 campaigns are closed, and the coupled engine is UNPROMOTED.**
  Stage 2 built the coupled monthly system and ran the full twelve-bar sealed
  exam for the first time: **nine pass, three fail**
  (`docs/superpowers/specs/2026-08-18-stage2-results.md`). D-SP-10's
  conditioning-reach fix took storyâ†”market agreement from 1.4 to 17.3 points over
  chance (`docs/superpowers/specs/2026-08-18-stage2-reach-results.md`), and
  D-SP-11's three rulers were designed, anchored, sealed and measured
  (`docs/superpowers/specs/2026-08-18-stage2-rulers-results.md`). **No owner
  ruling has been taken on any of it**, and every one of those engine changes is
  composed in `scripts/`, never in `src/ah/gen/spine.py`. Nothing generated is
  player-facing.
- **Ranked play stays parked** (D-SP-7, 2026-08-16) â€” the surface is
  practice-only until a new owner decision.

---

# OWNER DECISIONS OPEN

## 1. The stage-2 rulers â€” measured, awaiting adoption (D-SP-11)

`docs/superpowers/specs/2026-08-18-stage2-rulers-results.md` Â§6 states seven
stop-questions. **Four are adoptions that change what the platform is**; three
are record-keeping. None has been ruled.

**The four adoptions:**

1. **Adopt the conditional era-crossing rule, or keep it as a measured
   disclosure?** The rule lets a seam cross the inflation line only in a month
   where the spine's own inflation path crosses it, in the spine's own direction.
   All 104 crossings were faithful, zero unlicensed. It buys reach 77.6% â†’ 80.7%
   and story/market agreement 77.8% â†’ 78.6% â€” **and every flesh bar pays for it**:
   `A1` âˆ’7.51 â†’ âˆ’9.68, `A2`'s high-inflation correlation +0.077 â†’ +0.026, `R2`'s
   p95 1.102 â†’ 1.210, `S1`'s seam p95 2.04 â†’ 2.18. The scoreboard count does not
   move (eight of twelve on both sides), so nothing forces the choice; the choice
   is whether the ruling's own objective outranks the direction the bars moved.
2. **Do `S1` and `A1R` become bars â€” a fourteen-bar exam?** Both are sealed
   constructs with anti-tests (and, for `A1R`, a power calculation), and both
   return FAIL. Promoting them makes the exam fourteen bars; leaving them as
   rulers makes them diagnostics that inform without judging. The charter funded
   the rulers and did not say which.
3. **Is join-selection-by-inflation-distance funded?** `S1` fails on every engine
   in the lineage, and it names a lever nobody has pulled: every seam already
   respects the declared 2.5 pp join bound (`R2`'s join half passes at 2.4997),
   but among the era-safe candidates the compiler chooses without regard to how
   far inflation moves. A compiler that *preferred small-Î” joins* would move
   toward `S1`'s band **without touching one declared tolerance**. That is an
   engine change, and this campaign's engine change was the era rule.
4. **`R2`'s p95 half and `S1`'s seam half now overlap badly â€” split the promise,
   or keep the carried bar?** `R2`'s p95 pools seams and contiguous months and
   moves with either; `S1` separates them and shows the seams were out of band
   before D-SP-10 existed. Retire `R2`'s p95 in favour of `S1`'s seam half plus
   an explicit seam-frequency statement â€” or keep it, on the grounds that a
   carried bar's whole value is that it does not move?

**The three record-keeping questions**, for completeness: whether to re-derive
`S1`'s statistic independently or accept the disclosure that it was not cut
blind; whether each prior `A1` verdict should carry a pointer to `A1R`'s
measurement (the pooled truth is **âˆ’1.54 pp where the sealed single-batch
reading was âˆ’7.51 â€” off by 47 standard errors**, so every prior `A1` verdict in
either direction read a statistic whose sampling error dwarfed its effect;
nothing is re-graded, the charter forbids it); and the standing note that
**promotion of `_reach_draw` / `_era_crossing_licence` into `src/` is not asked
for by this campaign** â€” see WP-C below.

## 2. The three papers â€” owner edits

`docs/papers/` holds three DRAFT write-ups dated 2026-08-19. Each needs the
owner's editorial pass before it is released or quoted outside the repository:

- `docs/papers/2026-08-19-economic-realism-engineering-quantity-DRAFT.md` â€” the
  academic paper. Releasing it closes the "no released academic write-up" gap
  recorded in `docs/current/README.md`;
  `docs/P1-specified-world-models-preprint.md` now names it as its
  successor-in-draft.
- `docs/papers/2026-08-19-twenty-decades-plain-DRAFT.md` â€” the plain-English
  companion.
- `docs/papers/2026-08-19-decade-you-live-through-users-guide-DRAFT.md` â€” the
  player-facing guide, and the natural source text for WP-A's in-surface copy.

## 3. Remote-branch pruning â€” outward-facing, so it is the owner's call

Both remote branches below are **fully merged into `origin/main`** (verified with
`git branch -r --merged origin/main`) and can be deleted:

- `origin/er14-01-design`
- `origin/wp2-10-ablation`

That is the complete list â€” `origin/main` is the only other remote ref.

**Local, for the same sweep** (not outward-facing, but it is the owner's tree):
twenty local branches are merged into `main` â€” `app-open-01-fixes`,
`app-open-02-bands`, `er14-01-design`, `er14-02-mechanisms`, `er14-03-credit`,
`er14-04b-sleeve`, `er14-04c-app`, `er14-05-release`, `er14-06-successors`,
`er14-release`, `housekeeping-03-merge-hook`, `spine-01-pilot`, `spine-02-rerun`,
`spine2-01-exam`, `spine2-02-fit`, `stage2-01-anchors`, `stage2-02-fit`,
`stage2-03-reach`, `stage2-04-rulers`, `su-app-07-targets-and-ranges`. Two of
them (`er14-release`, `su-app-07-targets-and-ranges`) are checked out in session
worktrees and cannot be deleted while they are. The main checkout
(`C:/Users/james/PycharmProjects/Terrarium`) currently sits on a **detached HEAD
at `f835a70`**, well behind `main`; moving it to `main` changes the owner's
working tree, so it is left for them. Four session worktrees survive
(`Terrarium-alloc`, `Terrarium-g2repro`, `Terrarium-mainmerge`,
`Terrarium-spine2`) â€” removing any is safe only once the owner is done with it.

## 4. Standing questions carried, still unanswered

- **Default plan vs edited book (`app-open-02` review, I2).** The served default
  commitment plan is built from WORLD targets; a player who lowers a private
  target ~21%+ would breach the commitment cap in later (6%-escalated) plan
  years. Shipped remedy: the client pre-flights the exact server rule and blocks
  Play with a named fix. **Open ruling: should the default plan RESCALE to the
  book's own edited targets instead?** No rescale is implemented today.
- **Un-parking ranked play** (D-SP-7). Practice-only stands until reversed; the
  RankedSetup screen, the server's ranked contract, the leaderboard store and the
  digest-eligibility machinery are all intact behind a fenced bypass in
  `app/src/App.tsx`. The rebuilt-ladder ranked-eligibility question revives with
  it.
- **The D-SP series proposed and never taken:** D-SP-1 (the severity table's
  sealed values), D-SP-2 (the hazard's state vector), D-SP-3 (the premise
  vocabulary), D-SP-5 (refitting L2 natively on the four quadrants). D-SP-4 was
  ruled PARK and superseded the same day by D-SP-6.
- **Toy-engine realism family** â€” ER-2, ER-5, the ER-8 remainder and ER-9
  (`docs/engine-realism-register.md`). Deprioritized; decides whether toy presets
  are ever player-facing.
- **ER-15 remains open** â€” an entered opening book can sit arbitrarily far
  outside the ladder shape the pacing model and the linkage were fitted on.
  Mitigated by the practice-only demotion, not fixed; re-fitting across a family
  of ladder shapes would move DN-5 Â§2.1's sealed pacing figures, which is an
  amendment event and an owner decision.
- **Group play** â€” back-burnered until reopened.

---

# NEXT WPs PROPOSED

Three, in the order they would sensibly run. None is started.

## WP-A â€” the disclosure surface ("how this world was made")

The state-of-the-thesis memo's Path A named this non-negotiable: **the
disclosure moves from the evidence files into the player's face.** Its success
bar 1 is that a first-time player learns *from the play surface itself* that the
decade is prescribed and the months are real â€” the world card carrying its
precedent line and a "how this world was made" panel. **Nothing in `app/`
renders a precedent line today** (checked). The three new `71x` worlds each ship
a full `x_stress.precedent` block this surface can read directly, and
`docs/papers/2026-08-19-decade-you-live-through-users-guide-DRAFT.md` is the
source text for the player-facing copy. Needs no research and is unblocked by
everything above.

## WP-B â€” the entered-book flow, finished

`su-app-06` lets an analyst enter an opening book; ER-14's fourth private sleeve
then changed what a valid book looks like, and `OpeningBook`/`CommitmentPlan`'s
shape check (`set(book.private) == set(PRIVATE_SLEEVES)`) now **422s** any book
that cannot name the world's full private set â€” deliberate and documented in
`src/ah/serve.py`, but it means a legacy three-sleeve book fails rather than
degrades. The work: make that failure legible in the app, settle the I2 rescale
ruling above, and give the entered-book path the same band and severity framing
the derived path got in `app-open-02`. ER-15 stays open regardless â€” this WP
makes the demotion visible, it does not extend the fitted evidence.

## WP-C â€” promoting the stage-2 engine into `src/`

**Conditional on decision 1 above.** `_reach_draw` (D-SP-10) and
`_era_crossing_licence` (D-SP-11) are composed in `scripts/` and have never
touched `src/ah/gen/spine.py`. Promotion is a release event in its own right â€”
new sealed artifacts, a generator-version story, and a decision about whether a
generated world may ever reach a leaderboard (the state-of-the-thesis memo's
Path B bars are the promotion criteria, and stage 2 does not clear them). **Do
not start this before the era rule is adopted or declined.**

---

# Housekeeping carried forward

Small, unscheduled, each re-verified as still open on 2026-08-19.

- **JST commercial use.** `docs/data/LICENSE-REGISTRY.md` states plainly that
  JordÃ -Schularick-Taylor is CC BY-NC-SA 4.0 and that commercial providers are
  *"strictly forbidden to integrate all or parts of the dataset into their
  services and/or resell the data"* (corrected from FREE on 2026-08-14). Whether
  a generator trained on JST-derived priors may back a commercial play surface is
  a licensing judgment, not an engineering one, and is still unanswered. **Newly
  noticed while checking:** `docs/data/jst.md` still says
  `**License:** FREE (cite the JST papers)` â€” the per-source note never received
  the registry's correction. That line is a docs one-liner and should not wait on
  the licensing answer.
- **ER-11 route (b)** â€” routing the sealed per-sleeve kernel live, ~3 working
  days, available as a release event whenever the realism is wanted. Until then
  the shipped reported plane is the ENGINE's filter (`_reported_marks`) and
  **de-smoothing a shipped series does not recover truth**: SM-10's inverse
  property does not hold on the shipped path.
- **`scripts/gen_bundle_fixtures.py` is not reproducible.** Its own docstring
  claims both fixtures are deterministic, but `src/ah/cli.py` mints
  `run_id = str(uuid.uuid4())` and a wall-clock `created_at` on every `ah run`,
  so a regen writes different bytes from identical inputs. Verified still true
  after the ER-14 rebuilds. Also still carried: `fixtures/compiler` CRLF churn
  under Windows `autocrlf` â€” and see CLAUDE.md's new seal-EOL gotcha, which is
  the sharp edge of the same problem.
- **Sealed `v1.1` erratum, NOT folded in.** The `pm_direct_lending` row's
  `n_quarters: 195` counts MONTHLY BDC observations, not quarters. It was meant
  to ride the next reseal event; the ER-14 reseal (`AM-2026-08-18-001`) came and
  went and the value was **copied unchanged into
  `mappings/sleeve-mappings-v1.2.yaml`** (verified). It now needs its own
  amendment, or the next reseal after this one carried deliberately rather than
  hoped for.

## Resolved since the last revision â€” dropped from the board

Recorded once, so nobody re-opens them from an old copy.

- **ER-14** â€” CLOSED and released (above). It was the largest item on this board.
- **F5 (calibration drift)** â€” closed, batched into the same reseal as ER-14:
  F5a the CTA EWMA vol estimator and position cap, F5b `r2_train_val` restored to
  every PM row, F5c Student-t PM residuals with a block correlation.
- **The spine line (D-SP-4 / -6 / -8)** â€” closed at its second frontier and
  succeeded by stage 2; the spine v2 exam rulings it was waiting on were taken
  and sealed.
- **World 703's precedent line** â€” the carried follow-up asked whether it
  overstates its join tolerances by claiming "9 level factors". **The premise
  does not hold:** the phrase appears nowhere in
  `src/ah/presets/stress_1990.json` (checked string by string), nor in the
  successor `713` that inherits its precedent. The overstatement that did exist
  was `802`'s disclosure line, and it was corrected. Closed.
- **The local branch sweep and the probe worktree** â€” both done; the current
  sweep list is under owner decision 3 above.
