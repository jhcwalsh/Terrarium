"""The utility tier: discriminative score, predictive score, TSTR degradation (WP2.2 Task 4).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``utility.py`` bullet: "discriminative score,
predictive score, TSTR degradation." All three are tier ``"monthly"`` (the brief's
explicit statement), and all three compare the GENERATED ensemble against **real
train+validation data** -- never a fresh catalog read, and never the touch-once
holdout.

Where the real data comes from, and the leakage guard
--------------------------------------------------------
Every real value this suite reads comes from
:attr:`~ah.eval.reference.ReferenceStats.historical_series` -- the SAME per-factor,
train+validation-only series :mod:`ah.eval.reference` already builds internally
(``series_by_factor``) and now exposes, so this suite reads through the identical
sanctioned surface :mod:`ah.eval.reference` and :mod:`ah.eval.metrics.tails` use,
never a second, independent catalog read. This module holds no
:class:`~ah.splits.FinalEvaluationToken` and never imports :mod:`ah.eval.g2` --
``tests/test_utility.py``'s
``test_utility_module_never_imports_g2_or_names_the_token`` is the AST guard proof, in
the style of ``tests/test_reference.py``'s.

Determinism, and why the seed is a module constant, not the battery's run seed
-----------------------------------------------------------------------------
Every fit in this module is a real (if deliberately simple) model fit, so
determinism is load-bearing, not incidental: every stochastic step -- which examples
land in a train/test split, which generated pairs are subsampled to fit a TSTR model
-- flows from a single ``numpy.random.Generator(PCG64(seed))``, never a global RNG,
never ``random``. :data:`UTILITY_FIT_SEED` is a SEALED MODULE CONSTANT, not the
battery's own ``seed`` parameter (:class:`~ah.eval.battery.MetricFn` is a one-argument
``Callable[[Ensemble], float]`` with no seed parameter at all -- the same signature
constraint every other metric suite's closures satisfy) -- so re-running the battery
at a different run seed (which only drives :func:`~ah.eval.battery.mc_error`'s
subsampling) reports a bit-identical utility-tier value for an unchanged ensemble.
``tests/test_utility.py`` asserts both directions directly on the module-level
functions: identical ``seed`` gives a bit-identical score, and a different ``seed``
gives a different one (so the first assertion is not vacuous).

Three metrics, one small shared model-fitting core
------------------------------------------------------
:func:`_fit_gd` is deterministic, ordinary (full-batch) gradient descent for a linear
model with a bias term -- ``loss="logistic"`` (binary cross-entropy, sigmoid output)
for :func:`discriminative_score`, ``loss="squared"`` (ordinary linear regression) for
:func:`predictive_score`/:func:`tstr_degradation`. Fixed, sealed hyperparameters
(:data:`_GD_EPOCHS`, :data:`_GD_LEARNING_RATE`, :data:`_GD_L2`); zero weight
initialization (deterministic, and correct for a convex loss -- no random init is
needed). All randomness in this module lives OUTSIDE :func:`_fit_gd`, in which
examples are selected/split before fitting -- :func:`_fit_gd` itself is a pure,
seed-free function of its ``(X, y)`` inputs, which is what makes "identical seed ->
identical selection -> identical fit -> bit-identical score" true by construction
rather than something that has to be checked layer by layer.

No sklearn, no scipy -- CLAUDE.md's dependency rule; both the classifier and the
regressor are ~20 lines of numpy each.

- :func:`discriminative_score` -- ``|balanced test accuracy - 0.5|`` of a
  logistic-regression classifier trained to distinguish [mean, std] window features of
  real vs. generated factor dynamics. 0 = indistinguishable; lower is better. Balanced,
  not raw, accuracy: the two sides differ in size by ~100:1 at production scale, and
  raw accuracy under that imbalance measures the class ratio rather than the
  generator -- see that function for the full statement.
- :func:`predictive_score` -- train-on-synthetic, test-on-real (TSTR) one-step-ahead
  mean squared error of a linear ``x_{t+1} = a + b*x_t`` model.
- :func:`tstr_degradation` -- ``MSE_tstr / MSE_trtr`` (:func:`predictive_score`'s error
  divided by a train-on-real-test-on-real baseline fit the same way). ``>= 1.0`` is the
  expected direction (synthetic-trained is no better than real-trained); lower is
  better; ``< 1.0`` is possible and not an error (see the function's own docstring).

Every exact functional form, hyperparameter, and orientation is restated in
``pre-registration.yaml``'s ``discriminative_score_estimator`` /
``predictive_score_estimator`` / ``tstr_degradation_estimator`` blocks -- this module
implements those definitions, it does not define them a second, independent way.

Registration is deferred, exactly as every other reference-dependent suite
-------------------------------------------------------------------------------
This suite needs a computed :class:`~ah.eval.reference.ReferenceStats` (for
``historical_series``) and a :class:`~ah.factors.FactorManifest` (for the shared
active-factor axis), so it registers through :func:`build_utility_suite` /
:func:`register_utility_suite` rather than as an import-time side effect.
``ah.eval.battery.run_full_battery`` is the production caller, via
``battery._REFERENCE_DEPENDENT_SUITE_BUILDERS``'s ``"utility"`` row.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

from ah.eval.battery import MetricFn, MetricSpec, register_suite
from ah.eval.reference import ReferenceStats
from ah.factors import FactorManifest
from ah.gen.base import Ensemble

SUITE = "utility"
TIER = "monthly"

# Non-overlapping window length (months) for discriminative_score's [mean, std]
# features -- long enough to carry real dynamics (two years), short enough that even a
# 60-month production path contributes more than one window.
UTILITY_WINDOW_MONTHS = 24

# Gradient-descent hyperparameters, shared by every fit in this module (logistic for
# discriminative_score, squared-error for predictive_score/tstr_degradation). Sealed,
# fixed constants -- not tuned per call -- so a fit is reconstructible from
# pre-registration.yaml alone.
#
# WP2.2 Task 4 fix pass (Important 7): the fit previously ran a FIXED 200 epochs at
# lr=0.1 with nothing checking or stating convergence. For the squared loss, gradient
# descent diverges whenever `lr > 2 / lambda_max(X^T X / n + lambda I)`; the predictive
# design matrix is z-scored by the REAL mean/std, so a generated ensemble with ~4.5x
# real volatility pushes lambda_max past 20 and the fit blew up to inf/nan. The failure
# direction was safe (it fails the gate) but the metric stopped being a MEASUREMENT.
# Two changes, both stated in pre-registration.yaml's estimator blocks:
#   * the step is `min(_GD_LEARNING_RATE, 1 / L)` with `L` a cheap upper bound on the
#     loss's gradient-Lipschitz constant computed from the actual design (below), so
#     the iteration is provably non-divergent at ANY input scale, and is unchanged at
#     `_GD_LEARNING_RATE` for the well-scaled designs this suite normally builds; and
#   * the loop stops on a GRADIENT-NORM criterion rather than an epoch count, with
#     `_GD_MAX_EPOCHS` only as a bound on work.
_GD_LEARNING_RATE = 0.1
_GD_L2 = 1e-3
_GD_MAX_EPOCHS = 5000
_GD_GRAD_TOL = 1e-10

# The seed EVERY stochastic step in this suite's ensemble-level wiring uses -- see the
# module docstring's "Determinism" section for why this is a sealed constant and not
# the battery's own run seed.
UTILITY_FIT_SEED = 20260125

_DISCRIMINATIVE_TRAIN_FRACTION = 0.7
_PREDICTIVE_SUBSAMPLE_FRACTION = 0.5
_TRTR_SPLIT_FRACTION = 0.5

__all__ = [
    "SUITE",
    "TIER",
    "UTILITY_FIT_SEED",
    "UTILITY_WINDOW_MONTHS",
    "build_utility_suite",
    "discriminative_score",
    "predictive_score",
    "register_utility_suite",
    "tstr_degradation",
]


# --------------------------------------------------------------------------- #
# shared gradient-descent core
# --------------------------------------------------------------------------- #


def _sigmoid(z: np.ndarray) -> np.ndarray:
    # Numerically stable: clip to keep exp() finite either side (never NaN/inf).
    z = np.clip(z, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-z))


def _fit_gd(
    X: np.ndarray,
    y: np.ndarray,
    *,
    loss: str,
    sample_weight: np.ndarray | None = None,
    max_epochs: int = _GD_MAX_EPOCHS,
) -> np.ndarray:
    """Deterministic full-batch gradient descent for a linear model with a bias term.

    ``X`` is ``(n, d)``; a column of ones is appended internally as the bias feature,
    so the returned weight vector is ``(d + 1,)`` with the bias LAST. Zero
    initialization (the convex losses used here need no random start). ``loss``:
    ``"logistic"`` (sigmoid output, binary cross-entropy gradient) or ``"squared"``
    (identity output, linear-regression gradient) -- both use the same
    ``gradient = X^T W (pred - y) / sum(W) + L2 * w`` form (L2 applied to every weight
    including the bias -- a stated simplification, not excluding the bias from the
    penalty the way some conventions do).

    ``sample_weight`` is a non-negative ``(n,)`` vector of per-example weights,
    defaulting to all-ones. :func:`discriminative_score` uses it to weight each class by
    the inverse of its own size, which is what stops a 100:1 majority class from simply
    owning the fit (see that function).

    **Step size and stopping criterion** (WP2.2 Task 4 fix pass, Important 7 -- the fit
    previously had neither, and diverged to inf/nan on a badly scaled design):

    - the step is ``min(_GD_LEARNING_RATE, 1 / L)``, where ``L = c * lambda_max_bound +
      _GD_L2`` bounds the loss's gradient-Lipschitz constant, ``c = 1`` for the squared
      loss and ``c = 0.25`` for the logistic (the maximum of the sigmoid's derivative),
      and ``lambda_max_bound = trace(design^T W design) / sum(W)`` is the cheap trace
      bound on the weighted second-moment matrix's largest eigenvalue. Gradient descent
      on an ``L``-smooth convex objective is monotonically non-increasing for any step
      ``<= 1/L``, so this is provably non-divergent at ANY input scale. On a z-scored
      2-feature design ``L`` is ~2, so the cap binds and the step stays at
      :data:`_GD_LEARNING_RATE` -- the ordinary case is unchanged.
    - the loop stops when the gradient's infinity norm falls below
      :data:`_GD_GRAD_TOL`, with ``max_epochs`` only as a bound on work. A converged fit
      is therefore invariant to the epoch budget, which is what makes the returned value
      a property of ``(X, y, loss, sample_weight)`` rather than of the schedule.

    Pure and seed-free: every call with the same inputs returns the bit-identical
    weights -- see the module docstring for why all randomness in this suite lives
    outside this function.
    """
    if loss not in ("logistic", "squared"):
        raise ValueError(f"_fit_gd: loss must be 'logistic' or 'squared', got {loss!r}")
    n, d = X.shape
    design = np.hstack([X, np.ones((n, 1), dtype=np.float64)])
    if sample_weight is None:
        w = np.ones(n, dtype=np.float64)
    else:
        w = np.asarray(sample_weight, dtype=np.float64).reshape(-1)
        if w.shape[0] != n or np.any(w < 0.0):
            raise ValueError("_fit_gd: sample_weight must be non-negative with one entry per row")
    w_total = float(np.sum(w))
    if w_total <= 0.0:
        raise ValueError("_fit_gd: sample_weight must not sum to zero")

    curvature = 1.0 if loss == "squared" else 0.25
    lambda_max_bound = float(np.sum(w[:, np.newaxis] * design * design)) / w_total
    lipschitz = curvature * lambda_max_bound + _GD_L2
    step = min(_GD_LEARNING_RATE, 1.0 / lipschitz) if lipschitz > 0.0 else _GD_LEARNING_RATE

    weights = np.zeros(d + 1, dtype=np.float64)
    for _ in range(max_epochs):
        z = design @ weights
        pred = _sigmoid(z) if loss == "logistic" else z
        gradient = design.T @ (w * (pred - y)) / w_total + _GD_L2 * weights
        if float(np.max(np.abs(gradient))) < _GD_GRAD_TOL:
            break
        weights = weights - step * gradient
    return weights


def _apply_linear(X: np.ndarray, weights: np.ndarray) -> np.ndarray:
    n = X.shape[0]
    design = np.hstack([X, np.ones((n, 1), dtype=np.float64)])
    return design @ weights


# --------------------------------------------------------------------------- #
# discriminative_score
# --------------------------------------------------------------------------- #


def discriminative_score(
    real_features: np.ndarray,
    generated_features: np.ndarray,
    *,
    seed: int,
    train_fraction: float = _DISCRIMINATIVE_TRAIN_FRACTION,
) -> float:
    """``|balanced test-set accuracy - 0.5|`` of a logistic real-vs-generated classifier.

    ``real_features``/``generated_features`` are ``(n, d)`` feature matrices over the
    SAME ``d`` features (this suite's ensemble-level wiring uses ``d=2``, ``[mean,
    std]`` per window -- see :func:`build_utility_suite`). Labels: real=1, generated=0.

    **Class imbalance, and why this metric is defined the way it is** (WP2.2 Task 4 fix
    pass, Critical 2). The two sides are NOT the same size and never will be: real
    windows number ``history_months / 24`` per factor while generated windows number
    ``(months / 24) * n_paths``, roughly 100:1 at production scale. The first
    implementation pooled them into one unbalanced set, split it at random and reported
    ``|raw accuracy - 0.5|``. Raw accuracy under 100:1 imbalance is maximized by the
    constant majority-class predictor at 0.99, so the reported score sat near its 0.5
    maximum no matter what the generator did -- measured with the two distributions held
    IDENTICAL: 0.008 at a 1:1 ratio, 0.333 at 5:1, 0.447 at 20:1, 0.493 at 150:1. Worse,
    the score IMPROVED as the ensemble shrank toward balance: another metric a generator
    could game by producing less. Three changes fix it, and all three are necessary:

    1. **class-stratified split** -- ``train_fraction`` of EACH class goes to train, so
       the test split always contains both classes and the split ratio cannot itself
       become a source of imbalance;
    2. **inverse-class-frequency sample weights** in the fit, so the majority class does
       not simply own the logistic objective (see :func:`_fit_gd`'s ``sample_weight``);
    3. **balanced accuracy** as the report -- ``0.5 * (recall_real + recall_generated)``,
       the unweighted mean of the two per-class recalls, whose value for ANY constant
       predictor is exactly 0.5 whatever the class ratio.

    The reported value is ``|balanced_accuracy - 0.5|``, in ``[0, 0.5]``: 0 =
    indistinguishable (the generator fools the classifier); higher = more detectably
    different. **Lower is better** as a G2 criterion.

    Feature standardization is z-score by the TRAIN split's own mean/std only (never the
    test split's -- a leakage channel in the feature scaling itself, distinct from but
    analogous to the platform's train+validation/holdout leakage guard).

    ``NaN`` if fewer than 4 pooled examples, or if either class has fewer than 2
    examples (a stratified split needs one of each class to fit on and one to score on;
    with fewer, balanced accuracy is undefined rather than merely noisy).
    """
    real = np.asarray(real_features, dtype=np.float64)
    generated = np.asarray(generated_features, dtype=np.float64)
    if real.ndim != 2 or generated.ndim != 2 or real.shape[1] != generated.shape[1]:
        raise ValueError(
            "discriminative_score: real_features and generated_features must be 2-D "
            "with the same number of columns"
        )
    X = np.vstack([real, generated])
    y = np.concatenate([np.ones(real.shape[0]), np.zeros(generated.shape[0])])
    n = X.shape[0]
    if n < 4:
        return float("nan")

    rng = np.random.Generator(np.random.PCG64(seed))
    train_parts: list[np.ndarray] = []
    test_parts: list[np.ndarray] = []
    # Class order is fixed (real, then generated) so the RNG draw sequence -- and hence
    # the split -- is a deterministic function of the seed, not of dict/set iteration.
    for label in (1.0, 0.0):
        members = np.flatnonzero(y == label)
        if members.size < 2:
            return float("nan")
        shuffled = members[rng.permutation(members.size)]
        n_train = min(max(1, round(train_fraction * members.size)), members.size - 1)
        train_parts.append(shuffled[:n_train])
        test_parts.append(shuffled[n_train:])
    train_idx = np.concatenate(train_parts)
    test_idx = np.concatenate(test_parts)

    X_train, y_train = X[train_idx], y[train_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0)
    std_safe = np.where(std > 0.0, std, 1.0)
    X_train_std = (X_train - mean) / std_safe
    X_test_std = (X_test - mean) / std_safe

    # Inverse class frequency, normalized so the two classes contribute equally to the
    # objective regardless of their sizes.
    class_weight = {label: 0.5 / float(np.sum(y_train == label)) for label in (1.0, 0.0)}
    sample_weight = np.array([class_weight[float(label)] for label in y_train], dtype=np.float64)

    weights = _fit_gd(X_train_std, y_train, loss="logistic", sample_weight=sample_weight)
    probs = _sigmoid(_apply_linear(X_test_std, weights))
    preds = (probs >= 0.5).astype(np.float64)
    recalls = [float(np.mean(preds[y_test == label] == label)) for label in (1.0, 0.0)]
    balanced_accuracy = float(np.mean(recalls))
    return abs(balanced_accuracy - 0.5)


# --------------------------------------------------------------------------- #
# predictive_score / tstr_degradation
# --------------------------------------------------------------------------- #


def predictive_score(
    generated_x: np.ndarray,
    generated_y: np.ndarray,
    real_x: np.ndarray,
    real_y: np.ndarray,
    *,
    seed: int,
    subsample_fraction: float = _PREDICTIVE_SUBSAMPLE_FRACTION,
) -> float:
    """Train-on-synthetic, test-on-real (TSTR) one-step-ahead mean squared error.

    ``generated_x``/``generated_y`` and ``real_x``/``real_y`` are 1-D arrays of
    ``(x_t, x_{t+1})`` one-step-ahead pairs (this suite's wiring pools them across
    every shared active factor, standardized per factor -- see
    :func:`build_utility_suite`). A linear model ``x_{t+1} = a + b*x_t`` is fit
    (:func:`_fit_gd`, ``loss="squared"``) on a SEEDED random ``subsample_fraction``
    (without replacement, via ``numpy.random.Generator(PCG64(seed))``) of the
    GENERATED pairs, then evaluated (mean squared error) on EVERY real pair -- no
    subsampling on the real/test side. ``NaN`` if fewer than 2 generated pairs or no
    real pairs at all.
    """
    gx = np.asarray(generated_x, dtype=np.float64).reshape(-1, 1)
    gy = np.asarray(generated_y, dtype=np.float64).reshape(-1)
    rx = np.asarray(real_x, dtype=np.float64).reshape(-1, 1)
    ry = np.asarray(real_y, dtype=np.float64).reshape(-1)
    n = gx.shape[0]
    if n < 2 or rx.shape[0] < 1:
        return float("nan")

    rng = np.random.Generator(np.random.PCG64(seed))
    n_sub = min(max(2, round(subsample_fraction * n)), n)
    idx = rng.choice(n, size=n_sub, replace=False)

    weights = _fit_gd(gx[idx], gy[idx], loss="squared")
    predicted = _apply_linear(rx, weights)
    return float(np.mean((ry - predicted) ** 2))


def tstr_degradation(
    generated_x: np.ndarray,
    generated_y: np.ndarray,
    real_x: np.ndarray,
    real_y: np.ndarray,
    *,
    seed: int,
    subsample_fraction: float = _PREDICTIVE_SUBSAMPLE_FRACTION,
    split_fraction: float = _TRTR_SPLIT_FRACTION,
) -> float:
    """``MSE_tstr / MSE_trtr`` -- :func:`predictive_score` divided by a
    train-on-real-test-on-real (TRTR) baseline fit the same way.

    ``MSE_tstr`` is :func:`predictive_score` on the same inputs and ``seed``.
    ``MSE_trtr`` fits the identical linear model on a SEEDED random ``split_fraction``
    half of the REAL pairs and evaluates mean squared error on the other half. The
    two draws come from two independently constructed
    ``numpy.random.Generator(PCG64(seed))`` instances seeded identically -- NOT from one
    shared generator advanced twice, so they are the same draw sequence rather than two
    successive ones. Fully deterministic either way; the distinction is stated because
    the earlier wording claimed a shared draw, which is not what the code does.

    **Orientation**: ``>= 1.0`` is the expected direction -- the synthetic-trained
    model predicts real one-step-ahead dynamics no better than a model trained
    directly on (half of) real data; ``1.0`` is "no degradation". **Lower is better**
    as a G2 criterion. A value ``< 1.0`` is POSSIBLE and not an error: it would mean
    the generator's larger effective fitting sample outweighs the sim-to-real gap for
    this intentionally simple two-parameter predictor -- a real, reportable outcome,
    not a bug to be clamped away.

    ``NaN`` if ``MSE_tstr`` is NaN, if fewer than 4 real pairs are available, or if
    the resulting real train/eval split is degenerate. ``+inf`` if ``MSE_trtr`` is
    exactly ``0.0`` (a degenerate constant real series with no ratio informative
    against it).
    """
    mse_tstr = predictive_score(
        generated_x, generated_y, real_x, real_y, seed=seed, subsample_fraction=subsample_fraction
    )
    if math.isnan(mse_tstr):
        return float("nan")

    rx = np.asarray(real_x, dtype=np.float64).reshape(-1, 1)
    ry = np.asarray(real_y, dtype=np.float64).reshape(-1)
    n = rx.shape[0]
    if n < 4:
        return float("nan")

    rng = np.random.Generator(np.random.PCG64(seed))
    order = rng.permutation(n)
    n_fit = min(max(2, round(split_fraction * n)), n - 2)
    if n_fit < 2:
        return float("nan")
    fit_idx, eval_idx = order[:n_fit], order[n_fit:]
    if eval_idx.size == 0:
        return float("nan")

    weights = _fit_gd(rx[fit_idx], ry[fit_idx], loss="squared")
    predicted = _apply_linear(rx[eval_idx], weights)
    mse_trtr = float(np.mean((ry[eval_idx] - predicted) ** 2))
    if mse_trtr == 0.0:
        return float("inf")
    return mse_tstr / mse_trtr


# --------------------------------------------------------------------------- #
# ensemble-level wiring: windows, one-step pairs, the shared active-factor axis
# --------------------------------------------------------------------------- #


def _shared_factors(
    manifest: FactorManifest, reference: ReferenceStats, ensemble: Ensemble
) -> list[str]:
    """Active factors present in BOTH the real historical series and this ensemble.

    Neither side is padded or substituted for the other -- a factor absent from
    either side (e.g. ``commodities``, declared unavailable) is simply excluded from
    the pooled comparison, exactly as ``ah.eval.metrics.monthly``'s per-factor NaN
    guard excludes an absent factor from a single-factor metric.
    """
    return [
        f
        for f in manifest.active_factors()
        if f in reference.historical_series and f in ensemble.factor_names
    ]


def _window_features(x: np.ndarray, window: int) -> np.ndarray:
    """Non-overlapping ``[mean, std]`` features over ``window``-length blocks of ``x``
    (the partial tail dropped) -- the same non-overlapping, partial-tail-dropped
    windowing convention ``ah.eval.reference.nonoverlapping_sums`` already uses."""
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    usable = (x.shape[0] // window) * window
    if usable == 0:
        return np.empty((0, 2), dtype=np.float64)
    blocks = x[:usable].reshape(-1, window)
    return np.stack([blocks.mean(axis=1), blocks.std(axis=1)], axis=1)


def _real_window_features(series: pd.Series) -> np.ndarray:
    return _window_features(series.to_numpy(dtype=np.float64), UTILITY_WINDOW_MONTHS)


def _generated_window_features(ensemble: Ensemble, factor: str) -> np.ndarray:
    """Windows extracted independently WITHIN each path (never spanning a path
    boundary), pooled by concatenation -- the identical convention
    ``ah.eval.metrics.horizon``'s pooled drawdown/decade-window helpers use."""
    slab = ensemble.factor(factor).astype(np.float64)
    parts = [_window_features(slab[i], UTILITY_WINDOW_MONTHS) for i in range(slab.shape[0])]
    non_empty = [p for p in parts if p.shape[0] > 0]
    if not non_empty:
        return np.empty((0, 2), dtype=np.float64)
    return np.concatenate(non_empty, axis=0)


def _concat_or_empty(parts: Sequence[np.ndarray], width: int) -> np.ndarray:
    non_empty = [p for p in parts if p.shape[0] > 0]
    if not non_empty:
        return np.empty((0, width), dtype=np.float64)
    return np.concatenate(non_empty, axis=0)


def _factor_mean_std(series: pd.Series) -> tuple[float, float]:
    values = series.to_numpy(dtype=np.float64)
    if values.size == 0:
        return 0.0, 1.0
    mean = float(np.mean(values))
    std = float(np.std(values))
    return mean, (std if std > 0.0 else 1.0)


def _real_one_step_pairs(
    series: pd.Series, mean: float, std: float
) -> tuple[np.ndarray, np.ndarray]:
    values = (series.to_numpy(dtype=np.float64) - mean) / std
    if values.shape[0] < 2:
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
    return values[:-1], values[1:]


def _generated_one_step_pairs(
    ensemble: Ensemble, factor: str, mean: float, std: float
) -> tuple[np.ndarray, np.ndarray]:
    """One-step-ahead pairs extracted independently WITHIN each path (never spanning a
    path boundary), pooled by concatenation."""
    slab = (ensemble.factor(factor).astype(np.float64) - mean) / std
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for i in range(slab.shape[0]):
        row = slab[i]
        if row.shape[0] < 2:
            continue
        xs.append(row[:-1])
        ys.append(row[1:])
    if not xs:
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
    return np.concatenate(xs), np.concatenate(ys)


def _predictive_pairs(
    manifest: FactorManifest, reference: ReferenceStats, ensemble: Ensemble
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """Pooled ``(generated_x, generated_y, real_x, real_y)`` one-step-ahead pairs over
    every shared active factor, each factor standardized by ITS OWN real historical
    mean/std before pooling (so one linear model is not dominated by whichever factor
    happens to carry the largest raw scale). ``None`` if no factor contributes pairs
    on both sides.
    """
    gx_parts: list[np.ndarray] = []
    gy_parts: list[np.ndarray] = []
    rx_parts: list[np.ndarray] = []
    ry_parts: list[np.ndarray] = []
    for factor in _shared_factors(manifest, reference, ensemble):
        mean, std = _factor_mean_std(reference.historical_series[factor])
        rx, ry = _real_one_step_pairs(reference.historical_series[factor], mean, std)
        gx, gy = _generated_one_step_pairs(ensemble, factor, mean, std)
        if rx.shape[0] > 0:
            rx_parts.append(rx)
            ry_parts.append(ry)
        if gx.shape[0] > 0:
            gx_parts.append(gx)
            gy_parts.append(gy)
    if not rx_parts or not gx_parts:
        return None
    return (
        np.concatenate(gx_parts),
        np.concatenate(gy_parts),
        np.concatenate(rx_parts),
        np.concatenate(ry_parts),
    )


# --------------------------------------------------------------------------- #
# build_utility_suite / register_utility_suite
# --------------------------------------------------------------------------- #


def _discriminative_score_metric(manifest: FactorManifest, reference: ReferenceStats) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        shared = _shared_factors(manifest, reference, ensemble)
        real = _concat_or_empty(
            [_real_window_features(reference.historical_series[f]) for f in shared], 2
        )
        generated = _concat_or_empty([_generated_window_features(ensemble, f) for f in shared], 2)
        if real.shape[0] == 0 or generated.shape[0] == 0:
            return float("nan")
        return discriminative_score(real, generated, seed=UTILITY_FIT_SEED)

    return fn


def _predictive_score_metric(manifest: FactorManifest, reference: ReferenceStats) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        pairs = _predictive_pairs(manifest, reference, ensemble)
        if pairs is None:
            return float("nan")
        gx, gy, rx, ry = pairs
        return predictive_score(gx, gy, rx, ry, seed=UTILITY_FIT_SEED)

    return fn


def _tstr_degradation_metric(manifest: FactorManifest, reference: ReferenceStats) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        pairs = _predictive_pairs(manifest, reference, ensemble)
        if pairs is None:
            return float("nan")
        gx, gy, rx, ry = pairs
        return tstr_degradation(gx, gy, rx, ry, seed=UTILITY_FIT_SEED)

    return fn


def build_utility_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """The three whole-panel utility-tier :class:`~ah.eval.battery.MetricSpec` entries.

    Whole-panel, not per-factor (see the module docstring): each metric pools every
    active factor present on both the real and generated sides into one comparison,
    matching :data:`~ah.eval.reference.PANEL_STATS`'s bare-name registration for these
    three names.
    """
    return (
        MetricSpec(
            name="discriminative_score",
            tier=TIER,
            fn=_discriminative_score_metric(manifest, reference),
            suite=SUITE,
        ),
        MetricSpec(
            name="predictive_score",
            tier=TIER,
            fn=_predictive_score_metric(manifest, reference),
            suite=SUITE,
        ),
        MetricSpec(
            name="tstr_degradation",
            tier=TIER,
            fn=_tstr_degradation_metric(manifest, reference),
            suite=SUITE,
        ),
    )


def register_utility_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("utility", build_utility_suite(manifest, reference))``."""
    register_suite(SUITE, build_utility_suite(manifest, reference))
