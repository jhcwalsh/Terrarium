"""The validation battery orchestrator (WP2.2 Task 1).

Replaces Step 0's skeleton (``ah.battery.report``, which stays in place -- see its
module docstring and ``governance/retrofit-register.md`` for its fate, a WP2.3
decision, not this module's). This is the Step-2 battery: it runs every metric suite
registered in :data:`SUITES` over a generator :class:`~ah.gen.base.Ensemble`, attaches
a Monte-Carlo error bar to every result, looks each metric up against the train+
validation :class:`~ah.eval.reference.ReferenceStats` bands and
:class:`~ah.eval.prereg.PreRegistration` thresholds, and emits a :class:`BatteryReport`
in both JSON and markdown.

Registration, and who performs it
-----------------------------------
Tasks 2-6 add metric suites (``monthly``, ``horizon``, ``tails``, ``utility``,
``memorization``, ``economics``, ``conditional``, ``calibration``) by calling
:func:`register_suite`; :func:`run_battery` iterates :data:`SUITES` generically. Adding
a suite must never require editing this module -- proved by
``tests/test_eval_battery.py``, which registers a throwaway suite and shows it appears
in a report without touching :func:`run_battery`.

An earlier version of this docstring said suites register "at import time". They cannot,
and none does: a suite whose specs depend on a computed
:class:`~ah.eval.reference.ReferenceStats` (``monthly``'s
``cross_block_corr_matrix_distance`` is a distance *to* the historical correlation
matrix) has nothing to register until a reference exists, and computing one needs a live
:class:`~ah.splits.DataAccess`. Those suites expose a
``build_<suite>(manifest, reference)`` builder instead, and
:func:`register_reference_dependent_suites` -- called by :func:`run_full_battery`, the
production entry point -- performs the registration once the reference has been
computed. Stating an import-time rule that no code follows, in a file the
pre-registration seal hashes, is how a seal comes to look stronger than it is; hence
this paragraph rather than the old sentence.

Two entry points
-----------------
:func:`run_full_battery` is the one to call: it computes the train+validation reference
from the catalog (at the ensemble's own path length -- see
:func:`ah.eval.reference.block_bootstrap_band`), registers every reference-dependent
suite against it, and runs the battery. :func:`run_battery` is the lower layer, for a
caller that already holds a :class:`~ah.eval.reference.ReferenceStats` and has
registered its own suites (every test in ``tests/test_eval_battery.py`` does).

Monte-Carlo error
------------------
Every ensemble-level metric gets a Monte-Carlo error bar via :func:`mc_error`: the
metric is recomputed on ``n_subsamples`` disjoint groups of an ensemble's paths (drawn
from a fresh ``numpy.random.Generator(PCG64(seed))``, never a global RNG), and the
error reported is the standard error of those per-subsample estimates -- see
:func:`mc_error`'s docstring for the batch-means argument that this recovers the
correct order of magnitude for a metric that is itself a sample mean.

Tiers
-----
DN-1.1 Sec.II.6's five horizon tiers, used verbatim (``ah.eval.reference`` already
uses these exact strings): ``monthly``, ``1_5yr``, ``10yr``, ``economic``, ``severe``.

Filtered vs. unfiltered
------------------------
Where an acceptance filter has been applied upstream (WP2.7's L4 assembly filter,
not built yet), pass its output as ``filtered=``; :func:`run_battery` runs every suite
over *both* ``ensemble`` and ``filtered`` and :class:`BatteryReport` carries both --
the plan is explicit that the filter may not teach to the exam, so both are always
reported side by side rather than the filtered view silently replacing the raw one.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

import numpy as np

from ah.eval import prereg as prereg_mod
from ah.eval.prereg import PreRegistration, Threshold
from ah.eval.reference import (
    DEFAULT_BLOCK_LENGTH,
    FactorCoverage,
    ReferenceStats,
    StatBand,
    compute_reference,
)
from ah.factors import FactorManifest
from ah.gen.base import Ensemble
from ah.splits import DataAccess

BATTERY_VERSION = "eval-battery-0.1"

# DN-1.1 Sec.II.6's five horizon tiers, in report order. Fixed and exhaustive: a
# MetricSpec naming any other string is rejected by register_suite().
TIERS: tuple[str, ...] = ("monthly", "1_5yr", "10yr", "economic", "severe")

# How many disjoint subsamples mc_error() draws per metric by default. Bounded by the
# ensemble's own path count (see _n_subsamples_for) so a small test ensemble never
# trips mc_error's "fewer paths than subsamples" guard.
_DEFAULT_MC_SUBSAMPLES = 20


class BatteryError(RuntimeError):
    """Raised for a malformed suite registration or an unrunnable battery."""


MetricFn = Callable[[Ensemble], float]


@dataclass(frozen=True)
class MetricSpec:
    """One registered metric: a name, its DN-1.1 horizon tier, its function, its suite.

    ``name`` follows the same key convention :mod:`ah.eval.reference` and
    :mod:`ah.eval.prereg` use, so a metric's result can be matched against a reference
    band / sealed threshold by name alone: ``"<factor>.<stat>"`` for a single-factor
    metric, ``"<factorA>~<factorB>.<stat>"`` for a cross-block metric. A metric with no
    matching band/threshold is still computed and reported (severity ``"report"``,
    ``passed=None``) -- not every useful metric needs a sealed band.
    """

    name: str
    tier: str
    fn: MetricFn
    suite: str


@dataclass(frozen=True)
class MetricResult:
    """One metric's outcome for one ensemble."""

    name: str
    suite: str
    tier: str
    value: float
    mc_error: float | None
    band: StatBand | None
    severity: str
    passed: bool | None


# suite name -> its registered MetricSpecs, in registration order. Tasks 2-6 populate
# this via register_suite(); run_battery() iterates it generically (sorted by suite
# name, for a deterministic report independent of import order).
#
# TODO(WP2.2 Tasks 3-6): only `monthly` exists, so a real battery run today covers the
# monthly tier and nothing else -- `run_full_battery` registers exactly what
# _REFERENCE_DEPENDENT_SUITE_BUILDERS names. Every remaining suite (horizon, tails,
# utility, memorization, economics, conditional, calibration) must be added to that
# table (or register itself) as it lands, or it will be written, tested, and then never
# run. Tracked as governance/retrofit-register.md RFR-13; the verdict a partial battery
# produces is a partial verdict and WP2.3 must not read it as a full one.
SUITES: dict[str, tuple[MetricSpec, ...]] = {}


def register_suite(suite: str, specs: Iterable[MetricSpec]) -> None:
    """Register ``suite``'s metrics. Registration only -- never edits :func:`run_battery`.

    Rejects: an empty suite name or empty spec list; a spec whose ``suite`` disagrees
    with the name it is registered under; a spec with an unknown ``tier``; a duplicate
    metric name within the suite; re-registering a suite name already present (call
    sites needing to replace a suite in a test should mutate :data:`SUITES` directly
    via ``monkeypatch``, not this function, which is the one-shot production path).
    """
    if not suite:
        raise BatteryError("register_suite: suite name must be a non-empty string")
    specs_tuple = tuple(specs)
    if not specs_tuple:
        raise BatteryError(f"register_suite: suite '{suite}' has no metrics to register")
    if suite in SUITES:
        raise BatteryError(f"register_suite: suite '{suite}' is already registered")

    seen_names: set[str] = set()
    for spec in specs_tuple:
        if spec.suite != suite:
            raise BatteryError(
                f"register_suite: spec '{spec.name}' declares suite={spec.suite!r}, "
                f"expected {suite!r}"
            )
        if spec.tier not in TIERS:
            raise BatteryError(
                f"register_suite: spec '{spec.name}' has unknown tier {spec.tier!r}; known: {TIERS}"
            )
        if spec.name in seen_names:
            raise BatteryError(
                f"register_suite: duplicate metric name '{spec.name}' within suite '{suite}'"
            )
        seen_names.add(spec.name)

    SUITES[suite] = specs_tuple


# --------------------------------------------------------------------------- #
# Monte-Carlo error via ensemble subsampling
# --------------------------------------------------------------------------- #


def mc_error(fn: MetricFn, ensemble: Ensemble, *, seed: int, n_subsamples: int) -> float:
    """The Monte-Carlo standard error of ``fn(ensemble)``, via disjoint subsampling.

    ``ensemble.n_paths`` paths are shuffled (a fresh ``numpy.random.Generator(PCG64(
    seed))``, never a global RNG -- the same draw for the same ``seed`` every time) and
    split into ``n_subsamples`` groups of nearly-equal size; ``fn`` is recomputed on
    each group's own :class:`~ah.gen.base.Ensemble` (the same ``factor_names``, a
    ``paths`` slice, and a ``meta`` copied from the parent with ``n_paths`` corrected to
    the subsample's own size -- see the loop below), and the result is
    ``std(per-subsample estimates, ddof=1) / sqrt(n_subsamples)``.

    Why that formula: when ``fn`` is (or behaves asymptotically like) a sample mean
    over paths of an iid quantity with variance ``sigma**2``, a subsample of size
    ``n/k`` has estimate-variance ``sigma**2 * k / n``, so the standard deviation
    across the ``k`` subsample estimates is ``sigma * sqrt(k/n)``; dividing by
    ``sqrt(k)`` gives ``sigma/sqrt(n)`` -- the standard error of the *full* n-path
    estimate. This is the batch-means Monte-Carlo error estimator, applied uniformly to
    every suite via this one helper rather than each suite deriving its own.

    Raises :class:`BatteryError` if ``n_subsamples < 2`` (no spread to measure) or if
    ``ensemble`` has fewer paths than ``n_subsamples`` (a subsample would be empty).
    """
    if n_subsamples < 2:
        raise BatteryError(f"mc_error: n_subsamples must be >= 2, got {n_subsamples}")
    n = ensemble.n_paths
    if n < n_subsamples:
        raise BatteryError(
            f"mc_error: ensemble has {n} paths, fewer than n_subsamples={n_subsamples}"
        )

    rng = np.random.Generator(np.random.PCG64(seed))
    order = rng.permutation(n)
    chunks = np.array_split(order, n_subsamples)

    estimates = np.empty(n_subsamples, dtype=np.float64)
    for i, idx in enumerate(chunks):
        # The sub-ensemble's meta must describe the sub-ensemble. `Ensemble.n_paths`
        # reads `paths.shape[0]` but `EnsembleMeta.n_paths` is an independent field, so
        # reusing the parent's meta verbatim would hand every metric an object whose
        # two path counts disagree -- and a metric that reads `e.meta.n_paths` (the
        # documented lineage record) would silently compute the wrong MC error on every
        # subsample. Everything else about the lineage (generator, vintage, seed,
        # checkpoint) is genuinely inherited and is carried over untouched.
        sub_meta = replace(ensemble.meta, n_paths=len(idx))
        sub_ensemble = Ensemble(
            paths=ensemble.paths[idx], factor_names=ensemble.factor_names, meta=sub_meta
        )
        estimates[i] = fn(sub_ensemble)

    return float(np.std(estimates, ddof=1) / np.sqrt(n_subsamples))


def _n_subsamples_for(ensemble: Ensemble) -> int:
    """Never more subsamples than a small ensemble can support (each needs >=1 path)."""
    return max(2, min(_DEFAULT_MC_SUBSAMPLES, ensemble.n_paths // 2))


# --------------------------------------------------------------------------- #
# band / threshold lookup by metric name
# --------------------------------------------------------------------------- #


def _lookup_band(name: str, reference: ReferenceStats) -> StatBand | None:
    """First match across sorted blocks, then sorted cross-block pairs.

    **Coupling, stated rather than assumed:** this is a flat lookup by metric name over
    a block-nested structure, and it is correct only because factor ids are globally
    unique -- ``ah.factors._validate`` rejects a ``factors.yaml`` in which one factor
    appears in two blocks, so a ``"<factor>.<stat>"`` key can belong to at most one
    block and a ``"<factorA>~<factorB>.<stat>"`` key to at most one pair. If that
    manifest-level uniqueness rule is ever relaxed, this lookup (and
    :func:`_lookup_threshold` below) must be keyed by ``(block, key)`` instead, and
    :class:`MetricSpec` must carry the block. Blocks and pairs are iterated in sorted
    order so the (currently unreachable) ambiguous case would at least be deterministic
    rather than dependent on mapping insertion order.
    """
    for block in sorted(reference.blocks):
        stats = reference.blocks[block].stats
        if name in stats:
            return stats[name]
    for pair in sorted(reference.cross_blocks):
        stats = reference.cross_blocks[pair].stats
        if name in stats:
            return stats[name]
    return None


def _lookup_threshold(name: str, prereg: PreRegistration) -> Threshold | None:
    """First match across sorted blocks, then sorted pairs, then the panel section.

    See :func:`_lookup_band` for the globally-unique-factor-id coupling the first two
    rely on. The panel section is keyed by a bare statistic name (a whole-panel
    statistic belongs to no factor and no pair -- see
    :data:`ah.eval.reference.PANEL_STATS`), and those names carry no ``"."``, so they
    cannot collide with a block or pair key.
    """
    for block in sorted(prereg.block_thresholds):
        entries = prereg.block_thresholds[block]
        if name in entries:
            return entries[name]
    for pair in sorted(prereg.cross_block_thresholds):
        entries = prereg.cross_block_thresholds[pair]
        if name in entries:
            return entries[name]
    return prereg.panel_thresholds.get(name)


def _passed(value: float, threshold: Threshold) -> bool:
    """``value in [threshold.min, threshold.max]``. **A NaN value FAILS.**

    THE ONE NaN RULE, stated identically here and in
    :func:`ah.battery.report.evaluate`, and in ``pre-registration.yaml``'s
    ``conventions.nan_metric_rule``: an uncomputable metric has not demonstrated
    compliance, so it does not pass. NaN fails here for free (every comparison with NaN
    is ``False``, so the ``>=``/``<=`` guards return ``False`` whenever a bound is
    given) -- but it is asserted by a test rather than left to that accident, because
    a threshold with *no* bounds at all would otherwise pass a NaN vacuously. Step 0's
    ``ah.battery.report.evaluate`` used to take the opposite view and skip the
    comparison entirely for NaN, marking it OK; both modules are inside the seal, so
    the two rules could have judged the same generator differently.
    """
    if np.isnan(value):
        return False
    return (threshold.min is None or value >= threshold.min) and (
        threshold.max is None or value <= threshold.max
    )


# --------------------------------------------------------------------------- #
# run_battery
# --------------------------------------------------------------------------- #


def _run_suites(
    ensemble: Ensemble, *, reference: ReferenceStats, prereg: PreRegistration, seed: int
) -> tuple[MetricResult, ...]:
    n_subsamples = _n_subsamples_for(ensemble)
    results: list[MetricResult] = []
    for suite in sorted(SUITES):
        for spec in SUITES[suite]:
            value = float(spec.fn(ensemble))
            error = mc_error(spec.fn, ensemble, seed=seed, n_subsamples=n_subsamples)
            band = _lookup_band(spec.name, reference)
            threshold = _lookup_threshold(spec.name, prereg)
            if threshold is not None:
                severity = threshold.severity
                passed: bool | None = _passed(value, threshold)
            else:
                severity = "report"
                passed = None
            results.append(
                MetricResult(
                    name=spec.name,
                    suite=spec.suite,
                    tier=spec.tier,
                    value=value,
                    mc_error=error,
                    band=band,
                    severity=severity,
                    passed=passed,
                )
            )
    return tuple(results)


def _group_by_tier(results: tuple[MetricResult, ...]) -> dict[str, list[MetricResult]]:
    grouped: dict[str, list[MetricResult]] = {}
    for r in results:
        grouped.setdefault(r.tier, []).append(r)
    return grouped


def _result_dict(r: MetricResult) -> dict[str, Any]:
    return {
        "name": r.name,
        "suite": r.suite,
        "tier": r.tier,
        "value": r.value,
        "mc_error": r.mc_error,
        "band": None
        if r.band is None
        else {
            "point": r.band.point,
            "lo": r.band.lo,
            "hi": r.band.hi,
            "n_resamples": r.band.n_resamples,
            "level": r.band.level,
            "tier": r.band.tier,
        },
        "severity": r.severity,
        "passed": r.passed,
    }


@dataclass(frozen=True)
class BatteryReport:
    """The battery's output: version, prereg digest, system/vintage identity, results.

    ``results`` is the unfiltered run; ``results_filtered`` is ``None`` unless a
    ``filtered`` ensemble was passed to :func:`run_battery`, in which case it is that
    ensemble's own results -- both are always kept, side by side, never one replacing
    the other (see the module docstring's "Filtered vs. unfiltered").

    Missing-factor accounting and coverage are carried from the
    :class:`~ah.eval.reference.ReferenceStats` the run was judged against.
    ``missing_declared`` is the routine case (the manifest says no source exists);
    ``missing_no_data`` is the dangerous one (a real source that returned nothing).
    ``governance/retrofit-register.md`` RFR-5 records that an ``enforce`` threshold can
    be sealed for a factor with no computed reference statistic, and this report is
    where that has to be visible rather than inferred. ``coverage`` says how much
    history each computed band actually rests on -- roughly a fourfold spread across
    the mapped series.
    """

    battery_version: str
    prereg_digest: str
    system_id: str
    vintage_id: str
    active_blocks: tuple[str, ...]
    seed: int
    results: tuple[MetricResult, ...]
    results_filtered: tuple[MetricResult, ...] | None = None
    missing_declared: tuple[str, ...] = ()
    missing_no_data: tuple[str, ...] = ()
    coverage: Mapping[str, FactorCoverage] = MappingProxyType({})
    prereg_verified: bool = False

    @property
    def enforce_failures(self) -> tuple[MetricResult, ...]:
        """Every ``severity: enforce`` metric that did not pass, unfiltered run only.

        The filtered run is diagnostic (the acceptance filter may not teach to the
        exam), so it never contributes to the verdict -- only to the report.
        """
        return tuple(r for r in self.results if r.severity == "enforce" and r.passed is False)

    @property
    def passed(self) -> bool:
        """The aggregate verdict: no ``enforce``-severity metric failed.

        Same shape as Step 0's :attr:`ah.battery.report.BatteryReport.passed`, so a
        caller (and the eventual CLI exit code) reads one property regardless of which
        battery produced the report. A ``report``-severity failure is recorded and does
        not block, by definition of the severity.
        """
        return not self.enforce_failures

    def to_dict(self) -> dict[str, Any]:
        def _tiers(results: tuple[MetricResult, ...]) -> dict[str, list[dict[str, Any]]]:
            grouped = _group_by_tier(results)
            return {
                tier: [_result_dict(r) for r in grouped[tier]] for tier in TIERS if tier in grouped
            }

        doc: dict[str, Any] = {
            "battery_version": self.battery_version,
            "prereg_digest": self.prereg_digest,
            "system_id": self.system_id,
            "vintage_id": self.vintage_id,
            "active_blocks": list(self.active_blocks),
            "seed": self.seed,
            "passed": self.passed,
            "enforce_failures": [r.name for r in self.enforce_failures],
            "prereg_verified": self.prereg_verified,
            "missing_factors": {
                "declared_unavailable": list(self.missing_declared),
                "no_data": list(self.missing_no_data),
            },
            "coverage": {
                factor: {
                    "first_date": cov.first_date,
                    "last_date": cov.last_date,
                    "n_obs": cov.n_obs,
                }
                for factor, cov in self.coverage.items()
            },
            "unfiltered": {"tiers": _tiers(self.results)},
        }
        if self.results_filtered is not None:
            doc["filtered"] = {"tiers": _tiers(self.results_filtered)}
        return doc

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        lines = [
            f"# Validation battery report ({self.battery_version})",
            "",
            f"- system: {self.system_id}",
            f"- vintage: {self.vintage_id}",
            f"- active blocks: {', '.join(self.active_blocks)}",
            f"- seed: {self.seed}",
            f"- prereg digest: {self.prereg_digest}",
            f"- prereg verified: {'yes' if self.prereg_verified else 'no (unsealed)'}",
            f"- **verdict: {'PASS' if self.passed else 'FAIL'}** "
            f"({len(self.enforce_failures)} enforce failure(s))",
            "",
            "## Factor availability",
            "",
            "| factor | status |",
            "| --- | --- |",
            *[f"| {f} | declared unavailable |" for f in self.missing_declared],
            *[f"| {f} | **DECLARED AVAILABLE, NO DATA** |" for f in self.missing_no_data],
            *(
                []
                if (self.missing_declared or self.missing_no_data)
                else ["| - | every active factor produced data |"]
            ),
            "",
            "## Reference coverage (train+validation)",
            "",
            "| factor | first | last | n obs |",
            "| --- | --- | --- | --- |",
            *[
                f"| {factor} | {cov.first_date} | {cov.last_date} | {cov.n_obs} |"
                for factor, cov in sorted(self.coverage.items())
            ],
            "",
        ]

        def _section(title: str, results: tuple[MetricResult, ...]) -> None:
            lines.append(f"## {title}")
            lines.append("")
            grouped = _group_by_tier(results)
            for tier in TIERS:
                if tier not in grouped:
                    continue
                lines.append(f"### {tier}")
                lines.append("")
                lines.append(
                    "| metric | suite | value | mc_error | band lo | band hi | severity | passed |"
                )
                lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
                for r in grouped[tier]:
                    lo = "" if r.band is None else f"{r.band.lo:.6g}"
                    hi = "" if r.band is None else f"{r.band.hi:.6g}"
                    mc = "" if r.mc_error is None else f"{r.mc_error:.6g}"
                    passed_str = "-" if r.passed is None else ("PASS" if r.passed else "FAIL")
                    lines.append(
                        f"| {r.name} | {r.suite} | {r.value:.6g} | {mc} | {lo} | {hi} | "
                        f"{r.severity} | {passed_str} |"
                    )
                lines.append("")

        _section("Unfiltered", self.results)
        if self.results_filtered is not None:
            _section("Filtered", self.results_filtered)

        return "\n".join(lines) + "\n"


def run_battery(
    ensemble: Ensemble,
    *,
    reference: ReferenceStats,
    prereg: PreRegistration,
    manifest: FactorManifest,
    seed: int,
    filtered: Ensemble | None = None,
) -> BatteryReport:
    """Run every registered suite over ``ensemble`` (and ``filtered``, if given).

    ``reference`` supplies the train+validation bands metrics are reported against
    (never computed here -- see :func:`ah.eval.reference.compute_reference`).
    ``prereg`` supplies the sealed (or, pre-WP2.3, provisional) thresholds that decide
    ``severity``/``passed`` for a metric whose name matches one, and its ``source_path``
    is dry-run sealed (:func:`ah.eval.prereg.seal`) to compute ``prereg_digest`` -- the
    exact code+thresholds that judged this run, recorded on the report itself.
    ``manifest`` supplies ``active_blocks`` for the report header, and is the manifest
    the pre-registration is verified against.

    **Verification.** STEP2-GENERATOR-PLAN Sec.WP2.3 requires
    :func:`ah.eval.prereg.verify` to run "at every battery/G2 invocation". It is called
    here whenever ``prereg.sealed`` is true, and skipped (with ``prereg_verified:
    false`` recorded on the report, so the skip is visible rather than assumed) while
    the pre-registration is still provisional -- today's ``pre-registration.yaml``
    carries placeholder thresholds and ``sealed: false``, and cannot satisfy every
    check yet.
    TODO(WP2.3): once ``sealed: true`` lands, this guard becomes dead weight -- drop it
    and verify unconditionally, and pass the ``lock_path`` so the digest check runs too.
    """
    prereg_verified = False
    if prereg.sealed:
        prereg_mod.verify(prereg, manifest)
        prereg_verified = True

    results = _run_suites(ensemble, reference=reference, prereg=prereg, seed=seed)
    results_filtered = None
    if filtered is not None:
        results_filtered = _run_suites(filtered, reference=reference, prereg=prereg, seed=seed)

    digest = prereg_mod.seal(
        prereg.source_path,
        sealed_at="n/a (dry-run digest does not depend on sealed_at)",
        dry_run=True,
    )

    return BatteryReport(
        battery_version=BATTERY_VERSION,
        prereg_digest=digest,
        system_id=ensemble.meta.generator_id,
        vintage_id=ensemble.meta.vintage_id,
        active_blocks=manifest.active_blocks,
        seed=seed,
        results=results,
        results_filtered=results_filtered,
        missing_declared=reference.missing_declared,
        missing_no_data=reference.missing_no_data,
        coverage=reference.coverage,
        prereg_verified=prereg_verified,
    )


# --------------------------------------------------------------------------- #
# run_full_battery: compute the reference, register the suites, run
# --------------------------------------------------------------------------- #

# Suite name -> the module path and builder attribute that constructs its specs from a
# (manifest, reference) pair. A table rather than a hardcoded call so a later task adds
# a suite by adding a row, not by editing `run_full_battery`. Imported lazily inside
# `register_reference_dependent_suites` because a metric suite imports THIS module for
# `MetricSpec`/`register_suite`; a module-level import here would be a cycle.
_REFERENCE_DEPENDENT_SUITE_BUILDERS: dict[str, tuple[str, str]] = {
    "monthly": ("ah.eval.metrics.monthly", "build_monthly_suite"),
}


def register_reference_dependent_suites(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[str, ...]:
    """(Re)register every suite whose specs need a computed reference. Returns the names.

    **Idempotent by replacement.** :func:`register_suite` refuses to re-register a name
    -- correct for the one-shot production path it guards -- so this drops any existing
    registration for the suites it owns before registering them afresh. Without that, a
    process that ran the battery twice (two ensembles, two vintages, a CLI loop) would
    raise on the second call; with it, the second run's specs are built against the
    second run's reference, which is the only correct behaviour: a spec closes over the
    reference it was built with (``cross_block_corr_matrix_distance`` closes over the
    historical correlation matrix it measures distance to), so reusing the first run's
    registration would silently judge the second ensemble against the first reference.

    Suites *not* in :data:`_REFERENCE_DEPENDENT_SUITE_BUILDERS` are left untouched,
    including any a test registered by hand.
    """
    from importlib import import_module

    registered: list[str] = []
    for suite, (module_name, builder_name) in sorted(_REFERENCE_DEPENDENT_SUITE_BUILDERS.items()):
        builder = getattr(import_module(module_name), builder_name)
        SUITES.pop(suite, None)
        register_suite(suite, builder(manifest, reference))
        registered.append(suite)
    return tuple(registered)


def run_full_battery(
    ensemble: Ensemble,
    *,
    access: DataAccess,
    manifest: FactorManifest,
    prereg: PreRegistration,
    seed: int,
    reference_seed: int | None = None,
    vintage_id: str | None = None,
    n_resamples: int = 1000,
    level: float = 0.9,
    block_length: int = DEFAULT_BLOCK_LENGTH,
    filtered: Ensemble | None = None,
) -> BatteryReport:
    """Compute the reference, register every reference-dependent suite, run the battery.

    **The entry point a real battery run goes through.** Before WP2.2 Task 2's fix pass
    nothing in ``src/`` called any ``register_*_suite()``, so :data:`SUITES` was empty in
    every production code path: :func:`run_battery` computed zero metrics and returned a
    report whose :attr:`BatteryReport.passed` was vacuously ``True``. This function is
    what makes the battery a battery.

    Steps, in order:

    1. :func:`ah.eval.reference.compute_reference` over ``manifest``'s active factors,
       read through ``access`` on **train+validation only** (that function holds no
       :class:`~ah.splits.FinalEvaluationToken` and cannot reach the holdout), with
       ``resample_length=ensemble.months`` -- every bootstrap replicate is drawn at the
       judged ensemble's own path length so both sides of every length-sensitive
       statistic carry the same estimator bias (see
       :func:`ah.eval.reference.block_bootstrap_band` for the full argument, and
       ``ah.eval.metrics.monthly``'s module docstring for the residual this does not
       cover).
    2. :func:`register_reference_dependent_suites` against that reference.
    3. :func:`run_battery`, which verifies the pre-registration (once sealed), evaluates
       every registered suite, and attaches bands, thresholds and Monte-Carlo errors.

    ``reference_seed`` defaults to ``seed``; it is separated so the reference's bootstrap
    draw and the battery's Monte-Carlo subsampling draw can be varied independently
    without either becoming a function of the other. ``vintage_id`` defaults to
    ``ensemble.meta.vintage_id`` -- the reference is stamped with the vintage the
    ensemble claims to have been generated against, which is what makes a report's
    ``vintage_id`` mean one thing rather than two.

    Determinism: every draw flows from ``reference_seed``/``seed`` through
    ``numpy.random.Generator(PCG64(...))``; the same inputs give a bit-identical report.
    """
    reference = compute_reference(
        access,
        manifest,
        vintage_id=ensemble.meta.vintage_id if vintage_id is None else vintage_id,
        seed=seed if reference_seed is None else reference_seed,
        n_resamples=n_resamples,
        level=level,
        block_length=block_length,
        resample_length=ensemble.months,
    )
    register_reference_dependent_suites(manifest, reference)
    return run_battery(
        ensemble,
        reference=reference,
        prereg=prereg,
        manifest=manifest,
        seed=seed,
        filtered=filtered,
    )
