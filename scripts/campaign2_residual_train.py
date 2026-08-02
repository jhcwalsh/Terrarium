"""Campaign-2 A': retrain the sealed flow config under the residual
parameterization and score the four acceptance statistics.

Run:  uv run python -u scripts/campaign2_residual_train.py --created-at DATE

NON-CRITERION-BEARING measurement, decided by the owner's recorded escalation
(campaign2-regime-fix-options memo: B' missed, A' fires). NOT tuning: the config
is the committed WP2.9 flow selection with exactly ONE change — the A'
``residual_drift`` flag — the training seed is the WP2.10 seed-index-1 seed (the
same slot the B' baseline checkpoint occupies), and the final budget comes from
the committed search-space file. The campaign promotion seal will pre-state the
parameterization; this run measures whether it recovers persistence.

Scores each ensemble on the same eight target metrics as the B' sweep
(campaign2_guidance_sweep.py), at guidance 1.0 and — per the B' secondary
finding — 2.0. History anchors: long-inflation-era freq 1.000, half-life 61.2,
lost-decade ~0.00-0.05, equity drawdown depth 0.069.
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

import yaml  # noqa: E402
from run_blocks_tuning import catalog_access  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval.metrics.horizon import build_horizon_suite  # noqa: E402
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
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID, build_source, campaign_source  # noqa: E402
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
OUT_CKPT = _REPO_ROOT / "experiments" / "campaign2-residual" / "checkpoint.pt"
OUT_JSON = _REPO_ROOT / "artifacts" / "campaign2" / "residual-acceptance.json"
TARGET_SUBSTRINGS = (
    "cpi.long_inflation_era",
    "cpi.mean_reversion_halflife",
    "lost_decade",
    "equity_mkt.drawdown_median_depth",
)
HISTORY_ANCHORS = {
    "long_inflation_era_frequency": 1.000,
    "inflation_half_life": 61.2,
    "stagnant_decade_frequency": "0.00-0.05",
    "equity_drawdown_median_depth": 0.069,
}


def train(args: argparse.Namespace) -> dict:
    manifest = load_manifest()
    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        source = build_source(access, manifest, vintage_id=args.vintage)
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise SystemExit("climate artifact sha != WP2.7 pin; refusing")
    dataset = bd.build_dataset(source, climate, residual_drift=True)
    print(
        f"dataset: {dataset.n_train_raw} raw train blocks, residual_drift=True",
        flush=True,
    )

    selection = json.loads(SELECTION.read_text("utf-8"))
    config = FlowConfig(**{**selection["config"], "residual_drift": True})
    final_budget = yaml.safe_load(SPACE.read_text("utf-8"))["final"]
    seed = systems.train_seed_for("flow", 1)
    print(f"training sealed-selection config + residual_drift, seed {seed}", flush=True)

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
        OUT_CKPT,
        extra_meta={
            "generator_id": "hier-flow-v1",
            "vintage_id": args.vintage,
            "seed": seed,
            "seed_index": 1,
            "selection": selection,
            "climate_sha256": PINNED_CLIMATE_SHA256,
            "regimes_sha256": PINNED_REGIMES_SHA256,
            "training_wall_seconds": wall,
            "device": args.device,
            "final_budget": final_budget,
            "created_at": args.created_at,
            "wp": "campaign-2 A' residual parameterization (non-criterion-bearing measurement)",
        },
    )
    print(
        f"trained: {result.steps_run} steps in {wall:.1f}s, best step {result.best_step}, "
        f"S {result.best_s:.6f}; checkpoint {meta['checkpoint_hash'][:16]}...",
        flush=True,
    )
    return meta


def build_system() -> HierFlowV1:
    """hier_flow_v1_factory's assembly, pointed at the A' checkpoint (its hash is
    not the WP2.9 pin — that is the point); L1/L2 artifact pins still enforced."""
    model, std, meta = load_checkpoint(OUT_CKPT)
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    regimes = load_regimes(DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise SystemExit("climate artifact sha != WP2.7 pin")
    if regimes.meta["content_sha256"] != PINNED_REGIMES_SHA256:
        raise SystemExit("regimes artifact sha != WP2.7 pin")
    source = campaign_source()
    sampler = FlowBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device="cpu",
        block_batch=1,
    )
    system = HierFlowV1(climate, regimes, source, sampler)
    system.checkpoint_hash = meta["checkpoint_hash"]
    return system


def measure(args: argparse.Namespace, checkpoint_meta: dict) -> None:
    manifest = load_manifest()
    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        reference = compute_reference(access, manifest, vintage_id=args.vintage, seed=20260802)
    suite = build_horizon_suite(manifest, reference)
    targets = [s for s in suite if any(sub in s.name for sub in TARGET_SUBSTRINGS)]
    print(f"target metrics ({len(targets)}):", [s.name for s in targets], flush=True)

    rows = []
    for g in (1.0, 2.0):
        t0 = time.time()
        system = build_system()
        system._sampler.guidance_scale = float(g)
        ens = system.sample_months(args.months, args.n_paths, args.sample_seed)
        row: dict[str, object] = {"guidance": g, "assemble_s": round(time.time() - t0, 1)}
        for spec in targets:
            try:
                row[spec.name] = float(spec.fn(ens))
            except Exception as exc:
                row[spec.name] = f"error: {type(exc).__name__}"
        rows.append(row)
        print(f"guidance {g}: {row}", flush=True)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "non_criterion_bearing": True,
        "purpose": "A' residual parameterization vs the four acceptance statistics",
        "checkpoint_hash": checkpoint_meta["checkpoint_hash"],
        "config_hash": checkpoint_meta["config_hash"],
        "baseline": "artifacts/campaign2/guidance-sweep-results.json (B' rows, same seed/paths)",
        "history_anchors": HISTORY_ANCHORS,
        "n_paths": args.n_paths,
        "months": args.months,
        "sample_seed": args.sample_seed,
        "created_at": args.created_at,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"A' MEASUREMENT DONE -> {OUT_JSON}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--n-paths", type=int, default=512)
    parser.add_argument("--months", type=int, default=120)
    parser.add_argument("--sample-seed", type=int, default=20260802)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()

    if args.skip_train and OUT_CKPT.exists():
        import torch

        meta = torch.load(OUT_CKPT, map_location="cpu", weights_only=False)["meta"]
    else:
        meta = train(args)
    measure(args, meta)


if __name__ == "__main__":
    main()
