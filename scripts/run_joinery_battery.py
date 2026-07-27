"""Run the full validation battery against the assembled L1+L2+L4 system (WP2.7).

The first end-to-end run of the whole hierarchy: fitted L1 climate posterior ->
fitted L2 semi-Markov skeleton -> waypoints -> bootstrap stand-in blocks ->
cross-fade -> Denton reconciliation -> acceptance filter -> Ensemble. This is
ablation system C's machinery exercised for free (STEP2 Sec.WP2.7); systems.py
names the sealed ablation compositions in WP2.10.

Runs at the SEALED criterion size (n_paths=1024, months=120, campaign vintage
2026-07-26.1), FILTERED and UNFILTERED, and hands both to
``ah.eval.battery.run_full_battery`` (which verifies the pre-registration and
lock before judging anything). Also writes ``joinery-assembly-report.md`` with
the support diagnostics, the reconciliation-adjustment distribution, the
waypoint-tolerance record and the full acceptance-filter log -- the WP2.7
evidence the sealed battery report has no line for.

Usage (offline; local catalog + fitted artifacts, no network)::

    uv run python scripts/run_joinery_battery.py --out-dir artifacts/wp27

Determinism: one --seed; layer seeds are seed + LAYER_SEED_OFFSETS (assemble.py);
the reference bootstrap draw uses the sealed reference_run.seed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ah.data.catalog import Catalog
from ah.eval import prereg as prereg_mod
from ah.eval.battery import run_full_battery
from ah.factors import load_manifest
from ah.gen.bootstrap import (
    CAMPAIGN_VINTAGE_ID,
    CRITERION_MONTHS,
    CRITERION_N_PATHS,
    build_source,
)
from ah.gen.joinery import assemble as asm
from ah.gen.joinery.assemble import JoineryConfig, assemble_decades
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The sealed reference-run parameters (pre-registration.yaml `reference_run:`).
REFERENCE_SEED = 20260726
N_RESAMPLES = 1000
LEVEL = 0.9
BLOCK_LENGTH = 120

# WP2.7's own run seed (distinct from the reference seed by convention only).
DEFAULT_RUN_SEED = 20260727


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def _enforce_rows(doc: dict[str, Any], which: str) -> list[dict[str, Any]]:
    tiers = doc[which]["tiers"]
    rows = [row for tier in tiers.values() for row in tier]
    return [r for r in rows if r["severity"] == "enforce"]


def _verdict(doc: dict[str, Any], which: str) -> dict[str, Any]:
    rows = _enforce_rows(doc, which)
    failures = [r for r in rows if r["passed"] is False]
    return {
        "n_enforce": len(rows),
        "n_enforce_failures": len(failures),
        "enforce_failures": [
            {"name": r["name"], "suite": r["suite"], "value": r["value"]} for r in failures
        ],
        "enforce_results": [
            {"name": r["name"], "value": r["value"], "passed": r["passed"]}
            for r in sorted(rows, key=lambda r: r["name"])
        ],
    }


def _assembly_report(meta_conditioning: dict[str, Any], label: str) -> list[str]:
    support = meta_conditioning["support"]
    recon = meta_conditioning["reconciliation"]
    tol = meta_conditioning["waypoint_tolerance"]
    filt = meta_conditioning["acceptance_filter"]
    lines = [
        f"## {label} ensemble",
        "",
        "### Waypoint tolerance",
        f"- all decades within tolerance: {tol['all_ok']} "
        f"({tol['n_decades_ok']} of {meta_conditioning['reconciliation']['n_decades']})",
        f"- floor-clamped cells: {tol['floor_clamped_cells']}",
        "",
        "### Reconciliation adjustment distribution (mean |x-z| per decade, working space)",
    ]
    for name, row in recon["per_factor"].items():
        lines.append(
            f"- {name} ({row['variant']}): p50 {row['mean_abs_adjustment_p50']:.5f}, "
            f"p90 {row['mean_abs_adjustment_p90']:.5f}, max {row['mean_abs_adjustment_max']:.5f}, "
            f"flagged decades {row['n_flagged_decades']}"
        )
    lines += [
        "",
        "### Support diagnostics",
        f"- extrapolation quantile: p{int(support['quantile'] * 100)} of historical self-distances",
        f"- extrapolation share: mean {support['extrapolation_share_mean']:.4f}, "
        f"max {support['extrapolation_share_max']:.4f}",
        f"- decades flagged off-support (share > {asm.sp.OFF_SUPPORT_FLAG_SHARE}): "
        f"{support['n_flagged_off_support']}",
        f"- regime-mix TV distance: mean {support['regime_freq_tv_mean']:.4f}",
        "- pooled regime mix: "
        + ", ".join(f"{k} {v:.3f}" for k, v in support["regime_frequencies_pooled"].items()),
        f"- sampler stratum fallbacks: {meta_conditioning['sampler_fallbacks']}",
        "",
        "### Acceptance filter",
        f"- enabled: {filt['enabled']}; metrics {filt['metrics']} on {filt['factors']}",
        f"- rejected {filt['n_rejected']} decade(s) (cap {filt['max_reject_fraction']:.0%})",
    ]
    for entry in filt["rejections"]:
        lines.append(
            f"  - decade {entry['decade']} (seed {entry['decade_seed']}, "
            f"score {entry['score']:.3f}) -> replacement index {entry['replacement_index']} "
            f"(seed {entry['replacement_seed']}, score {entry['replacement_score']:.3f})"
        )
    lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=_REPO_ROOT / "artifacts" / "wp27")
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--seed", type=int, default=DEFAULT_RUN_SEED)
    parser.add_argument("--n-paths", type=int, default=CRITERION_N_PATHS)
    parser.add_argument("--months", type=int, default=CRITERION_MONTHS)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    prereg = prereg_mod.load(_REPO_ROOT / "pre-registration.yaml")
    climate = asm.load_climate_artifact(asm.DEFAULT_CLIMATE_ARTIFACT)
    regimes_artifact = asm.load_regimes_artifact(asm.DEFAULT_REGIMES_ARTIFACT)
    print(f"L1 artifact sha {climate.meta['content_sha256'][:16]}...")
    print(f"L2 artifact sha {regimes_artifact.meta['content_sha256'][:16]}...")

    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        source = build_source(access, manifest, vintage_id=args.vintage)
        print(f"draw span {source.dates[0].date()}..{source.dates[-1].date()} ({source.n_rows} m)")
        print(f"regime frequencies: {dict(sorted(source.label_frequencies.items()))}")

        print(f"assembling UNFILTERED ensemble ({args.n_paths} x {args.months})...")
        unfiltered = assemble_decades(
            climate=climate,
            regimes_artifact=regimes_artifact,
            source=source,
            n_decades=args.n_paths,
            seed=args.seed,
            months=args.months,
            config=JoineryConfig(acceptance_filter=False),
        )
        print("assembling FILTERED ensemble (same seed, filter on)...")
        filtered = assemble_decades(
            climate=climate,
            regimes_artifact=regimes_artifact,
            source=source,
            n_decades=args.n_paths,
            seed=args.seed,
            months=args.months,
            config=JoineryConfig(acceptance_filter=True),
        )
        n_rej = filtered.meta.conditioning["acceptance_filter"]["n_rejected"]
        print(f"filter rejected {n_rej}/{args.n_paths} decades")

        print("running the battery (unfiltered primary, filtered attached)...")
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

    summary = {
        "system": asm.GENERATOR_ID,
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
        "layer_artifacts": unfiltered.meta.conditioning["layer_artifacts"],
        "acceptance_filter": {
            k: v
            for k, v in filtered.meta.conditioning["acceptance_filter"].items()
            if k != "rejections"
        },
        "n_rejections": n_rej,
        "support_unfiltered": {
            k: v
            for k, v in unfiltered.meta.conditioning["support"].items()
            if not k.endswith("_by_decade")
        },
        "reconciliation_unfiltered": unfiltered.meta.conditioning["reconciliation"],
        "waypoint_tolerance_unfiltered": unfiltered.meta.conditioning["waypoint_tolerance"],
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", "utf-8"
    )

    lines = [
        "# WP2.7 joinery assembly report",
        "",
        f"- system: {asm.GENERATOR_ID} (L1+L2+L4, bootstrap stand-in blocks)",
        f"- vintage: {args.vintage}; n_paths {args.n_paths}; months {args.months}; "
        f"seed {args.seed}",
        f"- criterion_bearing: {doc['criterion_bearing']}",
        f"- battery verdict (unfiltered): "
        f"{'PASS' if doc['passed'] else 'FAIL'} "
        f"({summary['unfiltered']['n_enforce_failures']} enforce failures of "
        f"{summary['unfiltered']['n_enforce']})",
        "",
    ]
    lines += _assembly_report(unfiltered.meta.conditioning, "Unfiltered")
    lines += _assembly_report(filtered.meta.conditioning, "Filtered")
    (args.out_dir / "joinery-assembly-report.md").write_text("\n".join(lines), "utf-8")

    print(f"criterion_bearing: {doc['criterion_bearing']}")
    print(f"unfiltered verdict: {'PASS' if doc['passed'] else 'FAIL'}")
    for row in summary["unfiltered"]["enforce_results"]:
        print(f"  enforce {row['name']:42s} {row['value']!s:>12} passed={row['passed']}")
    if summary["filtered"]:
        print(f"filtered enforce failures: {summary['filtered']['n_enforce_failures']}")
    print(f"wrote {args.out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
