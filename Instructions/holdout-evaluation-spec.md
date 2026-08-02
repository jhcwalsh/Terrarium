# Holdout-evaluation specification — APPROVED and SEALED

*APPROVED by the owner 2026-08-02 ('approved - seal the holdout spec');
sealed into the G5 lock by AM-2026-08-02-006 the same day, BEFORE any
campaign-2 promotion seal exists. What S2-HOLDOUT-NOT-SPENT demands before the one shot can ever be fired:
"write the evaluation down first — what is generated, at what size, from
what conditioning state, scored on which metrics against which
realizations, with what consequence — seal that specification BEFORE the
campaign it judges, then mint the token." This draft is that
specification. On owner approval it joins the G5 lock by amendment,
BEFORE the campaign-2 promotion seal. The spend itself remains a separate,
explicit owner act at Step 5's end (KICKOFF-STEP5 §4) — approving this
spec approves the RECIPE, not the firing.*

## What is generated

One ensemble from the **campaign-2 PROMOTED generator** (whatever the
sealed promotion rule selects; if promotion fails, the incumbent
`hier-flow-v1` — the spec does not depend on which model wins):

- `n_paths: 1024` (the sealed S2-ENSEMBLE-SIZE, unchanged)
- horizon: the full holdout span, monthly
- **conditioning state: the world as of 2021-01**, constructed from
  train+validation data ONLY (the L1 posterior and regime state at the
  boundary; nothing later than 2020-12 enters the conditioning)
- seeds: `base_seed 20260000`, single draw — stated now so no seed
  shopping is possible

## What it is scored against

The **realized holdout**: observed factor history 2021-01 to the end of
the campaign-2 vintage (2026-07), read once through the
`FinalEvaluationToken` path, logged.

## The metrics (all sealed already; nothing new invented)

- **Primary: `drawdown_surprise`** (sealed G5 primary) — realized
  holdout max drawdown minus the ensemble's p95 predicted depth.
- Secondary, pre-stated: the Step 2 battery's calibration tier computed
  on ensemble-vs-realized (coverage of the realized path within ensemble
  bands at the sealed quantiles); realized terminal wealth's percentile
  within the ensemble; per-factor sign of mean error. Reported as a
  table, no aggregation into a single verdict number.

## The consequence (pre-stated, both directions)

The result publishes in `RESEARCH-EVIDENCE.md` RQ2 **verbatim whichever
way it falls**:

- Inside the bands: one sentence of support for decade-scale usability,
  with the single-realization caveat stated (n=1 decade; this is
  confirmation, not proof).
- Outside the bands: the divergence is reported as a finding with the
  same caveat, **no retuning, no second draw, no "the market was
  unprecedented" footnote** beyond the numbers themselves.

## What cannot happen

- No component may be tuned, selected, or re-run against the holdout —
  before or after. One generation, one comparison, one table.
- The spec, once sealed, changes only by pre-hoc amendment BEFORE the
  campaign promotion seal; after that it is fixed until spent.

**Decision record:** approved and sealed as above. Changes henceforth
only by pre-hoc amendment BEFORE the campaign promotion seal.

---

*Not investment advice.*
