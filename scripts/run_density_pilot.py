"""WP5.5: the decision-density study at PILOT scale (D-K5-3, owner-directed).

Hundreds of worlds x cheap deciders, alpha attributed by window via DN-5's
chain-link decomposition, with TIME AND COST MEASURED AND TABLED so the
full-scale run is budgeted from data rather than guesses (the owner's words).

Run:  uv run python scripts/run_density_pilot.py --out artifacts/wp55 --created-at DATE

A "world" at pilot scale is a (preset, engine seed) pair: the four committed
presets give four regime architectures, and the seed axis gives the residual
randomness -- hundreds of distinct decades on the toy engine, whose decision
layer (annual windows, actions, twin) is the layer the density question is
posed at. The full-version budget table extrapolates BOTH axes: this layer at
thousands of worlds, and the generated hier-flow-v1 world variant (whose
per-world sampling cost is the measured campaign number, quoted, not guessed).

Deterministic: seeds enumerate a fixed grid; no clocks inside the measurement
loop (wall timings are instrumentation, recorded as such).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import numpy as np  # noqa: E402

from ah.core.engine import run_path  # noqa: E402
from ah.core.institution import decision_months  # noqa: E402
from ah.core.numericworld import project_numeric  # noqa: E402
from ah.core.worldspec import WorldSpec  # noqa: E402
from ah.density import window_contributions  # noqa: E402
from ah.tournament import (  # noqa: E402
    WindowState,
    band_rule_policy,
    hold_course_policy,
    random_policy,
)

PRESETS_DIR = _REPO_ROOT / "src" / "ah" / "presets"
BASE_SEED = 20260803
N_SEEDS_PER_PRESET = 75  # 4 presets x 75 = 300 worlds (the "hundreds" pilot)

#: The cheap decider set (D-K5-3: "ablations + committee sparingly"): the
#: band rule at two thresholds (the ablation pair), the seeded luck baseline,
#: and hold-course. The LLM committee is deliberately absent at pilot scale --
#: its per-window cost is API-bound and belongs in the budget table as a
#: quoted rate, not in a 300-world loop.
def _participants() -> dict:
    return {
        "band-rule-5pct": band_rule_policy(0.05),
        "band-rule-10pct": band_rule_policy(0.10),
        "luck": random_policy(base_seed=17),
        "hold-course": hold_course_policy(),
    }


def _play(paths, policy, months_list, basis="reported"):
    """The tournament's sequential reveal, inlined for the pilot loop."""
    from ah.core.institution import simulate_institution

    decisions: dict[int, str] = {}
    for w, month in enumerate(months_list):
        so_far = simulate_institution(paths, decisions, use_reported=True)
        total = float(so_far.total[month])
        prev = float(so_far.total[month - 12]) if month >= 12 else 100.0
        from ah.core.institution import SLEEVES

        state = WindowState(
            window=w,
            month=month,
            total=total,
            weights={s: float(so_far.weights[month, j]) for j, s in enumerate(SLEEVES)},
            trailing_12m_total_return=total / prev - 1.0,
            basis=basis,
        )
        action, _rationale = policy(state)
        decisions[month] = action
    return decisions


def _regime_at(world: dict, month: int) -> str:
    quarter = month // 3
    for seg in (world.get("regimes") or {}).get("sequence") or []:
        if int(seg["from_quarter"]) <= quarter <= int(seg["to_quarter"]):
            return str(seg["regime"])
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_REPO_ROOT / "artifacts" / "wp55")
    parser.add_argument("--seeds", type=int, default=N_SEEDS_PER_PRESET)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    presets = {p.stem: json.loads(p.read_text("utf-8")) for p in sorted(PRESETS_DIR.glob("*.json"))}
    participants = _participants()

    rows = []
    t_grid0 = time.perf_counter()
    timings = {"engine_s": 0.0, "play_s": 0.0, "attribution_s": 0.0}
    for preset_name, world in presets.items():
        nw = project_numeric(WorldSpec.model_validate(world))
        for i in range(args.seeds):
            seed = BASE_SEED + 7919 * i
            t0 = time.perf_counter()
            paths = run_path(nw, seed)
            timings["engine_s"] += time.perf_counter() - t0
            months_list = decision_months(paths.months)
            for name, policy in participants.items():
                t0 = time.perf_counter()
                decisions = _play(paths, policy, months_list)
                timings["play_s"] += time.perf_counter() - t0
                t0 = time.perf_counter()
                attr = window_contributions(paths, decisions, use_reported=True)
                timings["attribution_s"] += time.perf_counter() - t0
                for j, (month, c) in enumerate(zip(attr.months, attr.contributions, strict=True)):
                    rows.append(
                        {
                            "preset": preset_name,
                            "seed": seed,
                            "participant": name,
                            "window": j,
                            "month": month,
                            "regime": _regime_at(world, month),
                            "action": attr.actions[j],
                            "contribution": c,
                        }
                    )
    wall = time.perf_counter() - t_grid0

    n_worlds = len(presets) * args.seeds
    n_participants = len(participants)
    n_windows = len({r["window"] for r in rows})

    # ---- aggregation: where does |c_j| concentrate? ----------------------- #
    def agg(keyfn):
        out: dict = {}
        for r in rows:
            out.setdefault(keyfn(r), []).append(abs(r["contribution"]))
        return {
            k: {
                "mean_abs": float(np.mean(v)),
                "p90_abs": float(np.percentile(v, 90)),
                "share": float(np.sum(v)),
                "n": len(v),
            }
            for k, v in sorted(out.items())
        }

    by_window = agg(lambda r: r["window"])
    total_abs = sum(v["share"] for v in by_window.values()) or 1.0
    for v in by_window.values():
        v["share"] = v["share"] / total_abs
    by_regime = agg(lambda r: r["regime"])
    t_regime = sum(v["share"] for v in by_regime.values()) or 1.0
    for v in by_regime.values():
        v["share"] = v["share"] / t_regime
    by_participant = agg(lambda r: r["participant"])

    # ---- the budget table (D-K5-3's deliverable) -------------------------- #
    per_world_s = wall / n_worlds
    # The generated-world variant's per-world cost: the measured campaign-2
    # sampling rate (criterion cell assembly, GPU sampler, block_batch 128:
    # ~1400 s for 2x1024 decades -> ~0.68 s/decade), quoted from
    # artifacts/campaign2 cell timings rather than guessed.
    HIER_FLOW_S_PER_WORLD = 0.68
    budget = {
        "pilot": {
            "worlds": n_worlds,
            "participants": n_participants,
            "windows_per_world": n_windows,
            "wall_seconds": round(wall, 1),
            "seconds_per_world": round(per_world_s, 4),
            "stage_seconds": {k: round(v, 1) for k, v in timings.items()},
        },
        "full_run_toy_layer": {
            "worlds": 5000,
            "extrapolated_wall_minutes": round(5000 * per_world_s / 60.0, 1),
            "basis": "measured pilot rate, same participant set",
        },
        "full_run_generated_worlds": {
            "worlds": 5000,
            "sampling_wall_hours": round(5000 * HIER_FLOW_S_PER_WORLD / 3600.0, 2),
            "basis": (
                "measured campaign-2 criterion-cell rate (~0.68 s/decade, GPU sampler "
                "block_batch 128); decision layer adds the toy-layer rate on top"
            ),
        },
        "committee_llm_rate_note": (
            "an LLM committee decider costs ~1 API call per window per participant; "
            "at 10 windows x 5000 worlds that is 50k calls per persona -- priced from "
            "the provider table at run time, deliberately excluded from pilot compute"
        ),
    }

    doc = {
        "kind": "decision-density-pilot",
        "created_at": args.created_at,
        "information_basis": "reported",
        "attribution": "DN-5 sequential chain-link (ah.density.window_contributions)",
        "grid": {
            "presets": sorted(presets),
            "seeds_per_preset": args.seeds,
            "base_seed": BASE_SEED,
            "participants": sorted(participants),
        },
        "by_window": by_window,
        "by_regime": by_regime,
        "by_participant": by_participant,
        "budget": budget,
    }
    (args.out / "density-pilot.json").write_text(
        json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n"
    )

    # ---- the report ------------------------------------------------------- #
    lines = [
        "# Decision-density pilot (WP5.5)",
        "",
        f"*Generated by scripts/run_density_pilot.py; {args.created_at}. "
        f"{n_worlds} worlds (4 presets x {args.seeds} seeds), "
        f"{n_participants} deciders, DN-5 chain-link attribution, reported basis.*",
        "",
        "## Where |contribution| concentrates, by window",
        "",
        "| window | month | share of total |c| | mean |c| | p90 |c| |",
        "|---|---|---|---|---|",
    ]
    window_months = {r["window"]: r["month"] for r in rows}
    for w, v in by_window.items():
        lines.append(
            f"| {w} | m{window_months[w]} | {v['share']:.1%} | "
            f"{v['mean_abs']:.3f} | {v['p90_abs']:.3f} |"
        )
    lines += [
        "",
        "## By regime at the window",
        "",
        "| regime | share of total |c| | mean |c| | n |",
        "|---|---|---|---|",
    ]
    for k, v in by_regime.items():
        lines.append(f"| {k} | {v['share']:.1%} | {v['mean_abs']:.3f} | {v['n']} |")
    lines += [
        "",
        "## Budget table (D-K5-3's deliverable -- measured, then extrapolated)",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| pilot worlds | {n_worlds} |",
        f"| pilot wall | {wall:.1f} s |",
        f"| seconds per world (this decider set) | {per_world_s:.3f} |",
        f"| full run, toy layer, 5000 worlds | ~{budget['full_run_toy_layer']['extrapolated_wall_minutes']} min |",
        f"| full run, generated worlds, 5000 decades (sampling) | ~{budget['full_run_generated_worlds']['sampling_wall_hours']} h GPU |",
        "",
        f"LLM-committee note: {budget['committee_llm_rate_note']}.",
        "",
        "*Not investment advice.*",
    ]
    (args.out / "density-pilot.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(f"pilot: {n_worlds} worlds, {len(rows)} window rows, {wall:.1f}s wall")
    print(f"wrote {args.out / 'density-pilot.json'} and .md")


if __name__ == "__main__":
    main()
