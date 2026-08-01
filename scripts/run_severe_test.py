"""WP2.11 part 1: the severe test, under its pinned protocol.

The sealed ``severe_test_protocol`` (``pre-registration.yaml``), verbatim:

    Exclude the 1970s (1970-01-01 to 1979-12-31 inclusive) from the fitting
    sample. Refit L1 and L2 and RETRAIN L3 with the FROZEN architectures and
    hyperparameters of the primary runs -- refit/retrain only, NO fresh
    hyperparameter search on the reduced sample, no architecture change, no
    early-stopping-criterion change. Regenerate from the 1965 climate state and
    compare 1966-1984 behaviour through the horizon tier.

L1 and L2 are refit by ``scripts/fit_climate.py --severe-test`` and
``scripts/fit_regimes.py --severe-test``. This script does the rest, in two
stages, strictly sequentially -- **one GPU job at a time**:

``train``
    Build the severe block dataset (the severe L1 posterior + the campaign
    source, ``exclude=SEVERE_TEST_EXCLUSION``) and RETRAIN L3 at the frozen
    selected config and the frozen final budget, at one seed index per run.
    Nothing here searches or re-selects: the config comes from the family's
    committed ``selection.json`` and the budget from its committed search-space
    file, exactly as ``scripts/train_ablation_seeds.py`` does. The sealed tuning
    budget is spent and retraining at frozen hyperparameters is not tuning.

``battery``
    Assemble the SEVERE system and the PRIMARY (full-sample) system, both from
    the 1965 climate state (``JoineryConfig.s0_date``), at the sealed
    ``ensemble_size`` (1024 x 120), and judge both through the sealed battery
    against the sealed campaign reference. The two differ in exactly one thing --
    the fitting sample -- so any gap is attributable to the exclusion.

The compared window (1966-1984) deliberately CONTAINS the excluded decade. That
is the whole design: the question is whether a generator that never saw the
1970s can still produce them.

Determinism: ``CUBLAS_WORKSPACE_CONFIG=:4096:8`` is set at IMPORT time (before any
CUDA context exists) and ``torch.use_deterministic_algorithms(True)`` is asserted by
BOTH stages -- the same posture ``scripts/run_ablation_grid.py`` runs the sealed
WP2.10 cells under. Every stream is keyed by an integer seed; no clock is read into
any artifact.

The holdout is never touched: every read goes through ``DataAccess.train_val``,
and nothing here imports ``ah.eval.g2``.

Both co-primary L3 families run through this script. ``--family`` selects one;
it defaults to ``flow``, so every WP2.11 part 1 invocation means exactly what it
meant before this argument existed. The two families never share a stage: each
has its own frozen config, its own checkpoints, its own cells and its own grid
file, and the train stage must run for a family before its battery stage can.

Usage (one GPU job at a time)::

    uv run python -u scripts/run_severe_test.py train --created-at 2026-07-29 \
        --device cuda --indices 0 1 2
    uv run python -u scripts/run_severe_test.py battery --block-batch 128 \
        --sampler-device cuda

    uv run python -u scripts/run_severe_test.py train --family diffusion \
        --created-at 2026-07-31 --device cuda --indices 0 1 2
    uv run python -u scripts/run_severe_test.py battery --family diffusion \
        --block-batch 128 --sampler-device cuda
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

# Must be set BEFORE torch creates a CUDA context, so it is set at import time
# rather than inside a stage (``ah.gen.blocks.train.configure_determinism`` does
# the same, but only the train stage reaches it).
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch  # noqa: E402
import yaml  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval import prereg as prereg_mod  # noqa: E402
from ah.eval.battery import (  # noqa: E402
    register_reference_dependent_suites,
    run_battery,
)
from ah.eval.reference import compute_reference  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen import severe  # noqa: E402
from ah.gen.blocks import data as bd  # noqa: E402
from ah.gen.blocks import diffusion as df  # noqa: E402
from ah.gen.blocks import flow as fl  # noqa: E402
from ah.gen.blocks import train as tr  # noqa: E402
from ah.gen.blocks import tuning as tu  # noqa: E402
from ah.gen.blocks.diffusion import DiffusionConfig, HierBlockSystem  # noqa: E402
from ah.gen.blocks.flow import FlowConfig  # noqa: E402
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
    JoineryConfig,
)
from ah.gen.regimes.semimarkov import load_artifact as load_regimes  # noqa: E402
from ah.gen.systems import SEED_STRIDE, train_seed_for  # noqa: E402
from ah.splits import DataAccess  # noqa: E402

# The sealed reference-run parameters, identical to every other battery script.
REFERENCE_SEED = 20260726
N_RESAMPLES = 1000
LEVEL = 0.9
BLOCK_LENGTH = 120
SAMPLE_SEED_BASE = 20260727

OUT_ROOT = _REPO_ROOT / "experiments" / "wp211"
CHECKPOINT_MANIFEST = OUT_ROOT / "severe-checkpoints.json"

#: The severe-test L1/L2 artifacts, produced by the two `--severe-test` fits.
SEVERE_CLIMATE_ARTIFACT = (
    _REPO_ROOT
    / "experiments"
    / "climate-l1-severe-f7d4119c7101-s20260726"
    / "climate-posterior.npz"
)

#: The two co-primary L3 families, keyed exactly as ``ah.gen.systems`` keys them.
#:
#: ``train_tag``, ``cell_tag`` and ``grid_name`` are FROZEN per family rather than
#: derived, because WP2.11 part 1's flow artifacts already exist on disk under the
#: names below and its report is committed under ``artifacts/wp211/``. Flow's grid
#: therefore keeps its original un-suffixed ``severe-grid.json`` name: renaming it
#: for symmetry would strand a committed artifact and force a re-run whose only
#: product is a different filename. The asymmetry is deliberate and recorded here
#: rather than left for a reader to discover.
FAMILIES: dict[str, dict[str, Any]] = {
    "diffusion": {
        "config_cls": DiffusionConfig,
        "tuning_exp": "l3a-diffusion-tuning-v1",
        "space": _REPO_ROOT / "configs" / "wp28-diffusion-search-v1.yaml",
        "module": df,
        "sampler_cls": df.DiffusionBlockSampler,
        "train_tag": "severe-l3a-diffusion",
        "cell_tag": "diffusion",
        "grid_name": "severe-grid-diffusion.json",
    },
    "flow": {
        "config_cls": FlowConfig,
        "tuning_exp": "l3b-flow-tuning-v1",
        "space": _REPO_ROOT / "configs" / "wp29-flow-search-v1.yaml",
        "module": fl,
        "sampler_cls": fl.FlowBlockSampler,
        "train_tag": "severe-l3b-flow",
        "cell_tag": "flow",
        "grid_name": "severe-grid.json",
    },
}


def spec_for(family: str) -> dict[str, Any]:
    """The frozen spec for one L3 family, or a hard exit naming the valid keys."""
    if family not in FAMILIES:
        raise SystemExit(f"unknown family {family!r}; expected one of {sorted(FAMILIES)}")
    return FAMILIES[family]


def severe_regimes_artifact() -> Path:
    """The single severe L2 artifact directory (its config hash is data-independent)."""
    matches = sorted((_REPO_ROOT / "experiments").glob("regimes-l2-severe-*/regimes-posterior.npz"))
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one severe L2 artifact, found {len(matches)}: {matches}"
        )
    return matches[0]


def catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    import pandas as pd

    def reader(series_id: str):
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


# --------------------------------------------------------------------------- #
# stage: train
# --------------------------------------------------------------------------- #


def build_severe_dataset(catalog_root: Path, vintage: str) -> bd.BlockDataset:
    """The severe block dataset: the severe L1 posterior + the excluded decade."""
    from run_flow_tuning import build_dataset_waiting_for_catalog  # noqa: F401  (lock policy)

    manifest = load_manifest()
    while True:
        try:
            with Catalog(catalog_root) as catalog:
                access = catalog_access(catalog, vintage)
                source = build_source(access, manifest, vintage_id=vintage)
            break
        except Exception as exc:  # pragma: no cover - operational
            if "used by another process" not in str(exc):
                raise
            print("catalog busy; waiting 60s for the duckdb lock", flush=True)
            time.sleep(60.0)

    climate = load_climate(SEVERE_CLIMATE_ARTIFACT)
    if climate.meta.get("severe_test_exclusion") is None:
        raise SystemExit(
            f"{SEVERE_CLIMATE_ARTIFACT} records no severe_test_exclusion; that is the "
            f"PRIMARY posterior, not the severe one -- refusing"
        )
    return bd.build_dataset(source, climate, exclude=severe.SEVERE_TEST_EXCLUSION)


def stage_train(args: argparse.Namespace) -> None:
    torch.use_deterministic_algorithms(True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = (
        json.loads(CHECKPOINT_MANIFEST.read_text("utf-8")) if CHECKPOINT_MANIFEST.exists() else {}
    )

    dataset = build_severe_dataset(args.catalog_root, args.vintage)
    print(
        f"severe dataset: {dataset.n_train_raw} raw train blocks, "
        f"{dataset.n_train_effective} effective/epoch, "
        f"{dataset.n_dropped_excluded} blocks dropped by the exclusion, "
        f"{dataset.n_dropped_straddling} dropped straddling a split boundary",
        flush=True,
    )
    std = dataset.standardization
    print(f"severe x_mean[:3]={std.x_mean[:3]}  c_mean[:3]={std.c_mean[:3]}", flush=True)

    family = args.family
    spec = spec_for(family)
    _space, _budget, space_sha = tu.load_search_space(spec["space"], spec["config_cls"])
    final_budget = yaml.safe_load(Path(spec["space"]).read_text("utf-8"))["final"]
    selection = json.loads(
        (_REPO_ROOT / "experiments" / spec["tuning_exp"] / "selection.json").read_text("utf-8")
    )
    config = spec["config_cls"](**selection["config"])
    print(
        f"FROZEN config {selection['config_hash']} (space sha {space_sha[:12]}); "
        f"FROZEN budget {final_budget}",
        flush=True,
    )

    for index in args.indices:
        key = f"{family}:{index}"
        out_dir = OUT_ROOT / f"{spec['train_tag']}-s{index}"
        ckpt_path = out_dir / "checkpoint.pt"
        if key in manifest and ckpt_path.exists():
            print(f"[{key}] already trained; skipping", flush=True)
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        seed = train_seed_for(family, index)
        print(f"\n=== SEVERE retrain {key}: train seed {seed} ===", flush=True)
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
            log=lambda msg: print(f"  {msg}", flush=True),
        )
        wall = time.time() - t0
        meta = tr.save_checkpoint(
            result,
            dataset,
            ckpt_path,
            extra_meta={
                "generator_id": spec["module"].GENERATOR_ID,
                "vintage_id": args.vintage,
                "seed": seed,
                "seed_index": index,
                "selection": selection,
                "search_space_sha256": space_sha,
                "climate_sha256": load_climate(SEVERE_CLIMATE_ARTIFACT).meta["content_sha256"],
                "severe_test_exclusion": severe.SEVERE_TEST_EXCLUSION.label,
                "severe_blocks_dropped_by_exclusion": dataset.n_dropped_excluded,
                "training_wall_seconds": wall,
                "device": args.device,
                "final_budget": final_budget,
                "created_at": args.created_at,
                "n_train_raw_blocks": dataset.n_train_raw,
                "n_train_effective_per_epoch": dataset.n_train_effective,
            },
        )
        manifest[key] = {
            "train_seed": seed,
            "checkpoint": str(ckpt_path.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "checkpoint_hash": meta["checkpoint_hash"],
            "config_hash": meta["config_hash"],
            "best_s": meta["best_s"],
            "best_gen_term": meta["best_gen_term"],
            "best_aux_term": meta["best_aux_term"],
            "best_step": meta["best_step"],
            "steps_run": meta["steps_run"],
            "stopped_early": meta["stopped_early"],
            "wall_s": wall,
        }
        CHECKPOINT_MANIFEST.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8"
        )
        print(
            f"[{key}] done in {wall / 60:.1f} min; S={meta['best_s']:.6f} "
            f"step {meta['best_step']}/{meta['steps_run']} "
            f"early={meta['stopped_early']} sha {meta['checkpoint_hash'][:16]}...",
            flush=True,
        )


# --------------------------------------------------------------------------- #
# stage: battery
# --------------------------------------------------------------------------- #


def _sampler_for(family: str, checkpoint: Path, expected_hash: str, source, block_batch, device):
    spec = spec_for(family)
    model, std, meta = spec["module"].load_checkpoint(checkpoint)
    if meta["checkpoint_hash"] != expected_hash:
        raise SystemExit(
            f"{checkpoint}: hash {meta['checkpoint_hash'][:16]}... != pinned "
            f"{expected_hash[:16]}..."
        )
    kwargs: dict[str, Any] = dict(
        trained_fingerprint=meta["cb_fingerprint"],
        device=device,
        block_batch=block_batch,
    )
    # Mirrors ah.gen.systems._build_sampler's branch verbatim: guidance is a
    # FLOW-ONLY constructor argument (WP2.9's guidance arm) and
    # DiffusionBlockSampler does not accept it. Kept as a branch rather than a
    # spec field so the two call sites cannot drift apart silently.
    if family == "flow":
        kwargs["guidance_scale"] = spec["module"].DEFAULT_GUIDANCE_SCALE
    sampler = spec["sampler_cls"](model, std, tuple(source.factor_names), **kwargs)
    return sampler, meta


def _arm_class(family: str, arm: str) -> type:
    """The ``HierBlockSystem`` subclass for one (family, arm).

    Built with ``type()`` rather than written out four times so the two arms
    cannot drift in anything but the one word that distinguishes them. The
    descriptions reproduce WP2.11 part 1's flow strings exactly -- they land in
    ensemble metadata and therefore in every committed ``summary.json``.
    """
    module = spec_for(family)["module"]
    fit = "1970s EXCLUDED from the fit" if arm == "severe" else "full-sample fit"
    return type(
        f"_{arm.capitalize()}{family.capitalize()}",
        (HierBlockSystem,),
        {
            "generator_id": module.GENERATOR_ID,
            "system_description": f"L1+L2+L4 ({module.GENERATOR_ID} blocks), {fit}",
        },
    )


def build_arm(family: str, arm: str, seed_index: int, source, *, block_batch: int, device: str):
    """Construct the severe or the primary system for one family, from 1965."""
    config = JoineryConfig(s0_date=severe.SEVERE_TEST_S0_DATE)
    cls = _arm_class(family, arm)
    if arm == "severe":
        climate = load_climate(SEVERE_CLIMATE_ARTIFACT)
        regimes = load_regimes(severe_regimes_artifact())
        manifest = json.loads(CHECKPOINT_MANIFEST.read_text("utf-8"))
        key = f"{family}:{seed_index}"
        if key not in manifest:
            raise SystemExit(
                f"{CHECKPOINT_MANIFEST} has no entry {key!r}; run the train stage "
                f"for --family {family} first"
            )
        entry = manifest[key]
        sampler, meta = _sampler_for(
            family,
            _REPO_ROOT / entry["checkpoint"],
            entry["checkpoint_hash"],
            source,
            block_batch,
            device,
        )
        system = cls(climate, regimes, source, sampler, config)
    else:
        climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
        regimes = load_regimes(DEFAULT_REGIMES_ARTIFACT)
        if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
            raise SystemExit("primary climate artifact sha != WP2.7 pin")
        if regimes.meta["content_sha256"] != PINNED_REGIMES_SHA256:
            raise SystemExit("primary regimes artifact sha != WP2.7 pin")
        from ah.gen import systems as sysmod

        path, expected = sysmod._checkpoint_for(family, seed_index)
        sampler, meta = _sampler_for(family, path, expected, source, block_batch, device)
        system = cls(climate, regimes, source, sampler, config)
    system.checkpoint_hash = meta["checkpoint_hash"]
    system.config_hash = meta.get("config_hash")
    return system, meta


def run_cell(
    family: str,
    arm: str,
    seed_index: int,
    *,
    source,
    manifest,
    prereg,
    reference,
    n_paths: int,
    months: int,
    block_batch: int,
    device: str,
) -> dict[str, Any]:
    sample_seed = SAMPLE_SEED_BASE + SEED_STRIDE * seed_index
    out_dir = OUT_ROOT / "cells" / f"{arm}-{spec_for(family)['cell_tag']}-s{seed_index}"
    out_dir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    t0 = time.time()

    system, ckpt_meta = build_arm(
        family, arm, seed_index, source, block_batch=block_batch, device=device
    )
    timings["build_s"] = time.time() - t0

    t = time.time()
    print(f"    assembling UNFILTERED ({n_paths} x {months}) seed {sample_seed}...", flush=True)
    unfiltered = system.sample_months(months, n_paths, sample_seed, unfiltered=True)
    timings["assemble_unfiltered_s"] = time.time() - t

    t = time.time()
    print("    assembling FILTERED (same seed, filter on)...", flush=True)
    filtered = system.sample_months(months, n_paths, sample_seed)
    timings["assemble_filtered_s"] = time.time() - t

    t = time.time()
    print("    judging (sealed battery, unfiltered primary)...", flush=True)
    report = run_battery(
        unfiltered,
        reference=reference,
        prereg=prereg,
        manifest=manifest,
        seed=sample_seed,
        filtered=filtered,
    )
    timings["battery_s"] = time.time() - t
    timings["total_s"] = time.time() - t0

    doc = report.to_dict()
    (out_dir / "battery.json").write_text(report.to_json(), "utf-8")
    (out_dir / "battery.md").write_text(report.to_markdown(), "utf-8")

    meta_c = unfiltered.meta.conditioning
    summary = {
        "arm": arm,
        "family": family,
        "seed_index": seed_index,
        "sample_seed": sample_seed,
        "s0_date": severe.SEVERE_TEST_S0_DATE,
        "generator_id": unfiltered.meta.generator_id,
        "system_description": meta_c.get("system"),
        "checkpoint_hash": unfiltered.meta.checkpoint_hash,
        "config_hash": unfiltered.meta.config_hash,
        "train_seed": ckpt_meta.get("seed"),
        "climate_sha256": ckpt_meta.get("climate_sha256"),
        "severe_test_exclusion": ckpt_meta.get("severe_test_exclusion"),
        "vintage_id": doc["vintage_id"],
        "n_paths": unfiltered.n_paths,
        "months": unfiltered.months,
        "criterion_bearing": doc["criterion_bearing"],
        "prereg_verified": doc["prereg_verified"],
        "prereg_digest": doc["prereg_digest"],
        "passed_unfiltered": doc["passed"],
        "layer_artifacts": meta_c.get("layer_artifacts"),
        "support_unfiltered": {
            k: v for k, v in (meta_c.get("support") or {}).items() if "by_decade" not in k
        },
        "reconciliation_unfiltered": meta_c.get("reconciliation"),
        "n_rejections": (meta_c.get("acceptance_filter") or {}).get("n_rejected"),
        "block_sampler_batch": meta_c.get("block_sampler_batch", block_batch),
        "block_sampler_device": meta_c.get("block_sampler_device", device),
        "timings": timings,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", "utf-8"
    )
    return summary


def stage_battery(args: argparse.Namespace) -> None:
    # Same determinism posture as scripts/run_ablation_grid.py, which the sealed
    # WP2.10 cells were produced under; CUBLAS_WORKSPACE_CONFIG is set at import.
    torch.use_deterministic_algorithms(True)
    family = args.family
    spec = spec_for(family)
    spec["module"].DEFAULT_BLOCK_BATCH = args.block_batch
    spec["module"].DEFAULT_SAMPLER_DEVICE = args.sampler_device

    manifest = load_manifest()
    prereg = prereg_mod.load(_REPO_ROOT / "pre-registration.yaml")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        source = build_source(access, manifest, vintage_id=args.vintage)
        print("computing the sealed campaign reference (once)...", flush=True)
        t = time.time()
        reference = compute_reference(
            access,
            manifest,
            vintage_id=args.vintage,
            seed=REFERENCE_SEED,
            n_resamples=N_RESAMPLES,
            level=LEVEL,
            block_length=BLOCK_LENGTH,
            resample_length=args.months,
        )
        print(f"reference done in {(time.time() - t) / 60:.1f} min", flush=True)
        register_reference_dependent_suites(manifest, reference)

        rows: list[dict[str, Any]] = []
        for seed_index in args.indices:
            for arm in args.arms:
                out_dir = OUT_ROOT / "cells" / f"{arm}-{spec['cell_tag']}-s{seed_index}"
                if (out_dir / "summary.json").exists() and not args.force:
                    print(f"  {family}/{arm}:s{seed_index} already done; skipping", flush=True)
                    rows.append(json.loads((out_dir / "summary.json").read_text("utf-8")))
                    continue
                print(f"\n=== cell {family}/{arm}:s{seed_index} ===", flush=True)
                rows.append(
                    run_cell(
                        family,
                        arm,
                        seed_index,
                        source=source,
                        manifest=manifest,
                        prereg=prereg,
                        reference=reference,
                        n_paths=args.n_paths,
                        months=args.months,
                        block_batch=args.block_batch,
                        device=args.sampler_device,
                    )
                )

    grid_path = OUT_ROOT / spec["grid_name"]
    grid_path.write_text(
        json.dumps(
            {
                "protocol": "severe_test_protocol (pre-registration.yaml)",
                "exclusion": severe.SEVERE_TEST_EXCLUSION.label,
                "s0_date": severe.SEVERE_TEST_S0_DATE,
                "family": family,
                "n_paths": args.n_paths,
                "months": args.months,
                "block_batch": args.block_batch,
                "sampler_device": args.sampler_device,
                "cells": rows,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        "utf-8",
    )
    print(f"\nwrote {grid_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)

    p_train = sub.add_parser("train", help="retrain L3 on the reduced sample")
    p_train.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    p_train.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    p_train.add_argument("--device", default="cuda")
    p_train.add_argument("--created-at", required=True)
    p_train.add_argument("--indices", type=int, nargs="+", default=[0, 1, 2])
    p_train.add_argument("--family", default="flow", choices=sorted(FAMILIES))
    p_train.set_defaults(func=stage_train)

    p_bat = sub.add_parser("battery", help="regenerate from 1965 and judge")
    p_bat.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    p_bat.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    p_bat.add_argument("--n-paths", type=int, default=CRITERION_N_PATHS)
    p_bat.add_argument("--months", type=int, default=CRITERION_MONTHS)
    p_bat.add_argument("--block-batch", type=int, default=128)
    p_bat.add_argument("--sampler-device", default="cuda")
    p_bat.add_argument("--indices", type=int, nargs="+", default=[0, 1, 2])
    p_bat.add_argument("--arms", nargs="+", default=["severe", "primary"])
    p_bat.add_argument("--family", default="flow", choices=sorted(FAMILIES))
    p_bat.add_argument("--force", action="store_true")
    p_bat.set_defaults(func=stage_battery)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
