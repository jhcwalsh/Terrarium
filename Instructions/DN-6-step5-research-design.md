# DN-6 — Step 5 Research Design

*Draft v0.1 · August 2026 · Specifies the research programme Step 5 is supposed to produce, and the small number of things that must happen at M4 for it to be possible at all. Companion to DN-5 (which defines the measure), D9 in the tier-1 decision register (which defines the generator-evaluation protocol), and D-06/D-08 in the documentation register.*

---

## 1. The one thing that is urgent

Everything in this note is deferred except one item, and that item lands at M4.

**Research consent must be obtained when the data is collected.** A cohort of beta players cannot be retroactively consented, and player decision data collected without a research-use basis is unusable for publication no matter how good it is. This is a clause in D-08, which is already on the M4 blocking list, so the cost today is a paragraph and a checkbox. The cost of discovering it later is the first year of data.

Everything else in this document can be drafted at leisure. This cannot.

---

## 2. Three papers, not one

They have different audiences, different timelines, and only one depends on human subjects. Conflating them has been delaying all three.

| | Paper | Depends on | Could start |
|---|---|---|---|
| **P1** | **World-model positioning working paper** — Terrarium as a *specified* rather than learned world model; a POMDP with authored hidden state; sim2real and domain randomisation framing | Nothing. DN-1.1 exists | **Now** |
| **P2** | **TERRARIUM-Bench** — the validation battery as a published, versioned standard | D4 strategy-set freeze, D6 thresholds, Step 2 seal | After G2 |
| **P3** | **Decision density** — where in a decade decision value concentrates, and whether simulated experience changes decision quality or only risk appetite | Consent at M4, ranked-run volume, WP3.11 | M8 |

P1 and P2 need no human data. P3 is the one this note is mostly about.

---

## 3. What P3 actually claims — and the trap in it

The simulated-experience literature has a well-established finding and a well-established limitation. The measured effect of experiential sampling is **changed risk-taking**, not demonstrably improved decision quality. A sceptical practitioner will raise this, and if the paper's framing does not already contain it, the paper loses.

So the framing is not "simulation improves decisions." It is:

> Existing work cannot separate changed risk appetite from improved judgement because it lacks a ground-truth counterfactual against which a decision can be scored. Terrarium supplies one — the policy twin on a fixed revealed path — and can therefore measure both quantities simultaneously and report which moves.

**That separation is the contribution.** It is a stronger paper than "our simulator works," it is honest, and it is publishable whichever way the result comes out — which is the property a pre-registered study needs.

This requires two distinct pre-specified outcomes:

| | Construct | Measure |
|---|---|---|
| **Primary** | Decision quality | Decision alpha *A* against the policy twin, per DN-5 §5.1 |
| **Co-primary** | Risk-taking | Ex-ante risk of the chosen allocation at each decision window — private weight, public equity beta, and modelled drawdown exposure |

A finding that risk-taking rises while *A* does not is a *result*, not a failure, and the paper must be written so that it reads as one.

---

## 4. Identification

### 4.1 The design advantage, stated precisely

On a canonical challenge seed the revealed path is byte-identical across players. Decisions are therefore the only difference between two runs, and *A* is computed against the same twin on the same path. That is an unusually clean comparison — closer to a controlled experiment than most behavioural finance field data — and it is worth stating in the paper as a methodological contribution in its own right.

### 4.2 The flagship experiment — randomise the reported/true toggle

The product already contains its own treatment. The reported-vs-true toggle is the single most demonstrable idea in Terrarium, and whether it *helps* is an open empirical question with a genuine answer either way.

```
Arm A   reported values only          (the institutional status quo)
Arm B   reported + true toggle        (the product's central claim)
```

Randomise at first ranked run, stratified by world. Hypothesis: Arm B shows higher *A*, concentrated in windows following a private-mark divergence.

This is the strongest design available, it costs almost nothing — the toggle is a feature flag — and it directly tests the product's own thesis. **A null result here is important information and should be published.**

⚑ *Product decision required: withholding a feature from half of new users is a real product cost. Recommend running it as a time-boxed cohort at beta rather than permanently.*

### 4.3 Secondary randomisation — the social-proof reveal

Showing "68% of players de-risked in year 4; they finished 1.9 points behind" is in the extensions backlog as a growth mechanic. Randomising *when* it is shown makes it a herding experiment. Cheap, and the resulting finding is more shareable than the mechanic it came from.

### 4.4 Observational strand — decision density

No randomisation needed. Across many players and worlds, the distribution of |*c_j*| by window position, by market state at the window, and by action type. The question is where decision value actually concentrates — and the prior worth testing is that it concentrates in very few windows.

Note the DN-5 §5.4 pacing-lag artefact will show up here as a real finding: late-decade pacing actions carry near-zero *c_j*. That is substantive, not noise.

---

## 5. Threats to validity

Stated bluntly, because the strongest of them is created by a product decision already ratified.

| Threat | Severity | Handling |
|---|---|---|
| **Differential attrition** | **Highest.** A full decade is a long session, and players who are losing quit more than players who are winning. Attrition correlated with the outcome variable is the classic way a performance study becomes uninterpretable | Intention-to-treat on all ranked starters. Report completion by arm and by interim performance. Pre-specify a completion-rate floor below which the primary analysis is reported as exploratory |
| Self-selection into ranked | High | Ranked requires an account, so the population skews engaged. Describe it honestly; do not generalise to practitioners at large |
| World self-selection | Medium | Stratify by world; report within-world estimates |
| Practice effects | Medium | Practice replays are already excluded from scoring. Log them and use as a covariate rather than discarding the information |
| **Help-agent usage** | Medium, and easy to miss | The agent ships at M4 and explains mechanics. It is part of the treatment environment. **Log every interaction** — it is both a confound and one of the more interesting covariates available |
| No experience covariates | Medium | §7 |
| Multiple comparisons across K windows | Medium | Pre-specify the primary window-level test; everything else exploratory and labelled as such |
| Hawthorne / gamification | Low–medium | Players know they are playing. Acknowledge; the counterfactual twin absorbs most of the concern |

---

## 6. Pre-registration

Registered on OSF or AsPredicted **before the first ranked run**, not before analysis. Contents:

- Hypotheses, stated directionally, for the primary and co-primary outcomes
- Exact definition of *A* and the risk measures, with `decision_alpha_version` pinned
- Randomisation procedure and stratification
- Inclusion and exclusion rules — including how incomplete runs are treated, decided in advance
- Primary analysis specification; everything else declared exploratory
- Stopping rule
- The completion-rate floor from §5

This mirrors the D6 discipline already applied to the generator thresholds. The behavioural study is where analytic flexibility does the most damage, so it gets the same treatment.

---

## 7. The covariate tension — decide deliberately

The study wants experience level, role, and prior alternatives exposure. The funnel wants no friction at signup. These are in direct conflict, and whichever team ships first will settle it by default unless it is decided.

Options, in ascending friction:

1. **Nothing.** Cleanest funnel, weakest paper — no way to say whether the effect differs for practitioners and students
2. **Post-run, optional, one screen.** Asked after the first completed run, when the player is engaged rather than at the door. **Recommended**
3. **At signup.** Best coverage, worst conversion

⚑ *Product + Quant. Recommend option 2, three questions maximum, explicitly optional, asked once.*

---

## 8. What must be logged from the first ranked run

The analysis dataset is not recoverable retroactively. Log now:

```
run_id, world_id, seed, decision_alpha_version, arm assignments
per window:  actions[], revealed state at submission, server timestamp,
             time-on-window, toggle state, help-agent interactions
outcome:     A, c_j series, risk measures per window,
             forced-sale events, completion status
player:      pseudonymous id, account age, runs completed,
             optional covariates (§7), consent flags
```

Most of this exists in the RunRecord already. The additions are toggle state, help-agent interactions, time-on-window, and arm assignment.

---

## 9. Power

Unknown, and honestly so. The variance of *A* across players on a fixed seed has never been observed — it is the single number that determines whether P3 is feasible at beta scale or needs a year of accumulation.

**Recommended sequence:** run the first 200–300 ranked runs as an explicit pilot, estimate the variance, then pre-register the main study with a real power calculation. Do not pre-register a study whose sample size was guessed.

The pilot is not wasted — it is also the completion-rate instrument from A2 §3.

---

## 10. Governance

| Item | Owner | When |
|---|---|---|
| Research-use consent in D-08 | Counsel | **M4 — blocking** |
| Anonymisation, retention, withdrawal policy | Counsel | M4 |
| Ethics review — needed or not, depends on venue and co-author affiliation | You | Before co-authors, not before submission |
| Conflict-of-interest disclosure — commercial interest in the instrument, employer relationship supplying calibration data | You + Albourne | Pre-agreed, not improvised at submission |
| Data-sharing position — the replication package | You | With P3 pre-registration |

The conflict disclosure is straightforward but should be agreed in advance. Every journal will ask, and the answer is more comfortable when it was written before the results were known.

---

## 11. Open

| # | Item | Blocks |
|---|---|---|
| 1 | Whether the toggle randomisation runs at all, and for how long (§4.2) | P3 flagship design |
| 2 | Covariate collection point (§7) | Logging schema |
| 3 | Target venue for P3 — finance, decision science, or HCI | Framing, ethics requirement |
| 4 | Whether P1 is a preprint now or waits for G2 evidence | Nothing. Recommend preprint now |
| 5 | Completion-rate floor for the primary analysis (§5) | Pre-registration |

---

*Not investment advice. Research design only; no data has been collected.*
