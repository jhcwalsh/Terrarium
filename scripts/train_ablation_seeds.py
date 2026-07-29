"""WP2.10: retrain each L3 family's ALREADY-SELECTED config at further seeds.

The sealed tuning budget is spent. This is **not** tuning and must never become
tuning: the config is read from the family's committed ``selection.json``, the
final budget from its committed search-space file, and the ONLY thing that varies
across runs is the training seed (``ah.gen.systems.train_seed_for``). No search,
no re-selection, no early-stopping-criterion change — the same discipline
``pre-registration.yaml``'s ``severe_test_protocol`` pins for WP2.11's refits.

Writes ``experiments/<family>-final-s<index>/checkpoint.pt`` and appends the
checkpoint's weight SHA-256 to ``configs/wp210-seed-checkpoints.json``, which is
what :func:`ah.gen.systems.build` verifies against. A checkpoint with no manifest
entry cannot be loaded by the grid, which is the point.

Usage (one GPU job at a time -- never concurrently with the grid)::

    uv run python -u scripts/train_ablation_seeds.py --device cuda \
        --created-at 2026-07-28 --indices 1 2
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

import torch  # noqa: E402
import yaml  # noqa: E402

from ah.gen import systems  # noqa: E402
from ah.gen.blocks import train as tr  # noqa: E402
from ah.gen.blocks import tuning as tu  # noqa: E402
from ah.gen.blocks.diffusion import DiffusionConfig  # noqa: E402
from ah.gen.blocks.flow import FlowConfig  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    PINNED_CLIMATE_SHA256,
    PINNED_REGIMES_SHA256,
)

FAMILIES = {
    "diffusion": {
        "config_cls": DiffusionConfig,
        "tuning_exp": "l3a-diffusion-tuning-v1",
        "space": _REPO_ROOT / "configs" / "wp28-diffusion-search-v1.yaml",
        "exp_prefix": "l3a-diffusion-final",
    },
    "flow": {
        "config_cls": FlowConfig,
        "tuning_exp": "l3b-flow-tuning-v1",
        "space": _REPO_ROOT / "configs" / "wp29-flow-search-v1.yaml",
        "exp_prefix": "l3b-flow-final",
    },
}


def _dataset(catalog_root: Path, vintage: str):
    """The campaign block dataset, built exactly as WP2.8/2.9 built it.

    Imported lazily from the tuning driver so 'same data' is a fact rather than a
    reimplementation (WP2.9 verified the two arms' datasets are byte-identical).
    """
    from run_blocks_tuning import build_campaign_dataset

    return build_campaign_dataset(catalog_root, vintage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--indices", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--families", nargs="+", default=["diffusion", "flow"])
    args = parser.parse_args()

    torch.use_deterministic_algorithms(True)
    manifest_path = systems.seed_checkpoint_manifest_path()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}

    dataset = _dataset(args.catalog_root, args.vintage)
    print(
        f"dataset: {dataset.n_train_raw} raw train blocks, "
        f"{dataset.n_train_effective} effective/epoch",
        flush=True,
    )

    for family in args.families:
        spec = FAMILIES[family]
        _space, _budget, space_sha = tu.load_search_space(spec["space"], spec["config_cls"])
        final_budget = yaml.safe_load(Path(spec["space"]).read_text("utf-8"))["final"]
        selection = json.loads(
            (_REPO_ROOT / "experiments" / spec["tuning_exp"] / "selection.json").read_text("utf-8")
        )
        config = spec["config_cls"](**selection["config"])
        print(
            f"\n=== {family}: selected config {selection['config_hash']} "
            f"(space sha {space_sha[:12]}) ===",
            flush=True,
        )

        for index in args.indices:
            key = f"{family}:{index}"
            seed = systems.train_seed_for(family, index)
            exp_id = f"{spec['exp_prefix']}-s{index}"
            out = _REPO_ROOT / "experiments" / exp_id / "checkpoint.pt"
            if key in manifest and out.exists():
                print(f"[skip] {key} already trained -> {manifest[key]['checkpoint_hash'][:16]}...")
                continue

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
                    "generator_id": {
                        "diffusion": "hier-diffusion-v1",
                        "flow": "hier-flow-v1",
                    }[family],
                    "vintage_id": args.vintage,
                    "seed": seed,
                    "seed_index": index,
                    "selection": selection,
                    "search_space_sha256": space_sha,
                    "climate_sha256": PINNED_CLIMATE_SHA256,
                    "regimes_sha256": PINNED_REGIMES_SHA256,
                    "training_wall_seconds": wall,
                    "device": args.device,
                    "final_budget": final_budget,
                    "created_at": args.created_at,
                    "wp": "2.10 additional training seed (config NOT re-searched)",
                    "n_train_raw_blocks": dataset.n_train_raw,
                    "n_train_effective_per_epoch": dataset.n_train_effective,
                },
            )
            print(
                f"[{key}] {result.steps_run} steps in {wall:.1f}s "
                f"(best step {result.best_step}, early={result.stopped_early}); "
                f"S {result.best_s:.6f} = gen {result.best_gen_term:.6f} + 1.0 * "
                f"aux {result.best_aux_term:.6f}",
                flush=True,
            )
            manifest[key] = {
                "family": family,
                "seed_index": index,
                "train_seed": seed,
                "checkpoint": out.relative_to(_REPO_ROOT).as_posix(),
                "checkpoint_hash": meta["checkpoint_hash"],
                "config_hash": meta["config_hash"],
                "best_s": result.best_s,
                "best_gen_term": result.best_gen_term,
                "best_aux_term": result.best_aux_term,
                "best_step": result.best_step,
                "steps_run": result.steps_run,
                "stopped_early": bool(result.stopped_early),
                "wall_seconds": wall,
                "cb_fingerprint": meta["cb_fingerprint"],
            }
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8")
            print(f"[{key}] wrote {manifest_path}", flush=True)

    print("\nseed-checkpoint manifest:")
    for key in sorted(manifest):
        e = manifest[key]
        print(
            f"  {key:14s} seed {e['train_seed']}  {e['checkpoint_hash'][:16]}...  S {e['best_s']:.6f}"
        )


if __name__ == "__main__":
    main()
