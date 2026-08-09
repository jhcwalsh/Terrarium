"""The generator console (port 8797) — watch a decade get built, layer by layer.

Read-only, internal console family (hub 8795, data 8796, THIS 8798-adjacent
slot, build 8798, QA 8799). Two instruments:

* a four-stage step-through of ONE hier-flow decade — climate, seasons,
  weather, joinery — from the campaign-2 checkpoints (hash-verified), and
* an artifact-based monitor of live campaign runs under ``experiments/``.

RECORDED DEPENDENCY: this module consumes the joinery's per-decade private
classes (``_DecadeFactory``) and module-level filter helpers READ-ONLY. A
generator refactor may break this console; the console must never push back
on the generator. Nothing in ``ah/gen/`` is edited, and nothing shown here
is a score.

Run:  uv run uvicorn ah.genconsole:app --port 8797
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHECKPOINT_MANIFEST = _REPO_ROOT / "configs" / "campaign2-checkpoints.json"

StageEvent = tuple[str, dict[str, Any]]

#: step-through stage order — the DN-1.1 layer names
STAGES: tuple[str, ...] = ("climate", "seasons", "weather", "joinery")


def _rle(labels: list[str]) -> list[dict[str, Any]]:
    """Run-length encode a label path into spells."""
    spells: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        if spells and spells[-1]["label"] == label:
            spells[-1]["months"] += 1
        else:
            spells.append({"label": label, "start": i, "months": 1})
    return spells


def build_decade(
    seed: int,
    checkpoint_index: int,
    *,
    on_stage: Callable[[str, dict[str, Any]], None],
    block_batch: int = 16,
    device: str = "cpu",
    sampler_override: Any = None,
) -> dict[str, Any]:
    """Build ONE decade through the real four layers, emitting each stage.

    Assembly mirrors ``campaign2_promotion._build_campaign_flow`` exactly:
    checkpoint hash verified against the committed campaign manifest, climate
    and regimes artifacts checked against the WP2.7 sha pins. Any pin
    mismatch raises ``ValueError`` — the app layer renders it as a page
    error; there is no fallback checkpoint. Deterministic: the platform seed
    rule makes this decade bit-identical to decade 0 of a batched ensemble
    with the same base seed.
    """
    import torch

    from ah.gen.blocks.flow import FlowBlockSampler, load_checkpoint
    from ah.gen.bootstrap import campaign_source
    from ah.gen.climate.model import STATE_NAMES
    from ah.gen.climate.simulate import load_artifact as load_climate
    from ah.gen.joinery import assemble as ja
    from ah.gen.joinery import support as sp
    from ah.gen.joinery import waypoints as wpts
    from ah.gen.regimes.semimarkov import REGIME_LABELS
    from ah.gen.regimes.semimarkov import load_artifact as load_regimes

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

    manifest_doc = json.loads(_CHECKPOINT_MANIFEST.read_text("utf-8"))
    key = f"flow:{checkpoint_index}"
    entry = manifest_doc.get(key)
    if entry is None:
        raise ValueError(f"no campaign checkpoint manifest entry for {key}")
    model, std, meta = load_checkpoint(_REPO_ROOT / entry["checkpoint"])
    if meta["checkpoint_hash"] != entry["checkpoint_hash"]:
        raise ValueError(
            f"checkpoint hash mismatch for {key}: manifest "
            f"{entry['checkpoint_hash'][:16]}..., loaded {meta['checkpoint_hash'][:16]}..."
        )
    climate = load_climate(ja.DEFAULT_CLIMATE_ARTIFACT)
    regimes = load_regimes(ja.DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != ja.PINNED_CLIMATE_SHA256:
        raise ValueError("climate artifact sha256 != WP2.7 pin")
    if regimes.meta["content_sha256"] != ja.PINNED_REGIMES_SHA256:
        raise ValueError("regimes artifact sha256 != WP2.7 pin")

    source = campaign_source()
    sampler = sampler_override or FlowBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device=device,
        block_batch=block_batch,
    )
    config = ja.JoineryConfig()
    stats = wpts.source_stats(source, climate)
    support_ref = sp.build_support_reference(source, climate, quantile=config.support_quantile)
    factory = ja._DecadeFactory(
        climate=climate,
        regimes_artifact=regimes,
        source=source,
        stats=stats,
        support_ref=support_ref,
        sampler=sampler,
        config=config,
        months=120,
        seed=seed,
        world=None,
        guidance=None,
    )

    prep = factory.prepare(0)
    months = list(range(prep.sim.months))
    on_stage(
        "climate",
        {
            "months": months,
            "states": {
                name: [float(v) for v in prep.sim.states[0, :, i]]
                for i, name in enumerate(STATE_NAMES)
            },
            "theta_index": int(prep.sim.theta_index[0]),
        },
    )

    labels = [str(REGIME_LABELS[int(c)]) for c in prep.waypoints.labels]
    on_stage("seasons", {"labels": labels, "durations": _rle(labels)})

    result = factory.assemble([prep])[0]
    names = list(source.factor_names)
    block_starts = list(range(0, len(months), config.block_months))
    on_stage(
        "weather",
        {
            "block_months": int(config.block_months),
            "factors": {
                name: [float(v) for v in result.path[:, i]] for i, name in enumerate(names)
            },
            "blocks": [{"start": s, "regime": labels[s]} for s in block_starts],
        },
    )

    filter_stats: dict[str, dict[str, dict[str, float]]] = {}
    for name in ja.FILTER_FACTORS:
        if name not in names:
            continue
        col = names.index(name)
        filter_stats[name] = {
            metric: {
                "decade": float(ja._FILTER_FUNCS[metric](result.path[:, col])),
                "historical": float(ja._FILTER_FUNCS[metric](source.values[:, col])),
            }
            for metric in ja.FILTER_METRICS
        }
    on_stage(
        "joinery",
        {
            "reconciliation": result.reconciliation.summary(),
            "filter_stats": filter_stats,
            "filter_note": (
                "accept/reject is an ensemble-relative decision over many decades; "
                "a single decade has statistics, not a verdict"
            ),
        },
    )

    return {
        "months": len(months),
        "checkpoint_hash": str(meta["checkpoint_hash"]),
        "stages": list(STAGES),
    }
