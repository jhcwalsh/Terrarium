"""The memorization tier: nearest-neighbour distance, membership inference, near-duplicate
fraction (WP2.2 Task 5).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``memorization.py`` bullet. **This suite is what makes
"the generator did not memorize its training data" falsifiable.** WP2.2b's NC4 (a
memorizer that replays training decades with noise) must fail it, so every metric here
is built and tested to genuinely detect copying, in both directions:
``tests/test_memorization.py`` asserts a literal replayer scores
``nn_distance ~ 0``, ``membership_inference_auc ~ 1``, ``near_duplicate_fraction ~ 1``,
and an independent seeded draw scores ``nn_distance`` clearly positive, AUC ~ 0.5,
fraction ~ 0. All three are tier ``"monthly"``.

Memorization is measured against TRAIN, with VALIDATION as the control -- the holdout
is never involved
----------------------------------------------------------------------------------------
Every real value this suite reads comes from
:attr:`~ah.eval.reference.ReferenceStats.historical_series` -- the SAME sanctioned
surface :mod:`ah.eval.metrics.tails`/:mod:`ah.eval.metrics.utility` already read
through, never a fresh catalog read. This module holds no
:class:`~ah.splits.FinalEvaluationToken` and never imports :mod:`ah.eval.g2`
(``tests/test_memorization.py``'s AST guard).

``historical_series`` is already TRAIN+VALIDATION combined (the reference/normalization
surface), and this suite needs the two split apart -- train as the thing to check for
copying, validation as the control the generator never had reason to reproduce. Rather
than threading a live :class:`~ah.splits.DataAccess` through the
``build_<suite>(manifest, reference)`` call shape every other reference-dependent suite
shares (which would be the ONLY suite builder with a different signature, and would
need a change to :func:`ah.eval.battery.register_reference_dependent_suites`, which the
brief for this task asks not to touch), :func:`_train_validation_series` re-partitions
the already-fetched combined series by the SEALED split boundaries
(:data:`ah.splits.TRAIN` / :data:`ah.splits.VALIDATION`) -- the same
``[start, end)`` masking :meth:`ah.splits.DataAccess.frame` itself applies before
``historical_series`` was ever built, so this recovers exactly the rows a second,
fresh split-scoped read would have given, with no second catalog read and no
:class:`~ah.splits.DataAccess` import at all (``tests/test_memorization.py``'s
``test_memorization_module_never_imports_data_access`` is the guard; TRAIN/VALIDATION
are bare date boundaries, not a read capability, so importing them is not a leakage
channel). ``tests/test_memorization.py``'s
``test_train_validation_series_reconstructs_the_original_when_concatenated`` proves the
equivalence directly.

Sequences: a "block", its length, its distance metric, its normalization
------------------------------------------------------------------------------
A "sequence" is a non-overlapping :data:`MEMORIZATION_BLOCK_MONTHS`-month window of ONE
factor's own path (never spanning a path boundary on the generated side, never crossing
the train/validation boundary on the real side), reused at
:data:`~ah.eval.metrics.utility.UTILITY_WINDOW_MONTHS`'s scale (24 months, imported
directly rather than restated) so this suite does not invent a second arbitrary window
length beside the one ``utility.py`` already uses for its own real-vs-generated
windowing. **Pinned, not merely reused (Important 5, WP2.2 Task 5 fix pass):**
``pre-registration.yaml``'s ``memorization_nn_distance_estimator`` states 24 as a
sealed LITERAL, not as "whatever ``utility.py``'s window happens to be" -- so
:data:`MEMORIZATION_BLOCK_MONTHS` is defined as ``UTILITY_WINDOW_MONTHS`` (avoiding a
second hand-restated constant that could drift out of sync with ``utility.py``'s own)
AND asserted equal to 24 at import time. Before this pin, a change to
``UTILITY_WINDOW_MONTHS`` for a purely utility-tier reason would have silently
redefined this suite's sealed 24-month block length with nothing failing -- the
previous test only asserted ``> 1``. The import-time check makes that impossible: any
future change to ``UTILITY_WINDOW_MONTHS`` away from 24 raises immediately, forcing a
deliberate, dated amendment to this module's own constant rather than an accidental,
silent one.

Each block is the RAW (not summarized) 24-dimensional vector of that factor's own
monthly values over the window, **standardized by that factor's own TRAIN mean/std**
(:func:`_standardize`, reusing :func:`ah.eval.metrics.utility._factor_mean_std`'s
convention on the TRAIN split specifically -- train is the reference population this
suite checks copying against, so standardization is anchored there, not on the
train+validation combination). Distance between two blocks of the SAME factor is
Euclidean (:func:`_block_distance`): ``d(u, v) = sqrt(sum((u_i - v_i)^2))`` over the
standardized, flattened 24-vector -- the plain, scale-free reading of "how far apart do
two trajectories of the same shape-normalized factor look", needing no further
normalization because the standardization already put every factor on a common scale.
Blocks of DIFFERENT factors are never compared to each other (comparing an equity
return block to a rate-level block, even standardized, compares two different kinds of
dynamics) -- every distance in this module is within one factor, and results are pooled
across factors only at the level of a computed distance (or PIT-style rank), never a
raw value.

1. ``nn_distance_{p05,p50}``
-----------------------------
For every GENERATED block (non-overlapping 24-month windows, extracted independently
WITHIN each path -- the identical convention
:func:`ah.eval.metrics.utility._generated_window_features` uses), its nearest-neighbour
distance is the minimum :func:`_block_distance` to any TRAIN block of the SAME factor
(:func:`_nearest_neighbor_distance`). Pooled across every generated block of every
qualifying factor (POOLED, not per-path: the whole point is one distribution of
"how close is this generated trajectory to the nearest thing the generator was trained
on", not a per-path average of it), ``nn_distance_p05``/``nn_distance_p50`` are that
pooled distribution's 5th percentile and median. Small values -> generated blocks sit
close to specific training examples; large values -> the generator is not reproducing
individual training trajectories.

2. ``membership_inference_auc``
---------------------------------
A distance-to-nearest-synthetic-sample membership-inference attack (the standard
generative-model privacy audit: a training example that was memorized sits
suspiciously close to the model's own output). For every TRAIN block, its "proximity
signal" is its own nearest-neighbour distance to the GENERATED pooled blocks of the
same factor (note the direction is reversed from metric 1: nearest GENERATED neighbour
of a REAL block, not nearest TRAIN neighbour of a generated block); the identical
signal is computed for every VALIDATION block. The attack classifies "is this a
training block?" by SMALLER distance -> more likely training (if the generator
memorized it, it should sit unusually close to what the generator emits).
``membership_inference_auc`` is the AUC of that classifier, computed as the
Mann-Whitney statistic (:func:`_mann_whitney_auc`) of ``-distance`` for the train
population against ``-distance`` for the validation population -- POOLED across every
qualifying factor (again pooled, not per-path or per-factor-averaged: one attack over
one pooled population of real blocks). ``0.5`` = train and validation blocks are
equally close to the generator's output (no detectable leakage); ``1.0`` = train blocks
are systematically much closer than validation blocks (the generator's output betrays
which examples it trained on).

3. ``near_duplicate_fraction``
---------------------------------
The fraction of GENERATED blocks whose nearest-neighbour distance to a TRAIN block
(the SAME quantity metric 1 pools) falls below a data-driven epsilon
(:func:`_leave_one_out_epsilon`): the :data:`MEMORIZATION_EPSILON_PERCENTILE`
(5th) percentile of TRAIN's own LEAVE-ONE-OUT nearest-neighbour distance (every train
block of a factor against every OTHER train block of the same factor). **Why this
choice of epsilon, not an arbitrary constant**: it self-calibrates to how close two
genuinely INDEPENDENT historical trajectories of the same factor ever naturally sit --
epsilon is set to the tightest 5% of that self-similarity distribution, so only a
generated block sitting closer to some training example than all but the closest 5% of
DISTINCT historical examples ever sit to each other counts as a "near duplicate". A
generic historical regime match (two different decades that happen to look similar) is
not, by construction, within this epsilon; a genuine near-verbatim reproduction is.
POOLED (not per-path) across every qualifying factor's generated blocks.

Two anti-gaming floors: :data:`MEMORIZATION_MIN_TRAIN_BLOCKS`
------------------------------------------------------------------
A factor whose TRAIN split carries fewer than :data:`MEMORIZATION_MIN_TRAIN_BLOCKS`
(5) non-overlapping 24-month blocks contributes NOTHING to any of the three metrics --
a leave-one-out epsilon (which itself needs at least 2 blocks to be defined at all) and
a nearest-neighbour search over a literal handful of candidates measure noise, not
memorization. If NO factor clears the floor, all four metric names are NaN (never a
favourable 0/0.5/0 computed from too little -- THE ONE NaN RULE, and the same
"generating less must not improve the metric" discipline every other WP2.2 suite
states).

A third anti-gaming floor: :data:`MEMORIZATION_MIN_GENERATED_BLOCKS` (Important 3,
WP2.2 Task 5 fix pass)
--------------------------------------------------------------------------------------
The floor above guards only the TRAIN side; every sibling suite that pools an
ensemble-side sample also floors the GENERATED side (``ah.eval.metrics.economics``'s
:data:`~ah.eval.metrics.economics.ECONOMICS_MIN_OBS`,
``ah.eval.metrics.calibration``'s
:data:`~ah.eval.metrics.calibration.CALIBRATION_MIN_GENERATED_SUMS`), and before this
fix pass this suite did not. A one-path, 24-month ensemble yields exactly ONE generated
block, at which point ``nn_distance_p05``/``nn_distance_p50`` are literally one
observation (a percentile of a singleton is that singleton, not a distribution) and
``membership_inference_auc`` drifts toward its FAVOURABLE 0.5 value purely because the
generator produced almost nothing to attack, not because it is genuinely
non-memorizing -- "the generator produces less" reading as a better score, the
identical failure mode every other floor in this platform exists to close.
:data:`MEMORIZATION_MIN_GENERATED_BLOCKS` (30, matching
:data:`~ah.eval.metrics.calibration.CALIBRATION_MIN_GENERATED_SUMS`'s floor on a pooled
generated sample of comparable shape) is the TOTAL pooled generated-block count across
every qualifying factor; below it, ALL FOUR metric names are NaN (poisons the whole
suite, not a per-metric partial NaN, matching :data:`MEMORIZATION_MIN_TRAIN_BLOCKS`'s
own all-or-nothing shape) -- see :func:`_pooled_memorization_signals`.
``tests/test_memorization.py``'s
``test_memorization_nan_when_generated_side_is_too_small_even_with_ample_train`` is the
deliverable: TRAIN clears its own floor easily while the generated side is starved, and
the suite must NaN rather than report a favourable degenerate number.

Registration is deferred, exactly as every other reference-dependent suite
-------------------------------------------------------------------------------
Needs a computed :class:`~ah.eval.reference.ReferenceStats` (for ``historical_series``)
and a :class:`~ah.factors.FactorManifest` (for the shared active-factor axis), so it
registers through :func:`build_memorization_suite` / :func:`register_memorization_suite`
rather than as an import-time side effect. ``ah.eval.battery.run_full_battery`` is the
production caller, via ``battery._REFERENCE_DEPENDENT_SUITE_BUILDERS``'s
``"memorization"`` row.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable

import numpy as np
import pandas as pd

from ah.eval.battery import MetricFn, MetricSpec, register_suite
from ah.eval.metrics.utility import UTILITY_WINDOW_MONTHS
from ah.eval.reference import ReferenceStats
from ah.eval.reference import _rank as reference_rank
from ah.factors import FactorManifest
from ah.gen.base import Ensemble
from ah.splits import TRAIN, VALIDATION

SUITE = "memorization"
TIER = "monthly"

# Reused from ah.eval.metrics.utility rather than restated -- see the module docstring's
# "Sequences" section. Aliased under this module's own name so a reader of a block
# definition below can see the scale without leaving the file.
MEMORIZATION_BLOCK_MONTHS = UTILITY_WINDOW_MONTHS

# Important 5, WP2.2 Task 5 fix pass -- see the module docstring's "Pinned, not merely
# reused" paragraph. pre-registration.yaml's memorization_nn_distance_estimator states
# 24 as a sealed literal; this makes a divergence a loud import-time failure instead of
# a silent redefinition of a sealed estimator.
if MEMORIZATION_BLOCK_MONTHS != 24:
    raise AssertionError(
        f"MEMORIZATION_BLOCK_MONTHS = {MEMORIZATION_BLOCK_MONTHS} (from "
        f"UTILITY_WINDOW_MONTHS), but pre-registration.yaml's "
        f"memorization_nn_distance_estimator seals this suite's block length at the "
        f"LITERAL value 24. UTILITY_WINDOW_MONTHS changed for a utility-tier reason "
        f"without anyone deciding whether the sealed memorization estimator should "
        f"change with it -- that decision must be made explicitly (and, once sealed, "
        f"logged as an amendment), not made by accident."
    )

# See the module docstring's "Two anti-gaming floors". 5, not the elsewhere-used 10 or
# 30: a leave-one-out epsilon needs >= 2 blocks to be defined at all (one block to be
# "left out", at least one other to measure distance to), and a nearest-neighbour
# distance itself is meaningful from a single candidate upward -- 5 is a small margin
# above the bare minimum, not a moment-matching floor like AGG_GAUSSIANITY_MIN_SUMS.
MEMORIZATION_MIN_TRAIN_BLOCKS = 5

# Important 3, WP2.2 Task 5 fix pass -- see the module docstring's "A third
# anti-gaming floor". The TOTAL pooled generated-block count (across every qualifying
# factor) below which all four metric names NaN. 30 matches
# ah.eval.metrics.calibration.CALIBRATION_MIN_GENERATED_SUMS's floor on a pooled
# generated sample of comparable shape (a handful of blocks per factor is not a
# distribution).
MEMORIZATION_MIN_GENERATED_BLOCKS = 30

# The percentile of TRAIN's own leave-one-out nearest-neighbour distance distribution
# that defines "near duplicate" -- see the module docstring's "near_duplicate_fraction"
# for the full justification (matches ah.eval.metrics.monthly.HILL_TAIL_FRACTIONS' 5%
# reading of "the tail", the same round number chosen for the same reason: a stated,
# reproducible cut rather than an arbitrary one).
MEMORIZATION_EPSILON_PERCENTILE = 5.0

__all__ = [
    "MEMORIZATION_BLOCK_MONTHS",
    "MEMORIZATION_EPSILON_PERCENTILE",
    "MEMORIZATION_MIN_GENERATED_BLOCKS",
    "MEMORIZATION_MIN_TRAIN_BLOCKS",
    "SUITE",
    "TIER",
    "build_memorization_suite",
    "register_memorization_suite",
]


# --------------------------------------------------------------------------- #
# train/validation split of an already-combined historical_series (no DataAccess)
# --------------------------------------------------------------------------- #


def _train_validation_series(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Split an already-fetched TRAIN+VALIDATION series by the sealed split boundary.

    See the module docstring for why this recovers exactly what a second,
    split-scoped catalog read would have given, without one.
    """
    idx = series.index
    train = series.loc[(idx >= pd.Timestamp(TRAIN.start)) & (idx < pd.Timestamp(TRAIN.end))]
    val = series.loc[(idx >= pd.Timestamp(VALIDATION.start)) & (idx < pd.Timestamp(VALIDATION.end))]
    return train, val


# --------------------------------------------------------------------------- #
# standardization, blocks, distances -- see the module docstring's "Sequences"
# --------------------------------------------------------------------------- #


def _standardize(x: np.ndarray, *, mean: float, std: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return (x - mean) / std


def _factor_mean_std(series: pd.Series) -> tuple[float, float]:
    """The TRAIN split's own mean/std -- reused convention from
    :func:`ah.eval.metrics.utility._factor_mean_std`, applied here to TRAIN alone
    rather than train+validation (see the module docstring)."""
    values = series.to_numpy(dtype=np.float64)
    if values.size == 0:
        return 0.0, 1.0
    mean = float(np.mean(values))
    std = float(np.std(values))
    return mean, (std if std > 0.0 else 1.0)


def _raw_blocks(x: np.ndarray, *, block_months: int, mean: float, std: float) -> np.ndarray:
    """Non-overlapping, standardized ``block_months``-length blocks of ``x`` (partial
    tail dropped) -- shape ``(n_blocks, block_months)``, RAW values (not a [mean, std]
    summary, unlike ``ah.eval.metrics.utility._window_features``: a memorization check
    needs the trajectory's own shape, not just its first two moments)."""
    x = _standardize(np.asarray(x, dtype=np.float64).reshape(-1), mean=mean, std=std)
    usable = (x.shape[0] // block_months) * block_months
    if usable == 0:
        return np.empty((0, block_months), dtype=np.float64)
    return x[:usable].reshape(-1, block_months)


def _block_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two standardized blocks -- see the module docstring."""
    return float(np.sqrt(np.sum((a - b) ** 2)))


def _nearest_neighbor_distance(query: np.ndarray, candidates: np.ndarray) -> float:
    """Minimum :func:`_block_distance` from ``query`` to any row of ``candidates``.
    ``NaN`` if ``candidates`` is empty."""
    if candidates.shape[0] == 0:
        return float("nan")
    diffs = candidates - query[np.newaxis, :]
    return float(np.min(np.sqrt(np.sum(diffs**2, axis=1))))


def _leave_one_out_epsilon(blocks: np.ndarray, percentile: float) -> float:
    """The data-driven epsilon for ``near_duplicate_fraction`` -- see the module
    docstring. ``NaN`` if fewer than 2 blocks (a leave-one-out distance needs at least
    one OTHER block to compare against)."""
    n = blocks.shape[0]
    if n < 2:
        return float("nan")
    distances = np.empty(n, dtype=np.float64)
    for i in range(n):
        others = np.delete(blocks, i, axis=0)
        distances[i] = _nearest_neighbor_distance(blocks[i], others)
    return float(np.percentile(distances, percentile))


# --------------------------------------------------------------------------- #
# Mann-Whitney AUC (no sklearn) -- see the module docstring's "membership_inference_auc"
# --------------------------------------------------------------------------- #


def _mann_whitney_auc(positive: np.ndarray, negative: np.ndarray) -> float:
    """AUC of a classifier that scores "positive" higher than "negative", via the
    Mann-Whitney U statistic: ``P(positive > negative) + 0.5 * P(positive == negative)``,
    computed from average ranks of the pooled sample (ties averaged -- reuses
    :func:`ah.eval.reference._rank`'s tie convention rather than restating it).

    Closed-form rank-sum identity: with ``n_pos``/``n_neg`` the two group sizes and
    ``R`` the sum of the pooled average ranks of the positive group,
    ``AUC = (R - n_pos*(n_pos+1)/2) / (n_pos*n_neg)`` -- the standard equivalence
    between the Mann-Whitney U statistic and the AUC of the pooled-rank classifier,
    verified in ``tests/test_memorization.py`` against a literal brute-force pairwise
    comparison. ``NaN`` if either group is empty.
    """
    positive = np.asarray(positive, dtype=np.float64).reshape(-1)
    negative = np.asarray(negative, dtype=np.float64).reshape(-1)
    n_pos, n_neg = positive.shape[0], negative.shape[0]
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    pooled = np.concatenate([positive, negative])
    ranks = reference_rank(pooled)
    rank_sum_positive = float(np.sum(ranks[:n_pos]))
    u_positive = rank_sum_positive - n_pos * (n_pos + 1) / 2.0
    return u_positive / (n_pos * n_neg)


# --------------------------------------------------------------------------- #
# ensemble-level wiring
# --------------------------------------------------------------------------- #


def _shared_factors(
    manifest: FactorManifest, reference: ReferenceStats, ensemble: Ensemble
) -> list[str]:
    return [
        f
        for f in manifest.active_factors()
        if f in reference.historical_series and f in ensemble.factor_names
    ]


def _generated_blocks(ensemble: Ensemble, factor: str, mean: float, std: float) -> np.ndarray:
    """Every generated block of ``factor``, extracted independently WITHIN each path
    (never spanning a path boundary), pooled by concatenation."""
    slab = ensemble.factor(factor).astype(np.float64)
    parts = [
        _raw_blocks(slab[i], block_months=MEMORIZATION_BLOCK_MONTHS, mean=mean, std=std)
        for i in range(slab.shape[0])
    ]
    non_empty = [p for p in parts if p.shape[0] > 0]
    if not non_empty:
        return np.empty((0, MEMORIZATION_BLOCK_MONTHS), dtype=np.float64)
    return np.concatenate(non_empty, axis=0)


class _FactorMemorizationInputs:
    """Per-factor train/validation/generated blocks plus the train-derived epsilon --
    computed once per factor and shared by all four metrics' closures."""

    def __init__(self, reference: ReferenceStats, factor: str) -> None:
        series = reference.historical_series[factor]
        train_series, val_series = _train_validation_series(series)
        mean, std = _factor_mean_std(train_series)
        self.mean = mean
        self.std = std
        self.train_blocks = _raw_blocks(
            train_series.to_numpy(dtype=np.float64),
            block_months=MEMORIZATION_BLOCK_MONTHS,
            mean=mean,
            std=std,
        )
        self.val_blocks = _raw_blocks(
            val_series.to_numpy(dtype=np.float64),
            block_months=MEMORIZATION_BLOCK_MONTHS,
            mean=mean,
            std=std,
        )
        self.qualifies = self.train_blocks.shape[0] >= MEMORIZATION_MIN_TRAIN_BLOCKS
        self.epsilon = (
            _leave_one_out_epsilon(self.train_blocks, MEMORIZATION_EPSILON_PERCENTILE)
            if self.qualifies
            else float("nan")
        )

    def generated_blocks(self, ensemble: Ensemble, factor: str) -> np.ndarray:
        return _generated_blocks(ensemble, factor, self.mean, self.std)


def _pooled_memorization_signals(
    manifest: FactorManifest, reference: ReferenceStats, ensemble: Ensemble
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(nn_distances, train_proximity, val_proximity, near_dup_hits)`` pooled over
    every qualifying shared factor -- the one pass every metric's closure is built on,
    so the four numbers are guaranteed consistent with each other.

    Important 3 (WP2.2 Task 5 fix pass): ``nn_distances`` carries exactly one entry per
    pooled GENERATED block, so its length IS the generated-side sample size the module
    docstring's "A third anti-gaming floor" describes. Below
    :data:`MEMORIZATION_MIN_GENERATED_BLOCKS`, every array is returned EMPTY -- not
    partially populated -- so all four downstream metrics NaN identically (THE ONE NaN
    RULE, and the same all-or-nothing shape :data:`MEMORIZATION_MIN_TRAIN_BLOCKS`
    already has on the train side).
    """
    nn_distances: list[float] = []
    train_proximity: list[float] = []
    val_proximity: list[float] = []
    near_dup_hits: list[bool] = []

    for factor in _shared_factors(manifest, reference, ensemble):
        inputs = _FactorMemorizationInputs(reference, factor)
        if not inputs.qualifies:
            continue
        generated = inputs.generated_blocks(ensemble, factor)
        if generated.shape[0] == 0:
            continue

        for g in generated:
            d = _nearest_neighbor_distance(g, inputs.train_blocks)
            nn_distances.append(d)
            near_dup_hits.append(d < inputs.epsilon)

        for t in inputs.train_blocks:
            train_proximity.append(-_nearest_neighbor_distance(t, generated))
        for v in inputs.val_blocks:
            val_proximity.append(-_nearest_neighbor_distance(v, generated))

    if len(nn_distances) < MEMORIZATION_MIN_GENERATED_BLOCKS:
        return (
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=bool),
        )

    return (
        np.array(nn_distances, dtype=np.float64),
        np.array(train_proximity, dtype=np.float64),
        np.array(val_proximity, dtype=np.float64),
        np.array(near_dup_hits, dtype=bool),
    )


def _cached_pooled_signals(
    manifest: FactorManifest, reference: ReferenceStats
) -> Callable[[Ensemble], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """A single-slot cache of :func:`_pooled_memorization_signals`, shared by all four
    metric closures :func:`build_memorization_suite` builds (Minor, WP2.2 Task 5 fix
    pass: before this, every pairwise distance was computed 4x -- once per metric --
    for the identical ``(manifest, reference, ensemble)`` triple).

    Keyed on ensemble IDENTITY, verified via a weak reference rather than trusted by
    ``id()`` alone: ``id()`` can be reused after garbage collection, and a stale hit
    keyed only on a recycled id would silently return another ensemble's signals. The
    cache holds exactly one entry -- the suite is evaluated ensemble-by-ensemble
    (:func:`~ah.eval.battery.run_battery` calls ``spec.fn(ensemble)`` for all four specs
    on the SAME ensemble object in sequence before moving to the next one, and
    ``mc_error`` builds a fresh sub-ensemble per subsample anyway, so a single slot
    captures the actual 4x duplication without unbounded growth).
    """
    cache: dict[int, tuple[weakref.ReferenceType[Ensemble], tuple[np.ndarray, ...]]] = {}

    def get(ensemble: Ensemble) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        key = id(ensemble)
        hit = cache.get(key)
        if hit is not None and hit[0]() is ensemble:
            return hit[1]  # type: ignore[return-value]
        result = _pooled_memorization_signals(manifest, reference, ensemble)
        cache.clear()
        cache[key] = (weakref.ref(ensemble), result)
        return result

    return get


def _nn_distance_metric(
    signals: Callable[[Ensemble], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    which: str,
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        nn_distances, _, _, _ = signals(ensemble)
        if nn_distances.size == 0:
            return float("nan")
        return float(np.percentile(nn_distances, 5 if which == "p05" else 50))

    return fn


def _membership_inference_auc_metric(
    signals: Callable[[Ensemble], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        _, train_proximity, val_proximity, _ = signals(ensemble)
        if train_proximity.size == 0 or val_proximity.size == 0:
            return float("nan")
        return _mann_whitney_auc(train_proximity, val_proximity)

    return fn


def _near_duplicate_fraction_metric(
    signals: Callable[[Ensemble], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        _, _, _, near_dup_hits = signals(ensemble)
        if near_dup_hits.size == 0:
            return float("nan")
        return float(np.mean(near_dup_hits))

    return fn


def _spec(name: str, fn: MetricFn) -> MetricSpec:
    return MetricSpec(name=name, tier=TIER, fn=fn, suite=SUITE)


def build_memorization_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """The four whole-panel memorization-tier :class:`~ah.eval.battery.MetricSpec`
    entries. Whole-panel, matching :data:`~ah.eval.reference.PANEL_STATS`'s bare-name
    registration for these four names -- see the module docstring."""
    signals = _cached_pooled_signals(manifest, reference)
    return (
        _spec("nn_distance_p05", _nn_distance_metric(signals, "p05")),
        _spec("nn_distance_p50", _nn_distance_metric(signals, "p50")),
        _spec("membership_inference_auc", _membership_inference_auc_metric(signals)),
        _spec("near_duplicate_fraction", _near_duplicate_fraction_metric(signals)),
    )


def register_memorization_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("memorization", build_memorization_suite(manifest, reference))``."""
    register_suite(SUITE, build_memorization_suite(manifest, reference))
