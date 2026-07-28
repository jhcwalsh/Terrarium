"""WP2.9: the sampler bake-off — both L3 arms of system D through ONE entry point.

§WP2.9 acceptance: "both samplers through one entry point; like-for-like
bake-off table". This script drives :mod:`ah.gen.blocks.bakeoff` over every arm
in ``--arms`` on the SAME data, the SAME validation folds, the SAME noise seeds
and the SAME conditioning slate, and writes the table.

WHAT IT MEASURES (all of it band-independent, so it can run before the WP2.7b
ig_spread band correction lands):

  * both terms of the sealed S, per arm, computed by the SAME
    ``train.evaluate_fold_scores`` code path both arms were selected by --
    reported SEPARATELY with their scales, never as a cross-arm ranking, because
    the two generative objectives are different quantities (sealed
    tuning_protocol.selection_criterion);
  * sampling cost: true NFE per block (classifier-free guidance counted as the
    two network evaluations per step that it is), blocks/s, seconds per decade
    and per 10k decades, at a DECLARED block width and device;
  * the conditioning-response table -- the artifacts/wp28/ig-spread-diagnosis.md
    §4 finite-difference measurement, generalized, so the arms' responsiveness
    is comparable and not just their scores;
  * for the flow arm, the SAME checkpoint with and without guidance, so the
    guidance effect is visible as an arm rather than baked in.

WHAT IT DOES NOT MEASURE, and why: battery outcomes, reconciliation-adjustment
distributions and waypoint-band diagnostics all run through the joinery, whose
ig_spread band is being corrected on another branch. A bake-off measured across
two different bands is not a bake-off, so those rows stay empty here and are
filled by the end-to-end run once the band lands.

Usage (offline; local catalog + fitted artifacts + trained checkpoints)::

    uv run python -u scripts/run_sampler_bakeoff.py --device cuda --block-batch 128
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


from run_flow_tuning import build_dataset_waiting_for_catalog  # noqa: E402

from ah.gen.blocks import bakeoff as bo  # noqa: E402
from ah.gen.blocks import losses as ls  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402

PENDING_BAND_NOTE = (
    "Battery outcome, reconciliation-adjustment distribution and waypoint-band "
    "diagnostics are NOT in this table. They run through the joinery, whose "
    "ig_spread waypoint band is being corrected (WP2.7b); measuring the two arms "
    "across two different bands would not be a bake-off. Those rows are filled by "
    "the end-to-end sealed battery run once the band correction has landed."
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    p.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    p.add_argument("--out-dir", type=Path, default=_REPO_ROOT / "artifacts" / "wp29")
    p.add_argument("--arms", nargs="+", default=list(bo.ARM_IDS))
    p.add_argument("--device", default="cpu")
    p.add_argument("--block-batch", type=int, default=1)
    p.add_argument("--cost-blocks", type=int, default=1024)
    p.add_argument("--n-probe", type=int, default=256)
    p.add_argument("--n-rep-eval", type=int, default=16)
    p.add_argument(
        "--guidance-scales",
        type=float,
        nargs="*",
        default=[],
        help="extra classifier-free guidance scales to evaluate as ABLATION arms on any "
        "checkpoint with a trained null branch. Each is an ADDITIONAL row, never a "
        "replacement for the selected configuration, and each is labelled as an "
        "ablation in the table.",
    )
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    import torch

    torch.use_deterministic_algorithms(True)

    dataset = build_dataset_waiting_for_catalog(args.catalog_root, args.vintage)
    compiled, excluded = ls.compile_block_strategies(dataset.factor_names, dataset.block_months)
    print(f"dataset folds {[int(f.size) for f in dataset.fold_indices]}; excluded {excluded}")

    rows: list[bo.BakeoffRow] = []
    for arm in args.arms:
        variants: list[tuple[str, float | None]] = [(arm, None)]
        # Each arm keeps ITS OWN checkpoint standardization -- the train-only
        # constants it was fitted with. They must equal the freshly built
        # dataset's, and that is asserted rather than assumed: silently
        # substituting one arm's constants for another's would corrupt the
        # comparison in a way no downstream number would reveal.
        sampler, meta = bo.build_sampler(arm, device=args.device, block_batch=args.block_batch)
        np.testing.assert_allclose(sampler._std.x_mean, dataset.standardization.x_mean)
        np.testing.assert_allclose(sampler._std.c_std, dataset.standardization.c_std)
        assert tuple(sampler.factor_names) == tuple(dataset.factor_names)
        selected_scale = float(getattr(sampler, "guidance_scale", 1.0))
        if meta.get("supports_guidance"):
            for scale in args.guidance_scales:
                if float(scale) != selected_scale:
                    variants.append((f"{arm} (ablation: guidance {scale:g})", float(scale)))

        for label, guidance in variants:
            print(f"\n=== {label} ===", flush=True)
            s, meta = bo.build_sampler(
                arm,
                device=args.device,
                block_batch=args.block_batch,
                guidance_scale=guidance,
            )
            row = bo.BakeoffRow(
                arm=label,
                checkpoint_hash=meta.get("checkpoint_hash"),
                config_hash=meta.get("config_hash"),
                generative_objective=meta.get("generative_objective", ""),
                guidance_scale=float(getattr(s, "guidance_scale", 1.0)),
            )

            t0 = time.time()
            scores = bo.fold_scores(s, dataset, compiled, n_rep=args.n_rep_eval, device=args.device)
            row.gen_term = scores["gen_term"]
            row.aux_term = scores["aux_term"]
            row.selection_lambda = scores["selection_lambda"]
            print(
                f"S {row.s_value:.6f} = gen {row.gen_term:.6f} + 1.0 * aux "
                f"{row.aux_term:.6f}   [{time.time() - t0:.0f}s]"
            )

            row.cost = bo.measure_sampling_cost(
                s, arm=label, n_blocks=args.cost_blocks, seed=20260728
            )
            print(
                f"cost: NFE/block {row.cost.nfe_per_block}, "
                f"{row.cost.blocks_per_second:.1f} blocks/s, "
                f"{row.cost.seconds_per_decade:.4f} s/decade, "
                f"{row.cost.seconds_per_10k_decades:,.0f} s per 10k decades"
            )

            t0 = time.time()
            row.conditioning = bo.conditioning_response(s, dataset, n_probe=args.n_probe)
            for name, ch in row.conditioning["channels"].items():
                print(
                    f"  {name:24s} hist {ch['historical_ols']:+.4f}  "
                    f"model {ch['model_finite_difference']:+.4f}  ratio {ch['ratio']:.1%}"
                )
            print(f"  [{time.time() - t0:.0f}s]")

            row.notes.append(
                f"selected under its own sealed 40-trial budget; "
                f"generative objective = {row.generative_objective or 'n/a'}"
            )
            if guidance is not None:
                row.notes.append(
                    f"ABLATION ARM, not a selected configuration: the SAME checkpoint "
                    f"sampled at guidance {guidance:g} instead of the sealed selection's "
                    f"{selected_scale:g}. Classifier-free guidance is learned aim (it "
                    f"amplifies conditioning the model already reads), not post-hoc repair; "
                    f"it is reported here alongside the unguided row so the effect is "
                    f"visible, and it costs 2x the network evaluations."
                )
            rows.append(row)

    doc = {
        "vintage_id": args.vintage,
        "device": args.device,
        "block_batch": args.block_batch,
        "n_rep_eval": args.n_rep_eval,
        "n_probe": args.n_probe,
        "cost_blocks": args.cost_blocks,
        "pending": PENDING_BAND_NOTE,
        "incomparability_note": bo.INCOMPARABILITY_NOTE,
        "rows": [r.as_dict() for r in rows],
    }
    (args.out_dir / "bakeoff.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    md = bo.render_markdown(
        rows, title="WP2.9 sampler bake-off (hier-diffusion-v1 vs hier-flow-v1)"
    )
    md += f"\n## Not yet measured\n\n{PENDING_BAND_NOTE}\n"
    (args.out_dir / "bakeoff.md").write_text(md, "utf-8")
    print("\n" + md)
    print(f"wrote {args.out_dir / 'bakeoff.md'}")


if __name__ == "__main__":
    main()
