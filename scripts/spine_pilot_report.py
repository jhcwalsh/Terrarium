"""Task 7: the spine-conditioned compiler pilot measurement run.

Spec: docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md
section 5. Bars are SEALED at docs/superpowers/specs/spine-pilot-prereg.json
(commit c9bd036) -- this script may build judges and read thresholds from that
file, but it may never write one back into the thresholds themselves.

Import-safe: importing this module draws no data, samples no ensemble, and
writes no file. All of that happens only under ``if __name__ == "__main__"``,
so ``tests/test_gen_spine.py`` can import the pure judge functions directly.

The ensemble the spine-conditioned compiler builds carries the sampled paths
and the source-row indices, but NOT the spine's own labels/policy/mu_pi (only
``ens.slow_states.states`` -- the L1 states -- ride along; the L2 labels used
for the CONTRACTION/quadrant test do not). Because ``sample_spine`` is a pure,
deterministic function of (climate, regimes_artifact, premise, seed, months),
this report reconstructs each seed's spine directly with the SAME call
``ah.gen.spine.SpineBootstrap.sample_months`` makes internally, so the two are
bit-identical -- see ``test_sample_spine_shapes_and_determinism``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
SEALED_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-pilot-prereg.json"
WORLD_PATH = _REPO_ROOT / "src" / "ah" / "presets" / "spine_pilot.json"
RESULTS_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-08-15-spine-pilot-results.md"

N_PATHS = 20


# --------------------------------------------------------------------------- #
# small pure helpers
# --------------------------------------------------------------------------- #


def _pearson_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation, 0.0 on a degenerate (zero-variance) input."""
    if a.size == 0 or b.size == 0:
        return 0.0
    if float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _panel_base_rate_from_disclosure(disclosure: str) -> tuple[float, int, int]:
    """Parses "NNN/MMM months" out of B6's sealed base-rate disclosure string,
    rather than hardcoding the panel base rate as a second, driftable literal."""
    m = re.search(r"(\d+)/(\d+) months", disclosure)
    if not m:
        raise ValueError(f"could not parse a panel base rate from disclosure: {disclosure!r}")
    num, den = int(m.group(1)), int(m.group(2))
    return num / den, num, den


# --------------------------------------------------------------------------- #
# judges (pure; sealed comes pre-sliced to the relevant b-key sub-dict, except
# judge_b6 which also reads the b6 sub-dict's own base_rate_disclosure)
# --------------------------------------------------------------------------- #


def judge_b1(spine: Any, sealed: dict[str, Any]) -> dict[str, Any]:
    """Reaction function: policy-stance change vs. lagged inflation gap."""
    lag_lo, lag_hi = int(sealed["lag_months"][0]), int(sealed["lag_months"][1])
    n_decades = spine.policy.shape[0]
    decades: list[dict[str, Any]] = []
    for k in range(n_decades):
        policy = np.asarray(spine.policy[k], dtype=np.float64)
        pi_star = np.asarray(spine.states[k, :, 0], dtype=np.float64)
        mu_pi = float(spine.mu_pi[k])
        dpol = np.diff(policy)
        gap = (pi_star - mu_pi)[:-1]
        best_lag: int | None = None
        best_corr: float | None = None
        for lag in range(lag_lo, lag_hi + 1):
            corr = _pearson_corr(dpol[lag:], gap[:-lag])
            if best_corr is None or abs(corr) > abs(best_corr):
                best_corr, best_lag = corr, lag
        passed = best_corr is not None and best_corr > 0.0
        decades.append({"lag": best_lag, "corr": best_corr, "pass": bool(passed)})
    value = float(np.mean([d["pass"] for d in decades])) if decades else 0.0
    threshold = float(sealed["min_sign_fraction"])
    return {
        "pass": bool(value >= threshold),
        "value": value,
        "threshold": threshold,
        "n_decades": n_decades,
        "decades": decades,
    }


def judge_b2(ens: Any, source: Any, sealed: dict[str, Any]) -> dict[str, Any]:
    """Era coherence: join YoY jumps and the adjacent-month YoY spread."""
    from ah.gen.spine import panel_yoy

    rows = np.asarray(ens.row_indices)
    yoy = panel_yoy(source)
    visited = np.unique(rows)
    bad = visited[np.isnan(yoy[visited])]
    if bad.size:
        raise AssertionError(
            f"B2 wiring bug: {bad.size} visited panel row(s) have an undefined trailing "
            f"CPI YoY -- pools must exclude warm-up rows; first offenders: {bad[:5].tolist()}"
        )
    n_paths, months = rows.shape
    join_jumps: list[float] = []
    all_adjacent: list[float] = []
    n_joins = 0
    for p in range(n_paths):
        for m in range(1, months):
            diff = abs(float(yoy[rows[p, m]]) - float(yoy[rows[p, m - 1]]))
            all_adjacent.append(diff)
            if rows[p, m] != rows[p, m - 1] + 1:
                n_joins += 1
                join_jumps.append(diff)
    max_join_jump = max(join_jumps) if join_jumps else 0.0
    p95_adjacent = float(np.percentile(all_adjacent, 95)) if all_adjacent else 0.0
    bound_join = float(sealed["join_yoy_max_pp"])
    bound_p95 = float(sealed["p95_ratio_max"]) * float(sealed["panel_p95_adjacent_yoy_pp"])
    ok_join = max_join_jump <= bound_join
    ok_p95 = p95_adjacent <= bound_p95
    return {
        "pass": bool(ok_join and ok_p95),
        "value": {"max_join_jump_pp": max_join_jump, "p95_adjacent_yoy_pp": p95_adjacent},
        "threshold": {"join_yoy_max_pp": bound_join, "p95_bound_pp": bound_p95},
        "n_joins": n_joins,
        "ok_join": bool(ok_join),
        "ok_p95": bool(ok_p95),
    }


def judge_b4(spine: Any, sealed: dict[str, Any]) -> dict[str, Any]:
    """Persistence and the clock's order: dwell medians + clockwise fraction,
    both pooled across every decade the spine carries (not judged per-decade)."""
    from ah.gen.regimes.semimarkov import spells_from_labels
    from ah.gen.spine import CLOCKWISE, spine_quadrant

    quadrants = list(sealed["quadrants"])
    n_decades = spine.labels.shape[0]
    durations: dict[int, list[int]] = {q: [] for q in range(len(quadrants))}
    clockwise = 0
    total_changes = 0
    for k in range(n_decades):
        states_k, labels_k = spine.states[k], spine.labels[k]
        mu_pi = float(spine.mu_pi[k])
        cells = np.array(
            [
                spine_quadrant(states_k[m], int(labels_k[m]), mu_pi=mu_pi)
                for m in range(states_k.shape[0])
            ],
            dtype=np.int64,
        )
        for state, _start, length in spells_from_labels(cells):
            durations[int(state)].append(int(length))
        for m in range(1, cells.size):
            a, b = int(cells[m - 1]), int(cells[m])
            if a != b:
                total_changes += 1
                if (a, b) in CLOCKWISE:
                    clockwise += 1

    band_lo, band_hi = sealed["dwell_median_ratio_band"]
    panel_medians = sealed["panel_dwell_medians"]
    dwell_rows: list[dict[str, Any]] = []
    all_dwell_pass = True
    for q in range(len(quadrants)):
        visits = len(durations[q])
        panel_med = float(panel_medians[q])
        if visits == 0:
            med: float | None = None
            ratio: float | None = None
            row_pass = not (panel_med > 0.0)  # never visited: only OK if panel agrees
        else:
            med = float(np.median(durations[q]))
            ratio = med / panel_med if panel_med != 0.0 else None
            row_pass = ratio is not None and band_lo <= ratio <= band_hi
        all_dwell_pass = all_dwell_pass and row_pass
        dwell_rows.append(
            {
                "quadrant": quadrants[q],
                "visits": visits,
                "median": med,
                "panel_median": panel_med,
                "ratio": ratio,
                "pass": bool(row_pass),
            }
        )

    clockwise_fraction = float(clockwise) / total_changes if total_changes else float("nan")
    panel_cw = float(sealed["panel_clockwise_fraction"])
    tol = float(sealed["clockwise_fraction_tolerance"])
    cw_pass = total_changes > 0 and abs(clockwise_fraction - panel_cw) <= tol

    overall = bool(all_dwell_pass and cw_pass)
    return {
        "pass": overall,
        "dwell": dwell_rows,
        "clockwise": {
            "value": clockwise_fraction,
            "panel": panel_cw,
            "tolerance": tol,
            "total_changes": total_changes,
            "clockwise_changes": clockwise,
            "pass": bool(cw_pass),
        },
    }


def judge_b5(ens_conditioning: dict[str, Any], sealed: dict[str, Any]) -> dict[str, Any]:
    """Hazard realism: per-quadrant realized onset rate vs. the panel's."""
    corr = ens_conditioning["corrections"]
    onsets = corr["per_quadrant_onsets"]
    months = corr["per_quadrant_months"]
    panel_rates = sealed["panel_rates"]
    panel_months = sealed["panel_cell_months"]
    min_cell = int(sealed["min_cell_months"])
    rel_tol = float(sealed["rel_tolerance"])

    table: list[dict[str, Any]] = []
    overall = True
    for q in range(len(panel_rates)):
        m, o = int(months[q]), int(onsets[q])
        realized_rate = (o / m) if m > 0 else 0.0
        eligible = int(panel_months[q]) >= min_cell
        sealed_rate = float(panel_rates[q])
        if not eligible:
            row_pass = True  # sealed excludes starved cells from judgment
            rel_err: float | None = None
        elif sealed_rate == 0.0:
            row_pass = o == 0
            rel_err = None
        else:
            rel_err = abs(realized_rate - sealed_rate) / sealed_rate
            row_pass = rel_err <= rel_tol
        overall = overall and row_pass
        table.append(
            {
                "quadrant": q,
                "onsets": o,
                "months": m,
                "realized_rate": realized_rate,
                "panel_rate": sealed_rate,
                "panel_cell_months": int(panel_months[q]),
                "eligible": eligible,
                "rel_error": rel_err,
                "pass": bool(row_pass),
            }
        )
    return {"pass": bool(overall), "table": table}


def judge_b6(spine: Any, sealed: dict[str, Any]) -> dict[str, Any]:
    """Transmission: conditional onset rate after a policy-gap tight month,
    with the sealed three-way PASS/FAIL/INCONCLUSIVE outcome (base_rate_disclosure)."""
    from ah.gen.spine import CONTRACTION_CODES

    k = int(sealed["k_months"])
    threshold = float(sealed["spine_policy_gap_threshold_pp"])
    rel_tol = float(sealed["rel_tolerance"])
    n_decades = spine.policy.shape[0]

    tight_total = 0
    eligible_total = 0
    followed = 0
    for d in range(n_decades):
        policy = np.asarray(spine.policy[d], dtype=np.float64)
        pi_star = np.asarray(spine.states[d, :, 0], dtype=np.float64)
        r_star = np.asarray(spine.states[d, :, 1], dtype=np.float64)
        labels = np.asarray(spine.labels[d], dtype=np.int64)
        months = policy.shape[0]
        gap = policy - (r_star + pi_star)
        in_c = np.isin(labels, list(CONTRACTION_CODES))
        onset_at = np.zeros(months, dtype=bool)
        onset_at[0] = bool(in_c[0])
        onset_at[1:] = in_c[1:] & ~in_c[:-1]

        eligible_end = max(months - k, 0)  # excludes the last k months (full lookahead only)
        eligible_total += eligible_end
        for t in range(eligible_end):
            if gap[t] > threshold:
                tight_total += 1
                if bool(onset_at[t + 1 : t + 1 + k].any()):
                    followed += 1

    spine_base_rate = tight_total / eligible_total if eligible_total else 0.0
    value = followed / tight_total if tight_total else 0.0

    panel_rate = float(sealed["panel_conditional_onset_rate"])
    panel_uncond = float(sealed["panel_unconditional_onset_rate"])
    rel_err = abs(value - panel_rate) / panel_rate if panel_rate else float("inf")
    magnitude_ok = rel_err <= rel_tol
    sign_ok = value > panel_uncond
    would_pass = magnitude_ok and sign_ok

    panel_base_rate, num, den = _panel_base_rate_from_disclosure(
        str(sealed.get("base_rate_disclosure", ""))
    )
    if spine_base_rate == 0.0 and panel_base_rate == 0.0:
        base_ratio = 1.0
    elif spine_base_rate == 0.0 or panel_base_rate == 0.0:
        base_ratio = float("inf")
    else:
        base_ratio = max(spine_base_rate / panel_base_rate, panel_base_rate / spine_base_rate)

    if would_pass:
        verdict = "PASS"
    elif base_ratio > 2.0:
        verdict = "INCONCLUSIVE (construct mismatch)"
    else:
        verdict = "FAIL"

    return {
        "pass": bool(would_pass),
        "verdict": verdict,
        "value": value,
        "threshold": panel_rate,
        "panel_unconditional_onset_rate": panel_uncond,
        "rel_error": rel_err,
        "magnitude_ok": bool(magnitude_ok),
        "sign_ok": bool(sign_ok),
        "tight_months": tight_total,
        "eligible_months": eligible_total,
        "followed_by_onset": followed,
        "spine_base_rate": spine_base_rate,
        "panel_base_rate": panel_base_rate,
        "panel_base_rate_fraction": f"{num}/{den}",
        "base_rate_ratio": base_ratio,
    }


# --------------------------------------------------------------------------- #
# the measurement run itself -- only under __main__
# --------------------------------------------------------------------------- #


def _load_sealed() -> dict[str, Any]:
    return json.loads(SEALED_PATH.read_text(encoding="utf-8"))


def _load_world() -> Any:
    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


def _conjoin_bool(values: list[bool]) -> bool:
    return bool(all(values))


def _conjoin_b6(verdicts: list[str]) -> str:
    """Any real FAIL dominates; else any INCONCLUSIVE dominates; else PASS."""
    if all(v == "PASS" for v in verdicts):
        return "PASS"
    if any(v == "FAIL" for v in verdicts):
        return "FAIL"
    if any(v.startswith("INCONCLUSIVE") for v in verdicts):
        return "INCONCLUSIVE (construct mismatch)"
    return "FAIL"  # unreachable: verdicts are only ever these three strings


def _run_seed(seed: int, world: Any, source: Any, sealed: dict[str, Any]) -> dict[str, Any]:
    from ah.gen.spine import SpineBootstrap, sample_spine
    from ah.gen.systems import _pinned_layers

    climate, regimes_artifact = _pinned_layers()
    months = int(world.horizon.quarters) * 3
    premise = world.spine.premise

    sp = sample_spine(
        climate, regimes_artifact, premise, n_decades=N_PATHS, seed=seed, months=months
    )
    gen = SpineBootstrap()
    gen.fit(source)
    ens = gen.sample(world, N_PATHS, seed)
    cond = ens.meta.conditioning

    b1 = judge_b1(sp, sealed["b1"])
    b2 = judge_b2(ens, source, sealed["b2"])
    b4 = judge_b4(sp, sealed["b4"])
    b5 = judge_b5(cond, sealed["b5"])
    b6 = judge_b6(sp, sealed["b6"])

    return {
        "seed": seed,
        "spine_attempts": int(sp.attempts),
        "conditioning": cond,
        "b1": b1,
        "b2": b2,
        "b4": b4,
        "b5": b5,
        "b6": b6,
    }


def _fmt_bool(p: bool) -> str:
    return "PASS" if p else "FAIL"


def _print_seed(row: dict[str, Any]) -> None:
    cond = row["conditioning"]
    corr = cond["corrections"]
    print(f"=== seed {row['seed']} ===")
    print(f"spine attempts: {row['spine_attempts']}")
    print(f"pool_occupancy: {cond['pool_occupancy']}")
    print(f"per_path_onsets: {corr['per_path_onsets']}")
    print(f"per_quadrant_onsets: {corr['per_quadrant_onsets']}")
    print(f"per_quadrant_months: {corr['per_quadrant_months']}")
    print(
        f"forced_reentries: {cond['forced_reentries']}  unfiltered_reentries: {cond['unfiltered_reentries']}"
    )
    b1, b2, b4, b5, b6 = row["b1"], row["b2"], row["b4"], row["b5"], row["b6"]
    print(f"B1 {_fmt_bool(b1['pass'])}  value={b1['value']:.4f} (>= {b1['threshold']:.2f})")
    print(
        f"B2 {_fmt_bool(b2['pass'])}  max_join_jump={b2['value']['max_join_jump_pp']:.4f}pp "
        f"p95_adjacent={b2['value']['p95_adjacent_yoy_pp']:.4f}pp  n_joins={b2['n_joins']}"
    )
    print(
        f"B4 {_fmt_bool(b4['pass'])}  clockwise={b4['clockwise']['value']:.4f} "
        f"(panel {b4['clockwise']['panel']:.4f})"
    )
    print(f"B5 {_fmt_bool(b5['pass'])}")
    print(
        f"B6 {b6['verdict']}  value={b6['value']:.4f} (panel {b6['threshold']:.4f})  "
        f"spine_base={b6['spine_base_rate']:.4f}  panel_base={b6['panel_base_rate']:.4f} "
        f"({b6['panel_base_rate_fraction']})"
    )
    print()


def _print_summary(
    rows: list[dict[str, Any]],
    all_b1: bool,
    all_b2: bool,
    all_b4: bool,
    all_b5: bool,
    all_b6: str,
) -> None:
    print("=== SUMMARY (per-seed verdicts, ALL-seed conjunction) ===")
    header = f"{'seed':>10} | {'B1':6} | {'B2':6} | {'B4':6} | {'B5':6} | {'B6':30}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['seed']:>10} | {_fmt_bool(row['b1']['pass']):6} | "
            f"{_fmt_bool(row['b2']['pass']):6} | {_fmt_bool(row['b4']['pass']):6} | "
            f"{_fmt_bool(row['b5']['pass']):6} | {row['b6']['verdict']:30}"
        )
    print("-" * len(header))
    print(
        f"{'ALL':>10} | {_fmt_bool(all_b1):6} | {_fmt_bool(all_b2):6} | "
        f"{_fmt_bool(all_b4):6} | {_fmt_bool(all_b5):6} | {all_b6:30}"
    )


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _write_report(
    sealed: dict[str, Any],
    rows: list[dict[str, Any]],
    all_b1: bool,
    all_b2: bool,
    all_b4: bool,
    all_b5: bool,
    all_b6: str,
) -> None:
    lines: list[str] = []
    lines.append("# Spine-conditioned compiler pilot -- measurement results (Task 7)")
    lines.append("")
    lines.append(
        "Sealed thresholds: `docs/superpowers/specs/spine-pilot-prereg.json` "
        "(commit `c9bd036`). World: `src/ah/presets/spine_pilot.json` "
        '(`00000000-0000-4000-9000-000000000802`, "The Hard Landing"). '
        f"Sensitivity seeds: {sealed['sensitivity_seeds']}. `n_paths=20` per seed."
    )
    lines.append("")
    lines.append("## Verdict summary")
    lines.append("")
    lines.append(
        _md_table(
            ["seed", "B1", "B2", "B4", "B5", "B6"],
            [
                [
                    str(row["seed"]),
                    _fmt_bool(row["b1"]["pass"]),
                    _fmt_bool(row["b2"]["pass"]),
                    _fmt_bool(row["b4"]["pass"]),
                    _fmt_bool(row["b5"]["pass"]),
                    row["b6"]["verdict"],
                ]
                for row in rows
            ]
            + [
                [
                    "**ALL**",
                    _fmt_bool(all_b1),
                    _fmt_bool(all_b2),
                    _fmt_bool(all_b4),
                    _fmt_bool(all_b5),
                    all_b6,
                ]
            ],
        )
    )
    lines.append("")
    lines.append(
        "ALL-seed conjunction rule: B1/B2/B4/B5 are AND across seeds. B6's three-way "
        "conjunction: any seed FAIL dominates (a real construct-matched failure); "
        "else any seed INCONCLUSIVE dominates; else PASS."
    )

    lines.append("")
    lines.append("## B1 -- reaction function")
    lines.append("")
    lines.append(
        _md_table(
            ["seed", "fraction of decades passing", "threshold", "verdict"],
            [
                [
                    str(row["seed"]),
                    f"{row['b1']['value']:.4f}",
                    f">= {row['b1']['threshold']:.2f}",
                    _fmt_bool(row["b1"]["pass"]),
                ]
                for row in rows
            ],
        )
    )

    lines.append("")
    lines.append("## B2 -- era coherence")
    lines.append("")
    lines.append(
        _md_table(
            [
                "seed",
                "n_joins",
                "max join YoY jump (pp)",
                "bound (pp)",
                "p95 adjacent YoY (pp)",
                "bound (pp)",
                "verdict",
            ],
            [
                [
                    str(row["seed"]),
                    str(row["b2"]["n_joins"]),
                    f"{row['b2']['value']['max_join_jump_pp']:.4f}",
                    f"{row['b2']['threshold']['join_yoy_max_pp']:.4f}",
                    f"{row['b2']['value']['p95_adjacent_yoy_pp']:.4f}",
                    f"{row['b2']['threshold']['p95_bound_pp']:.4f}",
                    _fmt_bool(row["b2"]["pass"]),
                ]
                for row in rows
            ],
        )
    )

    lines.append("")
    lines.append("## B4 -- persistence and the clock's order")
    lines.append("")
    for row in rows:
        lines.append(f"### seed {row['seed']}")
        lines.append("")
        lines.append(
            _md_table(
                [
                    "quadrant",
                    "visits (spells)",
                    "median (months)",
                    "panel median",
                    "ratio",
                    "band",
                    "pass",
                ],
                [
                    [
                        d["quadrant"],
                        str(d["visits"]),
                        "n/a" if d["median"] is None else f"{d['median']:.1f}",
                        f"{d['panel_median']:.1f}",
                        "n/a" if d["ratio"] is None else f"{d['ratio']:.3f}",
                        f"[{sealed['b4']['dwell_median_ratio_band'][0]}, {sealed['b4']['dwell_median_ratio_band'][1]}]",
                        _fmt_bool(d["pass"]),
                    ]
                    for d in row["b4"]["dwell"]
                ],
            )
        )
        cw = row["b4"]["clockwise"]
        lines.append("")
        lines.append(
            f"Clockwise fraction: {cw['value']:.4f} ({cw['clockwise_changes']}/{cw['total_changes']} "
            f"transitions) vs panel {cw['panel']:.4f} +/- {cw['tolerance']} -> {_fmt_bool(cw['pass'])}"
        )
        lines.append(f"B4 overall: {_fmt_bool(row['b4']['pass'])}")
        lines.append("")

    lines.append("## B5 -- hazard realism")
    lines.append("")
    for row in rows:
        lines.append(f"### seed {row['seed']}")
        lines.append("")
        lines.append(
            _md_table(
                [
                    "quadrant",
                    "onsets",
                    "months",
                    "realized rate",
                    "panel rate",
                    "panel cell months",
                    "eligible",
                    "rel error",
                    "pass",
                ],
                [
                    [
                        str(t["quadrant"]),
                        str(t["onsets"]),
                        str(t["months"]),
                        f"{t['realized_rate']:.4f}",
                        f"{t['panel_rate']:.4f}",
                        str(t["panel_cell_months"]),
                        str(t["eligible"]),
                        "n/a" if t["rel_error"] is None else f"{t['rel_error']:.3f}",
                        _fmt_bool(t["pass"]),
                    ]
                    for t in row["b5"]["table"]
                ],
            )
        )
        lines.append("")
        lines.append(f"B5 overall: {_fmt_bool(row['b5']['pass'])}")
        lines.append("")

    lines.append("## B6 -- transmission (three-way outcome)")
    lines.append("")
    lines.append(
        _md_table(
            [
                "seed",
                "value (spine conditional)",
                "panel conditional",
                "panel unconditional",
                "rel error",
                "sign ok",
                "spine base rate",
                "panel base rate",
                "base rate ratio",
                "verdict",
            ],
            [
                [
                    str(row["seed"]),
                    f"{row['b6']['value']:.4f}",
                    f"{row['b6']['threshold']:.4f}",
                    f"{row['b6']['panel_unconditional_onset_rate']:.4f}",
                    f"{row['b6']['rel_error']:.4f}",
                    _fmt_bool(row["b6"]["sign_ok"]),
                    f"{row['b6']['spine_base_rate']:.4f} ({row['b6']['tight_months']}/{row['b6']['eligible_months']})",
                    f"{row['b6']['panel_base_rate']:.4f} ({row['b6']['panel_base_rate_fraction']})",
                    f"{row['b6']['base_rate_ratio']:.3f}",
                    row["b6"]["verdict"],
                ]
                for row in rows
            ],
        )
    )
    lines.append("")
    lines.append(f"Sealed disclosure: {sealed['b6']['base_rate_disclosure']}")

    lines.append("")
    lines.append("## Occupancy and corrections (no silent caps)")
    lines.append("")
    for row in rows:
        cond = row["conditioning"]
        corr = cond["corrections"]
        lines.append(f"### seed {row['seed']}")
        lines.append("")
        lines.append(f"- spine attempts: {row['spine_attempts']}")
        lines.append(f"- pool_occupancy: `{cond['pool_occupancy']}`")
        lines.append(f"- per_path_onsets: `{corr['per_path_onsets']}`")
        lines.append(f"- per_quadrant_onsets: `{corr['per_quadrant_onsets']}`")
        lines.append(f"- per_quadrant_months: `{corr['per_quadrant_months']}`")
        lines.append(f"- forced_reentries: {cond['forced_reentries']}")
        lines.append(f"- unfiltered_reentries: {cond['unfiltered_reentries']}")
        lines.append("")

    lines.append("## Sealed disclosures (quoted verbatim)")
    lines.append("")
    lines.append(f"- B4 power disclosure: {sealed['b4']['power_disclosure']}")
    lines.append(f"- B5 zero-rate convention: {sealed['b5']['zero_rate_convention']}")
    lines.append(f"- B5 numerator disclosure: {sealed['b5']['numerator_disclosure']}")
    lines.append(f"- B6 base-rate disclosure: {sealed['b6']['base_rate_disclosure']}")
    lines.append(f"- Severity table disclosure: {sealed['severity_table_disclosure']}")
    lines.append("")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {RESULTS_PATH}")


def main() -> None:
    from ah.gen.bootstrap import campaign_source

    sealed = _load_sealed()
    world = _load_world()
    source = campaign_source()

    rows: list[dict[str, Any]] = []
    for seed in sealed["sensitivity_seeds"]:
        row = _run_seed(int(seed), world, source, sealed)
        _print_seed(row)
        rows.append(row)

    all_b1 = _conjoin_bool([row["b1"]["pass"] for row in rows])
    all_b2 = _conjoin_bool([row["b2"]["pass"] for row in rows])
    all_b4 = _conjoin_bool([row["b4"]["pass"] for row in rows])
    all_b5 = _conjoin_bool([row["b5"]["pass"] for row in rows])
    all_b6 = _conjoin_b6([row["b6"]["verdict"] for row in rows])

    _print_summary(rows, all_b1, all_b2, all_b4, all_b5, all_b6)
    _write_report(sealed, rows, all_b1, all_b2, all_b4, all_b5, all_b6)


if __name__ == "__main__":
    main()
