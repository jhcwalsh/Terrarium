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

Unavailable factors
--------------------
A factor whose :class:`~ah.factors.FactorSource` is ``kind: unavailable``
(``commodities``, and every inactive ``uk`` factor, are never asked for -- inactive
factors are not even in :meth:`~ah.factors.FactorManifest.active_factors`) is omitted
from the returned panel and named in :attr:`Panel.missing`, in
:meth:`~ah.factors.FactorManifest.active_factors` order -- never silently dropped, never
turned into a ``NaN`` column. The same happens if a ``series``/``derived`` factor's
declared series id turns out to have no data in train+validation (an unknown series id
or an empty frame) -- a real-world gap, not a bug, exactly the same "missing, not an
error" contract :mod:`ah.eval.reference` uses for ``commodities`` today.

Assembly
--------
Every available factor's frame is joined into one wide panel via
:func:`ah.data.derive.assemble_panel` (outer join on date, asserting no gaps after each
column's own first observation) -- the same helper Step 1's own panel assembly (WP1.6)
uses, reused rather than reimplemented. If every active factor turns out to be missing,
the panel is an empty, dateless frame rather than an error from ``assemble_panel`` on
zero columns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from ah.data import derive
from ah.factors import FactorManifest, FactorSource
from ah.splits import DataAccess

SplitReader = Callable[[DataAccess, str], pd.DataFrame]


class PanelError(RuntimeError):
    """Raised when a factor's declared source cannot honestly be turned into a frame.

    Never raised for a legitimate data gap (see the module docstring) -- only for a
    malformed ``factor_sources`` entry that ``ah.factors.load_manifest`` should have
    rejected already (an unknown ``expr``, or an ``inputs`` arity that ``expr``'s
    helper does not accept), so this is a defence-in-depth check, not the primary gate.
    """


def _default_split_reader(access: DataAccess, series_id: str) -> pd.DataFrame:
    """The sanctioned reference surface: train+validation only, never the holdout."""
    return access.train_val(series_id)


# Each derived expr's ah.data.derive helper and the exact number of positional
# `inputs` it expects, in order. A fixed, explicit table -- not a generic
# getattr(derive, expr) dispatch -- so an unknown expr in factors.yaml fails here with
# a named error rather than an AttributeError several frames deep, and so the arity of
# each helper is asserted once, in one place, rather than left to blow up inside
# ah.data.derive itself with a confusing positional-argument message.
_DERIVED_EXPRS: dict[str, tuple[int, Callable[[list[pd.DataFrame]], pd.DataFrame]]] = {
    "difference": (2, lambda frames: derive.difference(frames[0], frames[1])),
    "funding_stress": (1, lambda frames: derive.funding_stress(frames[0])),
}


def _read_series(
    access: DataAccess, series_id: str, split_reader: SplitReader
) -> pd.DataFrame | None:
    """``split_reader(access, series_id)``, or ``None`` for an unknown/empty series.

    Mirrors ``ah.eval.reference._read_train_val``'s "missing, not an error" contract:
    ``None`` covers both a series id the reader does not know (``KeyError``) and one
    that is known but has zero rows in train+validation.
    """
    try:
        frame = split_reader(access, series_id)
    except KeyError:
        return None
    if frame.empty:
        return None
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
    expected_arity, fn = spec
    if len(input_frames) != expected_arity:
        raise PanelError(
            f"factor '{factor}': derived expr '{source.expr}' expects "
            f"{expected_arity} input(s), got {len(input_frames)}"
        )
    return fn(input_frames)


@dataclass(frozen=True)
class Panel:
    """The reference panel: one column per available active factor, plus what's missing.

    ``frame`` is ``date``-indexed-by-column (a ``date`` column plus one column per
    available factor, named after the factor, never the series id) with values in the
    units :attr:`ah.factors.FactorSource.units` declares. ``missing`` names every
    active factor omitted from ``frame`` -- unavailable by manifest declaration, or
    unavailable because its declared series id/inputs have no train+validation data --
    in :meth:`~ah.factors.FactorManifest.active_factors` order (never a set: a caller
    reporting "which factors are missing" gets a stable, reproducible order).
    """

    frame: pd.DataFrame
    missing: tuple[str, ...]


def build_panel(
    access: DataAccess,
    manifest: FactorManifest,
    *,
    split_reader: SplitReader = _default_split_reader,
) -> Panel:
    """Build the train+validation reference panel over every active factor.

    Reads exactly :meth:`~ah.factors.FactorManifest.active_factors` -- an inactive
    block's factors (``uk``, while inactive) are never even considered, exactly as
    :func:`ah.eval.reference.compute_reference` never reads them. For each:

    - ``kind: unavailable`` -- omitted, recorded in :attr:`Panel.missing`.
    - ``kind: series`` -- ``split_reader(access, series_id)``; if that has no data,
      omitted and recorded in :attr:`Panel.missing` (a data gap, not an error).
    - ``kind: derived`` -- every one of ``source.inputs`` is read the same way; if
      *any* input has no data the whole factor is omitted and recorded missing (a
      derived series computed from a partially-missing input would silently misstate
      the transform, so this is all-or-nothing, not a partial column). Otherwise the
      declared ``expr`` (an existing :mod:`ah.data.derive` helper) computes the
      factor's frame from its inputs, in the declared order.

    Every available factor's frame is then assembled into one wide panel via
    :func:`ah.data.derive.assemble_panel` (outer join on date; raises if any column has
    a gap after its own first observation -- the same contract Step 1's own panel
    assembly uses). If every active factor is missing, an empty, dateless
    :class:`Panel` is returned rather than an error out of ``assemble_panel`` on zero
    columns.
    """
    columns: dict[str, pd.DataFrame] = {}
    missing: list[str] = []

    for factor in manifest.active_factors():
        source = manifest.sources[factor]

        if source.kind == "unavailable":
            missing.append(factor)
            continue

        if source.kind == "series":
            assert source.series_id is not None
            raw = _read_series(access, source.series_id, split_reader)
            if raw is None:
                missing.append(factor)
                continue
            columns[factor] = raw
            continue

        if source.kind == "derived":
            input_frames: list[pd.DataFrame] = []
            any_missing = False
            for series_id in source.inputs:
                raw = _read_series(access, series_id, split_reader)
                if raw is None:
                    any_missing = True
                    break
                input_frames.append(raw)
            if any_missing:
                missing.append(factor)
                continue
            derived_frame = _compute_derived(source, factor, input_frames)
            if derived_frame.empty:
                missing.append(factor)
                continue
            columns[factor] = derived_frame
            continue

        raise PanelError(  # pragma: no cover - load_manifest() already rejects this
            f"factor '{factor}': unknown source kind '{source.kind}'"
        )

    if not columns:
        return Panel(frame=pd.DataFrame({"date": []}), missing=tuple(missing))

    # ah.data.derive.assemble_panel expects {name: (date, value)} frames -- exactly
    # the shape access.train_val() and every derive.py helper already returns, so no
    # renaming is needed: the dict key becomes the wide panel's column name directly.
    wide = derive.assemble_panel(columns)
    return Panel(frame=wide, missing=tuple(missing))
