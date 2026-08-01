"""Seal and verify pre-registration-g3.yaml — the G3-pre lock (wp3-00).

A thin wrapper over the SEALED Step-2 machinery: hashing and lock-writing are
:func:`ah.eval.prereg.seal` verbatim (composed, never restated — the same
canonicalization, the same lock format, so a reader of one lock can read the
other). What is G3-specific lives here: the judged-source list is read from the
document's own ``seal_scope.hashed_files`` (single source of truth), the mint
refuses while ``sealed: false`` (the W11 review gate), and structural
verification checks the G3 document's own shape — the G2 ``verify()`` checks a
different document and is not reused.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ah.eval import prereg as _prereg
from ah.eval import sleevetails as _sleevetails

__all__ = [
    "G3_LOCK_PATH",
    "G3_PREREG_PATH",
    "G3SealError",
    "seal_g3",
    "verify_g3",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
G3_PREREG_PATH = _REPO_ROOT / "pre-registration-g3.yaml"
G3_LOCK_PATH = _REPO_ROOT / "pre-registration-g3.lock"

#: Statistic names the document must carry per sleeve, in sleevetails' order.
_REQUIRED_STATS = tuple(name for name, _, _ in _sleevetails.STATISTICS)


class G3SealError(RuntimeError):
    """A G3 pre-registration, lock, or mint attempt that violates its contract."""


def _load_doc() -> dict[str, Any]:
    if not G3_PREREG_PATH.exists():
        raise G3SealError(f"{G3_PREREG_PATH.name}: not found")
    doc = yaml.safe_load(G3_PREREG_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise G3SealError(f"{G3_PREREG_PATH.name}: top level must be a mapping")
    return doc


def _judged_sources(doc: dict[str, Any]) -> list[Path]:
    """The seal-scope list, minus the two files prereg.seal hashes on its own.

    ``prereg.seal`` always hashes the document itself and its ``factor_manifest``;
    passing them again would double-hash. Everything else in
    ``seal_scope.hashed_files`` is handed over verbatim — the document's list is
    the single source of truth, and a listed file that does not exist raises
    here rather than being silently skipped.
    """
    listed = doc.get("seal_scope", {}).get("hashed_files")
    if not isinstance(listed, list) or not listed:
        raise G3SealError("seal_scope.hashed_files missing or empty")
    manifest_name = str(doc.get("factor_manifest", "factors.yaml"))
    skip = {G3_PREREG_PATH.name, manifest_name}
    sources: list[Path] = []
    for entry in listed:
        rel = str(entry)
        if rel in skip:
            continue
        path = _REPO_ROOT / rel
        if not path.exists():
            raise G3SealError(
                f"seal_scope lists '{rel}' but it does not exist — a sealed list may "
                "not name phantoms (the RFR-77/-78 lesson)"
            )
        sources.append(path)
    return sources


def structural_check(doc: dict[str, Any]) -> None:
    """The G3 document's own shape rules; raises listing every failure."""
    failures: list[str] = []

    sealed_sleeves = doc.get("sleeve_tail_thresholds")
    if not isinstance(sealed_sleeves, dict) or not sealed_sleeves:
        failures.append("sleeve_tail_thresholds missing or empty")
        sealed_sleeves = {}
    expected = _sleevetails.hf_sleeve_members()
    if set(sealed_sleeves) != set(expected):
        failures.append(
            f"sealed sleeves {sorted(sealed_sleeves)} != judged-code sleeves "
            f"{sorted(expected)} — the document and sleevetails.hf_sleeve_members() "
            "must agree exactly"
        )
    for sleeve_id, block in sealed_sleeves.items():
        members = block.get("members") if isinstance(block, dict) else None
        if sleeve_id in expected and tuple(members or ()) != expected[sleeve_id]:
            failures.append(f"{sleeve_id}: sealed members differ from the taxonomy's")
        for stat, _, severity in _sleevetails.STATISTICS:
            entry = (block or {}).get(stat)
            if not isinstance(entry, dict):
                failures.append(f"{sleeve_id}.{stat}: missing")
                continue
            if entry.get("severity") != severity:
                failures.append(
                    f"{sleeve_id}.{stat}: severity {entry.get('severity')!r} != "
                    f"sleevetails' {severity!r}"
                )
            if not (float(entry["min"]) <= float(entry["max"])):
                failures.append(f"{sleeve_id}.{stat}: min > max")

    criteria = doc.get("episode_2022_criteria")
    if not isinstance(criteria, dict) or "gate_rule" not in criteria:
        failures.append("episode_2022_criteria missing or has no gate_rule")
    if "tier0_beats_rule" not in doc:
        failures.append("tier0_beats_rule missing")
    if "pm_sleeves_structurally_unavailable" not in doc:
        failures.append("pm_sleeves_structurally_unavailable missing")

    if failures:
        raise G3SealError("G3 structural check failed:\n  " + "\n  ".join(failures))


def seal_g3(*, sealed_at: str, dry_run: bool = False) -> str:
    """Mint (or, with ``dry_run``, just compute) the G3 digest.

    A real mint REFUSES while the document says ``sealed: false`` — flipping
    that flag is the owner's act after the W11 pre-seal review, and this
    function enforcing it is what makes the review gate mechanical rather than
    remembered.
    """
    doc = _load_doc()
    structural_check(doc)
    if not dry_run and doc.get("sealed") is not True:
        raise G3SealError(
            "mint refused: pre-registration-g3.yaml says 'sealed: false'. The owner "
            "flips it after the W11 pre-seal review (MPP-A1); nothing else may."
        )
    return _prereg.seal(
        G3_PREREG_PATH,
        out_path=None if dry_run else G3_LOCK_PATH,
        judged_sources=_judged_sources(doc),
        sealed_at=sealed_at,
        dry_run=dry_run,
    )


def verify_g3() -> str:
    """Recompute the digest and compare to the lock; raises on any mismatch."""
    doc = _load_doc()
    structural_check(doc)
    if doc.get("sealed") is not True:
        raise G3SealError("pre-registration-g3.yaml is not sealed; nothing to verify")
    if not G3_LOCK_PATH.exists():
        raise G3SealError(f"{G3_LOCK_PATH.name}: not found — sealed document with no lock")
    import json

    lock = json.loads(G3_LOCK_PATH.read_text(encoding="utf-8"))
    recomputed = seal_g3(sealed_at=str(lock.get("sealed_at", "")), dry_run=True)
    if recomputed != lock.get("digest"):
        raise G3SealError(
            f"digest mismatch: lock says {lock.get('digest')}, files give {recomputed} — "
            "an unamended edit to a sealed G3 file"
        )
    return recomputed
