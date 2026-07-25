"""The reference panel reader (WP2.2 Task 1).

A thin, testable layer between the campaign catalog (:mod:`ah.splits`) and
:mod:`ah.eval.reference`: it turns a :class:`~ah.factors.FactorManifest` into a single
date-indexed frame of every **available, active** factor, in the units the manifest's
``factor_sources`` declares, reusing :mod:`ah.data.derive`'s existing helpers for
``kind: derived`` factors rather than reimplementing them here.

**Never reads the holdout.** This module receives a :class:`~ah.splits.DataAccess` and
reads it exclusively through the ``split_reader`` hook, which defaults to
:meth:`~ah.splits.DataAccess.train_val` -- the same sanctioned reference surface
:mod:`ah.eval.reference` uses, and for the same reason: reference statistics (and
anything built on top of this panel) must never see the touch-once holdout. There is no
code path here by which a :class:`~ah.splits.FinalEvaluationToken` could reach
:meth:`~ah.splits.DataAccess.frame` even if a caller tried to hand one in -- this module
never constructs or imports one (``ah.eval.g2`` is the only sanctioned mint).

Two kinds of "missing", never conflated
---------------------------------------
An earlier version of this module recorded one flat ``missing`` tuple, which merged two
outcomes that must be told apart:

- **declared unavailable** (:attr:`FactorFrames.missing_declared`): the manifest itself
  says no honest source exists -- ``kind: unavailable``. ``commodities`` is the live
  example. Expected, governed by a retrofit-register row, and not a surprise.
- **declared available, no data** (:attr:`FactorFrames.missing_no_data`): the manifest
  names a real series id (or derived inputs) and the reader returned nothing for it in
  train+validation. This is *not* expected and is the dangerous case: FRED serves only
  ~3 years of ``BAMLH0A0HYM2``, so a non-splice-aware read leaves ``hy_spread`` silently
  joining ``commodities`` in a flat ``missing`` list, and WP2.3 would seal bands over a
  panel quietly lacking a factor. It is reported separately, surfaced in
  :class:`ah.eval.battery.BatteryReport`, and recorded on
  :class:`ah.eval.reference.ReferenceStats`.

Neither is raised: a data gap is a fact about the world, not a bug. But only one of them
is *routine*, and a consumer that cannot tell them apart cannot notice the other.

Assembly
--------
Every available factor's frame is joined into one wide panel via
:func:`ah.data.derive.assemble_panel` (outer join on date, asserting no gaps after each
column's own first observation) -- the same helper Step 1's own panel assembly (WP1.6)
uses, reused rather than reimplemented. If every active factor turns out to be missing,
the panel is an empty, dateless frame rather than an error from ``assemble_panel`` on
zero columns.

The read surface is shared with :mod:`ah.eval.reference`
---------------------------------------------------------
:func:`read_factor_frames` is the single place a :class:`~ah.factors.FactorManifest`'s
``factor_sources`` mapping is turned into per-factor ``(date, value)`` frames.
:func:`build_panel` calls it and then assembles; :func:`ah.eval.reference.compute_reference`
calls it and then computes statistics per factor *without* assembling (its statistics are
deliberately not aligned onto one shared date axis -- see that module's "Data alignment"
section). Both therefore resolve ``series``/``derived``/``unavailable`` entries through
exactly the same code, which is what closes the WP2.2-Task-1 defect where
``compute_reference`` defaulted to an identity factor-id-to-series-id map and silently
produced an empty reference.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import pandas as pd

from ah.data import derive
from ah.factors import FactorManifest, FactorSource
from ah.splits import DataAccess

SplitReader = Callable[[DataAccess, str], pd.DataFrame]

# The canonical ``(date, value)`` columns every reader frame must carry. A frame that is
# non-empty but lacks them is a bug, not a data gap (see _read_series).
_REQUIRED_COLUMNS = frozenset({"date", "value"})


class PanelError(RuntimeError):
    """Raised when a factor's declared source cannot honestly be turned into a frame.

    Never raised for a legitimate data gap (see the module docstring) -- only for a
    malformed ``factor_sources`` entry that ``ah.factors.load_manifest`` should have
    rejected already (an unknown ``expr``, or an ``inputs`` arity that ``expr``'s
    helper does not accept), or for a frame that came back non-empty but without the
    canonical ``date``/``value`` columns. Those are bugs, not gaps.
    """


def default_split_reader(access: DataAccess, series_id: str) -> pd.DataFrame:
    """The sanctioned reference surface: train+validation only, never the holdout."""
    return access.train_val(series_id)


# Kept as a private alias for the module's own default-argument bindings; the public
# name above is what ah.eval.reference and tests reference.
_default_split_reader = default_split_reader


@dataclass(frozen=True)
class DerivedExpr:
    """One ``kind: derived`` transform: its helper, its arity, and its units algebra.

    ``units_rule`` states what the transform does to its inputs' units, so a declared
    ``units`` in ``factors.yaml`` can be checked against the units
    ``requirements.yaml`` registers for the transform's inputs instead of being taken
    on trust (``ig_spread: units: idx`` would otherwise pass everything). ``"same"``
    means every input must share one unit and the output carries it -- the only algebra
    any transform registered today needs; a future transform that changes units (a
    ratio, a log) registers its own rule here rather than opting out of the check.
    """

    arity: int
    fn: Callable[[list[pd.DataFrame]], pd.DataFrame]
    units_rule: str = "same"


# Each derived expr's ah.data.derive helper and the exact number of positional
# `inputs` it expects, in order. A fixed, explicit table -- not a generic
# getattr(derive, expr) dispatch -- so an unknown expr in factors.yaml fails here with
# a named error rather than an AttributeError several frames deep, and so the arity of
# each helper is asserted once, in one place, rather than left to blow up inside
# ah.data.derive itself with a confusing positional-argument message.
_DERIVED_EXPRS: dict[str, DerivedExpr] = {
    "add": DerivedExpr(2, lambda frames: derive.add(frames[0], frames[1])),
    "difference": DerivedExpr(2, lambda frames: derive.difference(frames[0], frames[1])),
    "funding_stress": DerivedExpr(1, lambda frames: derive.funding_stress(frames[0])),
}


def expected_derived_units(expr: str, input_units: tuple[str, ...]) -> str:
    """The units a ``kind: derived`` factor must declare, given its inputs' units.

    Raises :class:`PanelError` for an unknown ``expr``, a wrong number of inputs, or --
    under the ``"same"`` units rule -- inputs whose units disagree (differencing a
    percent rate from an index is a units error, not a spread). Used by
    ``tests/test_factors.py`` to check every committed ``derived`` entry against
    ``requirements.yaml``'s own registered units.
    """
    spec = _DERIVED_EXPRS.get(expr)
    if spec is None:
        raise PanelError(f"unknown derived expr '{expr}'; known: {sorted(_DERIVED_EXPRS)}")
    if len(input_units) != spec.arity:
        raise PanelError(
            f"derived expr '{expr}' expects {spec.arity} input(s), got {len(input_units)}"
        )
    if spec.units_rule != "same":  # pragma: no cover - no other rule is registered yet
        raise PanelError(f"derived expr '{expr}' has unknown units_rule '{spec.units_rule}'")
    distinct = sorted(set(input_units))
    if len(distinct) != 1:
        raise PanelError(
            f"derived expr '{expr}' combines inputs of differing units {distinct}; its "
            f"units rule is 'same', so every input must carry one unit"
        )
    return distinct[0]


def _read_series(
    access: DataAccess, series_id: str, split_reader: SplitReader, *, factor: str
) -> pd.DataFrame | None:
    """``split_reader(access, series_id)``, or ``None`` for an unknown/empty series.

    ``None`` is the "missing, not an error" contract: it covers both a series id the
    reader does not know (``KeyError``) and one that is known but has zero rows in
    train+validation. A frame that *is* non-empty but lacks the canonical
    ``date``/``value`` columns is a different failure mode entirely -- a bug, not a gap
    -- and raises :class:`PanelError` naming the factor and series id rather than
    letting an anonymous ``KeyError`` surface from deep inside pandas.
    """
    try:
        frame = split_reader(access, series_id)
    except KeyError:
        return None
    if frame.empty:
        return None
    missing_cols = _REQUIRED_COLUMNS - set(frame.columns)
    if missing_cols:
        raise PanelError(
            f"factor '{factor}' (series_id '{series_id}'): train_val frame is missing "
            f"required column(s) {sorted(missing_cols)}"
        )
    return frame


def _compute_derived(
    source: FactorSource, factor: str, input_frames: list[pd.DataFrame]
) -> pd.DataFrame:
    assert source.expr is not None
    spec = _DERIVED_EXPRS.get(source.expr)
    if spec is None:
        raise PanelError(
            f"factor '{factor}': unknown derived expr '{source.expr}'; known: "
            f"{sorted(_DERIVED_EXPRS)}"
        )
    if len(input_frames) != spec.arity:
        raise PanelError(
            f"factor '{factor}': derived expr '{source.expr}' expects "
            f"{spec.arity} input(s), got {len(input_frames)}"
        )
    output = spec.fn(input_frames)
    # Defence in depth (WP2.2 Task 1 fix pass, MINOR 4): every _DERIVED_EXPRS helper
    # today returns ah.data.derive's own _frame(), which always carries exactly
    # date/value, so this never fires yet -- but _read_series validates the same
    # contract on every *input* frame, and a future DerivedExpr entry could easily
    # return something else. Checking the output closes that hole the same way.
    if not isinstance(output, pd.DataFrame):
        raise PanelError(
            f"factor '{factor}': derived expr '{source.expr}' returned "
            f"{type(output).__name__}, not a DataFrame"
        )
    missing_cols = _REQUIRED_COLUMNS - set(output.columns)
    if missing_cols:
        raise PanelError(
            f"factor '{factor}': derived expr '{source.expr}' output is missing "
            f"required column(s) {sorted(missing_cols)}"
        )
    return output


@dataclass(frozen=True)
class FactorFrames:
    """Per-factor train+validation frames, plus the two distinct kinds of "missing".

    ``frames`` maps factor id -> a canonical ``(date, value)`` frame in the units
    :attr:`ah.factors.FactorSource.units` declares (for a ``derived`` factor, the
    transform's output). ``missing_declared`` and ``missing_no_data`` are both in
    :meth:`~ah.factors.FactorManifest.active_factors` order (never sets: a caller
    reporting "which factors are missing" gets a stable, reproducible order) and are
    deliberately kept apart -- see the module docstring's "Two kinds of missing".
    """

    frames: Mapping[str, pd.DataFrame]
    missing: tuple[str, ...]
    missing_declared: tuple[str, ...]
    missing_no_data: tuple[str, ...]


def read_factor_frames(
    access: DataAccess,
    manifest: FactorManifest,
    *,
    split_reader: SplitReader = _default_split_reader,
) -> FactorFrames:
    """Resolve every active factor's ``factor_sources`` entry into a ``(date, value)`` frame.

    **The single factor-id -> Step-1-series resolution surface.** Both
    :func:`build_panel` and :func:`ah.eval.reference.compute_reference` go through this
    function, so neither can drift into its own interpretation of the manifest.

    Reads exactly :meth:`~ah.factors.FactorManifest.active_factors` -- an inactive
    block's factors (``uk``, while inactive) are never even considered. For each:

    - ``kind: unavailable`` -- omitted, recorded in ``missing_declared``.
    - ``kind: series`` -- ``split_reader(access, series_id)``; if that has no data,
      omitted and recorded in ``missing_no_data`` (a data gap, not an error).
    - ``kind: derived`` -- every one of ``source.inputs`` is read the same way; if
      *any* input has no data the whole factor is omitted and recorded in
      ``missing_no_data`` (a derived series computed from a partially-missing input
      would silently misstate the transform, so this is all-or-nothing, not a partial
      column). Otherwise the declared ``expr`` (an existing :mod:`ah.data.derive`
      helper) computes the factor's frame from its inputs, in the declared order.
    """
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    missing_declared: list[str] = []
    missing_no_data: list[str] = []

    for factor in manifest.active_factors():
        source = manifest.sources[factor]

        if source.kind == "unavailable":
            missing.append(factor)
            missing_declared.append(factor)
            continue

        if source.kind == "series":
            assert source.series_id is not None
            raw = _read_series(access, source.series_id, split_reader, factor=factor)
            if raw is None:
                missing.append(factor)
                missing_no_data.append(factor)
                continue
            frames[factor] = raw
            continue

        if source.kind == "derived":
            input_frames: list[pd.DataFrame] = []
            any_missing = False
            for series_id in source.inputs:
                raw = _read_series(access, series_id, split_reader, factor=factor)
                if raw is None:
                    any_missing = True
                    break
                input_frames.append(raw)
            if any_missing:
                missing.append(factor)
                missing_no_data.append(factor)
                continue
            derived_frame = _compute_derived(source, factor, input_frames)
            if derived_frame.empty:
                missing.append(factor)
                missing_no_data.append(factor)
                continue
            frames[factor] = derived_frame
            continue

        raise PanelError(  # pragma: no cover - load_manifest() already rejects this
            f"factor '{factor}': unknown source kind '{source.kind}'"
        )

    return FactorFrames(
        frames=MappingProxyType(frames),
        missing=tuple(missing),
        missing_declared=tuple(missing_declared),
        missing_no_data=tuple(missing_no_data),
    )


@dataclass(frozen=True)
class Panel:
    """The reference panel: one column per available active factor, plus what's missing.

    ``frame`` is ``date``-indexed-by-column (a ``date`` column plus one column per
    available factor, named after the factor, never the series id) with values in the
    units :attr:`ah.factors.FactorSource.units` declares. ``missing`` names every
    active factor absent from ``frame``, in ``active_factors()`` order;
    ``missing_declared`` and ``missing_no_data`` partition it into the two distinct
    kinds of absence (module docstring).
    """

    frame: pd.DataFrame
    missing: tuple[str, ...]
    missing_declared: tuple[str, ...]
    missing_no_data: tuple[str, ...]


def build_panel(
    access: DataAccess,
    manifest: FactorManifest,
    *,
    split_reader: SplitReader = _default_split_reader,
) -> Panel:
    """Build the train+validation reference panel over every active factor.

    Resolution is :func:`read_factor_frames`' job (see it for the per-``kind``
    contract). This function adds only the assembly step: every available factor's
    frame is joined into one wide panel via :func:`ah.data.derive.assemble_panel`
    (outer join on date; raises if any column has a gap after its own first
    observation, and requires every column to reach the panel's last date -- see that
    function's docstring for the trailing-gap constraint). If every active factor is
    missing, an empty, dateless :class:`Panel` is returned rather than an error out of
    ``assemble_panel`` on zero columns.
    """
    read = read_factor_frames(access, manifest, split_reader=split_reader)

    if not read.frames:
        return Panel(
            frame=pd.DataFrame({"date": []}),
            missing=read.missing,
            missing_declared=read.missing_declared,
            missing_no_data=read.missing_no_data,
        )

    # ah.data.derive.assemble_panel expects {name: (date, value)} frames -- exactly
    # the shape access.train_val() and every derive.py helper already returns, so no
    # renaming is needed: the dict key becomes the wide panel's column name directly.
    wide = derive.assemble_panel(dict(read.frames))
    return Panel(
        frame=wide,
        missing=read.missing,
        missing_declared=read.missing_declared,
        missing_no_data=read.missing_no_data,
    )
