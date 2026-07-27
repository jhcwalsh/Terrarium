"""Factor manifest with a block layer (WP2.1b Item 2 pre-seal patch) and the
factor -> Step-1 catalog series mapping (WP2.2 Task 1).

A monolithic factor set means adding a jurisdiction later (a new country's rates and
inflation curve, an FX block) invalidates sealed thresholds wholesale. The block layer
in ``factors.yaml`` makes that addition *additive*: existing per-block thresholds stay
byte-identical and only new per-block + new cross-block thresholds are needed. See
``Instructions/WP2.1b-PRE-SEAL-PATCH.md`` Item 2.

``factors.yaml``'s ``factor_sources`` section (WP2.2 Task 1) is the mapping this
project lacked entirely before: a factor id (``equity_mkt``, ``ust_10y``, ...) on its
own names nothing in the Step-1 catalog. Every declared factor, in every block
(including the inactive ``uk`` block), has exactly one :class:`FactorSource` entry --
``kind: series`` (read one ``requirements.yaml`` series id directly), ``kind: derived``
(compute from one or more series ids via an existing ``ah.data.derive`` helper), or
``kind: unavailable`` (no honest source exists; ``reason`` names the governing
record). :meth:`FactorManifest.series_id_for` and :meth:`FactorManifest.is_available`
are the read surface ``ah.eval.reference``, ``ah.eval.panel`` and later work consume;
see ``ah/eval/panel.py`` for how a ``derived`` entry is actually computed.

Top-level (a peer of :mod:`ah.splits`), not under ``ah.gen`` or ``ah.eval``: both
packages consume the manifest, and ``ah.gen`` must not depend on ``ah.eval``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "factors.yaml"

_SOURCE_KINDS = frozenset({"series", "derived", "unavailable"})

# The numeraire a return-bearing factor is quoted on (see FactorSource). `zero_cost` is
# a self-financing / long-short overlay: it commits no capital, so it is numeraire-
# neutral and may be combined with total-return legs. `excess_return` is a
# capital-committing leg quoted net of a rate -- the actual error this vocabulary
# exists to make visible, and `ah.strategies` refuses to weight one in a D4 portfolio.
_NUMERAIRES = frozenset({"total_return", "excess_return", "zero_cost"})


class ManifestError(ValueError):
    """Raised when ``factors.yaml`` fails validation."""


@dataclass(frozen=True)
class FactorSource:
    """How one factor is obtained from Step-1 data (``factors.yaml``'s ``factor_sources``).

    Exactly one shape per ``kind``:

    - ``series``: ``series_id`` and ``units`` are set; ``expr``/``inputs``/``reason``
      are ``None``/``()``. The factor is ``access.train_val(series_id)`` verbatim, no
      transform.
    - ``derived``: ``expr`` (an ``ah.data.derive`` function name) and ``inputs`` (the
      requirements.yaml series ids, positional, in the order that helper expects) and
      ``units`` are set; ``series_id``/``reason`` are ``None``.
    - ``unavailable``: ``reason`` is set (non-empty, names the governing record); every
      other field is ``None``/``()`` -- there is no series, derived or otherwise.

    Three fields cut across all three kinds:

    - ``numeraire`` -- ``total_return``, ``excess_return`` or ``zero_cost``, declared
      for a return-bearing factor and absent for a level (a level has no numeraire).
      This is the machine-checked half of ``pre-registration.yaml``'s
      ``conventions.numeraire``: ``ah.strategies`` refuses to load a D4 strategy whose
      legs do not all resolve to the sealed numeraire (or to a declared zero-cost
      overlay), which is what stops an excess-return equity leg being weighted beside a
      total-return bond leg. On a ``kind: unavailable`` entry it records the numeraire
      D4 *assumes* the factor will carry once a source is registered.
    - ``proxy`` / ``proxy_for`` -- set together, and only together. ``proxy: true``
      means a substitution or splice-backed backfill is in play for this factor and
      ``proxy_for`` names it (donor series plus the governing ``ah.data.splice`` rule).
      Machine-visible on purpose: before this, a splice-backed backfill was free text
      inside ``notes``, invisible to any check.
    """

    kind: str
    units: str | None = None
    series_id: str | None = None
    expr: str | None = None
    inputs: tuple[str, ...] = ()
    reason: str | None = None
    notes: str | None = None
    numeraire: str | None = None
    proxy: bool = False
    proxy_for: str | None = None


@dataclass(frozen=True)
class FactorManifest:
    """Block-structured factor set, loaded from ``factors.yaml``.

    ``blocks`` maps block id -> factor names in declaration order. ``active_blocks``
    is the ordered set of blocks the current campaign runs over; blocks declared in
    ``blocks`` but absent from ``active_blocks`` are inert. ``sources`` maps every
    declared factor (every block, active or not) to its :class:`FactorSource`.
    """

    blocks: Mapping[str, tuple[str, ...]]
    active_blocks: tuple[str, ...]
    sources: Mapping[str, FactorSource]

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

    def is_available(self, factor: str) -> bool:
        """Whether ``factor`` has a real (non-``unavailable``) Step-1 source.

        Raises ``KeyError`` if ``factor`` is not declared in any block.
        """
        return self.sources[factor].kind != "unavailable"

    def series_id_for(self, factor: str) -> str:
        """The single catalog series id backing a directly-sourced (``kind: series``) factor.

        Raises ``KeyError`` if ``factor`` is not declared, and ``ValueError`` if it is
        declared but not ``kind: series`` (a ``derived`` factor has multiple ``inputs``
        and no single series id; an ``unavailable`` factor has none at all -- both
        cases must be handled via :attr:`FactorManifest.sources` directly, not this
        method, which is deliberately narrow).
        """
        source = self.sources[factor]
        if source.kind != "series":
            raise ValueError(
                f"factor '{factor}' is not a direct series (kind={source.kind!r}); "
                f"series_id_for() only applies to kind='series' factors -- read "
                f"manifest.sources['{factor}'] directly for 'derived'/'unavailable'"
            )
        assert source.series_id is not None  # invariant of a validated 'series' entry
        return source.series_id


def _validate_sources(
    factor_sources: object, blocks: Mapping[str, tuple[str, ...]], source: Path
) -> dict[str, FactorSource]:
    """Parse and validate ``factor_sources`` against the already-validated ``blocks``.

    Every factor declared in any block (active or not) must have exactly one entry;
    every entry must name a factor some block actually declares. Each entry's shape is
    checked against its ``kind`` (see :class:`FactorSource`'s docstring for the three
    shapes) -- a ``kind: series`` entry carrying a stray ``reason``, or a ``kind:
    unavailable`` entry carrying a ``series_id``, is rejected rather than silently
    accepted, because a sealed mapping with an ambiguous shape is worse than one that
    fails to load at all.
    """
    if not isinstance(factor_sources, dict) or not factor_sources:
        raise ManifestError(f"{source}: 'factor_sources' must be a non-empty mapping")

    all_factors = {f for factors in blocks.values() for f in factors}

    unknown = sorted(set(factor_sources) - all_factors)
    if unknown:
        raise ManifestError(
            f"{source}: factor_sources names factor(s) {unknown} that no "
            f"factor_blocks entry declares"
        )
    missing = sorted(all_factors - set(factor_sources))
    if missing:
        raise ManifestError(
            f"{source}: factor_sources is missing entry(ies) for declared factor(s) {missing}"
        )

    sources: dict[str, FactorSource] = {}
    for factor, entry in factor_sources.items():
        if not isinstance(entry, dict):
            raise ManifestError(f"{source}: factor_sources.{factor} must be a mapping")

        kind = entry.get("kind")
        if kind not in _SOURCE_KINDS:
            raise ManifestError(
                f"{source}: factor_sources.{factor}.kind must be one of "
                f"{sorted(_SOURCE_KINDS)}, got {kind!r}"
            )
        units = entry.get("units")
        series_id = entry.get("series_id")
        expr = entry.get("expr")
        raw_inputs = entry.get("inputs")
        reason = entry.get("reason")
        notes = entry.get("notes")
        numeraire = entry.get("numeraire")
        proxy = entry.get("proxy", False)
        proxy_for = entry.get("proxy_for")
        if notes is not None and (not isinstance(notes, str) or not notes):
            raise ManifestError(
                f"{source}: factor_sources.{factor}.notes must be a non-empty string when given"
            )
        if numeraire is not None and numeraire not in _NUMERAIRES:
            raise ManifestError(
                f"{source}: factor_sources.{factor}.numeraire must be one of "
                f"{sorted(_NUMERAIRES)} when given, got {numeraire!r}"
            )
        if not isinstance(proxy, bool):
            raise ManifestError(
                f"{source}: factor_sources.{factor}.proxy must be a boolean, got {proxy!r}"
            )
        if proxy and (not isinstance(proxy_for, str) or not proxy_for):
            raise ManifestError(
                f"{source}: factor_sources.{factor} sets proxy: true but no non-empty "
                f"'proxy_for' naming what is being substituted"
            )
        if proxy_for is not None and not proxy:
            raise ManifestError(
                f"{source}: factor_sources.{factor} sets 'proxy_for' without 'proxy: true'; "
                f"a substitution must be flagged, not merely described"
            )

        if kind == "series":
            if not isinstance(series_id, str) or not series_id:
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=series) needs a non-empty 'series_id'"
                )
            if not isinstance(units, str) or not units:
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=series) needs a non-empty 'units'"
                )
            if expr is not None or raw_inputs is not None or reason is not None:
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=series) must not set "
                    f"'expr'/'inputs'/'reason'"
                )
            inputs: tuple[str, ...] = ()
        elif kind == "derived":
            if not isinstance(expr, str) or not expr:
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=derived) needs a non-empty 'expr'"
                )
            if (
                not isinstance(raw_inputs, list)
                or not raw_inputs
                or not all(isinstance(i, str) and i for i in raw_inputs)
            ):
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=derived) needs a non-empty "
                    f"list of non-empty 'inputs'"
                )
            if not isinstance(units, str) or not units:
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=derived) needs a non-empty 'units'"
                )
            if series_id is not None or reason is not None:
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=derived) must not set "
                    f"'series_id'/'reason'"
                )
            inputs = tuple(raw_inputs)
        else:  # kind == "unavailable"
            if not isinstance(reason, str) or not reason:
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=unavailable) needs a "
                    f"non-empty 'reason'"
                )
            if (
                series_id is not None
                or expr is not None
                or raw_inputs is not None
                or units is not None
            ):
                raise ManifestError(
                    f"{source}: factor_sources.{factor} (kind=unavailable) must not set "
                    f"'series_id'/'units'/'expr'/'inputs'"
                )
            inputs = ()

        sources[factor] = FactorSource(
            kind=kind,
            units=units if isinstance(units, str) else None,
            series_id=series_id if isinstance(series_id, str) else None,
            expr=expr if isinstance(expr, str) else None,
            inputs=inputs,
            reason=reason if isinstance(reason, str) else None,
            notes=notes if isinstance(notes, str) else None,
            numeraire=numeraire if isinstance(numeraire, str) else None,
            proxy=proxy,
            proxy_for=proxy_for if isinstance(proxy_for, str) else None,
        )
    return sources


def _validate(
    factor_blocks: object, active_blocks: object, factor_sources: object, source: Path
) -> FactorManifest:
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
            raise ManifestError(
                f"{source}: active_blocks entries must be non-empty strings, got {block_id!r}"
            )
        if block_id not in blocks:
            raise ManifestError(f"{source}: active_blocks references unknown block '{block_id}'")

    sources = _validate_sources(factor_sources, blocks, source)

    return FactorManifest(
        blocks=MappingProxyType(blocks),
        active_blocks=tuple(active_blocks),
        sources=MappingProxyType(sources),
    )


@cache
def _load_manifest_cached(resolved_path: Path) -> FactorManifest:
    doc = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    factor_blocks = doc.get("factor_blocks")
    active_blocks = doc.get("active_blocks")
    factor_sources = doc.get("factor_sources")
    return _validate(factor_blocks, active_blocks, factor_sources, source=resolved_path)


def load_manifest(path: Path | None = None) -> FactorManifest:
    """Load and validate the factor manifest, defaulting to the repo-root ``factors.yaml``.

    Cached by resolved path so repeated calls for the same file return the *same*
    :class:`FactorManifest` object (identity, not just equality).
    """
    resolved = (path if path is not None else _DEFAULT_PATH).resolve()
    return _load_manifest_cached(resolved)
