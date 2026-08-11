"""WP2.10: run the full multi-seed ablation grid (systems A-E) and checkpoint it.

One long, unattended, RESUMABLE batch. Design constraints, all deliberate:

* **One process, strictly sequential.** Never two GPU jobs at once — measured on
  this machine, concurrency turned a 90-minute battery into nine hours. Nothing
  here forks, and the DuckDB catalog (which takes an exclusive file lock) is opened
  once.
* **The reference is computed ONCE and reused.** ``run_full_battery`` recomputes
  it per call; it is a pure function of ``(access, manifest, campaign vintage,
  reference seed, n_resamples, level, block_length, resample_length)``, every one
  of which is identical across all cells, and it costs ~6 minutes a time. This
  script therefore performs ``run_full_battery``'s three documented steps
  explicitly, with identical arguments — ``compute_reference``,
  ``register_reference_dependent_suites``, ``run_battery`` — which
  ``tests/test_ablation_grid.py`` pins as equivalent on a synthetic case.
* **Checkpoint after every cell.** A cell writes its own directory under
  ``experiments/wp210/cells/<cell_id>/``; a rerun skips any cell whose
  ``summary.json`` already exists. A failure costs one cell, not the grid, and a
  cell that raises is recorded in ``failures.json`` and does not stop the run.
* **Filtered and unfiltered, every cell**, at the sealed criterion size.

Usage::

    uv run python -u scripts/run_ablation_grid.py --block-batch 128 \
        --sampler-device cuda            # the whole grid
    uv run python -u scripts/run_ablation_grid.py --only D:hier-flow-v1:0   # one cell
    uv run python -u scripts/run_ablation_grid.py --dry-run                 # plan only
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval import prereg as prereg_mod  # noqa: E402
from ah.eval.battery import (  # noqa: E402
    register_reference_dependent_suites,
    run_battery,
)
from ah.eval.reference import compute_reference  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen import systems  # noqa: E402
from ah.gen.bootstrap import (  # noqa: E402
    CAMPAIGN_VINTAGE_ID,
    CRITERION_MONTHS,
    CRITERION_N_PATHS,
    build_source,
)
from ah.splits import DataAccess  # noqa: E402

# The sealed reference-run parameters (pre-registration.yaml `reference_run:`),
# identical to every WP2.4/2.7/2.8/2.9 battery script.
REFERENCE_SEED = 20260726
N_RESAMPLES = 1000
LEVEL = 0.9
BLOCK_LENGTH = 120

# CAMPAIGN-3 (AM-2026-08-10-001): the grid root moved. The wp210 root is the
# CAMPAIGN-2 grid record, frozen; running the campaign-3 grid there would make
# the checkpoint-resume logic silently SKIP every A/B/C/E cell (same cell ids,
# campaign-2 summaries already on disk) -- the fourth instance of the
# campaign-split trap (vintage id, factor set, checkpoint manifest, grid root).
OUT_ROOT = _REPO_ROOT / "experiments" / "campaign3" / "grid"


@dataclass(frozen=True)
class Cell:
    """One (system, seed index) job."""

    letter: str
    system_id: str
    seed_index: int
    sample_seed: int
    train_seed: int | None
    neural: bool
    family: str | None

    @property
    def cell_id(self) -> str:
        return f"{self.letter}:{self.system_id}:{self.seed_index}"

    @property
    def slug(self) -> str:
        return f"{self.letter}-{self.system_id}-s{self.seed_index}"


def plan_cells() -> list[Cell]:
    """The grid, in ASCENDING measured cost order.

    Cheap cells first is not cosmetic: it means an overnight batch has produced
    most of its rows before it reaches the single most expensive family, and a
    configuration mistake surfaces in minutes rather than after ninety.
    """
    cost_rank = {
        "bootstrap-v1": 0,
        systems.SYSTEM_A_ID: 1,
        systems.neural_only_id("flow"): 2,
        systems.neural_rollout_id("flow"): 3,
        "hier-flow-v1": 4,
        "hier-diffusion-v1": 5,
    }
    cells: list[Cell] = []
    for row in systems.SYSTEMS:
        for seed in systems.SEED_PLAN:
            cells.append(
                Cell(
                    letter=row.letter,
                    system_id=row.system_id,
                    seed_index=seed.index,
                    sample_seed=seed.sample_seed,
                    train_seed=(
                        systems.train_seed_for(row.family, seed.index)
                        if row.neural and row.family
                        else None
                    ),
                    neural=row.neural,
                    family=row.family,
                )
            )
    cells.sort(key=lambda c: (cost_rank.get(c.system_id, 99), c.seed_index))
    return cells


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def _verdict(doc: dict[str, Any], which: str) -> dict[str, Any]:
    rows = [r for tier in doc[which]["tiers"].values() for r in tier if r["severity"] == "enforce"]
    failures = [r for r in rows if r["passed"] is False]
    return {
        "n_enforce": len(rows),
        "n_enforce_failures": len(failures),
        "enforce_results": [
            {"name": r["name"], "tier": r["tier"], "value": r["value"], "passed": r["passed"]}
            for r in sorted(rows, key=lambda r: r["name"])
        ],
    }


def _strip_by_decade(support: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in support.items() if not k.endswith("_by_decade")}


def run_cell(
    cell: Cell,
    *,
    access: DataAccess,
    manifest,
    prereg,
    reference,
    n_paths: int,
    months: int,
    out_dir: Path,
    block_batch: int,
    sampler_device: str,
) -> dict[str, Any]:
    """Assemble both ensembles, judge them, and write the cell's artifacts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    t0 = time.time()

    system = systems.build(cell.system_id, seed_index=cell.seed_index)
    timings["build_s"] = time.time() - t0

    # `bootstrap-v1` never enters the joinery, so it HAS no acceptance filter and
    # its `sample_months` takes no `unfiltered=`. There is no filtered/unfiltered
    # distinction to draw for it, and inventing one by re-sampling the same
    # ensemble twice would put a fabricated "filtered" column in the report. The
    # capability is detected, and its absence recorded, rather than assumed.
    has_filter = "unfiltered" in inspect.signature(system.sample_months).parameters

    t = time.time()
    print(
        f"    assembling UNFILTERED ({n_paths} x {months}) seed {cell.sample_seed}...", flush=True
    )
    unfiltered = (
        system.sample_months(months, n_paths, cell.sample_seed, unfiltered=True)
        if has_filter
        else system.sample_months(months, n_paths, cell.sample_seed)
    )
    timings["assemble_unfiltered_s"] = time.time() - t

    filtered = None
    if has_filter:
        t = time.time()
        print("    assembling FILTERED (same seed, filter on)...", flush=True)
        filtered = system.sample_months(months, n_paths, cell.sample_seed)
        timings["assemble_filtered_s"] = time.time() - t
    else:
        print("    no acceptance filter on this system (not joinery-assembled)", flush=True)
        timings["assemble_filtered_s"] = 0.0

    t = time.time()
    print("    judging (sealed battery, unfiltered primary)...", flush=True)
    report = run_battery(
        unfiltered,
        reference=reference,
        prereg=prereg,
        manifest=manifest,
        seed=cell.sample_seed,
        filtered=filtered,
    )
    timings["battery_s"] = time.time() - t
    timings["total_s"] = time.time() - t0

    doc = report.to_dict()
    (out_dir / "battery.json").write_text(report.to_json(), "utf-8")
    (out_dir / "battery.md").write_text(report.to_markdown(), "utf-8")

    meta_c = unfiltered.meta.conditioning
    filter_record = meta_c.get("acceptance_filter", {})
    summary = {
        "cell_id": cell.cell_id,
        "letter": cell.letter,
        "system_id": cell.system_id,
        "seed_index": cell.seed_index,
        "sample_seed": cell.sample_seed,
        "train_seed": cell.train_seed,
        "family": cell.family,
        "generator_id": unfiltered.meta.generator_id,
        "checkpoint_hash": unfiltered.meta.checkpoint_hash,
        "config_hash": unfiltered.meta.config_hash,
        "vintage_id": doc["vintage_id"],
        # BatteryReport.to_dict() does NOT serialize the ensemble size, so it is
        # read off the judged ensemble itself -- the authoritative source, and the
        # same object ah.eval.battery.criterion_bearing_for compared against the
        # sealed ensemble_size when it stamped `criterion_bearing` above.
        "n_paths": unfiltered.n_paths,
        "months": unfiltered.months,
        "criterion_bearing": doc["criterion_bearing"],
        "prereg_verified": doc["prereg_verified"],
        "prereg_digest": doc["prereg_digest"],
        "passed_unfiltered": doc["passed"],
        "unfiltered": _verdict(doc, "unfiltered"),
        "filtered": _verdict(doc, "filtered") if doc.get("filtered") else None,
        "system_description": meta_c.get("system"),
        "waypoints_bound": meta_c.get("waypoints_bound"),
        "reconciliation_applied": meta_c.get("reconciliation_applied"),
        "climate_layer": meta_c.get("climate_layer"),
        "layer_artifacts": meta_c.get("layer_artifacts"),
        "residual_model": meta_c.get("residual_model"),
        "cb_contract_fingerprint": (meta_c.get("cb_contract") or {}).get("fingerprint"),
        "has_acceptance_filter": bool(has_filter),
        "n_rejections": filter_record.get("n_rejected"),
        "support_unfiltered": _strip_by_decade(meta_c.get("support", {})),
        "reconciliation_unfiltered": meta_c.get("reconciliation"),
        "waypoint_tolerance_unfiltered": meta_c.get("waypoint_tolerance"),
        "sampler_fallbacks": meta_c.get("sampler_fallbacks"),
        "block_sampler": meta_c.get("block_sampler"),
        "block_sampler_batch": meta_c.get("block_sampler_batch", block_batch),
        "block_sampler_device": meta_c.get("block_sampler_device", sampler_device),
        "timings": timings,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", "utf-8"
    )
    return summary


def dump_historical_strategy_returns(reference, path: Path) -> dict[str, Any]:
    """The dated historical realization path per D4 strategy, written once.

    This is what makes ``benchmark_draw_span_bias``'s restricted comparison
    computable AFTER the grid without recomputing the reference: the restricted
    score needs history's realizations by date, and the report already carries the
    generated ``(var_95, es_95)`` forecast pair.
    """
    from ah.eval.ablation import historical_strategy_returns_dated
    from ah.strategies import load_d4_strategies, load_derived_series

    derived = load_derived_series()
    out: dict[str, Any] = {}
    for strategy in load_d4_strategies():
        got = historical_strategy_returns_dated(reference, strategy, derived)
        if got is None:
            out[strategy.strategy_id] = None
            continue
        index, values = got
        out[strategy.strategy_id] = {
            "dates": [str(d.date()) for d in index],
            "values": [float(v) for v in values],
        }
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", "utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--n-paths", type=int, default=CRITERION_N_PATHS)
    parser.add_argument("--months", type=int, default=CRITERION_MONTHS)
    parser.add_argument("--block-batch", type=int, default=128)
    parser.add_argument("--sampler-device", default="cuda")
    parser.add_argument("--only", nargs="*", default=None, help="cell ids to run")
    parser.add_argument("--force", action="store_true", help="rerun cells that already exist")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cells = plan_cells()
    if args.only:
        wanted = set(args.only)
        cells = [c for c in cells if c.cell_id in wanted]
        if not cells:
            raise SystemExit(f"--only matched no cells; known: {[c.cell_id for c in plan_cells()]}")

    cells_root = args.out_root / "cells"
    print(f"grid: {len(cells)} cells at {args.n_paths} x {args.months}, vintage {args.vintage}")
    for cell in cells:
        done = (cells_root / cell.slug / "summary.json").exists()
        print(
            f"  {cell.cell_id:44s} sample_seed {cell.sample_seed}"
            f"{'' if cell.train_seed is None else f'  train_seed {cell.train_seed}'}"
            f"{'   [done]' if done and not args.force else ''}"
        )
    if args.dry_run:
        return

    import torch

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

    # Both L3 families read their OWN module-level sampler defaults, so set both:
    # naming the arm that is not running is inert. Every ensemble records what it used.
    from ah.gen.blocks import diffusion as df
    from ah.gen.blocks import flow as fl

    for module in (df, fl):
        module.DEFAULT_BLOCK_BATCH = int(args.block_batch)
        module.DEFAULT_SAMPLER_DEVICE = str(args.sampler_device)

    manifest = load_manifest()
    prereg = prereg_mod.load(_REPO_ROOT / "pre-registration.yaml")
    args.out_root.mkdir(parents=True, exist_ok=True)

    failures: list[dict[str, Any]] = []
    completed: list[str] = []
    grid_t0 = time.time()

    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        build_source(access, manifest, vintage_id=args.vintage)  # sealed-span assertion

        print("computing the train+val reference ONCE for the whole grid...", flush=True)
        t = time.time()
        reference = compute_reference(
            access,
            manifest,
            vintage_id=args.vintage,
            seed=REFERENCE_SEED,
            n_resamples=N_RESAMPLES,
            level=LEVEL,
            block_length=BLOCK_LENGTH,
            resample_length=args.months,
        )
        register_reference_dependent_suites(manifest, reference)
        print(f"  reference ready [{time.time() - t:.0f}s]", flush=True)

        dump_historical_strategy_returns(
            reference, args.out_root / "historical-strategy-returns.json"
        )

        for i, cell in enumerate(cells, start=1):
            out_dir = cells_root / cell.slug
            if (out_dir / "summary.json").exists() and not args.force:
                print(f"[{i}/{len(cells)}] {cell.cell_id}  SKIP (already done)", flush=True)
                completed.append(cell.cell_id)
                continue
            print(
                f"\n[{i}/{len(cells)}] {cell.cell_id}  ({time.time() - grid_t0:.0f}s elapsed)",
                flush=True,
            )
            try:
                summary = run_cell(
                    cell,
                    access=access,
                    manifest=manifest,
                    prereg=prereg,
                    reference=reference,
                    n_paths=args.n_paths,
                    months=args.months,
                    out_dir=out_dir,
                    block_batch=args.block_batch,
                    sampler_device=args.sampler_device,
                )
            except Exception as exc:  # one cell's failure must not cost the grid
                print(f"    FAILED: {type(exc).__name__}: {exc}", flush=True)
                traceback.print_exc()
                failures.append(
                    {
                        "cell_id": cell.cell_id,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                    }
                )
                (args.out_root / "failures.json").write_text(
                    json.dumps(failures, indent=2) + "\n", "utf-8"
                )
                continue
            completed.append(cell.cell_id)
            print(
                f"    criterion_bearing {summary['criterion_bearing']}; "
                f"unfiltered {'PASS' if summary['passed_unfiltered'] else 'FAIL'} "
                f"({summary['unfiltered']['n_enforce_failures']}"
                f"/{summary['unfiltered']['n_enforce']}); "
                f"{summary['timings']['total_s']:.0f}s",
                flush=True,
            )

    manifest_doc = {
        "n_paths": args.n_paths,
        "months": args.months,
        "vintage_id": args.vintage,
        "reference_seed": REFERENCE_SEED,
        "n_resamples": N_RESAMPLES,
        "level": LEVEL,
        "block_length": BLOCK_LENGTH,
        "block_batch": args.block_batch,
        "sampler_device": args.sampler_device,
        "cells": [asdict(c) | {"cell_id": c.cell_id, "slug": c.slug} for c in plan_cells()],
        "completed": sorted(completed),
        "failures": failures,
        "wall_seconds": time.time() - grid_t0,
    }
    (args.out_root / "grid.json").write_text(
        json.dumps(manifest_doc, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    print(
        f"\ngrid finished in {(time.time() - grid_t0) / 60:.1f} min: "
        f"{len(completed)} completed, {len(failures)} failed"
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
