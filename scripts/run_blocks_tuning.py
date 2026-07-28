"""WP2.8: run the SEALED tuning search for hier-diffusion-v1 (GPU).

The protocol is pre-registration.yaml `tuning_protocol` (binding): <= 40 distinct
started configs, every trial (crashes included) logged with config hash, git SHA,
seed and per-fold validation scores to experiments/<exp_id>/tuning-log.jsonl;
selection by the sealed S = mean_folds(gen) + 1.0 * mean_folds(aux), NFE
tie-break. The search space was stated in advance in
configs/wp28-diffusion-search-v1.yaml, whose SHA-256 is recorded in the log
header before the first trial.

Usage (offline; local catalog + fitted artifacts, no network)::

    uv run python -u scripts/run_blocks_tuning.py --device cuda \
        --created-at 2026-07-27

Determinism: the trial list is a PCG64(seed) draw from the stated space; each
trial trains under the plan-Sec.1 determinism block with its own logged seed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.data.catalog import Catalog  # noqa: E402
from ah.experiment import ExperimentStore  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen.blocks import data as bd  # noqa: E402
from ah.gen.blocks import tuning as tu  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID, build_source  # noqa: E402
from ah.gen.climate.simulate import load_artifact as load_climate  # noqa: E402
from ah.gen.joinery.assemble import (  # noqa: E402
    DEFAULT_CLIMATE_ARTIFACT,
    PINNED_CLIMATE_SHA256,
)
from ah.splits import DataAccess  # noqa: E402

DEFAULT_SPACE = _REPO_ROOT / "configs" / "wp28-diffusion-search-v1.yaml"
EXP_ID = "l3a-diffusion-tuning-v1"


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def build_campaign_dataset(catalog_root: Path, vintage: str) -> bd.BlockDataset:
    manifest = load_manifest()
    with Catalog(catalog_root) as catalog:
        access = catalog_access(catalog, vintage)
        source = build_source(access, manifest, vintage_id=vintage)
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise SystemExit("climate artifact sha != WP2.7 pin; refusing to build the dataset")
    return bd.build_dataset(source, climate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--space", type=Path, default=DEFAULT_SPACE)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--exp-id", default=EXP_ID)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()

    space, budget, space_sha = tu.load_search_space(args.space)
    print(f"search space {args.space.name} sha256 {space_sha}")
    print(f"budget params: {budget}")

    t0 = time.time()
    dataset = build_campaign_dataset(args.catalog_root, args.vintage)
    print(
        f"dataset: {dataset.x.shape[0]} raw blocks ({dataset.n_train_raw} train raw, "
        f"~{dataset.n_train_effective} effective/epoch, "
        f"folds {[int(f.size) for f in dataset.fold_indices]}, "
        f"{dataset.n_dropped_straddling} straddling dropped) "
        f"[{time.time() - t0:.1f}s]"
    )

    exp_dir = _REPO_ROOT / "experiments" / args.exp_id
    store = ExperimentStore(_REPO_ROOT / "experiments")
    if not store.exists(args.exp_id):
        store.create(
            args.exp_id,
            {
                "purpose": "wp2.8 sealed tuning search (hier-diffusion-v1)",
                "search_space_file": str(args.space.name),
                "search_space_sha256": space_sha,
                "budget_params": budget,
                "vintage_id": args.vintage,
            },
            seed=int(budget["seed"]),
            vintage_id=args.vintage,
            created_at=args.created_at,
        )

    configs = tu.sample_trial_configs(space, int(budget["n_trials"]), seed=int(budget["seed"]))
    print(f"drawn {len(configs)} distinct candidate configs (sealed budget {tu.TRIAL_BUDGET})")

    t_search = time.time()
    entries = tu.run_search(
        dataset,
        configs,
        exp_dir=exp_dir,
        seed=int(budget["seed"]),
        trial_max_steps=int(budget["trial_max_steps"]),
        trial_eval_every=int(budget["trial_eval_every"]),
        trial_patience=int(budget["trial_patience"]),
        device=args.device,
        n_rep_eval=int(budget["n_rep_eval"]),
        space_sha256=space_sha,
        log=lambda m: print(f"[{time.time() - t_search:8.1f}s] {m}", flush=True),
    )

    selection = tu.select_config(entries, n_folds=len(dataset.fold_indices))
    tu.mark_selected(exp_dir, selection)
    (exp_dir / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    print("\n=== SELECTION (sealed criterion) ===")
    print(f"config_hash      {selection['config_hash']}")
    print(f"S                {selection['s_value']:.6f}")
    print(f"  gen_term       {selection['gen_term']:.6f}")
    print(f"  aux_term       {selection['aux_term']:.6f}  (selection_lambda 1.0, PINNED)")
    print(f"eval NFE         {selection['eval_nfe']}")
    print(
        f"trials           {selection['n_trials_started']} started / "
        f"{selection['n_trials_completed']} completed / budget {selection['trial_budget']}"
    )
    print(f"search wall time {time.time() - t_search:.1f}s")
    print(f"wrote {exp_dir / 'selection.json'}")


if __name__ == "__main__":
    main()
