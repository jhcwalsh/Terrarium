"""The world bundle (su-eng-01) — DN-3 W2's payload contract, versioned.

The browser never receives an ensemble: a bundle carries exactly what the
single-user experience renders, precomputed once and immutable (W10).
Contract v0.1, four sections plus provenance:

- ``revealed``   — the run's own path (monthly returns per asset, reported
                   variants for the smoothed sleeves) with its **t0 seal**
                   (``ah.artifacts.live.seal_tape`` over the numeric tape) so
                   live mode can prove nobody rewrote history mid-game (W3).
- ``bands``      — per-asset fan quantiles (p5/p25/p50/p75/p95 of cumulative
                   growth) drawn from the run's OWN regenerated ensemble.
- ``summary``    — final twin value, decision-window schedule, episode
                   markers (the world's regime sequence), digest verification.
- ``feed``       — the world's narrative dispatches, the store chronicle,
                   and (v0.2, su-app-03) ``artifacts``: the tier-1 wire
                   generated from the tape by ``ah.feed.build_tier1_feed``,
                   each item carrying its ``month`` so the app reveals it
                   with the pointer (E2). PD-4 stands: everything is authored
                   at BUILD time; tier-2 letters join only at the frozen
                   >=95% first-pass bar, and ``meta.artifact_tier`` records
                   what this bundle actually contains.

Determinism and lineage: the bundle is derived from the RunRecord ALONE via
the same regenerate-and-verify path as ``ah inspect`` — a tampered record
yields a loud ``digest_verified: false`` in the bundle rather than a pretty
payload. Two builds of the same run are byte-identical (no clocks; the only
timestamp is the record's own ``created_at``). Size budget: **under 1 MB
compressed**, enforced here (a bundle that outgrows W2's budget should fail
its build, not slowly poison load times).
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from typing import Any

import numpy as np

from ah.artifacts.live import seal_tape
from ah.core.digest import digest_ensemble
from ah.core.engine import ASSETS, REPORTED_SLEEVES, EnginePaths, run_ensemble, run_path
from ah.core.institution import decision_months, hold_course_twin
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.feed import build_tier1_feed
from ah.play import simulate_play
from ah.store import chronicle as chronicle_store
from ah.store.runrecords import get_run_record
from ah.store.worlds import get_world

__all__ = ["BUNDLE_VERSION", "MAX_COMPRESSED_BYTES", "BundleError", "build_bundle", "write_bundle"]

BUNDLE_VERSION = "world-bundle-0.4"  # 0.4: the twin's ledger replaces the pacing preview
MAX_COMPRESSED_BYTES = 1_000_000  # W2's budget: a complete world under 1 MB compressed
_QUANTILES = (5, 25, 50, 75, 95)


class BundleError(RuntimeError):
    """A bundle that cannot be built honestly (missing lineage, budget blown)."""


def _round(values: np.ndarray, places: int = 6) -> list[float]:
    return [round(float(v), places) for v in values]


def _twin_ledger(revealed: EnginePaths) -> dict[str, list[float] | list[int]]:
    """The hold-course institution's quarterly cashflows, for the bundle."""
    result = simulate_play(revealed, None)
    return {
        "quarter_months": [q.month for q in result.quarters],
        "calls": _round(np.array([q.calls_paid for q in result.quarters])),
        "distributions": _round(np.array([q.distributions_received for q in result.quarters])),
        "nav_true": _round(np.array([q.nav_true for q in result.quarters])),
        "nav_reported": _round(np.array([q.nav_reported for q in result.quarters])),
        "cash": _round(np.array([q.cash for q in result.quarters])),
        "unfunded": _round(np.array([q.unfunded_total for q in result.quarters])),
        "private_weight_true": _round(np.array([q.private_weight_true for q in result.quarters])),
    }


def build_bundle(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    """The W2 contract for one RunRecord, regenerated and verified from lineage."""
    rec = get_run_record(conn, run_id)
    if rec is None:
        raise BundleError(f"no run_record with run_id={run_id}")
    world_doc = get_world(conn, rec["world_id"])
    if world_doc is None:
        raise BundleError(f"run {run_id} references missing world {rec['world_id']}")

    ws = WorldSpec.model_validate(world_doc)
    nw = project_numeric(ws)
    revealed = run_path(nw, rec["seed"])
    ensemble = run_ensemble(nw, rec["n_paths"], base_seed=rec["seed"])
    verified = digest_ensemble(ensemble) == rec["outputs_digest"]
    twin = hold_course_twin(nw, rec["seed"])

    # The numeric tape (months x series): asset returns then reported columns,
    # in a fixed, recorded order — the t0 seal covers exactly these bytes.
    series_order = [*ASSETS, *(f"{s}_reported" for s in REPORTED_SLEEVES)]
    tape = np.column_stack(
        [revealed.returns[a] for a in ASSETS] + [revealed.reported[s] for s in REPORTED_SLEEVES]
    ).astype(np.float64)
    # The seal covers the bytes the bundle SHIPS: round first, seal the rounded
    # tape, store the same values -- a client re-sealing what it received must
    # reproduce the hash exactly.
    tape = np.round(tape, 6)

    bands: dict[str, dict[str, list[float]]] = {}
    for asset in ASSETS:
        # engine returns are in PERCENT (see ah.core.engine notes) — divide
        # before compounding, or the cone explodes/goes negative (found live:
        # the first played decade rendered empty fans at the broken scale)
        growth = np.cumprod(1.0 + ensemble.returns[asset] / 100.0, axis=1)
        qs = np.percentile(growth, _QUANTILES, axis=0)
        bands[asset] = {f"p{q}": _round(qs[i]) for i, q in enumerate(_QUANTILES)}

    narrative = world_doc.get("narrative") or {}
    regimes = world_doc.get("regimes") or {}
    chronicle_rows = chronicle_store.read(conn, rec["world_id"])

    doc: dict[str, Any] = {
        "bundle_version": BUNDLE_VERSION,
        "meta": {
            "world_id": rec["world_id"],
            "run_id": run_id,
            "seed": rec["seed"],
            "n_paths": rec["n_paths"],
            "months": revealed.months,
            "created_at": rec["created_at"],
            "resolved_engine": rec["resolved_engine"],
            "decision_stamps": {
                "decision_schema_version": rec.get("decision_schema_version"),
                "decision_alpha_version": rec.get("decision_alpha_version"),
                "twin_definition": rec.get("twin_definition"),
            },
            "artifact_tier": (
                "tier-1 templated wire (build-time, deterministic); "
                "tier-2 letters await the frozen >=95% first-pass bar"
            ),
            "digest_verified": bool(verified),
            "outputs_digest": rec["outputs_digest"],
            "title": narrative.get("title"),
            "tagline": narrative.get("tagline"),
        },
        "revealed": {
            "series_order": series_order,
            "tape": [_round(row) for row in tape],
            "tape_seal": seal_tape(tape),
        },
        "bands": bands,
        # The HOLD-COURSE TWIN's cashflows. Decision-independent by
        # construction — the twin never acts — so it stays pre-authorable at
        # build time (PD-4). The player's own ledger depends on their
        # decisions and is served per-session instead.
        "twin_ledger": _twin_ledger(revealed),
        "summary": {
            "twin_final_value": float(twin.final_value),
            "decision_months": decision_months(revealed.months),
            "episodes": regimes.get("sequence") or [],
            "summary_stats": rec["summary_stats"],
        },
        "feed": {
            "artifacts": build_tier1_feed(
                nw, revealed, base_seed=rec["seed"], n_peer_paths=rec["n_paths"]
            ),
            "dispatches": narrative.get("dispatches") or [],
            "chronicle": [
                {
                    "seq": row["seq"],
                    "type": row["type"],
                    "run_id": row.get("run_id"),
                    "created_at": row["created_at"],
                }
                for row in chronicle_rows
            ],
        },
    }
    return doc


def write_bundle(doc: dict[str, Any], path) -> int:
    """Serialize + gzip; enforce W2's size budget. Returns compressed bytes."""
    from pathlib import Path

    payload = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)  # mtime=0: determinism
    if len(compressed) > MAX_COMPRESSED_BYTES:
        raise BundleError(
            f"bundle is {len(compressed)} bytes compressed, over W2's "
            f"{MAX_COMPRESSED_BYTES}-byte budget — shrink it, do not ship it"
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(compressed)
    return len(compressed)
