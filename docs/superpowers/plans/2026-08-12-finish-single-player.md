# Finish the single-player game (owner directive 2026-08-12: "now")

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans,
> task by task. Authority: `Instructions/DN-5-decision-alpha-and-twin.md`
> v0.2 (the twins, the levers, §7's acceptance table),
> `Instructions/experience-deltas-register.md` rows E1/E3/E4/E7,
> `Instructions/KICKOFF-PRODUCT-SU.md` §2 (the vertical slice). Owner
> directives in force: group play back-burnered; toy-engine realism family
> ignored; housekeeping queues immediately after this plan.

**Goal:** the vertical slice's sentence becomes fully true: "annual decision
windows open with the committee briefing, the four public actions **plus the
commitment lever**, … the post-game review renders **three series**,
per-window annotations, **the flinch cost and the arithmetic warning**."

**Alpha discipline:** sp-01 changes the twin (fixed pace → DN-5's ratified
pacing flex) and the decision space — ONE bump to `port-v3-pacing` /
`port-v3-pacing-gen` when sp-01 lands; later WPs ride it.

### sp-01 — the pacing core (server-side)
- [ ] The player's per-sleeve annual commitment as a decision type: a
      structured decision (`commit`, per private sleeve, in points) beside
      the four public actions; "hold to plan" recorded distinguishably from
      an unvisited window (E1's engine-side requirement).
- [ ] The POLICY twin flexes pacing per DN-5 §2.1:
      `target_commitment = base_pace × g(w_policy − w_reported)`, g clipped
      to a floor/ceiling band — never zero, never doubled.
- [ ] The DRIFT twin (fixed nominal schedule, annual rebalance never) as a
      computable third run at outcome time — E7's "data arrival".
- [ ] DN-5 §7 acceptance subset: telescoping (Σ contributions = alpha),
      null player scores exactly 0.0, drift reduction (band → ∞ &
      fixed rule reproduces the drift twin bit-for-bit), pacing floor holds
      in the deepest drawdown, determinism.

### sp-02 — the lever in the hand (app)
- [ ] Decision window UI gains the commitment control (per-sleeve, default
      pre-filled with the plan's pace; committing the default IS "hold to
      plan" and is recorded as such).
- [ ] The t₀ pacing plan rendered (the plan you are holding to or leaving);
      coverage on both bases and the vintage stack are already in view.
- [ ] Server remains the authority; the app renders and asks.

### sp-03 — the two annotations (E4)
- [ ] The FLINCH COST: commitment cut → later distribution shortfall vs the
      t₀ plan, computed from the session record alone at outcome time.
- [ ] The ARITHMETIC WARNING: a coverage reaction that was denominator-
      driven (NAV fell) rather than numerator-driven (calls rose), priced.
- [ ] Review screen renders both, "state the number, never gloat."

### sp-04 — the loose ends
- [ ] `board_pack` producer (five sections from tape stats + wire; the
      template exists, nothing feeds it).
- [ ] Realized-regime episode markers for generated worlds
      (`summary.episodes` from the revealed path's RegimeRecord, not the
      authored sequence).
- [ ] The programme walk for generated worlds (the console's pending note
      goes away; `build_programme_report` dispatches like everything else).

### sp-05 — the tutorial consequence + register close-out — DONE 2026-08-12
- [x] The commit-primer on the setup screen: one unmissable commitment
      consequence, every player, every decade, pinned by test. Plus E1's
      two remaining moment-of-decision gaps: the vintage stack by age and
      trailing distributions (session-served, rendered in the ledger panel).
- [x] Register rows E1/E3/E4 CLOSED with pointers (E3's I5 deferral
      recorded); `docs/interpretation-guide.md` written with
      coverage-on-both-bases as the toggle's second act; the stale
      Reckoning copy now states the forced-secondary count.

**PLAN COMPLETE 2026-08-12.** sp-01 `2443225` · sp-02 `01a0bf2` · sp-03
`23ab335` · sp-04 `de9c207` · sp-05 (this merge). The single-player game is
finished by the register's own definition of done. Next per the owner's
standing order: the governance housekeeping (gate-merge guard, citation
checker, reference-parameter check).

**Gate per WP:** acceptance tests + full suite + ruff/pyright + CHANGELOG;
merge `--no-ff` only after the gate log's EXIT line is read as its own step.
