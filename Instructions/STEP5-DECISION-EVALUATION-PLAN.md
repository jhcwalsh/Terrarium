# STEP5-DECISION-EVALUATION-PLAN.md — Scoring Decisions Against the Road Not Taken
## Implementation plan for Claude Code · Step 5 (WS-G) · produces G3/G4 evidence and RQ1–RQ4

**Prerequisite:** Steps 3 and 4 sufficiently complete that decisions can be made and outcomes measured. **Critical constraint:** the metric definitions and evaluation protocol in WP5.1–5.2 are **frozen during Step 3**, before any result is seen. Freezing them here, after outcomes are visible, would invalidate the entire exercise.

**Mission.** The platform's product is not paths or stories — it is decisions evaluated against counterfactuals. This step builds the harness that scores them, spends the touch-once holdout exactly once, and consolidates the research questions into a publishable record.

### Definition of done
1. The evaluation protocol is sealed (same mechanism as Step 2's pre-registration: YAML + metric code hashed) before the first evaluation run.
2. Walk-forward evaluation runs over the training/validation span with Wilcoxon signed-rank across folds; results reproduce from RunRecords.
3. Every decision-maker — human committee, AI committee, heuristic rule, and each benchmark policy — is scored on identical worlds and seeds against its hold-course twin.
4. **Decision-density analysis** delivered: decision alpha attributed by window across thousands of worlds, answering empirically where in a decade value is created and destroyed.
5. The holdout is evaluated **once**, through the explicit-purpose path, and the result is written up whatever it says.
6. `RESEARCH-EVIDENCE.md` consolidates RQ1 (fidelity), RQ2 (held-out regimes), RQ3 (decision value), RQ4 (robustness) with the honest negative results included.

---

## Work packages

**WP5.1 — Protocol implementation.** Expanding-window walk-forward per D9; fold structure; quarterly rebalancing; the benchmark decision-policy set (history-only optimization, Gaussian Monte Carlo, bootstrap ensemble, static 60/40, static endowment mix, plus fixed heuristic rules); Wilcoxon signed-rank across folds with effect sizes, not just p-values.

**WP5.2 — Metric definitions, frozen.** **Drawdown surprise** (realized max drawdown minus ensemble-predicted p95, per fold) as the headline. Plus: decision alpha vs hold-course twin; **decision alpha by window** (R12); forced-sale incidence and cost; liquidity-shortfall probability; funding-ratio tail outcomes (worst 1%); private-weight breach duration; pre-commitment adherence rate (from Step 4's playbook); and calibration carried over from Step 2's battery tier. Each with an exact formula, a worked example, and a unit test.

**WP5.3 — Counterfactual machinery.** The hold-course twin per run; re-coning (conditional ensemble regenerated from any mid-path state, answering "what could still happen from here"); and the counterfactual scoring that gives the platform its name — *given what was known then, across the paths that could have followed, was that decision good?* — implemented as an explicit metric rather than a narrative flourish.

**WP5.4 — Multi-agent comparative harness.** Same world, same seed, N decision-makers, independent institutions; leaderboards; dispersion statistics; and the cohort-exercise export (what a wargame produces afterward: each team's path, decisions, rationales, and scores).

**WP5.5 — Decision-density study.** Across thousands of worlds and decision-makers, attribute outcome dispersion to decision windows: which windows matter, how much, and under what conditions. Expected finding, to be tested rather than assumed: consequence concentrates at t₀, at regime breaks, and in the re-risking window after a trough — with quiet-period decisions carrying delayed weight. This is the platform's most distinctive research output and it feeds directly back into Step 4's window design.

**WP5.6 — The one-shot holdout.** Through the explicit-purpose access path, once, logged. Everything else has been decided by then; this is confirmation, not exploration.

**WP5.7 — Research consolidation.** `RESEARCH-EVIDENCE.md` assembling RQ1–RQ4 with the Step 2 ablation, the Step 3 episode reproduction, the Step 4 actor validation, and this step's decision results — including the negative results, which are the credibility of the whole record. Publication pack: methods, pre-registration hashes, ablation tables, and the reproducibility appendix (every figure regenerable from a RunRecord id).

---

## Sequencing, non-goals, pitfalls
**Order:** 5.1 → 5.2 (both frozen during Step 3) → 5.3 → 5.4 → 5.5 → 5.6 → 5.7. **Non-goals:** live client deployment; any claim about AI-actor quality that outruns the Step 4 evidence; optimization *of* decisions (this step measures; a future step could optimize, and would need its own protocol). **Pitfalls:** metric definitions quietly adjusted after seeing results (the seal exists for this); comparing decision-makers on different seeds or worlds (identical or it means nothing); p-value hunting across the metric set (pre-state the primary metric — drawdown surprise — and treat the rest as secondary); mistaking a single decade's decision alpha for skill (always across folds and worlds); and the deepest one — concluding that a policy is good because it won in the ensemble you generated, when what you have tested is the policy *and* the generator together. Say so plainly in the write-up.
