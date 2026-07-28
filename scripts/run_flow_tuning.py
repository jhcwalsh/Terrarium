"""WP2.9: run the SEALED tuning search for hier-flow-v1 (GPU).

The protocol is pre-registration.yaml `tuning_protocol` (binding), and the budget
is PER SYSTEM PER SAMPLER: this search has its own 40 distinct started configs
and does NOT inherit WP2.8's 8 unspent ones. Every trial (crashes included) is
logged with config hash, git SHA, seed and per-fold validation scores to
experiments/<exp_id>/tuning-log.jsonl; selection is the sealed
S = mean_folds(gen) + 1.0 * mean_folds(aux), ties broken by lower TRUE sampling
NFE. The search space was stated in advance in
configs/wp29-flow-search-v1.yaml, whose SHA-256 is recorded in the log header
before the first trial.

This is the same protocol CODE as WP2.8 (ah.gen.blocks.tuning), parameterized by
the config class -- not a second copy, so the two arms cannot drift apart.

Usage (offline; local catalog + fitted artifacts, no network)::

    uv run python -u scripts/run_flow_tuning.py --device cuda --created-at 2026-07-28
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

from run_blocks_tuning import build_campaign_dataset  # noqa: E402

from ah.experiment import ExperimentStore  # noqa: E402
from ah.gen.blocks import tuning as tu  # noqa: E402
from ah.gen.blocks.flow import FlowConfig  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402

DEFAULT_SPACE = _REPO_ROOT / "configs" / "wp29-flow-search-v1.yaml"
EXP_ID = "l3b-flow-tuning-v1"


def build_dataset_waiting_for_catalog(
    catalog_root: Path, vintage: str, *, timeout_s: float = 8 * 3600, poll_s: float = 60.0
):
    """Build the campaign dataset, waiting politely for the catalog's file lock.

    DuckDB takes an EXCLUSIVE file lock on ``catalog.duckdb`` (on Windows even a
    read-only connection is refused while another process holds it), so two
    Step-2 jobs cannot open it at once. Rather than fail, or race, or copy the
    file out from under a live writer, this polls until the lock clears. The
    dataset build itself is sub-second; the catalog is held for seconds, not
    hours, by anything that is not a full battery run.
    """
    deadline = time.time() + timeout_s
    attempt = 0
    while True:
        try:
            return build_campaign_dataset(catalog_root, vintage)
        except Exception as exc:
            if "used by another process" not in str(exc) or time.time() > deadline:
                raise
            attempt += 1
            print(
                f"catalog busy (attempt {attempt}); another Step-2 job holds the "
                f"duckdb lock -- waiting {poll_s:.0f}s",
                flush=True,
            )
            time.sleep(poll_s)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--space", type=Path, default=DEFAULT_SPACE)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--exp-id", default=EXP_ID)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()

    space, budget, space_sha = tu.load_search_space(args.space, FlowConfig)
    print(f"search space {args.space.name} sha256 {space_sha}")
    print(f"budget params: {budget}")

    t0 = time.time()
    dataset = build_dataset_waiting_for_catalog(args.catalog_root, args.vintage)
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
                "purpose": "wp2.9 sealed tuning search (hier-flow-v1)",
                "search_space_file": str(args.space.name),
                "search_space_sha256": space_sha,
                "budget_params": budget,
                "vintage_id": args.vintage,
                "budget_note": (
                    "sealed trial_budget_per_system is PER SAMPLER; WP2.8's unspent "
                    "8 are not available here and are not used"
                ),
            },
            seed=int(budget["seed"]),
            vintage_id=args.vintage,
            created_at=args.created_at,
        )

    configs = tu.sample_trial_configs(
        space, int(budget["n_trials"]), seed=int(budget["seed"]), config_cls=FlowConfig
    )
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
    print("\n=== SELECTION (sealed criterion, hier-flow-v1) ===")
    print(f"config_hash      {selection['config_hash']}")
    print(f"S                {selection['s_value']:.6f}")
    print(f"  gen_term       {selection['gen_term']:.6f}  (velocity MSE -- 3b's own scale)")
    print(f"  aux_term       {selection['aux_term']:.6f}  (selection_lambda 1.0, PINNED)")
    print(f"true NFE         {selection['eval_nfe']}")
    print(
        f"trials           {selection['n_trials_started']} started / "
        f"{selection['n_trials_completed']} completed / budget {selection['trial_budget']}"
    )
    print(f"search wall time {time.time() - t_search:.1f}s")
    print(f"wrote {exp_dir / 'selection.json'}")


if __name__ == "__main__":
    main()
