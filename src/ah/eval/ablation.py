"""WP2.10 — tabulate the ablation grid in the shape WP2.11's SEALED rule consumes.

**This module does not execute the decision rule.** ``pre-registration.yaml``'s
``multi_seed_decision_rule`` is executed by ``ah/eval/g2.py``, which is inside the
seal and is WP2.11's to write. What this module does is *extract*, from stored
:class:`~ah.eval.battery.BatteryReport` documents, every quantity that rule names —
so WP2.11 can evaluate it arithmetically instead of re-running a 10-hour grid.

Everything here is a projection of fields the sealed battery already computed:
``suite``, ``name``, ``value``, ``severity``, ``passed``, and the band's own
``band_outside`` / ``band_degenerate`` / ``lo`` / ``hi``. Nothing is re-judged and
no threshold is re-derived. The one arithmetic operation performed on a sealed
number is the MEAN of ``elicitability_score`` over the comparison set, which
clause (i) names explicitly, and the ddof=1 dispersion of its cross-seed
difference, which the pooled route names explicitly.

What the sealed rule asks for, and where it is answered here
------------------------------------------------------------
``tail_tier_definition``   :func:`comparison_set` — family (a) restricted to the
                           strategies with computable historical statistics, plus
                           all of family (b).
``beats_definition`` (i)   :func:`clause_i` — the mean ``elicitability_score`` over
                           the comparison set's strategies. Lower is better. The
                           NaN rule is carried, not smoothed: a NaN on either side
                           makes the seed NOT a beat.
``beats_definition`` (ii)  :func:`clause_ii` — the count of comparison-set metrics
                           outside their sealed reference band, over usable bands
                           only. The seal discloses this ranges entirely over
                           family (b); :func:`clause_ii` MEASURES that rather than
                           assuming it, and reports the strategy-level contribution
                           separately so a reader can see it is zero.
pooled route               :func:`pooled_difference` — ``mean_s(d_s)`` and
                           ``sd_s(d_s)`` at ddof=1, and the exact inequality's two
                           halves evaluated separately.
``rule`` (2)-(4)           :func:`enforce_rows` (monthly / 1_5yr tiers),
                           :func:`memorization_enforce`, :func:`constraint_violations`.
``criterion_bearing``      :func:`criterion_bearing` — asserted per run, never hoped for.
``benchmark_draw_span_bias``  :func:`restricted_elicitability` — the same sealed
                           scoring function against the 1990-2020 realizations only.

Cross-seed dispersion convention, stated once and applied everywhere
--------------------------------------------------------------------
Every per-metric table reports **the individual seed values AND their mean**. A
standard deviation over three seeds is a two-degree-of-freedom estimate and is
fragile enough that quoting it alone would overstate what the grid measured. An
sd appears in exactly one place — the pooled route's ``sd_s(d_s)`` — because the
sealed inequality names it, and it is labelled ``ddof=1`` there because the seal
specifies ddof=1.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

__all__ = [
    "BAND_FAMILY_SUFFIXES",
    "ELICITABILITY_STAT",
    "ComparisonSet",
    "clause_i",
    "clause_ii",
    "comparison_set",
    "constraint_violations",
    "criterion_bearing",
    "enforce_rows",
    "memorization_enforce",
    "pooled_difference",
    "restricted_elicitability",
    "tails_rows",
]

#: The one directional scalar in the tails suite (``beats_definition`` (i)).
ELICITABILITY_STAT = "elicitability_score"

#: Family (b) of ``tail_tier_definition``: the cross-block tail-dependence pair.
BAND_FAMILY_SUFFIXES = ("tail_dependence_lower", "tail_dependence_upper")

#: The enforce tiers clause (2) names.
REGRESSION_TIERS = ("monthly", "1_5yr")


class AblationError(RuntimeError):
    """Raised when a stored report cannot supply something the sealed rule needs."""


# --------------------------------------------------------------------------- #
# reading a stored BatteryReport document
# --------------------------------------------------------------------------- #


def _results(report: Mapping[str, Any], which: str = "unfiltered") -> list[dict[str, Any]]:
    """Every metric row of one side of a report (``"unfiltered"``/``"filtered"``)."""
    if which not in ("unfiltered", "filtered"):
        raise AblationError(f"which must be 'unfiltered' or 'filtered'; got {which!r}")
    side = report.get(which)
    if side is None:
        raise AblationError(f"report carries no '{which}' results")
    return [row for tier_rows in side["tiers"].values() for row in tier_rows]


def tails_rows(report: Mapping[str, Any], which: str = "unfiltered") -> dict[str, dict[str, Any]]:
    """Every ``suite == "tails"`` row of a report, keyed by metric name.

    ``tail_tier_definition`` says the tail tier IS this suite — "a suite, not a
    horizon tier" — so membership is read off the row's own ``suite`` field and
    never off its ``tier``.
    """
    return {row["name"]: row for row in _results(report, which) if row["suite"] == "tails"}


@dataclass(frozen=True)
class ComparisonSet:
    """``tail_tier_definition``'s comparison set, resolved against a live report."""

    #: ``<strategy_id>`` for each strategy with computable historical statistics.
    strategy_ids: tuple[str, ...]
    #: family (a), restricted: the eleven per-strategy names for those strategies.
    strategy_names: tuple[str, ...]
    #: family (b): every cross-block ``tail_dependence_*`` name.
    band_names: tuple[str, ...]
    #: the strategies excluded because their historical side is uncomputable.
    excluded_strategy_ids: tuple[str, ...]

    @property
    def elicitability_names(self) -> tuple[str, ...]:
        return tuple(f"{sid}.{ELICITABILITY_STAT}" for sid in self.strategy_ids)

    @property
    def names(self) -> tuple[str, ...]:
        return self.strategy_names + self.band_names


def comparison_set(
    report: Mapping[str, Any],
    *,
    d4_strategy_ids: Sequence[str],
    uncomputable_strategy_ids: Sequence[str],
    which: str = "unfiltered",
) -> ComparisonSet:
    """Resolve ``tail_tier_definition``'s comparison set against one report.

    ``d4_strategy_ids`` and ``uncomputable_strategy_ids`` come from the sealed
    document (``d4_strategies`` and ``reference_run.uncomputable_d4_strategies``) —
    the set is "the five d4_strategies MINUS reference_run.uncomputable_
    d4_strategies", so on the campaign vintage the strategies that REMAIN are
    ``sixty_forty``, ``momentum`` and ``carry``, and the ones removed are
    ``eqw_factors`` and ``endowment_proxy``.
    """
    excluded = tuple(sorted(set(uncomputable_strategy_ids)))
    kept = tuple(sid for sid in d4_strategy_ids if sid not in set(excluded))
    if not kept:
        raise AblationError("the comparison set is empty: every D4 strategy is uncomputable")
    rows = tails_rows(report, which)
    strategy_names = tuple(
        sorted(name for name in rows if name.split(".", 1)[0] in set(kept) and "~" not in name)
    )
    band_names = tuple(
        sorted(name for name in rows if name.rsplit(".", 1)[-1] in BAND_FAMILY_SUFFIXES)
    )
    missing = [f"{sid}.{ELICITABILITY_STAT}" for sid in kept]
    absent = [name for name in missing if name not in rows]
    if absent:
        raise AblationError(f"report is missing comparison-set metrics: {absent}")
    return ComparisonSet(
        strategy_ids=kept,
        strategy_names=strategy_names,
        band_names=band_names,
        excluded_strategy_ids=excluded,
    )


# --------------------------------------------------------------------------- #
# clause (i): the objective
# --------------------------------------------------------------------------- #


def clause_i(
    report: Mapping[str, Any], cset: ComparisonSet, which: str = "unfiltered"
) -> dict[str, Any]:
    """The mean ``elicitability_score`` over the comparison set's strategies.

    Returns the per-strategy values, their mean (NaN if ANY is NaN — the sealed NaN
    rule propagates rather than dropping the strategy), and an explicit
    ``has_nan`` flag so a reader never has to infer it from a NaN mean.
    """
    rows = tails_rows(report, which)
    per_strategy = {
        sid: float(rows[f"{sid}.{ELICITABILITY_STAT}"]["value"]) for sid in cset.strategy_ids
    }
    values = np.array(list(per_strategy.values()), dtype=np.float64)
    has_nan = bool(np.any(np.isnan(values)))
    return {
        "per_strategy": per_strategy,
        "n_strategies": len(per_strategy),
        # np.mean, NOT nanmean: the seal says a NaN makes the seed NOT a beat, so
        # the NaN must survive into the number the rule reads.
        "mean": float(np.mean(values)),
        "has_nan": has_nan,
        "mc_error_by_strategy": {
            sid: rows[f"{sid}.{ELICITABILITY_STAT}"].get("mc_error") for sid in cset.strategy_ids
        },
    }


# --------------------------------------------------------------------------- #
# clause (ii): no tail-band regression
# --------------------------------------------------------------------------- #


def _band_usable(row: Mapping[str, Any]) -> bool:
    """``ah.eval.battery.band_is_usable``, read off the serialized band.

    A band is usable when it exists, its bounds are finite, and it is not
    degenerate (``lo == hi``). The battery already recorded ``band_degenerate``;
    finiteness is re-read from the bounds themselves so this does not depend on a
    field the report might omit.
    """
    band = row.get("band")
    if band is None:
        return False
    lo, hi = band.get("lo"), band.get("hi")
    if lo is None or hi is None:
        return False
    if not (math.isfinite(float(lo)) and math.isfinite(float(hi))):
        return False
    return not bool(band.get("band_degenerate", float(lo) == float(hi)))


def clause_ii(
    report: Mapping[str, Any], cset: ComparisonSet, which: str = "unfiltered"
) -> dict[str, Any]:
    """The count of comparison-set metrics outside their sealed reference band.

    Ranges over the WHOLE comparison set and then filters to usable bands, so the
    seal's disclosure — "clause (ii) is evaluated ENTIRELY over family (b) ... ZERO
    strategy-level metrics enter it" — is a MEASURED property of this run rather
    than an assumption baked into the loop. ``n_usable_strategy_bands`` is the
    number that must be zero for the disclosure to hold; it is reported, not
    asserted away.
    """
    rows = tails_rows(report, which)
    usable_strategy = [n for n in cset.strategy_names if _band_usable(rows[n])]
    usable_band = [n for n in cset.band_names if _band_usable(rows[n])]
    outside = sorted(
        n for n in (usable_strategy + usable_band) if bool(rows[n]["band"]["band_outside"])
    )
    return {
        "count": len(outside),
        "n_usable_bands": len(usable_strategy) + len(usable_band),
        "n_usable_strategy_bands": len(usable_strategy),
        "n_usable_cross_block_bands": len(usable_band),
        "n_comparison_set_names": len(cset.names),
        "outside_names": outside,
        "seal_disclosure_holds": len(usable_strategy) == 0,
    }


# --------------------------------------------------------------------------- #
# the pooled route
# --------------------------------------------------------------------------- #


def pooled_difference(diffs: Sequence[float]) -> dict[str, Any]:
    """``mean_s(d_s)`` and ``sd_s(d_s)`` (ddof=1), and the sealed inequality's halves.

    The seal states the pooled route as an exact inequality: challenger beats
    benchmark pooled iff ``mean_s(d_s) < 0`` AND ``|mean_s(d_s)| > sd_s(d_s)`` with
    sd at ddof=1. Both halves are returned separately so WP2.11 can show its
    arithmetic. ``sd`` is NaN for fewer than two seeds, which is what ddof=1 means
    and is not smoothed over.
    """
    d = np.asarray(list(diffs), dtype=np.float64)
    if d.size == 0:
        raise AblationError("pooled_difference needs at least one seed difference")
    mean = float(np.mean(d))
    sd = float(np.std(d, ddof=1)) if d.size > 1 else float("nan")
    negative = bool(mean < 0.0)
    exceeds = bool(abs(mean) > sd) if not math.isnan(sd) else False
    return {
        "n_seeds": int(d.size),
        "per_seed_d": [float(x) for x in d],
        "mean_d": mean,
        "sd_d_ddof1": sd,
        "mean_is_negative": negative,
        "abs_mean_exceeds_sd": exceeds,
        "pooled_beat": bool(negative and exceeds),
    }


# --------------------------------------------------------------------------- #
# clauses (2)-(4) and criterion_bearing
# --------------------------------------------------------------------------- #


def enforce_rows(
    report: Mapping[str, Any],
    *,
    tiers: Sequence[str] | None = None,
    which: str = "unfiltered",
) -> list[dict[str, Any]]:
    """Every ``severity == "enforce"`` row, optionally restricted to given tiers."""
    wanted = None if tiers is None else set(tiers)
    out = [
        {
            "name": row["name"],
            "suite": row["suite"],
            "tier": row["tier"],
            "value": row["value"],
            "passed": row["passed"],
            "status": row["status"],
        }
        for row in _results(report, which)
        if row["severity"] == "enforce" and (wanted is None or row["tier"] in wanted)
    ]
    return sorted(out, key=lambda r: (r["tier"], r["name"]))


def memorization_enforce(
    report: Mapping[str, Any], which: str = "unfiltered"
) -> list[dict[str, Any]]:
    """Clause (3): every memorization-suite enforce threshold, with its verdict."""
    return sorted(
        (
            {
                "name": row["name"],
                "tier": row["tier"],
                "value": row["value"],
                "passed": row["passed"],
            }
            for row in _results(report, which)
            if row["severity"] == "enforce" and row["suite"] == "memorization"
        ),
        key=lambda r: r["name"],
    )


def constraint_violations(report: Mapping[str, Any], which: str = "unfiltered") -> dict[str, Any]:
    """Clause (4): ``money_pump_violations`` and ``floor_violations``, exactly 0.

    Reports the values AND whether each is exactly zero. A missing metric is an
    error, not a silent pass — clause (4) cannot be satisfied by absence.
    """
    by_name = {row["name"]: row for row in _results(report, which)}
    out: dict[str, Any] = {}
    for name in ("money_pump_violations", "floor_violations"):
        if name not in by_name:
            raise AblationError(f"report has no '{name}' metric; clause (4) is unevaluable")
        value = float(by_name[name]["value"])
        out[name] = {
            "value": value,
            "is_zero": bool(value == 0.0),
            "passed": by_name[name]["passed"],
        }
    out["all_zero"] = all(v["is_zero"] for k, v in out.items() if isinstance(v, dict))
    return out


def criterion_bearing(
    report: Mapping[str, Any],
    *,
    expected_n_paths: int,
    expected_months: int,
    expected_vintage_id: str,
) -> dict[str, Any]:
    """Assert the run is criterion-bearing, and say exactly which conditions held.

    ``criterion_bearing_runs_only`` requires all three of: the sealed ensemble size,
    the sealed campaign vintage, and a verified pre-registration with a matching
    lock. The battery records the composite flag; the three components are re-read
    here so a failure names its cause rather than reporting one opaque ``false``.
    """
    if "n_paths" not in report or "months" not in report:
        raise AblationError(
            "report carries no ensemble size: ah.eval.battery.BatteryReport.to_dict() "
            "does not serialize n_paths/months, so a caller must merge them in from the "
            "judged ensemble (scripts/run_ablation_grid.py records both in its "
            "summary.json). Refusing to report criterion_bearing from the composite flag "
            "alone -- the point of this function is to name WHICH condition failed."
        )
    checks = {
        "battery_flag": bool(report.get("criterion_bearing") is True),
        "prereg_verified": bool(report.get("prereg_verified") is True),
        "n_paths": int(report["n_paths"]) == int(expected_n_paths),
        "months": int(report["months"]) == int(expected_months),
        "vintage_id": str(report["vintage_id"]) == str(expected_vintage_id),
    }
    return {
        **checks,
        "ok": all(checks.values()),
        "observed": {
            "n_paths": report["n_paths"],
            "months": report["months"],
            "vintage_id": report["vintage_id"],
            "prereg_digest": report.get("prereg_digest"),
        },
    }


# --------------------------------------------------------------------------- #
# the benchmark draw-span bias disclosure
# --------------------------------------------------------------------------- #


def restricted_elicitability(
    realizations: Sequence[float] | np.ndarray, var: float, es: float, level: float = 0.95
) -> float:
    """``elicitability_score`` against a RESTRICTED realization sample.

    ``benchmark_draw_span_bias`` binds WP2.11 to report the challenger-vs-benchmark
    elicitability comparison "restricted to the 1990-2020 realizations as well as
    on the full sample". That is computable from what the battery already stores,
    because the metric's two arguments are separable: the FORECAST pair is the
    generated ensemble's own ``(var_95, es_95)``, which the report carries per
    strategy, and the REALIZATIONS are history's, which are a function of the
    reference alone. Restricting the window touches only the realizations.

    The scoring function itself is the sealed one — imported, never restated — so
    the restricted number and the battery's own number can never diverge in
    definition, only in sample.
    """
    from ah.eval.metrics.tails import elicitability_score

    return float(elicitability_score(np.asarray(realizations, dtype=np.float64), var, es, level))


def strategy_forecast_pair(
    report: Mapping[str, Any], strategy_id: str, which: str = "unfiltered"
) -> tuple[float, float]:
    """The generated ``(VaR, ES)`` pair at the backtest level, from a stored report.

    ``ah.eval.metrics.tails._elicitability_metric`` forms its forecast as
    ``var_es(pooled_generated_returns, BACKTEST_LEVEL)`` with ``BACKTEST_LEVEL ==
    0.95`` — which is exactly what the report's ``<sid>.var_95`` / ``<sid>.es_95``
    rows already are. So the pair is READ, not recomputed, and a restricted-window
    score is anchored to the same forecast the sealed metric used.
    """
    by_name = {row["name"]: row for row in _results(report, which)}
    try:
        return (
            float(by_name[f"{strategy_id}.var_95"]["value"]),
            float(by_name[f"{strategy_id}.es_95"]["value"]),
        )
    except KeyError as exc:
        raise AblationError(f"report has no var_95/es_95 for strategy '{strategy_id}'") from exc


def historical_strategy_returns_dated(
    reference: Any, strategy: Any, derived: Mapping[str, Any] | None = None
) -> tuple[Any, np.ndarray] | None:
    """History's realized return path for one D4 strategy, WITH its date index.

    Same construction as ``ah.eval.metrics.tails._historical_strategy_returns`` —
    inner-join exactly this strategy's own legs (resolved through ``derived`` to
    their source factors) onto their shared date overlap, wrap as a single-path
    ensemble, and hand it to the SAME ``strategy_returns`` the generated side uses
    — and it returns the index the sealed helper discards. ``None`` when a leg has
    no historical series at all, mirroring the sealed helper exactly.

    ``tests/test_ablation.py`` asserts the values agree with the sealed helper's
    element for element, so this is a *widened return type*, not a second route to
    the arithmetic.
    """
    import pandas as pd

    from ah.eval.metrics.tails import strategy_returns
    from ah.gen.base import Ensemble, EnsembleMeta
    from ah.strategies import load_derived_series, strategy_legs

    derived = load_derived_series() if derived is None else derived
    legs = strategy_legs(strategy)
    needed = sorted({derived[leg].source_factor if leg in derived else leg for leg in legs})
    if any(f not in reference.historical_series for f in needed):
        return None
    joined = pd.concat(
        {f: reference.historical_series[f] for f in needed}, axis=1, join="inner"
    ).sort_index()
    if joined.empty:
        return None
    values = joined.to_numpy(dtype=np.float64)
    ensemble = Ensemble(
        paths=values[np.newaxis, :, :],
        factor_names=list(needed),
        meta=EnsembleMeta(
            generator_id="historical-train-val",
            vintage_id=reference.vintage_id,
            seed=reference.seed,
            n_paths=1,
            months=values.shape[0],
        ),
    )
    return joined.index, np.asarray(strategy_returns(ensemble, strategy, derived)).reshape(-1)
