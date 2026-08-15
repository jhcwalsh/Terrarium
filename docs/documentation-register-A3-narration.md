# Documentation Register — Amendment A3
## The DN-9 narration series, triaged · August 2026

*Patches the register with the decisions raised in DN-9 v1.2. Follows the A2 format. **The point of this document is that thirty-five entries are not thirty-five decisions** — most are parameters awaiting a value, and several will be answered empirically by the workbench build rather than by anyone sitting in a room.*

---

## 1. How the thirty-five sort

| Bucket | Count | Process | When |
|---|---|---|---|
| **A · Ratify** — genuine choices that block work | **9** | One session. You, with Product | **Now** |
| **B · Parameter register** — need a *value*, not a choice | 13 | Owner supplies; several fall out of the workbench | With the build |
| **C · Editorial convention** — settle by fiat, low stakes | 5 | Editorial decides, logs it | With the style guide |
| **D · Referred** — belongs to another note | 4 | Raised there, not here | Per that note |
| **E · Pre-registration** — test criteria, sealed not ratified | 4 | **Different process entirely** | Before the test runs |

**Only bucket A needs you.** Nine decisions, most of which have a recommendation already attached.

---

## 2. Bucket A — ratify these nine

| # | Decision | Recommended | Blocks |
|---|---|---|---|
| N-c | Does the paper ever report the true plane? | **No, in every arm.** The paper sees what a publication sees | Renderer; **DN-6 arm-A integrity** |
| N-h | Front page replaces the outcome card | **Yes.** Same renderer, same cache key | Sharing-spec amendment |
| N-n | Quarterly slate as the turn unit, monthly tape retained | **Yes.** Refines A2 decision 3, does not reverse it | WP4.6–4.7, DN-3 |
| N-ac | Board power: colour / soft / hard | **Soft, with early termination** | WP4.9, DN-5 |
| N-ai | Tier-2 narration as a paid feature; Tier-1 compilation free | **Yes.** Free tier keeps three of the four best mechanics | PLG strategy, free/paid line |
| N-r | Rationale agent as a fourth LLM role, with its own boundary note and gate | **Yes**, M5 | D-15 revision, WP4.2h |
| N-m ⚖ | Real public institutions named, real individuals never | **Yes** | All template packs |
| N-u ⚖ | Verdict tags: two axes, no portfolio axis | **Yes.** The third axis is advice | Tier-1 templates |
| N-d ⚖ | Dot-plot inclusion, with error calibrated to real projection error | **Include** | FOMC module |

Three are Counsel-dependent and can be batched into one review.

**N-c is the one to take first.** It is the only entry here where a wrong answer invalidates something already built — the DN-6 flagship experiment depends on arm A never seeing the true plane, and a paper that could see through appraisal smoothing would be the leak.

---

## 3. Bucket B — parameter register, not decisions

These need a number. They belong in the model parameter register alongside the WP3.9 entries, with owner and blank value, and **several will be filled by the workbench's `UNRESOLVED.md` rather than by judgement.**

| # | Parameter | Owner | Filled by |
|---|---|---|---|
| — | **Severity cut-points, per-class scales, 22 thresholds** | Quant | Workbench, calibrated against the ensemble |
| N-o | Slot-contest tie-breaks; three-vs-four-slot threshold | Editorial | Workbench |
| N-p | Smoothed narration anchor ρ | Quant | Fit once, freeze, stamp |
| N-e | Consensus dispersion — spec parameter or fixed | Quant | Workbench |
| N-a | Thread-class taxonomy; parity tolerance | Editorial + Quant | Bible builder |
| N-b | Vocabulary cross-firing rates | Editorial + Quant | Workbench diagnostics |
| N-b2 | Derived-observables register — 3 entries | Quant | Workbench |
| N-i | Columnist hit-rate target | Editorial | Judgement |
| N-t | Stickiness — median thesis life 4–6 meetings | Quant + Editorial | Calibration |
| N-z | Risk-flag parity rate (15–25%) | Quant + Editorial | Calibration |
| N-x | Bias register — 5 entries, each with a parameter and a test | Editorial + Quant | Agent build |
| N-s ⚖ | Filtered-state estimator ŝ_t | Quant | Spec, then build |
| N-ah | Board reaction-bank dimensionality | Eng + Quant | **Sized empirically against repetition — it is the largest cost lever** |

**Do not attempt to fill these in a ratification session.** Guessing at values the build will surface empirically is how unratified numbers become canon.

---

## 4. Bucket C — editorial convention

Settle, log, move on. No session required.

| # | Convention | Recommended |
|---|---|---|
| N-ab | FOMC = the Committee; governance body = the Board | **Adopt.** Already caused one collision in conversation |
| N-g | Single house masthead across worlds | **Adopt** — brand furniture, and it reads on a share card |
| N-aa | Mandate boundary as a hard template constraint, not prompt guidance | **Adopt** — it is the mechanism that produces the lag |
| N-ae | Board B's failure mode built with equal weight to A's | **Adopt** — otherwise it is a difficulty slider |
| N-ad | Persona model: A/B poles with an interpolating parameter | **Adopt** |

---

## 5. Bucket D — referred elsewhere

Raised in DN-9, owned by another document. Log the referral so it is not lost.

| # | Item | Referred to |
|---|---|---|
| N-ag ⚖ | Scoring: report both vs decompose | **DN-5** |
| N-y | Economist / columnist / help-agent role boundaries | **D-15**, next revision |
| N-f | Annual review immediately before the decision window | **DN-6** — it is a treatment worth randomising |
| N-j | Peer-survey randomisation design | **DN-6 §4.3** |

---

## 6. Bucket E — pre-registration, not ratification ⛔

**Different process, and the distinction matters.** These are tests. They get sealed with criteria before running, not ratified in a register. Treating them as ordinary decisions is the exact defect P2 §8 catalogues: *a sealed protocol pinning a procedure but no criterion.*

| # | Test | Must be sealed before |
|---|---|---|
| N-k | N-2 leak probe: specification and margin | Tier-2 exists |
| N-w | N-2 extended: with and without rationale text | Rationale agent ships |
| N-v ⛔ | Rationale strain as a policy-realism metric in the battery | Strain is reported |
| N-q ⛔ | Policy-path quantisation; step-size and reversal diagnostic | The FOMC set-piece ships |

**N-l is a staffing constraint on the above, not a test:** N-2 is not scored by whoever wrote the template pack. Settle it while the editorial role is still being filled.

**N-q and N-v are diagnostics on the generator, not on narration.** They belong in the horizon-stratified battery (DN-1 II.6), which means they touch the sealed Step-2 apparatus and need Quant's sequencing rather than a register entry.

---

## 7. Already ratified on instruction

Recorded in DN-9 §14 and repeated here so the register is the single source.

| # | Decision | Position |
|---|---|---|
| N-ac | Board power | **Soft, with early termination** *(appears in bucket A for formal ratification)* |
| N-af | Rationale field on decision windows | **Proceed.** Task issued |

---

## 8. Still open, and not in any bucket

| Item | Owner | Why it is not a decision |
|---|---|---|
| **Template-pack ownership** | You | A hiring or contracting question. The likeliest cause of an M4 slip, and invisible in a build review |
| **Independent read of DN-9** | Reviewer | Four defects found by looking; the base rate argues for more |
| N-aj ⛔ | Product + Quant | Peer-survey cohort snapshots — a *defect* to be fixed, not an option to be chosen |

---

## 9. What to actually do

1. **One hour**: ratify the nine in §2. Six have recommendations you have already effectively endorsed.
2. **Ten minutes**: adopt the five in §3 by fiat and log them.
3. **One email**: batch the three ⚖ items to Counsel.
4. **Hand bucket B to the workbench.** Its `UNRESOLVED.md` is a better list than a session would produce, because it is discovered by building.
5. **Give bucket E to Quant with the sealing requirement stated**, not as a to-do list.

---

*Amends the documentation register. Companion to DN-9 v1.2. Not investment advice.*
