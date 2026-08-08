"""Campaign R1 Track B — the six campaign-2 cells on a new vintage.

Run (background it; ~3.5 h measured on the campaign-2 records)::

    uv run python -u scripts/campaign_r1_generator.py --phase battery
    uv run python -u scripts/campaign_r1_generator.py --phase report

NOT a gate, and NOT campaign 2: the checkpoints are the EXISTING campaign-2
artifacts (resolved through configs/campaign2-checkpoints.json, hashes
verified before sampling), the judged code path is run_ablation_grid.run_cell
VERBATIM, and the only new thing under them is the vintage. The sealed
constant CAMPAIGN_VINTAGE_ID is read for the baseline label and never edited;
the re-run vintage arrives by argument (the compute_campaign_reference.py
precedent). Output lands in experiments/campaign-r1/ and the report in
docs/data/CAMPAIGN-R1-GENERATOR.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

RERUN_VINTAGE_DEFAULT = "2026-08-07.5"
CELLS_ROOT = _REPO_ROOT / "experiments" / "campaign-r1" / "cells"
SUMMARY_JSON = _REPO_ROOT / "experiments" / "campaign-r1" / "rerun-summary.json"
BASELINE_JSON = _REPO_ROOT / "artifacts" / "campaign2" / "promotion-verdict.json"
REPORT_OUT = _REPO_ROOT / "docs" / "data" / "CAMPAIGN-R1-GENERATOR.md"


def verify_checkpoint_entry(manifest: dict[str, Any], key: str, *, actual_hash: str) -> None:
    """Refuse to sample from a checkpoint whose bytes are not the recorded ones."""
    entry = manifest.get(key)
    if entry is None:
        raise SystemExit(f"campaign R1: no checkpoint manifest entry for {key}")
    if entry["checkpoint_hash"] != actual_hash:
        raise SystemExit(
            f"campaign R1: checkpoint hash mismatch for {key} - manifest "
            f"{entry['checkpoint_hash'][:16]}..., loaded {actual_hash[:16]}..."
        )


def plan_rerun_cells() -> list[Any]:
    """The six campaign-2 cells: bootstrap-v1 and hier-flow-v1, three seeds."""
    import campaign2_promotion as c2p
    import run_ablation_grid as rag

    from ah.gen import systems

    return [
        rag.Cell(
            letter="B" if system_id == c2p.BENCHMARK_ID else "F",
            system_id=system_id,
            seed_index=seed.index,
            sample_seed=seed.sample_seed,
            train_seed=(
                systems.train_seed_for("flow", seed.index)
                if system_id == c2p.CHALLENGER_ID
                else None
            ),
            neural=system_id == c2p.CHALLENGER_ID,
            family="flow" if system_id == c2p.CHALLENGER_ID else None,
        )
        for system_id in (c2p.BENCHMARK_ID, c2p.CHALLENGER_ID)
        for seed in systems.SEED_PLAN
    ]


def phase_battery(args: argparse.Namespace) -> None:
    import campaign2_promotion as c2p
    import run_ablation_grid as rag
    import torch

    from ah.data.catalog import Catalog
    from ah.eval import prereg as prereg_mod
    from ah.eval.battery import register_reference_dependent_suites
    from ah.eval.reference import compute_reference
    from ah.factors import load_manifest
    from ah.gen import systems
    from ah.gen.bootstrap import build_source

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

    # campaign-2's own checkpoint resolution, hash-verified inside
    # _build_campaign_flow against configs/campaign2-checkpoints.json
    real_build = systems.build

    def dispatch(system_id: str, *, seed_index: int = 0):
        if system_id == c2p.CHALLENGER_ID:
            return c2p._build_campaign_flow(
                seed_index, block_batch=args.block_batch, device=args.sampler_device
            )
        return real_build(system_id, seed_index=seed_index)

    # fail-fast pre-flight: verify every checkpoint's bytes against the
    # committed manifest BEFORE hours of battery work start
    from ah.gen.blocks.flow import load_checkpoint

    manifest_doc = json.loads(c2p.MANIFEST_PATH.read_text("utf-8"))
    for k in c2p.SEEDS:
        key = f"flow:{k}"
        entry = manifest_doc.get(key)
        if entry is None:
            raise SystemExit(f"campaign R1: no checkpoint manifest entry for {key}")
        _model, _std, meta = load_checkpoint(_REPO_ROOT / entry["checkpoint"])
        verify_checkpoint_entry(manifest_doc, key, actual_hash=meta["checkpoint_hash"])
        print(f"  checkpoint {key} verified {meta['checkpoint_hash'][:16]}...", flush=True)

    rag.systems.build = dispatch
    try:
        manifest = load_manifest()
        prereg = prereg_mod.load(_REPO_ROOT / "pre-registration.yaml")
        with Catalog(args.catalog_root) as catalog:
            access = rag.catalog_access(catalog, args.vintage)
            build_source(access, manifest, vintage_id=args.vintage)  # span assertion
            print(f"computing reference on {args.vintage} (sealed parameters)...", flush=True)
            reference = compute_reference(
                access,
                manifest,
                vintage_id=args.vintage,
                seed=rag.REFERENCE_SEED,
                n_resamples=rag.N_RESAMPLES,
                level=rag.LEVEL,
                block_length=rag.BLOCK_LENGTH,
                resample_length=args.months,
            )
            register_reference_dependent_suites(manifest, reference)
            CELLS_ROOT.mkdir(parents=True, exist_ok=True)
            for cell in plan_rerun_cells():
                out_dir = CELLS_ROOT / cell.slug
                if (out_dir / "summary.json").exists() and not args.force:
                    print(f"[skip] {cell.cell_id} (done)")
                    continue
                print(f"[cell] {cell.cell_id} sample_seed {cell.sample_seed}", flush=True)
                summary = rag.run_cell(
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
                print(
                    f"  criterion_bearing={summary['criterion_bearing']} "
                    f"passed_unfiltered={summary['passed_unfiltered']} "
                    f"total {summary['timings']['total_s']:.0f}s",
                    flush=True,
                )
    finally:
        rag.systems.build = real_build
    print("BATTERY PHASE DONE")


def phase_summarize(args: argparse.Namespace) -> None:
    """Compose the per-seed shape with the SAME ab.* arithmetic as the sealed
    verdict phase (campaign2_promotion.phase_verdict), on the re-run cells."""
    import campaign2_promotion as c2p
    import yaml as _yaml

    from ah.eval import ablation as ab

    doc = _yaml.safe_load((_REPO_ROOT / "pre-registration.yaml").read_text("utf-8"))
    d4_ids = tuple(doc["d4_strategies"])
    uncomputable = tuple(doc["reference_run"]["uncomputable_d4_strategies"])

    def load_cell(system_id: str, seed_index: int) -> tuple[dict, dict]:
        for slug_dir in sorted(CELLS_ROOT.iterdir()):
            summary = json.loads((slug_dir / "summary.json").read_text("utf-8"))
            if summary["system_id"] == system_id and summary["seed_index"] == seed_index:
                report = json.loads((slug_dir / "battery.json").read_text("utf-8"))
                return summary, {
                    **report,
                    "n_paths": summary["n_paths"],
                    "months": summary["months"],
                }
        raise SystemExit(f"no re-run cell artifact for {system_id} seed {seed_index}")

    def facts(report: dict) -> dict:
        cset = ab.comparison_set(
            report, d4_strategy_ids=d4_ids, uncomputable_strategy_ids=uncomputable
        )
        return {
            "clause_i": ab.clause_i(report, cset),
            "clause_ii": ab.clause_ii(report, cset),
            "criterion_bearing": ab.criterion_bearing(
                report,
                expected_n_paths=args.n_paths,
                expected_months=args.months,
                expected_vintage_id=args.vintage,
            ),
        }

    per_seed, diffs = [], []
    for k in c2p.SEEDS:
        _b_summary, b_report = load_cell(c2p.BENCHMARK_ID, k)
        c_summary, c_report = load_cell(c2p.CHALLENGER_ID, k)
        b, c = facts(b_report), facts(c_report)
        d = c["clause_i"]["mean"] - b["clause_i"]["mean"]
        nan_blocked = bool(c["clause_i"]["has_nan"] or b["clause_i"]["has_nan"])
        clause_i_beat = bool(d < 0.0) and not nan_blocked
        clause_ii_ok = c["clause_ii"]["count"] <= b["clause_ii"]["count"]
        per_seed.append(
            {
                "seed_index": k,
                "challenger_checkpoint": c_summary["checkpoint_hash"],
                "challenger_mean_elicitability": c["clause_i"]["mean"],
                "benchmark_mean_elicitability": b["clause_i"]["mean"],
                "difference": d,
                "nan_blocked": nan_blocked,
                "clause_i_beat": clause_i_beat,
                "challenger_band_exceedance": c["clause_ii"]["count"],
                "benchmark_band_exceedance": b["clause_ii"]["count"],
                "clause_ii_no_regression": clause_ii_ok,
                "beats_this_seed": bool(clause_i_beat and clause_ii_ok),
                "challenger_criterion_bearing": c["criterion_bearing"],
                "benchmark_criterion_bearing": b["criterion_bearing"],
            }
        )
        diffs.append(d)
    record = {
        "vintage_id": args.vintage,
        "note": "campaign R1 vintage-robustness EXHIBIT - not a verdict",
        "per_seed": per_seed,
        "pooled": ab.pooled_difference(diffs),
    }
    SUMMARY_JSON.write_text(json.dumps(record, indent=1, default=str) + "\n", "utf-8")
    print(f"wrote {SUMMARY_JSON.relative_to(_REPO_ROOT)}")


def phase_report(args: argparse.Namespace) -> None:
    import campaign_r1_compare as crc

    baseline = json.loads(BASELINE_JSON.read_text("utf-8"))
    rerun = json.loads(SUMMARY_JSON.read_text("utf-8"))
    rows = crc.compare_cells(baseline, rerun)
    # pooled_difference names its verdict key 'beats'; the verdict file
    # recorded it as 'pooled_beat' - normalize for the renderer
    rerun_pooled = dict(rerun["pooled"])
    rerun_pooled.setdefault("pooled_beat", rerun_pooled.get("beats"))
    text = crc.render_markdown(
        rows,
        vintage=rerun["vintage_id"],
        baseline_vintage=baseline["vintage_id"],
        baseline_verdict=baseline["verdict"],
        rerun_pooled=rerun_pooled,
        baseline_pooled=baseline["pooled"],
    )
    REPORT_OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {REPORT_OUT.relative_to(_REPO_ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("battery", "summarize", "report"), required=True)
    parser.add_argument("--vintage", default=RERUN_VINTAGE_DEFAULT)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--n-paths", type=int, default=1024)
    parser.add_argument("--months", type=int, default=120)
    parser.add_argument("--block-batch", type=int, default=64)
    parser.add_argument("--sampler-device", default="cpu")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.phase == "battery":
        phase_battery(args)
    elif args.phase == "summarize":
        phase_summarize(args)
    else:
        phase_report(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
