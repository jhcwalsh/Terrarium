"""The 1-5yr and 10yr horizon tiers (WP2.2 Task 3).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``horizon.py`` bullet, and DN-1.1 Sec.II.6 rows 2-3,
which are NORMATIVE for which tier each metric belongs to:

    | tier   | metrics                                                         |
    |--------|------------------------------------------------------------------|
    | 1_5yr  | variance ratios; mean-reversion half-lives; regime duration       |
    |        | distributions; drawdown depth/duration joint distribution         |
    | 10yr   | lost-decade frequency; long-inflation-era frequency; 10y return   |
    |        | vs starting valuation (slope, R^2); ergodicity                    |

Every metric here is registered at the tier its own DN-1.1 row states -- ``1_5yr`` or
``10yr``, never ``monthly`` (this module's model, ``ah.eval.metrics.monthly``, is the
only ``monthly``-tier suite).

Where the definitions live, and why not here
----------------------------------------------
Exactly as in ``ah.eval.metrics.monthly`` (see that module's docstring for the full
argument): **every statistic this suite reports is defined in :mod:`ah.eval.reference`,
not in this module.** :mod:`ah.eval.prereg` validates a threshold key's ``<stat>``
against :data:`~ah.eval.reference.SINGLE_FACTOR_STATS` / ``PANEL_STATS``, and once
``sealed: true`` lands :func:`ah.eval.battery.run_battery` calls
:func:`ah.eval.prereg.verify` on every invocation -- a statistic defined only here could
never carry a sealed threshold, and an entry authored under its name would break every
battery run. This module contributes only the ensemble-level pooling convention and the
absent-factor NaN guard, exactly as ``monthly.py`` does; it restates no formula.

Per-path vs pooled, stated per metric (RFR-15 bites here)
------------------------------------------------------------
``governance/retrofit-register.md`` RFR-15 (opened by WP2.2 Task 2) is that a reference
bootstrap replicate drawn at ``resample_length=ensemble.months`` is length-matched
correctly for a PER-PATH statistic (both sides see the same series length, so both
carry the same estimator bias) but NOT for a POOLED one (the ensemble side pools
``n_paths * (something)`` observations while a replicate carries only ``months``, or --
for the single-indicator-per-series statistics below -- exactly ``months``). Every
metric in this suite is one of the following, stated explicitly rather than left for
WP2.3 to discover:

- **Per-path, averaged** (:func:`ah.eval.metrics._pooling.mean_over_paths`, the single
  shared definition both this suite and ``monthly.py`` now call -- they used to hold
  character-identical private copies, which is two implementations of one sealed
  convention): ``mean_reversion_halflife``. An AR(1) half-life is a property of ONE path's own
  time-ordered series; concatenating paths before fitting it would manufacture a
  spurious lag-1 relationship at every path seam, exactly as ``monthly.py``'s ACF
  statistics warn against.
- **Truly pooled, via concatenation of per-path arrays** (never a bare per-path mean of
  per-path scalars -- see each helper below): ``variance_ratio_{12,36,60,120}m``
  (non-overlapping k-month sums computed independently WITHIN each path via
  :func:`~ah.eval.reference.nonoverlapping_sums`, then concatenated across paths --
  the exact convention ``monthly.py``'s ``agg_gaussianity`` already uses for a
  marginal-distribution statistic) and ``drawdown_median_depth`` /
  ``drawdown_median_duration`` / ``drawdown_depth_duration_rank_corr`` (drawdown
  episodes extracted independently within each path via
  :func:`~ah.eval.reference.drawdown_episodes`, then concatenated). RFR-15's residual
  applies to all of these: the reference band is drawn at ``resample_length=
  ensemble.months``, a SINGLE path's worth of data, while the pooled ensemble-side
  value draws on ``n_paths`` times as much -- the two sides are not sample-size-matched,
  and (for variance and the rank correlation) not bias-matched either. Stated here, not
  discovered at seal time.
- **A decade-window frequency, computed per path and averaged**
  (:func:`_pooled_window_frequency_over_paths`): ``lost_decade_frequency``,
  ``long_inflation_era_frequency``. Each estimator is the fraction of ITS INPUT'S OWN
  overlapping 120-month windows satisfying a property (see
  :func:`ah.eval.reference.lost_decade_frequency`), so a production 120-month path
  carries exactly one window and the per-path average IS the pooled frequency over
  paths; at a longer path length each path contributes equally many windows and the
  identity still holds.

  **What an earlier version of this paragraph claimed, and why it was wrong** (WP2.2
  Task 3 fix pass 1, Critical 1): it said these two "are not sample-size-mismatched
  against their own reference band", on the grounds that a resample of length
  ``ensemble.months`` is one decade and the estimator was one indicator per decade. Both
  halves were false. The estimator was a single 0.0/1.0 indicator over the whole input
  with no internal windowing, and ``block_bootstrap_band`` takes PERCENTILES of the
  replicate values rather than their mean -- so the historical frequency was never
  formed anywhere and the band was the 5th/95th percentile of a Bernoulli variable:
  ``[0, 1]`` or ``[0, 0]``/``[1, 1]``. Both estimators now window internally, and both
  are registered ``length_matched=False`` so their replicates are drawn at the full
  train+validation length -- stated in the sealed definition, since it is a deliberate
  and necessary departure from ``conventions.estimator_length_matching``'s default.
- **No ensemble-side convention applies at all, because the input does not exist**:
  ``ergodicity_gap``. DN-1.1 Sec.II.6 defines it as a LONG-PATH-vs-ENSEMBLE comparison,
  and :func:`ah.eval.battery.run_battery` is handed one ``Ensemble`` of
  production-length paths and no long path. See "Three structural gaps" below.
- **Structural gaps, always NaN**: ``regime_duration_{mean,p50,p90}`` /
  ``ten_year_return_vs_valuation_{slope,r2}`` (see below), so the per-path/pooled
  question does not arise on any ensemble that exists today.

Three structural gaps, made NaN, MARKED, rather than faked
-------------------------------------------------------------
Three DN-1.1-listed metric groups need an input that does not exist anywhere in the
platform today -- not "absent from this particular ensemble" (the routine, per-ensemble
case ``ah.gen.base.UnknownFactorError`` exists for), but absent for every generator,
always, until the manifest or the generator layer is extended.

**They are marked, not merely NaN** (WP2.2 Task 3 fix pass 1). ``MetricSpec.status`` is
``"structurally_unavailable"`` on every one of them, and :meth:`
ah.eval.battery.BatteryReport.to_dict` and the markdown both carry it. A bare NaN is
byte-identical in the report to a genuine generator failure, and under THE ONE NaN RULE
an ``enforce`` threshold on one of these names would fail **every run forever** -- so a
WP2.3 reader must be able to tell the two apart from the artifact alone, without
reading this docstring.

The two whose missing input is a FACTOR MAPPING in ``factors.yaml``:

- ``regime_duration_{mean,p50,p90}``: the Step-1 regime ruleset
  (:func:`ah.data.derive.label_regime`) classifies a month from FIVE inputs --
  ``usrec``, ``cpi_yoy``, ``growth_yoy``, ``drawdown``, ``hy_oas``. Three are
  constructible from generated factors (``cpi`` -> cpi_yoy, ``equity_mkt`` ->
  drawdown, ``hy_spread`` -> hy_oas), but ``usrec`` (an NBER recession indicator) and
  ``growth_yoy`` (industrial-production growth) are registered Step-1 catalog series
  (``fred.USREC``, ``fred.INDPRO`` -- see ``requirements.yaml``) with NO factor
  mapping in ``factors.yaml`` at all: they are DN-1.1 Sec.II.2's Layer-1 "climate"
  state variables, not yet exposed as Step-2 generator-visible output factors. Calling
  ``label_regime`` needs concrete values for all five; two cannot honestly be supplied
  from anything a generator (bootstrap or otherwise) produces today. Rather than
  inventing a substitute value for the missing two (which would silently bias every
  classification toward whatever default was chosen), this suite reports NaN --
  honestly reflecting "not yet measurable" per THE ONE NaN RULE -- and the ruleset
  version this metric WOULD use, once the gap closes, is recorded here for
  traceability (WP2.6 refits on these labels and the plan requires the ruleset version
  be traceable): :data:`REGIME_RULESET_VERSION`.
- ``ten_year_return_vs_valuation_{slope,r2}``: needs a starting-valuation series
  (``cape_v`` / demeaned log CAPE, :func:`ah.data.derive.demeaned_log_cape`). The raw
  ``shiller.cape`` series is registered in ``requirements.yaml``, but no factor in
  ``factors.yaml`` maps to it -- the same Layer-1-climate-state gap as above, for the
  valuation state ``v_t`` this time.

The third, whose missing input is a GENERATOR CAPABILITY rather than a factor:

- ``ergodicity_gap``: DN-1.1 Sec.II.6's 10yr row defines it as "ergodicity (**long-path
  vs ensemble** stats)" -- the time average of one long single realization against the
  cross-sectional average of an ensemble (:func:`ah.eval.reference.ergodicity_gap`
  implements exactly that, and is tested against both an ergodic and a genuinely
  non-ergodic process). :func:`ah.eval.battery.run_battery` receives one
  :class:`~ah.gen.base.Ensemble` of production-length paths and no long path, so there
  is nothing to put in the first argument, and no generator exists yet to ask for one.
  The previous implementation avoided that by taking both sides from the same 120-month
  ensemble -- which made it algebraically ``|variance_ratio_120m - 1|`` at production
  path length (two sealed names, one number, the duplication this file already refused
  for ``agg_gaussianity`` horizon 1) and rested it on an iid-within-path null under
  which a *correct* generator of any persistent factor reads as catastrophically
  non-ergodic. Recorded as ``governance/retrofit-register.md`` RFR-20.

All three are recorded in ``governance/retrofit-register.md`` (RFR-17, RFR-18, RFR-20)
as the commodities/UK-block gaps are (RFR-1/RFR-3): a stated, dated limitation, not a
silent one, with an owner (WP2.3, or whichever WP first supplies the missing input) and
a consequence (every threshold sealed under these six names is sealed against a metric
that cannot yet fail OR pass meaningfully -- see :func:`ah.eval.battery._passed`, NaN
already fails an ``enforce`` bound).

Registration is deferred, and now has a caller
-------------------------------------------------
Exactly as ``monthly.py``: this suite needs a computed
:class:`~ah.eval.reference.ReferenceStats` and a :class:`~ah.factors.FactorManifest` to
construct its specs at all, so it registers through :func:`build_horizon_suite` /
:func:`register_horizon_suite` rather than as an import-time side effect.
:func:`ah.eval.battery.run_full_battery` is the production caller (via
``battery._REFERENCE_DEPENDENT_SUITE_BUILDERS``'s ``"horizon"`` row, this task's
addition).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ah.data import derive
from ah.eval.battery import STRUCTURALLY_UNAVAILABLE, MetricFn, MetricSpec, register_suite
from ah.eval.metrics._pooling import mean_over_paths
from ah.eval.reference import (
    VARIANCE_RATIO_HORIZONS,
    ReferenceStats,
)
from ah.eval.reference import (
    drawdown_episodes as reference_drawdown_episodes,
)
from ah.eval.reference import (
    drawdown_median as reference_drawdown_median,
)
from ah.eval.reference import (
    drawdown_rank_corr as reference_drawdown_rank_corr,
)
from ah.eval.reference import (
    long_inflation_era_frequency as reference_long_inflation_era_frequency,
)
from ah.eval.reference import (
    lost_decade_frequency as reference_lost_decade_frequency,
)
from ah.eval.reference import (
    mean_reversion_halflife as reference_mean_reversion_halflife,
)
from ah.eval.reference import (
    nonoverlapping_sums as reference_nonoverlapping_sums,
)
from ah.eval.reference import (
    variance_ratio_from_arrays as reference_variance_ratio_from_arrays,
)
from ah.factors import FactorManifest
from ah.gen.base import Ensemble
from ah.strategies import load_conventions

SUITE = "horizon"
TIER_1_5YR = "1_5yr"
TIER_10YR = "10yr"

# Recorded for traceability (WP2.6 refits on these labels; the plan requires the
# ruleset version be traceable) -- see the module docstring's "Two structural gaps".
# ``regime_duration_*`` is NaN on every ensemble today (usrec/growth_yoy have no
# factor mapping), so this constant documents which ruleset version the metric WOULD
# be evaluated against once that gap closes, rather than leaving the traceability
# obligation unmet just because the metric cannot run yet.
REGIME_RULESET_VERSION = derive.regime_thresholds()["version"]

__all__ = [
    "REGIME_RULESET_VERSION",
    "SUITE",
    "TIER_1_5YR",
    "TIER_10YR",
    "build_horizon_suite",
    "register_horizon_suite",
]


# --------------------------------------------------------------------------- #
# pooling helpers -- see the module docstring's "Per-path vs pooled"
# --------------------------------------------------------------------------- #


# The one shared definition, aliased under this module's own name so a reader of a
# metric below can see which convention it uses without leaving the file. This IS
# ``monthly.py``'s helper -- the same function object, not a second copy.
_mean_over_paths = mean_over_paths


def _pooled_window_frequency_over_paths(
    fn: Callable[[np.ndarray], float], ensemble: Ensemble, factor: str
) -> float:
    """Apply a decade-window frequency estimator to each path independently, then
    average the per-path frequencies.

    Every path is the same length, so each contributes the same number of 120-month
    windows and the average of per-path frequencies IS the pooled frequency over all
    windows -- not merely an approximation to it (see the module docstring's "Per-path
    vs pooled"). At the production path length that number of windows is exactly one
    per path. NaN per-path outcomes (a path shorter than one decade, so it carries no
    window at all) are dropped, not averaged in as 0, matching
    :func:`ah.eval.metrics._pooling.mean_over_paths`'s convention -- so a generator
    emitting paths shorter than a decade reports NaN here rather than a frequency of 0.
    """
    return _mean_over_paths(fn, ensemble, factor)


def _pooled_variance_ratio(ensemble: Ensemble, factor: str, k: int) -> float:
    """Variance ratio at horizon ``k``, pooled across every path's own non-overlapping
    k-month sums (and its own raw monthly values) -- see the module docstring's
    "Truly pooled, via concatenation of per-path arrays".
    """
    slab = ensemble.factor(factor).astype(np.float64)
    sums_per_path = [reference_nonoverlapping_sums(slab[i], k) for i in range(slab.shape[0])]
    pooled_sums = np.concatenate(sums_per_path) if sums_per_path else np.empty(0, dtype=np.float64)
    pooled_raw = slab.reshape(-1)
    return reference_variance_ratio_from_arrays(pooled_sums, pooled_raw, k)


def _pooled_drawdown_episodes(ensemble: Ensemble, factor: str) -> tuple[np.ndarray, np.ndarray]:
    """Every drawdown episode of every path, pooled by concatenation -- episodes are
    extracted independently WITHIN each path (never spanning a path boundary) before
    being pooled, exactly as ``monthly.py``'s ``agg_gaussianity`` pools non-overlapping
    sums.
    """
    slab = ensemble.factor(factor).astype(np.float64)
    depths_per_path: list[np.ndarray] = []
    durations_per_path: list[np.ndarray] = []
    for i in range(slab.shape[0]):
        depths, durations = reference_drawdown_episodes(slab[i])
        depths_per_path.append(depths)
        durations_per_path.append(durations)
    depths = np.concatenate(depths_per_path) if depths_per_path else np.empty(0, dtype=np.float64)
    durations = (
        np.concatenate(durations_per_path) if durations_per_path else np.empty(0, dtype=np.float64)
    )
    return depths, durations


# --------------------------------------------------------------------------- #
# MetricSpec factories: guard against a factor absent from a given ensemble
# --------------------------------------------------------------------------- #


def _spec(
    name: str,
    tier: str,
    fn: MetricFn,
    *,
    status: str = "ok",
    metadata: tuple[tuple[str, str], ...] = (),
) -> MetricSpec:
    return MetricSpec(name=name, tier=tier, fn=fn, suite=SUITE, status=status, metadata=metadata)


def _variance_ratio_metric(factor: str, k: int) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return _pooled_variance_ratio(ensemble, factor, k)

    return fn


def _mean_reversion_halflife_metric(factor: str) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return _mean_over_paths(reference_mean_reversion_halflife, ensemble, factor)

    return fn


def _drawdown_median_depth_metric(factor: str) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        depths, _ = _pooled_drawdown_episodes(ensemble, factor)
        return reference_drawdown_median(depths)

    return fn


def _drawdown_median_duration_metric(factor: str) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        _, durations = _pooled_drawdown_episodes(ensemble, factor)
        return reference_drawdown_median(durations)

    return fn


def _drawdown_rank_corr_metric(factor: str) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        depths, durations = _pooled_drawdown_episodes(ensemble, factor)
        return reference_drawdown_rank_corr(depths, durations)

    return fn


def _lost_decade_frequency_metric(factor: str) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return _pooled_window_frequency_over_paths(
            reference_lost_decade_frequency, ensemble, factor
        )

    return fn


def _long_inflation_era_frequency_metric(factor: str) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if factor not in ensemble.factor_names:
            return float("nan")
        return _pooled_window_frequency_over_paths(
            reference_long_inflation_era_frequency, ensemble, factor
        )

    return fn


def _structural_gap_metric() -> MetricFn:
    """Always NaN -- see the module docstring's "Three structural gaps".

    Deliberately ignores its ensemble: the missing input is missing for every
    ensemble, so reading one would only make the NaN look conditional. Every spec
    built on this carries ``status=STRUCTURALLY_UNAVAILABLE`` so the report says which
    kind of NaN it is.
    """

    def fn(ensemble: Ensemble) -> float:
        del ensemble
        return float("nan")

    return fn


# --------------------------------------------------------------------------- #
# build_horizon_suite / register_horizon_suite
# --------------------------------------------------------------------------- #


def build_horizon_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """Every horizon-tier :class:`~ah.eval.battery.MetricSpec`, for ``manifest``'s
    active factors. ``reference`` is accepted for signature symmetry with
    :func:`ah.eval.metrics.monthly.build_monthly_suite` (every reference-dependent
    suite builder shares one call shape in
    ``ah.eval.battery._REFERENCE_DEPENDENT_SUITE_BUILDERS``) but is not read: every
    metric here is either computed purely from the ensemble (variance ratio,
    half-life, drawdown, lost-decade, long-inflation-era, ergodicity) or is a
    structural-gap NaN stub that needs no reference at all (see the module
    docstring).
    """
    del reference  # signature symmetry only -- see docstring
    specs: list[MetricSpec] = []
    active = manifest.active_factors()
    conventions = load_conventions()
    return_bearing = conventions.return_bearing_factors

    for factor in active:
        for k, suffix in VARIANCE_RATIO_HORIZONS:
            specs.append(
                _spec(
                    f"{factor}.variance_ratio_{suffix}",
                    TIER_1_5YR,
                    _variance_ratio_metric(factor, k),
                )
            )
        specs.append(
            _spec(
                f"{factor}.mean_reversion_halflife",
                TIER_1_5YR,
                _mean_reversion_halflife_metric(factor),
            )
        )
        # Structural gap, not a computable metric (see the module docstring's third
        # bullet): DN-1.1's definition needs a LONG PATH the battery is never handed.
        specs.append(
            _spec(
                f"{factor}.ergodicity_gap",
                TIER_10YR,
                _structural_gap_metric(),
                status=STRUCTURALLY_UNAVAILABLE,
                metadata=(("requires", "single long path (RFR-20)"),),
            )
        )

    # Drawdown and lost-decade need a compoundable RETURN series (see
    # reference.py's drawdown_episodes/lost_decade_frequency docstrings) -- restricted
    # to the sealed return_bearing_factors classification, not applied uniformly to
    # every active factor the way variance ratio/half-life/ergodicity are, because
    # compounding a LEVEL series (a rate, a spread, an index) via (1+level).cumprod()
    # is not merely uninformative, it is numerically wrong (a level near 300 "returns"
    # would blow up to an astronomical compounded wealth).
    for factor in active:
        if factor not in return_bearing:
            continue
        specs.append(
            _spec(
                f"{factor}.drawdown_median_depth", TIER_1_5YR, _drawdown_median_depth_metric(factor)
            )
        )
        specs.append(
            _spec(
                f"{factor}.drawdown_median_duration",
                TIER_1_5YR,
                _drawdown_median_duration_metric(factor),
            )
        )
        specs.append(
            _spec(
                f"{factor}.drawdown_depth_duration_rank_corr",
                TIER_1_5YR,
                _drawdown_rank_corr_metric(factor),
            )
        )
        specs.append(
            _spec(
                f"{factor}.lost_decade_frequency", TIER_10YR, _lost_decade_frequency_metric(factor)
            )
        )

    # long_inflation_era_frequency is inherently ABOUT inflation, unlike the
    # factor-agnostic mathematical operations above -- applied only to `cpi`, the
    # manifest's one inflation-index factor, never to every active factor uniformly
    # (running "sustained high-CPI-style-run" logic on, say, equity_vol's own level
    # would not measure an inflation era at all).
    if "cpi" in active:
        specs.append(
            _spec(
                "cpi.long_inflation_era_frequency",
                TIER_10YR,
                _long_inflation_era_frequency_metric("cpi"),
            )
        )

    # Structural gaps (see module docstring): always NaN on any ensemble today, and
    # MARKED as such so a NaN here is distinguishable in the report from a generator
    # that simply failed to produce a number. The regime metrics also carry the ruleset
    # version they would be evaluated under once the gap closes -- WP2.6 refits on
    # these labels and the plan requires that version be traceable, which a module
    # constant nothing reads is not.
    regime_metadata = (("regime_ruleset_version", REGIME_RULESET_VERSION), ("gap", "RFR-17"))
    for name in ("regime_duration_mean", "regime_duration_p50", "regime_duration_p90"):
        specs.append(
            _spec(
                name,
                TIER_1_5YR,
                _structural_gap_metric(),
                status=STRUCTURALLY_UNAVAILABLE,
                metadata=regime_metadata,
            )
        )
    for name in ("ten_year_return_vs_valuation_slope", "ten_year_return_vs_valuation_r2"):
        specs.append(
            _spec(
                name,
                TIER_10YR,
                _structural_gap_metric(),
                status=STRUCTURALLY_UNAVAILABLE,
                metadata=(("gap", "RFR-18"),),
            )
        )

    return tuple(specs)


def register_horizon_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("horizon", build_horizon_suite(manifest, reference))``."""
    register_suite(SUITE, build_horizon_suite(manifest, reference))
