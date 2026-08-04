"""Campaign-2 promotion: train three seeds, run criterion batteries, apply the
sealed multi-seed decision rule against bootstrap-v1.

Phases (run in order; each is resumable/idempotent)::

    uv run python -u scripts/campaign2_promotion.py --phase train
    uv run python -u scripts/campaign2_promotion.py --phase battery
    uv run python -u scripts/campaign2_promotion.py --phase verdict

NOT tuning (the train_ablation_seeds.py discipline): the config is the committed
WP2.9 flow selection with exactly one forced change -- ``n_factors`` follows the
sealed campaign-2 factor set (fifteen; a geometry fact, not a searched knob).
Per decision C3 the parameterization is direct (``residual_drift`` False) and
guidance stays 1.0. Training seeds are ``systems.train_seed_for("flow", k)`` and
sampling seeds are ``systems.SEED_PLAN`` -- the same seed discipline as WP2.10.

The battery phase reuses ``run_ablation_grid.run_cell`` VERBATIM (same judged
code path as WP2.10); only the checkpoint resolution differs, because
``systems.build``'s pins are the G2-era 12-factor artifacts. The verdict phase
derives every number through ``ah.eval.ablation`` (the sealed arithmetic).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import run_ablation_grid as rag  # noqa: E402
import yaml  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval import ablation as ab  # noqa: E402
from ah.eval import prereg as prereg_mod  # noqa: E402
from ah.eval.battery import register_reference_dependent_suites  # noqa: E402
from ah.eval.reference import compute_reference  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen import systems  # noqa: E402
from ah.gen.blocks import data as bd  # noqa: E402
from ah.gen.blocks import train as tr  # noqa: E402
from ah.gen.blocks.flow import (  # noqa: E402
    FlowBlockSampler,
    FlowConfig,
    HierFlowV1,
    load_checkpoint,
)
from ah.gen.bootstrap import (  # noqa: E402
    CAMPAIGN_VINTAGE_ID,
    CRITERION_MONTHS,
    CRITERION_N_PATHS,
    build_source,
)
from ah.gen.climate.simulate import load_artifact as load_climate  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    DEFAULT_CLIMATE_ARTIFACT,
    DEFAULT_REGIMES_ARTIFACT,
    PINNED_CLIMATE_SHA256,
    PINNED_REGIMES_SHA256,
)
from ah.gen.regimes.semimarkov import load_artifact as load_regimes  # noqa: E402

SPACE = _REPO_ROOT / "configs" / "wp29-flow-search-v1.yaml"
SELECTION = _REPO_ROOT / "experiments" / "l3b-flow-tuning-v1" / "selection.json"
MANIFEST_PATH = _REPO_ROOT / "configs" / "campaign2-checkpoints.json"
CELLS_ROOT = _REPO_ROOT / "experiments" / "campaign2" / "cells"
VERDICT_JSON = _REPO_ROOT / "artifacts" / "campaign2" / "promotion-verdict.json"
BENCHMARK_ID = "bootstrap-v1"
CHALLENGER_ID = "hier-flow-v1"
SEEDS = (0, 1, 2)


def _campaign_dataset(catalog_root: Path):
    manifest = load_manifest()
    with Catalog(catalog_root) as catalog:
        access = rag.catalog_access(catalog, CAMPAIGN_VINTAGE_ID)
        source = build_source(access, manifest, vintage_id=CAMPAIGN_VINTAGE_ID)
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise SystemExit("climate artifact sha != WP2.7 pin; refusing")
    return bd.build_dataset(source, climate)


def phase_train(args: argparse.Namespace) -> None:
    dataset = _campaign_dataset(args.catalog_root)
    n_factors = int(dataset.x.shape[-1])
    print(f"campaign dataset: {dataset.n_train_raw} raw train blocks, {n_factors} factors")

    selection = json.loads(SELECTION.read_text("utf-8"))
    config = FlowConfig(**{**selection["config"], "n_factors": n_factors})
    final_budget = yaml.safe_load(SPACE.read_text("utf-8"))["final"]
    manifest_doc = json.loads(MANIFEST_PATH.read_text("utf-8")) if MANIFEST_PATH.exists() else {}

    for k in SEEDS:
        key = f"flow:{k}"
        out = _REPO_ROOT / "experiments" / f"campaign2-flow-s{k}" / "checkpoint.pt"
        if key in manifest_doc and out.exists():
            print(f"[skip] {key} already trained -> {manifest_doc[key]['checkpoint_hash'][:16]}...")
            continue
        seed = systems.train_seed_for("flow", k)
        print(f"[{key}] training seed {seed} -> {out}", flush=True)
        t0 = time.time()
        result = tr.train_blocks(
            dataset,
            config,
            seed=seed,
            max_steps=int(final_budget["max_steps"]),
            eval_every=int(final_budget["eval_every"]),
            patience=int(final_budget["patience"]),
            device=args.device,
            n_rep_eval=int(final_budget["n_rep_eval"]),
            log=lambda m, _t0=t0: print(f"[{time.time() - _t0:8.1f}s] {m}", flush=True),
        )
        wall = time.time() - t0
        meta = tr.save_checkpoint(
            result,
            dataset,
            out,
            extra_meta={
                "generator_id": CHALLENGER_ID,
                "vintage_id": CAMPAIGN_VINTAGE_ID,
                "seed": seed,
                "seed_index": k,
                "selection": selection,
                "n_factors": n_factors,
                "climate_sha256": PINNED_CLIMATE_SHA256,
                "regimes_sha256": PINNED_REGIMES_SHA256,
                "training_wall_seconds": wall,
                "device": args.device,
                "final_budget": final_budget,
                "created_at": args.created_at,
                "wp": (
                    "campaign-2 promotion training (config = sealed WP2.9 selection; "
                    "n_factors follows the sealed campaign-2 factor set; NOT re-searched; "
                    "C3: residual_drift off, guidance 1.0)"
                ),
            },
        )
        manifest_doc[key] = {
            "family": "flow",
            "seed_index": k,
            "train_seed": seed,
            "checkpoint": out.relative_to(_REPO_ROOT).as_posix(),
            "checkpoint_hash": meta["checkpoint_hash"],
            "config_hash": meta["config_hash"],
            "best_s": result.best_s,
            "best_step": result.best_step,
            "steps_run": result.steps_run,
            "stopped_early": bool(result.stopped_early),
            "wall_seconds": wall,
            "cb_fingerprint": meta["cb_fingerprint"],
            "vintage_id": CAMPAIGN_VINTAGE_ID,
        }
        MANIFEST_PATH.write_text(json.dumps(manifest_doc, indent=2, sort_keys=True) + "\n", "utf-8")
        print(
            f"[{key}] {result.steps_run} steps in {wall:.1f}s "
            f"(best {result.best_step}, early={result.stopped_early}); S {result.best_s:.6f}",
            flush=True,
        )
    print("TRAIN PHASE DONE")


def _build_campaign_flow(seed_index: int, *, block_batch: int, device: str) -> HierFlowV1:
    """hier_flow_v1_factory's assembly against the campaign-2 checkpoint manifest.

    ``systems.build`` resolves the G2-era 12-factor pins (including at seed 0),
    which is exactly what a campaign-2 cell must NOT sample -- hence this builder.
    L1/L2 artifact pins are still enforced; the checkpoint hash is verified
    against the campaign manifest entry.
    """
    manifest_doc = json.loads(MANIFEST_PATH.read_text("utf-8"))
    entry = manifest_doc[f"flow:{seed_index}"]
    path = _REPO_ROOT / entry["checkpoint"]
    model, std, meta = load_checkpoint(path)
    if meta["checkpoint_hash"] != entry["checkpoint_hash"]:
        raise SystemExit(f"checkpoint hash != campaign manifest entry for flow:{seed_index}")
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    regimes = load_regimes(DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise SystemExit("climate artifact sha != WP2.7 pin")
    if regimes.meta["content_sha256"] != PINNED_REGIMES_SHA256:
        raise SystemExit("regimes artifact sha != WP2.7 pin")
    from ah.gen.bootstrap import campaign_source

    source = campaign_source()
    sampler = FlowBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device=device,
        block_batch=block_batch,
    )
    system = HierFlowV1(climate, regimes, source, sampler)
    system.checkpoint_hash = meta["checkpoint_hash"]
    system.config_hash = meta.get("config_hash")
    return system


def phase_battery(args: argparse.Namespace) -> None:
    import torch

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

    # Same judged code path as WP2.10: rag.run_cell verbatim. Only checkpoint
    # RESOLUTION is redirected, via this dispatcher over systems.build.
    real_build = systems.build

    def dispatch(system_id: str, *, seed_index: int = 0):
        if system_id == CHALLENGER_ID:
            return _build_campaign_flow(
                seed_index, block_batch=args.block_batch, device=args.sampler_device
            )
        return real_build(system_id, seed_index=seed_index)

    rag.systems.build = dispatch
    try:
        manifest = load_manifest()
        prereg = prereg_mod.load(_REPO_ROOT / "pre-registration.yaml")
        with Catalog(args.catalog_root) as catalog:
            access = rag.catalog_access(catalog, CAMPAIGN_VINTAGE_ID)
            build_source(access, manifest, vintage_id=CAMPAIGN_VINTAGE_ID)  # span assertion
            print("computing reference (sealed parameters)...", flush=True)
            # The FULL sealed parameter set, exactly as run_ablation_grid passes it.
            # An earlier run omitted resample_length: the default (None) draws
            # full-sample-length bands where the sealed battery is length-matched
            # at the judged path length, and BOTH sides' band-exceedance gates
            # explode against bands measuring a different quantity (the bootstrap
            # itself "failing" at 0.91 was the tell). criterion_bearing does not
            # check reference parameters -- recorded in the promotion evidence.
            reference = compute_reference(
                access,
                manifest,
                vintage_id=CAMPAIGN_VINTAGE_ID,
                seed=rag.REFERENCE_SEED,
                n_resamples=rag.N_RESAMPLES,
                level=rag.LEVEL,
                block_length=rag.BLOCK_LENGTH,
                resample_length=args.months,
            )
            register_reference_dependent_suites(manifest, reference)
            CELLS_ROOT.mkdir(parents=True, exist_ok=True)
            rag.dump_historical_strategy_returns(
                reference, CELLS_ROOT.parent / "historical-strategy-returns.json"
            )

            cells = [
                rag.Cell(
                    letter="B" if system_id == BENCHMARK_ID else "F",
                    system_id=system_id,
                    seed_index=seed.index,
                    sample_seed=seed.sample_seed,
                    train_seed=(
                        systems.train_seed_for("flow", seed.index)
                        if system_id == CHALLENGER_ID
                        else None
                    ),
                    neural=system_id == CHALLENGER_ID,
                    family="flow" if system_id == CHALLENGER_ID else None,
                )
                for system_id in (BENCHMARK_ID, CHALLENGER_ID)
                for seed in systems.SEED_PLAN
            ]
            for cell in cells:
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


def phase_verdict(args: argparse.Namespace) -> None:
    """The sealed multi_seed_decision_rule, composed exactly as
    scripts/build_ablation_report.py composes it (same ab.* calls, same NaN rule,
    same pooled inequality)."""
    import yaml as _yaml

    doc = _yaml.safe_load((_REPO_ROOT / "pre-registration.yaml").read_text("utf-8"))
    d4_ids = tuple(doc["d4_strategies"])
    uncomputable = tuple(doc["reference_run"]["uncomputable_d4_strategies"])

    def load_cell(system_id: str, seed_index: int) -> tuple[dict, dict]:
        for slug_dir in sorted(CELLS_ROOT.iterdir()):
            summary = json.loads((slug_dir / "summary.json").read_text("utf-8"))
            if summary["system_id"] == system_id and summary["seed_index"] == seed_index:
                report = json.loads((slug_dir / "battery.json").read_text("utf-8"))
                report = {
                    **report,
                    "n_paths": summary["n_paths"],
                    "months": summary["months"],
                }
                return summary, report
        raise SystemExit(f"no cell artifact for {system_id} seed {seed_index}")

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
                expected_vintage_id=CAMPAIGN_VINTAGE_ID,
            ),
        }

    per_seed, diffs = [], []
    for k in SEEDS:
        _b_summary, b_report = load_cell(BENCHMARK_ID, k)
        c_summary, c_report = load_cell(CHALLENGER_ID, k)
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
    pooled = ab.pooled_difference(diffs)
    every_seed = all(r["beats_this_seed"] for r in per_seed)
    clause_ii_every = all(r["clause_ii_no_regression"] for r in per_seed)
    pooled_route = bool(pooled.get("beats") and clause_ii_every)
    verdict = "PROMOTE" if (every_seed or pooled_route) else "SHIP-BENCHMARK"
    record = {
        "verdict": verdict,
        "route": "per-seed" if every_seed else ("pooled" if pooled_route else "neither"),
        "rule": "pre-registration.yaml multi_seed_decision_rule (sealed)",
        "benchmark": BENCHMARK_ID,
        "challenger": CHALLENGER_ID + " (campaign-2 checkpoints)",
        "vintage_id": CAMPAIGN_VINTAGE_ID,
        "comparison_strategies": [sid for sid in d4_ids if sid not in uncomputable],
        "per_seed": per_seed,
        "pooled": pooled,
        "benchmark_draw_span_bias_disclosure": (
            "multi_seed_decision_rule.benchmark_draw_span_bias applies verbatim; the "
            "restricted comparison is generated by scripts/build_ablation_report.py "
            "machinery for the evidence doc"
        ),
        "created_at": args.created_at,
    }
    VERDICT_JSON.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_JSON.write_text(json.dumps(record, indent=1, default=str) + "\n", "utf-8")
    print(json.dumps(record, indent=1, default=str))
    print(f"VERDICT -> {VERDICT_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("train", "battery", "verdict"))
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--sampler-device", default="cuda")
    parser.add_argument("--block-batch", type=int, default=128)
    parser.add_argument("--n-paths", type=int, default=CRITERION_N_PATHS)
    parser.add_argument("--months", type=int, default=CRITERION_MONTHS)
    parser.add_argument("--created-at", default="2026-08-02")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    {"train": phase_train, "battery": phase_battery, "verdict": phase_verdict}[args.phase](args)


if __name__ == "__main__":
    main()
