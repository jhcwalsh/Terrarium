"""WP2.9: train the SELECTED flow config to early-stopping convergence.

Runs AFTER scripts/run_flow_tuning.py has written
experiments/l3b-flow-tuning-v1/selection.json (the sealed selection). The final
budget (max_steps/eval_every/patience) comes from the committed search-space
file's `final:` block — a budget, not a searched hyperparameter.

Everything here is WP2.8's train_blocks_final.py with the config class swapped:
the same trainer, the same determinism measurement, the same neighborhood table
(local numpy statistics, no ah.eval import), the same checkpoint identity. The
neighborhood check is EVIDENCE, NOT A SEALED GATE.

Usage::

    uv run python -u scripts/train_flow_final.py --device cuda --created-at 2026-07-28
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import torch  # noqa: E402
from run_flow_tuning import (  # noqa: E402
    DEFAULT_SPACE,
    EXP_ID,
    build_dataset_waiting_for_catalog,
)
from train_blocks_final import neighborhood_table, render_table  # noqa: E402

from ah.experiment import ExperimentStore  # noqa: E402
from ah.gen.blocks import constraints as ct  # noqa: E402
from ah.gen.blocks import losses as ls  # noqa: E402
from ah.gen.blocks import train as tr  # noqa: E402
from ah.gen.blocks import tuning as tu  # noqa: E402
from ah.gen.blocks.flow import FlowConfig  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    PINNED_CLIMATE_SHA256,
    PINNED_REGIMES_SHA256,
)

FINAL_EXP_ID = "l3b-flow-final"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--skip-determinism-check", action="store_true")
    args = parser.parse_args()

    _space, _budget, space_sha = tu.load_search_space(DEFAULT_SPACE, FlowConfig)
    import yaml

    final_budget = yaml.safe_load(DEFAULT_SPACE.read_text("utf-8"))["final"]

    tuning_dir = _REPO_ROOT / "experiments" / EXP_ID
    selection = json.loads((tuning_dir / "selection.json").read_text("utf-8"))
    config = FlowConfig(**selection["config"])
    print(f"selected config {selection['config_hash']} (search space sha {space_sha})")
    print(
        f"selected S {selection['s_value']:.6f} = gen {selection['gen_term']:.6f} "
        f"+ 1.0 * aux {selection['aux_term']:.6f}"
    )
    print(f"solver {config.solver}, eval_nfe {config.eval_nfe}, true NFE {config.sampling_nfe}")

    dataset = build_dataset_waiting_for_catalog(args.catalog_root, args.vintage)
    seed = int(final_budget["seed"])

    determinism_record: dict = {"checked": False}
    if not args.skip_determinism_check:
        print("measuring same-device bit-determinism (200 steps x 2)...")
        hashes = []
        for _ in range(2):
            r = tr.train_blocks(
                dataset,
                config,
                seed=seed,
                max_steps=200,
                eval_every=200,
                patience=99,
                device=args.device,
                n_rep_eval=2,
            )
            hashes.append(r.checkpoint_hash)
        determinism_record = {
            "checked": True,
            "device": args.device,
            "steps": 200,
            "bit_identical": hashes[0] == hashes[1],
            "hashes": hashes,
        }
        print(f"determinism: {determinism_record}")
        if not determinism_record["bit_identical"]:
            raise SystemExit(
                "GPU training run is NOT bit-deterministic; investigate before the "
                "final run (the plan forbids waving this away)"
            )

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
        log=lambda m: print(f"[{time.time() - t0:8.1f}s] {m}", flush=True),
    )
    wall = time.time() - t0
    gpu_mem = float(torch.cuda.max_memory_allocated() / 2**20) if args.device == "cuda" else None
    print(
        f"final training: {result.steps_run} steps in {wall:.1f}s "
        f"(best step {result.best_step}, stopped_early={result.stopped_early}, "
        f"peak GPU mem {gpu_mem and f'{gpu_mem:.0f} MiB'})"
    )
    print(
        f"best S {result.best_s:.6f} = gen {result.best_gen_term:.6f} "
        f"+ 1.0 * aux {result.best_aux_term:.6f}"
    )

    exp_dir = _REPO_ROOT / "experiments" / FINAL_EXP_ID
    meta = tr.save_checkpoint(
        result,
        dataset,
        exp_dir / "checkpoint.pt",
        extra_meta={
            "generator_id": "hier-flow-v1",
            "vintage_id": args.vintage,
            "seed": seed,
            "selection": selection,
            "search_space_sha256": space_sha,
            "climate_sha256": PINNED_CLIMATE_SHA256,
            "regimes_sha256": PINNED_REGIMES_SHA256,
            "training_wall_seconds": wall,
            "peak_gpu_mem_mib": gpu_mem,
            "device": args.device,
            "determinism": determinism_record,
            "final_budget": final_budget,
            "created_at": args.created_at,
            "n_train_raw_blocks": dataset.n_train_raw,
            "n_train_effective_per_epoch": dataset.n_train_effective,
            "sampling_nfe": int(config.sampling_nfe),
            "solver": config.solver,
        },
    )
    store = ExperimentStore(_REPO_ROOT / "experiments")
    if not store.exists(FINAL_EXP_ID):
        store.create(
            FINAL_EXP_ID,
            {"purpose": "wp2.9 final hier-flow-v1 training", **config.as_dict()},
            seed=seed,
            vintage_id=args.vintage,
            created_at=args.created_at,
        )
    store.record_metrics(
        FINAL_EXP_ID,
        {
            "checkpoint_hash": result.checkpoint_hash,
            "best_s": result.best_s,
            "gen_term": result.best_gen_term,
            "aux_term": result.best_aux_term,
            "per_fold_gen": result.per_fold_gen,
            "per_fold_aux": result.per_fold_aux,
            "steps_run": result.steps_run,
            "wall_seconds": wall,
        },
    )
    print(f"checkpoint {result.checkpoint_hash}")
    print(f"cb fingerprint {meta['cb_fingerprint']}")

    print("building the monthly-tier neighborhood comparison (validation folds)...")
    model = result.model.to(args.device).eval()
    _compiled, excluded = ls.compile_block_strategies(dataset.factor_names, dataset.block_months)
    gen_all, real_all = [], []
    n_rep = 16
    for k in range(len(dataset.fold_indices)):
        cond = torch.as_tensor(
            dataset.fold_cond_standardized(k), dtype=torch.float32, device=args.device
        )
        rng = np.random.Generator(np.random.PCG64(515_000 + k))
        noise = rng.standard_normal((n_rep * cond.shape[0], config.block_months, config.n_factors))
        with torch.no_grad():
            z = model.sample(
                cond.repeat(n_rep, 1),
                torch.as_tensor(noise, dtype=torch.float32, device=args.device),
                int(config.eval_nfe),
            )
        gen_all.append(
            ct.panel_to_constrained(
                dataset.standardization.destandardize_x(z.double().cpu().numpy()),
                dataset.factor_names,
            )
        )
        real_all.append(dataset.fold_x_units(k))
    gen_units = np.concatenate(gen_all)
    real_units = np.concatenate(real_all)
    table = neighborhood_table(gen_units, real_units, dataset.factor_names)
    table["n_gen_blocks"] = int(gen_units.shape[0])
    table["n_real_blocks"] = int(real_units.shape[0])
    table["excluded_strategies"] = excluded
    (exp_dir / "neighborhood.json").write_text(
        json.dumps(table, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    md = (
        "# WP2.9 monthly-tier neighborhood check (validation folds, hier-flow-v1)\n\n"
        "EVIDENCE, NOT A SEALED GATE. Local numpy statistics of generated blocks\n"
        f"(n={gen_units.shape[0]}, {n_rep} per conditioning vector, solver "
        f"{config.solver}, NFE {config.sampling_nfe}) vs the actual validation blocks "
        f"(n={real_units.shape[0]}).\n\n" + render_table(table, dataset.factor_names) + "\n"
    )
    (exp_dir / "neighborhood.md").write_text(md, "utf-8")
    print(md)
    print(f"wrote {exp_dir / 'neighborhood.md'}")
    print("\nPIN THIS in src/ah/gen/blocks/flow.py:")
    print(f'PINNED_CHECKPOINT_SHA256 = "{result.checkpoint_hash}"')


if __name__ == "__main__":
    main()
