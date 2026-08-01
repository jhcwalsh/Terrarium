"""The generator-output contract: Ensemble -> schema-valid document (WP2R.4).

``schemas/generator-output-v1.0.schema.json`` is the frozen contract for what a
generator emits. This module is its only producer: :func:`build_document` turns
an :class:`~ah.gen.base.Ensemble` into the contract document, and
:func:`validate_document` checks any document against the schema. Tensors are
never embedded — each is pinned by shape/dtype/sha256 through
:func:`ah.core.digest.sha256_of_arrays`, the same canonical rounding RunRecords
rely on, so :func:`verify_arrays` can re-derive every digest from the arrays.

Absence is a statement. A generator with no regime path or no slow-state layer
declares :class:`~ah.gen.base.AbsentLayer` with a reason at construction; a bare
``None`` means the generator has not adopted the contract, and
:func:`build_document` raises rather than inventing a reason on its behalf.

The factor namespace (name/block/kind/units/identity) is *copied* from the
sealed factor manifest (``factors.yaml``) and ``requirements.yaml`` at build
time — this module reads both and edits neither. The copy being faithful is
asserted by a test, not trusted.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np

from ah.core.digest import sha256_of_arrays
from ah.data.manifest import requirements
from ah.factors import FactorManifest, load_manifest
from ah.gen.base import Ensemble, RegimeRecord, SlowStateRecord

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_PATH",
    "OutputContractError",
    "build_document",
    "validate_document",
    "verify_arrays",
]

CONTRACT_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[3]  # src/ah/gen -> repo root
SCHEMA_PATH = _REPO_ROOT / "schemas" / "generator-output-v1.0.schema.json"


class OutputContractError(RuntimeError):
    """An ensemble or document that does not satisfy the generator-output contract."""


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def validate_document(document: dict[str, Any]) -> None:
    """Raise :class:`OutputContractError` unless ``document`` satisfies the schema."""
    validator = jsonschema.Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise OutputContractError(
            f"generator-output document violates the contract at {where}: {first.message}"
            + (f" (+{len(errors) - 1} more)" if len(errors) > 1 else "")
        )


def _json_safe(obj: Any) -> Any:
    """Conditioning records arrive with numpy scalars and tuples; JSON knows neither."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def _tensor(array: np.ndarray) -> dict[str, Any]:
    return {
        "shape": [int(s) for s in array.shape],
        "dtype": str(array.dtype),
        "sha256": sha256_of_arrays([array]),
    }


def _factor_entries(factor_names: list[str], manifest: FactorManifest) -> list[dict[str, Any]]:
    """The namespace block: manifest + requirements copied, per emitted column."""
    series_registry = requirements()
    block_of: dict[str, str] = {}
    for block, names in manifest.blocks.items():
        for name in names:
            block_of[name] = block

    entries: list[dict[str, Any]] = []
    for name in factor_names:
        source = manifest.sources.get(name)
        block = block_of.get(name)
        if source is None or block is None:
            raise OutputContractError(
                f"ensemble carries factor '{name}' that the factor manifest does not declare"
            )
        units: str | None
        identity: dict[str, Any] | None = None
        if source.kind == "series":
            series_id = source.series_id or ""
            series = series_registry.get(series_id)
            if series is None:
                raise OutputContractError(
                    f"factor '{name}' names series '{series_id}' absent from requirements.yaml"
                )
            units = series.units
        elif source.kind == "derived":
            units = source.units
            identity = {"expr": source.expr, "inputs": list(source.inputs)}
        else:  # unavailable
            units = None
        entries.append(
            {
                "name": name,
                "block": block,
                "kind": source.kind,
                "units": units,
                "identity": identity,
            }
        )
    return entries


def _absent(reason: str) -> dict[str, Any]:
    return {"absent": True, "reason": reason}


def build_document(ensemble: Ensemble, *, manifest: FactorManifest | None = None) -> dict[str, Any]:
    """The generator-output contract document for ``ensemble``, validated before return.

    Raises :class:`OutputContractError` if the ensemble's ``regimes`` or
    ``slow_states`` is a bare ``None`` — a generator adopting the contract must
    either produce the layer or declare :class:`~ah.gen.base.AbsentLayer` with
    its own reason.
    """
    meta = ensemble.meta
    manifest = load_manifest() if manifest is None else manifest

    if ensemble.regimes is None:
        raise OutputContractError(
            f"{meta.generator_id} emitted no regime record and no AbsentLayer reason; "
            "the output contract refuses silent omission"
        )
    if ensemble.slow_states is None:
        raise OutputContractError(
            f"{meta.generator_id} emitted no slow-state record and no AbsentLayer reason; "
            "the output contract refuses silent omission"
        )

    regimes_block: dict[str, Any]
    regime_tensor: dict[str, Any] | None
    if isinstance(ensemble.regimes, RegimeRecord):
        regimes_block = {
            "labels_legend": list(ensemble.regimes.legend),
            "mode": ensemble.regimes.mode,
            "ruleset_version": ensemble.regimes.ruleset_version,
        }
        regime_tensor = _tensor(ensemble.regimes.labels)
    else:
        regimes_block = _absent(ensemble.regimes.reason)
        regime_tensor = None

    slow_block: dict[str, Any]
    slow_tensor: dict[str, Any] | None
    if isinstance(ensemble.slow_states, SlowStateRecord):
        slow_block = {
            "names": list(ensemble.slow_states.names),
            "layer": ensemble.slow_states.layer,
        }
        slow_tensor = _tensor(ensemble.slow_states.states)
    else:
        slow_block = _absent(ensemble.slow_states.reason)
        slow_tensor = None

    conditioning = _json_safe(meta.conditioning)
    diagnostic_keys = ("reconciliation", "support", "waypoint_tolerance", "acceptance_filter")
    if all(key in conditioning for key in diagnostic_keys):
        diagnostics: dict[str, Any] = {
            "waypoints_bound": bool(conditioning.get("waypoints_bound", True)),
            **{key: conditioning[key] for key in diagnostic_keys},
        }
    else:
        # Mechanical and factual: the reason describes exactly what is true of
        # the emitted conditioning record, not a judgement about the generator.
        diagnostics = _absent(
            f"{meta.generator_id} emitted no joinery diagnostics (no "
            "reconciliation/support/waypoint-tolerance/acceptance-filter record "
            "in its conditioning)"
        )

    document = {
        "contract_version": CONTRACT_VERSION,
        "provenance": {
            "generator_id": meta.generator_id,
            "checkpoint_hash": meta.checkpoint_hash,
            "config_hash": meta.config_hash,
            "vintage_id": meta.vintage_id,
            "seed": int(meta.seed),
            "active_blocks": list(meta.active_blocks),
        },
        "shape": {
            "n_paths": ensemble.n_paths,
            "months": ensemble.months,
            "n_factors": len(ensemble.factor_names),
        },
        "factors": _factor_entries(ensemble.factor_names, manifest),
        "arrays": {
            "paths": _tensor(ensemble.paths),
            "regime_labels": regime_tensor,
            "slow_states": slow_tensor,
        },
        "regimes": regimes_block,
        "slow_states": slow_block,
        "diagnostics": diagnostics,
        "conditioning": conditioning,
    }
    validate_document(document)
    return document


def verify_arrays(ensemble: Ensemble, document: dict[str, Any]) -> None:
    """Re-derive every tensor digest in ``document`` from ``ensemble``'s arrays.

    Raises :class:`OutputContractError` on the first mismatch — a document that
    does not describe these arrays is not this ensemble's document.
    """
    described = document.get("arrays", {})
    actual: dict[str, np.ndarray | None] = {
        "paths": ensemble.paths,
        "regime_labels": (
            ensemble.regimes.labels if isinstance(ensemble.regimes, RegimeRecord) else None
        ),
        "slow_states": (
            ensemble.slow_states.states
            if isinstance(ensemble.slow_states, SlowStateRecord)
            else None
        ),
    }
    for name, array in actual.items():
        descriptor = described.get(name)
        if array is None:
            if descriptor is not None:
                raise OutputContractError(
                    f"document describes tensor '{name}' but the ensemble does not carry it"
                )
            continue
        if descriptor is None:
            raise OutputContractError(
                f"ensemble carries tensor '{name}' but the document does not describe it"
            )
        recomputed = _tensor(array)
        if recomputed != descriptor:
            raise OutputContractError(
                f"tensor '{name}' does not match its descriptor: document says "
                f"{descriptor}, arrays give {recomputed}"
            )
