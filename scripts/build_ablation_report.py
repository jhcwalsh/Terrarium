"""WP2.10: GENERATE ``ABLATION.md`` and ``ablation.json`` from the stored grid.

Acceptance says the tables are generated, not hand-assembled, so this script is
the only thing that ever writes them. It reads exactly three kinds of artifact and
nothing else:

* ``experiments/wp210/cells/<slug>/summary.json``  — the cell's identity and verdict
* ``experiments/wp210/cells/<slug>/battery.json``  — the sealed battery report
* ``experiments/wp210/historical-strategy-returns.json`` — dated realizations, for
  the draw-span-restricted comparison

and it derives every number through :mod:`ah.eval.ablation`, which projects fields
the sealed battery already computed. ``tests/test_ablation_report.py`` asserts the
document is reproducible: running this twice over the same artifacts yields
byte-identical output.

Usage::

    uv run python scripts/build_ablation_report.py
    uv run python scripts/build_ablation_report.py --out ABLATION.md --json ablation.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.eval import ablation as ab  # noqa: E402
from ah.gen import systems  # noqa: E402

BENCHMARK_ID = "bootstrap-v1"
DRAW_SPAN_START = "1990-01-01"
DRAW_SPAN_END = "2020-12-01"


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "**no**"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f):
        return "**NaN**"
    if math.isinf(f):
        return "inf" if f > 0 else "-inf"
    return f"{f:.{digits}f}"


def load_grid(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """``(grid manifest, {cell_id: {"summary":…, "report":…}})`` for completed cells."""
    grid_path = root / "grid.json"
    grid = json.loads(grid_path.read_text("utf-8")) if grid_path.exists() else {"cells": []}
    cells: dict[str, dict[str, Any]] = {}
    for cell_dir in sorted((root / "cells").glob("*")):
        summary_path = cell_dir / "summary.json"
        report_path = cell_dir / "battery.json"
        if not (summary_path.exists() and report_path.exists()):
            continue
        summary = json.loads(summary_path.read_text("utf-8"))
        cells[summary["cell_id"]] = {
            "summary": summary,
            "report": json.loads(report_path.read_text("utf-8")),
        }
    return grid, cells


def sealed_strategy_ids(prereg_path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    doc = yaml.safe_load(prereg_path.read_text("utf-8"))
    return tuple(doc["d4_strategies"]), tuple(doc["reference_run"]["uncomputable_d4_strategies"])


# --------------------------------------------------------------------------- #
# per-cell extraction
# --------------------------------------------------------------------------- #


def cell_facts(
    entry: dict[str, Any],
    *,
    d4_ids: tuple[str, ...],
    uncomputable: tuple[str, ...],
    n_paths: int,
    months: int,
    vintage_id: str,
    which: str = "unfiltered",
) -> dict[str, Any]:
    """Every quantity the sealed rule names, for one cell, on one side."""
    summary = entry["summary"]
    # The battery report does not serialize the ensemble size; the driver read it off
    # the judged ensemble and recorded it. Merged here so criterion_bearing can name
    # which of the three sealed conditions failed rather than echo one composite flag.
    report = {**entry["report"], "n_paths": summary["n_paths"], "months": summary["months"]}
    cset = ab.comparison_set(
        report, d4_strategy_ids=d4_ids, uncomputable_strategy_ids=uncomputable, which=which
    )
    return {
        "cell_id": summary["cell_id"],
        "letter": summary["letter"],
        "system_id": summary["system_id"],
        "seed_index": summary["seed_index"],
        "sample_seed": summary["sample_seed"],
        "train_seed": summary["train_seed"],
        "checkpoint_hash": summary["checkpoint_hash"],
        "config_hash": summary["config_hash"],
        "which": which,
        "criterion_bearing": ab.criterion_bearing(
            report,
            expected_n_paths=n_paths,
            expected_months=months,
            expected_vintage_id=vintage_id,
        ),
        "clause_i": ab.clause_i(report, cset, which),
        "clause_ii": ab.clause_ii(report, cset, which),
        "clause_2_enforce": ab.enforce_rows(report, tiers=ab.REGRESSION_TIERS, which=which),
        "clause_3_memorization": ab.memorization_enforce(report, which),
        "clause_4_constraints": ab.constraint_violations(report, which),
        "conditional_tier_reported_not_gating": [
            {"name": r["name"], "value": r["value"], "severity": r["severity"]}
            for tier_rows in report[which]["tiers"].values()
            for r in tier_rows
            if r["suite"] == "conditional"
        ],
        "forecast_pairs": {
            sid: ab.strategy_forecast_pair(report, sid, which) for sid in cset.strategy_ids
        },
        "n_enforce_failures": summary[which]["n_enforce_failures"],
        "n_enforce": summary[which]["n_enforce"],
        "passed": summary[which]["n_enforce_failures"] == 0,
        "support": summary.get("support_unfiltered"),
        "reconciliation": summary.get("reconciliation_unfiltered"),
        "n_rejections": summary.get("n_rejections"),
        "timings": summary.get("timings"),
        "block_sampler_batch": summary.get("block_sampler_batch"),
        "block_sampler_device": summary.get("block_sampler_device"),
        "waypoints_bound": summary.get("waypoints_bound"),
        "reconciliation_applied": summary.get("reconciliation_applied"),
        "climate_layer": summary.get("climate_layer"),
    }


def restricted_comparison(
    facts_by_cell: dict[str, dict[str, Any]],
    historical: dict[str, Any],
    strategy_ids: tuple[str, ...],
) -> dict[str, Any]:
    """``benchmark_draw_span_bias``: elicitability on the 1990-2020 realizations only.

    The forecast pair is the run's own ``(var_95, es_95)``; only the realization
    sample is restricted. Both the full-sample and restricted means are reported per
    cell so WP2.11 can put the two side by side without recomputing anything.
    """
    restricted_hist: dict[str, list[float]] = {}
    n_full: dict[str, int] = {}
    for sid in strategy_ids:
        record = historical.get(sid)
        if record is None:
            continue
        dates = record["dates"]
        values = record["values"]
        keep = [
            v for d, v in zip(dates, values, strict=True) if DRAW_SPAN_START <= d <= DRAW_SPAN_END
        ]
        restricted_hist[sid] = keep
        n_full[sid] = len(values)

    out: dict[str, Any] = {
        "window": [DRAW_SPAN_START, DRAW_SPAN_END],
        "n_realizations_full": n_full,
        "n_realizations_restricted": {k: len(v) for k, v in restricted_hist.items()},
        "per_cell": {},
        "computable": bool(restricted_hist),
    }
    for cell_id, facts in facts_by_cell.items():
        per_strategy: dict[str, float] = {}
        for sid in strategy_ids:
            if sid not in restricted_hist or not restricted_hist[sid]:
                per_strategy[sid] = float("nan")
                continue
            var, es = facts["forecast_pairs"][sid]
            per_strategy[sid] = ab.restricted_elicitability(restricted_hist[sid], var, es)
        values = np.array(list(per_strategy.values()), dtype=np.float64)
        out["per_cell"][cell_id] = {
            "per_strategy": per_strategy,
            "mean": float(np.mean(values)) if values.size else float("nan"),
            "full_sample_mean": facts["clause_i"]["mean"],
        }
    return out


def head_to_head(facts: dict[str, dict[str, Any]], restricted: dict[str, Any]) -> dict[str, Any]:
    """Per challenger system: the per-seed and pooled comparison against the benchmark.

    This is the arithmetic ``multi_seed_decision_rule`` reads. It is REPORTED here,
    never evaluated into a verdict — the verdict is WP2.11's, executed by the sealed
    ``g2.py``.
    """
    bench = {f["seed_index"]: f for f in facts.values() if f["system_id"] == BENCHMARK_ID}
    out: dict[str, Any] = {"benchmark": BENCHMARK_ID, "systems": {}}
    for system_id in sorted({f["system_id"] for f in facts.values()} - {BENCHMARK_ID}):
        rows = {f["seed_index"]: f for f in facts.values() if f["system_id"] == system_id}
        per_seed: list[dict[str, Any]] = []
        diffs: list[float] = []
        diffs_restricted: list[float] = []
        for index in sorted(rows):
            if index not in bench:
                continue
            c, b = rows[index], bench[index]
            d = c["clause_i"]["mean"] - b["clause_i"]["mean"]
            nan_blocked = bool(c["clause_i"]["has_nan"] or b["clause_i"]["has_nan"])
            clause_i_beat = bool(d < 0.0) and not nan_blocked
            clause_ii_ok = c["clause_ii"]["count"] <= b["clause_ii"]["count"]
            per_seed.append(
                {
                    "seed_index": index,
                    "challenger_mean_elicitability": c["clause_i"]["mean"],
                    "benchmark_mean_elicitability": b["clause_i"]["mean"],
                    "d": d,
                    "nan_blocked": nan_blocked,
                    "clause_i_beat": clause_i_beat,
                    "challenger_band_exceedance": c["clause_ii"]["count"],
                    "benchmark_band_exceedance": b["clause_ii"]["count"],
                    "clause_ii_no_regression": clause_ii_ok,
                    "beats_this_seed": bool(clause_i_beat and clause_ii_ok),
                }
            )
            diffs.append(d)
            rc = restricted["per_cell"].get(c["cell_id"], {}).get("mean", float("nan"))
            rb = restricted["per_cell"].get(b["cell_id"], {}).get("mean", float("nan"))
            diffs_restricted.append(rc - rb)
        entry: dict[str, Any] = {"per_seed": per_seed}
        if diffs:
            entry["pooled_full_sample"] = ab.pooled_difference(diffs)
            entry["every_seed_beats"] = bool(per_seed) and all(
                r["beats_this_seed"] for r in per_seed
            )
            entry["clause_ii_holds_every_seed"] = all(
                r["clause_ii_no_regression"] for r in per_seed
            )
        if diffs_restricted and not all(math.isnan(x) for x in diffs_restricted):
            entry["pooled_restricted_1990_2020"] = ab.pooled_difference(diffs_restricted)
        out["systems"][system_id] = entry
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

DISPERSION_NOTE = (
    "**Cross-seed dispersion convention.** Every per-metric table below shows the "
    "INDIVIDUAL SEED VALUES and their mean. A standard deviation over three seeds is a "
    "two-degree-of-freedom estimate, and quoting it alone would overstate what this "
    "grid measured; the seed values are strictly more information and a reader can "
    "form any summary from them. An sd appears in exactly one place -- the pooled "
    "route's `sd_s(d_s)` -- because `multi_seed_decision_rule.beats_definition` names "
    "it, and it is computed at `ddof=1` there because the seal specifies ddof=1."
)


def _system_row(letter: str, system_id: str) -> systems.AblationSystem | None:
    for row in systems.SYSTEMS:
        if row.letter == letter and row.system_id == system_id:
            return row
    return None


def render(doc: dict[str, Any]) -> str:
    facts = doc["cells"]
    ordered = sorted(facts.values(), key=lambda f: (f["letter"], f["system_id"], f["seed_index"]))
    lines: list[str] = []
    a = lines.append

    a("# ABLATION.md -- WP2.10 multi-seed ablation (systems A-E)")
    a("")
    a(
        "GENERATED by `scripts/build_ablation_report.py` from the stored grid under "
        "`experiments/wp210/`. Do not edit by hand: `tests/test_ablation_report.py` "
        "asserts this document is reproducible from those artifacts."
    )
    a("")
    a(
        f"Grid: {doc['grid']['n_paths']} paths x {doc['grid']['months']} months, campaign "
        f"vintage `{doc['grid']['vintage_id']}`, block-sampler width "
        f"{doc['grid']['block_batch']} on `{doc['grid']['sampler_device']}`, "
        f"reference seed {doc['grid']['reference_seed']} "
        f"({doc['grid']['n_resamples']} resamples, level {doc['grid']['level']}, "
        f"block length {doc['grid']['block_length']})."
    )
    a("")
    a(
        "**Sampler width and device are stated, not hidden.** Every cell ran at one "
        "width on one device. WP2.8b measured cross-width differences at <= 1.8e-5 of "
        "a factor's own cross-ensemble standard deviation -- round-off from a batched "
        "float32 GEMM, unavoidable and bounded, never asserted to be zero. Two "
        "ensembles at the same seed and different widths agree to round-off, not bit "
        "for bit."
    )
    a("")
    a(DISPERSION_NOTE)
    a("")

    # -- the systems ------------------------------------------------------- #
    a("## 1. The systems (DN-1.1 Sec.II.7)")
    a("")
    a("| Sys | id | composition | question | seeds |")
    a("|---|---|---|---|---|")
    for row in systems.SYSTEMS:
        kind = "training" if row.neural else "sampling"
        n = len({f["seed_index"] for f in facts.values() if f["system_id"] == row.system_id})
        a(f"| {row.letter} | `{row.system_id}` | {row.composition} | {row.question} | {n} {kind} |")
    a("")
    if systems.UNTESTED_ARMS:
        a(
            "**Not run, and named rather than left implicit:** "
            + ", ".join(f"`{s}`" for s in systems.UNTESTED_ARMS)
            + ". Systems B and C run the FLOW arm only -- running both co-primary "
            "samplers through them doubles the grid, and the six extra diffusion cells "
            "are its most expensive. B and C ablate the joinery and the climate layer, "
            "not the sampler family; the sampler-family question is answered at full "
            "strength in D, which runs both arms. The diffusion variants of B and C are "
            "constructible (`ah.gen.systems.build`) and UNTESTED."
        )
        a("")

    # -- criterion bearing -------------------------------------------------- #
    a("## 2. Criterion-bearing status (sealed `criterion_bearing_runs_only`)")
    a("")
    a(
        "Every number entering `multi_seed_decision_rule` must come from a run at the "
        "sealed ensemble size, against the sealed campaign vintage, with a verified "
        "pre-registration and matching lock. Asserted per cell, not assumed."
    )
    a("")
    a("| cell | n_paths | months | vintage | prereg verified | criterion-bearing |")
    a("|---|---|---|---|---|---|")
    for f in ordered:
        cb = f["criterion_bearing"]
        a(
            f"| `{f['cell_id']}` | {cb['observed']['n_paths']} | {cb['observed']['months']} | "
            f"`{cb['observed']['vintage_id']}` | {_fmt(cb['prereg_verified'])} | "
            f"{_fmt(cb['ok'])} |"
        )
    a("")

    # -- lineage ------------------------------------------------------------ #
    a("## 3. Lineage: checkpoints and seeds")
    a("")
    a("| cell | sample seed | train seed | checkpoint | config |")
    a("|---|---|---|---|---|")
    for f in ordered:
        ck = f["checkpoint_hash"]
        a(
            f"| `{f['cell_id']}` | {f['sample_seed']} | "
            f"{'-' if f['train_seed'] is None else f['train_seed']} | "
            f"{'-' if not ck else '`' + ck[:16] + '...`'} | "
            f"{'-' if not f['config_hash'] else '`' + f['config_hash'] + '`'} |"
        )
    a("")

    # -- clause (i) --------------------------------------------------------- #
    a("## 4. Clause (i): mean `elicitability_score` over the comparison set")
    a("")
    a(
        "The comparison set is `tail_tier_definition`'s family (a) restricted to the "
        "strategies with computable historical statistics -- the five sealed "
        "`d4_strategies` MINUS `reference_run.uncomputable_d4_strategies` "
        f"(`{'`, `'.join(doc['comparison_set']['excluded_strategy_ids'])}`), which "
        f"leaves `{'`, `'.join(doc['comparison_set']['strategy_ids'])}`. "
        "**Lower is better** -- it is the only directional scalar in the suite. "
        "**NaN rule:** a NaN on either side makes the seed NOT a beat, so NaNs "
        "propagate into the mean here rather than being averaged away."
    )
    a("")
    header = (
        "| system | "
        + " | ".join(f"seed {s.index}" for s in systems.SEED_PLAN)
        + " | mean over seeds | any NaN |"
    )
    a(header)
    a("|---|" + "---|" * (len(systems.SEED_PLAN) + 2))
    for system_id in doc["system_order"]:
        vals = []
        for s in systems.SEED_PLAN:
            f = facts.get(f"{doc['letter_by_system'][system_id]}:{system_id}:{s.index}")
            vals.append(float("nan") if f is None else f["clause_i"]["mean"])
        arr = np.array(vals, dtype=np.float64)
        any_nan = any(
            facts[k]["clause_i"]["has_nan"] for k in facts if facts[k]["system_id"] == system_id
        )
        a(
            f"| `{system_id}` | "
            + " | ".join(_fmt(v, 6) for v in vals)
            + f" | {_fmt(float(np.mean(arr)), 6)} | {_fmt(any_nan)} |"
        )
    a("")
    a("Per-strategy detail (each cell's own contributions):")
    a("")
    a("| cell | " + " | ".join(f"`{sid}`" for sid in doc["comparison_set"]["strategy_ids"]) + " |")
    a("|---|" + "---|" * len(doc["comparison_set"]["strategy_ids"]))
    for f in ordered:
        a(
            f"| `{f['cell_id']}` | "
            + " | ".join(
                _fmt(f["clause_i"]["per_strategy"].get(sid), 6)
                for sid in doc["comparison_set"]["strategy_ids"]
            )
            + " |"
        )
    a("")

    # -- clause (ii) -------------------------------------------------------- #
    a("## 5. Clause (ii): comparison-set metrics outside their sealed reference band")
    a("")
    a(
        "Counted over the WHOLE comparison set and then filtered to "
        "`ah.eval.battery.band_is_usable` bands, so the seal's disclosure -- that "
        "clause (ii) ranges entirely over the cross-block `tail_dependence_lower` / "
        "`tail_dependence_upper` family and that ZERO strategy-level metrics enter it "
        "-- is MEASURED here rather than assumed. `usable strategy bands` is the number "
        "that must be 0 for that disclosure to hold."
    )
    a("")
    a(
        "| cell | outside count | usable bands | usable cross-block | usable strategy | "
        "disclosure holds |"
    )
    a("|---|---|---|---|---|---|")
    for f in ordered:
        c2 = f["clause_ii"]
        a(
            f"| `{f['cell_id']}` | {c2['count']} | {c2['n_usable_bands']} | "
            f"{c2['n_usable_cross_block_bands']} | {c2['n_usable_strategy_bands']} | "
            f"{_fmt(c2['seal_disclosure_holds'])} |"
        )
    a("")

    # -- head to head ------------------------------------------------------- #
    a("## 6. Head-to-head against `bootstrap-v1` (the sealed rule's inputs)")
    a("")
    a(
        "REPORTED, NOT ADJUDICATED. `multi_seed_decision_rule` is executed by "
        "`ah/eval/g2.py` at WP2.11; this section supplies its arithmetic so that "
        "execution needs no re-run of the grid. `d_s` is (challenger - benchmark)'s "
        "mean elicitability difference in seed s. The pooled route is a beat iff "
        "`mean_s(d_s) < 0` AND `|mean_s(d_s)| > sd_s(d_s)` at ddof=1 -- both halves "
        "are shown separately."
    )
    a("")
    a(
        "| challenger | "
        + " | ".join(f"d(seed {s.index})" for s in systems.SEED_PLAN)
        + " | mean_s(d_s) | sd_s(d_s) ddof=1 | mean<0 | \\|mean\\|>sd | pooled beat | "
        "beats every seed | clause (ii) every seed |"
    )
    a("|---|" + "---|" * (len(systems.SEED_PLAN) + 7))
    for system_id, entry in doc["head_to_head"]["systems"].items():
        pooled = entry.get("pooled_full_sample")
        if pooled is None:
            continue
        per = {r["seed_index"]: r["d"] for r in entry["per_seed"]}
        a(
            f"| `{system_id}` | "
            + " | ".join(_fmt(per.get(s.index), 6) for s in systems.SEED_PLAN)
            + f" | {_fmt(pooled['mean_d'], 6)} | {_fmt(pooled['sd_d_ddof1'], 6)} | "
            f"{_fmt(pooled['mean_is_negative'])} | {_fmt(pooled['abs_mean_exceeds_sd'])} | "
            f"{_fmt(pooled['pooled_beat'])} | {_fmt(entry['every_seed_beats'])} | "
            f"{_fmt(entry['clause_ii_holds_every_seed'])} |"
        )
    a("")

    # -- draw span bias ----------------------------------------------------- #
    a("## 7. Benchmark draw-span bias (sealed, binding on WP2.11)")
    a("")
    a(
        "`bootstrap-v1` can only resample "
        f"{doc['restricted']['window'][0]}..{doc['restricted']['window'][1]}, while a "
        "challenger fitted on the full train+validation span has seen 1929-33, 1937, "
        "1973-74 and 1987 -- and BOTH are scored against the same realizations, which "
        "include all of it. The head-to-head is therefore **biased toward promotion** "
        "by a mechanism that has nothing to do with either generator's quality. The "
        "seal binds WP2.11 to report the comparison restricted to the 1990-2020 "
        "realizations as well as on the full sample."
    )
    a("")
    if doc["restricted"]["computable"]:
        a(
            "**It is computable, and computed here.** The metric's two arguments are "
            "separable: the FORECAST pair is the generated ensemble's own "
            "`(var_95, es_95)`, which every stored report carries per strategy, and the "
            "REALIZATIONS are history's. Restricting the window touches only the "
            "realizations, and the scoring function is the sealed "
            "`ah.eval.metrics.tails.elicitability_score` itself, imported rather than "
            "restated."
        )
        a("")
        a(
            "Realization counts: "
            + ", ".join(
                f"`{sid}` {doc['restricted']['n_realizations_restricted'][sid]} of "
                f"{doc['restricted']['n_realizations_full'][sid]}"
                for sid in sorted(doc["restricted"]["n_realizations_restricted"])
            )
            + "."
        )
        a("")
        a(
            "| challenger | "
            + " | ".join(f"d(seed {s.index})" for s in systems.SEED_PLAN)
            + " | mean_s(d_s) | sd ddof=1 | pooled beat (restricted) |"
        )
        a("|---|" + "---|" * (len(systems.SEED_PLAN) + 3))
        for system_id, entry in doc["head_to_head"]["systems"].items():
            pooled = entry.get("pooled_restricted_1990_2020")
            if pooled is None:
                continue
            a(
                f"| `{system_id}` | "
                + " | ".join(_fmt(d, 6) for d in pooled["per_seed_d"])
                + f" | {_fmt(pooled['mean_d'], 6)} | {_fmt(pooled['sd_d_ddof1'], 6)} | "
                f"{_fmt(pooled['pooled_beat'])} |"
            )
        a("")
        a(
            "Neither number gates -- the sealed rule is the sealed rule -- but a PROMOTE "
            "that survives only on the full sample and vanishes on the common window is "
            "a promotion of a data window."
        )
    else:
        a(
            "**NOT COMPUTED.** The dated historical realization series "
            "(`experiments/wp210/historical-strategy-returns.json`) is absent, so the "
            "restricted sample cannot be formed. WP2.11 would need it, or an equivalent "
            "`ReferenceStats.historical_series` read, to produce this table."
        )
    a("")

    # -- clauses 2-4 -------------------------------------------------------- #
    a("## 8. Clauses (2)-(4): enforce tiers, memorization, constraints")
    a("")
    a(
        "| cell | monthly/1_5yr enforce failures | memorization enforce failures | "
        "money_pump | floor | all clause-4 zero |"
    )
    a("|---|---|---|---|---|---|")
    for f in ordered:
        reg_fail = sum(1 for r in f["clause_2_enforce"] if r["passed"] is False)
        mem_fail = sum(1 for r in f["clause_3_memorization"] if r["passed"] is False)
        c4 = f["clause_4_constraints"]
        a(
            f"| `{f['cell_id']}` | {reg_fail} | {mem_fail} | "
            f"{_fmt(c4['money_pump_violations']['value'], 1)} | "
            f"{_fmt(c4['floor_violations']['value'], 1)} | {_fmt(c4['all_zero'])} |"
        )
    a("")
    a("Per-cell enforce detail, monthly and 1_5yr tiers:")
    a("")
    a("| cell | metric | tier | value | passed |")
    a("|---|---|---|---|---|")
    for f in ordered:
        for r in f["clause_2_enforce"]:
            a(
                f"| `{f['cell_id']}` | `{r['name']}` | {r['tier']} | "
                f"{_fmt(r['value'], 6)} | {_fmt(r['passed'])} |"
            )
    a("")

    # -- filtered vs unfiltered --------------------------------------------- #
    a("## 9. Filtered and unfiltered")
    a("")
    a(
        "Every JOINERY-ASSEMBLED cell was assembled twice at the same seed -- once with "
        "the acceptance filter off (the primary, judged run) and once with it on. The "
        "filter's metric subset is disjoint from every enforce-tier metric by "
        "construction (WP2.7), so the two verdicts should agree; where they do not, that "
        "is a finding. `bootstrap-v1` never enters the joinery and therefore HAS no "
        "acceptance filter: its filtered column is `n/a`, not zero. Re-sampling the same "
        "ensemble twice to fill that column would have put a fabricated result in this "
        "table."
    )
    a("")
    a("| cell | unfiltered enforce failures | filtered enforce failures | decades rejected |")
    a("|---|---|---|---|")
    for f in ordered:
        filt = doc["filtered_failures"].get(f["cell_id"])
        a(
            f"| `{f['cell_id']}` | {f['n_enforce_failures']} | "
            f"{'n/a' if filt is None else filt} | {_fmt(f['n_rejections'], 0)} |"
        )
    a("")

    # -- diagnostics -------------------------------------------------------- #
    a("## 10. Support and reconciliation diagnostics")
    a("")
    a(
        "Systems B and C run with `bind_waypoints=False`: no Denton reconciliation, and "
        "therefore no post-Denton floor re-application either. Their reconciliation rows "
        "are empty BY CONSTRUCTION, which is what the ablation is measuring, and their "
        "`floor_violations` in section 8 is the evidence for whether the L3 constraint "
        "parameterization holds the floors on its own."
    )
    a("")
    a(
        "| cell | waypoints bound | Denton applied | climate layer | extrapolation share "
        "(mean) | decades off-support | regime TV (mean) |"
    )
    a("|---|---|---|---|---|---|---|")
    for f in ordered:
        sup = f.get("support") or {}
        a(
            f"| `{f['cell_id']}` | {_fmt(f['waypoints_bound'])} | "
            f"{_fmt(f['reconciliation_applied'])} | {f['climate_layer'] or 'n/a'} | "
            f"{_fmt(sup.get('extrapolation_share_mean'))} | "
            f"{_fmt(sup.get('n_flagged_off_support'), 0)} | "
            f"{_fmt(sup.get('regime_freq_tv_mean'))} |"
        )
    a("")
    a("Reconciliation-adjustment distribution (mean |adjustment| per year, per factor):")
    a("")
    a("| cell | factor | variant | p50 | p90 | max | flagged decades |")
    a("|---|---|---|---|---|---|---|")
    for f in ordered:
        recon = (f.get("reconciliation") or {}).get("per_factor") or {}
        if not recon:
            a(f"| `{f['cell_id']}` | -- | not applied | -- | -- | -- | -- |")
            continue
        for name in sorted(recon):
            r = recon[name]
            a(
                f"| `{f['cell_id']}` | {name} | {r['variant']} | "
                f"{_fmt(r['mean_abs_adjustment_p50'], 5)} | "
                f"{_fmt(r['mean_abs_adjustment_p90'], 5)} | "
                f"{_fmt(r['mean_abs_adjustment_max'], 5)} | {r['n_flagged_decades']} |"
            )
    a("")

    # -- conditional tier --------------------------------------------------- #
    a("## 11. Conditional tier -- REPORTED, NOT GATING (sealed)")
    a("")
    a(
        "`multi_seed_decision_rule.conditional_tier_is_not_gating`, verbatim in effect: "
        "conditional-tier results are reported alongside the verdict and DO NOT gate "
        "promotion. Sealed rationale: the platform's purpose weighs conditioning, but "
        "historical tail fidelity remains the falsifiable criterion, so conditioning is "
        "evidence rather than a gate at G2. Revisit at G3."
    )
    a("")
    cond_names = sorted(
        {r["name"] for f in ordered for r in f["conditional_tier_reported_not_gating"]}
    )
    if cond_names:
        a("| cell | " + " | ".join(f"`{n}`" for n in cond_names) + " |")
        a("|---|" + "---|" * len(cond_names))
        for f in ordered:
            by_name = {r["name"]: r["value"] for r in f["conditional_tier_reported_not_gating"]}
            a(
                f"| `{f['cell_id']}` | "
                + " | ".join(_fmt(by_name.get(n)) for n in cond_names)
                + " |"
            )
    else:
        a("_No conditional-suite metrics were present in the stored reports._")
    a("")

    # -- cost --------------------------------------------------------------- #
    a("## 12. Measured cost")
    a("")
    a("| cell | build | assemble unfiltered | assemble filtered | battery | total |")
    a("|---|---|---|---|---|---|")
    total = 0.0
    for f in ordered:
        t = f.get("timings") or {}
        total += float(t.get("total_s", 0.0))
        a(
            f"| `{f['cell_id']}` | {_fmt(t.get('build_s'), 1)}s | "
            f"{_fmt(t.get('assemble_unfiltered_s'), 1)}s | "
            f"{_fmt(t.get('assemble_filtered_s'), 1)}s | "
            f"{_fmt(t.get('battery_s'), 1)}s | {_fmt(t.get('total_s'), 1)}s |"
        )
    a("")
    a(
        f"Total measured cell time: {total / 3600.0:.2f} h (the shared train+validation "
        f"reference was computed ONCE for the whole grid, not per cell)."
    )
    a("")
    return "\n".join(lines) + "\n"


def build(root: Path, prereg_path: Path) -> dict[str, Any]:
    grid, entries = load_grid(root)
    d4_ids, uncomputable = sealed_strategy_ids(prereg_path)
    n_paths = int(grid.get("n_paths", 1024))
    months = int(grid.get("months", 120))
    vintage_id = str(grid.get("vintage_id", "2026-07-26.1"))

    facts: dict[str, dict[str, Any]] = {}
    filtered_failures: dict[str, int | None] = {}
    for cell_id, entry in entries.items():
        facts[cell_id] = cell_facts(
            entry,
            d4_ids=d4_ids,
            uncomputable=uncomputable,
            n_paths=n_paths,
            months=months,
            vintage_id=vintage_id,
        )
        filt = entry["summary"].get("filtered")
        filtered_failures[cell_id] = None if filt is None else filt["n_enforce_failures"]

    if not facts:
        raise SystemExit(f"no completed cells under {root / 'cells'}")

    any_report = next(iter(entries.values()))["report"]
    cset = ab.comparison_set(
        any_report, d4_strategy_ids=d4_ids, uncomputable_strategy_ids=uncomputable
    )
    historical_path = root / "historical-strategy-returns.json"
    historical = json.loads(historical_path.read_text("utf-8")) if historical_path.exists() else {}
    restricted = restricted_comparison(facts, historical, cset.strategy_ids)

    letter_by_system = {f["system_id"]: f["letter"] for f in facts.values()}
    system_order = [row.system_id for row in systems.SYSTEMS if row.system_id in letter_by_system]
    return {
        "grid": {
            "n_paths": n_paths,
            "months": months,
            "vintage_id": vintage_id,
            "reference_seed": grid.get("reference_seed", 20260726),
            "n_resamples": grid.get("n_resamples", 1000),
            "level": grid.get("level", 0.9),
            "block_length": grid.get("block_length", 120),
            "block_batch": grid.get("block_batch", 128),
            "sampler_device": grid.get("sampler_device", "cuda"),
            "failures": grid.get("failures", []),
        },
        "comparison_set": {
            "strategy_ids": list(cset.strategy_ids),
            "excluded_strategy_ids": list(cset.excluded_strategy_ids),
            "n_strategy_names": len(cset.strategy_names),
            "n_band_names": len(cset.band_names),
        },
        "cells": facts,
        "filtered_failures": filtered_failures,
        "letter_by_system": letter_by_system,
        "system_order": system_order,
        "restricted": restricted,
        "head_to_head": head_to_head(facts, restricted),
        "untested_arms": list(systems.UNTESTED_ARMS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_REPO_ROOT / "experiments" / "wp210")
    parser.add_argument("--prereg", type=Path, default=_REPO_ROOT / "pre-registration.yaml")
    parser.add_argument("--out", type=Path, default=_REPO_ROOT / "ABLATION.md")
    parser.add_argument("--json", type=Path, default=_REPO_ROOT / "ablation.json")
    args = parser.parse_args()

    doc = build(args.root, args.prereg)
    args.json.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n", "utf-8")
    args.out.write_text(render(doc), "utf-8")
    print(f"wrote {args.out} and {args.json} from {len(doc['cells'])} cells")


if __name__ == "__main__":
    main()
