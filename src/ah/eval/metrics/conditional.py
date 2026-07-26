"""Condition adherence + off-support degradation (WP2.2 Task 6).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``conditional.py`` bullet, verbatim: "condition
adherence: for a battery of WorldSpec test worlds (authored set, checked in), measure
realized ensemble statistics vs specified conditions (inflation average, crisis
timing/severity, rate endpoints) -- error distributions per condition type; off-support
degradation: sweep conditions from historical-typical to counterfactual extremes,
report battery-pass-rate and adherence as functions of distance from support. The
bootstrap runs this suite too -- its structural inability to honor novel conditions
becomes measured evidence, not an aside."

This is the suite that measures whether a generator honours the conditions a WorldSpec
asks for -- the thing the whole platform exists to do -- and STEP2-GENERATOR-PLAN
Sec.WP2.3's sealed decision rule is explicit that it is **reported alongside G2 but does
not gate promotion** ("the platform's purpose weighs conditioning, but historical tail fidelity
remains the falsifiable criterion -- revisit at G3"). Every threshold this suite carries
in ``pre-registration.yaml`` is therefore ``severity: report``, never ``enforce`` --
nothing here may block a promotion decision.

Why this suite's metrics REGENERATE ensembles rather than reading the judged one
------------------------------------------------------------------------------------
Every other WP2.2 suite's :class:`~ah.eval.battery.MetricFn` reads the single
``ensemble`` :func:`~ah.eval.battery.run_battery` was given. This suite cannot: "measure
realized ensemble statistics vs specified conditions" is meaningless against an ensemble
that was not generated under a stated condition in the first place, and the platform has
no convention yet for stamping a WorldSpec's ``factor_conditions`` onto an
:class:`~ah.gen.base.EnsembleMeta` produced under *unconditional* sampling (the common
case every other suite is exercised against, including every ``run_full_battery`` test
fixture in ``tests/test_eval_battery.py``).

Instead, every metric here resolves :attr:`~ah.gen.base.EnsembleMeta.generator_id` off
the ensemble it was actually handed -- **the same generator the rest of the battery is
judging** -- via :func:`ah.gen.registry.resolve`, and calls that generator's own
``.sample(world, n_paths, seed)`` fresh, once per authored/swept
:class:`~ah.core.numericworld.NumericWorld`, for every condition-adherence check this
module runs. This is why "the bootstrap runs this suite too" (the plan's own phrase) is
meaningful rather than vacuous: at battery-run time the generator under test is
re-invoked against a battery of conditions it may never have seen, and a generator that
structurally cannot honor a condition (a block bootstrap sampling from unconditional
history, ignoring ``factor_conditions`` entirely) produces a real, large, quantified
adherence error -- not a NaN, not a crash. Determinism is preserved: every regeneration
seed is ``ensemble.meta.seed + _SEED_STRIDE * k`` for a stable, sorted ``k``, the same
``base_seed + 7919*k`` convention ``CLAUDE.md`` states for ensemble seeds platform-wide
(:data:`_SEED_STRIDE`).

**Platform-gap consequence, stated plainly.** No generator is registered in
:mod:`ah.gen.registry` in production until WP2.4 (the bootstrap benchmark). Until then
-- and for any ``run_full_battery`` call against an ensemble whose ``generator_id`` no
factory has been registered under (e.g. every orchestration fixture in
``tests/test_eval_battery.py``, ``generator_id="orchestration-test"``) -- every metric
in this suite is honestly NaN: :func:`ah.gen.registry.resolve` raises
:class:`~ah.gen.registry.UnknownGeneratorError`, caught here and reported as NaN rather
than propagated (a metric must never crash the battery), and NaN correctly fails under
THE ONE NaN RULE if any threshold here were ever ``enforce`` -- which is exactly why
every threshold is ``report``: an ensemble produced before this suite's own
infrastructure (a resolvable generator) exists must not be judged as though it failed a
conditioning test it structurally could not be given.

Part A -- condition adherence
------------------------------
Four condition types, each mapped to the WorldSpec field(s) that express it
(``schemas/worldspec-v1.0.schema.json``'s ``factor_conditions``, mirrored in
:mod:`ah.core.worldspec`'s ``FactorConditions``) and each backed by two checked-in
authored worlds under ``fixtures/worlds/conditional/`` (a mild and a severe intensity,
tagged ``extensions.x_condition_type`` / ``extensions.x_intensity`` -- namespaced
metadata the schema explicitly permits and engines must ignore, read only by
:func:`load_conditional_test_worlds`, never by a generator).

**Those eight files are sealed input data, not fixtures in the disposable sense.** Every
``condition_adherence_*`` estimator in ``pre-registration.yaml`` defines its statistic as
"pooled across every checked-in ``fixtures/worlds/conditional/*.json`` world tagged X", so
editing one world's ``average_pct`` moves every inflation metric's value. They are
therefore inside the pre-registration seal
(:data:`ah.eval.prereg._REQUIRED_JUDGED_FIXTURE_GLOBS`,
``governance/retrofit-register.md`` RFR-33), exactly like the ``factors.yaml`` the bands
are keyed to: after WP2.3 seals, changing one is a lock violation requiring a dated
amendment, and the estimator is reconstructible from the sealed set alone. The four
condition types:

- ``inflation`` -- ``factor_conditions.inflation.average_pct``. Realized (per path):
  the mean of the trailing-12-month YoY CPI inflation
  (:func:`ah.eval.metrics.economics.cpi_yoy_from_level`, reused rather than
  re-derived) over the whole generated horizon. Error: ``abs(realized - target)``,
  percentage points, unsigned. Lower is better without a "too good" penalty -- unlike
  ``policy_anchor_deviation`` (a soft, DERIVED economic regularity a generator was
  never explicitly asked to hit), the WorldSpec here EXPLICITLY asked for this exact
  number, so an exact hit is genuinely the correct answer, not a degenerate one.
- ``rate`` -- ``factor_conditions.policy_rate.{start_pct,end_pct}``. Realized (per
  path): the path's own first-month and last-month ``policy_rate`` level. Error: the
  mean of ``abs(realized_start - start_pct)`` and ``abs(realized_end - end_pct)`` over
  whichever of the two the world specifies (both, in every checked-in fixture). Units:
  percentage points.
- ``crisis_timing`` -- ``factor_conditions.crisis_windows[0]`` (``{start_quarter,
  length_quarters}``). Realized (per path): the index (in quarters) of the
  non-overlapping 3-month block with the most negative cumulative ``equity_mkt``
  return over the whole path (:func:`ah.eval.reference.nonoverlapping_sums`, reused
  rather than a second windowing scheme). Target: the window's own midpoint quarter,
  ``start_quarter + length_quarters/2``. Error: ``abs(realized_quarter -
  target_quarter)``, in quarters.
- ``crisis_severity`` -- ``factor_conditions.crisis_windows[0].severity`` (schema range
  ``[0, 1]``, "0 = mild wobble, 1 = 2008-scale"). Realized (per path): the magnitude
  of that same worst non-overlapping quarterly ``equity_mkt`` shock, clamped at 0
  (a path with no down-quarter at all realizes zero shock, not a negative one),
  expressed in percentage points. Target: ``severity * :data:`CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT```
  -- a STATED, SIMPLIFIED linear mapping (see that constant's docstring for its
  historical anchor), exactly the same kind of stated substitution
  ``ah.eval.metrics.economics``'s ``TAYLOR_*`` constants make for
  ``policy_anchor_deviation``, for the identical reason: the schema names "2008-scale"
  as the ``severity=1`` anchor but gives no formula translating it into a
  generator-visible return magnitude. Error: ``abs(realized_shock_pct -
  target_shock_pct)``, percentage points. **Deliberately timing-agnostic**: severity is
  scored against the path's GLOBAL worst quarter, not one restricted to the specified
  window, so a timing miss is not double-counted as a severity failure too --
  ``condition_adherence_error_crisis_timing`` already measures placement.

Each condition type registers two metrics: ``condition_adherence_error_{type}`` (the
POOLED mean of every per-path error, across every path of every one of that type's
authored worlds) and ``condition_adherence_error_p90_{type}`` (the pooled 90th
percentile of the identical per-path error array) -- "so a generator that is usually
right and occasionally wildly wrong cannot hide behind a mean" (the brief's own words).

Per-path vs pooled, stated explicitly (structural requirement 4)
-------------------------------------------------------------------
Every condition-adherence statistic here is **POOLED**, not per-path in the
:mod:`ah.eval.reference` ``length_matched`` sense -- and it cannot be registered in
:data:`~ah.eval.reference.SINGLE_FACTOR_STATS`/:data:`~ah.eval.reference.CROSS_BLOCK_STATS`
(which carry that flag) at all: those two registries compare a factor's OWN
train+validation history to itself, and every statistic here compares a FRESHLY
GENERATED ensemble to a WorldSpec's stated target, which has no historical analog to
band against -- exactly :data:`~ah.eval.reference.PANEL_STATS`'s "no ``fn``" shape,
the same one ``ah.eval.metrics.economics``/``memorization``/``utility`` already use for
their own generated-vs-something comparisons. The underlying computation IS per-path
(one error value per simulated path, per world -- see above), but the two REPORTED
numbers (mean, p90) are pooled aggregates over every ``(world, path)`` pair of that
condition type, which is the granularity the p90-catches-a-tail argument needs: p90 of
a single world's single point estimate would be that same point, degenerate.

Anti-gaming floor: :data:`CONDITIONAL_MIN_OBS`
--------------------------------------------------
A percentile is a noisier statistic than a mean at fixed sample size, so the floor
below which this suite refuses to report a mean OR a p90 is set with the percentile in
mind, not just the mean (contrast the shape of :data:`~ah.eval.reference.VARIANCE_RATIO_MIN_SUMS`
=10, which only ever bands a mean-like ratio). 20 pooled per-path observations is the
floor; below it, NaN -- which FAILS under THE ONE NaN RULE for any ``enforce``
threshold, though nothing here is currently sealed ``enforce``.

**Structural requirement 6, restated for this suite specifically.** Any single
authored/swept world's regeneration failing outright -- an unresolvable
``generator_id`` (:class:`~ah.gen.registry.UnknownGeneratorError`), a generator
exception during ``.sample()``, the regenerated ensemble omitting the factor the
condition needs, or the regenerated ensemble producing a non-finite value anywhere in
the quantity being checked -- **poisons the WHOLE pooled metric to NaN**, never drops
silently to a smaller surviving sample. A generator that raises, or refuses to emit
the conditioned factor, has produced LESS than one that emits it and adheres honestly,
and under THE ONE NaN RULE that must never read as a smaller (better) error -- the
identical discipline ``ah.eval.metrics.economics``'s ``money_pump_estimator``/
``floor_violations_estimator`` already state for an omitted audited factor.

Part B -- off-support degradation
------------------------------------
Swept over exactly two of the four condition types -- ``inflation`` and ``rate`` --
because both have a REAL train+validation historical quantity to define "distance from
support" against (:data:`OFF_SUPPORT_TYPES`). ``crisis_timing`` (a temporal placement,
not a magnitude) and ``crisis_severity`` (a WorldSpec-only ``[0,1]`` scale with no
directly observed historical unit) have no natural real-valued distance under the
simple definition this task uses -- see "Distance from support" below for the
definition and why it does not extend to those two, and **WP2.7's ``support.py``
(Mahalanobis distance on encoder features + a regime-frequency check) is the work
package that supersedes this placeholder for every condition type, including these
two**, once encoder features exist. This module does not invent a fake encoder to cover
the gap now.

Distance from support
~~~~~~~~~~~~~~~~~~~~~~~
For a swept condition's target scalar ``v`` against a REFERENCE quantity ``X`` (the
train+validation historical series of the SAME quantity being conditioned -- YoY CPI
inflation for ``inflation``, the raw ``policy_rate`` level for ``rate``, both read from
:attr:`~ah.eval.reference.ReferenceStats.historical_series`, never a fresh catalog
read): ``distance(v) = abs(v - mean(X)) / std(X)`` -- an ordinary z-score against ``X``'s
train+validation distribution. Four swept levels (:data:`OFF_SUPPORT_LEVELS`), each a
STATED z-score used to construct the actual swept target (``mean(X) + z*std(X)``,
clipped to the WorldSpec schema's own valid range for that field):
``typical`` (z=0, the historical mean itself), ``p95``/``p99`` (the standard-normal
95th/99th-percentile z-scores, 1.6449/2.3263 -- constructing a target that far from the
historical mean IN Z-SCORE TERMS, not literally reading history's own 95th/99th
percentile, which this simple Gaussian proxy does not attempt to estimate), and
``beyond`` (z=4.0, a stated, clearly-outside-any-plausible-normal-quantile
counterfactual extreme). The swept target is clipped into the swept field's OWN
``schemas/worldspec-v1.0.schema.json`` bounds, **read from that schema at run time**
(:func:`_off_support_bounds`) rather than restated here: a hand-copied bound is a second
independent definition of one quantity, and its failure mode is precisely the one
:func:`_regenerate` now absorbs -- tighten the schema and an unclipped target builds a
structurally invalid document.

**Partial support poisons the level, exactly as a partial pool poisons a Part A metric.**
``off_support_adherence_at_{level}``'s sealed definition is "across BOTH swept types", so
a reference carrying ``policy_rate`` history but no ``cpi`` history must NOT quietly
report the rate arm alone under that name -- a different, smaller, unlabelled statistic.
If ANY member of :data:`OFF_SUPPORT_TYPES` has no usable support distribution, every level
is built empty and every Part B metric is NaN. This is the reference-side half of the
same never-drop-to-a-smaller-pool discipline :func:`_pooled_errors` applies on the
generated side.

``off_support_adherence_at_{level}`` is the pooled mean adherence error (percentage
points, the shared unit of both swept types) across BOTH swept condition types at that
level; ``off_support_pass_rate_at_{level}`` is the fraction of the identical pooled
per-path error array that falls at or below :data:`OFF_SUPPORT_PASS_TOLERANCE_PCT`
(2.0 percentage points -- a stated, round tolerance in the same units the checked-in
``inflation``/``rate`` bands above already report in, chosen as a tolerance tight
enough to distinguish real adherence from a lucky miss, loose enough not to fail a
generator on ordinary Monte-Carlo path-to-path noise). **"Battery" here names this
suite's OWN pooled adherence checks across the two swept types at a given level, not
the full cross-suite validation battery** -- running every OTHER suite (monthly,
horizon, tails, ...) against each swept off-support world is the genuinely full
`battery-pass-rate-as-a-function-of-distance` DN-1.1 describes, and is exactly the
severe-test-shaped evaluation WP2.9/WP2.11 run once a real generator exists; this
metric is a cheap, always-available proxy computed entirely inside this one suite.

Registration is deferred, exactly as every other reference-dependent suite
-------------------------------------------------------------------------------
``manifest`` is accepted for signature symmetry with every suite builder in
``ah.eval.battery._REFERENCE_DEPENDENT_SUITE_BUILDERS`` but unused: every metric here
reads the FRESHLY REGENERATED ensemble's own factor names, never ``manifest``'s. Unlike
``ah.eval.metrics.economics`` (which also does not read ``reference``), THIS module DOES
read ``reference.historical_series`` -- for Part B's support distributions only.

Monte-Carlo error: measured over REGENERATION SEEDS, not path subsamples
--------------------------------------------------------------------------
:func:`ah.eval.battery.mc_error` recomputes a metric on disjoint subsamples of the
PASSED ensemble's paths. Every metric in this module ignores those paths entirely -- only
``ensemble.meta.generator_id``/``ensemble.meta.seed`` cross into the regeneration -- so
that estimator returns exactly ``0.0`` here, on every metric, always. That number is
arithmetically correct and *substantively misleading*: these values carry real
Monte-Carlo uncertainty (each is a pooled statistic over
:data:`CONDITIONAL_RESAMPLE_N_PATHS` freshly sampled paths per world), and ``mc_error`` is
exactly the number a WP2.3 threshold author reads to size a band ("MC error << band
width", STEP2-GENERATOR-PLAN Sec.WP2.2). Reporting a confident ``0.0`` beside a value
with genuine spread invites a band far tighter than the metric can support.

This suite therefore supplies its OWN estimator, :func:`conditional_mc_error`, wired
through :attr:`ah.eval.battery.MetricSpec.mc_error_fn` (an additive hook -- every other
suite keeps the default path-subsampling estimator untouched). It recomputes the metric at
:data:`CONDITIONAL_MC_ERROR_REPLICATES` further regeneration seeds -- the axis this
suite's randomness actually flows along -- and reports
``std(replicates, ddof=1)``. Note the absent ``/sqrt(k)``: :func:`ah.eval.battery.mc_error`
divides because its ``k`` subsamples partition the paths behind the *reported* value, so
the batch-means argument scales back up to the full n; here each replicate is an
INDEPENDENT re-draw of the whole statistic at the same path count, and the reported value
is one such draw, so the cross-replicate standard deviation IS its standard error
directly. A generator that ignores ``seed`` (the perfect test double) still reports
``0.0`` -- now as a measured fact about that generator rather than an artifact of the
estimator.

Cost is bounded by :func:`_regenerate`'s module-local memo: the value and its replicates
are a pure function of ``(world document, generator_id, n_paths, seed)``, the mean and p90
metrics of a condition type share every regeneration, and the memo is cleared at each
:func:`build_conditional_suite` call so it never outlives one suite registration. That
takes a full battery evaluation of this suite from ~670 ``.sample()`` calls (16 metrics x
21 recomputations x 2 worlds, every one of them recomputing a bit-identical value) to
~144 -- fewer calls than before, now buying a real error bar instead of a tautological
zero. ``governance/retrofit-register.md`` RFR-32 records this, and closes RFR-31 (which
had deferred the cost half of it to WP2.4/WP2.8 and never named the honesty half).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ah.core.digest import canonical_json
from ah.core.loader import load_worldspec, worldspec_schema
from ah.core.numericworld import NumericWorld, project_numeric
from ah.eval.battery import MetricFn, MetricSpec, register_suite
from ah.eval.metrics.economics import cpi_yoy_from_level
from ah.eval.reference import ReferenceStats, nonoverlapping_sums
from ah.factors import FactorManifest
from ah.gen import registry as gen_registry
from ah.gen.base import Ensemble

SUITE = "conditional"
# DN-1.1 Sec.II.6 has no row named "conditional" -- the brief's own instruction is to
# register at tier "monthly" absent a more specific assignment, which this suite
# follows verbatim.
TIER = "monthly"

_REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_DIR = _REPO_ROOT / "fixtures" / "worlds" / "conditional"

CONDITION_TYPES: tuple[str, ...] = ("inflation", "rate", "crisis_timing", "crisis_severity")
# The two condition types Part B's off-support sweep covers -- see the module
# docstring's "Distance from support" for why crisis_timing/crisis_severity are
# excluded from the simple z-score definition this task uses.
OFF_SUPPORT_TYPES: tuple[str, ...] = ("inflation", "rate")

# Ensemble seeds are `base_seed + 7919*k` platform-wide (CLAUDE.md); every regeneration
# in this module derives its seed the same way, keyed by a stable, sorted index k.
_SEED_STRIDE = 7919

# How many paths each regenerated per-world/per-sweep ensemble carries. Small enough to
# keep a battery run fast (this suite calls .sample() once per world per metric
# evaluation -- see the module docstring's mc_error note), large enough that a 10%
# "usually right, occasionally wrong" tail (the p90 test's own construction) is
# represented by several whole paths rather than a fraction of one.
CONDITIONAL_RESAMPLE_N_PATHS = 64

# See the module docstring's "Anti-gaming floor".
CONDITIONAL_MIN_OBS = 20

# Q4 2008 S&P 500 total return was approximately -21.9% (the historical event the
# WorldSpec schema's own crisis_windows.severity description names as the severity=1.0
# anchor: "1 = 2008-scale"). Rounded to -22.0%, this is a STATED, SIMPLIFIED, linear
# severity -> quarterly-equity-shock mapping used only because no generator-visible
# quantity gives severity a formula of its own -- see the module docstring's
# `crisis_severity` section and ah.eval.metrics.economics's TAYLOR_* constants for the
# identical kind of stated substitution.
CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT = 22.0

# Part B's swept levels: (name, z-score used to construct mean(X) + z*std(X)). See the
# module docstring's "Distance from support".
OFF_SUPPORT_LEVELS: tuple[tuple[str, float], ...] = (
    ("typical", 0.0),
    ("p95", 1.6448536269514722),  # standard-normal 95th-percentile z-score
    ("p99", 2.3263478740408408),  # standard-normal 99th-percentile z-score
    ("beyond", 4.0),
)
# A stated, round tolerance in the shared percentage-point unit of both swept types
# (inflation average_pct, policy_rate end_pct) -- see the module docstring's Part B.
OFF_SUPPORT_PASS_TOLERANCE_PCT = 2.0

# The swept field each off-support condition type writes, as a path into
# `schemas/worldspec-v1.0.schema.json`'s factor_conditions object -- the ONE place either
# fact is stated. `_sweep_world` writes the field; `_off_support_bounds` reads its bounds.
_SWEPT_FIELD: dict[str, tuple[str, str]] = {
    "inflation": ("inflation", "average_pct"),
    "rate": ("policy_rate", "end_pct"),
}

# How many further regeneration seeds `conditional_mc_error` recomputes each metric at --
# see the module docstring's Monte-Carlo section. 8 is enough for a usable order of
# magnitude on a std with ddof=1 while keeping the per-metric regeneration count bounded;
# it is deliberately NOT `ah.eval.battery._DEFAULT_MC_SUBSAMPLES`, which is bounded by the
# PASSED ensemble's path count -- a quantity this suite's metrics never read, and which
# therefore must not decide how many independent regenerations are available.
CONDITIONAL_MC_ERROR_REPLICATES = 8

# Replicate seeds are `meta.seed + _MC_REPLICATE_STRIDE*(r+1)`. The stride is a large
# multiple of `_SEED_STRIDE` so a replicate's own per-world offsets (`+ _SEED_STRIDE*k`,
# k < 1000 for Part A and k in [1000, 2000) for Part B) can never collide with another
# replicate's, nor with the reported value's.
_MC_REPLICATE_STRIDE = _SEED_STRIDE * 10_000

# `_regenerate`'s memo size. Sized to the working set of ONE (mean, p90) metric pair --
# 2 worlds x (1 reported value + CONDITIONAL_MC_ERROR_REPLICATES) seeds = 18 entries --
# plus headroom, deliberately NOT to hold every world of every metric: a cached Ensemble
# is real memory (n_paths x months x n_factors float64), and consecutive metrics are the
# only ones that share regenerations.
_REGENERATION_CACHE_SIZE = 32

__all__ = [
    "CONDITIONAL_MC_ERROR_REPLICATES",
    "CONDITIONAL_MIN_OBS",
    "CONDITIONAL_RESAMPLE_N_PATHS",
    "CONDITION_TYPES",
    "CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT",
    "FIXTURES_DIR",
    "OFF_SUPPORT_LEVELS",
    "OFF_SUPPORT_PASS_TOLERANCE_PCT",
    "OFF_SUPPORT_TYPES",
    "SUITE",
    "TIER",
    "ConditionalFixtureError",
    "build_conditional_suite",
    "clear_regeneration_cache",
    "conditional_mc_error",
    "load_conditional_test_worlds",
    "register_conditional_suite",
]


class ConditionalFixtureError(ValueError):
    """Raised when a checked-in ``fixtures/worlds/conditional/`` world is malformed."""


# --------------------------------------------------------------------------- #
# Part A helpers -- per-path error arrays over a FRESHLY REGENERATED ensemble
# --------------------------------------------------------------------------- #


def _quarterly_equity_sums(equity: np.ndarray) -> np.ndarray | None:
    """``(n_paths, n_quarters)`` non-overlapping 3-month sums of ``equity_mkt``.

    Reuses :func:`ah.eval.reference.nonoverlapping_sums` per path (never a second
    windowing scheme). ``None`` if the path is too short for even one full quarter.
    """
    if equity.shape[1] < 3:
        return None
    per_path = [nonoverlapping_sums(equity[i], 3) for i in range(equity.shape[0])]
    return np.stack(per_path, axis=0)


def inflation_error_per_path(ensemble: Ensemble, target_average_pct: float) -> np.ndarray:
    """``abs(mean(trailing-12m YoY CPI inflation)) - target)`` per path, percentage points.

    Empty (never raising) if ``cpi`` is absent from ``ensemble`` or the path is too
    short for any YoY value (<=12 months).
    """
    if "cpi" not in ensemble.factor_names:
        return np.empty(0, dtype=np.float64)
    cpi = ensemble.factor("cpi").astype(np.float64)
    yoy = cpi_yoy_from_level(cpi)
    if yoy.shape[1] == 0:
        return np.empty(0, dtype=np.float64)
    realized = np.mean(yoy, axis=1)
    return np.abs(realized - target_average_pct)


def rate_error_per_path(
    ensemble: Ensemble, start_pct: float | None, end_pct: float | None
) -> np.ndarray:
    """Mean of the specified endpoint(s)' absolute deviation, per path, percentage points.

    ``policy_rate[:, 0]`` is the realized start, ``policy_rate[:, -1]`` the realized
    end. Averages over whichever of ``start_pct``/``end_pct`` is not ``None`` (both, in
    every checked-in fixture). Empty if ``policy_rate`` is absent, the path has no
    months, or neither endpoint is given.
    """
    if "policy_rate" not in ensemble.factor_names:
        return np.empty(0, dtype=np.float64)
    pr = ensemble.factor("policy_rate").astype(np.float64)
    if pr.shape[1] == 0:
        return np.empty(0, dtype=np.float64)
    parts: list[np.ndarray] = []
    if start_pct is not None:
        parts.append(np.abs(pr[:, 0] - start_pct))
    if end_pct is not None:
        parts.append(np.abs(pr[:, -1] - end_pct))
    if not parts:
        return np.empty(0, dtype=np.float64)
    return np.mean(np.stack(parts, axis=0), axis=0)


def crisis_timing_error_per_path(ensemble: Ensemble, target_quarter: float) -> np.ndarray:
    """``abs(quarter-of-worst-equity-shock - target_quarter)`` per path, in quarters."""
    if "equity_mkt" not in ensemble.factor_names:
        return np.empty(0, dtype=np.float64)
    quarterly = _quarterly_equity_sums(ensemble.factor("equity_mkt").astype(np.float64))
    if quarterly is None:
        return np.empty(0, dtype=np.float64)
    worst_quarter = np.argmin(quarterly, axis=1).astype(np.float64)
    return np.abs(worst_quarter - target_quarter)


def crisis_severity_error_per_path(ensemble: Ensemble, target_severity: float) -> np.ndarray:
    """``abs(realized_worst_quarterly_shock_pct - target_shock_pct)`` per path.

    ``target_shock_pct = target_severity * CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT``.
    Deliberately timing-agnostic -- see the module docstring's ``crisis_severity``
    section.
    """
    if "equity_mkt" not in ensemble.factor_names:
        return np.empty(0, dtype=np.float64)
    quarterly = _quarterly_equity_sums(ensemble.factor("equity_mkt").astype(np.float64))
    if quarterly is None:
        return np.empty(0, dtype=np.float64)
    realized_shock_pct = np.maximum(0.0, -np.min(quarterly, axis=1)) * 100.0
    target_shock_pct = target_severity * CRISIS_SEVERITY_REFERENCE_QUARTERLY_SHOCK_PCT
    return np.abs(realized_shock_pct - target_shock_pct)


def _crisis_window_target_quarter(window: Any) -> float:
    """The window's own midpoint quarter, off the numeric projection's ``CrisisWindow``."""
    return float(window.start_quarter) + float(window.length_quarters) / 2.0


# --------------------------------------------------------------------------- #
# checked-in fixture loading (Part A)
# --------------------------------------------------------------------------- #


def _check_tag_matches_conditions(condition_type: str, world: NumericWorld, label: str) -> None:
    """A world's ``x_condition_type`` tag must match the ``factor_conditions`` it carries.

    Without this, a world tagged ``inflation`` whose ``factor_conditions`` has no
    ``inflation`` block is only discovered at metric-evaluation time -- and (before this
    check) as a raw ``KeyError``/``IndexError`` escaping ``spec.fn``, which aborts the
    WHOLE battery rather than NaN-ing one metric. The tag and the fields are two
    statements of one fact, so they are reconciled once, at load time, where a malformed
    checked-in world is a loud fixture error instead of a runtime surprise.
    """
    fc = world.factor_conditions
    if condition_type == "inflation":
        ok = fc.inflation is not None and fc.inflation.average_pct is not None
        needed = "factor_conditions.inflation.average_pct"
    elif condition_type == "rate":
        ok = fc.policy_rate is not None and (
            fc.policy_rate.start_pct is not None or fc.policy_rate.end_pct is not None
        )
        needed = "factor_conditions.policy_rate.start_pct and/or .end_pct"
    else:  # crisis_timing / crisis_severity -- the schema requires all three sub-fields
        ok = bool(fc.crisis_windows)
        needed = "a non-empty factor_conditions.crisis_windows"
    if not ok:
        raise ConditionalFixtureError(
            f"{label}: tagged extensions.x_condition_type={condition_type!r} but carries "
            f"no {needed}; the tag and the conditioned fields must agree"
        )


@lru_cache(maxsize=1)
def load_conditional_test_worlds() -> tuple[tuple[str, dict[str, Any]], ...]:
    """Every ``fixtures/worlds/conditional/*.json`` world, as ``(condition_type, doc)``.

    Sorted by filename (deterministic regardless of filesystem iteration order).
    Each document is validated against the WorldSpec schema via
    :func:`ah.core.loader.load_worldspec` -- an authored world that does not validate
    is a silent hole in the suite, so this raises rather than skipping it. Every
    document must carry ``extensions.x_condition_type`` naming one of
    :data:`CONDITION_TYPES`, **and must actually carry the ``factor_conditions`` that tag
    names** (:func:`_check_tag_matches_conditions`); a fixture that omits either raises
    :class:`ConditionalFixtureError`.

    ``@lru_cache``: the fixtures are static, read-only, and this is called once per
    :func:`build_conditional_suite` invocation (every real battery run) -- re-reading
    and re-validating 8 small JSON files from disk on every call would be pure waste.
    """
    docs: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        # schema + pydantic validation; raises on a malformed world
        world = project_numeric(load_worldspec(raw))
        extensions = raw.get("extensions") or {}
        condition_type = extensions.get("x_condition_type")
        if condition_type not in CONDITION_TYPES:
            raise ConditionalFixtureError(
                f"{path}: extensions.x_condition_type must be one of {CONDITION_TYPES}, "
                f"got {condition_type!r}"
            )
        _check_tag_matches_conditions(condition_type, world, str(path))
        docs.append((condition_type, raw))
    if not docs:
        raise ConditionalFixtureError(f"{FIXTURES_DIR}: no authored world fixtures found")
    return tuple(docs)


def _worlds_for_type(condition_type: str) -> tuple[tuple[int, dict[str, Any]], ...]:
    """This type's worlds as ``(k, doc)``, ``k`` a GLOBALLY unique regeneration index.

    ``k`` indexes the whole sorted fixture set, not this type's slice of it, so the
    ``base_seed + 7919*k`` convention the module docstring cites gives every checked-in
    world its own seed. Restarting ``k`` per condition type would regenerate
    ``inflation_mild`` and ``rate_endpoints_mild`` under an identical seed -- harmless
    today, but a claim in the docstring that the code did not actually honour.
    """
    items = tuple(
        (k, doc)
        for k, (ctype, doc) in enumerate(load_conditional_test_worlds())
        if ctype == condition_type
    )
    if not items:
        raise ConditionalFixtureError(
            f"no checked-in fixtures/worlds/conditional/*.json world is tagged "
            f"extensions.x_condition_type={condition_type!r}"
        )
    return items


# --------------------------------------------------------------------------- #
# regeneration + pooling -- shared by Part A and Part B
# --------------------------------------------------------------------------- #

ErrorFn = Callable[[Ensemble, NumericWorld], np.ndarray]


@lru_cache(maxsize=_REGENERATION_CACHE_SIZE)
def _regenerate_cached(
    doc_json: str, generator_id: str, n_paths: int, seed: int
) -> tuple[Ensemble, NumericWorld] | None:
    """Memoized :func:`_regenerate`. Keyed on the world document's canonical JSON.

    **Why the whole document and not just its ``world_id``.** The Part B sweep worlds
    reuse one ``world_id`` per (condition type, level) while their actual conditioning
    target is a function of the :class:`~ah.eval.reference.ReferenceStats` the suite was
    built against -- a second battery run on a different vintage constructs a DIFFERENT
    world under the SAME id. An id-keyed memo would hand it the first run's ensemble.
    The canonical JSON is the content itself, so the key cannot be stale.

    **Why memoizing is sound, and what it assumes.** The returned pair is a pure function
    of these four arguments: :func:`ah.gen.registry.resolve` constructs a fresh generator
    from a registered factory, :func:`ah.core.loader.load_worldspec` is pure, and
    ``Generator.sample(world, n_paths, seed)`` is required to be deterministic in
    ``seed`` (``CLAUDE.md``'s determinism invariant -- the same premise the whole suite
    rests on). The one assumption is that ``generator_id`` names the same generator for
    the lifetime of the cache; :func:`build_conditional_suite` clears it on every suite
    registration, so the cache never outlives one battery run's registry state.

    Callers must treat the returned :class:`~ah.gen.base.Ensemble` as read-only -- it is
    shared. Every error function in this module reads it through ``.astype(np.float64)``,
    which copies.
    """
    # ONE guarded region for every failure mode this suite must not crash on: an
    # unregistered `generator_id` (`UnknownGeneratorError`); a registered FACTORY that
    # raises while CONSTRUCTING the generator (WP2.4's bootstrap will load and fit inside
    # its factory, so this is not hypothetical); a swept/authored document that fails
    # schema or pydantic validation; and the generator raising during `.sample()`. A
    # generator crashing on a novel/off-support condition is itself adherence evidence, to
    # be reported as an unresolvable-world NaN -- never propagated, which would lose every
    # OTHER suite's results too (`ah.eval.battery._run_suites` calls `spec.fn` unguarded).
    try:
        generator = gen_registry.resolve(generator_id)
        world = project_numeric(load_worldspec(json.loads(doc_json)))
        ensemble = generator.sample(world, n_paths, seed)
    except Exception:
        return None
    return ensemble, world


def clear_regeneration_cache() -> None:
    """Drop every memoized regeneration. Called on each :func:`build_conditional_suite`."""
    _regenerate_cached.cache_clear()


def _regenerate(
    doc: dict[str, Any], generator_id: str, n_paths: int, seed: int
) -> tuple[Ensemble, NumericWorld] | None:
    """Resolve ``generator_id`` and sample ``doc`` fresh; ``None`` on any failure.

    Returns the regenerated ensemble *and* the numeric world it was sampled from, so a
    caller reads conditioning targets off the SAME projection the generator was handed
    rather than off the raw JSON dict -- two representations of one quantity otherwise --
    and so ``load_worldspec`` runs once per regeneration instead of twice.
    """
    return _regenerate_cached(canonical_json(doc), generator_id, n_paths, seed)


def _pooled_errors(
    generator_id: str,
    seed: int,
    world_items: tuple[tuple[int, dict[str, Any]], ...],
    error_fn: ErrorFn,
    *,
    n_paths: int = CONDITIONAL_RESAMPLE_N_PATHS,
) -> np.ndarray:
    """Pooled per-path error array across every ``(k, doc)`` in ``world_items``.

    Returns a single-NaN array (poisoning every downstream aggregate) if ANY world's
    regeneration fails, the regenerated ensemble cannot produce a non-empty error
    array, or any produced error is non-finite -- see the module docstring's
    "Anti-gaming floor" for why this never silently drops to a smaller surviving pool.
    """
    _poison = np.array([float("nan")])
    pooled: list[np.ndarray] = []
    for k, doc in world_items:
        regen = _regenerate(doc, generator_id, n_paths, seed + _SEED_STRIDE * k)
        if regen is None:
            return _poison
        errors = error_fn(*regen)
        if errors.size == 0 or not bool(np.all(np.isfinite(errors))):
            return _poison
        pooled.append(errors)
    if not pooled:
        return _poison
    return np.concatenate(pooled)


def _mean_metric(pool: Callable[[Ensemble], np.ndarray]) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        errors = pool(ensemble)
        if errors.size < CONDITIONAL_MIN_OBS or not bool(np.all(np.isfinite(errors))):
            return float("nan")
        return float(np.mean(errors))

    return fn


def _p90_metric(pool: Callable[[Ensemble], np.ndarray]) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        errors = pool(ensemble)
        if errors.size < CONDITIONAL_MIN_OBS or not bool(np.all(np.isfinite(errors))):
            return float("nan")
        return float(np.percentile(errors, 90))

    return fn


# --------------------------------------------------------------------------- #
# Part A: per-condition-type error functions over a checked-in world document
# --------------------------------------------------------------------------- #


_EMPTY = np.empty(0, dtype=np.float64)


def _inflation_world_error(regen: Ensemble, world: NumericWorld) -> np.ndarray:
    cond = world.factor_conditions.inflation
    if cond is None or cond.average_pct is None:
        return _EMPTY
    return inflation_error_per_path(regen, float(cond.average_pct))


def _rate_world_error(regen: Ensemble, world: NumericWorld) -> np.ndarray:
    cond = world.factor_conditions.policy_rate
    if cond is None:
        return _EMPTY
    start = cond.start_pct
    end = cond.end_pct
    return rate_error_per_path(
        regen, None if start is None else float(start), None if end is None else float(end)
    )


def _crisis_timing_world_error(regen: Ensemble, world: NumericWorld) -> np.ndarray:
    windows = world.factor_conditions.crisis_windows
    if not windows:
        return _EMPTY
    return crisis_timing_error_per_path(regen, _crisis_window_target_quarter(windows[0]))


def _crisis_severity_world_error(regen: Ensemble, world: NumericWorld) -> np.ndarray:
    windows = world.factor_conditions.crisis_windows
    if not windows:
        return _EMPTY
    return crisis_severity_error_per_path(regen, float(windows[0].severity))


_ERROR_FNS: dict[str, ErrorFn] = {
    "inflation": _inflation_world_error,
    "rate": _rate_world_error,
    "crisis_timing": _crisis_timing_world_error,
    "crisis_severity": _crisis_severity_world_error,
}


def _make_condition_pool(condition_type: str) -> Callable[[Ensemble], np.ndarray]:
    world_items = _worlds_for_type(condition_type)
    error_fn = _ERROR_FNS[condition_type]

    def pool(ensemble: Ensemble) -> np.ndarray:
        return _pooled_errors(ensemble.meta.generator_id, ensemble.meta.seed, world_items, error_fn)

    return pool


# --------------------------------------------------------------------------- #
# Part B: off-support sweep (inflation, rate only -- see module docstring)
# --------------------------------------------------------------------------- #


def _support_mean_std(
    reference: ReferenceStats, factor: str, transform: Callable[[np.ndarray], np.ndarray]
) -> tuple[float, float] | None:
    series = reference.historical_series.get(factor)
    if series is None or series.empty:
        return None
    values = transform(series.to_numpy(dtype=np.float64))
    values = values[np.isfinite(values)]
    if values.size < 2:
        return None
    std = float(np.std(values, ddof=1))
    if std == 0.0 or not np.isfinite(std):
        return None
    return float(np.mean(values)), std


def _yoy_1d(level: np.ndarray) -> np.ndarray:
    return cpi_yoy_from_level(level.reshape(1, -1)).reshape(-1)


def _identity_1d(level: np.ndarray) -> np.ndarray:
    return level


def _clip(value: float, bounds: tuple[float, float]) -> float:
    return float(min(max(value, bounds[0]), bounds[1]))


@lru_cache(maxsize=1)
def _off_support_bounds() -> dict[str, tuple[float, float]]:
    """Each swept field's ``(minimum, maximum)``, READ FROM the WorldSpec JSON Schema.

    ``schemas/`` is the contract and the only definition of these numbers
    (``CLAUDE.md``); restating them here as literals would be two independent definitions
    of one quantity, and the failure mode is concrete: tighten the schema without
    updating the copy and every swept target above the new bound builds a document
    :func:`ah.core.loader.load_worldspec` rejects. Reading them means a schema change
    simply moves the clip.

    Raises :class:`ConditionalFixtureError` if a swept field has no bounds in the schema
    at all -- an unbounded swept field would let ``z=4.0`` construct an arbitrary target,
    which is not something to discover at battery time.
    """
    props = worldspec_schema()["properties"]["factor_conditions"]["properties"]
    bounds: dict[str, tuple[float, float]] = {}
    for ctype in OFF_SUPPORT_TYPES:
        group, field = _SWEPT_FIELD[ctype]
        node = props[group]["properties"][field]
        if "minimum" not in node or "maximum" not in node:
            raise ConditionalFixtureError(
                f"schemas/worldspec-v1.0.schema.json: factor_conditions.{group}.{field} "
                f"declares no minimum/maximum, so the off-support sweep has nothing to "
                f"clip a z=4.0 target into"
            )
        bounds[ctype] = (float(node["minimum"]), float(node["maximum"]))
    return bounds


_SWEEP_WORLD_BASE: dict[str, Any] = {
    "spec_version": "1.0.0",
    "status": "validated",
    "provenance": {
        "created_at": "2026-07-24T00:00:00Z",
        "author": "sso:wp22-task6",
        "source": {"kind": "manual"},
    },
    "narrative": {
        "language": "en",
        "title": "Off-support sweep probe",
        "tagline": "A synthetic conditioning target",
        "summary": (
            "A programmatically constructed world used only to sweep one condition "
            "dimension to a stated distance from the train+validation support -- not a "
            "scenario for a user."
        ),
        "lesson": "A WP2.2 Task 6 battery fixture, built at suite-registration time.",
        "dispatches": [
            {"date": "2027", "headline": "A synthetic sweep target begins", "detail": "n/a"},
            {"date": "2030", "headline": "The horizon continues", "detail": "n/a"},
            {"date": "2033", "headline": "The horizon closes", "detail": "n/a"},
        ],
    },
    "horizon": {"start": "2027-Q1", "quarters": 40},
    "regimes": {"mode": "unconditional"},
    "structural": {"parameter_vintage": "historical_average"},
    "engine_defaults": {"generator_id": "bootstrap-stratified", "n_paths": 1000},
}


def _sweep_world(condition_type: str, level: str, target: float) -> dict[str, Any]:
    doc = copy.deepcopy(_SWEEP_WORLD_BASE)
    doc["world_id"] = f"conditional-offsupport-{condition_type}-{level}"
    group, field = _SWEPT_FIELD[condition_type]
    doc["factor_conditions"] = {group: {field: target}}
    doc["extensions"] = {"x_condition_type": condition_type, "x_intensity": level}
    return doc


@dataclass(frozen=True)
class _OffSupportLevel:
    level: str
    # (k, doc) pairs, k a globally unique regeneration index across every swept world --
    # see `_worlds_for_type`'s docstring for why k must not restart.
    world_items: tuple[tuple[int, dict[str, Any]], ...]
    error_fns: tuple[ErrorFn, ...]


def _build_off_support_levels(reference: ReferenceStats) -> tuple[_OffSupportLevel, ...]:
    """One :class:`_OffSupportLevel` per :data:`OFF_SUPPORT_LEVELS` entry.

    **All-or-nothing across :data:`OFF_SUPPORT_TYPES`.** If any swept type lacks a usable
    train+validation support distribution, EVERY level is built with no worlds at all --
    so every Part B metric NaNs rather than reporting the surviving arm alone under a
    sealed name whose own definition says "across BOTH swept types". See the module
    docstring's "Partial support poisons the level".
    """
    support: dict[str, tuple[float, float] | None] = {
        "inflation": _support_mean_std(reference, "cpi", _yoy_1d),
        "rate": _support_mean_std(reference, "policy_rate", _identity_1d),
    }
    if any(support[ctype] is None for ctype in OFF_SUPPORT_TYPES):
        return tuple(
            _OffSupportLevel(level=name, world_items=(), error_fns=())
            for name, _ in OFF_SUPPORT_LEVELS
        )

    bounds = _off_support_bounds()
    levels: list[_OffSupportLevel] = []
    k = 0
    for level_name, z in OFF_SUPPORT_LEVELS:
        world_items: list[tuple[int, dict[str, Any]]] = []
        error_fns: list[ErrorFn] = []
        for ctype in OFF_SUPPORT_TYPES:
            stats = support[ctype]
            assert stats is not None  # guarded above; narrows for the type checker
            mean, std = stats
            target = _clip(mean + z * std, bounds[ctype])
            # Distinct seed range from Part A's (k = 0..n_fixtures) -- offset by 1000 so
            # the two parts' regenerations never collide for the same base ensemble, and
            # incremented across levels so every swept world has its own seed too.
            world_items.append((1000 + k, _sweep_world(ctype, level_name, target)))
            error_fns.append(_ERROR_FNS[ctype])
            k += 1
        levels.append(
            _OffSupportLevel(
                level=level_name, world_items=tuple(world_items), error_fns=tuple(error_fns)
            )
        )
    return tuple(levels)


def _off_support_pooled_errors(level: _OffSupportLevel, ensemble: Ensemble) -> np.ndarray:
    """Like :func:`_pooled_errors`, but each world carries its OWN error_fn (inflation
    and rate are pooled together here, so a single shared ``error_fn`` will not do)."""
    _poison = np.array([float("nan")])
    if not level.world_items:
        return _poison
    pooled: list[np.ndarray] = []
    for (k, doc), error_fn in zip(level.world_items, level.error_fns, strict=True):
        seed = ensemble.meta.seed + _SEED_STRIDE * k
        regen = _regenerate(doc, ensemble.meta.generator_id, CONDITIONAL_RESAMPLE_N_PATHS, seed)
        if regen is None:
            return _poison
        errors = error_fn(*regen)
        if errors.size == 0 or not bool(np.all(np.isfinite(errors))):
            return _poison
        pooled.append(errors)
    if not pooled:
        return _poison
    return np.concatenate(pooled)


def _off_support_adherence_metric(level: _OffSupportLevel) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        errors = _off_support_pooled_errors(level, ensemble)
        if errors.size < CONDITIONAL_MIN_OBS or not bool(np.all(np.isfinite(errors))):
            return float("nan")
        return float(np.mean(errors))

    return fn


def _off_support_pass_rate_metric(level: _OffSupportLevel) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        errors = _off_support_pooled_errors(level, ensemble)
        if errors.size < CONDITIONAL_MIN_OBS or not bool(np.all(np.isfinite(errors))):
            return float("nan")
        return float(np.mean(errors <= OFF_SUPPORT_PASS_TOLERANCE_PCT))

    return fn


# --------------------------------------------------------------------------- #
# build_conditional_suite / register_conditional_suite
# --------------------------------------------------------------------------- #


def conditional_mc_error(
    fn: MetricFn, ensemble: Ensemble, *, seed: int, n_subsamples: int
) -> float:
    """This suite's Monte-Carlo error: the spread over REGENERATION seeds.

    Signature-compatible with :func:`ah.eval.battery.mc_error` so it can be dropped into
    :attr:`~ah.eval.battery.MetricSpec.mc_error_fn`, but both of that function's tuning
    arguments are deliberately unused:

    - ``seed`` drives a ``permutation`` of the PASSED ensemble's paths there. No metric
      here reads those paths, and nothing in this estimator draws a random number at all
      -- the replicate seeds are fixed arithmetic on ``ensemble.meta.seed``, which is what
      makes the reported error bit-reproducible for a given ensemble rather than a
      function of whichever MC seed the battery was invoked with.
    - ``n_subsamples`` is bounded by the passed ensemble's path count
      (:func:`ah.eval.battery._n_subsamples_for`). That count is meaningless here: a
      2-path placeholder ensemble does not limit how many independent regenerations are
      available. :data:`CONDITIONAL_MC_ERROR_REPLICATES` decides instead.

    Returns ``std(replicates, ddof=1)`` -- NOT divided by ``sqrt(k)``; see the module
    docstring's Monte-Carlo section for why the batch-means rescaling does not apply.
    NaN in (an uncomputable metric) gives NaN out, which is the honest answer and which
    :func:`ah.eval.battery._require_mc_error_reported` accepts by design.
    """
    del seed, n_subsamples
    estimates = np.empty(CONDITIONAL_MC_ERROR_REPLICATES, dtype=np.float64)
    for r in range(CONDITIONAL_MC_ERROR_REPLICATES):
        replicate_meta = replace(
            ensemble.meta, seed=ensemble.meta.seed + _MC_REPLICATE_STRIDE * (r + 1)
        )
        replicate = Ensemble(
            paths=ensemble.paths, factor_names=ensemble.factor_names, meta=replicate_meta
        )
        estimates[r] = fn(replicate)
    return float(np.std(estimates, ddof=1))


def _spec(name: str, fn: MetricFn) -> MetricSpec:
    return MetricSpec(name=name, tier=TIER, fn=fn, suite=SUITE, mc_error_fn=conditional_mc_error)


def build_conditional_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """Every ``conditional``-tier :class:`~ah.eval.battery.MetricSpec`.

    ``manifest`` is accepted for signature symmetry with every other
    ``ah.eval.battery._REFERENCE_DEPENDENT_SUITE_BUILDERS`` entry but unused -- see the
    module docstring's "Registration is deferred". ``reference`` supplies Part B's
    train+validation support distributions (``historical_series``) only.

    Clears :func:`_regenerate`'s memo first, so a cached ensemble never outlives the
    registry state and reference it was produced under (see :func:`_regenerate_cached`).
    """
    del manifest
    clear_regeneration_cache()
    specs: list[MetricSpec] = []
    for ctype in CONDITION_TYPES:
        pool = _make_condition_pool(ctype)
        specs.append(_spec(f"condition_adherence_error_{ctype}", _mean_metric(pool)))
        specs.append(_spec(f"condition_adherence_error_p90_{ctype}", _p90_metric(pool)))
    for level in _build_off_support_levels(reference):
        specs.append(
            _spec(f"off_support_adherence_at_{level.level}", _off_support_adherence_metric(level))
        )
        specs.append(
            _spec(f"off_support_pass_rate_at_{level.level}", _off_support_pass_rate_metric(level))
        )
    return tuple(specs)


def register_conditional_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("conditional", build_conditional_suite(manifest, reference))``."""
    register_suite(SUITE, build_conditional_suite(manifest, reference))
