"""Task 8: B3 -- the over-commitment grid under spine worlds (world 802).

Ports the measurement method VERBATIM from the committed E1 declaration,
``docs/superpowers/specs/2026-08-15-e1-overcommitment-measurement.md`` (world
...703, the "Lost Decade" under the declared 6-month stress blocks), onto
world ...802 (spine-conditioned "The Hard Landing"), swapping only the world.
Same four allocation arms (15/35/40/55 points private, out of a 100-point
book with cash fixed at 2), the same standing ladder harness (20 seeds), the
same coverage statistic (worst unfunded/liquid per quarter, breach line 1.0 --
``ah.eval.decision_metrics.liquidity_shortfall_probability``, the cov-01
constant), and the same hold-course (no decisions) institution run, via
``ah.play.simulate_play`` over ``ah.port.adapter.run_gen_path``'s tape.

Seed scheme: the E1 doc's own (``771204 + 7919*k``), adapted to world 802's
base seed -- ``199002 + 7919*k`` for k in range(20) -- which is ALSO the
platform's own per-path seed stride (``ah/port/adapter.py``'s ``SEED_STRIDE``,
asserted equal to the engine's own rule), so this ladder is bit-identical to
what ``ah bundle``/``ah run`` would sample as the world's own first 20 paths.

Book construction, ported verbatim from the E1 protocol paragraph: cash fixed
at 2 points; private sleeves (pe/pc/re) scaled proportionally from the
default 20/8/7 (sums to 35, the shipped/default arm); liquid sleeves
(equity/bonds/hy/commodities -- ``ah.port.adapter.GEN_START_TARGETS``, the
generated-world default book with reits' 8 points folded into equity, OD-3)
scaled proportionally from 41/12/5/5 (sums to 63) to absorb the difference.
At the breach arm (55 private) this leaves exactly 43 liquid points, matching
the E1 doc's own reading #2 verbatim ("keeps enough liquid assets (43
points)") -- the strongest available cross-check that the book formula here
matches the one E1 actually ran.

Judged against the SEALED b3 bar
(``docs/superpowers/specs/spine-pilot-prereg.json``, commit ``c9bd036``):
monotone coverage in allocation, >=1 breach seed of 20 at the 55-point arm,
and a third check this script adds per the Task-8 brief -- hold-course depth
inside the world's declared band. See ``DEPTH_BAND`` below for exactly how
that band is constructed and cited; it is NOT a literal port (neither the E1
doc nor the stress-03 method states a numeric two-sided band) and is called
out as a documented deviation in the results appendix.

THE SEAL: this script POSTDATES ``spine-pilot-prereg.json``'s hash lock (it
did not exist when the seal was cut) and is not one of the hashed files. It
reads the sealed b3 thresholds and never writes them.

Import-safe: importing this module touches no data, samples no ensemble, and
writes no file. All of that happens only under ``if __name__ == "__main__":``.

Run:

    uv run python scripts/spine_pilot_b3.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
SEALED_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-pilot-prereg.json"
WORLD_PATH = _REPO_ROOT / "src" / "ah" / "presets" / "spine_pilot.json"
RESULTS_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-08-15-spine-pilot-results.md"

SEED_STRIDE = 7919  # the platform stride (ah/port/adapter.py's own seed rule)
N_SEEDS = 20

#: The default/floor/ceiling/breach book's fixed points, ported from the E1
#: protocol paragraph and ``ah.port.adapter.GEN_START_TARGETS``. Cash is
#: fixed at 2 regardless of arm (``ah.play.START_CASH``), never scaled.
_PRIVATE_BASE: dict[str, float] = {"pe": 20.0, "pc": 8.0, "re": 7.0}  # sums to 35
_LIQUID_BASE: dict[str, float] = {
    "equity": 41.0,
    "bonds": 12.0,
    "hy": 5.0,
    "commodities": 5.0,
}  # 63
_CASH_POINTS = 2.0

#: The declared band for the hold-course depth check (median peak-to-trough
#: equity drawdown, monthly resolution -- the same statistic
#: ``scripts/stress_report.py``'s ``depth_report`` computes). NEITHER the E1
#: doc nor the stress-03 method
#: (``docs/current/stress-scenario-methodology.md``) states a numeric
#: two-sided band: E1 never measures depth at all (it is arm-invariant, a
#: market fact independent of the institution's book, so it sits outside
#: E1's per-arm coverage/forced-secondary/final-value table), and stress-03
#: reports a single point value, not a band. This script therefore
#: CONSTRUCTS the band from the two fixed numbers already on the record for
#: world ...703, whose x_stress block ...802 inherits VERBATIM (Task-8
#: brief):
#:   - shallow bound -37.5%: world 703's own stress-03 measurement
#:     ("the third measurement... median peak-to-trough -37.5% over 18
#:     months", stress-scenario-methodology.md) -- since 802 layers spine
#:     hazard corrections ON TOP of the identical entry-severity/block rule
#:     (the severity_table's dwell/stratum shifts only LENGTHEN and DEEPEN
#:     crisis dwelling, never shorten it), 802 should read at least this
#:     deep.
#:   - deep bound -42.6%: the same document's Limits section, "the worst
#:     rolling twelve months in the panel is -42.6%" ("A ceiling set by the
#:     pool") -- the panel's own realized extreme; both 703 and 802 draw
#:     only real panel months, so this is the tightest documented
#:     structural bound available to quote.
#: This is a DOCUMENTED DEVIATION, not a literal port -- see the results
#: appendix and the Task-8 report for the full reasoning.
DEPTH_BAND: tuple[float, float] = (-0.426, -0.375)


def _arm_targets(private_pct: float) -> dict[str, float]:
    """The declared book at one grid point (E1 protocol, verbatim): cash
    fixed at 2, private sleeves scaled proportionally from 20/8/7, liquid
    sleeves scaled proportionally from 41/12/5/5 to absorb the difference."""
    p_scale = private_pct / sum(_PRIVATE_BASE.values())
    liquid_sum = 100.0 - _CASH_POINTS - private_pct
    l_scale = liquid_sum / sum(_LIQUID_BASE.values())
    targets = {a: v * p_scale for a, v in _PRIVATE_BASE.items()}
    targets.update({a: v * l_scale for a, v in _LIQUID_BASE.items()})
    return targets


def _drawdown(returns_pct: np.ndarray) -> tuple[float, int]:
    """(depth, duration_months) of one path's deepest equity drawdown.

    Ported verbatim from ``scripts/stress_report.py``'s ``_drawdown``, with
    one adaptation: ``EnginePaths.returns["equity"]`` (``run_gen_path``'s
    contract) is PERCENT, not decimal, so the division by 100 here is new;
    the drawdown/duration algebra is unchanged.
    """
    wealth = np.cumprod(1.0 + returns_pct / 100.0)
    running_max = np.maximum.accumulate(wealth)
    drawdown = wealth / running_max - 1.0
    trough = int(np.argmin(drawdown))
    at_peak = np.flatnonzero(wealth[: trough + 1] == running_max[trough])
    peak = int(at_peak[-1]) if at_peak.size else 0
    return float(drawdown[trough]), trough - peak


def _coverage_per_quarter(result: Any) -> np.ndarray:
    """unfunded/liquid, per quarter -- the P-B binding ratio
    ``ah.eval.decision_metrics.liquidity_shortfall_probability`` judges."""
    out = np.empty(len(result.quarters), dtype=np.float64)
    for i, q in enumerate(result.quarters):
        liquid_total = sum(q.liquid_values.values())
        out[i] = q.unfunded_total / liquid_total if liquid_total > 0.0 else float("inf")
    return out


def _load_sealed() -> dict[str, Any]:
    return json.loads(SEALED_PATH.read_text(encoding="utf-8"))


def _load_world() -> Any:
    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


# --------------------------------------------------------------------------- #
# the measurement run itself -- only reached under __main__
# --------------------------------------------------------------------------- #


def _run_all(world: Any, seeds: list[int], grid: list[float]) -> dict[str, Any]:
    """One run per (seed, arm). Refusals are recorded, never retried
    (SpineRefusal per seed is a data point, not a rerun trigger)."""
    import ah.gen.spine  # noqa: F401  # the registration hook (blocks/flow pattern)
    from ah.gen.spine import SpineRefusal
    from ah.play import simulate_play
    from ah.port.adapter import run_gen_path

    per_arm: dict[float, dict[str, list[Any]]] = {
        arm: {
            "worst_coverage": [],
            "forced_secondaries": [],
            "final_value": [],
            "coverage_rows": [],
        }
        for arm in grid
    }
    depths: list[float] = []
    durations: list[int] = []
    refusals: list[dict[str, Any]] = []
    seed_rows: list[dict[str, Any]] = []

    for seed in seeds:
        try:
            paths = run_gen_path(world, seed)
        except SpineRefusal as exc:
            refusals.append({"seed": seed, "reason": str(exc)})
            seed_rows.append({"seed": seed, "refused": True, "reason": str(exc)})
            continue

        depth, duration = _drawdown(paths.returns["equity"])
        depths.append(depth)
        durations.append(duration)

        arm_results: dict[float, dict[str, Any]] = {}
        for arm in grid:
            targets = _arm_targets(arm)
            result = simulate_play(paths, decisions=None, start_targets=targets)
            cov = _coverage_per_quarter(result)
            worst = float(np.max(cov))
            per_arm[arm]["worst_coverage"].append(worst)
            per_arm[arm]["forced_secondaries"].append(result.forced_secondaries)
            per_arm[arm]["final_value"].append(result.final_value)
            per_arm[arm]["coverage_rows"].append(cov)
            arm_results[arm] = {
                "worst_coverage": worst,
                "forced_secondaries": result.forced_secondaries,
                "final_value": result.final_value,
            }
        seed_rows.append(
            {
                "seed": seed,
                "refused": False,
                "depth": depth,
                "duration": duration,
                "arms": arm_results,
            }
        )

    from ah.eval.decision_metrics import liquidity_shortfall_probability

    arm_stats: dict[float, dict[str, Any]] = {}
    for arm in grid:
        rows = per_arm[arm]
        worst = np.asarray(rows["worst_coverage"], dtype=np.float64)
        n = int(worst.size)
        cov_matrix = np.stack(rows["coverage_rows"]) if rows["coverage_rows"] else np.empty((0, 0))
        breach_frac = liquidity_shortfall_probability(cov_matrix, threshold=1.0) if n else 0.0
        breach_count = int(np.sum(worst >= 1.0)) if n else 0
        fs = np.asarray(rows["forced_secondaries"], dtype=np.int64)
        fv = np.asarray(rows["final_value"], dtype=np.float64)
        arm_stats[arm] = {
            "n": n,
            "breach_count": breach_count,
            "breach_frac": breach_frac,
            "forced_secondary_seeds": int(np.sum(fs > 0)) if n else 0,
            "worst_coverage_median": float(np.median(worst)) if n else float("nan"),
            "worst_coverage_max": float(np.max(worst)) if n else float("nan"),
            "final_value_min": float(np.min(fv)) if n else float("nan"),
            "final_value_median": float(np.median(fv)) if n else float("nan"),
            "below_100": int(np.sum(fv < 100.0)) if n else 0,
            "below_75": int(np.sum(fv < 75.0)) if n else 0,
            "below_50": int(np.sum(fv < 50.0)) if n else 0,
        }

    return {
        "seed_rows": seed_rows,
        "arm_stats": arm_stats,
        "refusals": refusals,
        "depths": depths,
        "durations": durations,
    }


def _judge(sealed_b3: dict[str, Any], grid: list[float], run: dict[str, Any]) -> dict[str, Any]:
    """The three-part B3 verdict."""
    arm_stats = run["arm_stats"]

    # (a) monotone coverage in allocation -- the E1 doc's own reading walks
    # the table's MEDIAN column (0.103 -> 0.309 -> 0.382 -> 0.719) as the
    # legible signal; this script adopts the per-arm MEDIAN worst-coverage,
    # non-decreasing across the grid in its declared order, as the operative
    # definition (documented choice -- the doc states no formula).
    medians = [arm_stats[arm]["worst_coverage_median"] for arm in grid]
    monotone = all(medians[i] <= medians[i + 1] for i in range(len(medians) - 1))
    monotone_required = bool(sealed_b3["coverage_must_be_monotone"])
    verdict_monotone = bool(monotone) if monotone_required else True

    # (b) breach seeds at the 55-point arm
    breach_arm = grid[-1]
    breach_count = arm_stats[breach_arm]["breach_count"]
    min_breach = int(sealed_b3["min_breach_seeds_at_55"])
    verdict_breach = breach_count >= min_breach

    # (c) hold-course depth inside the declared band (see DEPTH_BAND)
    depths = run["depths"]
    median_depth = float(np.median(depths)) if depths else float("nan")
    lo, hi = DEPTH_BAND
    verdict_depth = bool(depths) and lo <= median_depth <= hi

    return {
        "monotone": {
            "pass": verdict_monotone,
            "medians": medians,
            "raw_monotone": monotone,
        },
        "breach": {
            "pass": verdict_breach,
            "breach_count": breach_count,
            "n": arm_stats[breach_arm]["n"],
            "threshold": min_breach,
        },
        "depth": {
            "pass": verdict_depth,
            "median_depth": median_depth,
            "band": DEPTH_BAND,
            "n": len(depths),
        },
        "overall": bool(verdict_monotone and verdict_breach and verdict_depth),
    }


def _fmt_bool(p: bool) -> str:
    return "PASS" if p else "FAIL"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _print_console(grid: list[float], run: dict[str, Any], verdict: dict[str, Any]) -> None:
    print(f"B3: {len(run['seed_rows'])} seeds attempted, {len(run['refusals'])} refused")
    print()
    header = f"{'arm':>6} | {'breach':>8} | {'fs seeds':>9} | {'cov med':>8} | {'cov max':>8} | {'final min':>10} | {'final med':>10}"
    print(header)
    print("-" * len(header))
    for arm in grid:
        s = run["arm_stats"][arm]
        print(
            f"{arm:>6.0f} | {s['breach_count']:>4}/{s['n']:<3} | {s['forced_secondary_seeds']:>4}/{s['n']:<4} | "
            f"{s['worst_coverage_median']:>8.4f} | {s['worst_coverage_max']:>8.4f} | "
            f"{s['final_value_min']:>10.2f} | {s['final_value_median']:>10.2f}"
        )
    print()
    print(
        f"hold-course depth: median {verdict['depth']['median_depth']:.4f} over {verdict['depth']['n']} seeds"
    )
    print(f"declared band: [{DEPTH_BAND[0]:.4f}, {DEPTH_BAND[1]:.4f}]")
    print()
    print("=== B3 VERDICT ===")
    print(
        f"(a) monotone coverage in allocation: {_fmt_bool(verdict['monotone']['pass'])}  medians={verdict['monotone']['medians']}"
    )
    print(
        f"(b) breach seeds at {grid[-1]:.0f}: {_fmt_bool(verdict['breach']['pass'])}  "
        f"{verdict['breach']['breach_count']}/{verdict['breach']['n']} (need >= {verdict['breach']['threshold']})"
    )
    print(
        f"(c) hold-course depth inside declared band: {_fmt_bool(verdict['depth']['pass'])}  "
        f"{verdict['depth']['median_depth']:.4f} in [{DEPTH_BAND[0]:.4f}, {DEPTH_BAND[1]:.4f}]"
    )
    print(f"OVERALL: {_fmt_bool(verdict['overall'])}")


def _append_report(
    sealed: dict[str, Any],
    seeds: list[int],
    grid: list[float],
    run: dict[str, Any],
    verdict: dict[str, Any],
) -> None:
    lines: list[str] = []
    lines.append("")
    lines.append("## B3 -- the over-commitment grid under spine worlds (Task 8)")
    lines.append("")
    lines.append(
        "Method citation: `docs/superpowers/specs/2026-08-15-e1-overcommitment-measurement.md` "
        "(the E1 declaration, world `...703`), ported VERBATIM onto world `...802` -- same "
        "four allocation arms, same 20-seed ladder harness (`199002 + 7919*k`, world 802's own "
        "base seed and the platform's own per-path stride), same book construction "
        "(cash fixed at 2; private sleeves scaled from 20/8/7; liquid sleeves scaled from "
        "41/12/5/5), same coverage statistic (worst unfunded/liquid, breach line 1.0 -- "
        "`ah.eval.decision_metrics.liquidity_shortfall_probability`), same hold-course "
        "(no-decisions) institution run. Sealed b3 bar: "
        "`docs/superpowers/specs/spine-pilot-prereg.json` (commit `c9bd036`) -- "
        f"grid `{sealed['b3']['grid_private_pct']}`, "
        f"`min_breach_seeds_at_55={sealed['b3']['min_breach_seeds_at_55']}`, "
        f"`n_seeds={sealed['b3']['n_seeds']}`, "
        f"`coverage_must_be_monotone={sealed['b3']['coverage_must_be_monotone']}`. "
        "**b3 harness postdates the seal; its method is the committed E1 declaration "
        "(2026-08-15), cited verbatim; sealed b3 thresholds unchanged.**"
    )
    lines.append("")
    lines.append(
        f"Seeds attempted: {len(seeds)}. Refusals: {len(run['refusals'])}"
        + (f" -- {run['refusals']}" if run["refusals"] else " (none).")
    )
    lines.append("")
    lines.append("### B3 grid table")
    lines.append("")
    lines.append(
        _md_table(
            [
                "arm (private pts)",
                "coverage breach (>=1.0 ever)",
                "forced secondaries",
                "worst coverage med . max",
                "final min . med",
                "seeds below 100/75/50",
            ],
            [
                [
                    f"{arm:.0f}",
                    f"{run['arm_stats'][arm]['breach_count']}/{run['arm_stats'][arm]['n']}",
                    f"{run['arm_stats'][arm]['forced_secondary_seeds']}/{run['arm_stats'][arm]['n']}",
                    f"{run['arm_stats'][arm]['worst_coverage_median']:.3f} . {run['arm_stats'][arm]['worst_coverage_max']:.3f}",
                    f"{run['arm_stats'][arm]['final_value_min']:.1f} . {run['arm_stats'][arm]['final_value_median']:.1f}",
                    f"{run['arm_stats'][arm]['below_100']}/{run['arm_stats'][arm]['below_75']}/{run['arm_stats'][arm]['below_50']}",
                ]
                for arm in grid
            ],
        )
    )
    lines.append("")
    lines.append("### Hold-course depth (arm-invariant market fact, per seed)")
    lines.append("")
    lines.append(
        f"Median peak-to-trough equity drawdown across {verdict['depth']['n']} successful seeds: "
        f"**{verdict['depth']['median_depth']:.4f}** ({verdict['depth']['median_depth'] * 100:.1f}%). "
        f"Declared band: `[{DEPTH_BAND[0]:.4f}, {DEPTH_BAND[1]:.4f}]` "
        f"(`[{DEPTH_BAND[0] * 100:.1f}%, {DEPTH_BAND[1] * 100:.1f}%]`) -- "
        "see `DEPTH_BAND` in `scripts/spine_pilot_b3.py` for the construction and citations "
        "(a documented deviation: neither the E1 doc nor the stress-03 method states a literal "
        "two-sided band)."
    )
    lines.append("")
    lines.append("### B3 verdict (three-part)")
    lines.append("")
    lines.append(
        _md_table(
            ["check", "value", "threshold", "verdict"],
            [
                [
                    "(a) coverage monotone in allocation",
                    "[" + ", ".join(f"{m:.4f}" for m in verdict["monotone"]["medians"]) + "]",
                    "non-decreasing medians across the grid",
                    _fmt_bool(verdict["monotone"]["pass"]),
                ],
                [
                    "(b) breach seeds at 55",
                    f"{verdict['breach']['breach_count']}/{verdict['breach']['n']}",
                    f">= {verdict['breach']['threshold']}",
                    _fmt_bool(verdict["breach"]["pass"]),
                ],
                [
                    "(c) hold-course depth inside declared band",
                    f"{verdict['depth']['median_depth']:.4f}",
                    f"[{DEPTH_BAND[0]:.4f}, {DEPTH_BAND[1]:.4f}]",
                    _fmt_bool(verdict["depth"]["pass"]),
                ],
                ["**OVERALL**", "", "", _fmt_bool(verdict["overall"])],
            ],
        )
    )
    lines.append("")
    lines.append("### Comparison against the E1 family (world 703, stress compiler, no spine)")
    lines.append("")
    lines.append(
        _md_table(
            [
                "arm (private pts)",
                "703 worst coverage med . max (E1, cited)",
                "802 worst coverage med . max (this run)",
            ],
            [
                [
                    "15",
                    "0.103 . 0.164",
                    f"{run['arm_stats'][15.0]['worst_coverage_median']:.3f} . {run['arm_stats'][15.0]['worst_coverage_max']:.3f}",
                ],
                [
                    "35",
                    "0.309 . 0.540",
                    f"{run['arm_stats'][35.0]['worst_coverage_median']:.3f} . {run['arm_stats'][35.0]['worst_coverage_max']:.3f}",
                ],
                [
                    "40",
                    "0.382 . 0.694",
                    f"{run['arm_stats'][40.0]['worst_coverage_median']:.3f} . {run['arm_stats'][40.0]['worst_coverage_max']:.3f}",
                ],
                [
                    "55",
                    "0.719 . 1.571",
                    f"{run['arm_stats'][55.0]['worst_coverage_median']:.3f} . {run['arm_stats'][55.0]['worst_coverage_max']:.3f}",
                ],
            ],
        )
    )
    lines.append("")
    lines.append(
        "The E1 family's own headline reading: coverage moves 0.10 -> 1.57 across this same "
        "grid on world 703 (stress compiler, no spine). The row above lets the owner read "
        "world 802's spine-conditioned numbers against that side by side, arm for arm."
    )
    lines.append("")

    existing = RESULTS_PATH.read_text(encoding="utf-8")
    RESULTS_PATH.write_text(
        existing.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"appended B3 section to {RESULTS_PATH}")


def main() -> None:
    sealed = _load_sealed()
    world = _load_world()
    base_seed = int(world.engine_defaults.base_seed)
    seeds = [base_seed + SEED_STRIDE * k for k in range(N_SEEDS)]
    grid = [float(p) for p in sealed["b3"]["grid_private_pct"]]

    run = _run_all(world, seeds, grid)
    verdict = _judge(sealed["b3"], grid, run)

    _print_console(grid, run, verdict)
    _append_report(sealed, seeds, grid, run, verdict)


if __name__ == "__main__":
    main()
