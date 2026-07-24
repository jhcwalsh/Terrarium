"""Canonical serialization + SHA-256 digests (STEP0-PLAN §WP0.6, §6).

Two jobs, one home:

* **Numeric output digests** — hash the engine's path tensors. Values are float64,
  rounded to 12 decimals before hashing, so the digest is stable across platforms
  (the float-determinism guard from STEP0-PLAN §6). Order is fixed by the engine's
  ``ASSETS`` / ``REPORTED_SLEEVES`` tuples.
* **Canonical JSON** — sorted keys, compact separators, ``repr``-based float
  formatting (Python's ``json`` already emits shortest-round-trip floats). Used for
  stable storage and for comparing engine-consumed world fields.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

import numpy as np

from ah.core.engine import ASSETS, REPORTED_SLEEVES, EnginePaths, EnsembleResult

_DECIMALS = 12


def sha256_of_arrays(arrays: Iterable[Any], *, decimals: int = _DECIMALS) -> str:
    """SHA-256 over concatenated float64 arrays, rounded to ``decimals`` places."""
    h = hashlib.sha256()
    for a in arrays:
        arr = np.ascontiguousarray(np.round(np.asarray(a, dtype=np.float64), decimals))
        h.update(arr.tobytes())
    return "sha256:" + h.hexdigest()


def digest_paths(paths: EnginePaths) -> str:
    """Digest a single simulated history (factor paths + returns + reported marks)."""
    arrays: list[Any] = [paths.rate, paths.spread, paths.inflation, paths.crisis]
    arrays += [paths.returns[a] for a in ASSETS]
    arrays += [paths.reported[a] for a in REPORTED_SLEEVES]
    return sha256_of_arrays(arrays)


def digest_ensemble(result: EnsembleResult) -> str:
    """Digest an ensemble's return + reported tensors (the run's output tensor)."""
    arrays: list[Any] = [result.returns[a] for a in ASSETS]
    arrays += [result.reported[a] for a in REPORTED_SLEEVES]
    return sha256_of_arrays(arrays)


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact, shortest-round-trip floats."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
