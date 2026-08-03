"""The was-it-a-good-call metric (wp5-03) -- an explicit computation.

The counterfactual scoring that gives the platform its name: *given what was
known then, across the paths that could have followed, was that decision
good?* Formally, with a re-cone ensemble ``C`` from decision window ``w``
(:func:`ah.gen.recone.recone` -- the conditional distribution of continuations
given everything observed through ``w``) and an evaluation functional ``V``
mapping (action, continuation path) to an outcome scalar:

    delta_k       = V(action, C.path_k) - V(baseline, C.path_k)
    good_call     = mean_k(delta_k)
    win_rate      = mean_k(1[delta_k > 0])
    quantiles     = empirical q05/q25/q50/q75/q95 of delta

PAIRED differences on the SAME continuation path -- the design advantage
DN-6 SS4.1 names (the counterfactual is evaluated under identical residual
randomness, so the difference isolates the decision) -- and the baseline is
the caller's twin policy (DN-5's ratified counterfactual: the policy twin;
``hold-course`` where the port twin is not in play). The evaluation functional
is SUPPLIED, not owned here: the tournament and density studies (wp5-04/05)
plug their own institutional evaluation; the tests pin the arithmetic with
transparent functionals and a worked example.

Sign convention: positive ``good_call`` means the action beat the baseline in
conditional expectation. ``NaN`` deltas are refused loudly (an evaluation that
cannot score a path is a bug in the functional, not a datum).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from ah.gen.base import Ensemble

__all__ = ["CounterfactualError", "CounterfactualScore", "score_decision"]

#: Version stamp for the metric definition; consumed by RunRecord-adjacent
#: reporting exactly as decision_alpha_version is (retrofit R-1's convention).
COUNTERFACTUAL_METRIC_VERSION = "1.0"

EvaluateFn = Callable[[np.ndarray], float]
"""Maps ONE continuation path ``(months, n_factors)`` to an outcome scalar,
with the action (or baseline policy) already bound in by the caller --
functools.partial or a closure; the metric never introspects the policy."""


class CounterfactualError(RuntimeError):
    """A cone or evaluation the metric refuses to average over."""


@dataclass(frozen=True)
class CounterfactualScore:
    """The explicit computation's result, self-describing.

    ``deltas`` is kept whole (n_paths of them): wp5-05 attributes dispersion
    by window and needs the distribution, not just its mean.
    """

    good_call: float
    win_rate: float
    q05: float
    q25: float
    q50: float
    q75: float
    q95: float
    n_paths: int
    at_month: int
    metric_version: str
    deltas: np.ndarray
    cone_meta: dict[str, Any]


def score_decision(
    cone: Ensemble,
    evaluate_action: EvaluateFn,
    evaluate_baseline: EvaluateFn,
) -> CounterfactualScore:
    """Score one decision against its baseline over a re-cone ensemble.

    ``cone`` must be a re-cone result (its meta carries the ``recone`` block;
    scoring an UNCONDITIONAL ensemble here would answer "is the action good in
    general", not "was it good GIVEN what was known then" -- refused, since the
    difference is the entire point of the metric).
    """
    recone_meta = cone.meta.conditioning.get("recone")
    if not recone_meta:
        raise CounterfactualError(
            "score_decision needs a re-cone ensemble (meta.conditioning['recone']); "
            "an unconditional ensemble answers a different question"
        )
    if cone.n_paths < 2:
        raise CounterfactualError(f"a cone of {cone.n_paths} path(s) has no distribution")

    deltas = np.empty(cone.n_paths, dtype=np.float64)
    for k in range(cone.n_paths):
        path = np.asarray(cone.paths[k], dtype=np.float64)
        a = float(evaluate_action(path))
        b = float(evaluate_baseline(path))
        deltas[k] = a - b
    if not np.all(np.isfinite(deltas)):
        bad = int(np.flatnonzero(~np.isfinite(deltas))[0])
        raise CounterfactualError(
            f"evaluation produced a non-finite delta at cone path {bad}; an evaluation "
            "functional that cannot score a path is a bug, not a datum"
        )

    q05, q25, q50, q75, q95 = (float(np.percentile(deltas, q)) for q in (5, 25, 50, 75, 95))
    return CounterfactualScore(
        good_call=float(deltas.mean()),
        win_rate=float(np.mean(deltas > 0.0)),
        q05=q05,
        q25=q25,
        q50=q50,
        q75=q75,
        q95=q95,
        n_paths=int(cone.n_paths),
        at_month=int(recone_meta["at_month"]),
        metric_version=COUNTERFACTUAL_METRIC_VERSION,
        deltas=deltas,
        cone_meta=dict(recone_meta),
    )
