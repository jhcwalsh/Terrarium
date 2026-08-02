# ACTOR-VALIDATION.md — the WP4.9 study, run and deferred honestly

Worlds: 6 synthetic study decades (seeded 1000..),
identical worlds/windows for every arm (the sealed comparison rule).
Ablation arms: heuristic, random_within_bounds, hold_course. Model arm: run asof 2026-08-02, model claude-sonnet-5, 3 personas.

## Action rates by arm (action-level fidelity, base measure)

| arm | acted in fraction of windows |
|---|---|
| heuristic | 0.00 |
| hold_course | 0.00 |
| model:momentum | 0.72 |
| model:preserver | 0.28 |
| model:steady | 0.00 |
| random_within_bounds | 1.00 |

## Effect size WITH dispersion (the anti-inflation rule, mechanical)

heuristic vs hold_course action-rate difference: mean +0.00, sd across worlds 0.00, n=6. No mean travels without its dispersion and world count.

## Model-arm pathologies (measured)

- **Action-level fidelity**: fallback rate 0.20 — fraction of
  committee decisions rejected by the bounded contract and replaced
  by the heuristic, with the rejection filed in the rationale.
- **Persona/prompt sensitivity**: 0.78 of (world, window) cells
  show persona disagreement (differing action counts or targets >1pt
  apart). Reported as PROMPT SENSITIVITY, per the plan's pitfall list
  — persona differences are measured, not sold as insight.

## Deferred, by owner decision D-K4-5 (kickoff, 2026-08-01)

- **The human-cohort arm**: the owner is the first and only test cohort
  when the app exists; external cohorts later. Until it runs, the
  **too-rational pathology is NOT MEASURABLE** — it is defined against
  human cohorts, and no proxy number is published in its place.

## Standing rule (the plan's, restated verbatim in effect)

**No client-facing actor claim precedes this evidence** — and this
study is INCOMPLETE until the human-cohort arm runs. What exists today
supports internal engineering conclusions only.

---

*Not investment advice.*
