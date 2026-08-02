"""Seal and verify step5-evaluation-protocol.yaml — the G5 lock (wp5-00).

The G3 wrapper's pattern, third use: hashing and lock-writing are
:func:`ah.eval.prereg.seal` verbatim; the judged-source list is the
document's own ``seal_scope.hashed_files``; the mint refuses while
``sealed: false``. G5-specific structure checked here: the primary metric
is pre-stated and every named metric resolves to a callable in
:mod:`ah.eval.decision_metrics`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ah.eval import decision_metrics as _metrics
from ah.eval import prereg as _prereg

__all__ = ["G5_LOCK_PATH", "G5_PROTOCOL_PATH", "G5SealError", "seal_g5", "verify_g5"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
G5_PROTOCOL_PATH = _REPO_ROOT / "step5-evaluation-protocol.yaml"
G5_LOCK_PATH = _REPO_ROOT / "pre-registration-g5.lock"


class G5SealError(RuntimeError):
    """A G5 protocol, lock, or mint attempt that violates its contract."""


def _load_doc() -> dict[str, Any]:
    if not G5_PROTOCOL_PATH.exists():
        raise G5SealError(f"{G5_PROTOCOL_PATH.name}: not found")
    doc = yaml.safe_load(G5_PROTOCOL_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise G5SealError(f"{G5_PROTOCOL_PATH.name}: top level must be a mapping")
    return doc


def _check_structure(doc: dict[str, Any]) -> None:
    metrics_block = doc.get("metrics", {})
    primary = metrics_block.get("primary")
    if primary != _metrics.PRIMARY_METRIC:
        raise G5SealError(
            f"primary metric mismatch: document says {primary!r}, code says "
            f"{_metrics.PRIMARY_METRIC!r}"
        )
    named = [primary, *metrics_block.get("secondary", [])]
    missing = [
        m
        for m in named
        if m not in ("calibration",)  # battery-tier carryover, defined in Step 2
        and not callable(getattr(_metrics, m, None))
    ]
    if missing:
        raise G5SealError(f"metrics named but not defined in decision_metrics: {missing}")
    if doc.get("decision_alpha_version") != _metrics.DECISION_ALPHA_VERSION:
        raise G5SealError("decision_alpha_version disagrees between document and code")


def _judged_sources(doc: dict[str, Any]) -> list[Path]:
    files = doc.get("seal_scope", {}).get("hashed_files", [])
    if not files:
        raise G5SealError("seal_scope.hashed_files is empty")
    paths = []
    for rel in files:
        if rel == G5_PROTOCOL_PATH.name:
            continue  # prereg.seal hashes the document itself
        p = _REPO_ROOT / rel
        if not p.exists():
            raise G5SealError(f"seal_scope lists missing file {rel}")
        paths.append(p)
    return paths


def seal_g5(*, sealed_at: str, dry_run: bool = False) -> str:
    """Mint (or, with ``dry_run``, just compute) the G5 digest.

    A real mint refuses while the document says ``sealed: false`` — the
    owner's 2026-08-02 order to freeze is what flipped it.
    """
    doc = _load_doc()
    _check_structure(doc)
    if not dry_run and doc.get("sealed") is not True:
        raise G5SealError("mint refused: step5-evaluation-protocol.yaml says sealed: false")
    return _prereg.seal(
        G5_PROTOCOL_PATH,
        out_path=None if dry_run else G5_LOCK_PATH,
        judged_sources=_judged_sources(doc),
        sealed_at=sealed_at,
        dry_run=dry_run,
    )


def verify_g5() -> str:
    """Recompute the digest and compare to the lock; raises on any mismatch."""
    doc = _load_doc()
    _check_structure(doc)
    if not G5_LOCK_PATH.exists():
        raise G5SealError(f"{G5_LOCK_PATH.name}: not found — sealed document with no lock")
    import json

    lock = json.loads(G5_LOCK_PATH.read_text(encoding="utf-8"))
    recomputed = seal_g5(sealed_at=str(lock.get("sealed_at", "")), dry_run=True)
    if recomputed != lock.get("digest"):
        raise G5SealError(
            f"digest mismatch: lock says {lock.get('digest')}, files give {recomputed} — "
            "an unamended edit to a sealed G5 file"
        )
    return recomputed
