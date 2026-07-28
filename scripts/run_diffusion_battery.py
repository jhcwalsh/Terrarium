"""WP2.8: full sealed battery for hier-diffusion-v1 through the joinery,
n_paths=1024 (criterion-bearing), filtered + unfiltered — one seed (WP2.10 will
redo this multi-seed; this run proves the pipe and gives the honest first look).

Also reports, against the WP2.7 bootstrap-stand-in baseline
(artifacts/wp27/summary.json): the Denton reconciliation-adjustment
distribution (the trained conditional sampler's adjustments should SHRINK — the
WP2.7 numbers to beat are policy p50 2.87 pct, cpi p50 0.167 log) and the
support/off-support diagnostics.

Usage (offline; local catalog + fitted artifacts + trained checkpoint)::

    uv run python -u scripts/run_diffusion_battery.py --out-dir artifacts/wp28

The generator is resolved THROUGH THE REGISTRY FACTORY (hash pins verified), so
the run exercises exactly the lineage path WP2.10 will use.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval import prereg as prereg_mod  # noqa: E402
from ah.eval.battery import run_full_battery  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen import registry  # noqa: E402
from ah.gen.blocks import diffusion as df  # noqa: E402
from ah.gen.bootstrap import (  # noqa: E402
    CAMPAIGN_VINTAGE_ID,
    CRITERION_MONTHS,
    CRITERION_N_PATHS,
    build_source,
)
from ah.splits import DataAccess  # noqa: E402

# The sealed reference-run parameters (pre-registration.yaml `reference_run:`).
REFERENCE_SEED = 20260726
N_RESAMPLES = 1000
LEVEL = 0.9
BLOCK_LENGTH = 120

DEFAULT_RUN_SEED = 20260727


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
            {"name": r["name"], "value": r["value"], "passed": r["passed"]}
            for r in sorted(rows, key=lambda r: r["name"])
        ],
    }


def _recon_comparison(mine: dict[str, Any], baseline_path: Path) -> list[str]:
    lines = ["### Reconciliation shrinkage vs the WP2.7 bootstrap baseline", ""]
    baseline = None
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text("utf-8"))["reconciliation_unfiltered"]
    for name, row in mine["per_factor"].items():
        base = baseline["per_factor"].get(name) if baseline else None
        base_txt = (
            f"(wp2.7 baseline p50 {base['mean_abs_adjustment_p50']:.5f}, "
            f"p90 {base['mean_abs_adjustment_p90']:.5f})"
            if base
            else "(no baseline found)"
        )
        lines.append(
            f"- {name} ({row['variant']}): p50 {row['mean_abs_adjustment_p50']:.5f}, "
            f"p90 {row['mean_abs_adjustment_p90']:.5f}, max {row['mean_abs_adjustment_max']:.5f}, "
            f"flagged {row['n_flagged_decades']} {base_txt}"
        )
    lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=_REPO_ROOT / "artifacts" / "wp28")
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--seed", type=int, default=DEFAULT_RUN_SEED)
    parser.add_argument("--n-paths", type=int, default=CRITERION_N_PATHS)
    parser.add_argument("--months", type=int, default=CRITERION_MONTHS)
    parser.add_argument("--baseline", type=Path, default=_REPO_ROOT / "artifacts" / "wp27")
    # WP2.8b throughput controls. Defaults reproduce the WP2.8 run BIT FOR BIT
    # (width 1 = one network evaluation per block per decade, on CPU). A wider
    # width batches the network across decades and is ~10x (CPU) to ~100x (CUDA)
    # faster, at the cost of float32 round-off differences that a batched GEMM
    # makes unavoidable — see scripts/verify_block_batching.py for the evidence.
    # Whatever is chosen is recorded in the ensemble lineage.
    parser.add_argument("--block-batch", type=int, default=df.DEFAULT_BLOCK_BATCH)
    parser.add_argument(
        "--sampler-device",
        default=df.DEFAULT_SAMPLER_DEVICE,
        help="cpu (default) or cuda; cuda needs CUBLAS_WORKSPACE_CONFIG=:4096:8 in the "
        "environment for torch.use_deterministic_algorithms(True) to accept cuBLAS",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    prereg = prereg_mod.load(_REPO_ROOT / "pre-registration.yaml")

    # Batch-1 traced inference is ~2x faster single-threaded on this CPU
    # (measured); determinism flags per plan Sec.1 for the sampling path too.
    import torch

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

    df.DEFAULT_BLOCK_BATCH = int(args.block_batch)
    df.DEFAULT_SAMPLER_DEVICE = str(args.sampler_device)

    print(f"resolving {df.GENERATOR_ID} through the registry (pins verified)...")
    system = registry.resolve(df.GENERATOR_ID)
    print(f"checkpoint {system.checkpoint_hash}")
    print(f"block batch {args.block_batch} on {args.sampler_device}")

    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        build_source(access, manifest, vintage_id=args.vintage)  # sealed-span assertion

        t0 = time.time()
        print(f"assembling UNFILTERED ensemble ({args.n_paths} x {args.months})...")
        unfiltered = system.sample_months(args.months, args.n_paths, args.seed, unfiltered=True)
        print(f"  [{time.time() - t0:.0f}s]")
        print("assembling FILTERED ensemble (same seed, filter on)...")
        filtered = system.sample_months(args.months, args.n_paths, args.seed)
        n_rej = filtered.meta.conditioning["acceptance_filter"]["n_rejected"]
        print(f"  filter rejected {n_rej}/{args.n_paths}  [{time.time() - t0:.0f}s]")

        print("running the sealed battery (unfiltered primary, filtered attached)...")
        report = run_full_battery(
            unfiltered,
            access=access,
            manifest=manifest,
            prereg=prereg,
            seed=args.seed,
            reference_seed=REFERENCE_SEED,
            n_resamples=N_RESAMPLES,
            level=LEVEL,
            block_length=BLOCK_LENGTH,
            filtered=filtered,
        )

    doc = report.to_dict()
    (args.out_dir / f"battery-seed{args.seed}.json").write_text(report.to_json(), "utf-8")
    (args.out_dir / f"battery-seed{args.seed}.md").write_text(report.to_markdown(), "utf-8")

    meta_c = unfiltered.meta.conditioning
    summary = {
        "system": df.GENERATOR_ID,
        "checkpoint_hash": system.checkpoint_hash,
        "config_hash": system.config_hash,
        "vintage_id": args.vintage,
        "n_paths": args.n_paths,
        "months": args.months,
        "seed": args.seed,
        "criterion_bearing": doc["criterion_bearing"],
        "prereg_verified": doc["prereg_verified"],
        "prereg_digest": doc["prereg_digest"],
        "passed_unfiltered": doc["passed"],
        "unfiltered": _verdict(doc, "unfiltered"),
        "filtered": _verdict(doc, "filtered") if doc.get("filtered") else None,
        "layer_artifacts": meta_c["layer_artifacts"],
        "cb_contract_fingerprint": meta_c["cb_contract"]["fingerprint"],
        "n_rejections": n_rej,
        "support_unfiltered": {
            k: v for k, v in meta_c["support"].items() if not k.endswith("_by_decade")
        },
        "reconciliation_unfiltered": meta_c["reconciliation"],
        "waypoint_tolerance_unfiltered": meta_c["waypoint_tolerance"],
        "sampler_fallbacks": meta_c["sampler_fallbacks"],
        "block_sampler_batch": meta_c["block_sampler_batch"],
        "block_sampler_device": meta_c["block_sampler_device"],
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", "utf-8"
    )

    support = summary["support_unfiltered"]
    lines = [
        "# WP2.8 hier-diffusion-v1 battery + joinery diagnostics",
        "",
        f"- system: {df.GENERATOR_ID} (L1+L2+L4, trained 3a blocks)",
        f"- checkpoint: {system.checkpoint_hash}",
        f"- vintage {args.vintage}; n_paths {args.n_paths}; months {args.months}; "
        f"seed {args.seed}; criterion_bearing {doc['criterion_bearing']}",
        f"- battery verdict: unfiltered "
        f"{'PASS' if doc['passed'] else 'FAIL'} "
        f"({summary['unfiltered']['n_enforce_failures']}/{summary['unfiltered']['n_enforce']} "
        f"enforce failures); filtered "
        f"{summary['filtered'] and summary['filtered']['n_enforce_failures']} failures",
        "",
    ]
    lines += _recon_comparison(summary["reconciliation_unfiltered"], args.baseline / "summary.json")
    baseline_support = None
    baseline_path = args.baseline / "summary.json"
    if baseline_path.exists():
        baseline_support = json.loads(baseline_path.read_text("utf-8"))["support_unfiltered"]
    lines += [
        "### Support / off-support",
        f"- extrapolation share mean {support['extrapolation_share_mean']:.4f} "
        f"(wp2.7 baseline "
        f"{baseline_support and round(baseline_support['extrapolation_share_mean'], 4)})",
        f"- decades flagged off-support: {support['n_flagged_off_support']} "
        f"(baseline {baseline_support and baseline_support['n_flagged_off_support']})",
        f"- regime TV mean {support['regime_freq_tv_mean']:.4f} "
        f"(baseline {baseline_support and round(baseline_support['regime_freq_tv_mean'], 4)})",
        f"- sampler fallbacks: {summary['sampler_fallbacks']}",
        "",
        "### Waypoint tolerance",
        f"- {summary['waypoint_tolerance_unfiltered']}",
        "",
    ]
    (args.out_dir / "wp28-battery-report.md").write_text("\n".join(lines), "utf-8")

    print(f"criterion_bearing: {doc['criterion_bearing']}")
    print(f"unfiltered verdict: {'PASS' if doc['passed'] else 'FAIL'}")
    for row in summary["unfiltered"]["enforce_results"]:
        print(f"  enforce {row['name']:42s} {row['value']!s:>12} passed={row['passed']}")
    if summary["filtered"]:
        print(f"filtered enforce failures: {summary['filtered']['n_enforce_failures']}")
    print(f"wrote {args.out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
