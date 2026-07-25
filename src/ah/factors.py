"""Factor manifest with a block layer (WP2.1b Item 2 pre-seal patch).

A monolithic factor set means adding a jurisdiction later (a new country's rates and
inflation curve, an FX block) invalidates sealed thresholds wholesale. The block layer
in ``factors.yaml`` makes that addition *additive*: existing per-block thresholds stay
byte-identical and only new per-block + new cross-block thresholds are needed. See
``Instructions/WP2.1b-PRE-SEAL-PATCH.md`` Item 2.

Top-level (a peer of :mod:`ah.splits`), not under ``ah.gen`` or ``ah.eval``: both
packages consume the manifest, and ``ah.gen`` must not depend on ``ah.eval``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "factors.yaml"


class ManifestError(ValueError):
    """Raised when ``factors.yaml`` fails validation."""


@dataclass(frozen=True)
class FactorManifest:
    """Block-structured factor set, loaded from ``factors.yaml``.

    ``blocks`` maps block id -> factor names in declaration order. ``active_blocks``
    is the ordered set of blocks the current campaign runs over; blocks declared in
    ``blocks`` but absent from ``active_blocks`` are inert.
    """

    blocks: Mapping[str, tuple[str, ...]]
    active_blocks: tuple[str, ...]

    def active_factors(self) -> tuple[str, ...]:
        """Factors of active blocks, in block order then declaration order."""
        factors: list[str] = []
        for block in self.active_blocks:
            factors.extend(self.blocks[block])
        return tuple(factors)

    def block_of(self, factor: str) -> str:
        """The block id owning ``factor``. Raises ``KeyError`` if unknown."""
        for block, factors in self.blocks.items():
            if factor in factors:
                return block
        raise KeyError(f"unknown factor '{factor}'")

    def cross_block_pairs(self) -> tuple[tuple[str, str], ...]:
        """Sorted unique pairs of active blocks, each pair itself sorted."""
        active_sorted = sorted(self.active_blocks)
        pairs = [
            (active_sorted[i], active_sorted[j])
            for i in range(len(active_sorted))
            for j in range(i + 1, len(active_sorted))
        ]
        return tuple(pairs)

    def is_active(self, block: str) -> bool:
        return block in self.active_blocks


def _validate(factor_blocks: object, active_blocks: object, source: Path) -> FactorManifest:
    if not isinstance(factor_blocks, dict) or not factor_blocks:
        raise ManifestError(f"{source}: 'factor_blocks' must be a non-empty mapping")
    if not isinstance(active_blocks, list) or not active_blocks:
        raise ManifestError(f"{source}: 'active_blocks' must be a non-empty list")

    blocks: dict[str, tuple[str, ...]] = {}
    seen_factors: dict[str, str] = {}
    for block_id, factors in factor_blocks.items():
        if not isinstance(block_id, str) or not block_id:
            raise ManifestError(f"{source}: block ids must be non-empty strings, got {block_id!r}")
        if not isinstance(factors, list) or not factors:
            raise ManifestError(f"{source}: block '{block_id}' must be a non-empty list of factors")
        factor_tuple: list[str] = []
        for factor in factors:
            if not isinstance(factor, str) or not factor:
                raise ManifestError(
                    f"{source}: factor names must be non-empty strings, got {factor!r}"
                )
            if factor in seen_factors:
                raise ManifestError(
                    f"{source}: factor '{factor}' appears in both "
                    f"'{seen_factors[factor]}' and '{block_id}'"
                )
            seen_factors[factor] = block_id
            factor_tuple.append(factor)
        blocks[block_id] = tuple(factor_tuple)

    for block_id in active_blocks:
        if not isinstance(block_id, str) or not block_id:
            raise ManifestError(f"{source}: active_blocks entries must be non-empty strings")
        if block_id not in blocks:
            raise ManifestError(f"{source}: active_blocks references unknown block '{block_id}'")

    return FactorManifest(blocks=blocks, active_blocks=tuple(active_blocks))


@cache
def _load_manifest_cached(resolved_path: Path) -> FactorManifest:
    doc = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    factor_blocks = doc.get("factor_blocks")
    active_blocks = doc.get("active_blocks")
    return _validate(factor_blocks, active_blocks, resolved_path)


def load_manifest(path: Path | None = None) -> FactorManifest:
    """Load and validate the factor manifest, defaulting to the repo-root ``factors.yaml``.

    Cached by resolved path so repeated calls for the same file return the *same*
    :class:`FactorManifest` object (identity, not just equality).
    """
    resolved = (path if path is not None else _DEFAULT_PATH).resolve()
    return _load_manifest_cached(resolved)
