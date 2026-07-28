"""WP2.8: train the SELECTED config to early-stopping convergence (the primary
checkpoint), measure GPU determinism, and produce the monthly-tier neighborhood
comparison on the validation folds.

Runs AFTER scripts/run_blocks_tuning.py has written experiments/
l3a-diffusion-tuning-v1/selection.json (the sealed selection). The final budget
(max_steps/eval_every/patience) comes from the committed search-space file's
`final:` block — a budget, not a searched hyperparameter.

The neighborhood check is EVIDENCE, NOT A SEALED GATE (STEP2 Sec.WP2.8
acceptance wording): generated blocks conditioned on each validation fold's
conditioning vectors are compared to the fold's actual blocks on LOCAL numpy
statistics (skew, excess kurtosis, lag-1/lag-2 within-block ACF, cross-factor
correlation) — local implementations, no ah.eval import.

Usage::

    uv run python -u scripts/train_blocks_final.py --device cuda \
        --created-at 2026-07-27

Determinism: the final seed is the committed `final.seed`; the plan-Sec.1
determinism block applies; a 200-step repeat-run measures same-device GPU
bit-determinism and the result is recorded in the checkpoint meta.
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

import torch  # noqa: E402
from run_blocks_tuning import DEFAULT_SPACE, EXP_ID, build_campaign_dataset  # noqa: E402

from ah.experiment import ExperimentStore  # noqa: E402
from ah.gen.blocks import constraints as ct  # noqa: E402
from ah.gen.blocks import losses as ls  # noqa: E402
from ah.gen.blocks import train as tr  # noqa: E402
from ah.gen.blocks import tuning as tu  # noqa: E402
from ah.gen.blocks.diffusion import DiffusionConfig, sample_heun  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    PINNED_CLIMATE_SHA256,
    PINNED_REGIMES_SHA256,
)

FINAL_EXP_ID = "l3a-diffusion-final"

# ---------------------------------------------------------------- local stats #


def _skew(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    sd = float(np.std(x))
    return float(np.mean(((x - x.mean()) / sd) ** 3)) if sd > 0 else float("nan")


def _exkurt(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    sd = float(np.std(x))
    return float(np.mean(((x - x.mean()) / sd) ** 4) - 3.0) if sd > 0 else float("nan")


def _acf_within_blocks(blocks: np.ndarray, lag: int) -> float:
    """Pooled within-block lag-`lag` autocorrelation over (B, L) series."""
    a = blocks[:, :-lag].reshape(-1)
    b = blocks[:, lag:].reshape(-1)
    sa, sb = np.std(a), np.std(b)
    if sa == 0 or sb == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def neighborhood_table(
    gen_units: np.ndarray, real_units: np.ndarray, factor_names: tuple[str, ...]
) -> dict:
    """Local monthly statistics, generated vs actual validation blocks."""
    per_factor = {}
    for j, name in enumerate(factor_names):
        g, r = gen_units[:, :, j], real_units[:, :, j]
        per_factor[name] = {
            "skew": {"gen": _skew(g.reshape(-1)), "real": _skew(r.reshape(-1))},
            "excess_kurtosis": {"gen": _exkurt(g.reshape(-1)), "real": _exkurt(r.reshape(-1))},
            "acf_1": {"gen": _acf_within_blocks(g, 1), "real": _acf_within_blocks(r, 1)},
            "acf_2": {"gen": _acf_within_blocks(g, 2), "real": _acf_within_blocks(r, 2)},
        }

    # cross-factor correlation over pooled cells + mean |gen - real| distance
    def corr(mat: np.ndarray) -> np.ndarray:
        flat = mat.reshape(-1, mat.shape[-1])
        return np.corrcoef(flat, rowvar=False)

    cg, cr = corr(gen_units), corr(real_units)
    iu = np.triu_indices(len(factor_names), k=1)
    return {
        "per_factor": per_factor,
        "cross_corr_mean_abs_gap": float(np.nanmean(np.abs(cg[iu] - cr[iu]))),
        "cross_corr_max_abs_gap": float(np.nanmax(np.abs(cg[iu] - cr[iu]))),
    }


def render_table(doc: dict, factor_names: tuple[str, ...]) -> str:
    lines = [
        "| factor | skew gen/real | exkurt gen/real | acf1 gen/real | acf2 gen/real |",
        "|---|---|---|---|---|",
    ]
    for name in factor_names:
        row = doc["per_factor"][name]

        def pair(stat: str, row: dict = row) -> str:
            return f"{row[stat]['gen']:+.3f} / {row[stat]['real']:+.3f}"

        lines.append(
            f"| {name} | {pair('skew')} | {pair('excess_kurtosis')} | "
            f"{pair('acf_1')} | {pair('acf_2')} |"
        )
    lines.append("")
    lines.append(
        f"cross-factor corr gap (pooled cells): mean abs "
        f"{doc['cross_corr_mean_abs_gap']:.4f}, max abs {doc['cross_corr_max_abs_gap']:.4f}"
    )
    return "\n".join(lines)


# -------------------------------------------------------------------- driver #


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--skip-determinism-check", action="store_true")
    args = parser.parse_args()

    _space, _budget, space_sha = tu.load_search_space(DEFAULT_SPACE)
    import yaml

    final_budget = yaml.safe_load(DEFAULT_SPACE.read_text("utf-8"))["final"]

    tuning_dir = _REPO_ROOT / "experiments" / EXP_ID
    selection = json.loads((tuning_dir / "selection.json").read_text("utf-8"))
    config = DiffusionConfig(**selection["config"])
    print(f"selected config {selection['config_hash']} (search space sha {space_sha})")
    print(
        f"selected S {selection['s_value']:.6f} = gen {selection['gen_term']:.6f} "
        f"+ 1.0 * aux {selection['aux_term']:.6f}"
    )

    dataset = build_campaign_dataset(args.catalog_root, args.vintage)
    seed = int(final_budget["seed"])

    # -- same-device GPU determinism measurement (200 steps, twice) ---------- #
    determinism_record: dict = {"checked": False}
    if not args.skip_determinism_check:
        print("measuring same-device bit-determinism (200 steps x 2)...")
        hashes = []
        for _ in range(2):
            r = tr.train_diffusion(
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

    # -- final training ------------------------------------------------------ #
    t0 = time.time()
    result = tr.train_diffusion(
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

    # -- checkpoint ---------------------------------------------------------- #
    exp_dir = _REPO_ROOT / "experiments" / FINAL_EXP_ID
    meta = tr.save_checkpoint(
        result,
        dataset,
        exp_dir / "checkpoint.pt",
        extra_meta={
            "generator_id": "hier-diffusion-v1",
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
        },
    )
    store = ExperimentStore(_REPO_ROOT / "experiments")
    if not store.exists(FINAL_EXP_ID):
        store.create(
            FINAL_EXP_ID,
            {"purpose": "wp2.8 final hier-diffusion-v1 training", **config.as_dict()},
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

    # -- neighborhood comparison (evidence, not a gate) ---------------------- #
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
            z = sample_heun(
                model,
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
        "# WP2.8 monthly-tier neighborhood check (validation folds)\n\n"
        "EVIDENCE, NOT A SEALED GATE. Local numpy statistics of generated blocks\n"
        f"(n={gen_units.shape[0]}, {n_rep} per conditioning vector, NFE "
        f"{config.eval_nfe}) vs the actual validation blocks "
        f"(n={real_units.shape[0]}).\n\n" + render_table(table, dataset.factor_names) + "\n"
    )
    (exp_dir / "neighborhood.md").write_text(md, "utf-8")
    print(md)
    print(f"wrote {exp_dir / 'neighborhood.md'}")
    print("\nPIN THIS in src/ah/gen/blocks/diffusion.py:")
    print(f'PINNED_CHECKPOINT_SHA256 = "{result.checkpoint_hash}"')


if __name__ == "__main__":
    main()
