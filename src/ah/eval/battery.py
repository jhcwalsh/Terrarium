"""The validation battery orchestrator (WP2.2 Task 1).

Replaces Step 0's skeleton (``ah.battery.report``, which stays in place -- see its
module docstring and ``governance/retrofit-register.md`` for its fate, a WP2.3
decision, not this module's). This is the Step-2 battery: it runs every metric suite
registered in :data:`SUITES` over a generator :class:`~ah.gen.base.Ensemble`, attaches
a Monte-Carlo error bar to every result, looks each metric up against the train+
validation :class:`~ah.eval.reference.ReferenceStats` bands and
:class:`~ah.eval.prereg.PreRegistration` thresholds, and emits a :class:`BatteryReport`
in both JSON and markdown.

Registration only
------------------
Tasks 2-6 add metric suites (``monthly``, ``horizon``, ``tails``, ``utility``,
``memorization``, ``economics``, ``conditional``, ``calibration``) by calling
:func:`register_suite` at import time; :func:`run_battery` iterates :data:`SUITES`
generically. Adding a suite must never require editing this module -- proved by
``tests/test_eval_battery.py``, which registers a throwaway suite and shows it appears
in a report without touching :func:`run_battery`.

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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ah.eval import prereg as prereg_mod
from ah.eval.prereg import PreRegistration, Threshold
from ah.eval.reference import ReferenceStats, StatBand
from ah.factors import FactorManifest
from ah.gen.base import Ensemble

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
    each group's own :class:`~ah.gen.base.Ensemble` (same ``factor_names``/``meta``, a
    ``paths`` slice), and the result is ``std(per-subsample estimates, ddof=1) /
    sqrt(n_subsamples)``.

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
        sub_ensemble = Ensemble(
            paths=ensemble.paths[idx], factor_names=ensemble.factor_names, meta=ensemble.meta
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
    for block in sorted(prereg.block_thresholds):
        entries = prereg.block_thresholds[block]
        if name in entries:
            return entries[name]
    for pair in sorted(prereg.cross_block_thresholds):
        entries = prereg.cross_block_thresholds[pair]
        if name in entries:
            return entries[name]
    return None


def _passed(value: float, threshold: Threshold) -> bool:
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
    """

    battery_version: str
    prereg_digest: str
    system_id: str
    vintage_id: str
    active_blocks: tuple[str, ...]
    seed: int
    results: tuple[MetricResult, ...]
    results_filtered: tuple[MetricResult, ...] | None = None

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
    ``manifest`` supplies ``active_blocks`` for the report header.
    """
    results = _run_suites(ensemble, reference=reference, prereg=prereg, seed=seed)
    results_filtered = None
    if filtered is not None:
        results_filtered = _run_suites(filtered, reference=reference, prereg=prereg, seed=seed)

    digest = prereg_mod.seal(
        prereg.source_path,
        out_path=Path("unused-dry-run.lock"),
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
    )
