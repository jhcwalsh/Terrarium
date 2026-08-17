"""Anti-test sweeps for every NEW judge in the spine v2 exam (obligation 6.1).

**Why this file exists.** Round two's B1 v2 reaction-function judge produced a
clean FAIL on all five seeds that carried **zero information about the model**:
the verdict-integrity review found its pass fraction *decreased* monotonically in
the reaction strength ``phi``, so a model with no reaction function at all scored
best and the bar was unreachable by any model, including a perfect one. The
exam's §6.1 therefore requires, before a judge is sealed, a sweep of the model
property the judge claims to measure, with the judge's pass rate shown to
**increase** in it.

**The rule, stated once and applied per bar.** A bar's pass rate must be
non-decreasing in *the effect it claims to measure*, and what that means depends
on the bar's shape:

- **One-sided bars** (O1, A1, A2) claim "more of this is better up to history's
  level". The sweep runs the effect from absent to history's own value and the
  pass rate must not fall along it.
- **Two-sided bars** (T1, D1-D4) claim "this should be *history's size*" -- both
  too little and too much are failures, so a sweep of the raw effect would
  correctly fall at the top and prove nothing. Their effect is therefore
  **closeness to the historical anchor**: at each grid point the sweep generates
  batches that miss the anchor by the same amount in each direction, and the pass
  rate must be non-decreasing as that miss shrinks to zero. A judge that is not
  maximised at the anchor fails this, which is precisely the B1 v2 defect
  translated to a two-sided bar. T1 additionally gets the one-sided sweep
  (no transmission -> history's transmission) because that is the literal B1 v2
  comparison and it is the one an owner will ask about.

**Determinism.** Every sweep draws from ``numpy.random.Generator(PCG64(seed))``
with its own literal seed below; no seed is derived from another by a stride
(the platform's seed-stride lesson), and a module-level assertion holds them
distinct. Re-running writes byte-identical output.

**The judges are the real ones.** Nothing here re-implements a judge or a
threshold: the sweeps import ``scripts/spine_v2_report``'s judge functions and
build their threshold block with ``sealed_from_anchors``, the same assembly the
seal writes. A sweep therefore cannot pass against numbers that differ from the
sealed ones.

Invocation (from the worktree root, no network needed):

    uv run python scripts/spine_v2_antitest.py
"""

from __future__ import annotations

import itertools
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from ah.gen.spine import QUADRANTS

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from spine_v2_report import (  # noqa: E402
    Batch,
    Decade,
    judge_a1,
    judge_a2,
    judge_d,
    judge_o1,
    judge_t1,
    sealed_from_anchors,
)

_REPO_ROOT = _SCRIPTS_DIR.parent
OUT_JSON = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-antitest-results.json"
OUT_MD = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-antitest-results.md"

#: One literal seed per sweep, all distinct.
SEED_T1_DIRECTIONAL = 20260901
SEED_T1_CLOSENESS = 20260902
SEED_O1 = 20260903
SEED_D1 = 20260904
SEED_D2 = 20260905
SEED_D3 = 20260906
SEED_D4 = 20260907
SEED_A1 = 20260908
SEED_A2 = 20260909
_SEEDS = (
    SEED_T1_DIRECTIONAL,
    SEED_T1_CLOSENESS,
    SEED_O1,
    SEED_D1,
    SEED_D2,
    SEED_D3,
    SEED_D4,
    SEED_A1,
    SEED_A2,
)
assert len(set(_SEEDS)) == len(_SEEDS), "every sweep must draw from its own seed"

#: Batches per grid point, and decades per batch. The decade count is the
#: campaign's own sealed batch size, so a sweep measures the judge at the size it
#: will actually be run at.
N_REPLICATES = 24
N_DECADES = 50
DECADE_MONTHS = 120
WARMUP_MONTHS = 12

#: A synthetic month's inflation, chosen relative to the sealed era line so that
#: "hot" and "cool" are unambiguous, and relative to the 4% allocation line so a
#: season sweep does not accidentally also sweep A1/A2.
_HOT_YOY_PP = 6.0
_COOL_YOY_PP = 1.0

#: The T1 sweep's synthetic decade: the monthly rate of downturn onsets that have
#: nothing to do with policy, and the lookahead a caused onset lands inside. Both
#: describe the SYNTHETIC MODEL, not the judge and not a bar.
_T1_BACKGROUND_RATE = 0.012
_T1_LOOKAHEAD_MONTHS = 12
_T1_EPISODE_GAP = (24, 60)
#: History's own transmission lift, the point a two-sided T1 sweep measures
#: closeness to (b_transmission_lift.point_estimates.rec_plus_cri.lift).
_T1_HISTORICAL_LIFT = 2.3718540268456376

#: Season index -> a label that puts the month on the right side of the growth
#: axis under the sealed grader. Recovery and expansion are expanding (EXP);
#: recession is REC; stagflation is STAG, which the mapping fix moved onto the
#: contracting side and which is the reason grader_v2 exists.
_SEASON_LABEL = {
    QUADRANTS.index("recession"): "REC",
    QUADRANTS.index("stagflation"): "STAG",
    QUADRANTS.index("recovery"): "EXP",
    QUADRANTS.index("expansion"): "EXP",
}
_SEASON_HOT = {
    QUADRANTS.index("recession"): False,
    QUADRANTS.index("stagflation"): True,
    QUADRANTS.index("recovery"): False,
    QUADRANTS.index("expansion"): True,
}


# --------------------------------------------------------------------------- #
# synthetic decade construction
# --------------------------------------------------------------------------- #


def _blank(n: int) -> dict[str, np.ndarray]:
    """The columns a Decade needs, filled with benign defaults."""
    yoy = np.full(n, _COOL_YOY_PP)
    yoy[:WARMUP_MONTHS] = np.nan
    return {
        "labels": np.array(["EXP"] * n, dtype=object),
        "yoy": yoy,
        "tight": np.zeros(n, dtype=bool),
        "equities": np.zeros(n),
        "bonds": np.zeros(n),
        "commodities": np.zeros(n),
    }


def _decade_from_seasons(seasons: np.ndarray) -> Decade:
    """A decade whose season sequence is exactly ``seasons`` after the warm-up."""
    n = seasons.size
    cols = _blank(n)
    labels = cols["labels"]
    yoy = cols["yoy"]
    for t in range(n):
        s = int(seasons[t])
        labels[t] = _SEASON_LABEL[s]
        if t >= WARMUP_MONTHS:
            yoy[t] = _HOT_YOY_PP if _SEASON_HOT[s] else _COOL_YOY_PP
    return Decade(
        labels=labels,
        yoy=yoy,
        tight=cols["tight"],
        equities=cols["equities"],
        bonds=cols["bonds"],
        commodities=cols["commodities"],
    )


def _spell_sequence(
    rng: np.random.Generator, target: int, filler: int, median_months: float, n: int
) -> np.ndarray:
    """Alternate ``target`` and ``filler`` seasons; target spells centre on
    ``median_months``. Lengths are drawn normal and clipped at one month, so the
    pooled median of the target's spells tracks ``median_months`` directly."""
    out = np.full(n, filler, dtype=np.int64)
    t = WARMUP_MONTHS
    use_target = True
    while t < n:
        if use_target:
            length = int(max(1, round(float(rng.normal(median_months, 1.2)))))
            out[t : t + length] = target
        else:
            length = int(max(1, round(float(rng.normal(4.0, 1.2)))))
            out[t : t + length] = filler
        t += length
        use_target = not use_target
    return out


def _t1_decade(rng: np.random.Generator, spec: dict[str, Any]) -> Decade:
    """A decade whose downturns are caused by tight policy to a stated degree.

    Tight policy arrives in EPISODES (6-13 months, separated by ``gap``), because
    that is how yield-curve inversions actually arrive and because independent
    monthly draws would put a tight month within a year of almost every month,
    leaving nothing for the lift to measure. The spec has three knobs, all
    properties of the SYNTHETIC MODEL and none of them a judge or a bar:
    ``p_cause`` (the chance an episode causes a downturn onset in the following
    year), ``background`` (the monthly rate of onsets that have nothing to do
    with policy) and ``gap`` (how far apart episodes sit). Turning ``p_cause``
    up, or ``background`` down, or ``gap`` wider all raise the transmission lift
    -- which is how the sweep reaches both sides of a two-sided band.
    """
    n = DECADE_MONTHS
    cols = _blank(n)
    p_cause = float(spec["p_cause"])
    background = float(spec["background"])
    gap_lo, gap_hi = (int(x) for x in spec.get("gap", _T1_EPISODE_GAP))
    tight = np.zeros(n, dtype=bool)
    episode_starts: list[int] = []
    t = int(rng.integers(0, 24))
    while t < n:
        t += int(rng.integers(gap_lo, gap_hi))
        if t >= n:
            break
        length = int(rng.integers(6, 14))
        tight[t : t + length] = True
        episode_starts.append(t)
        t += length
    onset = rng.random(n) < background
    for start in episode_starts:
        if float(rng.random()) < p_cause:
            offset = int(rng.integers(1, _T1_LOOKAHEAD_MONTHS + 1))
            if start + offset < n:
                onset[start + offset] = True
    labels = cols["labels"]
    for t in np.flatnonzero(onset):
        labels[t : t + 4] = "REC"
    return Decade(
        labels=labels,
        yoy=cols["yoy"],
        tight=tight,
        equities=cols["equities"],
        bonds=cols["bonds"],
        commodities=cols["commodities"],
    )


def _o1_decade(rng: np.random.Generator, clockwise_probability: float) -> Decade:
    """A decade whose season changes follow the clock's order with the given
    probability, and go somewhere else otherwise."""
    from ah.gen.spine import CLOCKWISE

    successor = {a: b for a, b in CLOCKWISE}
    n = DECADE_MONTHS
    seasons = np.zeros(n, dtype=np.int64)
    current = int(rng.integers(0, len(QUADRANTS)))
    t = 0
    while t < n:
        length = int(max(1, round(float(rng.normal(4.0, 1.2)))))
        seasons[t : t + length] = current
        t += length
        if float(rng.random()) < clockwise_probability:
            current = successor[current]
        else:
            others = [q for q in range(len(QUADRANTS)) if q not in (current, successor[current])]
            current = int(others[int(rng.integers(0, len(others)))])
    return _decade_from_seasons(seasons)


def _allocation_decade(
    rng: np.random.Generator,
    *,
    commodity_excess_high_pp: float,
    correlation_high: float,
    correlation_low: float,
) -> Decade:
    """A decade split into a low-inflation half and a high-inflation half, with
    the stock-bond correlation and the commodity-minus-bond spread set per half."""
    n = DECADE_MONTHS
    cols = _blank(n)
    yoy = cols["yoy"]
    high = np.zeros(n, dtype=bool)
    high[n // 2 :] = True
    yoy[:] = np.where(high, _HOT_YOY_PP, _COOL_YOY_PP)
    yoy[:WARMUP_MONTHS] = np.nan

    equities = rng.normal(0.0, 0.04, n)
    shock = rng.normal(0.0, 0.02, n)
    rho = np.where(high, correlation_high, correlation_low)
    bonds = rho * (equities * 0.02 / 0.04) + np.sqrt(np.maximum(1.0 - rho**2, 0.0)) * shock
    # bonds carry a small positive drift in both states; commodities carry the
    # swept excess when inflation is high and a fixed small one when it is not.
    bonds = bonds + 0.005
    commodities = rng.normal(0.0, 0.05, n) + 0.005
    commodities = commodities + np.where(high, commodity_excess_high_pp / 1200.0, 0.0)
    return Decade(
        labels=cols["labels"],
        yoy=yoy,
        tight=cols["tight"],
        equities=equities,
        bonds=bonds,
        commodities=commodities,
    )


def _batch(builder: Callable[[], Decade]) -> Batch:
    return Batch(tuple(builder() for _ in range(N_DECADES)))


# --------------------------------------------------------------------------- #
# the sweeps
# --------------------------------------------------------------------------- #


def _pass_rate(
    seed: int,
    grid: list[Any],
    make_batch: Callable[[np.random.Generator, Any], Batch],
    judge: Callable[[Batch], dict[str, Any]],
) -> tuple[list[float], list[float]]:
    """Pass rate and mean judged statistic at each grid point."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rates: list[float] = []
    values: list[float] = []
    for point in grid:
        passes = 0
        stats: list[float] = []
        for _ in range(N_REPLICATES):
            verdict = judge(make_batch(rng, point))
            passes += int(bool(verdict["pass"]))
            stats.append(float(verdict["value"]))
        rates.append(passes / N_REPLICATES)
        values.append(float(np.nanmean(stats)))
    return rates, values


def _two_sided(
    seed: int,
    misses: list[float],
    make_batch: Callable[[np.random.Generator, float], Batch],
    judge: Callable[[Batch], dict[str, Any]],
    anchor: float,
    floor: float | None = None,
) -> tuple[list[float], list[float]]:
    """Closeness sweep: at each miss size, half the batches sit that far ABOVE the
    anchor and half that far BELOW it. Returns the pass rate per miss size in
    the order given (which callers pass largest-miss-first, so a correct judge's
    rates are non-decreasing)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rates: list[float] = []
    values: list[float] = []
    for miss in misses:
        passes = 0
        stats: list[float] = []
        for k in range(N_REPLICATES):
            target = anchor + miss if k % 2 == 0 else anchor - miss
            if floor is not None:
                target = max(floor, target)
            verdict = judge(make_batch(rng, target))
            passes += int(bool(verdict["pass"]))
            stats.append(float(verdict["value"]))
        rates.append(passes / N_REPLICATES)
        values.append(float(np.nanmean(stats)))
    return rates, values


def _monotone(rates: list[float]) -> bool:
    return all(b >= a - 1e-12 for a, b in itertools.pairwise(rates))


def run_sweeps(sealed: dict[str, Any]) -> dict[str, Any]:
    """Every anti-test sweep, as a JSON-ready record."""
    sweeps: dict[str, Any] = {}

    # ---- T1, one-sided: no transmission -> history's transmission -------------
    grid = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    rates, values = _pass_rate(
        SEED_T1_DIRECTIONAL,
        grid,
        lambda rng, m: _batch(
            lambda: _t1_decade(rng, {"p_cause": m, "background": _T1_BACKGROUND_RATE})
        ),
        lambda b: judge_t1(b, sealed),
    )
    sweeps["T1_directional"] = {
        "bar": "T1",
        "shape": "one-sided sweep of the effect itself",
        "effect": "the probability that a tight-policy episode causes a downturn within a year",
        "grid": grid,
        "pass_rate": rates,
        "mean_statistic": values,
        "statistic": "pooled transmission lift",
        "monotone_non_decreasing": _monotone(rates),
        "note": (
            "the literal B1 v2 comparison: a judge whose pass rate falls as the modelled "
            "effect grows toward history's is measuring something other than the effect"
        ),
    }

    # ---- T1, two-sided: closeness to history's lift ---------------------------
    grid = [
        {"p_cause": 0.0, "background": _T1_BACKGROUND_RATE},
        {"p_cause": 0.3, "background": _T1_BACKGROUND_RATE},
        {"p_cause": 0.6, "background": _T1_BACKGROUND_RATE},
        {"p_cause": 1.0, "background": _T1_BACKGROUND_RATE},
        {"p_cause": 1.0, "background": 0.5 * _T1_BACKGROUND_RATE},
        {"p_cause": 1.0, "background": 0.15 * _T1_BACKGROUND_RATE},
        {"p_cause": 1.0, "background": 0.0, "gap": (60, 110)},
    ]
    rates, values = _pass_rate(
        SEED_T1_CLOSENESS,
        grid,
        lambda rng, spec: _batch(lambda: _t1_decade(rng, spec)),
        lambda b: judge_t1(b, sealed),
    )
    # T1's band is two-sided, so the raw grid is re-ordered by how far the
    # REALIZED lift sits from history's own -- the judge's pass rate must rise as
    # that distance shrinks. Ordering by the realized statistic rather than by a
    # calibrated parameter value keeps the sweep free of any tuning constant.
    band = [float(x) for x in sealed["bars"]["T1_lift_band"]]

    def _reach(lift: float) -> float:
        """How far the lift sits from history's, as a fraction of the distance
        history's own value sits from the band edge on that side. 0 is exactly
        history; 1 is exactly the band edge; above 1 is outside. Normalising by
        side matters because the band is not symmetric around the anchor."""
        if lift <= _T1_HISTORICAL_LIFT:
            return (_T1_HISTORICAL_LIFT - lift) / (_T1_HISTORICAL_LIFT - band[0])
        return (lift - _T1_HISTORICAL_LIFT) / (band[1] - _T1_HISTORICAL_LIFT)

    reach = [_reach(v) for v in values]
    order = sorted(range(len(grid)), key=lambda i: -reach[i])
    ordered_rates = [rates[i] for i in order]
    sweeps["T1_closeness"] = {
        "bar": "T1",
        "shape": "two-sided closeness sweep",
        "effect": (
            "closeness of the realized transmission lift to history's "
            f"{_T1_HISTORICAL_LIFT:.4f}x, spanning both sides of the band"
        ),
        "grid": [dict(spec) for spec in grid],
        "pass_rate": rates,
        "mean_statistic": values,
        "historical_lift": _T1_HISTORICAL_LIFT,
        "distance_from_history": [abs(v - _T1_HISTORICAL_LIFT) for v in values],
        "reach_toward_band_edge": reach,
        "pass_rate_ordered_by_closeness": ordered_rates,
        "statistic": "pooled transmission lift",
        "monotone_non_decreasing": _monotone(ordered_rates),
        "note": (
            "the raw grid is re-ordered by the realized lift's distance from history's, "
            "so the monotonicity claim is about closeness and not about the synthetic "
            "parameter; the raw pass_rate row is published beside it and does fall at the "
            "top, which is the two-sided band working as intended"
        ),
    }

    # ---- O1, one-sided --------------------------------------------------------
    grid = [0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9]
    rates, values = _pass_rate(
        SEED_O1,
        grid,
        lambda rng, q: _batch(lambda: _o1_decade(rng, q)),
        lambda b: judge_o1(b, sealed),
    )
    sweeps["O1"] = {
        "bar": "O1",
        "shape": "one-sided sweep of the effect itself",
        "effect": "the probability that a season change follows the clock's order",
        "grid": grid,
        "pass_rate": rates,
        "mean_statistic": values,
        "statistic": "pooled clockwise fraction",
        "monotone_non_decreasing": _monotone(rates),
    }

    # ---- D1-D4, two-sided closeness to each season's anchor -------------------
    d_seeds = [("D1", SEED_D1), ("D2", SEED_D2), ("D3", SEED_D3), ("D4", SEED_D4)]
    misses = [8.0, 6.0, 4.0, 3.0, 2.0, 1.0, 0.0]
    for (code, seed), season in zip(d_seeds, QUADRANTS, strict=True):
        anchor = float(sealed["bars"]["D_anchor_medians_months"][season])
        target_index = QUADRANTS.index(season)
        filler_index = QUADRANTS.index("recovery" if season != "recovery" else "expansion")

        def make(
            rng: np.random.Generator, median: float, ti=target_index, fi=filler_index
        ) -> Batch:
            return _batch(
                lambda: _decade_from_seasons(_spell_sequence(rng, ti, fi, median, DECADE_MONTHS))
            )

        rates, values = _two_sided(
            seed,
            misses,
            make,
            lambda b, c=code: judge_d(b, sealed, c),
            anchor=anchor,
            floor=1.0,
        )
        sweeps[code] = {
            "bar": code,
            "season": season,
            "shape": "two-sided closeness sweep",
            "effect": (
                f"closeness of the generated {season} spell median to history's "
                f"decade-pooled {anchor:g} months, both directions"
            ),
            "anchor_months": anchor,
            "grid_miss_months": misses,
            "pass_rate": rates,
            "mean_statistic": values,
            "statistic": "pooled completed-spell median, months",
            "monotone_non_decreasing": _monotone(rates),
        }

    # ---- A1, one-sided --------------------------------------------------------
    grid = [-4.0, -2.0, 0.0, 1.0, 2.0, 3.5, 5.0]
    rates, values = _pass_rate(
        SEED_A1,
        grid,
        lambda rng, x: _batch(
            lambda: _allocation_decade(
                rng, commodity_excess_high_pp=x, correlation_high=0.0, correlation_low=0.0
            )
        ),
        lambda b: judge_a1(b, sealed),
    )
    sweeps["A1"] = {
        "bar": "A1",
        "shape": "one-sided sweep of the effect itself",
        "effect": "the commodities-minus-bonds excess, in pp/yr, added when inflation is high",
        "grid": grid,
        "pass_rate": rates,
        "mean_statistic": values,
        "statistic": "pooled spread(high) minus spread(low), pp/yr",
        "monotone_non_decreasing": _monotone(rates),
    }

    # ---- A2, one-sided --------------------------------------------------------
    grid = [-0.10, 0.0, 0.10, 0.20, 0.30, 0.45, 0.60]
    rates, values = _pass_rate(
        SEED_A2,
        grid,
        lambda rng, r: _batch(
            lambda: _allocation_decade(
                rng, commodity_excess_high_pp=0.0, correlation_high=r, correlation_low=0.0
            )
        ),
        lambda b: judge_a2(b, sealed),
    )
    sweeps["A2"] = {
        "bar": "A2",
        "shape": "one-sided sweep of the effect itself",
        "effect": "the stock-bond correlation imposed on high-inflation months",
        "grid": grid,
        "pass_rate": rates,
        "mean_statistic": values,
        "statistic": "pooled high-minus-low stock-bond correlation difference",
        "monotone_non_decreasing": _monotone(rates),
    }
    return sweeps


def _value_key(sweep: dict[str, Any]) -> str:
    return "value"


def main() -> None:
    sealed = sealed_from_anchors()
    sweeps = run_sweeps(sealed)
    failures = [name for name, s in sweeps.items() if not s["monotone_non_decreasing"]]
    record = {
        "schema": "spine-v2-antitest-1",
        "obligation": (
            "exam section 6.1: before a judge is sealed, sweep the model property the judge "
            "claims to measure and confirm the judge's pass rate increases in it"
        ),
        "rule": (
            "one-sided bars (O1, A1, A2) are swept on the effect itself, from absent to "
            "history's own level, and the pass rate must not fall along it. Two-sided bars "
            "(T1, D1-D4) are swept on CLOSENESS to the historical anchor, because a raw "
            "sweep of a two-sided bar would correctly fall at the top and prove nothing: "
            "D1-D4 do it by generating half the batches a fixed distance above the anchor "
            "and half the same distance below it at each grid point, and T1 does it by "
            "running a raw parameter grid that spans both sides and then re-ordering the "
            "points by how far the REALIZED lift sits from history's, normalised by the "
            "band's own half-width on that side (its band is not symmetric around the "
            "anchor). T1 additionally gets the one-sided sweep, because that is the "
            "literal B1 v2 comparison"
        ),
        "n_replicates": N_REPLICATES,
        "n_decades_per_batch": N_DECADES,
        "decade_months": DECADE_MONTHS,
        "seeds": {
            "T1_directional": SEED_T1_DIRECTIONAL,
            "T1_closeness": SEED_T1_CLOSENESS,
            "O1": SEED_O1,
            "D1": SEED_D1,
            "D2": SEED_D2,
            "D3": SEED_D3,
            "D4": SEED_D4,
            "A1": SEED_A1,
            "A2": SEED_A2,
        },
        "thresholds_judged_against": sealed["bars"],
        "sweeps": sweeps,
        "all_monotone": not failures,
        "non_monotone_sweeps": failures,
    }
    OUT_JSON.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    _write_markdown(record)
    for name, sweep in sweeps.items():
        rates = ", ".join(f"{r:.2f}" for r in sweep["pass_rate"])
        flag = "OK" if sweep["monotone_non_decreasing"] else "NOT MONOTONE"
        print(f"{name:16s} [{rates}]  {flag}")
    print(f"all monotone: {not failures}")
    if failures:
        raise SystemExit(f"NOT SEALABLE: non-monotone sweeps {failures}")


def _write_markdown(record: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Spine v2 - anti-test sweep results (run BEFORE the seal)")
    lines.append("")
    lines.append(
        "Produced by `scripts/spine_v2_antitest.py`, which imports the real judges from "
        "`scripts/spine_v2_report.py` and the real thresholds through `sealed_from_anchors` "
        "- the same assembly the seal writes. Machine-readable values: "
        "`docs/superpowers/specs/spine-v2-antitest-results.json`."
    )
    lines.append("")
    lines.append(f"**The obligation.** {record['obligation']}.")
    lines.append("")
    lines.append(f"**The rule.** {record['rule']}.")
    lines.append("")
    lines.append(
        f"**Size.** {record['n_replicates']} batches per grid point, "
        f"{record['n_decades_per_batch']} decades per batch (the campaign's own sealed batch "
        f"size), {record['decade_months']} months per decade. One literal seed per sweep, all "
        "distinct; re-running reproduces the JSON byte for byte."
    )
    lines.append("")
    lines.append(
        f"**Verdict: {'every sweep is monotone non-decreasing' if record['all_monotone'] else 'NOT SEALABLE'}.**"
    )
    lines.append("")
    for name, sweep in record["sweeps"].items():
        lines.append(f"## {name} - {sweep['effect']}")
        lines.append("")
        grid_key = (
            "grid"
            if "grid" in sweep
            else ("grid_miss" if "grid_miss" in sweep else "grid_miss_months")
        )
        header = "effect" if grid_key == "grid" else "miss from anchor"
        lines.append(f"| {header} | pass rate | mean {sweep['statistic'].split(';')[0]} |")
        lines.append("|---|---|---|")
        for point, rate, value in zip(
            sweep[grid_key], sweep["pass_rate"], sweep["mean_statistic"], strict=True
        ):
            label = (
                ", ".join(f"{k}={v}" for k, v in point.items())
                if isinstance(point, dict)
                else f"{point:g}"
            )
            lines.append(f"| {label} | **{rate:.2f}** | {value:.4f} |")
        lines.append("")
        if "pass_rate_ordered_by_closeness" in sweep:
            ordered = ", ".join(f"{r:.2f}" for r in sweep["pass_rate_ordered_by_closeness"])
            lines.append(
                f"Pass rate re-ordered from the farthest realized lift to the closest: "
                f"**[{ordered}]**."
            )
            lines.append("")
        lines.append(
            f"Monotone non-decreasing: **{'yes' if sweep['monotone_non_decreasing'] else 'NO'}**."
        )
        if "note" in sweep:
            lines.append("")
            lines.append(sweep["note"][0].upper() + sweep["note"][1:] + ".")
        lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
