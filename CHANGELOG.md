# Changelog

All notable changes to this project are documented here. The project follows
[Conventional Commits](https://www.conventionalcommits.org/) and
[Keep a Changelog](https://keepachangelog.com/) conventions.

## [Unreleased] — Step 1 (data layer)

### Added
- **Campaign-2 A' — residual drift parameterization** (owner escalation
  path "B then A if needed"; B' measured and MISSED first). The B' sweep
  proved classifier-free guidance moves persistence monotonically the
  WRONG way (half-life 29.4→23.8 vs history 61.2 as scale rises) while
  sharpening drawdowns — the wrong lever by construction. A' makes trend
  tracking STRUCTURAL: the L3 network models deviations around
  conditioning-implied drift means (`bridge.conditioning_drift_means` —
  cpi ramp, equity constant drift, derived from the Δw components already
  in c_b, so the cb-v1 fingerprint is untouched). Dataset subtracts the
  means (`build_dataset(residual_drift=True)`); the sampler adds them
  back from the same raw c_b vector (exact train/sample symmetry, tested);
  every unit conversion restores them so the sealed tail auxiliary keeps
  scoring ACTUAL factor units (tested: fold units byte-identical across
  parameterizations). `FlowConfig`/`DiffusionConfig.residual_drift`
  omitted from `as_dict()` at its default so every pre-A' config hash —
  the sealed selection's included — recomputes byte-identical (recorded
  choice). Trainer refuses a config/dataset flag mismatch. 14 new tests.
  **Measured outcome: A' moves none of the four chased statistics — and
  the probes explain why.** Scoring the L1-implied target curves
  themselves (no L3 anywhere) reproduces the ensembles' numbers, so L3
  already tracks its conditioning; and the sealed-battery record shows
  the chased anchors were the SEVERE test's conditional 1966-84 values —
  under the sealed unconditional bands, cpi persistence PASSES. The
  genuine sealed defects are level-factor half-lives (reverting at the
  block-reassembly timescale) and equity/hml lost-decade excess (part
  start-state artifact). Full trace + revised owner options in
  `Instructions/campaign2-regime-fix-options.md`; A' stays as tested
  infrastructure, off by default.
- **The Tier-2 ship-gate chase: GATE G4 CLOSES** (owner-directed;
  fifteen live runs, every lever versioned). From WP4.5's honest 76.7% to
  the binding pair rule met at **96.7% / 100.0%** (runs 14/15, identical
  configuration). What it took, all on the record: gate-impl 1.0.3→1.0.6
  (each a false-positive correction argued against the sealed rule's own
  text — headline case, sentence-starters, market terms, modality,
  document furniture); prompts letter@1.1→1.4 / note@1.2→1.5
  (contrastive exemplars, role-not-name for real institutions, exact
  number formats); **pipeline v2** — the pre-gate self-check, ratified
  PRE-HOC by the owner (`AM-2026-08-02-004`) with the "first-pass"
  definition decided before any v2 run existed, and the
  two-consecutive-runs ship rule made binding after a lucky single pass
  (run 9, 96.7% unconfirmed at 90/96.7/90) was REFUSED; two harness bugs
  caught by their own guards (a literal backspace byte in a regex — the
  offline replay test; token-cap truncation amputating outlooks — the
  63.3% crater that diagnosed it). One true positive along the way: G4
  caught a letter naming The Federal Reserve. Tier-2 live-world authoring
  is ENABLED at exactly the shipped configuration; any change re-runs the
  frozen set. `G4-EVIDENCE.md` carries the closing line: **all four
  project gates resolved.** 3 new tests.
- **WP4.10 — the GenAI governance pack; Gate G4 scored, honestly open**
  (Step 4 closer). `governance/prompt-registry.yaml`: all four prompt
  families with versions, hash pins, regression links, and ship status
  (the authoring pair NOT SHIPPING at 76.7%; the committee STUDY-GRADE
  ONLY). **Injection testing on every payload path**
  (`tests/test_injection.py`): injected wire text rides into prompts as
  data, a draft that OBEYS an injection trips G3+G4, a committee decider
  that obeys emits an off-menu action the bounded contract rejects into
  the filed fallback — and the template engine is proven single-pass
  (payload values containing `{{…}}` are never re-expanded).
  `governance/eu-ai-act-mapping.md`: obligation mapping (transparency via
  renderer watermarking, traceability via G9, robustness via the frozen
  regression set) + the NIST AI RMF scaffold, counsel review flagged
  before client-facing reliance. `genai-track.md` updated to today's
  truth. **`governance/evidence/G4-EVIDENCE.md` scores all six gate
  criteria**: five evidenced, criterion 1's Tier-2 half UNMET at 76.7% <
  95% — so **Step 4's build is COMPLETE and Gate G4 is OPEN on one named
  item**, with its consequence enforced (live Tier-2 disabled) and next
  levers recorded. The same honest posture as G1's mark_lag. 4 tests.
- **WP4.9 — the actor validation study: run, measured, deferred honestly**
  (Step 4; `ah/artifacts/validation.py`, `scripts/run_actor_validation.py`,
  `governance/evidence/ACTOR-VALIDATION.md`). The ablation arms (heuristic,
  seeded random-within-bounds, hold-course) and the live Claude committee
  across three personas ran on **identical worlds, windows, and data** (the
  sealed comparison rule). Two live runs, the instrument debugged before
  its readings were believed: run 1 measured a 70% fallback rate that one
  probe call diagnosed as HARNESS pathology (a truncating token cap and a
  prompt that never showed the action element's shape — the model wrote
  `"action"` for `"verb"` and the bounded contract rightly rejected it);
  fixed on the correct levers (`committee-prompt@1.1`, element shape
  explicit; 1024 tokens). Run 2's honest numbers: **fallback rate 0.20**
  (residual model format drift, each rejection filed) and **persona
  sensitivity 0.78** — 78% of decision cells show persona disagreement,
  reported as PROMPT SENSITIVITY per the plan's pitfall list, never sold
  as insight. Effect sizes are structurally unable to travel without their
  across-world dispersion and world count. **Deferred per owner decision
  D-K4-5**: the human-cohort arm — and with it the too-rational pathology,
  which is DEFINED against human cohorts and gets no proxy number in its
  place. The standing rule rides in the evidence: no client-facing actor
  claim precedes the full study, and the study is INCOMPLETE until the
  human arm runs. 5 tests.
- **WP4.8 — the AI committee: bounded, briefed, filed, beatable** (Step 4;
  `ah/artifacts/committee.py`). The four disciplines from the plan,
  structural: **bounded** — model output parses through the typed decision
  contract, so an off-menu or declared-but-unimplemented action is
  rejected and never coerced; **briefed** — the briefing is deterministic
  code over `RevealedTape`, inheriting the information wall (there is
  nothing beyond the pointer in the input object), reported-plane weights
  and the last N wire items alongside; **filed** — every decision carries
  a rationale (a decision without one refuses), the persona id, prompt
  version (`committee-prompt@1.0`) and model id, and emits its minutes as
  a wire payload for the chronicle; **beatable** — the heuristic ablation
  is both the fallback (invalid model output → heuristic decision WITH
  the failure quoted in the filed rationale, never erased) and the
  wp4-09 baseline, joined by seeded random-within-bounds and hold-course.
  Personas are configuration rendered into the prompt, never code paths —
  their differences get measured as prompt sensitivity, not celebrated.
  Deciders are injected callables (offline tests; live Claude behind
  `--live` when wp4-09 runs the comparison). 11 tests.
- **WP4.7 — actor windows: calendars, triggers, the playbook, wargames**
  (Step 4; `ah/artifacts/windows.py`). Real decisions are not uniformly
  spaced: calendar windows carry the cadence, and **event windows** open
  on the plan's closed trigger list (spread breach, gating, mark
  catch-up, collateral call). The window log is append-only and typed on
  the retrofit's decision contract — **the RFR-89 re-check ran at the
  moment of first consumption and passed** (RFR-90): two actions in one
  window survive record, count, and export un-collapsed. The
  **pre-commitment playbook** freezes at t₀ by order-sensitive hash;
  triggers fire, executions record, and recording an execution for a rule
  that never triggered refuses — adherence is measured when the moment
  comes, not on paper. Its outputs are byte-shaped for the SEALED
  adherence metric **without importing it** (judge/defendant separation;
  format compatibility proven in the test, where importing the judge is
  legitimate). **Wargame sessions** hold one world, one seed, one
  decision-alpha version by construction, and export the cohort exercise
  (every team's windows) as evidence for the sealed metrics — scores are
  never computed actor-side. 9 tests.
- **wp5-00 — the Step 5 scorecard, frozen late and said so** (owner-ordered
  2026-08-02). The plan required the WP5.1–5.2 metric definitions frozen
  during Step 3; the obligation slipped to mid-Step 4 and is now
  discharged with the lateness on the record (`AM-2026-08-02-003`), not
  smoothed over. Sealed together in **`pre-registration-g5.lock`**
  (`sha256:ac6f2a3c…`, the third use of the Step 2 seal mechanism):
  `step5-evaluation-protocol.yaml` (expanding-window walk-forward, the six
  benchmark policies, Wilcoxon with effect sizes, the identical-worlds
  comparison rule, the one-shot holdout covenant) and
  `ah/eval/decision_metrics.py` — every metric an executable formula with
  its worked example asserted by test: **drawdown surprise as the sole
  pre-stated PRIMARY** (the p-hacking defense, sealed), decision alpha vs
  the hold-course twin, per-window alpha with an exact telescoping
  identity (this seal is what `decision_alpha_version: "1.0"` on every
  RunRecord formally refers to), forced-sale cost, liquidity-shortfall
  probability, funding-ratio tail, breach duration, pre-commitment
  adherence (denominator = triggered rules only; no credit for calm
  paper). The G5 wrapper refuses documents that disagree with the code;
  the seal guards patrol a third boundary (`TestG5SealBoundary`); tamper
  of one character in the sealed code fails verification, by test. What
  the amendment states precisely: nothing these metrics judge exists yet
  — wp4-07's windows, committees, and wargames all land AFTER the seal.
  12 tests.
- **WP4.6 — live mode: sealed reveal, three tape rules, the information
  wall** (Step 4; `ah/artifacts/live.py`). The decade is precomputed and
  **sealed at t₀** (SHA-256 over the tape; a single mark moved one
  millionth fails verification, by test). The three **tape-selection
  rules** — seeded-random, **pre-stated** percentile of terminal wealth,
  pinned id — each record complete provenance including the sealed hash;
  the percentile parameter refuses to be supplied after the fact. The
  **reveal pointer** is pure arithmetic over caller-supplied elapsed time
  (no clock reads, even here). The **information wall is structural**:
  `RevealedTape` copies only the revealed months at construction, so data
  past the pointer never enters the object — there is nothing beyond the
  wall to leak (asserted down to `data.base is None`). Chaptered
  generation exists **behind a flag, default OFF**, with waypoints sealed
  at t₀ (order-sensitive hash). Notification policy: **push only regime
  events**, everything else to the digest. **The v1.3 WorldSpec schema is
  RATIFIED** (owner approval 2026-08-02, same day as the draft):
  `schemas/worldspec-v1.3.schema.json` promotes `temporal_delivery` to a
  core block (calendar + reveal + tape-selection + notification policy,
  fully sub-schema'd — the percentile parameter lives in the spec, which
  is what makes it pre-stated); the version pattern widens as v1.2's did
  (1.0.x/1.2.x sealed documents stay valid unchanged), and
  `extensions.x_temporal_delivery` remains the migration path until v1.4.
  `read_calendar` prefers the core block, falls back to the extension,
  and **refuses a document carrying both** — two declarations is a
  contradiction, not a preference. The draft is retained in
  `Instructions/` as the approval record. 13 tests.
- **WP4.5 — the authoring regression set: frozen first, measured when the
  meter runs** (Step 4; `fixtures/authoring_regression/`). The G4-pre
  membership rule made concrete: **30 deterministic payloads** — 10
  letters ({bull, crash, gate_event, comp_gap, quiet} × both held
  entities) + 20 notes (× the disagreeing house pair × two subjects) —
  generated byte-identically by `scripts/gen_authoring_regression.py`,
  with **per-payload SHA-256 hashes in the manifest as the executable
  freeze** (any drift fails CI; the grid's completeness and the pair's
  built-in disagreement are asserted). `run_authoring_regression.py`
  runs the set live through the WP4.4 pipeline (Claude, Step 0 adapter
  pattern) and replays recorded outputs offline forever; evidence scores
  the first-pass rate against the frozen ≥95% ship gate. **Five live runs,
  the trajectory on the record**: 3.3% → 16.7% → 66.7% → 66.7% → **76.7%**
  first-pass, zero fallbacks in the last three runs. Runs 1–2 diagnosed
  GATE false positives (salutations, Title-Case headlines, market terms,
  outlook modality — fixed as versioned implementation lineage,
  `gate-impl/1.0.1` → `1.0.2`, each aligning code to the sealed rule's
  plain meaning); runs 4–5 isolated genuine model first-draft slips
  (in-character "guarantee" language, `9%` for `+9.0%`) answered by
  **prompt version bumps** (`letter@1.1`, `note@1.2`) with hash pins
  updated and the full set re-run each time, per the frozen rule. One
  true positive worth the price of the whole exercise: the model derived
  a 115bps spread differential and **G1 caught it**. **THE SHIP GATE IS
  NOT MET** (76.7% < 95%): no Tier-2 prompt version ships, live-world
  Tier-2 authoring stays disabled, and the manifest records both the
  measurement and the next levers (few-shot exemplars, pre-gate
  self-check — by version bump, as always). 7 tests + the offline replay
  over the run-5 recordings.
- **WP4.4 — the Tier-2 authoring pipeline: author, gate, retry, fall back**
  (Step 4; `ah/artifacts/payloads.py`, `prompts.py`, `gate.py`,
  `author.py`). The first LLM-adjacent code in the repo, built under the
  frozen G4-pre terms. **Payload builders are deterministic code, never an
  LLM**: P-LETTER/P-NOTE per the vendored spec §2, every figure
  pre-formatted so authors copy rather than compute, and **arc beats
  stripped at the dateline inside the builder** — a leak upstream is
  structurally impossible. **Prompts are the spec's §3 text verbatim** at
  the spec's version ids (`author-prompt/letter@1.0`, `note@1.0`), with a
  **template-hash pin test** making the freeze executable: editing a
  prompt without bumping its version fails CI first. **The consistency
  gate G1–G8 runs in the frozen order and split** (G1–G5+G8 block, G6
  advisory-and-says-so, G7 fog discipline): derived numbers block (G1),
  unsubstantiated events block (G2), future quarters/years block (G3,
  keyword rules — the spec's leak-checker prompt is v1.1, recorded),
  unknown proper nouns block (G4), promises/advice/no-hedging block (G5),
  stripped marking blocks (G8); G9 is the chronicle record's own
  refusals, already live since WP4.1. **The pipeline retries twice with
  violations attached, then falls back to a Tier-1 substitute** recorded
  as tier-1 authorship — boring but honest beats fluent but wrong. The
  author is an injected callable: tests run synthetic authors offline
  (pytest-socket enforces); live Claude authoring arrives with the
  regression set (WP4.5) behind `--live`. 17 tests.
- **Retrofit R-1 (DN-5) — decision-schema shaping, before the engine work
  exists** (owner-tasked; shape only, no behaviour). The typed decision
  contract (`ah/artifacts/decisions.py`): a window carries a LIST of typed
  actions (singleton never special-cased), `reached + []` is a first-class
  "chose to do nothing" distinct from `not_reached` (which may carry no
  actions), `set_pacing`/`sell_secondary` are declared in the enum and
  **rejected with an explicit not-yet-implemented error** — never silently
  dropped — and `cost_charged` is engine-written only (`engine_charge` is
  the single writer; client payloads carrying it refuse). Three inert
  **version stamps** on every new RunRecord (`decision_schema_version`
  "1.0", `decision_alpha_version` "1.0", `twin_definition` "policy") via an
  in-place additive migration — a pre-change database upgrades with legacy
  rows reading back stampless; `verify_run` and the replay anchor
  untouched. The **leaderboard** table is created before any row exists
  anywhere, with `(world_id, seed, decision_alpha_version)` in the unique
  constraint from birth and the version a required argument on every
  repository function. UI reservations (three-series analysis layout,
  per-window annotation slot) recorded as experience-deltas **E7/E8** per
  D-K4-2. **Survey finding, per the task's own ask**: no code assumed a
  single action per window because WP4.6/4.7 did not exist yet — the
  retrofit is contract-first, and that assumption gets re-checked when
  WP4.7 consumes the contract (RFR-89). 11 tests.
- **WP4.3 — the World Bible: checks B1–B6, the entity screen, cast binding**
  (Step 4; `ah/artifacts/bible.py`). The continuity database and safety
  enforcement point, executable. Schema-first validation, then the six
  creation checks — B1 real-entity screen over every named entity; B2 arcs
  inside the horizon, strictly ordered; B3 economic consistency (a stress
  beat before the world's credit-stress window blocks, unless flagged
  idiosyncratic; **no window supplied = B3 warned and NOT passed**, never
  silent); B4 the disagreeing pair (the schema's enum already guarantees
  valid priors, so B4 enforces that the houses' priors don't converge); B5
  trade-dress screen on mastheads; **B6 referential integrity** (ratified
  D-K4-1) — the example bible's `harborlight-implicit` danglers are closed
  to `institution` per the reconstruction notes' own recommendation, and
  the golden test now demands all six. The **entity screen** is a vendored
  snapshot with its version in every report
  (`fixtures/entity_screen/`): SEC EDGAR company list (10,412 issuers,
  fetched 2026-08-02, sha256 recorded) + curated global financial names +
  media tokens; normalized and legal-suffix-stripped exact matching, with
  the **GLEIF golden-copy integration a stated deferral in the manifest**
  (~430MB full file; narrowing of D-K4-4 flagged, not silent).
  `bind_cast` binds `held_by_institution` entities to Step 3 hero funds
  1:1 — a named GP has numbers behind it or the binding refuses. 13 tests.
- **WI-I6-1 — the pacing table: distribution rates out of the code, into a
  file** (owner-approved fix for inspection I6's red flag).
  `mappings/pacing-parameters-v1.0.yaml` is now THE source of truth for
  closed-end pacing parameters — every value labeled with its source class
  (measured / published / chosen), the register's ALB-A fallback stated, and
  two open questions on the record (PQ-1 functional form vs
  Takahashi–Alexander, re-opened only with ALB-A data; PQ-2 the
  yield-rate/income-cap double duty). `scripts/inspect_pacing.py` prints the
  table and its implied curves on demand; `tests/test_pacing_artifact.py` is
  the drift guard — a fixture that disagrees with the table fails CI. The
  rescale itself: pm_buyout `yield_rate` 0.01 → **0.55** (the fixture's own
  flows snapshot now reconciles with its parameters to 2%). **The sealed G1
  drought verdict is measured ROBUST to the rescale**: trough ratio 0.5442
  (old) vs 0.5433 (corrected), both inside the sealed [0.45, 0.55] —
  `governance/evidence/WI-I6-1-SENSITIVITY.md`, a robustness note, not a
  reseal; the sealed replay, its evidence, and the G3 lock untouched. All 91
  fixture-consuming tests pass unchanged. 4 new tests.
- **WP4.2 — Tier-1 templates: the volume, at zero marginal cost** (Step 4;
  `ah/artifacts/templates.py`). Every builder is a pure function of
  tape-shaped inputs — no LLM, no RNG, no clock; same tape, same words, by
  test. Numbers pre-format to publication precision (`fmt_*`) so downstream
  authors **copy rather than compute** — the G1 discipline inherited by
  construction. **Amendment Delta 2 lands**: capital call, distribution,
  coverage-band crossing, forced sale, secondary discount — all in the **cash
  account's voice** (the honest third plane, per the delta verbatim), with
  the **forced-sale item reading like the distress it is** (headline-cause,
  named sleeves, stated haircut; refuses to typeset without them). Plus the
  furniture: morning digest (quiet days included), data-release pages where
  the revision column is content, central-bank statements with stance
  language keyed deterministically on the rate move, quarterly statements
  with **peer percentiles computed from ensemble bands** (monotonicity
  checked, never authored), and the board pack that refuses to assemble with
  any of its five sections empty. 11 tests.
- **WP4.1 — the artifact service: calendar, chronicle record, renderers**
  (Step 4; `ah/artifacts/`). The storyteller layer's rails, before any
  storyteller exists. The **calendar** rides the WorldSpec schema's sanctioned
  `x_` escape hatch (`extensions.x_temporal_delivery.artifact_calendar`) —
  the vendored schema has no core `temporal_delivery` block, the conflict the
  plan/schema rule requires flagging: promotion to a core block awaits an
  owner schema minor bump. Declarations validate against the vendored schema
  untouched; scheduling is pure arithmetic (monthly / quarter-end / `event` =
  runtime-only), deterministic under declaration reordering. **Publications
  ride the existing append-only chronicle** as `type="artifact"` entries (one
  immutability story, no migration) carrying the sealed G9 record — type,
  dateline, author tier, gate result, payload hash, prompt version, model id,
  retry count — and an incomplete record **refuses to publish** (a tier-2
  record without prompt/model provenance is exactly what G9 blocks). Five
  **renderers** (wire item, release page, statement, letterhead, board pack)
  apply the simulated-world watermark IN the renderer, and `export()`
  re-applies it idempotently at the boundary. Payload hashing is
  canonical-JSON SHA-256 (key order never matters). The boundary guard is the
  first test: `ah/core`, `ah/gen`, `ah/port` never import the artifact layer.
  13 tests.
- **WP3.11 — the 2022 end-to-end reproduction: G1 completion, and the honest
  answer is FAIL** (Step 3; `G1-EVIDENCE.md`). Observed 2022–23 history through
  the full chain, scored by `ah/eval/episode2022.py` against the criteria sealed
  at G3-pre *before any judged code existed*. **Four criteria pass** — the public
  drawdown exactly, **`distribution_shortfall` at 0.544 through the full chain**
  (the P-A calibration held beyond the point function), secondary pricing,
  coverage. **`mark_lag` fails on its HF half (−3.1 months)**: the mapped HF
  composite troughs at June's first leg, before September's public trough — the
  genuine test the measured-zero-stickiness decision preserved, returning its
  genuine answer. Diagnosis on record: the sealed HY omission and/or stickiness
  resident in 2021–23 — both next-campaign questions, neither a tuning knob.
  `private_weight_breach` fails as a *permitted named* failure (9 months early —
  the denominator effect arrived at the first leg). **Tier 1 beats tier 0**
  (2 fails vs 3: constant G produces no drought at all), so tier 1 ships under
  the sealed beats rule with the failure reported, per the plan's own DoD.
  **`AM-2026-08-02-001`** seals the scorer (pure, engine-free — the judge never
  imports the defendant) — **post_hoc: true, stated plainly**: the replay ran
  first; what bounds the hazard is that every formula quotes its sealed sentence
  and the result sealed alongside is a FAIL. Lock at `sha256:5a7186e5…`;
  the boundary guard now covers the scorer as a third entry point. 13 tests.
- **WP3.10 — hero funds** (Step 3). `ah/port/heroes.py`: 3–5 named synthetic
  funds split from a cohort (log-normal weights on per-hero 7919-strided seeds,
  `n_funds=1`, `dispersion_draw` = weight quantile), every hero contract-valid,
  and **reconciliation as an identity**: every extensive field sums exactly to
  the parent, with a test that catches a cooked book. Name↔World-Bible binding
  deliberately left to Step 4. 4 tests.
- **WP3.9 — the liability proxy** (Step 3). `ah/port/proxy.py`: LSMC discipline
  (Krah et al.) with a polynomial basis a reader can audit — disjoint
  fit/validation scenario sets (7919 rule), **pre-stated error bounds declared
  before any fit** (0.5% validation / 1.0% capital-region), and the capital
  region tested point-by-point, not on average. **The fit refuses to ship when
  underpowered** (degrees 4–5 fail their own bounds honestly; degree 6 passes
  at 0.16%/0.03%); the proxy refuses to extrapolate outside its fitted region.
  Portfolio metrics run direct, per the plan's boundary. 5 tests.
- **WP3.8 — the pension twin** (Step 3). `ah/port/twin.py`: parameterized DB
  liability profile (v1-simple, stated; member-level projection is a later named
  refinement), funding ratio, rate/inflation shocks consuming the frozen WP2R.6
  hedging/collateral contract. **Actuarial directions and magnitudes pinned by
  test** (|ΔPV|/PV ≈ duration×Δy; ~19y scheme duration). **The gilt mechanic
  end-to-end**: a 250bp shock exhausts collateral headroom and force-unwinds the
  hedge at the worst moment — logged, never silent; an under-hedged plan's
  funding volatility is liability-dominated (3×+, tested). **The hold-course twin
  takes the crisis state only to ignore it** — §5.1's cost-of-flinching
  counterfactual, explicit in the signature. 8 tests.
- **WP3.7 — the portfolio engine** (Step 3). `ah/port/engine.py`: the §8
  waterfall in order (distributions in → calls out → spending → shortfall
  resolution: liquid pro-rata, then forced secondary at the 0.81-NAV public
  anchor haircut), **every forced sale logged** with period/amount/cause/sleeves.
  **§7's mechanic implemented and tested**: spending rides the trailing average
  of *reported* value — it falls <15% while true value crashes 40%, exactly when
  liquid assets are scarcest. **The plan's acceptance verbatim**: an
  over-committed institution in a crisis produces forced sales; a well-buffered
  one does not. Breach detection on both bases. 7 tests.
- **WP3.6 — vehicle mechanics** (Step 3). `ah/port/vehicles.py`: notice-period
  maturation, gate proration with rolled excess, side-pocket withholding and
  resolution, and `realizable_by_horizon` — the 30/90/180-day arithmetic of the
  terms, not the stated NAV (lockups zero it; gates cap each dealing date).
  **The 2022-23 evergreen mechanic emerges from rules**: stressed demand + the
  cap → the queue ages and fulfilment collapses with *no gate flag in the state
  to declare* — the lock-in is emergent, which is the point. ALB-F base rates
  never delivered: the stress bands are authored (kind C) against the public
  episode record and say so. 7 tests.
- **WP3.4 — tier 1, the market-sensitive cashflow engine** (Step 3;
  `linkage_version: tier1-public-0.1`). `ah/port/cashflow_tier1.py`: the same
  cohort recursion as tier 0 with the linkage ON — **the one-model identity is a
  passing test** (linkage off + fees off reproduces tier 0 flow-for-flow) — plus
  the structural mechanics: management fees with the basis change
  (committed→NAV), European carry above hurdle, recycling through the R14
  recallable machinery, subscription-line deferral, extension behavior.
  **`f_dist` calibrated to public anchors**: coefficients solved so P-A's
  drought-depth center (0.50) holds exactly at the *measured* 2022 state
  (dd 24.8%, IG spread ratio 1.253), influence shared in P-A's own 0.37:0.30
  elasticity ratio; substitutions documented (log P/D→drawdown; HY→IG, HY being
  a sealed missing factor). **`f_call` near-flat** (Delta 3: the self-funding
  breakdown is distribution-side) — a severe drawdown moves calls 3%.
  **No crisis/regime term, structurally** — continuous states only, pinned by a
  signature test; the adds-nothing regression runs at the WP3.11 replay. PM
  growth loadings are DN-5 priors **adopted as chosen (kind C)**, never called
  estimates. **`AM-2026-08-01-005`** (pre-hoc, the fifth) seals the linkage into
  the G3 lock (`sha256:a2bffa6e…`). 11 tests incl. stress-starves-distributions
  (−25%+ dists, −<10% calls).
- **WP3.5 — tier 0, the transparent cashflow benchmark, frozen before tier 1
  exists** (Step 3). `ah/port/cashflow_tier0.py` runs the register's classic
  constant-G TA **through the same cohort recursion tier 1 will use, linkage
  off** — one model, never two. The cohort recursion aligned to the register's
  canonical form (`RD(t) = Y·(t/L)^B`) with the flagged terminal convention
  resolved: at `age ≥ L`, full liquidation and the undrawn commitment lapses.
  **G measured, not adopted**: 12.05%/yr, the annualized mean public total return
  over 1,134 train+val months — PME-neutral by construction ("private assets are
  public assets with a J-curve", the strawman tier 1 must beat). The plan's
  historical-simulation leg is UNPARAMETERIZABLE (ALB-A/C never delivered) and
  recorded with its trigger. **`AM-2026-08-01-004`** (pre-hoc, the purest case:
  the comparator doesn't exist yet) seals the spec into the G3 lock
  (`sha256:5e555a4f…`). 6 tests: J-curve shape, terminal wind-up, 12%-fund
  moneyness, bit-determinism.
- **WP3.3 — the forward smoothing kernel** (Step 3). `ah/port/smoothing.py` + the
  frozen θ artifact (`mappings/smoothing-kernel-v1.0.yaml`, `smooth-2026.08`,
  sealed pre-hoc by `AM-2026-08-01-003` under the settled rule: **estimates seal,
  engines don't** — an unfrozen θ would let the sealed `mark_lag` criterion be
  gamed). **SM-10 proven as a test**: smooth with known θ, hand the result to the
  *sealed* de-smoother, it recovers the weights and the truth — reported and true
  are one model seen two ways. **The measured negative ships as measured**:
  stickiness calibrated **0.0** on in-sample NBER stress (θ0 *rose* in stress,
  0.793→0.833 — mildly opposite DN-5 §5.3's prior); the mechanism is implemented
  and inert, and WP3.11's sealed criterion becomes a genuine test of whether
  2022's mark lag emerges without it. Calibration on 2021–23 **refused** (holdout
  + judging episode), a recorded deviation in the seal's favour. The Geltner
  family is named UNPARAMETERIZED (no PM data) and raises rather than pretends.
  10 tests.
- **WP3.2 — factor → sleeve mappings** (Step 3). `scripts/estimate_sleeve_mappings.py`
  estimates DN-5 §3.2's pattern on the six regression sleeves' **de-smoothed**
  composites (asserted byte-equal to the sealed G3 reference), train+validation
  only, with sign constraints + shrinkage toward the DN-5 priors (SM-4) via bounded
  ridge; structural zeros never enter the solver. **`hf_cta` is a rule, not a
  regression** (DN-5 §3.4): 12-month TSM overlay on generated paths, vol-targeted,
  RNG-free, warm-up flat. Frozen artifact `mappings/sleeve-mappings-v1.0.yaml`
  (**`map-2026.08`** — WorldSpec's `mapping_version` has its first real value);
  runtime applier `ah/port/mapping.py` (correlated residuals per the platform seed
  rule). **The D1 exhibit delivers**: de-smoothed equity betas 30–80% above
  smoothed (event 0.32→0.42, multi 0.12→0.22). HY/commodities loadings recorded as
  **structurally unestimable** (the sealed missing_factors), never silent zeros.
  **`AM-2026-08-01-001` — the project's first pre-hoc amendment**: estimator,
  artifact and applier joined the G3 lock (`sha256:8f41bafb…`) exactly as the
  sealed document announced, before any result existed. Register **D4 CLOSED**:
  constant betas per DN-5 §4.3; regime variation reaches sleeves through the
  generator's factors, not the loadings. `MAPPINGS.md` carries fit/OOS/regime
  diagnostics (macro's R²=0.05 is DN-5's own prediction, reported not hidden).
- **WP3.1 — the runtime state objects** (`ah/port/`: cohort, sleeves, portfolio —
  Step 3). Liquidity-spine v0.2 §3 state + §4 recursions as pure objects (no I/O,
  no RNG, no clock; linkage responses injected as floats, Phase-A subset = 1.0).
  Every object **round-trips through the frozen v1.0 contracts and re-validates on
  serialize** — a state that can't serialize is a bug at mutation time. The
  denominator effect is first-class: coverage and private weight on **both bases**,
  plus `coverage_liquid` (P-B's binding-ratio caveat). Recall **unwinds paid-in**
  (stated LP convention keeping `paid_in <= committed` for the cohort's whole
  life); the evergreen queue ages with no gate declared; forced sales are a logged
  event list awaiting WP3.7's waterfall. 26 tests incl. a 15-year invariant sweep
  under wild returns; `ah.port` at 96% coverage (G3 floor 85%); ruff + pyright
  (full strictness — `port/` is not in the relaxed pyright environments) clean.
- **wp3-00 — G3-pre SEALED** (`pre-registration-g3.lock`, `sha256:d21910da5914…`,
  13 files; owner-approved 2026-08-01; the mint mechanically refused until the
  owner flipped the flag). Step 3's rules frozen **before any of the code they
  judge exists**: per-modeled-sleeve tail thresholds for the 7 HF sleeves
  (measured from de-smoothed train+val history, PM sealed as structurally
  unavailable with delivery as the trigger), the 2022 episode-reproduction
  criteria (measured −24.8% public drawdown anchor; P-A drought depth; the
  0.81 NAV secondary anchor; NaN = fail everywhere), and the tier-0-beats rule.
  Judged code: `ah/eval/sleevetails.py` + `ah/eval/g3seal.py`, both inside the
  lock (the boundary guard's first run caught `g3seal.py` undeclared — RFR-83's
  class, fixed before minting). The guard now binds both locks on every suite
  run. Review basis recorded in the register (`S3-G3PRE-SEAL`), including that
  W11 attendance is not evidenced. **WP3.2 estimation and cashflow code are now
  unblocked** — and judged by rules older than themselves.
- **WP2R.9 — Step 2R closes: full-stack regression under the frozen contracts;
  tag `v0.3.0-contracts`** (`CONSOLIDATION-EVIDENCE.md`). G0 CLI end-to-end on a
  migrated v1.2 preset (**replay MATCH**), Step-1 layer green with the first real
  delivery current, Step-2 battery evidenced by WP2R.5's bit-identical
  reproduction, and **WP2R.4's deferred clause discharged**: `hier-flow-v1` from
  its pinned, hash-verified checkpoint emits a generator-output document that
  validates with every tensor digest re-derived. **Zero digests re-baselined**
  (nothing numeric moved all step); zero open retrofit items assigned to 2R
  (R1–R7, R13–R14 all absorbed, each remaining register row has a named owner or
  trigger); the seal untouched at 33 files. No Step 3 work is blocked by an
  unfrozen interface.
- **WP2R.2 — HF de-smoothing at sub-strategy granularity (R2)** (Step 2R; owner
  decision, option b). The 7 never-delivered group-level `albourne.hf_*` series are
  retired and **21 sub-strategy series registered** (the 20 HedgeRS AW indices +
  MS Diversified), with the WP2R.2 id rule: *the intake `strategy` code IS the
  registered id fragment*, so canonicalization and the registry agree by
  construction. Taxonomy bumped to **v1.1** (mapping-file change, as designed).
  - **The manual-intake last mile now exists** (`apply_intake_frames` +
    `ah data intake apply`): accepted drop → vintage → QC → pointer, exactly
    `refresh()`'s discipline; unregistered ids are a loud error. Until now an
    accepted intake never reached the vintage store — half of **RFR-88**, whose
    other half (the PM code family still keys `albourne.buyout`, not the
    registered id) bites on first PM delivery and is recorded.
  - **First real delivery executed**: `scripts/export_hedgers_intake.py` bridges
    the licensed HedgeRS cache (local only, never committed) into a 5,914-row
    drop; vintage `2026-08-01.2` is **current** (21 written + 37 carried). The
    new registrations use `sla_days: 75` — set at authorship to the vendor's
    real month-boundary cadence (RFR-86's lesson applied to a *fresh* number,
    which is correction, not gate-tuning; the French SLA decision stays yours).
  - **`DESMOOTHING.md` authored** (it never existed — D1 register note): GLM
    MA(k) primary + Geltner secondary over all 21 series, acceptance asserted in
    the generating script (σ-ratio ≥ 1, means unchanged ≤ 5e-4, no beta falling
    under material weights). **The finding matches the plan's prediction**:
    material smoothing in credit/structured credit/ILS/distressed (σ-ratio up to
    1.43, equity beta rising 0.25→0.38 on distressed), negligible in
    macro/CTA/GAA. Parameters and diagnostics only — no licensed values leave
    `data/`. `tests/test_intake_apply.py` (4) covers the apply step.
- **WP2R.7 — WorldSpec v1.2: the resolved generator namespace** (Step 2R).
  `schemas/worldspec-v1.2.schema.json` becomes the active contract (v1.0 stays
  vendored, untouched): `generator_id` now carries the real registry ids —
  **`hier-flow-v1`, the G2-promoted default**, `bootstrap-v1`,
  `joinery-bootstrap-v0`, `hier-diffusion-v1`, `toy-v0` — while the three legacy
  names stay as deprecated members so the **sealed 1.0.x fixture worlds revalidate
  and run untouched** (`bootstrap-stratified`→`bootstrap-v1` and, new,
  `conditional-diffusion`→`hier-diffusion-v1` via registry aliases;
  `signature-mmd` stays nameable-but-unrunnable, matching its RESERVED card).
  `spec_version` widens to `1.(0|2).x`; `engine_defaults.taxonomy_version`
  (optional) references the WP2R.1 sleeve namespace. Presets regenerated at 1.2.0
  **by their own script** (one line per file). "V-rules unchanged" is a checked
  fact: a test strips the three declared changes and asserts v1.2 == v1.0
  byte-for-byte at the JSON level. The plan's "finalized `temporal_delivery`
  block" turned out to be defined **nowhere** — deferred to Step 4 as RFR-87
  rather than authored from a single clause of a later plan. 22 tests.
- **WP2R.5 — frozen-vintage reproduction and the rolling-refresh handoff** (Step 2R).
  - **G2's numbers reproduce bit-identically from the frozen vintage.** The
    verdict-bearing grid subset (promoted `hier-flow-v1` × 3 seeds *retrained from
    the sealed training seeds*, benchmark `bootstrap-v1` × 3) re-run end to end in a
    worktree pinned at `v0.2.0-g2`: **zero numeric differences** against the
    campaign originals across every `battery.json`/`summary.json` — training
    determinism holds, not merely sampling determinism. Benign diffs (wall clock;
    the lock digest, which legitimately re-sealed between the runs) and the
    comparator's own initial `nan != nan` bug are recorded in
    `governance/evidence/WP2R5-VINTAGE-HANDOFF.md`. Diffusion/ablation cells
    deliberately out of scope (≈4.6× cost, not verdict-bearing), stated.
  - **Rolling refresh handed off, honestly:** the "monthly cron"
    (`data-monthly.yml`) never stopped — it runs on origin against a temp volume;
    the local `--live` refresh wrote vintage `2026-08-01` and **QC quarantined it**
    (five `french.*` series at 61d vs a 60d SLA — a month-boundary cadence
    collision, RFR-86, owner's call; deliberately not "fixed" by widening the SLA in
    the WP judged by it). The pointer correctly holds at `2026-07-26.1`.
    `fred.SAHMREALTIME`'s first fetch (798 rows; `min_start` 1959-12 now verified
    live) waits in the quarantined vintage by design. Gap register current at 63
    series; campaign vintage already pinned per-component in the model inventory.
- **WP2R.6 — portfolio/institution state extensions (R6, R7), schema-level only**
  (Step 2R). `schemas/portfolio-institution-state-v1.0.schema.json` +
  `ah/core/institutionstate.py` (same dual-validation pattern): rates/inflation
  hedge ratios; the **collateral pool** — eligible assets with haircuts, posted,
  and *headroom*, the variable the 2022 gilt episode was about; **explicit and
  pass-through leverage** (ratio-of-NAV, 1.0 = unlevered); portfolio fee-drag
  aggregation; per-liquid-sleeve transaction-cost defaults; and the **FX hedge
  ratio, present but inert at 0** — consistent with sealed R5 (no v1 FX factor)
  while letting the contract survive the next campaign's FX block unchanged
  (S2R-FX-NEXT-CAMPAIGN). A stub DB-pension-shaped institution validates and
  round-trips (`fixtures/state/institution-stub.json`); Step 3's plan vocabulary
  is the field vocabulary, pinned by a test. Implementation is WP3.7/WP3.8's,
  deliberately not built here. 10 tests; new core module at 100% coverage.
- **WP2R.3 — the sleeve/vehicle state schema freeze (R3, R14)** (Step 2R).
  `schemas/sleeve-vehicle-state-v1.0.schema.json` implements the spec's §3 with the
  **three private vehicle types first-class** (closed-end cohort, open-ended sleeve,
  evergreen vehicle — the queue block exists *only* on evergreen, pinned by a test)
  plus the liquid funding sleeve, discriminated by `vehicle_type`. R14's
  recycling/recallable state is explicit and required (`recallable_balance`,
  `cumulative_recycled`); the granularity switch is exactly `n_funds` +
  `dispersion_draw` (spec §5 — same object for sleeve, cohort, and hero-fund modes).
  `ah/core/sleevestate.py` is the pydantic mirror with the WorldSpec dual-validation
  pattern (jsonschema first), **strictly stricter on exactly two documented
  cross-field invariants** JSON Schema cannot express (`paid_in <= committed`,
  `recallable_balance <= cumulative_distributions`) — the agreement test asserts
  both the agreement and the divergence set. Four hand-authored examples
  (`fixtures/state/*.example.json`) round-trip bit-faithfully; example sleeve ids
  resolve against the WP2R.1 taxonomy. 32 tests; the new core module is at 100%
  branch coverage inside the `ah.core` gate.
- **WP2R.1 — taxonomy freeze and the Albourne mapping (R1, R13)** (Step 2R).
  `taxonomy/sleeves.yaml` — the platform's own `sleeve_id` namespace, 61 sleeves over
  17 groups from the sleeve-vehicle-state spec's full candidate breadth, with
  `modeled_in_v1` marking the build list (7 HF + 9 PM, inside the spec's recommended
  ranges, at exactly the granularity of the 16 registered `albourne.*` return series).
  `taxonomy/albourne_mapping.yaml` — the vendor boundary: every registered Albourne
  series maps to exactly one sleeve (cashflow packs covered by an explicit non-sleeve
  list so nothing is unaccounted for); the 20 real HedgeRS AW sub-strategy indices
  (name + index id, from the HFModelling scope inventory) map to platform sleeves
  **by the platform's grouping, not HedgeRS's** (equity market neutral sits in Equity
  per spec §1.1); the two Universal composites are excluded *with reasons*, because an
  excluded code and a forgotten code must be distinguishable. **Secondaries is its own
  sleeve (R13)** with the never-cloned-from-buyout note pinned by a test.
  `ah/data/taxonomy.py` loads + validates both files (version skew, unknown targets,
  mapped-and-excluded conflicts all raise); `ah.data.intake.validate_file` now fails
  an Albourne strategy-grouped drop carrying an unmapped vendor code, with a readable
  report naming the code and the mapping file. 15 tests. Honest note: the plan's
  "re-file existing intakes" clause is vacuous — no Albourne intake was ever
  delivered; the committed fixtures are swept instead.
- **WP2R.8 — governance consolidation + the three seal guards** (Step 2R).
  - **`tests/test_seal_guards.py` (13 tests) closes the RFR-76..84 defect class** —
    "the seal asserts something nothing mechanically verifies" — by making the seal's
    *boundary* a checked fact: (1) **import closure**: every module reachable from the
    judging entry points (`ah.eval.g2`, `ah.battery.report`, plus `battery.py`'s
    dynamically imported metric suites) is sealed or on an exclusion list where every
    entry carries a disputable reason and staleness fails; (2) **sealed-name
    resolution**: threshold names, strategy weights, factor lists and the executable
    rule's tiers resolve against the registries defining them, with the one *known*
    unresolvable phrase (S2-HORIZON-TIER's "horizon tier") pinned so fixing it forces
    the pin to move; (3) **citation integrity** over `governance/*.md` and the
    evidence documents — `file::test`, repo paths, *and bare filenames* (RFR-84's
    corrected spec, including its quoted-as-known-bad exclusion). First run found one
    new genuine dangling citation (RFR-31's renamed test — corrected by appending
    **RFR-85**) and rediscovered the two already on record (RFR-75, RFR-84).
  - **Decision register consolidated**: D1/D2/D3 CLOSED with evidence; **D6 RATIFIED
    by the owner** (the AM-2026-07-26-001/-002 provisional values); the 2R plan's
    D4/D5 glosses closed **by content** per the owner (S2-D4 already closed;
    `S2-D5-STATE-SPACE` filed) while the register's own D4/D5 stay honestly OPEN with
    Step-3 owners; the plan-vs-register id mismatch and the D9 overload recorded
    (RFR-78 class); **S2R-FX-NEXT-CAMPAIGN**: the owner folded the FX block into the
    next campaign's retrain (one retrain buys FX + `WP1.13` CAPE + regime persistence),
    discharging SM-13 at the 2R session as DN-5 asked.
  - **`governance/evidence/`**: frozen snapshots of `G2-EVIDENCE.md`, `ABLATION.md`,
    `ablation.json` with pinned sha256s — copies, not moves, because sealed files cite
    the root documents by name. The negative-control report the plan names **never
    existed as a file**; recorded in the archive README rather than reconstructed.
  - Model-inventory refresh clause: verified already satisfied by WP2.11's seven
    Step-2 cards; nothing to add.
- **WP2R.4 — the generator-output contract** (`schemas/generator-output-v1.0.schema.json`,
  Step 2R). The frozen contract for what a generator emits: the provenance quartet
  (generator / checkpoint / config / vintage) plus seed and blocks; the factor namespace
  with units and the primitive-vs-derived split, derived variables carrying their defining
  identity (`expr` + `inputs`) so a consumer can recompute them; the regime path; the
  slow-state (L1) layer; and the joinery waypoint/diagnostic block. Tensors are pinned by
  shape/dtype/sha256 (`ah.core.digest` canonical rounding), never embedded.
  - **Absence is a statement.** A generator with no regime path or slow-state layer
    declares `AbsentLayer(reason)` at construction; the document spells it
    `{"absent": true, "reason": ...}`; a bare `None` makes `build_document` raise. No
    component of the contract can be silently missing — the mechanical form of the
    RFR-76..84 lesson, applied to a contract at birth rather than retrofitted.
  - `Ensemble` gains optional `regimes`/`slow_states` records (every existing constructor
    unchanged — sealed `ah/eval/` callers untouched). The joinery now *retains* what it
    previously dropped: per-decade operative regime labels (crisis overlays applied) and
    the L1 state rows; `bootstrap-v1` emits its **realized** regime path (the historical
    label of every row actually drawn — a record of the stratified draw, not a new
    conditioning mechanism; no RNG consumed, bit-identical paths per seed).
  - `ah/gen/output.py`: `build_document` (validates before returning), `validate_document`,
    `verify_arrays` (re-derives every digest). `tests/test_generator_output.py` (15):
    schema-validity and digest verification for the joinery and bootstrap emitters, the
    frozen-posterior-mean marking (system C), per-seed document bit-stability, both
    refusals (bare-`None` layer, undeclared factor), tamper detection, and namespace
    fidelity — every derived factor's identity resolves to a real `ah.data.derive` helper
    over registered series (the acceptance clause as a test).
  - **Process note:** CLAUDE.md declares `schemas/` read-only vendored truth; the 2R plan
    explicitly instructs authoring this new file there. Read per the stated conflict rule
    (plan wins for process): authoring a *new* contract is the sanctioned act, no existing
    schema was touched. Flagged here rather than resolved silently.
- **WP2.11 — THE G2 GATE. Verdict: PROMOTE `hier-flow-v1` over `bootstrap-v1`.**
  `AM-2026-07-31-003` seals the executable form of `multi_seed_decision_rule`;
  `pre-registration.lock` is now `sha256:99ab3f772be6a5af…` (33 files, membership
  unchanged). Not one threshold, band, gate, floor, split, size or severity moved — the
  rule's words are byte-identical and this adds only their executable form.
  - **`ah/eval/g2.py`** gains the four clauses beside the pre-existing token mint. It
    **composes** `ah/eval/ablation.py`'s sealed primitives rather than restating them —
    two implementations of one sealed inequality is two things that can disagree. Each
    clause carries the sentence it implements as a docstring quotation, and
    **`tests/test_g2.py` pins one sealed sentence per test (22 tests)**: strictly-lower
    (a tie is not a beat), the NaN rule on *either* side making a seed not-a-beat and not
    an exclusion, the pooled inequality at ddof=1 in both halves, clause (ii) vetoing the
    pooled route, `minimum_seeds`, and the criterion-bearing refusal on challenger *and*
    benchmark reports.
  - **One sealed requirement discharged.** `criterion_bearing_runs_only` said `g2.py`
    "MUST refuse a report where it is false" and noted the refusal "does not exist yet".
    It exists now, over every report entering the verdict, and it raises rather than
    degrading — a run at the wrong size or against a superseded vintage is not a weaker
    input to a verdict, it is not an input at all.
  - **Validated against known answers before being trusted.** Clause (1) reproduces
    `ABLATION.md` §6 — generated by a different program that `g2.py` has never read — to
    six decimals on all five figures: `d` = `[−0.277918, −0.304350, −0.307900]`, mean
    `−0.296723`, sd `0.016381`. It also **discriminates**: four of five ablation systems
    return SHIP-BENCHMARK, one returns PROMOTE.
  - **Where the executor and `ABLATION.md` appear to disagree, the sentence wins.** That
    table reports "pooled beat" and "clause (ii) every seed" as independent columns, by
    which `hier-diffusion-v1` is a pooled beat. `beats_definition` says clause (ii) "must
    still hold in every seed for the pooled route — the pooled arm relaxes the objective,
    not the band-regression check". Diffusion fails clause (ii) in every seed, so its
    pooled route fails. **The clause most plausibly bent toward a second promotion was
    implemented against the reading that would have granted it.**
  - **One ambiguity found and not resolved unilaterally.** Clause (2) admits a by-count
    and a by-metric reading; both are computed, `holds` is their conjunction (the
    stricter), and a disagreement emits a note. They agree on every cell of the grid.
  - **A vacuous guard found and replaced while testing.** The first draft refused a seed
    whose comparison sets differed by `strategy_ids` — derived from the sealed arguments
    alone and therefore identical by construction, i.e. dead code wearing the appearance
    of a safety check. It now guards the resolved metric *names*, which are read off each
    report and can differ, with a test pinning the distinction.
  - **`G2-EVIDENCE.md`** (new, repo root) leads with the disclosures rather than the
    verdict: the post-hoc correction and its timing, the non-independent reviewer, the
    draw-span bias *toward* promotion and the restricted re-run the margin widens under,
    the unspent holdout, the 73%-dead decade tier, the two-day hole in the seal, and the
    seven-strong defect class. It states both readings that must be published together —
    the challenger wins the pre-registered contest, *and* neither generator is a
    convincing model of history.
  - **`governance/model-inventory.yaml`** gains seven cards plus the required
    signature-variant deferral note: owner, training vintage, architecture, seeds,
    checkpoint hashes (primary and severe), validation evidence and known limitations
    for each. GPU determinism is stated once for all torch-backed cards, including what
    is **not** claimed — cross-device bit-identity was never tested.
- **`RFR-84` — RFR-82 contained two false statements, and both are instances of the
  class RFR-82 itself documents.** Written one commit after that class was named, by the
  party naming it. (1) It cites `tests/test_splits.py` as precedent for an import-graph
  check; **there is no such file** — the real tests are
  `tests/test_leakage_guard.py::test_gen_modules_never_import_g2` and
  `tests/test_bootstrap.py::test_no_gen_module_imports_ah_eval`. That is RFR-75's defect
  exactly, which itself notes it "was caught by a one-off script, not by anything that
  will run again". Nothing runs again, so it happened again, in the row explaining why.
  (2) It describes `AM-2026-07-31-001` as type `seal_scope_addition`; that filing was
  rejected by `tests/test_prereg.py` against the sealed four-type vocabulary and the
  amendment was filed as `correction` — the row described a filing that never existed.
  Corrected by appending, per this register's own rule. Neither error touches a
  threshold, a verdict, a hash, or the substance of the finding — `ablation.py` was
  genuinely unsealed, the re-seal is genuine, the proposed fix is right. What was wrong
  is the account of the evidence, which is the part a reviewer follows to verify it.

  **The prototype corrected its own specification.** Running the proposed check across
  `governance/*.md` and `pre-registration.yaml` found one genuine dangling citation
  pre-dating this work (a renamed conditional-tier test) and one false positive (RFR-75
  quoting the bad citation it documents) — so a prose checker must distinguish a citation
  from a quotation of one. And it **did not catch RFR-82's error at all**: RFR-75
  specified the check over `file::test` pairs, while RFR-82's error was a bare filename.
  The corrected spec resolves bare `tests/*.py` references too. Both refinements came
  from running it rather than reasoning about it.

  **Seven findings of one class in three days, and the seventh is the record of the
  fifth.** That is not carelessness more care would fix — prose citations to code are
  unverifiable by reading and decay silently. Only a machine check catches them. Unowned.
- **`AM-2026-07-31-002` — THE HOLDOUT WAS NOT SPENT, and remains unspent.
  `pre-registration.lock` is now `sha256:edd1f841050f92b8…`** (supersedes
  `sha256:f10553a4b742…`; 33 hashed files, unchanged membership). No threshold, band,
  gate, floor, split boundary, size, severity or rule text moved; `multi_seed_decision_rule`
  is byte-identical; no code changed and the token mint in `ah/eval/g2.py` is left intact
  and unused.

  **The defect that forced the decision.** The seal pins the holdout's span
  (`2021-01-01..2026-08-01`), its guard (a `FinalEvaluationToken` mintable only in
  `ah/eval/g2.py`, with an import-graph test proving `ah.gen` cannot reach it), its
  at-most-once budget, and an absolute no-tuning prohibition — and **never says what the
  one permitted evaluation computes.** `STEP2-GENERATOR-PLAN` §WP2.11 adds only "once,
  logged, never repeated". **None of the rule's four clauses reads the holdout**; all
  four run on the WP2.10 grid against a train+validation reference, so the verdict is
  fully determined without it. The project built an effective mechanism to protect a
  resource and never wrote down what to do with it.

  **Why declining is conservative rather than negligent.** Any procedure run at WP2.11
  would have been authored at WP2.11, with the grid, both severe arms, the head-to-head
  and the restricted-window re-run already visible — the forking path the seal exists to
  close, applied to the one resource that cannot be restored. No reader could distinguish
  "the system generalizes" from "the author picked a procedure that showed it does". Not
  spending costs the gate nothing and leaves the resource worth what it was.

  **Filed as an amendment rather than a note** because the sealed splits block asserts the
  holdout "is spent EXACTLY ONCE, by WP2.11", and leaving that unamended would leave the
  sealed document making a false statement about the project's own conduct — the exact
  defect class recorded five times already against other prose. **Both readings of "spent
  exactly once" are on the record**: as *requiring* a spend (so this is a dated departure
  the amendment legitimizes) or as *bounding* spending at one (so zero conforms). The
  stricter reading is why it is an amendment. **The prohibitions are unchanged and still
  bind** — at most once, ever, through the token, and no tuning under any circumstance.

  **`RFR-83`** owns the general defect: **a sealed guard with no sealed test behind it.**
  It extends RFR-77 one step further back — a sealed protocol must specify its own inputs
  and outputs, not merely its access control. **A guard is not a test.** Unowned, and it
  must be closed *before* the next campaign rather than during it.
- **`AM-2026-07-31-001` — A HOLE IN THE SEAL, not in the accounting of it, and the first
  in this project. `pre-registration.lock` is now
  `sha256:f10553a4b74242f2b8c77954f923c06de979a8adb0851adf8f8edecf940b15ec`**
  (supersedes `sha256:e5a669cf156a…`; **32 → 33 hashed files**, `src/ah/eval/ablation.py`
  added, nothing removed — the first amendment in the project to widen the hashed set).
  Not one threshold, band, gate, floor, split, size, severity or rule text moved, and no
  judging arithmetic changed.

  **The defect.** `src/ah/eval/ablation.py` implements `comparison_set`, `clause_i`,
  `clause_ii`, the pooled inequality of `beats_definition`, `enforce_rows`,
  `memorization_enforce`, `constraint_violations` and the `criterion_bearing` refusal —
  every arithmetic the G2 verdict is computed from, and the executable form of the
  clauses the sealed document states in words. Created by WP2.10 (`29fa613`, 2026-07-29)
  **outside** `src/ah/eval/metrics/`, where `_METRIC_SUITE_NAMES` cannot reach it, and
  never added to `_REQUIRED_JUDGED_SOURCES`. **It was not hashed at all from 2026-07-29
  to 2026-07-31** — the code computing the verdict was editable with no lock violation
  and no failing test.

  **Why this is a different category from the claims sweep.**
  `AM-2026-07-26-006/-008` added `_pooling.py` and `negative_controls.py` to the sealed
  *accounting* and could say truthfully that "the SEAL never had a hole; the accounting
  of it did" — both were hashed throughout, merely unnamed in the prose. **This file was
  not hashed.**

  **The rule it broke is this project's own, stated twice and with precedent.**
  `ah.eval.prereg`'s docstring: such a module "joins the seal only by being added to
  `_METRIC_SUITE_NAMES` / `_REQUIRED_JUDGED_SOURCES` … in the same PR that adds the
  module". The sealed header applies it by name to `battery.py` and `panel.py`, "joined
  to this list in the same commit that added them". WP2.10's commit says "No sealed
  judged source touched, zero amendments" — **true as written, and the wrong test**: the
  omission was not *touching* a sealed source but *creating* one and leaving it unsealed.

  **The results survive, by the wrong kind of assurance.** Exactly one commit has ever
  touched the file and the diff from it to the re-seal is empty, so every number in
  `ABLATION.md` rests on the bytes now hashed — verifiable from git alone. But that is
  evidence *after* the fact where the seal exists to give design *before* it. "We checked
  and nobody changed it" is a weaker claim than "it could not have been changed
  undetected", and being able to make the second claim is the entire point of hashing the
  judging code.

  **Filed as `correction`, not `protocol_change`**, because the sealed protocol already
  required this file to be hashed — the amendment brings the artifact into line with the
  rule rather than moving the rule. Inventing a fifth amendment type would have meant
  editing the sealed `AMENDMENT_TYPES` vocabulary for the filer's own convenience.
  Deliberately **not** folded into the `g2.py` implementation commit that forces a
  re-seal anyway: a hole in the seal must be findable as its own governance record.

  **`RFR-82` records the class, and it is the fifth of its family in three days** —
  RFR-76 (sealed gloss versus sealed field), RFR-77 (protocol with no criterion), RFR-78
  (sealed prose naming an identifier that does not resolve), RFR-81 (sealed prose
  misdescribing the data layer), and this. All five share one shape: **the seal asserts
  or assumes something nothing mechanically verifies.** This one's fix is the cheapest
  and closes a hole rather than a mis-description — an import-graph test that every
  module reachable from the judging entry points is sealed, suite-registered, or on an
  explicit excluded list with a stated reason. It would have failed the moment WP2.10
  committed. Unowned.
- **WP2.11 governance step — four decisions taken and three deferrals assigned a
  destination, ALL of them recorded BEFORE the one-shot holdout is touched and before
  `ah/eval/g2.py` computes any verdict. No sealed file changed, no re-seal, no
  amendment, no threshold written after the fact, no code touched.** The sequencing is
  the point: every interpretive question that could be answered differently once holdout
  numbers exist is answered now, while they do not.
  - **`S2-SEVERE-GATING` — the severe test's INCONCLUSIVE reading is a HUMAN JUDGEMENT,
    labelled as such, and the test enters `G2-EVIDENCE.md` as evidence rather than as a
    gate.** `severe_test_protocol` pins a procedure but no criterion (RFR-77), so no
    sealed rule produced WP2.11 part 1's reading. Two alternatives were rejected on the
    record: writing a pass mark now (a threshold authored by the party holding the
    result, after seeing it — the exact substitution the seal exists to prevent), and
    declaring the test structurally uninformative (overclaiming — the exclusion left a
    systematic footprint, regime-frequency TV +0.0140, consistent to four decimals
    across three seeds). **The four clauses of `multi_seed_decision_rule.rule` are
    untouched: the severe test is not one of them and never was**, so no verdict
    arithmetic moves.
  - **`S2-HORIZON-TIER` — both readings reported, neither adopted.** The sealed protocol
    says "the horizon tier"; `TIERS` defines no such tier. `suite == "horizon"` selects
    110 metrics, `tier in {1_5yr, 10yr}` selects 113, differing by
    `interval_coverage_50_5y`, `interval_coverage_90_5y` and `pit_ks_stat_5y`. **That
    the two agree is not a claim available before looking**, so narrowing is deferred to
    a dated `protocol_change` amendment taken pre-campaign, when no results are in view
    (RFR-78).
  - **`S2-DEFAULT-GENERATOR` — decided BLIND: if both co-primaries clear the sealed
    rule, the one that clears clause (1) on the STRICTER route (every seed, not merely
    pooled-beyond-dispersion) becomes the default `generator_id`; the runner-up stays
    registered and reachable but is not the default.** Taken before clauses (2)–(4) were
    adjudicated and before the holdout was touched — which is the only thing that makes
    it worth recording. The sealed `rule` is singular ("the challenger") while WP2.9
    deliberately carried two co-primaries, so a both-pass outcome had no sealed
    tie-break. A SHIP-BENCHMARK verdict moots it: `bootstrap-v1` stays default per the
    seal.
  - **`S2-REVIEWER-OF-RECORD` — the reviewer is the project owner, i.e. NOT independent
    of the work, and `G2-EVIDENCE.md` must say exactly that** rather than let the phrase
    "independent reviewer" imply an outside party. Binding sequencing: the post-hoc
    `AM-2026-07-29-001` and the WP2.10 head-to-head go in front of the reviewer **before**
    any verdict is computed. The evidence document must state, in one place, who
    reviewed, that they are not independent, and that the amendment is a post-hoc
    correction made by the beneficiary.
  - **`RFR-77`, `RFR-78` — the two general gaps behind the decisions above, both
    UNOWNED and both stated with their mechanical fix.** RFR-77: every sealed protocol
    whose result may be cited must either pin a threshold or declare itself non-gating,
    asserted by test over every `*_protocol` key. RFR-78: every tier, suite and metric
    identifier appearing in sealed prose must resolve against the live `TIERS`/`SUITES`
    registries — a gap `claims_with_tests` structurally cannot close, since it checks
    that a named test EXISTS, not that a named IDENTIFIER resolves. Same shape as
    RFR-76's targeted test; one pass should take all three.
  - **`RFR-79` — `RFR-42` finally has an owner and a destination**, after sitting
    "unscheduled" since 2026-07-26 with the register itself saying it should be owned
    before G2. Two of its three causes were discharged by the work (regime duration via
    WP2.6, `ergodicity_gap` via WP2.5); the valuation factor remains and is a **Step-1
    data item**, assigned to the project owner as **`WP1.13` (valuation series
    connector)**, targeted before Step 3's decade-scale work. **Assignment is not
    resolution:** G2 still proceeds with the `10yr` tier declared UNAVAILABLE per
    `conventions.ten_year_tier_coverage`, and `G2-EVIDENCE.md` still may not cite a
    `10yr` pass.
  - **`RFR-80` — corrects `RFR-79` the same day, by appending rather than editing, per
    this register's own rule.** RFR-79 claimed two of RFR-42's three causes were "since
    discharged by the work itself". **Not established, and for one of the two
    contradicted by the tree.** The sealed disclosure says `ergodicity_gap`'s
    multi-century path is a capability "WP2.5's climate model **could** supply and no
    current generator does" — a possible route, restated by RFR-79 as a delivered one;
    `src/ah/eval/negative_controls.py`, a hashed judged source at this commit, still
    records all 14 `ergodicity_gap` metrics as unavailable with no reference band. The
    regime-duration cause is **unverified**: `usrec`/`growth_yoy` exist in
    `ah/data/derive.py` as Step-1 labelling features, not as generated factors. **Correct
    reading: one cause assigned to `WP1.13`, two still open.** No verdict, threshold or
    sealed value is touched by either row. The lesson recorded with it: **a governance row
    summarising a sealed disclosure must quote its modality** — "could supply and no
    current generator does" versus "is supplied" is the whole defect, and it is RFR-76's
    failure mode committed in the register rather than in the seal.
  - **`RFR-81` — the valuation data was never missing; only the FACTOR MAPPING is, and
    this supersedes the SEALED disclosure's own account of it.**
    `conventions.ten_year_tier_coverage` says cause (a) needs "a new
    `requirements.yaml` series plus a `factors.yaml` mapping"; RFR-42, RFR-79 and RFR-80
    all repeated that framing, and RFR-79 scoped a whole work package on it.
    **`shiller.cape` has been registered since Step 1** (`requirements.yaml:49`, FREE,
    monthly, from 1881-01, auto intake) with `connectors/shiller.py` already parsing the
    `CAPE` column from Shiller's `ie_data.xls`; **`fred.USREC` is registered too**
    (`requirements.yaml:37`, from 1854-12, `enforce: true`). The real blocker is that
    `factors.yaml`'s active blocks are `global` (8) + `us` (6) = 14 factors and none is a
    valuation factor — and adding a fifteenth **generated** factor is a factor amendment
    plus a full retrain of L1/L2/L3, for the reason already sealed for `R5` (FX) and `J3`
    (UK): cross-block correlation cannot be grafted onto trained weights. The metric needs
    a valuation path the *generator* emits, not a historical series. **`WP1.13` is
    rescoped accordingly** — map an existing series and retrain, rather than build a
    connector — and the retrain-now-versus-next-campaign choice is recorded as
    **OPEN, owner's call**, not taken. Third finding in a row of the same shape, now
    pointing into the seal itself: a check resolving every series and factor name in
    sealed prose against `requirements.yaml`/`factors.yaml` would have caught it, and
    belongs with RFR-78's identical proposal for `TIERS`/`SUITES`.
  - **`S2-REVIEW-OUTCOME` — the reviewer-of-record review APPROVED on 2026-07-31, before
    the holdout was opened and before any verdict was computed**, discharging the
    sequencing `S2-REVIEWER-OF-RECORD` made binding. Material: the plain-language
    `governance/G2-REVIEWER-PACKET.md`. **The approval covers three narrow questions and
    nothing else** — that `AM-2026-07-29-001` is a genuine correction rather than a
    convenient one; that the benchmark's 1990–2020 draw-span disadvantage, weighed rather
    than noted, does not undermine the comparison (the challenger's margin *widens* under
    the sealed restricted-window re-run); and that the one-shot holdout may be spent.
    **It is explicitly NOT a judgement that the results are "good enough" and NOT an
    endorsement of model quality** — that was answered in advance by the sealed rule, and a
    reviewer deciding it on their own reading of the numbers, in either direction, would be
    doing the very thing the seal exists to prevent. The reviewer is **not independent** of
    the work. **Both readings stand together and both must be published:** the challenger
    beats the benchmark on the pre-registered criterion in every seed and on both routes,
    *and* neither generator is a convincing model of history — 1966–84 called a long
    inflation era under half the time against history's every window, inflation persistence
    at roughly half its historical half-life, drawdowns understated about twofold, stagnant
    decades invented at 0.29–0.75 against a historical 0.00–0.05, and the `10yr` tier that
    would catch decade-scale error 73% structurally unavailable. A PROMOTE changes the
    default `generator_id` for Step 3's work; it is not a statement of fitness for real
    decisions, which Step 5 exists to test.
  - **`S2-VALUATION-FACTOR` — route (1), taken 2026-07-31: complete G2 on the sealed 14
    factors.** Closes the decision RFR-81 left open. The `10yr` tier stays UNAVAILABLE as
    sealed; the valuation factor enters as a dated factor amendment plus a full L1/L2/L3
    retrain for the **next** campaign. Route (2) — retrain now — is recorded as rejected
    rather than omitted: it would restart the campaign with the WP2.10 head-to-head
    already known, the hazard `AM-2026-07-29-001` cost once, and at far greater scale
    since a retrain re-rolls every number the verdict rests on. The decision claims only
    that the fix does not belong inside the gate it would alter.
- **`AM-2026-07-29-001` — the first `post_hoc: true` amendment in this project. A false
  prose gloss in the sealed `multi_seed_decision_rule.tail_tier_definition` is corrected,
  and `pre-registration.lock` is now
  `sha256:e5a669cf156a5e9f27be0a48f6ec4e7c7737feb60fc7fbd4a3c4fa08b765c275`** (supersedes
  `sha256:2531904623db3d9e31c9dc234ae104cc8c010ed45223a381e94c6ba83312e585`; **32 hashed
  files, unchanged set** — this amendment adds no judged source, and the digest moves
  only because `pre-registration.yaml` is itself hashed). **Not one threshold, band,
  gate, floor, split, ensemble size, severity, selection weight or rule text moved, and
  no code changed.**

  **The defect.** `tail_tier_definition` defined the comparison set as "the five
  `d4_strategies` minus `reference_run.uncomputable_d4_strategies`, **which on this
  vintage is `sixty_forty`, `momentum` and `carry`**". The sealed field it glosses is
  `[eqw_factors, endowment_proxy]` — the gloss named the field's **complement**.

  **Why it is not inert.** The two readings give opposite G2 verdicts. Reading the FIELD
  (what `ah/eval/ablation.py` does, and what `d4_commodities_consequence` and
  `limitations.…missing_two_of_fourteen_factors` have said in the same sealed document
  since 2026-07-26): the comparison set is `{sixty_forty, momentum, carry}`, all
  computable, the rule executes. Reading the GLOSS literally: the comparison set is the
  two strategies whose `elicitability_score` is NaN in all 18 WP2.10 cells, and
  `beats_definition`'s NaN rule then makes **no seed a beat for any system, ever** — an
  automatic SHIP-BENCHMARK independent of all evidence. The amendment adopts the field's
  reading.

  **The timing, recorded rather than argued away.** It was found while extracting
  WP2.10's results — *with the results already in hand*, and after it was visible that
  `hier-flow-v1` beats `bootstrap-v1` on clause (1) in every seed. **A correction that
  makes a promotion possible was therefore made by the party that would benefit from a
  promotion, after seeing that a promotion was in reach.** The project owner was shown
  the results first, was told plainly that this is the timing, and approved it
  explicitly. `post_hoc: true` exists for exactly this; every prior entry in the log is
  `post_hoc: false`.

  **The standing check could not have caught it** (`governance/retrofit-register.md`
  RFR-76, unowned). `tests/test_prereg.py::test_the_sealed_tail_tier_definition_matches_the_registered_statistics`
  asserts that the definition names the eleven per-strategy and two per-pair statistics,
  that `uncomputable_d4_strategies` is a proper subset of `d4_strategies`, and that the
  subtraction is non-empty — it never compares the prose's *enumeration* against the
  field's *value*, and all five strategy ids appear elsewhere in the same folded block.
  `claims_with_tests` does not reach the clause either: it carries none of the sealed
  `trigger_phrases`, and this block's two registered anchors sit on the following two
  lines.
- **WP2.10 — the five ablation systems A–E as named compositions, the multi-seed
  ablation grid, and a GENERATED `ABLATION.md`. No sealed judged source touched,
  zero amendments; `ah.gen` still never imports `ah.eval`; no new dependency;
  `schemas/` untouched.**
  - `gen/systems.py` (new): DN-1.1 §II.7's table as code. **A** `abl-a-structure-only`
    (L1+L2+L4 with a new `GaussianResidualBlockSampler` in place of L3), **B**
    `abl-b-neural-rollout-flow` (L3 chained, no waypoint binding, no Denton), **C**
    `abl-c-neural-only-flow` (B plus a frozen climate layer), **D** the existing
    `hier-diffusion-v1` / `hier-flow-v1`, **E** the existing `bootstrap-v1`. A, B and C
    register through `ah.gen.registry`; `systems.build(id, seed_index=k)` additionally
    resolves a neural system to the checkpoint trained at seed index `k`.
  - **System A's residual model, stated rather than left to be inferred:**
    regime-conditional in LOCATION (the stratum mean when the stratum carries at least
    `GAUSSIAN_MIN_REGIME_OBS = 24` months, the pooled mean otherwise) and POOLED in
    DISPERSION (one sample covariance over the whole source). A regime-conditional
    covariance is not estimable — STAG is ~5 months and REF ~9 against twelve factors —
    and a pooled 372-month covariance is always PSD and adds no fitted knob. Rows within
    a block are iid: system A carries no block-level temporal structure at all, which is
    the point of the control. A keeps L4, because the waypoints are the only binding
    point at which L1 and L2 reach the monthly path, and because Gaussian draws are not
    floor-safe — Denton's floor re-application is what holds `floor_violations` at 0
    (191 of 3000 raw draws are sub-floor on `ig_spread`; the assembled ensemble has none).
  - **A shares the benchmark's draw-span handicap and D does not** — A's covariance rests
    on the same complete-case 1990-01..2020-12 window `bootstrap-v1` resamples, because
    `equity_vol`'s 1990 start binds a complete-case 12-factor covariance exactly as it
    binds the sealed `block_draw_span`. Recorded as a confound, not repaired with a
    fitted shrinkage constant.
  - `gen/joinery/assemble.py`: two additive `JoineryConfig` levers with unchanged
    defaults — `bind_waypoints` (False drops step 3's binding and step 5 entirely: Δw is
    zero in `c_b`, no Denton, and *therefore no post-Denton floor re-application*) and
    `use_climate` (False substitutes the new `frozen_climate()`, the posterior-mean state
    at `s0_date` held constant, so L1 contributes no variation and L2 runs at its
    baseline hazards). Every ensemble now records `waypoints_bound`,
    `reconciliation_applied`, `floors_reapplied_post_denton` and `climate_layer`.
  - `eval/ablation.py` (new): tabulates WP2.11's SEALED `multi_seed_decision_rule` inputs
    out of stored battery reports — the comparison set, clause (i)'s mean
    `elicitability_score` (NaN-propagating, per the sealed NaN rule), clause (ii)'s
    band-exceedance count (ranged over the WHOLE comparison set so the seal's "zero
    strategy-level metrics enter it" disclosure is MEASURED, not assumed), the pooled
    inequality's two halves at ddof=1, clauses (2)–(4), and `criterion_bearing` broken
    into its three sealed conditions. It does not execute the rule — `g2.py` does, at
    WP2.11 — and it re-derives nothing: every input is a projection of a field the sealed
    battery already computed.
  - **The benchmark draw-span bias disclosure is computable and computed.**
    `historical_strategy_returns_dated` reproduces `tails._historical_strategy_returns`
    element for element (asserted by test) while keeping the date index, so the sealed
    `elicitability_score` can be re-evaluated against the 1990-2020 realizations alone
    with the run's own `(var_95, es_95)` forecast pair read from its stored report.
  - `scripts/train_ablation_seeds.py` (new): retrains each family's ALREADY-SELECTED
    config (`cfg:505f9800900bd757`, `cfg:5943f6cd2f6f1048`) at further seeds — no search,
    no re-selection — and records each checkpoint's weight SHA-256 in
    `configs/wp210-seed-checkpoints.json`, which `systems.build` verifies against.
  - `scripts/run_ablation_grid.py` (new): the resumable single-process batch. Computes
    the train+val reference ONCE for the whole grid (a test pins that this is
    byte-identical to `run_full_battery` per cell), runs cells strictly sequentially in
    ascending cost order, checkpoints after every cell, and records a failing cell in
    `failures.json` without losing the grid.
  - `scripts/build_ablation_report.py` (new): GENERATES `ABLATION.md` and `ablation.json`
    from the stored artifacts. Tests assert the document is reproducible from them, and
    that it changes when an artifact changes.
- **WP2.9 — Layer 3b: conditional flow matching / rectified flow, CO-PRIMARY
  with diffusion (DN-1.1 §II.4 (b)). New code only under `ah/gen/blocks/`, plus
  tests, configs and scripts; no sealed judged source touched, zero amendments,
  `ah.gen` still never imports `ah.eval`, no new dependency.**
  - `gen/blocks/flow.py` (new): `FlowConfig`, `ConditionalVelocityField`,
    `FlowMatchingObjective`, `flow_integrate`, `FlowBlockSampler`, `HierFlowV1`
    and the registered `hier-flow-v1` factory (which pins the checkpoint hash,
    the `cb-v1` fingerprint and both L1/L2 artifact SHAs exactly as
    `hier-diffusion-v1` does). Rectified flow in its straight-line form:
    `x_t = (1-t)x_0 + t x_1`, constant conditional target `x_1 - x_0`,
    deterministic Euler or Heun integration from noise to data. Two sampler axes
    with no 3a counterpart — `solver` and few-step `eval_nfe` — plus a LEARNED
    NULL CONDITIONING VECTOR enabling classifier-free guidance (`cond_dropout`
    at training, `guidance_scale` at sampling).
  - **Guidance is counted honestly.** CFG costs two network evaluations per
    step, so `FlowConfig.sampling_nfe` reports the doubled figure and the tuning
    log records the TRUE NFE — otherwise the sealed tie-break on sampling cost
    would prefer a sampler that is twice as expensive. `FlowConfig` also
    collapses `guidance_scale` to 1.0 whenever `cond_dropout` is 0 (a null
    branch that was never trained must not be sampled from), *before* the config
    is hashed, so the sealed budget is not spent twice on the same model.
    `FlowBlockSampler(guidance_scale=...)` and `sample(..., guidance_scale=...)`
    override the checkpoint's own setting so the SAME checkpoint can be scored
    and reported with and without guidance.
  - **Shared, not forked.** `train.py` gained two structural protocols
    (`BlockConfig`, `BlockModel`), a family-generic `train_blocks`, and an
    optional `sample_fn` on `evaluate_fold_scores`; `train_diffusion` is now an
    alias, so every WP2.8 caller and test is unchanged. `tuning.py` takes a
    `config_cls`, so both arms run the same protocol code — the same budget
    accounting, the same log validation, the same closed-form selection with the
    same PINNED lambda — over their own logs. `diffusion.py` gained
    `TorchBlockSampler` (all the WP2.8b sampler machinery: fingerprint refusal,
    RNG contract, fixed-width/zero-padded batching, batch-1 tracing, output
    map), `HierBlockSystem` (now with a `guidance=` hook parameter recorded in
    ensemble lineage), and public `Attention`/`TransformerBlock`/`COND_GROUPS`.
    `ConditionalDenoiser` itself is structurally untouched — its `state_dict`
    keys are inside the pinned WP2.8 checkpoint hash, and that pin still
    verifies, as do WP2.8's final gen/aux numbers through the new trainer.
  - `gen/blocks/bakeoff.py` + `scripts/run_sampler_bakeoff.py` (new): the
    like-for-like harness, in library form so WP2.10 drives both arms of
    ablation system D from one call. Reports both terms of S separately per arm
    with their scales (the sealed `tuning_protocol` consequence, wired in rather
    than left to the writer — `INCOMPARABILITY_NOTE` is printed above every
    table and no cross-arm S ranking is produced), true NFE per block, blocks/s,
    s/decade and s/10k decades at a declared width and device, and the
    `artifacts/wp28/ig-spread-diagnosis.md` §4 conditioning-response measurement
    generalized over an arbitrary sampler.
  - `configs/wp29-flow-search-v1.yaml` (new): the search space stated in
    advance, its SHA-256 recorded in the log header before the first trial. The
    budget is the sealed 40 **for this sampler** — WP2.8's 8 unspent trials are
    not inherited and are not used. Shared knobs are held at WP2.8's values so
    neither arm is searched harder than the other; the three
    conditioning-strength axes (`cond_noise_std`, `cond_dropout`,
    `guidance_scale`, each with a neutral value in the space) are there because
    of WP2.8's MEASURED conditioning attenuation, and they are searched inside
    the sealed criterion — no auxiliary term is added and nothing outside
    `generative_objective + 1.0 * D4_aux` is optimized.
  - `scripts/run_flow_tuning.py`, `scripts/train_flow_final.py` (new): the 3a
    scripts with the config class swapped. Both wait politely for the DuckDB
    catalog's exclusive file lock rather than racing another Step-2 job for it.
    `scripts/verify_block_batching.py` gained `--arm` (default unchanged), so
    the WP2.8b batching evidence is produced for either family by one script.
  - **Campaign results** (full evidence in `artifacts/wp29/`). Search: **40/40
    trials started, 40 completed, 0 crashed**, 2 h 58 m on the RTX 3080, on the
    byte-identical WP2.8 dataset (367 raw blocks, ~42 effective/epoch, folds
    35/35/35). Selected `cfg:5943f6cd2f6f1048` — d_model 192 / 4 layers,
    **Euler at NFE 4**, `cond_dropout` 0.2, `guidance_scale` 1.0,
    `cond_noise_std` 0.1, `lambda_tail` 0.3 — at S = −1.833365 = gen 1.511200 +
    1.0·(−3.344565). Final training 13,000 steps / 926 s, early-stopped at step
    5,000, S = −1.765125 = gen 1.644183 + 1.0·(−3.409308); checkpoint
    `b1fe26e1…`, same-device CUDA bit-determinism verified, peak GPU memory
    140 MiB. Both S terms are reported separately with their scales per sampler
    and **no cross-arm S ranking is stated** — but the auxiliary term IS on one
    scale, and 3b's −3.409 beats 3a's −3.264. Sampling cost at width 128 on
    CUDA: **NFE 4 vs 31; 92 s vs 744 s per 10k decades on block sampling; 359 s
    vs 1,656 s per 10k decades end to end through the joinery (4.6×)**.
    λ = 1.0 made 3a's selection auxiliary-dominated (aux/gen sd 2.11×,
    corr(S,aux) 0.911, argmin S = argmin aux) and 3b's genuinely joint (1.14×,
    0.644, argmin S is neither term's) — the seal's own stated limitation, now
    quantified per arm.
  - **Guidance ablation** (same checkpoint, guidance 1.0 → 1.5 → 2.5): every
    conditioning channel strengthens (`dw_equity_cum_log` 69% → 96% → 144%,
    `dw_spread_center_pct` 19% → 25% → 32%, `h_spread_level_pct` 15% → 20% →
    30%, regime one-hot 3% → 5% → 8%) while the D4 tail auxiliary degrades
    monotonically (−3.409 → −3.302 → −3.118) at 2× the NFE. Reported both ways;
    the sealed criterion, which sees only `gen + 1.0·aux`, selected guidance
    off. The joinery `bridge.GuidanceHook` is plumbed and recorded in lineage
    but NOT activated — `cb-v1` carries no waypoint LEVEL, so the hook's frozen
    signature cannot express a band-centre correction at all, and any
    post-hoc-repair arm must be evaluated against a settled `ig_spread` band.
  - **Correction to WP2.8b's batch-composition claim.** WP2.8b recorded that a
    row's sampler output "depends only on that row and on the width — never on
    its position in the batch"; its test asserted permutation invariance using a
    fixture whose output head is zero-initialized, i.e. a network that emits
    identically zero, for which the claim is vacuous. Measured on networks with
    weights (both families, CPU oneDNN and CUDA alike): holding a row at its own
    batch index is EXACT — isolating it with every other row zeroed reproduces
    the full batch bit for bit — but MOVING it to a different index changes its
    output by ~2.4e-7, the same float32 GEMM round-off WP2.8b already measured
    across widths. The index-preserving property is the one `sample_blocks`'
    fixed-width chunking delivers (decade `m` is always row `m % width`) and the
    one the acceptance filter and the ensemble digest rely on.
    `TorchBlockSampler`'s docstring now states the true property, and
    `tests/test_blocks_diffusion.py`'s composition test was STRENGTHENED — it
    now runs on a network with weights and asserts index-preserving exactness
    plus a bounded reorder divergence, rather than a stronger claim on a trivial
    model. No behaviour changed and no committed number moves.
- **WP2.7b — the `ig_spread` waypoint band half-width is REGIME-CONDITIONAL
  (a WP2.7 correction; nothing sealed touched, no retraining, `beta_L` and
  `cb-v1` unchanged).**
  - `joinery/waypoints.py`: `sigma_resid` — one pooled residual sd for all six
    regimes — is replaced by `sigma_resid(R)`, estimated from train+validation
    history alone through the sanctioned surface. Per regime the residual
    variance is shrunk toward the *information-weighted geometric mean* of the
    six group variances with `BAND_PRIOR_DF = 1` degree of prior freedom, using
    AR(1)-corrected degrees of freedom, and the result is inflated to a
    PREDICTIVE sd by `sqrt(1 + 1/n_eff)` so the band centre's own estimation
    error is carried as width. `SourceStats` gains
    `spread_band_half_width_by_regime` and a JSON-safe
    `spread_band_diagnostics` (per regime: months, episodes, rho, both effective
    sample sizes, raw/shrunk sd, half-width, fallback flag); the pooled
    `spread_resid_sd` is retained as the absent-regime fallback and as the number
    the WP2.7/WP2.8 artifacts quote. The band CENTRE is deliberately unchanged.
  - `joinery/assemble.py`: the estimator's per-regime widths and effective
    sample sizes travel in every ensemble's lineage as
    `conditioning.spread_band` — the reconciliation diagnostic cannot be read
    without them.
  - Why, from the reference and not from any generator: the six within-regime
    residual variances span a 201x range (run-permutation test p = 0.0034), CRI
    supplies 51% of the pooled residual variance from 4.6% of the months, and **real
    1990-2020 spreads sit outside their own pooled CRI band in 16 of 17 months
    (94.1%)** while never leaving the STAG or REF band. Per-regime half-widths
    are now EXP 0.221, SLOW 0.177, REC 0.241, CRI 1.068, STAG 0.123, REF 0.119
    against the old pooled 0.292 — a reallocation, not a loosening (the mean
    width over generated year-ends moves only 0.292 -> 0.286).
  - `scripts/measure_spread_band.py` (new): old-vs-new band measurement for both
    samplers on one assembly (exact, because the band enters only the
    reconciliation target while the block stream is conditioned on the unchanged
    centre). `scripts/diagnose_ig_spread.py` now reads the regime-conditional
    band and says so.
  - **WP2.7's and WP2.8's published `ig_spread` reconciliation numbers are
    SUPERSEDED.** Band-exit rate old -> new: history 15.1% -> 27.4%, bootstrap
    20.7% -> 25.9%, diffusion 61.4% -> 69.1%; mean excursion 0.0445 -> 0.0295,
    0.0595 -> 0.0380, 0.2615 -> 0.2608. CRI exit collapses for the benchmark
    (86.7% -> 8.6%) and barely moves the trained sampler's total excursion: the
    8x reconciliation gap was NOT mostly a band artifact. Full evidence in
    `artifacts/wp27b/spread-band.md`; batteries re-run at n_paths=1024 (the
    diffusion re-run declares block width 128 on CUDA against the committed
    width-1 CPU baseline).
- **WP2.8b — block sampling batched ACROSS DECADES (throughput only; the joinery
  and the L3a sampler, no sealed source touched).**
  - `joinery/bridge.py`: new optional `BatchedBlockSampler` protocol
    (`sample_blocks(conds, rngs) -> (N, L, F)`) and a new driver
    `assemble_decade_paths(months=..., decades=[DecadeAssembly, ...], ...)` that
    runs N decades **block-major, in lockstep**: at each block index it builds
    every decade's c_b from that decade's own partially assembled path, hands
    the whole slate to the sampler in ONE call with each decade's own generator,
    and cross-fades the results back per decade. Blocks stay strictly sequential
    within a decade (h_t depends on months earlier blocks produced) — the batch
    axis is decades, never blocks. The per-block arithmetic (c_b construction,
    cpi chaining, the cross-fade) moved into one private `_PathBuilder` used by
    both drivers, so the two paths cannot drift. A sampler that does not
    advertise `sample_blocks` (`BootstrapBlockSampler`) falls back to the
    unchanged per-decade `assemble_decade_path` loop.
  - `joinery/assemble.py`: `_DecadeFactory` split into `prepare(m)` (steps 1-3:
    L1, L2, waypoints — no block stream touched) and `assemble(preps)` (step 4
    through the batched bridge, then step 5 per decade). `assemble_decades`
    prepares all decades before bridging them; the acceptance filter's
    replacement decades are likewise prepared and bridged as one batch. Steps 5
    and 6 are untouched: reconciliation still runs per decade and per year on a
    complete path, and the filter still scores fully reconciled decades. The
    batch width and device are recorded in the ensemble lineage
    (`block_sampler_batch`, `block_sampler_device`).
  - `blocks/diffusion.py`: `DiffusionBlockSampler(block_batch=...)` implements
    `sample_blocks` — it draws each decade's noise from that decade's own
    generator, in decade order, exactly where the per-decade driver would have
    drawn it, then evaluates the network at a **fixed width with the tail
    zero-padded**. Padding is what buys composition invariance: a row's output
    depends only on that row and the width, never on its position, its
    neighbours, or how much of the batch is padding (measured, then pinned by
    test) — so a decade's path is the same whether it is generated alone (as the
    filter regenerates replacements) or inside a 1024-decade run, and the
    ensemble is a deterministic function of (seed, width). The traced inference
    graph is now used at batch 1 ONLY: above it the dispatch is already
    amortized while `optimize_for_inference` starts substituting fused
    reduced-precision kernels (measured divergence from the eager model of 5e-5
    on CPU at width 64, 4.6e-4 on CUDA at width 256), so the batched path is the
    eager model.
  - `scripts/verify_block_batching.py`: the evidence harness — the same ensemble
    at several widths, wall clock and `sha256(paths)` each, divergence against a
    stored reference. `scripts/run_diffusion_battery.py` gains `--block-batch`
    and `--sampler-device`, both defaulting to the WP2.8 behaviour.
  - **BIT-IDENTITY, stated exactly.** Width 1 reproduces the committed WP2.8
    code BIT FOR BIT (20x120 filtered, real checkpoint: `sha256(paths)`
    `d43d4099…` before and after). Widths above 1 CANNOT: the float32 GEMM this
    network is built from is not batch-size invariant on either backend measured
    — a row's denoiser output moves by ~1.5e-7 relative (2 ULP) between batch 1
    and batch **2**, on CPU (oneDNN) and CUDA (cuBLAS) alike, and no further as
    the batch grows. That is hardware round-off, not a behaviour change, and no
    test asserts cross-width equality; the width is therefore an explicit,
    lineage-recorded parameter that **defaults to 1**, so no existing number
    moves unless someone asks for it.
- **WP2.8 — Layer 3a, the conditional diffusion block generator
  (`ah/gen/blocks/`) and the sealed tuning protocol — DN-1.1 §II.4 (a),
  registered as `hier-diffusion-v1`.**
  - `data.py`: all overlapping L=6 blocks of the campaign panel, each carrying
    the conditioning vector built **by the joinery bridge's own cb-v1
    machinery** (`bridge.BlockConditioning` + `_history_summary` +
    `_waypoint_increments`, C_B_DIM=18) — training and generation share one code
    path behind the frozen contract. Δw for a historical block comes from
    monthly target curves built from that segment's ACTUAL annual aggregates,
    interpolated exactly as `waypoints.monthly_targets` interpolates generated
    waypoints. **Train-only standardization** (constants recorded on the
    dataset and in the checkpoint; a WP2.5-style leakage test poisons the
    validation span and asserts every constant is bit-identical).
    **Block-aware folds**: a block belongs to the fold containing its start and
    any block straddling a boundary is dropped from both sides (tested).
    **Effective-sample correction**: an epoch draws blocks on an L-spaced grid
    with a random phase, so no two blocks in an epoch share a month —
    247 raw train blocks are ~42 effective per epoch, and both numbers are
    reported everywhere. Two recorded split-hygiene decisions, both strict:
    target curves are built per split segment (the policy year-CENTER anchors
    would otherwise interpolate the first validation year's mean into late-train
    Δw), and the h_t fallback statistics for TRAINING conditioning are
    train-segment-only. Simulated-conditioning augmentation was CONSIDERED and
    DECIDED AGAINST (reason recorded in the module docstring: pairing simulated
    c with nearest-conditioning historical targets would manufacture (c, x)
    pairs the data does not contain and teach the model that off-support
    conditioning maps to in-support blocks); conditioning-noise jitter is the
    searched alternative and off-support behaviour is measured instead.
  - `constraints.py`: hard floors by **transformed coordinates**, so a
    violation is impossible by the codomain of the inverse map rather than by
    clamping — rates/spreads in softplus space above the sealed floors
    (`RATE_FLOOR_PCT` −1.0, `SPREAD_FLOOR_PCT` 0.0; DN-1.1's illustrative
    "spread ≥ 100bp" is SUPERSEDED by the sealed WP2.2c conventions, recorded
    plainly), cpi/equity_vol in log space, returns in log1p space. Round trips
    are float64-exact across the softplus saturation boundary, and floor
    impossibility is tested BY CONSTRUCTION (z from −1e6 to +700, and a
    100×-noise panel through the full sampler), never by sampling luck.
  - `losses.py`: the `GenerativeObjective` protocol (WP2.9's velocity matching
    slots in behind it unchanged) and the **D4 tail elicitability auxiliary** in
    the WP2.2c-CORRECTED direction — (VaR, ES) from the GENERATED sample scored
    by Fissler-Ziegel against the comparison REALIZATIONS — implemented locally
    in differentiable torch, with the strategy definitions read from the sealed
    `ah.strategies` (never `ah.eval`). Parity with the sealed judged
    implementations is asserted by test (`strategy_returns`, `elicitability_score`,
    `var_es`). Recorded: only `sixty_forty` and `carry` are evaluable at block
    scale — `eqw_factors`/`endowment_proxy` are the sealed
    `uncomputable_d4_strategies`, and `momentum` is structurally degenerate on a
    6-month block (its sealed 12-month warm-up covers every month, so its return
    is identically 0.0). A non-positive generated ES contributes a stated
    penalty (10.0), declared in the search-space file before the search ran.
  - `diffusion.py`: EDM-style continuous-time diffusion (Karras preconditioning
    c_skip/c_out/c_in/c_noise, log-normal σ training draws, the EDM weight,
    Karras σ schedule, deterministic Heun integration with configurable NFE =
    2·steps − 1, asserted by a call-counting test). Backbone: a small pre-norm
    transformer over the six month-tokens with **cross-attention on c_b** (four
    conditioning-group tokens + a σ token) — justified by the data scale
    (x ∈ R^{6×12} = 72 numbers; a U-Net has nothing to downsample at length 6),
    ~0.94M parameters at the selected width/depth. Attention is hand-rolled so
    every op is deterministic under `use_deterministic_algorithms(True)`.
    `DiffusionBlockSampler` implements the frozen joinery `BlockSampler`
    protocol, refuses to construct on a c_b fingerprint mismatch, and draws all
    noise from the caller's numpy generator — `assemble_decades` drives it
    exactly as it drives the bootstrap stand-in (WP2.10's system D wiring,
    tested end to end including bit-determinism and floor survival through
    Denton).
  - `train.py`: the plan-§1 determinism block (torch seed + PCG64 data order +
    `use_deterministic_algorithms(True)` + cuDNN flags + `CUBLAS_WORKSPACE_CONFIG`),
    checkpoints identified by SHA-256 over canonical state-dict bytes plus the
    config hash and verified on every load, and **early stopping on the SEALED
    selection quantity S** (both terms, on EMA weights) — nothing
    battery-flavoured feeds a training decision, so the WP2.7 teach-to-the-exam
    bar has nothing to catch.
  - `tuning.py`: the forking-paths record. The search space was committed
    BEFORE the search (`configs/wp28-diffusion-search-v1.yaml`, its SHA-256
    written into the log header); every trial is logged with config hash, git
    SHA, seed and per-fold scores, and a trial is logged as started BEFORE its
    first step so an abandoned or crashed run still spends budget; selection is
    the sealed closed form with `selection_lambda` PINNED at 1.0 and an NFE
    tie-break, S recomputed from the logged fold scores rather than trusted.
    `validate_log` is the machine check the acceptance asks for and it runs
    against the REAL campaign log in the test suite.
  - `ah.gen.blocks` never imports `ah.eval` (AST test over the whole package).
  - Scripts: `run_blocks_tuning.py`, `train_blocks_final.py` (final training +
    the monthly-tier neighborhood evidence table), `run_diffusion_battery.py`
    (the sealed battery at n_paths=1024 filtered+unfiltered, with the
    reconciliation-shrinkage and support comparison against WP2.7's baseline).
- **WP2.7 — Layer 4, the joinery (`ah/gen/joinery/`): waypoints, bridging,
  Denton reconciliation, conditioning-support monitoring — DN-1.1 §II.5's
  7-step algorithm end to end, tested with bootstrap blocks as the stand-in
  generator (ablation system C's machinery).**
  - `waypoints.py`: per calendar year of each decade, from (L1 states, L2
    regimes): annual means of the policy anchor (under L2's c_t) and pi*;
    cumulative log equity drift via the stated mapping
    `(a_val − b_val·v̄_y)/100 + π̄*_y/100 + Σ(μ_R − μ̄)` (valuation anchor +
    expected inflation + regime texture from train+val regime-conditional
    means); a year-end ig_spread level BAND
    `μ_spread(R_yend) + β_L·credit_gap_yend ± σ_resid` (β_L/σ_resid from a
    train+val regression on the L1 posterior-mean credit-gap path); and the
    regime path itself. WorldSpec `factor_conditions` bind HERE as
    overrides/tilts — every schema field implemented: policy start/end with all
    four `path_shape`s (shapes stated in the docstring), inflation
    average/peak/peak_quarter (exact average preservation with a placed peak),
    equity drift (decade total pinned to the authored value) and vol
    (pass-through target), correlation (pass-through — cannot bind a waypoint),
    crisis_windows (overlaid as CRI months, moving the cycle, spread band and
    block stratification). `credit.*` (binds `hy_spread`) and `commodities.*`
    are recorded as explicit UNBOUND overrides — both factors are in the sealed
    `missing_factors`, and remapping authored hy numbers onto `ig_spread` would
    violate the schema's field definitions. Waypoints are floored
    (rate −1.0 / spread 0.0 — restated from the sealed convention, pinned by
    test to `ah.eval.metrics.economics`) so reconciliation targets stay
    feasible.
  - `bridge.py`: overlapping L=6-month blocks, stride 3, linear cross-fade on
    overlaps in state space; **the frozen c_b conditioning contract** WP2.8/2.9
    train against — `BlockConditioning` = [one-hot(R at block start) (6), s_t
    snapshot (5), h_t trailing-12m summary (equity log-return sum, monthly sd,
    spread level) (3), Δw waypoint-target increments (policy, log cpi, equity
    cum-log, spread center) (4)], C_B_DIM=18, schema `cb-v1`, stable JSON
    serialization + `contract_fingerprint()` (SHA-256 over the layout) for
    checkpoint pinning; layout frozen by a golden test. `BlockSampler` protocol
    (the L3 interface); `BootstrapBlockSampler` stand-in (regime-stratified
    contiguous multivariate blocks, circular wrap, visible stratum fallbacks).
    Guidance hook present and stubbed (`guidance=None` does nothing), per plan.
    Recorded decision: `cpi` is CHAINED at block joins (blocks contribute
    within-block inflation, rebased to continue the assembled level) — raw
    level resampling would make the Denton diagnostic measure the draw-span's
    price trend instead of generator-vs-structure disagreement.
  - `reconcile.py`: Denton first-difference benchmarking (exact KKT solve) of
    each waypoint-bearing factor to its annual aggregates, with a stated
    per-factor variant table: policy_rate additive/flow (rates cross zero);
    cpi proportional-via-log/stock (strictly positive index; additive-in-logs
    IS proportional); equity_mkt additive on monthly log returns/flow; ig_spread
    additive/stock to the NEAREST BAND EDGE (inside the band = untouched).
    Hard floors re-applied after the solve; floor-BOUND years (target
    infeasible at the floor, which wins by design) are exempted from the
    tolerance check and counted separately. Adjustment magnitude per factor per
    year returned as the monitored diagnostic, with per-factor "large" flags;
    deliberately inconsistent waypoints produce large flagged adjustments and
    consistent ones small unflagged ones (both tested, per the plan's
    acceptance).
  - `support.py`: Mahalanobis distance of each decade's conditioning vectors
    (the 12 continuous c_b components; the one-hot is monitored via a separate
    regime-frequency TV check) to the train+val conditioning distribution built
    from the bootstrap source's historical blocks + L1 posterior-mean states.
    Stated extrapolation quantile: **p99 of historical self-distances**;
    per-decade extrapolation share logged into `EnsembleMeta.conditioning`;
    off-support flag at share > 0.25. STAG thinness surfaces as zero/near-zero
    reference frequency, not papered over. The sealed battery has no
    ensemble-conditioning report line — the diagnostic lands in ensemble
    metadata + the assembly report; recorded as a WP2.11 presentation item.
  - `assemble.py`: `assemble_decades(...) -> Ensemble` — the 7-step algorithm.
    Distinct per-layer base seeds (offsets 0 / 1_000_003 / 2_000_003, pairwise
    non-congruent mod 7919, tested) fix WP2.6's seed-entanglement note;
    one-pass ordering by default (the WP2.6-certified ordering), `two_pass`
    config flag (off) re-runs L1 under L2's c_t — same draws, only the
    credit-gap forcing changes (tested: equity untouched, spread channel
    moves). Acceptance filter (step 6): metrics (skew, excess_kurtosis,
    hill_tail_index_5pct — local numpy implementations, NOT ah.eval imports)
    over the return factors; subset disjoint from every sealed
    `severity: enforce` name (tested by parsing `pre-registration.yaml`) AND
    from every statistic feeding an enforce band gate (ACF panel deliberately
    excluded — recorded deviation from DN-1.1's parenthetical, forced by the
    sealed dependence gate); ≤10% reject-and-resample-once, every rejection
    logged (seeds + scores), `acceptance_filter=False` for
    filtered-and-unfiltered battery reporting. Step 7 emits full lineage:
    layer artifact SHAs (L1/L2 pinned), layer seeds, ruleset version, c_b
    contract fingerprint, filter log, per-decade support + reconciliation
    distributions, waypoint-tolerance record. Factor→strategy mappings
    (DN-1.1's step-7 WS-C reference) recorded as Step-3 scope, deferred.
    `joinery-bootstrap-v0` registered (schema enum gap shared with
    `bootstrap-v1`, resolved at Step 2R).
  - `scripts/run_joinery_battery.py`: the first end-to-end run of the whole
    hierarchy at the sealed criterion size (1024×120, campaign vintage),
    filtered AND unfiltered through `run_full_battery`, plus
    `joinery-assembly-report.md` with the WP2.7 evidence
    (`artifacts/wp27/summary.json` committed).
  - Tests: `tests/test_joinery_{waypoints,bridge,reconcile,support,assemble}.py`
    + `tests/joinery_common.py` (synthetic artifacts/sources; no catalog, no
    network), including the plan's four acceptance tests and an import-graph
    guard that no joinery module imports `ah.eval`.
- **WP2.6 — Layer 2, the semi-Markov regime skeleton (`ah/gen/regimes/`):
  DN-1.1 SS II.3 over the six Step-1 ruleset states, NegBin sojourns and
  multinomial-logit transition rows both logit-linked to slow-state covariates,
  fitted on `regime_ruleset_v1` labels (+NBER via USREC), with the
  `regime_ruleset_v1b` sensitivity refit the plan demands.**
  - `semimarkov.py` (generation side, numpy `PCG64` only): config (YAML →
    pydantic, hashed), the hash-verified posterior artifact (same canonical
    content-SHA-256 pattern as WP2.5's), and seeded simulation — decade k uses
    `seed + 7919*k` and draws its own posterior index, so L2 parameter
    uncertainty sits inside the ensemble exactly as L1's does. Recorded
    conventions: `D = 1 + NegBin(r_k, p_k)` (failures-before-r-th-success;
    higher p ⇒ shorter sojourn), `logit p_k = alpha_k + gamma_k'z`; transition
    logits `a_kj + b_j'z` with destination loadings shared across origin rows
    (identification: `b_EXP = 0`, one intercept per row).
  - Covariates exactly DN-1.1's `z(s) = (curve slope, credit gap, pi* - target,
    drawdown state)`; historical slope is GS10−TB3MS spliced with the annual JST
    long-short spread pre-1953; credit gap and pi* come from the WP2.5
    posterior-mean smoothed path (the consumed climate artifact's content
    SHA-256 is recorded in the L2 artifact metadata); pi_target = 2.0
    (configured constant). Simulation-side proxies recorded as limitations:
    slope = psi0 − phi_c0·c(R_t), drawdown state = 1[R_t == CRI].
  - **The c_t contract (WP2.5's docstring) fulfilled:** `RegimePaths.cycle` =
    `cycle_by_regime[R_t]`, the per-regime train+val mean of L1's own fitting
    proxy `1 − 2*USREC` — proxy-consistent by construction (CRI = −1 and
    EXP/SLOW/STAG/REF = +1 exactly, by ruleset; REC lands between), values in
    [−1, +1], accepted verbatim by `climate.simulate_decades` (tested).
  - WorldSpec regime modes per `schemas/`: `sequence` pins R_t **exactly**
    (tested; segments must tile, rule V10), `transition_matrix` honours the
    authored quarterly matrix verbatim (rows validated, rule V11; regime names
    map through the single `WORLDSPEC_REGIME_TO_LABEL` copy in `bootstrap.py`),
    `unconditional` = iid draws at historical label frequencies.
  - `fit.py`: label assembly mirrors `bootstrap.regime_labels_for` (same
    features, same refusal on gaps, same dead `hy_oas` disjunct) but exposes the
    labeler's `thr` parameter for the sensitivity variant — a test pins the two
    paths to identical labels so they cannot drift. Spells: first left-truncated
    (dropped), last right-censored (exact finite-sum survival term; JAX's
    `betainc` has no gradient in `r`, so the CDF is an explicit pmf sum, tested
    against `scipy.stats.nbinom`). NUTS diagnostics per flattened parameter,
    generated `regime-fit-report.md` + `regime-sensitivity-report.md`
    (repo-root copies), experiment-store record.
  - **Acceptance evidence, generator-side by design:** the battery's
    `regime_duration_*` names are sealed `structurally_unavailable`, so the
    plan's "simulated duration/frequency distributions inside train+val
    bootstrap bands" is implemented in the fit report — stationary-bootstrap
    bands (mean block 120 months) on per-regime frequencies and sojourn
    quantiles vs the fitted L2 simulated over real-artifact L1 decades (L1
    starting states spread across the label era). No sealed file was touched.
  - `regime_ruleset_v1b` (config-defined; `regime_thresholds.yaml` untouched):
    cpi_high 4.0→3.5, growth_weak 0.0→0.25, growth_slow 1.5→1.75,
    drawdown_crisis −0.20→−0.15; label agreement, composition/duration shifts,
    hazard and transition-matrix deltas, and v1b acceptance bands all reported.
  - `scripts/fit_regimes.py`: the provenance script (offline, catalog-read,
    campaign vintage `2026-07-26.1`, pinned L1 artifact, deterministic).
  - 67 new tests (`test_regimes_semimarkov/fit.py`); no seal amendment needed
    (new files under `ah/gen/regimes/` + script + tests only).
- **WP2.5 — Layer 1, the climate model (`ah/gen/climate/`): DN-1.1 SS II.2 as a
  marginalized linear-Gaussian state space, NUTS over ~35 structural parameters,
  FFBS state draws, deterministic posterior artifact, decade simulator.**
  - `model.py`: the five-state contract `(pi_star, r_star, g, v, credit_gap)`
    Euler-discretized monthly, plus two internal observation-model auxiliaries
    (`credit_trend` for the 150-year secular credit deepening, LW-style trend/gap
    split; `policy_dev` for persistent Taylor-anchor deviations — the ZLB decade
    must not be forced into r*). Mixed-frequency masked Kalman filter fusing the
    annual JST panel (1871–2020) with the monthly Step-1 panel (CPI YoY, spliced
    FEDFUNDS, Shiller CAPE, quarterly BIS credit gap), exact marginal likelihood
    tested against a brute-force joint-Gaussian computation at rel 1e-8; FFBS
    smoother draws tested against exact posterior means. Priors are YAML → pydantic
    (`priors.yaml`, DN-1.1 table rows marked; every gap-fill's rationale inline),
    hashed into the experiment record. `jax_enable_x64` on at import (recorded
    rationale: 7x7 covariance recursions over 1800 steps corrupt in float32).
  - Two recorded DN-1.1 gap-fills: `g_t` (no dynamics equation in the note) is OU
    toward `mu_g`; `L_bar(R_t)` (regimes don't exist until WP2.6) enters as
    `delta_L * c_t` through the same exogenous cycle input the anchor consumes.
  - **The c_t contract for WP2.6:** an exogenous array in [-1, +1], shape
    `(months,)` or `(n_decades, months)`, consumed by the credit-gap norm and the
    policy anchor (an observation equation, never a state) — so WP2.6 swaps its
    regime-emitted c_t in at simulation time **without refitting L1**. Fitting on
    history uses `c_t = 1 - 2*USREC` (full-span NBER; recorded choice).
  - `fit.py`: panel assembly exclusively through `DataAccess.train_val`; **CAPE
    demeaned on the TRAIN span only, recomputed here** — `assert_train_only_
    normalization` refuses a full-sample demean, and tests prove (a) validation-era
    CAPE cannot move the constant, (b) holdout rows cannot reach the fit data at
    all (bit-identical panels either way). NUTS (dense mass, tree depth capped at
    8 after measuring ~0.13 s/gradient on the real panel), R-hat/ESS/divergences,
    posterior-predictive 90% coverage per channel, generated `climate-fit-report.md`,
    posterior artifact (npz) with a canonical content SHA-256 verified on every
    load, experiment-store record (config hash, git SHA, seed, vintage).
  - `simulate.py` (numpy-only, JAX-free): each generated decade draws `(theta, s0)`
    from the joint posterior — parameter uncertainty inside the ensemble, asserted
    by a dispersion test against the pinned-theta counterfactual; decade k seeded
    `base_seed + 7919*k`; `s0_date` selects any grid month (the WP2.11 severe test
    starts from the 1965 climate state this way); same file + same seed ⇒
    bit-identical paths (tested). `policy_anchor` helper for WP2.7 waypoints.
  - `scripts/fit_climate.py`: the provenance script for the real-panel fit on the
    sealed campaign vintage `2026-07-26.1` (offline, catalog-read, deterministic).
  - 61 new tests (`test_climate_model/fit/simulate.py`); no seal amendment needed
    (new files under `ah/gen/climate/` only — no judged source touched).
  - **Real-panel fit accepted** (`climate-fit-report.md`, artifact
    `sha256:98bdb68f…`, config `cfg:f7d4119c7101fd08`, seed 20260726, 133 min,
    4 chains x 750 draws): **0 divergences, max R-hat 1.0014, min ESS 1346**;
    PPC 90% coverage 0.88–1.00 across all ten channels. Slow states plausible:
    pi* half-life median 9.6y (prior rationale 8–20y), mu_r 0.88% +/- 0.67,
    phi_pi 0.62 (Taylor principle held, not imposed), b_val 6.3 (10y
    predictability slope). Recorded weak identifications: `delta_L` (credit-norm
    cycle link) is data-dominated-by-prior, and `sigma_g`'s lower tail touches 0
    — both flagged for WP2.6/WP2.7 rather than tightened away.
- **The sealed-claims sweep — every checkable sentence audited against the code, and
  the audit made standing. `pre-registration.lock` is now
  `sha256:2531904623db3d9e31c9dc234ae104cc8c010ed45223a381e94c6ba83312e585`** (supersedes
  `sha256:df5db7c8…`; 32 hashed files, unchanged set), amendments `AM-2026-07-26-006`
  (the sweep), `-007` (the digest note the append-only ordering made necessary) and
  `-008` (an eleventh finding, found after `-006` was already appended), all
  `post_hoc: false`. **Not one threshold, band, gate, floor, split, size or severity
  moved.** The digest moves because `factors.yaml`, `ah/eval/prereg.py`, `ah/splits.py`
  and `ah/eval/negative_controls.py` are hashed and their *prose* changed.

  **Eleven findings: seven in `pre-registration.yaml`, four in hashed source prose.**

  This closes a defect class rather than an incident. RFR-70 and RFR-71 were both
  sealed sentences describing checks the code did not perform; both survived multiple
  review passes; each was closed with its own single-purpose test and nothing
  generalised. The sweep read `pre-registration.yaml` end to end and checked every
  sentence asserting something about the code or the data against the implementation,
  and — where data-derived — against the sealed campaign vintage.

  - **Seven false claims, none of which moved a verdict.** (1) `factors.yaml`'s header
    still said `policy_rate` produced no train+validation data and called
    `missing_factors` "the sealed list of all three" — the **third** surviving copy of
    RFR-70's sentence; (2) `ah.eval.prereg._check_threshold_data_availability`'s
    docstring said the same — the **fourth**; (3) the thresholds header called
    `cross_block_corr_matrix_distance` "the one entry today" for a section that seals
    **35** of `PANEL_STATS`' **49** names; (4) `conventions.estimator_length_matching`
    said **THREE** statistics carry `length_matched=False` and then named four (four
    registration records carry it); (5) `conventions.warm_up`'s "about `0.95 * 5% =
    4.57%`" does not multiply — the factor is the *differential* warm-up fraction,
    `1 - (12/120 - 12/~800) = 0.915`, and 4.57% and everything downstream of it were
    right; (6) the Kupiec floor's stated implied interval `[0.0042, 0.1125]` is not the
    `LR = 6.635` contour, which is `[0.008328, 0.108796]` (counts `[1.00, 13.06]`) — the
    corrected interval is *narrower*, so the floor is slightly more demanding than the
    prose claimed; (7) `mc_error_grid.reading` attributed the ~3.8-fold 64→1024 reduction
    to `skew` and `acf_abs_sum`, which the sealed table puts at 4.52× and 5.60× —
    ~3.8× is `ust_10y.acf_r_lag1` (3.75×) and `excess_kurtosis` (3.69×).
  - **Two accounting/tense defects.** `seal_scope` calls this file's header and
    `ah.eval.prereg`'s docstring the full accounting of what is hashed, while
    `src/ah/eval/metrics/_pooling.py` and `src/ah/eval/negative_controls.py` were named
    in **neither** — both always hashed, so the *seal* was never short, only the
    accounting of it. And `tuning_protocol.prohibitions` sealed WP2.7's filter bar in
    the present tense ("asserted by test against this manifest") when no such test
    exists or can yet exist; it is now a stated requirement on WP2.7, exactly as
    `criterion_bearing_runs_only`'s refusal is on WP2.11. `ah/splits.py` also still
    called the sealed split dates "provisional".
  - **An eleventh finding, in a hashed source, found *after* the registry was drafted —
    which is the evidence that the registry's stated blind spot is real.**
    `ah/eval/negative_controls.py` cites
    `test_finding_the_monthly_tier_cannot_separate_nc3_from_the_undistorted_bootstrap`
    as the test its claim "rests on"; that test does not exist — WP2.2c Item 1 closed
    the finding and replaced it with two `test_closed_*` tests, and the citation was
    never updated. The same docstring also misstates the suite's own convention
    ("that test … **is deleted** in the same commit"; closed findings are *replaced*,
    not deleted). Caught by a one-off AST script, **not** by the new standing check,
    which covers `pre-registration.yaml` only. RFR-75 records the mechanical form of
    the missing check and leaves it explicitly unowned.
  - **What the sweep did *not* find, recorded because a clean result is a result.**
    Every `K = 4` absurdity bound reconciles exactly with its own quoted band (11 of 11,
    both sides); every `thresholds.strategies` bound is exactly `[historical/3,
    historical×3]`; the `mc_error_grid` band widths equal the quoted bands to six
    decimals; `reference_run.coverage` is internally consistent month for month; and
    `scripts/measure_seal_evidence.py` reproduces the D4 strategy statistics, the
    memorization null (n = 367, p05 0.0557, p50 2.0742), the spread-floor evidence and
    the RFR-12 momentum counterfactual **to every digit**. Every `verify()`, loader,
    `run_battery` and NaN-rule behavioural claim holds.
  - **Made standing: `pre-registration.yaml` now seals `claims_with_tests:`** — 31
    claims mapping every claim-shaped line to the test that pins it, 4 declared
    `not_a_code_claim` exemptions with reasons, and 1 claim with no test and an explicit
    `status: requirement_on_later_wp`. The trigger-phrase detector is **sealed**, so
    blinding the check is itself a lock violation. Three tests enforce it: every
    `pinned_by` resolves to a test that exists, every anchor still matches the sentence
    it locates, and **no claim-shaped line is unregistered**. Its limits are sealed
    beside it: it is a keyword detector rather than a reader; it checks that a named
    test *exists*, not that it asserts the claim; and it covers `pre-registration.yaml`
    only — four of this pass's findings were in hashed *source* prose, which stays
    uncovered and unowned. RFR-74.
  - Five new pin tests (`test_verify_rejects_active_blocks_that_disagree_with_the_manifest`,
    `test_the_sealed_seal_scope_accounts_for_every_hashed_file`,
    `test_the_sealed_length_matching_exception_count_is_the_registered_count`,
    `test_the_sealed_panel_section_states_its_own_size`,
    `test_loader_rejects_a_dead_zero_cost_leg_entry` — the last covering the half of the
    zero-cost-leg sentence nothing asserted). WP2.4's three-seed benchmark was re-run
    against the new digest: `criterion_bearing: true`, zero enforce failures, every
    gate value bit-identical.
- **WP2.3 final pass — four review findings closed, and a fresh seal.
  `pre-registration.lock` is now
  `sha256:df5db7c88c504e9fc2add7d36a439f4a75f867246ca9a674b72574c61c27840b`** (supersedes
  `sha256:42db2026…`; 32 hashed files, unchanged set), amendment `AM-2026-07-26-005`,
  `post_hoc: false`. **Not one threshold, band, gate, floor, split boundary, ensemble
  size or block length moved** — nothing in this pass is a re-measurement. The digest
  moves because two *judged sources* changed.

  - **A sealed scope justification rested on a false premise.**
    `seal_scope.splice_py_reason` claimed `policy_rate` and `hy_spread` are both in
    `reference_run.missing_factors` "precisely BECAUSE the backfills are absent".
    `missing_factors` is `[commodities, hy_spread]`: `policy_rate` is **present** on
    vintage `2026-07-26.1`, and what demonstrates `fedfunds_pre1954` is unapplied is its
    **start date** — `fred.FEDFUNDS`'s own 1954-07 rather than `fred.TB3MS`'s 1934-01.
    The correct wording already existed in `ah/eval/prereg.py`, `factors.yaml` and
    `S2-SEAL-SCOPE-2`, and was simply never carried into the sealed block. The
    *conclusion* — `splice.py` stays outside the seal — is unchanged and independently
    demonstrated per rule. RFR-70, which also carries `verify()`'s docstring ("if
    `lock_path` is given **and exists**"), describing behaviour that the previous re-seal
    itself removed.
  - **`criterion_bearing` claimed a check it did not perform, and the hazard was live.**
    `multi_seed_decision_rule.criterion_bearing_runs_only` names three conditions —
    sealed `ensemble_size`, sealed `campaign_vintage_id`, verified prereg + lock — and
    points at `BatteryReport.criterion_bearing` as recording them. The code compared
    `n_paths` and `months` and **nothing else**; `ensemble.meta.vintage_id` was carried
    onto every report and never compared. Two **incomplete** predecessor vintages remain
    on disk and reachable through the catalog's append-only pointer history —
    `2026-07-24` has no `fred.FEDFUNDS`, `2026-07-26` has no `fred.TEDRATE`, and
    `asof('2026-07-25')` / `asof('2026-07-26')` both resolve to `2026-07-24` — so a
    1024×120 run against either was stamped `criterion_bearing: true`. **The code was
    extended to meet the sealed sentence** (`ah.eval.battery.criterion_bearing_for`),
    rather than the sentence weakened to describe the code: that makes the sealed claim
    true and closes the hazard at the only place it can bite. RFR-71. WP2.11 still owes
    the hard refusal in `ah/eval/g2.py`; that half remains a requirement, and the file
    still says so.
  - **`beats_definition` clause (ii) is structurally empty for one of its two families —
    now disclosed.** The clause is scoped to usable *reference* bands, and
    `RegisteredStrategyStat` carries no `fn` by construction, so **no band exists or can
    exist** for any of the eleven strategy statistics. Clause (ii) is therefore evaluated
    entirely over the cross-block `tail_dependence_{lower,upper}` family (**63 usable
    bands**) and touches **zero** strategy-level metrics — it never covers
    `var_95`/`es_95`/`es_99`, which "NO TAIL-BAND REGRESSION over comparison-set metrics"
    read as if it did. **Disclosure only**: the clause is unchanged and still
    deterministic. The alternative — writing it against the sealed
    `thresholds.strategies` instead, which *would* cover them — is named in the sealed
    text and deliberately **not taken**, because adopting it with WP2.4's numbers already
    in hand is post-hoc; it is available as a dated amendment before any challenger is
    evaluated. RFR-72.
  - **The λ invariance argument does not survive incommensurable objectives.**
    `selection_lambda` **stays 1.0** and is not re-fitted; the stated *reason* was what
    overreached. `generative_objective` is a different quantity per arm — ablation system
    D runs two samplers, `hier-diffusion-v1` (an ELBO, a bound) and `hier-flow-v1` (an
    exact log-likelihood), separately selected because the trial budget is per system
    *per sampler* — so a fixed λ gives the D4 auxiliary a different **effective weight**
    per arm. Invariance is invariance of the **rule**, not of the weight, and no constant
    repairs it (a scale-aware value would have to be read off the trials, which the
    protocol forbids). **Binding on WP2.8:** report both terms of `S` separately, per
    system and per sampler, with their scales. RFR-73.
  - **WP2.4's evidence was re-measured against the final seal.**
    `scripts/run_bootstrap_battery.py` re-run at the sealed 1024×120 on campaign vintage
    `2026-07-26.1`, three seeds: **`criterion_bearing: true`, `prereg_verified: true`,
    verdict PASS, zero enforce failures — unchanged**, now carrying the new digest.
    Every reported number is identical to the pre-re-seal run: the band-exceedance rate
    (127/628 = 0.2022, then 126/628 = 0.2006 twice), the three gate values, the
    memorization surface, every `elicitability_score`, and the full enforce set.
  - **One artifact-integrity wart found by the re-run, and fixed.**
    `scripts/run_bootstrap_battery.py`'s `_results()` iterated the report document's own
    tier keys, and `BatteryReport.to_json` writes with `sort_keys=True` — so a document
    read back from disk yields `10yr, 1_5yr, economic, monthly` while an in-memory one
    yields `TIERS` order. A direct run and an `--analyse-only` re-derive therefore wrote
    `band_exceedance_census.outside_comparisons` in **two different orders**, with every
    value, count and rate identical. No number was ever affected, but a provenance
    script whose committed output depends on which mode produced it undermines the one
    claim it exists to make. The iteration order is now pinned to `TIERS`, so both modes
    agree. Not a judged source — no re-seal.

- **WP2.4 — `bootstrap-v1`, the frozen benchmark, and the battery's first false-positive
  measurement.** `src/ah/gen/bootstrap.py` implements the sealed `bootstrap_v1` spec and
  registers it in `ah.gen.registry`; it is the platform's first real generator and the
  standing comparison for every later PR. Nothing sealed was changed to produce these
  numbers — no threshold, no band, no gate, no negative control, and no line of
  `pre-registration.yaml`. `pre-registration.lock` verifies unchanged on every run.

  - **What was built, against the seal.** Politis-Romano stationary bootstrap, restart
    probability `p = 1/6` with a **circular** wrap, **multivariate blocks** (one shared
    row index across all twelve factors — tested exactly, on a source whose every column
    is an injective function of the row index, not statistically), stratified by the
    `regime_ruleset_v1` label of each block's **start month**. The draw span is *derived*
    from the panel and then checked against the seal: it comes back
    **1990-01…2020-12, 372 months**, over exactly the sealed twelve-factor `factor_set`,
    on campaign vintage `2026-07-26.1`. `EnsembleMeta.active_blocks` now has a producer
    (RFR-4), validated against `load_manifest().active_blocks` rather than trusted.
  - **THE HEADLINE: `bootstrap-v1` PASSES its own battery at the sealed criterion size**
    (1024×120, `criterion_bearing: true`, `prereg_verified: true`), with **0 enforce
    failures of 5** enforce comparisons, in **all three sampling seeds**.
  - **The sealed 200-path derivation reproduces exactly at 1024 paths.**
    `dependence_band_exceedance_fraction` **0.3611** (sealed prototype: 0.361, bound 0.5),
    `moment_band_exceedance_fraction` **0.0833** (sealed: 0.0833),
    `tail_band_exceedance_fraction` **0.1364** (sealed: 0.1364),
    `near_duplicate_fraction` **0.0644** (sealed at L=6: 0.065, bound 0.5),
    `nn_distance_p05` **0.694** (sealed: 0.693; floor 0.0279, cleared 25×). The three
    band-exceedance gates do not move with `n_paths` **at all** —
    `moment_band_exceedance_fraction`'s Monte-Carlo error is 3e-18 — because they are
    fractions over a *fixed* family of comparisons and more paths only sharpen each
    statistic without flipping any comparison. That is the mechanism behind RFR-44's
    warning that batch-means MC error is not the right sizing quantity for those gates,
    now observed rather than argued. **`mean_block_months: 6` behaves as sealed.**
  - **THE NUMBER THIS WORK PACKAGE EXISTS TO PRODUCE: the per-comparison band exceedance
    rate is 0.2022** (0.2006 in the other two seeds) — 127 of 628 usable banded
    comparisons — against the **0.10** the
    three gates' premise assumes (`limitations.null_exceedance_rate_is_unverified`). A
    plain resample of real history falls outside its own 90% reference bands at **twice**
    the nominal rate. Nothing was adjusted in response; the number is the finding. It
    does not move any verdict (the gates aggregate per family and all three pass), but it
    says the bands are not 90% bands *for a generator*, and WP2.5+ inherits that.
  - **Where the exceedances are, because the pattern is diagnostic.** 102 of 127 are in
    the `monthly` suite and almost all are one thing: every **level** factor's
    `acf_r_lag*`/`acf_r_sum` sits *below* its band (`policy_rate` 2.565 vs [3.755, 4.790],
    `ust_2y` 2.548 vs [3.726, 4.743], `cpi`, `ust_10y`, `hqm_curve`, `ig_spread`,
    `equity_vol`). A mean-6 block bootstrap cannot reproduce the near-unit-root
    persistence of a level series — a real, structural generator limitation, and the one
    the dependence gate is built to catch, which it registers at 0.361 against 0.5. The
    18 `horizon` exceedances (`variance_ratio_12m`, `mean_reversion_halflife`, every level
    factor) are the same defect seen through a second lens.
  - **The two `moment` failures are the two the seal predicted**, and both are era-scale,
    not era-mixing: `cpi.std` (36.85 vs [0.902, 16.81]) and `hqm_curve.std` (1.736 vs
    [0.633, 1.285]) — a level's dispersion over the 1990-2020 draw span against bands
    computed on that factor's own much longer, much lower-level history.
    `moment_gate_risk_measured`'s worry that era mixing would break `std` **did not
    materialise**: 2 of 24, exactly as sealed, unchanged at criterion size.
  - **Report-severity failures, none blocking:** `policy_anchor_deviation` 15.58 (a soft
    derived regularity a resample has no mechanism to hit), `ust_10y.acf_r_lag1` 0.7862
    (the only per-factor autocorrelation threshold sealed at all — the same mean-6
    persistence limit), `carry.var_95` 0.1379 / `carry.es_95` 0.2994, and thirteen
    `conditional`-suite metrics that are expected by sealed design.
  - **The five numbers `what_wp24_must_report` demanded are all supplied**, including the
    measured `elicitability_score` for every computable D4 strategy (`sixty_forty`
    **-2.540**, `momentum` **-2.391**, `carry` **-1.745**; `eqw_factors` and
    `endowment_proxy` NaN as sealed) and `term_premium` **1.573** /
    `equity_risk_premium` **0.00720**, both previously un-derived.
  - **The conditional suite ran, and its failure is the measurement the plan asked for.**
    Adherence errors: inflation 5.38pp (p90 10.32), rate 3.40pp (p90 5.50), crisis timing
    14.13 quarters (p90 28.0), crisis severity 10.46pp (p90 19.29). Off-support pass rate
    falls **0.531 → 0.031 → 0.000 → 0.000** across `typical`/`p95`/`p99`/`beyond`. The
    generator honours a regime *sequence* and nothing else, by sealed design; this is
    `conditioning_statement` measured, not a defect.
  - **`SEVERE_TEST_POSABLE = False`, in code.** The derived span starts 1990-01, so
    WP2.11's "exclude the 1970s, regenerate from 1965" is not posable for the benchmark
    and `G2-EVIDENCE.md` must record that row as NOT POSABLE.
  - **Two choices the seal did not make, recorded rather than buried.** (a) The WorldSpec
    schema enumerates eight regime names against the ruleset's six, so
    `recovery → EXP` and `deflation_boom → EXP` had to be chosen; the mapping is stated,
    exhaustiveness is tested, and every conditioned ensemble records its
    `requested_regimes`. (b) The plan's "(+slow-state-bucket)" stratification is **not
    implemented** — no slow-state model exists before WP2.5, and the sealed
    `stratification_statement` (which is the binding, self-contained definition) names
    only the start-month regime label.
  - **A second factor-resolution path, closed by a machine check.** `ah.gen` may not
    import `ah.eval`, and `ah.eval.panel` is a sealed judged source that cannot be
    refactored into a shared home without an amendment — so `bootstrap.py` carries its own
    `read_factor_frames`, and a test asserts it returns frames identical to
    `ah.eval.panel`'s for the real manifest.
  - `scripts/run_bootstrap_battery.py` is the provenance script (`--analyse-only`
    re-derives every number above from the committed `artifacts/wp24/battery-seed*.json`
    with no catalog); `tests/test_bootstrap.py` adds 31 tests (suite 1068 → 1099), every
    sealed constant asserted against `pre-registration.yaml` itself rather than restated.
    The per-seed battery reports are gitignored on the same reasoning as the other
    provenance-script outputs; `artifacts/wp24/summary.json` is committed because nothing
    else in the repository would hold these numbers.

- **WP2.3 re-seal — a new campaign vintage, and six defects in what was sealed.** The
  first seal froze campaign vintage `2026-07-24`, a snapshot taken *before*
  `fred.FEDFUNDS` was registered — so `policy_rate` had no data for reasons that had
  nothing to do with the data existing, and the seal made that permanent. A live refresh
  restored it (864 monthly observations, 1954-07 → 2026-06), the campaign vintage moved
  to **`2026-07-26.1`**, and every band, floor, strategy statistic and measured claim was
  re-derived. `pre-registration.lock` is fresh. Amendments `AM-2026-07-26-003` (the
  vintage move) and `-004` (the document defects), both `post_hoc: false` — no generator
  has been fitted, so nothing could be fitted to.

  - **What the vintage move restored.** `policy_rate` joins `reference_run.coverage`
    (1954-07→2020-12, n=798) and `bootstrap_v1.factor_set` (eleven factors → **twelve**);
    the **`carry`** D4 strategy becomes computable and gains sealed thresholds
    (`var_95` [0.0116, 0.1045], `es_95` [0.0173, 0.1561], from a measured VaR95 of
    0.03482 / ES95 of 0.05203 over 708 months); `term_premium`, `equity_risk_premium`
    and `policy_anchor_deviation` stop being NaN on every possible ensemble;
    `policy_rate.excess_kurtosis` is **restored** (at `report`, max 7.6079 — the first
    seal removed it, the pre-seal draft had it at `enforce`). Uncomputable D4 strategies
    go from three to two. **The check that the move touched only what depended on it:**
    every pre-existing per-factor band, and `sixty_forty`/`momentum`'s D4 statistics,
    came back **bit-identical**.
  - **What it did not fix, stated so it is not assumed.** `hy_spread` is still dead — 37
    observations, all inside the holdout; that is an ICE licensing limit on what FRED
    serves, not a stale snapshot, and no refresh will ever fix it. `commodities` is still
    unsourced, so `eqw_factors` and `endowment_proxy` stay uncomputable.
    `bootstrap_v1.block_draw_span` is still **1990-2020** because `equity_vol` (VIX)
    binds it, not `policy_rate` — now sealed as a machine-measured
    `block_draw_span_binding_factor` rather than asserted.
  - **The block-length window was re-measured and it MOVED.** Both edges are functions of
    the factor count. At twelve factors: L=3 fails the dependence gate at 0.537 (worst
    seed 0.556); **L=4's worst seed lands on exactly 0.500** against a `max` of 0.5 and is
    excluded on the knife-edge principle; `nn_distance_p05` now collapses to 0.0 at
    **L=10** rather than L=12, and L=8's margin falls 0.512 → 0.394. The window is
    roughly **5 ≤ L ≤ 9**, up from 4 ≤ L ≤ 8. `mean_block_months` stays **6**, now one
    step from the lower edge rather than mid-window — stated, not smoothed.
    `moment_band_exceedance_fraction` is 0.0833 (2 of 24) at every L, unchanged in
    substance. `scripts/measure_block_length_window.py` is the new provenance script; the
    first seal's numbers came from an uncommitted prototype.
  - **`ensemble_size.n_paths` 1000 → 1024, and its evidence moved inside the seal.** Two
    defects in one value: 1000 was a round number standing in for the 1024 the MC-error
    grid was actually measured at, and the grid itself lived in the *unsealed*
    `governance/decision-register.md`, editable with no amendment and no lock violation.
    The grid is now `ensemble_size.mc_error_grid`, re-measured on the new vintage at the
    sealed `mean_block_months`, with `scripts/measure_mc_error_grid.py` as its provenance
    script. **WP2.4 and WP2.8–2.10 must produce criterion-bearing ensembles at 1024×120.**
  - **The promotion rule's gating clause was unexecutable.** It said "beats bootstrap-v1
    on **the tail tier**" — but `battery.TIERS` has no tail tier and every tails-suite
    metric is registered `tier="monthly"`, so WP2.11 would have had to invent the
    definition *after seeing results*. `multi_seed_decision_rule.tail_tier_definition`
    now defines it as the `tails` **suite** with its two metric families named, and
    `beats_definition` states the objective (strictly lower mean `elicitability_score`),
    the no-tail-band-regression condition, the NaN direction, and the pooled arm as an
    exact inequality on the cross-seed mean and sd. Pinned by test against a live suite
    registration.
  - **The head-to-head is biased toward promotion, and it is now sealed.**
    `bootstrap-v1` resamples 1990-2020 only, while a challenger fitted on the full span
    has seen 1929-33, 1937, 1973-74 and 1987 — and both are scored against the *same*
    realizations. `multi_seed_decision_rule.benchmark_draw_span_bias` records it and
    obliges `G2-EVIDENCE.md` to report the comparison restricted to the common window
    alongside any PROMOTE.
  - **`tuning_protocol.selection_lambda: 1.0`.** The first seal said "at the config's own
    sealed lambda" and sealed no lambda anywhere — which pinned nothing and would have let
    each trial carry its own weighting. Authored, not derived, and named as such; the
    load-bearing property is invariance across systems, samplers and seeds, and it may
    never be selected from the trials.
  - **RFR-12 re-taken on measured evidence; RFR-9 finally answered.** With `policy_rate`
    present the `cash_tr_1m` residual leg is buildable, so the numeraire decision was
    re-taken rather than inherited from an impossibility argument that no longer holds.
    Still option (b): adding the leg truncates `momentum`'s sample 1134 → 798 months
    (ES99 0.15597 → 0.12923) while changing VaR95/ES95/VaR99/ES99 by **nothing at five
    decimals** on that same span — it corrects a mean-level bias invisible to every
    statistic sealed for `momentum`, at the cost of the worst tail in the record. Re-entry
    is now concrete (the `fedfunds_pre1954` splice from `fred.TB3MS`, 1934-01). RFR-9 —
    open since WP2.2 and assigned to WP2.3 — is closed as `S2-ENDOWMENT-WEIGHTS`:
    `endowment_proxy`'s `credit_xs_hy` 0.15 is a **risk budget**, not a capital share.
  - **`verify()` no longer tolerates a missing lock.** It skipped the lock check entirely
    when the file was absent, so `rm pre-registration.lock` made every battery run verify
    clean and silent — and a test *asserted* that behaviour. Naming a `lock_path` for a
    sealed document now asserts the lock is there. An unsealed document (the pre-seal
    state `seal()` is called from) is unaffected.
  - **Memorization floors re-derived**: the pooled historical null moved from p05 0.0548
    / p50 2.1660 (n=339, 11 factors) to **0.0557 / 2.0742** (n=367, 12 factors), so the
    sealed floors move to **0.0279 / 1.0371**. `scripts/measure_seal_evidence.py` is the
    new provenance script and calls the battery's own private helpers rather than
    reimplementing the search.
  - Count corrections: `structurally_unavailable_statistics` said "eleven names" for a
    twelve-name list; `d4_commodities_consequence` attributed both uncomputable D4
    strategies to `commodities` alone (`endowment_proxy` is independently blocked by
    `hy_spread`). New retrofit rows **RFR-61…RFR-69**.

### Fixed
- **`ah.data.refresh` silently dropped every fresh series from each new vintage.** A
  vintage is documented as a complete as-of snapshot and every read pins exactly one, but
  `plan` only fetches series that are *missing or stale* — so the first refresh after the
  initial build wrote only the due series and every fresh one vanished from pinned reads,
  reporting 0% coverage in `GAPS.md` while its observations sat on disk under the older
  vintage. `fred.TEDRATE` (retired 2022-01, therefore never stale under its 9999-day SLA)
  fell out of the `2026-07-26` vintage, taking `funding_spread` with it. `Catalog.
  latest_vintage_with()` plus `refresh._carry_forward()` now re-stamp every already-held,
  not-refetched series into the new vintage; immutability is untouched (a new
  `(vintage, series)` key, the older vintage byte-identical) and carried rows are not
  re-submitted to QC, because re-judging unchanged history against a later as-of date
  would quarantine a vintage for the sole reason that a retired series is still retired.
  `ah data refresh` reports the carried count. This is why the campaign vintage is
  `2026-07-26.1` and not `2026-07-26`. (RFR-62.)

- **WP2.3 — the pre-registration seal. This is the one-way door.** `pre-registration.yaml`
  is `sealed: true` and `pre-registration.lock` is committed, hashing 32 files: the
  document, `factors.yaml`, all eight metric suites, `reference.py`, `battery.py`,
  `panel.py`, `prereg.py` itself, `g2.py`, `splits.py`, `strategies.py`, `factors.py`,
  `negative_controls.py`, `_pooling.py`, both battery report modules, and the eight
  authored conditional worlds. `run_battery` now verifies the document **and the lock**
  on every invocation, so a modified YAML or a modified enforce-metric implementation
  stops the battery. From here, every change to any of those files is a dated,
  post-hoc-flagged amendment in `governance/amendment-log.yaml`.

  - **Every band comes from one reference run on this commit.** RFR-25 required it: six
    metric names changed *meaning* and two changed *value* during WP2.2's fix passes, so
    no pre-WP2.2c number survives. `scripts/compute_campaign_reference.py` is the
    provenance script; its constants are asserted equal to the sealed `reference_run:`
    block (vintage `2026-07-24`, seed 20260726, 1000 resamples, level 0.9, block length
    120, replicate length 120).
  - **The reference run found a live defect (RFR-5, closed).** Three of fourteen declared
    active factors have no train+validation data on the frozen vintage — `commodities`
    (declared unavailable), `policy_rate` (the vintage predates `fred.FEDFUNDS`'s
    registration) and `hy_spread` (its ~3 licensed years all fall inside the holdout).
    `policy_rate.excess_kurtosis` was sealed at **enforce**; under THE ONE NaN RULE it
    would have failed every run forever. Removed, and `verify()` now rejects any
    threshold keyed to a factor or D4 strategy with no computable statistic. Corollary:
    **three** of five D4 strategies are unevaluable, not the two
    `rationale.d4_commodities_consequence` named.
  - **The ensemble size is sealed** (`n_paths: 1000`, `months: 120`), on the owner's
    direction, because the gates' power rises without limit in ensemble size while their
    bounds do not move: `max: 0.5` at 16 paths is not the same criterion at 1000.
    Justified by a measured MC-error/band-width analysis (worst ratio 0.039 at n≈1024
    against 0.149 at n=64). Any other size is recorded `criterion_bearing: false` on the
    report and may not be cited at G2. **WP2.4 and WP2.8–2.10 must use it or amend.**
  - **`bootstrap-v1`'s full spec is frozen, and both of its enforce risks are measured.**
    Politis–Romano stationary bootstrap, **geometric blocks with mean 6 months**,
    regime-stratified on `regime_ruleset_v1`, over the eleven factors with data. The
    block length is bounded *below* by `dependence_band_exceedance_fraction` (mean block
    3 measures 0.515 and fails the 0.5 gate) and *above* by the memorization surface
    (`nn_distance_p05` collapses to 0.0 once the verbatim-window rate `(1-1/L)^23`
    exceeds its own 5th percentile, at L≈8); 6 is the middle. `near_duplicate_fraction`
    clears at every length tested — RFR-40's ~0.93 was a *fixed*-24-block number and does
    not transfer to geometric lengths. The length-matched `std` risk was checked too:
    `moment_band_exceedance_fraction` is 0.091 at every L from 3 to 24.
  - **New finding: the benchmark cannot run the severe test.** A multivariate block
    bootstrap over every factor with data can only draw from **1990-01 to 2020-12** —
    `equity_vol` (VIX) starts 1990 — so `bootstrap-v1` reaches no pre-1990 episode, and
    WP2.11's "exclude the 1970s, regenerate from 1965" test is *not posable* for it.
    Sealed as the benchmark's largest single defect, with the three routes out named.
    (RFR-56.)
  - **What the seal does not establish**, now inside the hash as a `limitations:` block:
    the gates' null exceedance rate is **unverified** (0.10 per comparison is the band's
    definition, not a measurement, and metric correlation breaks the independence the
    analytic rate assumes); the three band-exceedance gates were **designed against** the
    negative controls, so "catches 4 of 5" is not independent validation of their design;
    and **every** negative-control magnitude comes from a synthetic 16-path fixture, not
    the campaign vintage. Nine further sealed limitations cover the pooled-vs-per-path
    band mismatch, the tail gate's inability to fire at enforce, knife-edge comparisons,
    unjudged within-block correlation, and four named estimator substitutions.
  - **Owner decisions recorded, not disclaimed.** `S2-NC5-EXEMPTION` (the plan
    contradicts itself at lines 89 vs 93; line 93 governs, the conditional tier stays
    non-gating, NC5's exemption is a named narrow exception — and the pinning test now
    asserts **which** gate blocks NC5, not merely that something does);
    `S2-SPREAD-FLOOR` (RFR-41 ratified on measured evidence: 54.0% of `ig_spread` and
    86.9% of `funding_spread` observations sit below the old 100bp floor, none below
    0.0); `S2-NUMERAIRE-BIAS` (RFR-12 sealed as a stated bias — the `cash_tr_1m` residual
    leg was *impossible*, since it derives from the dataless `policy_rate`);
    `S2-SEAL-SCOPE-2` (`derive.py` sealed because it is on the read path, `splice.py` not
    because its proxy rules are registered but unapplied — and neither backfill is in the
    campaign vintage, which answers RFR-10's standing question).
  - **New `verify()` checks, all running on every battery invocation:** the sealed
    `splits:` block must equal `ah.splits.SPLITS` (RFR-6); no threshold may name a factor
    or strategy with no data (RFR-5); no `enforce` threshold may name a
    `structurally_unavailable` statistic (twelve names, 25 metric instances, each with
    the work package that restores it); and the sealed `ensemble_size` is checkable
    against a run's own size.
  - **The human gate is discharged by pre-authorization.** `AM-2026-07-26-001`
    (`post_hoc: false`) is the amendment log's first entry and names exactly what is
    provisional and what the D6 workshop must ratify. `AM-2026-07-26-002` corrects an
    omission in it — the plan requires a "capped trial budget stated in
    pre-registration" and none existed, so WP2.3 authored one
    (`tuning_protocol.trial_budget_per_system: 40`) and the first entry failed to list
    it as authored. The log is append-only, so the correction is a second entry that
    names the omission, which is also the first exercise of the amendment machinery
    against the real file.
- **WP2.2c — battery hardening: the battery can now reject a known-bad generator.**
  WP2.2b registered five deliberately broken generators and the battery passed all five;
  absent one accidental `floor_violations` failure that fired identically for every
  control (including those replaying real history verbatim), `BatteryReport.passed` would
  have been `True` for all five. Four of the five are now caught at **`enforce`** level by
  a **discriminating** gate inside their **designated** cell, and `shared_enforce_failures`
  is empty — no gate fires for everything.

  - **Item 1 — the three statistics whose bands existed and were never consulted.**
    `ah.eval.metrics.monthly` now emits `<factor>.mean`, `<factor>.std` and
    `<a>~<b>.correlation`. `reference.py` had registered all three and computed a real
    length-matched band for each since WP2.2; no suite ever computed the generated-side
    value, so a location/scale drift of any size was invisible. `mean`/`std` use the
    **per-path-then-averaged** convention (the reference band is the sampling
    distribution of the same single-series functional, so pooling would fold
    between-path mean dispersion into `std`); `correlation` is pooled, matching its
    `crisis_corr_lift` sibling. Deliverable:
    `test_closed_the_monthly_tier_separates_nc3_from_the_undistorted_bootstrap` — at a
    shared seed, where NC3's paths are a bit-exact affine transform of NC5's, the two
    band-failure sets were previously *identical* and NC3's are now a strict superset on
    the drift-sensitive names.
  - **Item 2 — `near_duplicate_fraction` measures copying, not block phase.**
    `ah.eval.metrics.memorization` searches each generated block against **every offset**
    of the TRAIN split (stride 1) instead of an index-0-anchored 24-month grid, with the
    epsilon recalibrated on the same search (a minimum over ~830 candidates is
    systematically smaller than one over 34; enlarging the search alone would have been a
    false-positive machine). A literal zero-noise verbatim copy went **0.2423 → ~1.0**;
    the same copy snapped to the grid **0.8875 → ~1.0**, i.e. phase now carries no
    information; NC4 **0.0654 → 0.7096**. A short-block resampler scores ~0.05–0.33.
  - **Item 3 — the `enforce` set chosen on evidence.** Three new `PANEL_STATS` gates
    (`moment_`/`tail_`/`dependence_band_exceedance_fraction`) make DN-1.1 §II.6's band
    criterion blocking *as an aggregate over a family*, because a per-name band gate at
    ~570 comparisons and a 10% miss rate would reject a perfect generator. The bound
    (0.5) is derived from the sealed band `level` and a majority rule (Markov: ≤0.2
    false-positive under arbitrary dependence; Hoeffding over ~13 factor units gives the
    same 0.5 at α=0.01) — no control's value was consulted. Two supporting statistics
    were added, `acf_r_sum`/`acf_abs_sum` (Box–Pierce without the `n` scaling): the
    first version of the dependence gate aggregated all 403 per-lag comparisons and
    scored NC1 at 0.367, because a 120-month per-lag band is wide; summing the *values*
    and banding the sum moves NC1 to 0.615. **The bound did not move; the statistic did.**
    `near_duplicate_fraction` was promoted to `enforce` at a bound **10× looser** than
    the one it replaced (0.05 → 0.5, since 0.05 is the metric's own null by construction).
  - **Item 4 — `SPREAD_FLOOR_PCT` 100bp → 0.0.** A 100bp floor rejects the historical
    record (TED sat at 15–40bp for most of 2010–2020), which is why it fired for all five
    controls and detected nothing. DN-1.1 §II.4's floors are a *generative* softplus
    device; the falsifiable audit that survives is that a spread cannot be negative. It
    now fires for `nc1-iid-gaussian` alone. Recorded as a stated deviation from DN-1.1's
    literal number (`governance/retrofit-register.md` RFR-41), for WP2.3 to ratify.
  - **Item 5 — the 10yr tier is disclaimed, not fixed.** 73% structurally unavailable;
    all three causes are missing *inputs* (no CAPE/valuation factor, no recession/growth
    indicator, an `ergodicity_gap` needing a path no generator emits) and none can be
    closed without inventing a factor. `conventions.ten_year_tier_coverage` states the
    count, that NC2 is designated there and caught nothing, and that `G2-EVIDENCE.md`
    must not cite a 10yr pass (RFR-42).
  - **Item 6 — knife-edge comparisons made visible.** Every banded result carries
    `band_distance` (signed margin; `0.0` = exactly on an edge) and `band_degenerate` in
    the JSON, plus a `band dist` markdown column: a zero-width band can be satisfied
    only by exact floating-point equality, and 33 exist in the synthetic-fixture run
    (35 in a real run against `factors.yaml`). This carries two DIFFERENT consequences,
    corrected here to distinguish them (WP2.2c honesty fix pass): the raw
    `band_distance`/`band_degenerate` values are unconditionally preserved in
    `MetricResult`/its JSON for every metric, degenerate or not (`battery.band_is_usable`
    only ever gates the *aggregate* `*_band_exceedance_fraction` metrics, never the raw
    report) — but `ah.eval.negative_controls`'s own `band_failures` list, which the
    negative-control report table uses as per-control evidence, calls
    `battery.outside_band` (itself gated by `band_is_usable`), so a degenerate-band
    comparison no longer counts there either. In the real run, 2 of the 35 degenerate
    comparisons (both `nc1-iid-gaussian`) were previously reported `band_failures` and
    are not anymore — a real, if small, evidentiary change, not merely a cosmetic one.

  **Not closed, disclaimed:** `nc5-condition-ignoring` is not caught at `enforce` in its
  designated cell, because the conditional tier is non-gating by
  STEP2-GENERATOR-PLAN §WP2.3's sealed decision rule, which this work package was
  directed not to change (it is detected there on 14 of 16 metrics, and blocked
  elsewhere). `tail_band_exceedance_fraction` stays `report`: a majority rule cannot fire
  on a tail failure confined to the 4 return-bearing factors of 13, so NC1 is blocked by
  the dependence gate rather than by the tail machinery that correctly detects it
  (RFR-43). A block bootstrap with blocks ≥ 24 months now fails the memorization gate —
  correctly, but WP2.4's `bootstrap-v1` must use shorter blocks or carry an amendment
  (RFR-40). No negative control was weakened and no threshold was tuned to make one fire.

- **WP2.2c honesty fix pass — disclosure findings inside the text WP2.3 is about to
  hash.** No threshold moved and no control was weakened; every change below is text and
  disclosure, plus one public-name promotion. **Critical 1**: `BAND_EXCEEDANCE_FAMILIES`'s
  moment/tail split is an undisclosed, outcome-determining degree of freedom, not a
  DN-1.1 mandate — DN-1.1 Sec.II.6's monthly row names no `mean`/`std` at all, and its
  citation was doing more work than it can bear. `skew` is affine-invariant like
  `mean`/`std`; moving it into the moment family flips `nc3-shifted-bootstrap`'s
  `moment_band_exceedance_fraction` 0.654 (FAIL) → 0.487 (PASS) at a real run against
  `factors.yaml`. Now recorded in full in `pre-registration.yaml`'s
  `band_exceedance_gate_estimator` convention and `ah.eval.metrics.monthly`'s
  `BAND_EXCEEDANCE_FAMILIES` comment, including that a reader may reasonably disagree
  with the taxonomy shipped. **Critical 2**: `ah.eval.metrics.monthly`'s module docstring
  claimed the moment gate's margins were "not knife-edge... drifted control near 1.0,
  undistorted near 0.1" — the measured values are 0.654 and 0.231, and
  `pre-registration.yaml` already said so; the docstring is corrected to match.
  **Important 3**: the three `*_band_exceedance_fraction` gates' design (summed ACF over
  per-lag aggregation) was chosen by measuring three candidates against the five negative
  controls — for these three gates the controls are therefore no longer independent
  design evidence, only evidence the sealed 0.5 bound isn't trivially satisfied.
  Recorded in `pre-registration.yaml` and `governance/retrofit-register.md` (RFR-45);
  `bootstrap-v1` (WP2.4) is named as the first genuinely independent test. **Important
  4**: `near_duplicate_fraction` at `enforce` is named as the eleventh instance of this
  work package's dominant failure mode and the first inside the blocking surface —
  `nc1-iid-gaussian` scores a perfect `0.0` on it, which is structural (nothing shares
  block structure with an iid series) and plan-grounded, not a defect, but a reader must
  not read the pass as fidelity evidence. **Minor**: four wrong numbers corrected —
  `near_duplicate_fraction`'s NC4 score (~1.0 → 0.7096) and its "cleared the old bound by
  31%" claim (was actually a *failure* of the old 0.05 bound by 31%); the dependence
  family's Binomial tail probability (~1e-30 → 1.0e-10, a 20-order-of-magnitude
  correction); the Hoeffding family-wise error rate (1% → 1.56%,
  `exp(-2·13·0.4²)`); and the claim that a degenerate band "is not removed from the
  report" — true for the raw `MetricResult`/JSON, but `ah.eval.negative_controls`'s own
  `band_failures` list (via `outside_band` → `band_is_usable`) does drop degenerate-band
  comparisons, 2 of which (both `nc1-iid-gaussian`) were previously reported failures.
  Two stale passages reconciled: `negative_controls.py`'s "bands... gate nothing" claim,
  overtaken by Item 3's aggregate gates; and the private `battery._lookup_band` import
  from a second sealed module, promoted to public `battery.lookup_band`. Two live,
  not-implemented options recorded for WP2.3 in `governance/retrofit-register.md`: a
  baseline-relative memorization bound (RFR-46, no longer blind now that Item 2 fixed
  phase-blindness) and a per-factor tail-gate combination (RFR-47, with the caveat that
  validating it on NC1 would repeat the Important-3 problem).

- **WP2.2b Task 7 review fix pass — evidence-integrity findings in the negative-control
  suite.** Three claims in the sealed, `G2-EVIDENCE.md`-cited text asserted more than the
  evidence supported; corrected without touching any control's construction or any
  `pre-registration.yaml` threshold (the red result stands). **Critical 1**: the paired
  NC3-vs-NC5 monthly-tier comparison (`tests/test_negative_controls.py`) compared two
  INDEPENDENTLY seeded ensembles (`seed+7919*2` vs `seed+7919*4`) via `<=`, which held by
  a one-metric margin and would flip on a different seed; replaced with a same-seed
  comparison verified bit-exact-affine (`np.array_equal`) and an exact
  `set(nc3.band_failures) == set(nc5.band_failures)`. **Critical 2**: NC5's conditional-
  suite rejection was described as "unambiguously about conditioning" -- false, since
  every control ignores `factor_conditions` and the tier fires for all five (NC1 alone
  fires 12 of NC5's 14 designated conditional metrics and is ~10x worse on
  `condition_adherence_error_inflation`); corrected, and the missing condition-honouring
  control recorded (`governance/retrofit-register.md` RFR-39). **Critical 3**: a
  threaded-OpenBLAS hypothesis for the suite's rare battery-verdict non-reproducibility
  is FALSIFIED (the 4340-value metric digest is bit-identical at
  `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS` = 1, 8, and default) and downgraded to
  unexplained; the real, measured, sufficient explanation -- 148 of 3035 finite banded
  comparisons sit at exactly zero distance from a band edge, 33 on a fully degenerate
  `[0.0, 0.0]` band -- is now recorded (RFR-38). Also: `ah.eval.negative_controls`'s "13
  of the 10yr tier's 22 metrics are structurally NaN" corrected to the true figure, 16 of
  22 (73%, not 59% -- three carry `band=None` and never land in the report's own NaN
  buckets), and `regime_duration_*` confirmed to sit at the `1_5yr` tier, not `10yr`
  (RFR-37); `near_duplicate_fraction` shown to be dominated by block-PHASE alignment
  rather than by copying, which changes the shape of remedy WP2.3 should consider
  (RFR-36); a `caught_at_criterion` column added to `NegativeControlReport` alongside the
  renamed `caught_on_any_surface`, so a reader can no longer misread `criterion: enforce`
  next to a "caught" cell as an enforce-level catch (RFR-35); `run_negative_controls` now
  restores `ah.eval.battery.SUITES` symmetrically with its existing `gen_registry`
  restore; `ah.gen.registry` gained public `snapshot()`/`restore()` so
  `negative_control_registry` no longer reaches into `_REGISTRY` directly. Six new rows
  in `governance/retrofit-register.md` (RFR-34..RFR-39) carry every finding this fix pass
  could not itself close.
- **WP1.10 — Refresh orchestration, scheduling, CLI.** `refresh.py`: `plan`
  (manifest ∩ due-by-SLA ∩ source, auto-intake only) → provider fetch/parse → QC →
  vintage commit or quarantine → reports; idempotent (re-running a vintage id is a
  detected no-op). `ah data` CLI: `refresh [--fixtures --vintage --source --asof
  --dry-run]`, `status`, `asof DATE`, `episode YEAR`, `intake validate <file>`.
  GitHub Actions `data-monthly.yml` (cron public refresh, status artifact, issue on
  QC failure) and `data-reminders.yml` (calendar issues for manual intakes); local/dev
  works without cloud.
- **WP1.9 — Gap register & reports.** `reports.py`: `gap_register` computes per
  required series coverage %, missing head/tail, staleness, and license blockers from
  the manifest vs the catalog; `generate_gaps_md` emits GAPS.md with an "anticipated
  additions" section (MSCI World, commodities, HFRI, EDHECinfra, PitchBook/LCD,
  dry-powder, Green Street, SOA mortality, daily equity) and the emergent-requirements
  rule. `generate_data_status_md` emits DATA-STATUS.md (vintage, per-source freshness,
  QC summary, revision-diff highlights).
- **WP1.8 — Episode packs.** `episode.py`: builders for 2008-10, 2020, 2022-23 that
  resolve inputs **through the catalog** (no ad-hoc reads), slice to the episode
  window, add reported-vs-de-smoothed private-markets sleeves, attach the cited
  secondary-pricing table (`docs/data/secondaries.md`, incl. the ~81% NAV 2022 anchor),
  and render a markdown brief. These are the fixtures Gate G1's reproduction test will
  consume.
- **WP1.7 — De-smoothing module.** `desmooth.py`: Geltner AR(1) reversal
  (r_true = (r_obs − (1−a)·r_obs,lag)/a, a = 1−phi); GLM MA(k) — θ≥0, Σθ=1 estimated
  on the simplex by whitening the recovered truth, k∈{1,2,3} by AIC (default 2), with
  a boundary-solution fallback to Geltner (+warning) when θ₀≥0.9; experimental
  regime-split `regime_glm`. Diagnostics (σ ratio, β to equity before/after, mean
  difference, Ljung-Box) rendered to `DESMOOTHING.md`. Hypothesis property:
  smooth-then-de-smooth recovers volatility within tolerance. numpy-only, deterministic.
- **WP1.6 — Derived metrics & factor panel.** `derive.py` primitives (spreads/excess
  returns via `difference`, `yoy`, `realized_vol`, `drawdown_state`,
  `demeaned_log_cape` = DN-1 v_t, `credit_to_gdp_gap` = L_t with JST pre-1961
  extension, `funding_stress` with TED→SOFR cutover). Regime labels v1: a single pure
  `label_regime` + `regime_thresholds.yaml` stamped `regime_ruleset_v1`, `label_series`,
  and an NBER confusion report. Panel assembly (`assemble_panel`) asserts no monthly
  gaps after each column's start, carries a `UNITS_REGISTRY`, and `generate_panel_md`
  produces the data dictionary.
- **WP1.5 — Splice & proxy framework.** `splice.py`: `ProxyRule` + fitted transforms
  (regression/level_map/ratio/scale), backward extension to `<target>__extended` with
  per-obs `is_proxy` + rule id (actuals never overwritten), `overlap_error`. Register
  rules: HY OAS pre-1996, long-Treasury TR pre-1973, private credit pre-2004, Nareit
  de-levered RE.
- **WP1.4 — QC framework.** `qc.py`: per-series checks (schema/dtype, monotonic
  non-duplicate dates, frequency conformance, unit-class bounds — rates [-5,30],
  spreads ≥0, index >0, returns [-80%,+200%], staleness vs SLA, jump detection using
  the prior window's σ, revision diff vs prior vintage with source-based severity:
  public revisions warn, licensed rewrites enforce) + cross-series identities
  (Baa ≥ Aaa). Severity inherits the manifest `enforce` flag. `run_qc` persists
  `qc_results` and quarantines the vintage on any enforce failure — the pointer then
  cannot advance. `Requirement` is now frozen/hashable.
- **WP1.3 — Manual-intake framework + licensed schemas.** `schemas/base.py`
  (declarative `IntakeSchema`: required columns, dtype/bounds, duplicate-period and
  silent-gap detection, human-readable rejection report) + concrete schemas:
  Albourne PM returns, Albourne HF returns, Albourne derived cashflow groups A-E
  (lifecycle p25/p75, calendar rates, age×calendar with fund counts, vintage
  quartiles, episode cuts), Cliffwater CDLI, Nareit, NCREIF. `intake.py`:
  `<series-group>_<asof>` filename convention, checksum, validate (never partially
  ingested), `to_series_frames` (strategy→canonical series), `ingest_file` records
  provenance to `intake_log`. Corrupted fixtures (dup/out-of-bounds/missing/gap)
  rejected with a report; clean fixtures round-trip to parquet.
- **WP1.2 — Public connectors.** `connectors/base.py` (Connector protocol,
  RawArtifact, D->M aggregation: monthly mean for rates/spreads, month-end for VIX;
  retrying fetch helper) plus FRED (observations JSON), Ken French (zip/CSV,
  monthly-block/annual-block quirk), Shiller (xlsx, content-located header, fractional
  dates), JST (.dta, USA filter), BIS (credit-gap CSV), Treasury HQM (xlsx, 10y spot).
  `fetch()` is network-only (never tested); `parse()` covered by golden tests over
  format-faithful offline fixtures (`scripts/gen_data_fixtures.py`). `docs/data/<source>.md`
  per source (URL, license, quirks). Added `openpyxl`.
- **WP1.1 — Manifest, catalog, vintage store.** `requirements.yaml` (normalized seed
  of STEP1-DATA-PLAN §3) + `ah/data/manifest.py` (typed `Requirement`/`Requirements`,
  redistributable = FREE only). `ah/data/catalog.py`: DuckDB catalog
  (`series`, `vintages`, `observations_index`, `current_pointer`, `intake_log`,
  `qc_results`) with an immutable Parquet vintage store — canonical schema
  `(date, value, series_id, vintage)`, re-writing a (vintage, series) raises,
  the `current` pointer is append-only and advances only when a vintage is not
  quarantined (QC gate), and `as_of` reads resolve through the pointer history.
  Added `duckdb` + `pyarrow` deps.

## [Unreleased] — Step 2 (generator layer)

### Fixed
- **WP2.2 Task 3 review fix pass 1 — two sealable bands that could not do their job.**
  - *The two decade-frequency statistics had a Bernoulli band, i.e. no band at all.*
    `lost_decade_frequency` and `long_inflation_era_frequency` were a single 0.0/1.0
    indicator over the whole input, so every bootstrap replicate returned 0 or 1 and the
    percentile band could only be `[0, 1]` (admits every possible value) or
    `[0,0]`/`[1,1]` (fails every generator with a non-zero rate) — and the historical
    frequency, the *mean* of that resample distribution, was never formed anywhere
    (`block_bootstrap_band` takes percentiles, not a mean). Both are now genuine
    frequencies: the fraction of the input's own **overlapping 120-month windows**
    satisfying the property. Stated consequence: a 120-month replicate holds exactly one
    window, so both are registered `length_matched=False` (`RegisteredStat`) and their
    replicates are drawn at the **full train+validation length**, recorded as
    `resample_length: null` on the band — the correct reading of
    `conventions.estimator_length_matching` (which exists because the ACF estimator is
    length-biased) rather than an exception to it. The band is consequently wide,
    reflecting history's ~9-14 independent decades, which is DN-1.1 §II.6's "honestly
    reported (n≈14)" for this tier. Non-degeneracy (`0 < lo < hi < 1`) is now asserted on
    a century-long `compute_reference` run.
  - *`ergodicity_gap` was algebraically `|variance_ratio_120m − 1|`.* At production path
    length the pooled variance ratio at k=months yields one sum per path, making the old
    gap the same number under a second sealed name — the duplication this file already
    refused when it dropped `agg_gaussianity` horizon 1 for being `excess_kurtosis`. Its
    `Var(pooled)/months` null was also iid-within-path, under which a *correct* generator
    of a persistent factor (φ=0.9 AR(1) → ≈18) read as catastrophically non-ergodic.
    Redefined as DN-1.1's actual metric — long-path time average vs ensemble
    cross-sectional average, in units of pooled dispersion, with no iid null in it — and
    marked `structurally_unavailable` because `run_battery` is handed no long path
    (RFR-20). The estimator is built and tested against ergodic, persistent-ergodic and
    genuinely non-ergodic processes, ready to wire.
  - *Drawdown metrics could be gamed by generating less, twice over.* Added
    `DRAWDOWN_MIN_EPISODES = 10` (shared by the reference and ensemble sides), and an
    overflowed path — `wealth/cummax = inf/inf = nan`, and `nan < 0.0` is `False`, so it
    was silently recorded as having **no drawdowns**, the favourable answer, then dropped
    from the pooled concatenation — now NaNs the metric. Same fix for
    `lost_decade_frequency`'s overflowing product.
  - *Guards and markers.* The 10yr MC-error guard is now exercised **through**
    `run_battery` (no code path could trigger it before); `MetricSpec` gains `status`
    (`structurally_unavailable`) and `metadata`, both surfaced in `to_dict()` and the
    markdown, so a platform gap is distinguishable from a generator failure and
    `REGIME_RULESET_VERSION` finally reaches the report; `StatBand` gains
    `n_valid_resamples`, making RFR-19's NaN-band degeneracy visible in the artifact.
  - *Governance.* Ten new `conventions.<stat>_estimator` blocks in
    `pre-registration.yaml` (plus `elementary_moment_estimators`,
    `crisis_corr_lift_estimator` and `mc_error_is_not_the_small_n_band`), with
    `prereg.ESTIMATOR_CONVENTION_KEYS` + a two-way machine check so no statistic can be
    registered without a sealed definition; the two ensemble pooling conventions moved to
    `ah/eval/metrics/_pooling.py` (and added to the sealed judged-source set); RFR-20
    (ergodicity), RFR-21 (the nominal-not-real lost-decade row `reference.py` claimed
    existed but did not), RFR-22 (§WP1.9 considered and inapplicable to RFR-17/18).
- **WP2.2 Task 1 review fix pass — the mapping is now actually read, the policy rate is
  a policy rate, and there is one numeraire.**
  - *The mapping was not wired in.* `compute_reference` took a `series_id_for` callable
    defaulting to identity and nothing ever passed it the manifest, so every factor id
    went to the catalog verbatim, every factor landed in `missing_factors`, and the
    reference came back **empty with no error** — while `build_panel`, which did read
    the mapping, had zero production callers. The two surfaces were also structurally
    incompatible (`FactorManifest.series_id_for` *raises* for `kind: derived`). Fixed by
    extracting `ah.eval.panel.read_factor_frames` as the single factor-id → series
    resolution surface; `build_panel` assembles on top of it and `compute_reference`
    computes statistics on top of it, so the panel a generator is fitted against and the
    bands WP2.3 seals can never resolve a factor differently.
  - *`policy_rate` → `fred.TB3MS` (a 3-month bill) replaced by `fred.FEDFUNDS`*, the
    administered rate, registered in `requirements.yaml` under the §WP1.9
    emergent-requirements rule with a `fedfunds_pre1954` splice rule backfilling
    pre-1954-07 history from `fred.TB3MS` (`is_proxy`) and an offline connector fixture.
    The bill was wrong twice over: it is a market yield that decouples from the funds
    rate in exactly the crisis months the tail/severe tiers judge, and it is also the
    short leg of `funding_spread`'s TED — so the two factors would have shared a
    construction-driven stress component and the cross-block correlation and
    crisis-correlation-lift bands would have been sealed over an artifact of the mapping.
  - *One numeraire.* `equity_mkt` mapped to Fama-French `Mkt-RF` (an **excess** return)
    while `govt_tr_10y` is a **total** return, and `sixty_forty`/`endowment_proxy`
    weighted them together. `equity_mkt` is now `kind: derived`,
    `add(french.mkt_rf, french.rf)` — a genuine total return. `conventions.numeraire:
    total_return` is sealed data, and `ah.strategies` now rejects a D4 strategy whose
    legs do not all resolve to it (or to an explicitly declared, self-financing
    `zero_cost` overlay: `smb`/`hml`/`mom`/`credit_xs_hy`). `FactorSource` gains
    `numeraire`, and `proxy`/`proxy_for` so a splice-backed backfill is machine-visible
    rather than free text in `notes`.
  - *One NaN rule.* `ah/battery/report.py::evaluate` treated a NaN metric as PASS while
    `ah/eval/battery.py::_passed` treated it as FAIL — two rules, both inside the seal.
    Now **NaN = FAIL** in both, stated in both modules and in
    `conventions.nan_metric_rule`. This is a deliberate behaviour change to Step 0's
    battery: an uncomputable metric has not demonstrated compliance.
  - *`mc_error` sub-ensembles no longer lie about their size* (`dataclasses.replace(
    meta, n_paths=len(idx))`); `Panel`/`ReferenceStats` split `missing_declared` from
    `missing_no_data`; `ReferenceStats.coverage` records each factor's train+validation
    span and observation count; `BatteryReport` gains missing-factor accounting,
    per-factor coverage, `enforce_failures` and an aggregate `.passed`; `run_battery`
    calls `prereg.verify()` whenever the pre-registration is sealed (TODO(WP2.3): drop
    the guard); derived factors' declared `units` are checked against their inputs'
    registered units; `seal()`'s `out_path` is optional for a dry run.
- **`.gitignore`: `data/` → `/data/`.** The unanchored pattern matched any directory
  named `data` at any depth, so the **entire `src/ah/data/` package** (all of Step 1's
  data layer), every synthetic connector fixture under `tests/fixtures/data/`, and
  `docs/data/` were untracked — a fresh clone could not run the test suite. 54 files
  added. `ruff` respects `.gitignore` by default, so those sources had never been
  linted; 13 pre-existing lint findings surfaced and are fixed here. See
  `governance/retrofit-register.md` RFR-11.
- **WP2.2 Task 1 review fix pass 2 — the numeraire defect survives at portfolio level;
  three documentation gaps closed; one defence-in-depth hole closed.** All
  documentation-only except the last item.
  - *The `zero_cost` leg taxonomy is sound at leg level but the sealed claim is
    portfolio-level.* Under `conventions.numeraire: total_return` with no cash leg, a
    strategy carrying uncommitted zero-cost notional, or flat under its own rule,
    realizes **zero** on that capital rather than the cash rate — three of five D4
    strategies are affected (`eqw_factors` at 0.6, `endowment_proxy` at 0.15, and
    `momentum` in its warm-up and every flat month, broken by this task's own numeraire
    switch and not previously recorded). `_validate_numeraires` cannot see this: it
    checks declared leg numeraires, not implied cash positions. Recorded as
    `governance/retrofit-register.md` RFR-12 (widens RFR-9) and a new paragraph in
    `pre-registration.yaml`'s `conventions.numeraire_statement`; WP2.3 must choose
    between an explicit `cash_tr_1m` residual leg or sealing the bias as-is. No code
    change — the fix is documenting the gap accurately before WP2.3 decides.
  - *`factors.yaml`'s `hy_spread`/`policy_rate` `proxy_for` entries overstated what
    `read_factor_frames` actually reads.* They read `fred.HY_OAS`/`fred.FEDFUNDS`
    directly, unextended; neither splice rule is applied by `ah.data.refresh` today
    (RFR-10, already known, but the manifest text implied otherwise). Reworded both
    `proxy_for` entries and their `notes` to say REGISTERED BUT NOT YET APPLIED, name
    WP2.3 as the owner, and cross-reference RFR-10; the same overstatement in
    `pre-registration.yaml`'s `units_of_level_factors` is corrected too.
  - *The RFR-1 circularity was only half-broken.* `factors.yaml`'s header already
    pointed at RFR-8, but `factor_sources.commodities.reason` and
    `pre-registration.yaml`'s `units_of_return_bearing_factors` still cited RFR-1
    directly. Both now point at RFR-8.
  - *`ah.eval.panel._compute_derived` validated input frames' columns but not its own
    output.* `_read_series` checks every input for `date`/`value`; the derived expr's
    return value went straight to `set_index("date")["value"]` with no check at all.
    Safe today only because every registered `_DERIVED_EXPRS` entry happens to return
    `ah.data.derive._frame()`'s exact two columns — a future transform need not. Now
    checked the same way, raising `PanelError` instead of a bare `KeyError` several
    frames inside pandas. New test
    `test_derived_expr_output_missing_columns_raises_panel_error` (monkeypatches a
    broken entry into `_DERIVED_EXPRS`; confirmed red — `KeyError: 'value'` — before
    the fix).
  - *`src/ah/data/cli.py` had two pre-existing lint violations, newly visible after the
    `.gitignore` fix.* Line 8's `from __future__ import annotations` violated
    `CLAUDE.md`'s documented rule for that exact file (Typer resolves parameter hints
    at runtime). Verified `ah data --help`, `ah data refresh --help` and `ah data
    status` all behave identically with and without it, then removed it — the file was
    simply never checked against the rule until the gitignore fix made it visible to
    `ruff`/review. Line 100's em dash in a CLI-echoed string (cp1252-safe today, but
    against the ASCII rule) replaced with `--`.

### Added
- **WP2.2b Task 7 — `eval/negative_controls.py`, the negative-control suite.** Five
  deliberately broken generators registered through `ah.gen.registry` exactly like a
  real one, so the battery cannot tell them apart: `nc1-iid-gaussian` (iid draws from
  the joint panel's own mean vector and full covariance — means/stdevs/contemporaneous
  correlations preserved, all tails/ACF/clustering destroyed); `nc2-shuffled` (real
  train+validation rows in a random order, one permutation per path **common across
  factors**, so marginals and contemporaneous structure are exact and only time
  ordering dies); `nc3-shifted-bootstrap` (moving-block bootstrap, block 24m, then
  `x' = mu + 1.5*(x-mu) + 0.5*sigma` per factor — both constants derived from band
  geometry, not tuned); `nc4-memorizer` (verbatim replay of a uniformly-drawn
  contiguous TRAIN window per path plus iid noise at `NC4_NOISE_FRACTION = 0.10` of
  each factor's own sigma — derived from the memorization suite's own 24-dimensional
  block geometry: a copy sits at `sqrt(24)*0.1 ≈ 0.49` from its source against
  `sqrt(48) ≈ 6.9` for two independent historical decades); `nc5-condition-ignoring`
  (NC3 with the distortion switched off, i.e. a plain block bootstrap, whose only
  defect is that it never reads `world.factor_conditions`). All randomness flows from
  one `PCG64(seed)`; all real data flows through `ReferenceStats.historical_series`,
  never a fresh catalog read and never the holdout (AST guard on `ah.eval.g2`, plus a
  guard that no control object retains a `DataAccess`). `run_negative_controls` emits a
  `NegativeControlReport` (JSON + markdown, `BatteryReport` conventions) with a row per
  control and a column per tier, naming every metric that fired, splitting failures by
  rejection surface (`enforce` / `report` threshold vs. reference band) and separating
  **substantive** (finite-valued) failures from NaN-driven ones — a control rejected by
  a metric that is NaN for every generator has not been caught. `negative_controls.py`
  joins `prereg._REQUIRED_JUDGED_SOURCES`.
- **WP2.2b Task 7 — what the controls found.** All five are rejected and all five are
  caught by their designated tier, but **not one is caught by an `enforce`-severity
  threshold for a reason specific to its own defect**. Four findings, each pinned by a
  named test in `tests/test_negative_controls.py` rather than papered over:
  (1) *no metric suite in the battery emits a `<factor>.mean`, `<factor>.std` or
  `<a>~<b>.correlation` metric at all*, although `reference.SINGLE_FACTOR_STATS` /
  `CROSS_BLOCK_STATS` register all three and `compute_reference` computes a real
  length-matched band for each — so NC3's drift (`equity_mkt` pooled mean 0.0233 against
  a band of `[-0.0016, 0.0101]`; std 0.0653 against `[0.0210, 0.0541]`) is invisible to
  the battery on exactly the axis it was built to break; (2) the only enforce gate that
  fires anywhere is `floor_violations`, and it fires identically for all five including
  controls replaying real values verbatim (a realistic funding spread sits below the
  sealed 100bp `SPREAD_FLOOR_PCT`), so it discriminates nothing; (3) a plain block
  bootstrap — the shape of WP2.4's own G2 benchmark — scores *worse* on
  `near_duplicate_fraction` (0.239) and `nn_distance_p05` (0.069) than the deliberate
  memorizer (0.065 / 0.649); (4) the `10yr` tier produced no substantive failure for
  any control (13 of its 22 metrics are structurally NaN for every generator).
- **WP2.1 — Experiment infra, splits, leakage guards, registry.** `splits.py`:
  train/validation/holdout spans with a `DataAccess` guard — the holdout is reachable
  only via a `FinalEvaluationToken` minted solely in `ah.eval.g2`, proven by an
  import-graph test that no `ah.gen` module imports that mint; `train_val()` is the
  reference/normalization surface (holdout excluded). `experiment.py` + `ah exp`
  (list/show/diff): deterministic config hashing, git SHA, seed, `experiments/<id>/`.
  `gen/base.py` (`Generator` protocol + `Ensemble` with full lineage metadata),
  `gen/registry.py` (resolve WorldSpec `generator_id`; unknown ids error).
- **WP2.1b Task 1 — Factor manifest with a block layer (pre-seal patch).**
  `factors.yaml` (repo root): `factor_blocks` (`global`, `us`, `uk`) +
  `active_blocks: [global, us]`; a jurisdiction addition later is an additive
  `block_addition` amendment, never a re-seal of existing blocks. `factors.py`
  (top-level, peer of `splits.py` — not under `gen/` or `eval/`, so `ah.gen` keeps
  no dependency on `ah.eval`): `FactorManifest` (`active_factors()`, `block_of()`,
  `cross_block_pairs()`, `is_active()`) + `load_manifest()`, `lru_cache`'d by resolved
  path so repeated calls return the same object; validates active-block references,
  no factor in two blocks, no empty block. `EnsembleMeta` gains `active_blocks:
  tuple[str, ...] = ()`; `battery/report.py`'s `BatteryReport` gains the same field,
  populated from `load_manifest()`.
- **WP2.1b Task 1 review fixes.** `FactorManifest.blocks` is now wrapped in
  `types.MappingProxyType` before being stored on the frozen dataclass, so the
  identity-cached `load_manifest()` object can no longer be mutated through its
  `blocks` mapping (the frozen dataclass only blocked attribute reassignment, not
  mutation of the dict's contents). `active_blocks` non-string/empty-entry errors
  now interpolate the offending value, matching the two parallel checks nearby.
  Added tests for the previously-untested "factor names and block ids must be
  non-empty strings" validation branches (empty-string factor, non-string factor,
  empty-string `active_blocks` entry) and for the new `blocks` immutability.
- **WP2.1b Task 2 — D4 benchmark-strategy set over generator outputs only (pre-seal
  patch).** The D4 set (VaR/ES tail fidelity, and the WP2.8 tail auxiliary loss)
  previously included an "endowment mix" defined over portfolio sleeves, which the
  battery could not compute without Step-3 machinery and an unfrozen sleeve
  taxonomy. `strategies.py` (top-level, peer of `factors.py`/`splits.py` — not under
  `eval/`, so `ah.gen.blocks.losses` (WP2.8) can import the same `Strategy`
  definitions without `ah.gen` depending on `ah.eval`): `Strategy` (frozen dataclass:
  static-weight or rule-based, factor id -> weight, rebalance/lookback/rule/params/
  notes) + `load_d4_strategies()`, `lru_cache`'d by resolved path so every caller
  gets the same object; validates every weight against `ah.factors.load_manifest()
  .active_factors()`, static weights sum to 1.0 within 1e-9, rule ids are known.
  `pre-registration.yaml` (repo root, new, marked UNSEALED — Task 4 adds thresholds
  and the seal machinery) now carries the `d4_strategies` block: `eqw_factors`
  (equal-weight across the return-bearing active factors), `sixty_forty`
  (equity_mkt/ust_10y), `endowment_proxy` (equity/govt/credit/commodities/REITs with
  an explicit `proxy_mapping` for private sleeves — private equity and REITs to
  equity_mkt, private credit to hy_spread, real assets to commodities), `momentum`
  (12-1 on equity_mkt, stated warm-up), and `carry` (static long ust_10y / short
  policy_rate — a funded long-short whose exposures sum to 0.0, which is why it is
  `kind: rule` rather than `static_weights`). `eval/metrics/tails.py` (new package):
  `strategy_returns()` (weighted sum of factor slabs, or rule dispatch for
  momentum/carry), `var_es()` (historical VaR/ES as positive loss magnitudes),
  `d4_tail_table()`. Elicitability, Kupiec/Christoffersen backtests, and
  tail-dependence coefficients remain WP2.2 scope (named, not stubbed).
  `tests/test_tails_import_graph.py` walks the AST of both new modules and asserts
  no import names a portfolio/sleeve/institution module.
- **WP2.1b Task 2 review fixes (fix pass 1) — derived series, and a sealed file that
  stands alone.** Review returned Spec: FAIL. Three defects mattered most.
  *(1) Levels are not returns.* `sixty_forty`, `endowment_proxy` and `carry` weighted
  rate/spread **levels** (`ust_10y`, `hy_spread`, `policy_rate`) as if they were period
  returns and summed them with `equity_mkt`: the 60/40 bond leg *rose* when yields
  rose, the endowment credit leg booked spread widening as a gain, and `carry`'s pooled
  loss distribution was dominated by a positive constant, so `var_es` returned a
  negative number in violation of its own positive-loss-magnitude convention.
  `pre-registration.yaml` gains a `derived_series:` block, declared before
  `d4_strategies`, in which a level factor is converted to a monthly decimal return by
  a named transform with every parameter, the closed-form formula, the
  percent-to-decimal conversion, the lag and the warm-up all stated: `govt_tr_10y`
  (`bond_total_return` on `ust_10y`, `duration_years: 8.5`), `credit_xs_hy`
  (`spread_excess_return` on `hy_spread`, `spread_duration_years: 4.0`) and
  `cash_tr_1m` (`bond_total_return` on `policy_rate` with `duration_years: 0.0` — cash
  is a zero-duration bond, so `carry`'s funding leg needs no bespoke arithmetic and no
  third transform). One convention throughout: levels are percent, `r_t = 0.01 * (
  x_{t-1}/12 - D*(x_t - x_{t-1}) )`, and month 0 is 0.0 under the file's single
  warm-up rule (the same rule `momentum` uses). `strategies.py` gains `DerivedSeries`,
  `load_derived_series()` (memoized by resolved path, like `load_d4_strategies()`) and
  `KNOWN_TRANSFORMS`; a strategy weight key may now name an active factor **or** a
  declared derived series, and nothing else. `sixty_forty` is now
  `{equity_mkt: 0.6, govt_tr_10y: 0.4}`; `endowment_proxy`'s govt/credit legs are
  `govt_tr_10y`/`credit_xs_hy` at unchanged sleeve weights; `carry` is long
  `govt_tr_10y` funded at `cash_tr_1m`. `eqw_factors` is unchanged.
  *(2) The sealed file no longer incorporates unsealed code by reference.* `carry`'s
  units convention and `momentum`'s warm-up were defined by pointing at
  `tails.py`'s module docstring; both are now stated in full in a `conventions:` block
  inside the file, and `tails.py`'s "factor-slab convention" paragraph is deleted and
  replaced by the levels-only-through-a-derived-series rule.
  *(3) The import-graph acceptance test passed without protecting.* It appended only
  `node.module` for `ast.ImportFrom`, so `from ah.core import institution` (and the
  `as`-aliased and relative forms) were missed — and `ah/core/institution.py` really
  exists and really holds `SLEEVES`. The checker now also emits
  `f"{node.module}.{alias.name}"` per alias and handles `node.module is None`, with a
  parametrized test proving it catches all five forms from parsed strings.
  Also: rule lookbacks are declared exactly once (`Strategy.lookback` drives the rule;
  `lookback_months` inside `params` is rejected); sealed parameters have no code-side
  defaults (a missing one raises `StrategyError` naming it); unknown keys and duplicate
  YAML mapping keys are hard errors (`_UniqueKeyLoader`); rule target series are sealed
  data (`params` keys ending `_series`, validated against the active factors plus the
  declared derived series at load, not at metric time); `endowment_proxy`'s
  `proxy_mapping` is loaded and its sleeve weights must roll up to the flat `weights`
  within 1e-9; `KNOWN_RULES`/`KNOWN_TRANSFORMS` are asserted equal to `tails.py`'s
  dispatch tables (and the `# pragma: no cover` that hid the gap is gone); the analytic
  VaR/ES tolerance drops from 2e-3 to 5e-4 (~8x the MC standard error at n=2e6, not
  ~33x); `Ensemble.factor` raises a named `UnknownFactorError` identifying the factor
  and the available set; and the seal now states, once, that `commodities` has no
  registered series and therefore **two of the five D4 strategies have no computable
  reference statistics at seal time**. Tests use plausible *level* magnitudes (a 10y
  yield near 4, a HY OAS near 4.5) for the rate/spread factors — the previous
  zero-mean N(0, 0.02) fixture is precisely why the sign inversion survived review.
- **WP2.1b Task 2 review fixes (fix pass 2) — sealed conventions the loader actually
  reads.** A re-review found the file's self-description ("the code is checked against
  it by tests") was still false in two places, plus six minor gaps. *(1)
  `conventions.percent_to_decimal` had no code reading it, and `tails.py`'s
  `_MONTHS_PER_YEAR` had no sealed key at all — an amendment to either would have been
  a silent no-op. `pre-registration.yaml` gains `conventions.months_per_year`; `tails.py`
  now sets `_PCT_TO_DECIMAL`/`_MONTHS_PER_YEAR` *from* `ah.strategies.load_conventions()`
  at import time, not as independent literals. *(2)* "a level factor never appears in
  `weights`" was enforced only by a hand-maintained frozenset in
  `tests/test_strategies.py` that had already drifted from the YAML prose (9 factors
  vs. 7) and covered nothing the loader itself checked. `conventions` gains
  `return_bearing_factors` / `level_factors` — sealed, exhaustive and disjoint over
  every active factor in `factors.yaml` (checked at load time) — and
  `ah.strategies.Conventions` / `load_conventions()` load them; `_validate_weights`
  now raises `StrategyError` naming any level factor weighted directly; the
  hand-maintained frozenset is deleted. This also fixes the missing `cpi`/`equity_vol`
  classification (both are now correctly `level_factors`, matching what the deleted
  frozenset already had right). Six minor items: `conventions.rebalance_cadences`
  (`[monthly]`) is now sealed and enforced — an undeclared `rebalance` value raises;
  `conventions.static_weights_composition` states the arithmetic-weighted-sum, no-
  compounding rule the three `static_weights` strategies were relying on implicitly;
  `d4_tail_table` gains an explicit `derived` parameter and raises if `strategies` is
  passed without it, instead of silently pairing an explicitly-loaded strategy set with
  the *default* file's derived-series transforms; two `derived_series.*.notes` entries
  that pointed at test function names by name now describe the sign property directly;
  `_lagged_carry_minus_duration` casts its whole input to float64 before any arithmetic
  (previously only `out` was float64 — under NumPy's NEP 50 promotion rules a float32
  input's carry/duration terms would have stayed float32) and raises a named
  `StrategyError` for non-2-D input instead of an `IndexError` from `level.shape[1]`.
- **WP2.1b Task 3 — Block-aware reference statistics and bootstrap bands (pre-seal
  patch).** `eval/reference.py` (new): the skeleton `reference.py` computes every
  reference statistic **on train+validation only** (`ah.splits.DataAccess.train_val`
  is the only surface it touches; it imports neither `ah.eval.g2` nor
  `FinalEvaluationToken` in code — an AST-based test proves it, matching
  `tests/test_leakage_guard.py`'s style), per active `FactorManifest` block and
  separately for cross-block joint metrics, with the block pair recorded on
  `CrossBlockReference.pair`. Public surface: `StatBand` (point + block-bootstrap
  band + `n_resamples`/`level`/`tier`), `BlockReference`, `CrossBlockReference`,
  `ReferenceStats` (`blocks`, `cross_blocks`, `active_blocks`, `vintage_id`,
  `n_resamples`, `seed`, `missing_factors`, `to_dict()` for JSON — cross-block pair
  keys render `"global|us"`), `compute_reference()`. `SINGLE_FACTOR_STATS` registers
  `mean`/`std`/`skew`/`excess_kurtosis`/`acf_1`/`acf_abs_1` (plain numpy, closed-form
  definitions documented in each docstring — `acf_1` uses the overall-mean,
  n-denominator Box-Jenkins estimator, not `numpy.corrcoef`), each paired with its
  DN-1.1 Sec.II.6 horizon tier (all `monthly` for this task — `1_5yr`/`10yr`/
  `economic`/`severe` are WP2.2 scope, named not stubbed, alongside the eight full
  metric suites `monthly.py`...`calibration.py`). `CROSS_BLOCK_STATS` registers
  `correlation` and `crisis_corr_lift` (correlation on a block-A factor's worst decile
  minus the unconditional correlation, precisely defined in its docstring).
  `block_bootstrap_band()`: a moving-block bootstrap over the time axis of an aligned
  ``(T, k)`` panel — row-blocks are drawn jointly across every column (never
  per-factor resampling), so calling it with the same `seed` and the same whole-block
  panel for every statistic in a block gives every one of that block's stats the same
  resampled time positions, the "joint" property the patch requires. All randomness
  from `numpy.random.Generator(PCG64(seed))`, constructed fresh per call — same seed,
  bit-identical band. `compute_reference()` reads each active factor via
  `access.train_val(series_id_for(factor))` (`series_id_for` defaults to identity —
  the factor-id -> catalog-series-id mapping doesn't exist yet; that's WP2.2/Step-2R
  scope) and inner-joins them on date before computing anything; a factor with no data
  (`commodities` — no Step-1 series sources it yet, per `factors.yaml`'s header note)
  is recorded in `missing_factors` rather than raising or producing `NaN`. Every
  active block gets a `BlockReference` entry even if all its factors are missing, so
  callers can always find a block by key.
  `tests/test_reference.py` (12 tests): the leakage proof reads dates from a
  `DataAccess` subclass that records every date/series id actually reaching
  `compute_reference` through `train_val` (not from the return value, and not by
  trusting `train_val`'s own exclusion — this closes the leak channel a caller could
  open by reading the raw `Reader` directly); the inactive-block proof does the same
  for `uk` (declared in the real `factors.yaml`, inactive) using a reader that *has*
  uk data available, so a bug iterating `manifest.blocks` instead of
  `manifest.active_blocks` would be caught rather than masked by a missing-data path.
  Also: same-seed/different-seed band (non-)identity; `blocks`/`cross_blocks` shape
  matches `manifest.active_blocks`/`cross_block_pairs()`; `mean`/`std` against
  closed-form values; `acf_1` recovers a known AR(1) phi; `excess_kurtosis` near zero
  for a normal sample and clearly positive for a Student-t sample; every band brackets
  its point estimate; `to_dict()` round-trips through `json.dumps`.
- **WP2.1b Task 3 review fixes (fix pass 1).** Addresses one Critical and four
  Important/Minor findings against `eval/reference.py`. *Critical:* the leakage-guard
  test's `_RecordingAccess` recorded dates from `DataAccess.train_val()`, which is
  already holdout-clean by construction and proven so independently
  (`test_leakage_guard.py::test_train_val_excludes_holdout`) — the offenders assertion
  could never fire, so it detected no new leak channel; a direct/parallel holdout read
  (`access.frame(sid, "holdout", token=...)`) bypassed it entirely and also escaped the
  AST guard, whose `ast.Name`/`ast.ImportFrom` checks don't cover qualified access like
  `ah.splits.FinalEvaluationToken`. Fixed by re-pointing `_RecordingAccess` at
  `frame()` (the method `train_val()` calls internally) and broadening the AST guard to
  flag `ast.Attribute` nodes too; both fixes are proven with mutation tests that apply
  the exact leak quoted in the review and show the (pre-fix) guard missing it and the
  (post-fix) guard catching it. *Important — alignment was global, not scoped:*
  `compute_reference` inner-joined every active factor onto one shared date axis before
  computing anything, so one short-history factor silently truncated every other
  factor's own reference window (real Step-1 series make this likely: spread/vol
  indices start decades after the equity series in the same `global` block), and a
  zero-overlap cross-block pair raised an unhandled `ValueError` from inside
  `block_bootstrap_band`. Alignment is now scoped to what each statistic needs: a
  single-factor stat reads only that factor's own train+validation observations (no
  join with any other factor, same block or not); a cross-block stat aligns only its
  own factor pair. A pair with zero overlap is recorded in the new
  `CrossBlockReference.zero_overlap_pairs` (surfaced in `to_dict()`) instead of
  raising. *Important — error messages didn't name the offender:* `_read_train_val`
  now validates the `date`/`value` columns itself and raises a new
  `ReferenceComputationError` naming the factor and series id for a malformed frame
  (previously an anonymous `KeyError` could propagate from deep in the alignment code);
  `block_bootstrap_band` gained a `context` parameter threaded from every call site
  (`block=... factor=...`/`pair=... factors=...`) so any of its `ValueError`s name what
  failed. *Important — `skew`/`acf_abs_1` had no ground-truth test:* added hand-computed
  exact-arithmetic tests for both (a 4-point sample for `skew`, a 6-point sample for
  `acf_abs_1` whose lag-1 autocorrelation of `|x - mean(x)|` works out to exactly
  `1/4`). *Minor:* the moving-block resample draw is now an explicit, reusable step
  (`_draw_moving_block_indices`, drawn once per factor/pair and passed into every stat
  sharing that panel via `block_bootstrap_band`'s new `resample_indices` parameter)
  instead of an emergent side effect of separate calls sharing `(seed, T, block_length,
  n_resamples)`; `CROSS_BLOCK_STATS` now carries `tier` on a `RegisteredCrossStat`
  record, symmetric with `SINGLE_FACTOR_STATS`'s `RegisteredStat`, instead of
  hardcoding `tier="monthly"` at the call site; `block_bootstrap_band` validates
  `block_length >= 1` instead of silently clamping a non-positive value to 1; the
  same-seed determinism test now compares the whole `ReferenceStats` object instead of
  just `.blocks`/`.cross_blocks` separately; `test_band_brackets_point_estimate_for_
  every_stat`'s expected count is now derived from the fixture's manifest shape instead
  of two hardcoded, coincidentally-equal `4`s. `tests/test_reference.py` grew from 12
  to 28 tests; no existing test was weakened or deleted. Full suite, ruff, and pyright
  clean.
- **WP2.1b Task 4 — Pre-registration seal machinery: block-nested thresholds,
  seal/verify, `block_addition` (pre-seal patch).** `eval/prereg.py` (new): builds the
  WP2.3 seal machinery with the block structure already in it — **nothing here seals
  for real**; `pre-registration.yaml`'s `sealed` flag stays `false`, and the
  acceptance bar is a dry-run `seal()` + `verify()` passing end to end (Instructions/
  WP2.1b-PRE-SEAL-PATCH.md Definition of done item 4). Public surface: `Threshold`
  (`min`/`max`/`severity`), `Decision`, `PreRegistration` (`sealed`, `active_blocks`,
  `block_thresholds`, `cross_block_thresholds`, `decisions`, `raw`), `Amendment`
  (`amendment_id`/`type`/`date`/`rationale`/`post_hoc`/`payload`), `PreRegError`,
  `load()`, `verify()`, `seal()`, `load_amendments()`, `append_amendment()`,
  `apply_block_addition()`. `verify()` checks: every active block has a
  `thresholds.blocks` entry and no entry names an inactive block; every active
  cross-block pair (`FactorManifest.cross_block_pairs()`) has a
  `thresholds.cross_blocks` entry and no entry names an inactive block;
  `prereg.active_blocks == manifest.active_blocks`; every threshold's `severity` is
  `enforce`/`report` and `min <= max`; and, closing a hole found in review, that the
  `conventions:` block is present and declares every key `ah.strategies.
  load_conventions()` reads (`percent_to_decimal`, `months_per_year`,
  `return_bearing_factors`, `level_factors`, `rebalance_cadences`,
  `static_weights_composition`), with `return_bearing_factors`/`level_factors`
  together classifying every active factor and none in both — `ah.strategies`
  deliberately treats a *missing* `conventions:` block as "none declared" (a
  concession for minimal test fixtures), which would otherwise let a misspelled
  `conventons:` key silently disable enforcement in the very file the seal hashes;
  `verify()` re-checks this unconditionally, reading `PreRegistration.raw` directly
  rather than re-reading the file through `ah.strategies` (which needs a path this
  module isn't guaranteed to have post-amendment). `seal()` hashes, canonically
  (reusing `ah.core.digest.canonical_json` + `hashlib.sha256` — no second hashing
  scheme), the pre-registration YAML, the `factors.yaml` it references, and the
  source text of every file in `judged_sources` (default: the WP2.2 metric-suite
  modules that exist yet, plus `eval/g2.py`, resolved lazily so files WP2.2 hasn't
  added don't block this task); writes a JSON lock (`digest`, `hashed_files`,
  `sealed_at`) unless `dry_run`. `sealed_at` is a required keyword argument — never
  `date.today()` (no-clock-reads invariant) — and plays no part in the digest itself
  (sealing the same inputs at two different `sealed_at` values gives the same
  digest). `governance/amendment-log.yaml` (new): append-only log, starting empty;
  header documents the four amendment types and states `block_addition`'s additive
  property verbatim (WP2.1b-PRE-SEAL-PATCH.md's required wording) — it adds new
  per-block and new cross-block thresholds for the newly-active block without
  invalidating any existing block's thresholds, so it is not a re-seal.
  `append_amendment()` opens the log in file-append mode, so every byte already on
  disk is provably untouched (not merely unchanged in content) by a later append.
  `apply_block_addition()` merges a `block_addition` amendment's new per-block and
  new cross-block thresholds into a `PreRegistration`, carrying every pre-existing
  block's/pair's thresholds over by reference (same `Threshold` objects) so they are
  byte-identical (via canonical-JSON serialization) before and after — the patch's
  acceptance criterion. `pre-registration.yaml` extended (not replaced): `schema_
  version`, `sealed: false`, a provisional `campaign_vintage_id`, `factor_manifest:
  factors.yaml`, `active_blocks: [global, us]`, a block-nested `thresholds:` section
  (one enforce- and one report-severity entry per active block, one cross-block entry
  — every value explicitly commented as a provisional placeholder pending WP2.2's
  reference statistics), and a `decisions:` block carrying R5 (FX) and J3 (UK block)
  from Item 3, both `CLOSED-deferred`, with their consequence strings verbatim (Task
  5 records the same strings in `governance/decision-register.md`). `battery/
  report.py`: `run_battery()` gained a `manifest: FactorManifest | None = None`
  parameter (same injection pattern as Task 3's `series_id_for`), defaulting to
  `load_manifest()`, so a synthetic block configuration can be run through the
  battery without a real campaign's `factors.yaml` (Item 2 acceptance: "a synthetic
  two-block configuration passes the battery"). `tests/test_prereg.py` (new, 35
  tests): the 13 tests named in the Task 4 brief plus dedicated coverage of the
  `conventions` closure (missing block, missing key, double-classified factor,
  unclassified active factor, and the block-addition-safe case of a conventions
  block pre-classifying a not-yet-active block's factors) and threshold sanity
  (invalid severity, `min > max`). `tests/test_battery.py` gained the synthetic-
  manifest acceptance test. Full suite (516 tests), ruff, and pyright clean.
- **WP2.1b Task 4 review fixes (fix pass 1).** Addresses one Critical, four
  Important and five Minor findings, plus a project-owner scope ruling on what the
  seal covers. **Scope ruling (Decision 0):** `CLAUDE.md`'s invariant ("thresholds
  *and the code that judges them*") governs over STEP2-GENERATOR-PLAN §WP2.3's
  narrower wording, so `_default_judged_sources()` now covers every module that can
  move a pass/fail verdict — the enforce-tier metric suites that exist, plus
  `eval/g2.py`, `eval/reference.py`, `eval/prereg.py` itself (non-circular: the
  digest lands in the lock, never back in the module), `strategies.py`, `factors.py`,
  `battery/report.py` and `battery/stylized.py`. Those seven are *required* to exist:
  a missing one raises rather than silently shrinking the seal. Documented at the top
  of `prereg.py` and in `pre-registration.yaml`, including the consequence that after
  WP2.3 seals, an edit to any of them is a dated amendment. **Critical:** the seal
  digest keyed on absolute filesystem paths, so a committed lock verified only on the
  machine that produced it — it would have failed in CI, in a reviewer's clone, and
  under WSL2. The digest is now keyed on relative, forward-slashed paths resolved
  against two roots (the repository root for judged code; the pre-registration's own
  directory at seal time / the lock's at verify time for the sealed documents), the
  lock stores them in that form, and a path under neither root is rejected at seal
  time. **Important:** `verify()` now validates threshold *keys*, not just their
  values — a per-block key must be `"<factor>.<stat>"` with the factor in that block
  and the stat registered in `reference.SINGLE_FACTOR_STATS`, a cross-block key
  `"<factorA>~<factorB>.<stat>"` with the factors drawn in the pair key's sorted order
  and the stat in `CROSS_BLOCK_STATS`, so a sealed `enforce` threshold can no longer
  name a statistic nothing computes. `append_amendment()` validates at *write* time
  (unknown type, empty `amendment_id`/`date`/`rationale`, non-boolean `post_hoc`,
  duplicate id) and writes nothing on failure — on an append-only artifact a bad entry
  is permanent, and a duplicate id previously produced a log `load_amendments()`
  refused forever. The lock now records `prereg_path` and `verify()` requires it to
  name the pre-registration being verified (`PreRegistration` gained `source_path`),
  so a lock sealed for a different document is rejected even when contents match.
  **Minor:** `verify()`'s conventions check adopts `ah.strategies`' full rule
  (classification must cover *exactly* the active factor set, nothing outside it), so
  it can no longer green-light a file `load_conventions()` raises on — a real
  `block_addition` therefore requires a hand edit to `conventions:` alongside the
  amendment's thresholds, now stated in the amendment log's header and exercised by
  the round-trip fixture; `verify()` requires `schema_version == "1.0"` and a present
  `decisions` block (a misspelled `decisons:` previously dropped R5/J3 silently);
  `read_text` failures in `seal()`/`verify()` are wrapped in `PreRegError` naming the
  file; two weak test matchers tightened (`FrozenInstanceError`, the full
  missing-pair message) and the report-all-failures test now draws its two faults from
  different `verify()` sections. Full suite 541 tests, ruff + pyright clean.
- **WP2.1b Task 5 — Governance: decision register, retrofit register, plan
  reconciliation (pre-seal patch, documentation only).** Records the decisions taken
  across WP2.1b Tasks 1-4 and reconciles two plan documents that now disagree with them.
  No production code changed. `governance/decision-register.md` gains a
  `## Step 2 decisions` section (D1-D10 in the existing platform table untouched): `S2-D4`
  (the D4 benchmark-strategy set, redefined over generated factors and their declared
  derived series — `govt_tr_10y`, `credit_xs_hy`, `cash_tr_1m`), `R5` and `J3` (FX and UK
  factor blocks, both CLOSED-deferred with their `pre-registration.yaml` consequence
  strings copied verbatim — a test (`test_decision_consequence_text_is_verbatim`) pins
  those strings, so the register and the YAML can never silently drift), and `S2-SEAL`
  (the seal-scope decision: CLAUDE.md's invariant — thresholds *and the code that judges
  them* — governs over STEP2-GENERATOR-PLAN §WP2.3's narrower wording, so the seal covers
  every module that can move a pass/fail verdict; consequence: post-seal, an edit to any
  judging module, including a no-op refactor, is an amendment). A footnote names the `D4`
  id collision with the platform table's D4 (correlation regime model) so a later reader
  isn't confused by two decisions sharing a number. `governance/retrofit-register.md` is
  new: a dated, append-only table for scope items surfaced but deferred during this work
  — seeded with `commodities`' missing Step-1 data source (declared in `factors.yaml`,
  weighted in two D4 strategies, reference statistics pending a connector under the
  requirements.yaml §WP1.9 rule; deferred to WP2.2) and the R5/J3 block-addition re-entry
  paths. Two plan reconciliations, each a dated note pointing at WP2.1b, minimal edits
  only: `Instructions/STEP2R-CONSOLIDATION-PLAN.md` §WP2R.4 no longer claims to resolve
  R5 (closed earlier, in WP2.1b) and its "one judgment call" note now records the answer;
  `Instructions/STEP2-GENERATOR-PLAN.md` §WP2.3's seal-scope sentence now matches
  `S2-SEAL` instead of disagreeing with it. Also commits six previously-untracked vendored
  design notes from `Instructions/` (separate preceding commit, project-owner approved):
  `DN1.1-multiyear-generator-design-note.md`/`.pdf` (discharges STEP2's halt condition),
  `DN2-hybrid-deployment-note.md`, `DN3-web-experience-architecture.md`,
  `DN4-jurisdiction-and-institution-plugin.md` (defines the `InstitutionProfile` interface
  the J3 consequence cites), `WP1.12-UK-CONNECTORS.md`. Decision register's acceptance
  check: no row in either the platform table or the new Step 2 section names WP2.3 or the
  pre-registration seal in its "Blocks" column. Full suite unchanged at 541 tests, ruff
  clean — this is a docs-only change and verified not to move either.
- **WP2.1b final branch review fixes (pre-seal patch, last commit before merge).**
  Closes the handful of gaps the whole-branch review found that would otherwise become
  post-hoc amendments once WP2.3 seals. `ah.eval.prereg._REQUIRED_JUDGED_SOURCES` now
  includes `src/ah/splits.py`: it hardcodes the train/validation/holdout boundaries, so
  moving `VALIDATION.end` changes every reference band with no lock violation unless the
  module defining "the reference data" is itself hashed — under Decision 0 (`governance
  /decision-register.md` row `S2-SEAL`, "the seal covers every module that can influence
  a pass/fail verdict") that was a miss. `ah.eval.prereg`'s "What the seal covers"
  docstring and `pre-registration.yaml`'s header comment both gain that category, plus a
  new "Considered and excluded" note explaining why `ah/gen/base.py`'s `Ensemble.factor()`
  (the generator layer's container, not the judge) and `src/ah/battery/thresholds.yaml`
  (Step-0 legacy `status: todo` data, WP2.3 must decide its fate) stay out of the hash on
  purpose. `_check_conventions` is brought into line with `ah.strategies._require_string_set`:
  it now rejects an empty, non-string-entry, or duplicate-entry
  `return_bearing_factors`/`level_factors` list the same way the loader would, closing an
  overclaim in `verify()`'s own docstring ("never green-lights a file `load_conventions`
  would raise on" — previously false in three ways). TDD, red first for each of the three
  rejection modes (`tests/test_prereg.py`); the two `block_addition` fixtures that
  previously used `level_factors: []` are reworked to carry a genuinely non-empty, valid
  classification (a second synthetic factor, `a1_lvl`) rather than relaxing the new check.
  `governance/retrofit-register.md` gains three rows (`RFR-4`..`RFR-6`, append-only): no
  producer yet exists for `EnsembleMeta.active_blocks` (lands on WP2.2/WP2.4); `verify()`
  doesn't yet cross-check threshold keys against `reference.py`'s `missing_factors`, so an
  `enforce` threshold on a factor with no data (e.g. `commodities.skew`) would seal cleanly
  (lands on WP2.3); `pre-registration.yaml` has no `splits:` section yet even though
  `splits.py`'s docstring promises one (lands on WP2.3, and now matters more since
  `splits.py` is hashed). `CLAUDE.md`'s halt-condition sentence is corrected: `DN-1.1` is
  vendored at `Instructions/DN1.1-multiyear-generator-design-note.md` and already cited as
  normative by `reference.py`, so that half of WP2.5+'s halt condition is discharged;
  `tier1-synthesis-and-decisions.md` remains genuinely missing from `docs/` and is not
  itself a halt condition. No production behaviour changes outside `_check_conventions`'s
  stricter validation and the widened judged-source set; `pre-registration.yaml` stays
  `sealed: false`. Full suite green (three new tests, two fixtures strengthened, none
  weakened), ruff/pyright clean.
- **WP2.2 Task 1 — Factor-source mapping, the reference panel reader, the battery
  orchestrator.** Closes the one genuinely blocking gap WP2.1b left open: no mapping
  anywhere in the repository bound a factor id (`equity_mkt`, `ust_10y`, ...) to a
  Step-1 catalog series, so reference statistics could not honestly be computed and
  `ah.eval.reference`'s `series_id_for` parameter had nothing real to supply. `factors.
  yaml` gains a `factor_sources:` section, one entry per factor in every block
  (including inactive `uk`): `kind: series` (one `requirements.yaml` series id,
  direct), `kind: derived` (one `ah.data.derive` helper over one or more series ids —
  `ig_spread` = `difference(fred.BAA, fred.AAA)`, `funding_spread` =
  `funding_stress(fred.TEDRATE)`, no SOFR-basis extension since no such series is
  registered), or `kind: unavailable` with a required `reason` (`commodities`, per
  `governance/retrofit-register.md` RFR-1; every `uk` factor, per decision J3 and
  `Instructions/WP1.12-UK-CONNECTORS.md`'s not-yet-landed connectors — never a
  fabricated proxy for either). `policy_rate` maps to `fred.TB3MS` (the 3-month T-bill;
  no FEDFUNDS/effective-funds-rate series is registered, and TB3MS is a real,
  registered series, not an invented one). `ah.factors.FactorManifest` gains
  `sources`, `series_id_for()`, and `is_available()`; `load_manifest()` now validates
  that every declared factor (every block) has exactly one entry and every entry names
  a real factor. `pre-registration.yaml`'s `conventions` prose is corrected now that
  the mapping is a fact rather than an assumption — `equity_mkt` is confirmed Mkt-RF,
  an *excess* return, not a total return, and every level factor's series is named
  explicitly instead of listed as "candidate". A new test
  (`test_factor_sources_units_agree_with_prereg_return_level_classification`) asserts
  `factor_sources`' units and `pre-registration.yaml`'s `return_bearing_factors`/
  `level_factors` classification can never disagree — a return-bearing factor's units
  must be exactly `ret`, a level factor's must never be — because these two files are
  sealed together and a divergence between them is exactly the defect class this
  project keeps finding; a second test cross-checks every `kind: series` entry's units
  against `requirements.yaml` itself.
  `src/ah/eval/panel.py` (new): `build_panel(access, manifest, *, split_reader=...)`
  turns a `FactorManifest` into one date-indexed `Panel` (`.frame`, `.missing`) over
  every available active factor, reusing `ah.data.derive`'s existing helpers (never
  reimplementing a transform) and `ah.data.derive.assemble_panel` for the join. Never
  reads the holdout — `split_reader` defaults to `DataAccess.train_val`, and the same
  recording-reader leakage test `tests/test_reference.py` uses (record at `frame()`,
  not `train_val()`) proves no holdout-era date reaches it.
  `src/ah/eval/battery.py` (new): the Step-2 battery orchestrator Tasks 2-6 register
  metric suites into. `MetricSpec`/`MetricResult` (frozen); `SUITES`, a module-level
  registry populated only via `register_suite()` — adding a suite never requires
  editing `run_battery()` (proved by a test that registers a throwaway suite and shows
  it in the next report). `mc_error(fn, ensemble, *, seed, n_subsamples)`: every
  ensemble-level metric's Monte-Carlo error bar, via disjoint path-subsampling from a
  fresh `PCG64(seed)` — the batch-means estimator recovers the standard error of a
  sample-mean metric to the right order of magnitude (tested against a known-variance
  synthetic ensemble) and is bit-identical for a fixed seed. `run_battery(ensemble, *,
  reference, prereg, manifest, seed, filtered=None)` looks up each metric's train+
  validation band (`ReferenceStats`) and sealed/provisional threshold
  (`PreRegistration`) by name, decides `severity`/`passed`, and emits a `BatteryReport`
  in both JSON and markdown carrying battery version, a dry-run prereg digest
  (`prereg.seal(dry_run=True)`), system/vintage ids, `active_blocks`, and per-tier
  (`monthly`/`1_5yr`/`10yr`/`economic`/`severe`, DN-1.1 §II.6) tables; a `filtered`
  ensemble's results are reported alongside the unfiltered ones, never replacing them
  (the acceptance filter may not teach to the exam). Runs end to end on the Step-0 toy
  engine's output with a throwaway test suite — the plan's own WP2.2 acceptance
  criterion; the real eight metric suites are Tasks 2-6's scope.
  Seal bookkeeping: `eval/battery.py` and `eval/panel.py` are judging code created
  outside `eval/metrics/`, so both join `ah.eval.prereg._REQUIRED_JUDGED_SOURCES` (and
  its docstring, and `pre-registration.yaml`'s mirrored header prose) in this same
  commit, with `tests/test_prereg.py`'s pinned judged-source set updated to match.
  Existing direct `FactorManifest(...)` constructions and hand-written `factors.yaml`
  fixtures across `tests/test_reference.py`, `tests/test_prereg.py` and
  `tests/test_battery.py` gained a `factor_sources`/`sources=` entry each (now
  required); no assertion in any of them was weakened. Full suite green (599 tests, up
  from 544 at branch start), ruff/pyright clean, coverage gate unaffected;
  `pre-registration.yaml` stays `sealed: false`.
- **WP2.2 Task 2 review fix pass 2 — closing the last findings before WP2.3 seals.**
  Everything here lands in files WP2.3 hashes, so it is cheap now and a dated
  post-hoc amendment afterwards.
  *Important 1, the panel metric could be gamed by omission.*
  `_paired_corr_matrices` intersected the reference's covered factor axis with
  `ensemble.factor_names`, so a generator that simply omitted a covered factor got a
  *smaller* matrix and a *smaller* (easier-to-pass) `cross_block_corr_matrix_distance`
  — generating less made an absolute-bound threshold easier to pass, exactly the
  instability the docstring already refused to tolerate for a degenerate factor
  (correctly NaN'd). An omitted covered factor now NaNs the metric identically to a
  degenerate one, never shrinks it. Tested: an ensemble that omits a covered factor
  from otherwise-identical draws must NaN, not merely differ.
  *Important 2, `resample_length` was dropped from the report.* `StatBand.
  resample_length` is load-bearing per `conventions.estimator_length_matching` (a
  length-matched band's `point` is not expected to lie inside `[lo, hi]`), but
  `_result_dict` and the markdown table emitted `point/lo/hi/n_resamples/level/tier`
  only — the battery JSON, the G2 evidence artifact, could not distinguish a
  length-matched band from an unmatched one. Now emitted in both, with an unmatched
  band rendering as `full` rather than an empty cell.
  *Minor 3, a threshold key with no producing metric was still uncaught.* `verify()`
  validates a threshold's `<stat>` against the *reference* registries, not against
  what any metric suite actually emits: `policy_rate.std` (enforce) and
  `equity_mkt~ust_10y.correlation` (report) were registered reference statistics with
  no producing monthly metric, so each would judge nothing, silently, at `enforce`
  or not. New converse test (every real threshold key must be produced by a
  registered metric) plus the mirror already in place (every metric name must be
  sealable). Repointed at metrics that exist: `policy_rate.excess_kurtosis`,
  `equity_mkt~ust_10y.crisis_corr_lift`.
  *Minor 4, the idempotent-replacement property was under-tested.* The existing
  repeatability test ran the same reference twice, proving only that no
  `BatteryError` is raised — it would pass under a regression to
  `SUITES.setdefault`. New test runs `run_full_battery` against two genuinely
  different references and asserts `cross_block_corr_matrix_distance` differs.
  The related `run_battery(reference=X)`-vs-what-the-specs-closed-over identity gap
  is recorded as `governance/retrofit-register.md` RFR-16 (WP2.3 to decide) rather
  than fixed here — it needs a `MetricSpec`/`register_suite` signature change.
  *Minor 5, a short-history factor could produce a silent zero-width band.*
  `_draw_moving_block_indices` now raises when `block_length >= t`: `max_start` would
  be forced to `0`, so every replicate is the identical whole-sample block (`lo ==
  hi`). Not reachable at today's 120-month paths and 1996+ shortest series, but
  reachable once a judged path length exceeds a factor's own history.
  *Minor 6, sealed numeric constants were unpinned.* New equality tests pin
  `_DECAY_RATE_MIN/_MAX`, `_DECAY_GRID_POINTS`, `_DECAY_GOLDEN_TOL`,
  `_DECAY_MAX_ITERATIONS`, `AGG_GAUSSIANITY_MIN_SUMS` and `DEFAULT_BLOCK_LENGTH`
  against the values `pre-registration.yaml`'s prose states, so pre-seal drift trips
  a test instead of a green suite hiding it.
  *Minor 7, a corrected false claim survived in an earlier report section.*
  Annotated in place in the WP2.2 Task 2 scratchpad report rather than only at the
  fix-pass section further down.
  *Minor 8, the block-length rule's actual scope was unstated.* At production
  defaults (`block_length=120`, `resample_length=ensemble.months <= 120`),
  `ceil(L/b) = 1`: every replicate is a single contiguous window, so the `(b-k)/b`
  seam-shrinkage argument that justifies `DEFAULT_BLOCK_LENGTH=120` does not bind on
  the length-matched production path at all — it governs only the unmatched
  (full-history) path. Also documented: `acf_abs_decay` is censored at the search
  bounds (a true rate above 5.0 returns `~5.0`, not NaN); both sides censor
  identically so it is not a correctness bug, but it belongs in the sealed
  definition. Both stated in `reference.py`'s docstrings and
  `pre-registration.yaml`'s sealed conventions, with a new test pinning the
  censoring behaviour.
  Full suite green (716 tests, up from 705), ruff/pyright clean, `ah.core` coverage
  96.54%; `pre-registration.yaml` stays `sealed: false`.
- **WP2.2 Task 2 review fix pass — the monthly panel becomes runnable and sealable.**
  The review returned Spec: FAIL with two Criticals, both blocking WP2.3.
  *Critical 1, the battery never ran.* No production code path called any
  `register_*_suite()`, so `battery.SUITES` was empty in every non-test run:
  `run_battery` computed zero metrics and returned a report whose `passed` was
  vacuously `True`. `ah.eval.battery.run_full_battery` is the orchestration step that
  was missing — compute the train+validation reference from the catalog, register every
  reference-dependent suite against it (`register_reference_dependent_suites`,
  idempotent by replacement so a second run is judged against its own reference), run
  the battery — with tests asserting a **non-empty** metric set, real bands and real
  coverage come back from an actual run. `battery.py`'s docstring no longer states an
  "at import time" registration rule that no code follows, since `battery.py` is a
  sealed judged source and a rule stated only in the seal is worse than none. The
  residual (no CLI/G2 caller yet; only `monthly` of the eight suites exists, so a real
  run's verdict is monthly-tier-only) is `governance/retrofit-register.md` RFR-13 plus
  a `TODO(WP2.2 Tasks 3-6)` at `SUITES`.
  *Critical 2, 34 of 37 monthly metric names were structurally un-sealable.*
  `prereg`'s threshold-key checker validates `<stat>` against `reference.py`'s
  registries, and once `sealed: true` lands `run_battery` calls `verify()`
  unconditionally — so a threshold under an unregistered name would not merely fail the
  seal, it would break every battery run. Every monthly statistic (Hill tail index at
  5%/1%, ACF of returns to lag 5, ACF of |deviation| to lag 24, the fitted decay,
  aggregational Gaussianity, leverage correlation) is now **defined in
  `ah.eval.reference` and registered in `SINGLE_FACTOR_STATS`**; `metrics/monthly.py`
  imports the estimators and contributes only the ensemble pooling conventions. The
  whole-panel `cross_block_corr_matrix_distance` belongs to no factor and no pair, so
  it gets a third registry (`PANEL_STATS`), a `thresholds.panel` section in
  `pre-registration.yaml`, a `_check_panel_threshold_key` in `verify()` and a
  `_lookup_threshold` branch — a deliberate extension of the checker, tested, not a
  key-shape workaround. The prior handoff's claim that WP2.3 could "seal a threshold
  under these exact names directly (thresholds don't require a `reference.py` band)"
  was **false** and is corrected here; there was exactly one path and this is it.
  *Estimator conventions, all now sealed in `pre-registration.yaml`.* The ACF estimator
  is length-dependent and the reference is a different length: the n-denominator
  shrinkage alone is ~20% at lag 24 on a 120-month path against ~2% on ~1100 months, so
  a generator reproducing history exactly would sit outside its own band at long lags.
  `compute_reference` gained `resample_length` and `run_full_battery` passes the
  ensemble's own path length, so both sides carry the same bias (the `(n-k)`-denominator
  alternative was rejected: it would have to change `_acf1` too and corrects only the
  shrinkage term). A test builds a near-deterministic 24-month volatility cycle and
  shows a generator reproducing it lands inside its length-matched band at lags 12 and
  24 while history's own full-sample estimate does not. Consequence stated on
  `StatBand`: a length-matched band's `point` is not expected to lie inside `[lo, hi]`.
  The residual for *pooled* statistics (matched in neither sample size nor bias) is
  RFR-15. Separately discovered and fixed: a moving-block bootstrap keeps only the
  `(b-k)/b` share of lag-k pairs, so at the old default block length of 24 every
  long-lag band was a resampling artifact — `DEFAULT_BLOCK_LENGTH` is now 120, with a
  test pinning both the rule and the artifact.
  `acf_abs_decay` is refitted **in levels** by profiled least squares (closed-form
  amplitude, 241-point grid then golden section, deterministic, no scipy) instead of OLS
  in log space over the positive values only: dropping non-positive ACF values was a
  one-sided selection that lifted the fitted tail and biased the rate downward. The
  levels fit consumes every lag whatever its sign, so no selection happens at all. The
  exponential form is kept over the canonically hyperbolic power law, with the
  justification now stated rather than assumed (comparative summary at a fixed lag
  window; a log-log fit is equally misspecified and weights low lags harder; every
  `acf_abs_lag{k}` is separately banded, so long memory is discriminated lag by lag).
  It is also now computed per path and averaged, like every other time-ordered
  statistic — a more biased estimator of the true rate, deliberately, because it is the
  one the reference band is built from.
  `agg_gaussianity_1m` is gone: at h=1 the aggregation is the identity, so it was
  bit-identical to `excess_kurtosis` — two sealed names, one number. `acf_1`/`acf_abs_1`
  became `acf_r_lag1`/`acf_abs_lag1` for the same reason (free while `sealed: false`;
  a dated amendment afterwards), resolving the naming question the prior task left open.
  `corr_matrix_distance` is renamed `cross_block_corr_matrix_distance` (it covers
  cross-block pairs only; the missing within-block pairwise correlation statistic is
  RFR-14), and `_paired_corr_matrices` returns an explicit mask so the two matrices —
  which carry 0.0 wherever the reference has no entry — cannot be misread as correlation
  matrices. `agg_gaussianity`'s `sums.size < 4` guard became a 30-sum floor (a
  fourth-moment statistic's standard error is `~sqrt(24/n)`: 2.4 at n=4). A judged-source
  pinning test now asserts every metric-suite module on disk resolves *into* the sealed
  set, not merely that its name is in `_METRIC_SUITE_NAMES`; the `acf_abs_lag1`
  agreement test calls `reference._acf_abs_1` instead of retyping it; `acf_abs_decay`
  gains an end-to-end numeric pin against `-ln(phi)` on a constructed AR(1)-volatility
  path; the Hill registration test checks its fixture's known `alpha=2.0`; and the
  global-`SUITES` mutation in `tests/test_monthly.py` uses a snapshot/restore fixture
  rather than a `finally`-pop. Full suite green (705 tests, up from 669), ruff/pyright
  clean, `ah.core` coverage 96.54%.
- **WP2.2 Task 2 — `eval/metrics/monthly.py`, the monthly-tier stylized-fact panel.**
  All nine STEP2-GENERATOR-PLAN §WP2.2 statistics (excess kurtosis, skew, Hill tail
  index at 5%/1%, ACF of returns lags 1-5, ACF of |deviation| lags 1-24 plus a fitted
  exponential-decay rate, aggregational Gaussianity at 1/3/12-month horizons, leverage
  correlation, correlation-matrix distance, crisis-conditional correlation lift), each
  unit-tested against a closed-form or simulated ground truth with a commented,
  justified tolerance. Reuses `ah.eval.reference`'s existing `_skew`,
  `_excess_kurtosis`, `_acf1`-generalization, `_correlation` and `_crisis_corr_lift`
  definitions verbatim rather than restating any of them (this project has already
  produced one sign-inverted, independently-restated metric defect); every reused
  definition has a test asserting numeric agreement with `reference.py` on the same
  input, not just a docstring claim. New statistics (Hill, ACF beyond lag 1,
  aggregational Gaussianity, leverage correlation, the decay fit, correlation-matrix
  distance) are each defined exactly once. Two pooling conventions, stated once in the
  module docstring and never mixed: pooled path×month observations for
  marginal-distribution statistics (kurtosis, skew, Hill, corr-matrix distance, crisis
  lift), and per-path-then-averaged for time-order-dependent ones (ACF, leverage,
  decay) — concatenating paths end to end before an ACF would manufacture a spurious
  correlation at every path seam. A factor absent from a given ensemble (e.g.
  `commodities`, `kind: unavailable`) returns NaN rather than raising, so one
  inapplicable metric cannot crash a whole battery run.
  Naming deviates from the brief's suggested identifiers in two stated, deliberate
  ways: `crisis_corr_lift` (not `crisis_conditional_corr_lift`) to match
  `CROSS_BLOCK_STATS`'s existing key exactly, so the historical band shows up next to
  the generated value automatically in every report; `acf_r_lag1`/`acf_abs_lag1` are
  **not** aliased to `reference.py`'s `acf_1`/`acf_abs_1` (uniform lag-1..N naming
  preferred over an asymmetric special case) — recorded as an open naming question for
  WP2.3, with numeric agreement still asserted by test regardless of the name.
  `corr_matrix_distance` (Frobenius norm of the difference, documented against the
  alternative Herdin et al. similarity measure) is scoped to the cross-block factor
  pairs `reference.py` actually computes a correlation for — `reference.py` has no
  within-block pairwise-correlation statistic yet, a gap recorded here, not silently
  worked around.
  Registration is a builder, `build_monthly_suite(manifest, reference) ->
  tuple[MetricSpec, ...]`, plus `register_monthly_suite(manifest, reference)` calling
  `register_suite("monthly", ...)` — a deliberate deviation from the "register at
  import" pattern `ah.eval.battery`'s docstring describes, because `corr_matrix_distance`
  structurally needs a computed `ReferenceStats` (unavailable at plain import, which has
  no live `DataAccess`) to even construct its specs; splitting the suite across two
  registration paths was rejected in favour of one uniform builder. No caller wires
  this into a real battery run yet (no CLI/G2 orchestration step exists to compute a
  real `ReferenceStats` and call `register_monthly_suite` — that wiring is a later
  task's job); `ah.eval.prereg._METRIC_SUITE_NAMES` already listed `"monthly"` (Task 1
  landed it defensively), so no seal-list edit was needed. Full suite green (669
  tests, up from 637 at task start — 32 new), ruff/pyright clean.
- **WP2.2 Task 3 — `eval/metrics/horizon.py`, the 1-5yr and 10yr tiers.** Eight DN-1.1
  §II.6-normative statistics, tier-tagged exactly as the design note's table states
  (`1_5yr`: `variance_ratio_{12,36,60,120}m`, `mean_reversion_halflife`,
  `drawdown_median_depth`/`_median_duration`/`_depth_duration_rank_corr`,
  `regime_duration_{mean,p50,p90}`; `10yr`: `lost_decade_frequency`,
  `long_inflation_era_frequency`, `ten_year_return_vs_valuation_{slope,r2}`,
  `ergodicity_gap`), each registered by name+tier into `ah.eval.reference`'s
  `SINGLE_FACTOR_STATS`/`PANEL_STATS` from the start (Task 2's structural lesson
  applied up front, not fixed in afterward) and wired into
  `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS` in the same commit, with a passing
  `run_full_battery` acceptance test that fails without the wiring. Per-metric
  per-path/pooled convention stated in the module docstring (RFR-15's residual bites
  every pooled one, recorded rather than left to be discovered).
  Two structural gaps made honestly NaN rather than faked: `regime_duration_*` (the
  Step-1 regime ruleset needs `usrec`/`growth_yoy`, neither a `factors.yaml` factor —
  RFR-17) and `ten_year_return_vs_valuation_*` (no CAPE/valuation factor exists —
  RFR-18); both recorded in `governance/retrofit-register.md` with an owner and a
  consequence, exactly as the `commodities` gap (RFR-8) already is. `variance_ratio`
  reuses `nonoverlapping_sums` (no second windowing scheme); `mean_reversion_halflife`
  reuses the registered lag-1 ACF estimator directly (the population lag-1
  autocorrelation of an AR(1) process IS phi); `drawdown_episodes` and
  `long_inflation_era_frequency`/`lost_decade_frequency` reuse
  `ah.data.derive.drawdown_state`/`yoy`/`regime_thresholds` verbatim rather than
  reimplementing them. `battery._require_mc_error_reported` makes "10yr metrics carry
  a Monte-Carlo error, or the battery rejects them" structural (rejects `error is
  None`, not `NaN` — an honestly-uncomputable 10yr metric must not crash every real
  battery run). Discovered and fixed in the same commit: `drawdown_state`/`lost_decade
  _frequency`'s compounding step can overflow on adversarial/extreme-magnitude input
  (this repo's `filterwarnings = ["error"]` would otherwise turn that into a hard
  crash) — now settles at `+/-inf` under `np.errstate` instead of raising, since the
  WP2.2b negative-control suite's entire purpose is running the battery against
  broken generators. `block_bootstrap_band`'s `np.percentile` step is not NaN-robust
  for a statistic that can be undefined on a short resample (`drawdown_depth_duration
  _rank_corr`) — recorded as RFR-19, not fixed here (shared, sealed infrastructure).
  Full suite green (758 tests, up from 716 at task start — 42 new), ruff/pyright
  clean.
- **WP2.2 Task 4 — `eval/metrics/tails.py` completed, `eval/metrics/utility.py` added.**
  Both wired into `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS` and
  `prereg._METRIC_SUITE_NAMES` (the latter already listed `utility`), with
  `run_full_battery` acceptance tests that fail without the wiring, exactly as Task 3
  set the precedent.
  `tails.py` (tier `monthly`, on the frozen D4 strategy set): `elicitability_score`,
  the Fissler-Ziegel (2016) strictly consistent joint (VaR, ES) scoring rule at level
  0.95 — lower is better, minimized in expectation exactly at the true (VaR, ES) pair
  (a first-order-conditions derivation is in the docstring and empirically checked: a
  mis-specified pair scores strictly worse on a fixed sample, not merely "finite").
  `kupiec_pof`/`christoffersen_independence`/`christoffersen_conditional_coverage`:
  the standard proportion-of-failures and Markov-chain independence LR backtests,
  df-1/df-2 chi-square p-values via a closed-form `_chi2_sf` (no scipy; verified
  against the textbook 3.841/5.991 critical values). All three score the GENERATED
  ensemble's realized exceedances against the HISTORICAL (train+validation) VaR
  forecast for that same D4 strategy — never the generated sample's own statistics,
  which would trivially optimize and prove nothing about tail fidelity.
  `_historical_strategy_returns` builds that historical series by inner-joining
  exactly one strategy's own legs from the new `ReferenceStats.historical_series`
  field (never a fresh catalog read) and wrapping them as a single-path `Ensemble`, so
  the SAME `strategy_returns` function evaluates history and the generator — no second
  route to the arithmetic. `tail_dependence_lower`/`_upper` (cross-block factor pairs,
  not D4 strategies — DN-1.1's own scoping): a nonparametric rank-based estimator at
  the sealed 5% tail fraction (matching `hill_tail_index`'s own convention), defined
  in `ah.eval.reference` (a real `CROSS_BLOCK_STATS` entry, so the existing
  block-bootstrap machinery gives it a genuine historical band for free) and
  re-exported into `tails.py` under the same name, exactly as `monthly.py` already
  does for `hill_tail_index`/`corr_matrix_distance`.
  A new small registry, `ah.eval.reference.STRATEGY_STATS` (11 names — the four
  `var_95`/`es_95`/`var_99`/`es_99` plus the seven backtest outputs), because a D4
  strategy is sealed *data*, not a `FactorManifest` factor/pair/panel axis; a new
  `pre-registration.yaml` `thresholds.strategies` section (`"<strategy_id>.<stat>"`,
  strategy id checked against *that document's own* `d4_strategies:` block, never a
  fresh `ah.strategies.load_d4_strategies()` read, mirroring how `_check_conventions`
  already avoids that trap) and `ah.eval.prereg._check_strategy_threshold_key`.
  `utility.py` (tier `monthly`, three whole-panel `PANEL_STATS` entries):
  `discriminative_score` (logistic regression, numpy gradient descent, on pooled
  `[mean, std]` window features of real vs. generated factor dynamics —
  `|test accuracy - 0.5|`), `predictive_score` (train-on-synthetic-test-on-real
  one-step-ahead linear-model MSE), `tstr_degradation` (`MSE_tstr / MSE_trtr` against
  a train-on-real-test-on-real baseline fit the same way). No sklearn/scipy. Every
  fit's only randomness (which examples are selected/split) flows from
  `numpy.random.Generator(PCG64(UTILITY_FIT_SEED))` — a sealed module constant, not
  the battery's own run seed, so re-running the battery at a different seed reports a
  bit-identical utility tier for an unchanged ensemble (asserted directly, both
  directions: identical seed bit-identical, different seed different). Real data
  read exclusively through `ReferenceStats.historical_series`; an AST guard proves
  neither module imports `ah.eval.g2`, in the style of `test_reference.py`'s own.
  Full suite green (850 tests, up from 776 at task start — 74 new), ruff/pyright
  clean.
- **WP2.2 Task 4 fix pass 1 — metrics that improved when the generator produced less.**
  Four findings shared one root and are fixed as a family, with
  `test_generating_less_never_improves_a_backtest_metric` extended from the one case
  that was already safe (omit a leg → NaN) to all four.
  **`elicitability_score`'s arguments were inverted (Critical).** The metric froze
  `(V, E)` at history's values and varied the *generated* losses, collapsing the score
  to `c1·mean((L−V)⁺) + c2` with `c1 > 0` — monotone increasing in generated tail
  heaviness, with a generator emitting **identically zero** as its global optimum
  (measured: −3.139 for zero output vs −2.856 for matching history). DN-1.1 line 95
  makes this WP2.8's auxiliary loss, so shipping it would have trained toward zero
  volatility. Now the Tail-GAN direction: `(VaR, ES)` estimated from the **generated**
  ensemble, scored against **real** realizations — coercive as ES→0 and minimized
  exactly when generated `(VaR, ES)` matches history's. The scoring rule itself is
  unchanged and its consistency test passes under either wiring, so the deliverable is
  the new test that varies the *sample* rather than the *forecast*.
  **`discriminative_score` measured class imbalance, not fidelity (Critical).** Real
  and generated windows were pooled unbalanced (~100:1 at production scale) and scored
  by raw accuracy, which the majority-class predictor maximizes: with the two
  distributions held identical the score read 0.008 at 1:1 but 0.493 at 150:1, and
  *improved* as the ensemble shrank. Now a class-stratified split, inverse-class-
  frequency weights in the fit, and **balanced** accuracy (exactly 0.5 for any constant
  predictor at any ratio).
  **The backtest statistics scaled with `n_paths`.** `LR = 2·T·KL(p̂‖α)` with
  `T = months × n_paths` meant halving the ensemble halved the statistic and raised the
  p-value. The pooled sample size is now fixed in the sealed definition at **one path**
  (`months`, or `months−1` transitions): pooling still sharpens `p̂`, but the reported
  statistic is what a single reference-length path with that rate would have produced —
  an effect size on a p-value scale, stated as such in the new
  `conventions.backtest_reference_sample_size`.
  **`christoffersen_independence` was perfect on zero exceedances** (every count 0 ⇒
  `LR = 0`, `p = 1.0` at every `T`); now a `BACKTEST_MIN_EXCEEDANCES = 10` floor → NaN,
  in the shape of `DRAWDOWN_MIN_EPISODES`. Kupiec is deliberately *not* floored.
  Also: `RegisteredCrossStat` gains `length_matched` (mirroring `RegisteredStat`) and
  both `tail_dependence_*` entries set it `False` — at the production `resample_length`
  of 120 their 5% tail held 6 observations, below the estimator's own floor, so every
  replicate was NaN and the band was empty; the three places claiming a "band for free"
  are corrected. `_fit_gd` gains a Lipschitz-bounded step (`min(0.1, 1/L)`) and a
  gradient-norm stopping criterion — it previously ran a fixed 200 epochs at `lr=0.1`
  and diverged to `inf`/`nan` on a design ~4.5× real volatility. `_historical_strategy
  _returns` now asserts its inner join is a contiguous run of months (adjacent rows are
  read as consecutive months and multiplied by a duration of 8.5). Historical VaR/ES is
  memoized per `(strategy_id, level)` (~735 redundant pandas joins per battery run).
  Both LR builders normalize `-0.0`. RFR-23's premise is corrected in place: the ~1.2
  expected exceedances at 99% is the *per-path* count and Kupiec pools, so the real
  constraint is Christoffersen's per-path transition counts. `conventions.warm_up`
  records the momentum warm-up asymmetry (a perfect generator's expected exceedance
  rate is ~4.57%, not 5%) and why the reference-sample-size fix bounds its consequence
  to `LR ≈ 0.049` from `≈ 49`. Full suite green (862 tests, up from 850 — 12 new),
  ruff/pyright clean.
- **WP2.2 Task 4 fix pass 2 — the reference sample size was still gameable, one axis
  over.** Fix pass 1 pinned the Kupiec/Christoffersen reference sample size against the
  `n_paths` axis but read it off the judged ensemble's own `months` — so `LR ~ months`
  survived: a 60-month ensemble reported half the statistic (tail 0.05 → 0.17) a
  120-month ensemble with the identical exceedance rate reported. **The dominant "the
  metric improves when the generator produces less" failure mode had moved, not
  closed.** Fixed by pinning a new constant, `BACKTEST_REFERENCE_MONTHS = 120`, as
  `reference_n` unconditionally. The six backtest names are renamed
  `..._stat`/`..._pvalue` → `..._lr_1path`/`..._chi2_tail_1path` — the sealed
  `backtest_reference_sample_size` convention explicitly disclaims the significance-level
  reading `_pvalue` implied, so the scope is now in the name (the same fix
  `corr_matrix_distance` → `cross_block_corr_matrix_distance` made pre-seal, RFR-14).
  `conventions.warm_up`'s "LR_pof ~ 0.049, i.e. nothing" is corrected: the normalization
  rescales every departure uniformly, so a genuine coverage defect of the same magnitude
  reads identically — the honest statement is that the warm-up bias sets a *floor* on
  the smallest real coverage error this family can detect, which WP2.3 must accept or
  close, not wave away. Also: `discriminative_score`'s ~0.05–0.10 noise floor (binomial
  SE at ~60 held-out real windows) is now stated in both the sealed prose and the
  function docstring; the three public LR functions now say they differ from the
  registered (reference-scaled) metrics; `estimator_length_matching`'s blanket claim is
  now "by default", with the three departures named; `_HistoricalCache` is warmed inside
  `build_tails_suite` so a non-contiguous historical join raises at registration, not
  mid-battery-run. `governance/retrofit-register.md` gains three rows (RFR-24: a
  coverage-band alternative for WP2.3 to weigh; RFR-25: every threshold must be derived
  from post-fix runs; RFR-26: extends RFR-15's pooled-length mismatch to
  `tail_dependence_*`'s three-way version, which RFR-15's remedy doesn't reach). Full
  suite green (864 tests, up from 862 — 2 new), ruff/pyright clean.
- **WP2.2 Task 5 — `eval/metrics/memorization.py`, `eval/metrics/economics.py`,
  `eval/metrics/calibration.py`.** Three smaller suites, wired into
  `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS` and `prereg._METRIC_SUITE_NAMES`
  (already listed there) exactly as Task 3/4's suites were.
  - *`memorization.py` (tier `monthly`)* — `nn_distance_{p05,p50}`,
    `membership_inference_auc`, `near_duplicate_fraction`, the suite that makes "the
    generator did not memorize its training data" falsifiable for WP2.2b's NC4. A
    "block" is a non-overlapping 24-month window (`UTILITY_WINDOW_MONTHS`, reused, not
    restated) of one factor's own path, standardized by that factor's own TRAIN
    mean/std; distance is Euclidean, within one factor only. `nn_distance` is the
    pooled nearest-TRAIN-neighbour distance of every generated block;
    `membership_inference_auc` is a distance-to-nearest-synthetic-sample
    membership-inference attack (Mann-Whitney AUC, via `ah.eval.reference._rank`'s
    tie-averaging, reused not restated) distinguishing TRAIN from VALIDATION by
    proximity to the generated output; `near_duplicate_fraction` uses a data-driven
    epsilon (the 5th percentile of TRAIN's own leave-one-out nearest-neighbour
    distance). TRAIN/VALIDATION are split from `ReferenceStats.historical_series`
    (already train+validation combined) by the SEALED `ah.splits.TRAIN`/`VALIDATION`
    date boundaries, never a second `DataAccess` read — the only reference-dependent
    suite builder that needed this trick, since `register_reference_dependent_suites`'s
    `(manifest, reference)` call shape carries no live catalog access and the task
    brief asked not to touch it. Both directions tested: a literal
    training-decade replayer (with 1e-6 noise) scores `nn_distance < 1e-3`,
    `membership_inference_auc > 0.9`, `near_duplicate_fraction > 0.9`; an independent
    seeded draw scores `nn_distance > 0.5`, AUC `≈ 0.5`, fraction `< 0.05`.
  - *`economics.py` (tier `economic`)* — DN-1.1 §II.6's Economic row
    ("Implied Sharpe ratios, term premium, ERP by regime; no-money-pump audit;
    policy-anchor sanity — Defensible ranges, documented") judged as absolute
    literature-range bounds, never a bootstrap band, matching that row's own
    reference-data column. `implied_sharpe_{EXP,SLOW,REC,CRI,STAG,REF}` is a
    structural gap (RFR-27, mirroring RFR-17/18/20/22): `label_regime` needs `usrec`/
    `growth_yoy`, neither mapped in `factors.yaml`. `term_premium` =
    `mean(ust_10y - policy_rate)` (levels, no numeraire question); `equity_risk_premium`
    = `mean(equity_mkt - cash_tr_1m)`, subtracting the ALREADY-SEALED `cash_tr_1m`
    derived series (not a second, independently invented cash-rate decision — the
    exact numeraire trap RFR-12 already documents). `money_pump_violations` (enforce,
    max 0) audits every `conventions.numeraire_zero_cost_legs` leg per path for
    "never negative, sometimes positive" (a costless free lunch); a deliberately
    always-positive `smb` fixture proves a non-zero count, the deliverable Task 5's
    brief demanded. `floor_violations` (enforce, max 0) checks DN-1.1 §II.4's stated
    floors (`i >= -1%`, `spread >= 100bp`) directly against generated values, ahead of
    WP2.8's `constraints.py` making them structurally impossible. `policy_anchor_deviation`
    substitutes a stated, simplified Taylor rule (`TAYLOR_R_STAR`/`TAYLOR_PHI_PI` from
    DN-1.1 §II.2's own prior means; `TAYLOR_PI_TARGET` from the literature, since DN-1.1
    deliberately leaves π* undetermined) for the latent r*/π*/cycle-term anchor DN-1.1
    actually specifies, which no generated factor can supply. Every computable metric
    NaNs (poisons, never drops) below `ECONOMICS_MIN_OBS = 60` pooled observations or on
    any non-finite value — closing the "generate fewer months to dodge the audit" vector
    a raw count would otherwise open.
  - *`calibration.py` (tier `monthly`)* — `pit_ks_stat_{1y,5y}`,
    `interval_coverage_{50,90}_{1y,5y}`. Rolling-origin protocol stated in full: the
    predictive distribution is the generated ensemble's own pooled non-overlapping
    12/60-month sums (deliberately unconditional — no history-conditioned forecast
    exists below Step 3); the real side is every OVERLAPPING 1-month-spaced window of
    train+validation, fixed by history alone. PIT uses a mid-rank empirical CDF;
    `pit_ks_stat` is a closed-form one-sample Kolmogorov-Smirnov statistic against
    Uniform(0,1) (no scipy — verified against the hand-derivable `D = 1/(2n)` closed
    form for an evenly spaced sample, and cross-checked against the textbook sup-norm
    definition on a fine grid). Interval coverage brackets the nominal rate on BOTH
    sides (over-coverage is exactly as much a failure as under-coverage). Both floors
    (`CALIBRATION_MIN_GENERATED_SUMS`/`CALIBRATION_MIN_ORIGINS = 30`) NaN rather than
    report a small-sample-lucky number. A correctly-specified seeded forecast scores
    `pit_ks_stat < 0.08` and coverage within 0.08 of nominal; a deliberately
    over-confident (10x-too-narrow) forecast scores `pit_ks_stat > 0.2` and coverage
    more than 0.15 below nominal.
  - *Registration.* All three registered in `ah.eval.reference.PANEL_STATS` (no `fn` —
    every metric compares the generated ensemble against real data or a stated rule
    directly, the same shape `discriminative_score` already uses), eleven new
    `conventions.<name>_estimator` blocks in `pre-registration.yaml` (plus the
    `_CONVENTIONS_KEYS` allow-list entries in `ah/strategies.py` so the file still
    loads), `money_pump_violations`/`floor_violations` sealed `enforce, max: 0` in
    `thresholds.panel` (not a placeholder — the definition itself), and
    `test_every_real_threshold_key_is_produced_by_a_registered_metric` widened to union
    four of the seven reference-dependent suites' produced names (`monthly`,
    `memorization`, `economics`, `calibration`) rather than `monthly`'s alone (a
    pre-existing scope gap the new panel entries were the first to expose). Full suite
    green (934 tests, up from 864 — 70 new), ruff/pyright clean.
- **WP2.2 Task 5 review fix pass — the eighth "generator produces less" instance, two
  missing generated-side floors, and an unstated NaN-driven verdict.**
  - *Critical 1 — `policy_anchor_deviation` rewarded a degenerate generator.* A
    `policy_rate` path DETERMINISTICALLY equal to the simplified anchor every month
    scored exactly 0.0 — the numerically best value — under the old one-sided
    `{min: null, max: 10.0}` band, despite being LESS realistic than a generator with
    genuine idiosyncratic variation (real policy rates deviate from a Taylor-type
    anchor by ~1-2pp RMS). `pre-registration.yaml`'s threshold is now TWO-SIDED
    (`min: 0.3`), mirroring `interval_coverage`'s own "neither direction is free"
    precedent; `economics.py`'s module docstring and the `policy_anchor_deviation_estimator`
    convention state the caveat explicitly. `tests/test_economics.py` gains the
    deliverable: `test_policy_anchor_deviation_near_zero_is_not_automatically_good`
    shows the degenerate generator scoring strictly better than a realistic one, and
    `test_policy_anchor_deviation_degenerate_generator_fails_the_sealed_two_sided_band`
    shows the sealed band now catches it.
  - *Important 2 — `money_pump_violations` narrowed to a per-leg check.* DN-1.1's audit
    names a strictly dominating COMBINATION of factors; the implementation checks only
    single legs, with no search over weighted combinations. Stated in `economics.py`'s
    docstring and `pre-registration.yaml`'s `money_pump_estimator`, and recorded as
    `governance/retrofit-register.md` RFR-29.
  - *Important 3 — `memorization.py` had no generated-side floor.* Both sibling suites
    floor the generated side (`ECONOMICS_MIN_OBS`, `CALIBRATION_MIN_GENERATED_SUMS`);
    memorization only floored TRAIN. A one-path, 24-month ensemble collapsed
    `nn_distance_p05/p50` to a single observation and drifted
    `membership_inference_auc` toward its favourable 0.5 — "the generator produces
    less" reading as a pass. New `MEMORIZATION_MIN_GENERATED_BLOCKS = 30` (matching
    `CALIBRATION_MIN_GENERATED_SUMS`'s shape) NaNs all four names together below the
    floor; `test_memorization_nan_when_generated_side_is_too_small_even_with_ample_train`
    is the deliverable (TRAIN clears its own floor easily; the generated side does not).
  - *Important 4 — calibration tested only the under-confidence direction.* The
    over-wide (under-confident) direction — the likelier gaming route, a lazy
    huge-variance generator earning near-perfect coverage for free — was untested.
    `test_underconfident_forecast_shows_high_coverage_and_a_large_ks_statistic` adds it.
  - *Important 5 — `MEMORIZATION_BLOCK_MONTHS` silently followed `UTILITY_WINDOW_MONTHS`.*
    The sealed estimator states 24 as a literal; the code now raises `AssertionError`
    at import time if the two ever diverge, and a new test pins the value directly.
  - *Important 6 — `TAYLOR_PI_TARGET`'s literature substitution had no retrofit-register
    row.* RFR-27 covered only `implied_sharpe_*`'s structural gap. New RFR-28 records
    the substitution and the dropped `phi_c*c_t` term as the durable artifact WP2.3
    reads (an implementer's report is not).
  - *Important 7 — two new enforce gates changed the battery verdict, unstated.* On the
    `run_full_battery` orchestration fixture, `money_pump_violations`/`floor_violations`
    are both NaN (the fixture emits none of the audited factors), which FAILS both
    enforce thresholds under THE ONE NaN RULE — `report.passed` is `False`, previously
    unasserted anywhere. Decided explicitly rather than softened: NaN continues to fail
    (consistent with the platform's one uniform NaN rule; an ensemble that omits the
    audited factors has produced less, exactly the failure mode these gates exist to
    catch). `test_run_full_battery_orchestration_fixture_fails_on_the_money_pump_and_floor_gates`
    pins the verdict; `governance/retrofit-register.md` RFR-30 records the decision and
    its consequence for WP2.4 (the bootstrap generator must emit at least one audited
    factor from each set).
  - *Minor.* The three stray `np.random.default_rng(...)` call sites (two in
    `test_economics.py`, one in `test_calibration.py`) converted to
    `Generator(PCG64(seed))`, the repo's one seeded-RNG convention.
    `test_economics.py` gains the `ah.eval.g2`-import AST guard its two siblings
    already had. `test_every_real_threshold_key_is_produced_by_a_registered_metric`
    widened from four of the seven reference-dependent suites' produced names to all
    seven (adding `horizon`/`tails`/`utility`). `_pooled_memorization_signals` is now
    computed once per ensemble and cached (identity-keyed via a weak reference) across
    all four memorization metric closures, instead of four times. `pit_ks_stat_5y`/
    `interval_coverage_{50,90}_5y` re-tiered from `monthly` to `1_5yr` (DN-1.1's own
    tier for a 60-month horizon), reconsidered and corrected before the pre-registration
    seal rather than carried forward as a known-wrong assignment.
  - Full suite green, ruff/pyright clean.
- **WP2.2 Task 6 — `eval/metrics/conditional.py`, condition adherence + off-support
  degradation.** The last WP2.2 suite, and the only one whose metrics REGENERATE
  ensembles rather than reading the judged one: every metric resolves
  `ensemble.meta.generator_id` via `ah.gen.registry.resolve` and calls that SAME
  generator's `.sample(world, n_paths, seed)` fresh, once per authored/swept
  `NumericWorld` — "the bootstrap runs this suite too" is meaningful because the
  generator under test is re-invoked against conditions it may never have seen, not
  read off a stashed unconditional ensemble. Registered tier `monthly` (DN-1.1 names no
  "conditional" row); every threshold sealed `report`, never `enforce` — nothing here
  gates G2 (STEP2-GENERATOR-PLAN §WP2.3's own sealed rationale).
  - *Part A — condition adherence.* Four condition types mapped to
    `factor_conditions` (`inflation.average_pct`, `policy_rate.{start_pct,end_pct}`,
    `crisis_windows[0].{start_quarter,length_quarters}`,
    `crisis_windows[0].severity`), each backed by two checked-in authored worlds
    (mild/severe) under new `fixtures/worlds/conditional/*.json` (validated against the
    schema by both production code and a dedicated test). Two metrics per type —
    `condition_adherence_error_{type}` (pooled mean of every per-path error, across
    every path of every world of that type) and `condition_adherence_error_p90_{type}`
    (the pooled 90th percentile of the identical array), so a generator "usually right,
    occasionally wildly wrong" cannot hide behind a mean. `crisis_severity`'s target
    magnitude uses a stated, simplified linear map from the schema's own "1 =
    2008-scale" anchor (Q4 2008 S&P 500 TR ≈ -21.9%, `CRISIS_SEVERITY_REFERENCE_
    QUARTERLY_SHOCK_PCT = 22.0`) — the identical kind of substitution
    `economics.py`'s `TAYLOR_*` constants make, for the identical reason.
  - *Part B — off-support degradation.* Swept over `inflation`/`rate` only (the two
    condition types with a real train+validation quantity to define "distance from
    support" against — `crisis_timing`/`crisis_severity` have no real-valued analog
    under this simple definition; **WP2.7's `support.py` supersedes this placeholder
    for every condition type**). Distance is an ordinary z-score against
    `ReferenceStats.historical_series`; four levels (`typical` z=0, `p95`/`p99` the
    standard-normal quantiles, `beyond` z=4) construct the swept target
    `mean+z*std`, clipped to the schema's bounds. `off_support_adherence_at_{level}`
    (pooled mean error) and `off_support_pass_rate_at_{level}` (fraction within a
    stated 2pp tolerance) — "battery" here names this suite's own pooled checks, not
    the full cross-suite battery (that is WP2.9/WP2.11's severe-test-shaped
    evaluation).
  - *Anti-gaming, this work package's dominant failure mode, addressed from the
    start rather than by a fix pass.* Every pooled metric NaNs the WHOLE aggregate
    (never drops silently to a smaller surviving sample) on any single world's
    unresolvable `generator_id`, a generator exception during `.sample()`, an absent
    conditioned factor, or a non-finite value — `CONDITIONAL_MIN_OBS=20` is an
    additional floor. Tests prove both directions per condition type (a hand-built
    exact-tracking generator scores ~0; one mirroring WP2.2b's NC5 — ignores
    `factor_conditions` entirely — scores clearly worse), the p90-catches-a-tail case
    (88%-exact/12%-wildly-off generator: mean stays small, p90 does not), monotonic
    off-support degradation and a typical-vs-beyond pass-rate gap (both against a
    generator whose fidelity is a stated, known function of distance), and that
    omitting the conditioned factor NaNs rather than reading as a smaller error than a
    generator that emits it and adheres badly.
  - *Registration.* 16 names in `ah.eval.reference.PANEL_STATS` (no `fn`/band, the
    `economics`/`memorization`/`utility` shape — every metric compares a freshly
    generated ensemble to a WorldSpec's stated target, never a single-argument
    historical point estimate); `battery._REFERENCE_DEPENDENT_SUITE_BUILDERS["conditional"]`
    (a test asserts a real `run_full_battery` call returns all 16 by name, confirmed to
    fail before the row was added); five new `conventions.<x>_estimator` blocks in
    `pre-registration.yaml` (one per condition type covering its mean/p90 pair, one
    shared across all eight off-support names), plus their five keys added to
    `ah.strategies._CONVENTIONS_KEYS`'s allow-list (missed the first pass — the sealed
    document otherwise fails to load at all). `ah.eval.metrics.economics._cpi_yoy`
    renamed to public `cpi_yoy_from_level` so `conditional.py` reuses the identical
    trailing-12m YoY transform rather than restating it.
  - *`mc_error` is honestly `0.0`, not NaN, for every metric here* — every metric
    ignores the passed ensemble's own paths (only `generator_id`/`seed` carry into the
    regeneration), so `ah.eval.battery.mc_error`'s subsampling recomputes the identical
    value on every subsample by construction. Stated in the module docstring and pinned
    by a test rather than left to be discovered. *(Superseded by the fix pass below:
    correct arithmetic, misleading number.)*
  - Full suite green, ruff/pyright clean.
- **WP2.2 Task 6 review fix pass 1 — two Criticals, and the seal widened to cover
  sealed input data.**
  - *Critical 1 — partial support silently shrank the off-support pool.* When
    `_support_mean_std` returned `None` for one of the two swept types, the level was
    built from the surviving type alone and reported under
    `off_support_adherence_at_{level}`, whose sealed definition says "across **both**
    swept types". Now all-or-nothing: if any `OFF_SUPPORT_TYPES` member lacks support,
    every level is empty and every Part B metric NaNs. The pre-existing guard tested
    only the both-absent case — holding fixed the exact axis the defect lived on; the
    one-present/one-absent case is now parametrized over both directions.
  - *Critical 2 — the off-support monotonicity test's inflation arm was inert.* The
    `cpi` test fixture was deterministic geometric growth, so its trailing-12m YoY was a
    **constant** and `std(ddof=1)` ≈ 1e-14: every swept inflation target collapsed onto
    the historical mean and the arm contributed ~zero error at every level (measured:
    `[1.32e-13, 1.20e-13, 1.13e-13, 9.37e-14]` — flat, and *decreasing*). The whole
    monotone trend came from `policy_rate`; the test would have passed with the
    inflation sweep deleted. `cpi` is now a log random walk with real YoY dispersion,
    degradation is asserted **per swept arm** (a pooled assertion is what let one dead
    arm hide), the pooled assertion is strict (it previously read `later >= earlier -
    1e-9` under a comment claiming "strictly increasing"), and a separate test pins that
    both support distributions have real dispersion so a future fixture edit cannot
    silence an arm again.
  - *`mc_error` now measured over regeneration seeds (Important 7).* Reporting `0.0`
    beside a value carrying real Monte-Carlo uncertainty is worse than reporting
    nothing — it is the exact number a WP2.3 threshold author reads to size a band.
    New `conditional_mc_error` recomputes each metric at
    `CONDITIONAL_MC_ERROR_REPLICATES = 8` further regeneration seeds and reports
    `std(replicates, ddof=1)` (no `/sqrt(k)`: each replicate is an independent re-draw
    of the whole statistic, and the reported value is one such draw). Wired through a
    new **additive** `ah.eval.battery.MetricSpec.mc_error_fn` hook — default `None`
    keeps the uniform path-subsampling estimator for every other suite.
  - *Regeneration memo (Important 8, closes RFR-31 via RFR-32).* `_regenerate` is now
    memoized on the world **document** (canonical JSON), `generator_id`, `n_paths` and
    `seed` — keyed on the document rather than `world_id` because Part B's sweep worlds
    reuse one id per (type, level) while their target is a function of the reference, so
    an id-keyed memo would serve a second battery run the first run's ensemble. Cleared
    on every `build_conditional_suite`, so it never outlives one registry state. A full
    evaluation drops from ~670 `.sample()` calls to ~144 — fewer calls than before, now
    buying a real error bar instead of a tautological zero.
  - *The authored worlds are now inside the seal (Important 5, RFR-33).*
    `conventions.condition_adherence_*_estimator` defines each statistic as "pooled
    across every checked-in `fixtures/worlds/conditional/*.json` world tagged X", but
    `prereg._default_judged_sources()` hashed only `.py` files plus two YAMLs — so
    editing a world's `average_pct` changed every inflation metric with no lock
    violation and no amendment. New `_REQUIRED_JUDGED_FIXTURE_GLOBS` seals the directory
    as input data, exactly as `factors.yaml` is; a test edits a world and asserts the
    digest changes.
  - *Two exception paths no longer abort the whole battery (Important 3).*
    `gen_registry.resolve` invokes the registered **factory** (WP2.4's bootstrap will
    load and fit in its factory) and `load_worldspec(doc)` sat outside the `try`, so a
    factory raising during construction, or a swept world failing schema/pydantic
    validation, propagated out of `spec.fn` and lost every other suite's results. Both
    are inside one guarded region now, with a test each.
  - *Schema bounds derived, not restated (Important 4).* `_off_support_bounds()` reads
    `factor_conditions.{inflation.average_pct, policy_rate.end_pct}`'s `minimum`/
    `maximum` from `schemas/worldspec-v1.0.schema.json`; a new test validates every
    **programmatically swept** world against the schema (the existing fixture test
    globbed `FIXTURES_DIR` only).
  - *Tag↔field consistency validated at load time (Important 6).* A world tagged
    `inflation` whose `factor_conditions` lacked an `inflation` block raised a raw
    `KeyError` at metric-evaluation time → battery abort, not NaN.
  - *Missing tests added.* A determinism pair (same seed ⇒ bit-identical, different seed
    ⇒ different — using the only test double that consumes `seed`), and the min-obs NaN
    branch, which was never exercised: the test carrying that name asserted
    `errors.size >= CONDITIONAL_MIN_OBS`, the **opposite** of its claim. It is renamed
    to what it actually checks and a real boundary test added (one short ⇒ NaN, exactly
    at the floor ⇒ reported), for the mean, the p90, and Part B.
  - *Minors.* Fixed a misattributed citation ("DN-1.1 §WP2.3" → STEP2-GENERATOR-PLAN
    §WP2.3) in a sealed source; `import copy` hoisted to module level; conditioning
    targets read off the `NumericWorld` projection the generator was handed rather than
    the raw JSON dict (`load_worldspec` now runs once per regeneration, not twice); the
    regeneration index `k` is globally unique instead of restarting per condition type
    (the docstring's `base_seed + 7919*k` claim is now true); `off_support_pass_rate_at_
    beyond`'s `min: 0.0` — a threshold on a `[0,1]` rate that can never be violated —
    raised to a non-vacuous provisional `0.05`; `tests/test_conditional.py` gained an
    autouse fixture restoring `ah.gen.registry`'s global table (seven registrations
    previously leaked into every later test module); and `rate_endpoints_mild`'s
    endpoints widened from 2.0→3.0 to 5.0→2.0, because a 3.0 endpoint was nearly free
    against the condition-ignoring generator's flat-3.0 output — the discrimination
    assertion is now a per-type margin scaled to each type's own fixture spread rather
    than a single flat `+1.0`.
  - 995 tests pass (was 972); ruff/pyright clean; coverage gate 96.54%.

## [v0.1.0-g0] — 2026-07-24

Gate G0 ("lay the rails") complete. All seven G0 criteria pass — see `G0-EVIDENCE.md`.
The toy world round-trips `compile → validate → run → record → replay` bit-identically.

### Added
- **WP0.9 — CLI, governance, docs, G0 end-to-end.** `ah` CLI (typer):
  `world build --preset|--scenario [--live]`, `world validate|show`, `run
  [--seed --paths]`, `replay` (recompute+compare digest), `verify`, `battery`,
  `chronicle`; SQLite state at `data/ah.db` (`--db` to override). Four preset worlds
  (`src/ah/presets/`, via `scripts/gen_presets.py`). Governance: `model-inventory.yaml`,
  `decision-register.md` (D1-D10, OPEN), `genai-track.md`. README loop + G0 checklist.
  `tests/test_g0_end_to_end.py` executes the seven G0 criteria programmatically.
- **WP0.8 — Validation battery skeleton.** `battery/stylized.py`: excess kurtosis,
  skew, Hill tail index (5% tail), ACF of returns (lags 1-5) and |returns| (lags
  1-12), max-drawdown distribution, cross-correlation matrix + Frobenius distance.
  `battery/thresholds.yaml`: per-metric {min?,max?,status} (all `todo` in Step 0).
  `battery/report.py`: `run_battery` → markdown + JSON, exits non-zero only on
  `enforce` failures; `BATTERY_VERSION = "battery-0.1"`. CI runs
  `python -m ah.battery.report` on the stagflation preset.
- **WP0.7 — Compiler interface + offline regression harness.** `CompilerProtocol`
  with `FixtureCompiler` (offline, slug→`fixtures/compiler/{slug}.json`) and
  `AnthropicCompiler` (live, CLI `--live` only; lazy `anthropic` import; never
  imported by tests). `postprocess.extract_json` (fence-strip + outermost-`{}` +
  parse); `prompt_v1` (`compile-world-v1.0`, JSON-only + fictional-entities rule);
  `pipeline.process` (validate→clamp→construct). 50 checked-in fixtures
  (`scripts/gen_fixtures.py`): 40 valid, 5 clamp, 5 reject — harness asserts valid+
  clamp build and run 12+ months, clamp records clamps, reject is rejected.
- **WP0.6 — Stores + digest.** `core/digest.py`: canonical JSON (sorted keys,
  compact, shortest-round-trip floats) and SHA-256 over float64 path tensors rounded
  to 12 decimals (`digest_paths`, `digest_ensemble`). `store/db.py`: SQLite (WAL,
  foreign keys) with `worlds`, `run_records`, `chronicle` tables and append-only
  chronicle triggers. `store/worlds.py`: engine-field immutability (edits under an
  existing world_id are rejected; narrative/provenance edits allowed in place).
  `store/runrecords.py`: save/get + `verify_run` (recompute digest from stored
  world+seed and compare) — tamper of stored digest or world is detected.
  `store/chronicle.py`: append/read only (no mutators), trigger-enforced at the DB.
- **WP0.5 — Institution simulator + decisions.** `simulate_institution(paths,
  decisions)` runs the start mix through an engine path with annual decision points
  (month `12*year-1`, years 1-9) and actions `hold|derisk|leanin|secondary`
  (10pt growth↔defensive shifts preserving proportions; secondary sells ≤8pts PE at
  0.82 with a total haircut and a pe→bonds target move). Returns are read as percent
  with per-sleeve limited liability, so weights sum to 1 and no sleeve goes negative
  by construction. `hold_course_twin` (passive benchmark) and `decision_alpha`
  (active − twin). Golden hold-course value + hypothesis invariants.

### Changed
- **Engine (WP0.4) HY spread-shock scaling.** WP0.5 surfaced that the HY
  `3.5·Δspread` term used Δspread in bps, producing ±300%/month returns; the spread
  path is bps but that coefficient only yields sane monthly returns with Δspread in
  percentage points. Δspread is now converted bps→pp; HY is now ±6-9%/month, in line
  with its own vol term and every other asset. The WP0.4 golden digest was
  regenerated accordingly.

### Added (earlier)
- **WP0.4 — Deterministic toy engine (`toy-v0`).** Monthly, pure-function engine
  (`run_path`, `run_ensemble`) over a `NumericWorld`: policy-rate AR path, HY-spread
  rise/decay, inflation AR, binary crisis mask, common-factor asset returns, and
  quarterly appraisal-smoothed reported marks for pe/pc/re. All randomness from one
  `Generator(PCG64(seed))`, drawn up front in fixed order; ensemble seeds
  `base_seed + 7919*k`; errors clearly on non-`toy-v0` generators. Tests: frozen
  golden digest (seed 42 stagflation), determinism, hypothesis invariants
  (finite / rate>=0.1 / spread>=150 / reported flat off quarter-ends), ensemble
  seeding, and the narrative-blindness guard (now access-pattern based).
- **WP0.3 — Validator (V-rules).** `validate(world) -> ValidationResult`
  {clamped_world, clamps, warnings, blocking}, implementing V1-V12 (WORLDSPEC.md §3).
  Bounds clamps (V9) are driven from the JSON Schema itself (one home for bounds),
  recorded as {path, submitted, applied}; >3 clamps warns. V2 clamps windows/peaks
  into the horizon; V3 swaps inverted spreads; V1/V4/V5/V6/V7/V8 warn on coherence;
  V10/V11 and custom-vintage-without-sleeves (V12) block. `validate` is pure (no wall
  clock); `stamp_validation` writes `provenance.validation` and flips draft→validated
  with a caller-supplied `validated_at`. 51 tests: one per rule, edge cases, and a
  table-driven sweep; canonical example is the clean baseline.
- **WP0.2 — WorldSpec models + loader.** pydantic v2 models mirroring
  `worldspec-v1.0.schema.json` exactly (required⇔required, `extra="forbid"`⇔
  `additionalProperties:false`, bounds/patterns/lengths). `load_worldspec(path|dict)`
  validates against the JSON Schema (Draft 2020-12) first, then constructs the model.
  Property test (hypothesis, 400 examples) asserts pydantic accepts ⇔ jsonschema
  accepts on fuzzed near-valid documents; canonical example round-trips identically.
  Narrative-blindness enforced structurally via a `NumericWorld` projection that
  omits `narrative`/`provenance`, plus a source-scan guard over engine/institution.
- **WP0.1 — Scaffold, tooling, CI.** Single-package `src/ah` layout; `pyproject.toml`
  pinned to Python 3.12 with the STEP0-PLAN §1 dependency set; uv workflow; ruff
  (lint+format), pyright (basic), pytest with `--disable-socket` (pytest-socket),
  coverage on `ah.core`; pre-commit hooks; GitHub Actions `ci.yml`
  (lint → typecheck → tests) with no network access; minimal `ah` CLI entry point.

### Contracts
- `worldspec 1.0.0` — vendored under `schemas/` (read-only): `worldspec-v1.0.schema.json`,
  `example-long-stagflation.worldspec.json`, `world-bible-v1.0.schema.json`, `WORLDSPEC.md`.
