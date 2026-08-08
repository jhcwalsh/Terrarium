"""Refresh orchestration (STEP1-DATA-PLAN §WP1.10).

``refresh`` runs: plan (manifest ∩ due-by-SLA ∩ source) -> fetch/parse (via an
injected provider) -> QC -> vintage commit or quarantine -> reports. It is idempotent:
re-running the same vintage id is detected and becomes a no-op (no duplicate vintage,
same content). The provider seam keeps the orchestration testable offline; production
wires connectors, dev can point at a directory of canonical CSVs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ah.data.catalog import Catalog
from ah.data.gapfill import fill_declared_gaps
from ah.data.manifest import Requirement, Requirements
from ah.data.qc import QCReport, run_qc
from ah.data.reports import gap_register, generate_data_status_md, generate_gaps_md, series_gap

Provider = Callable[[Requirement], "pd.DataFrame | None"]


@dataclass
class RefreshResult:
    vintage: str
    planned: list[str]
    written: list[str]
    dry_run: bool = False
    already_exists: bool = False
    quarantined: bool = False
    carried_forward: list[str] = field(default_factory=list)
    qc: QCReport | None = None
    gaps_md: str = ""
    status_md: str = ""
    warnings: list[str] = field(default_factory=list)
    #: Declared-gap interpolations applied this refresh (ah.data.gapfill) —
    #: reported separately from warnings: a fill is a documented action, not a
    #: failure.
    fill_notes: list[str] = field(default_factory=list)


def plan(
    reqs: Requirements, catalog: Catalog, *, asof: str, sources: list[str] | None = None
) -> list[Requirement]:
    """Auto-intake series that are missing or stale (and match the source filter)."""
    due: list[Requirement] = []
    for req in reqs:
        if req.intake != "auto":
            continue
        if sources is not None and req.source not in sources:
            continue
        gap = series_gap(catalog, req, asof=asof)
        if not gap.present or gap.stale:
            due.append(req)
    return due


def refresh(
    catalog: Catalog,
    reqs: Requirements,
    *,
    vintage: str,
    asof: str,
    provider: Provider,
    created_at: str,
    sources: list[str] | None = None,
    dry_run: bool = False,
) -> RefreshResult:
    due = plan(reqs, catalog, asof=asof, sources=sources)
    planned = [r.series_id for r in due]

    if dry_run:
        return RefreshResult(vintage, planned, [], dry_run=True)

    if catalog.vintage_status(vintage) is not None:
        # idempotent: this vintage was already built — no duplicate, no rewrite
        return RefreshResult(vintage, planned, [], already_exists=True)

    catalog.create_vintage(vintage, created_at=created_at)
    written: list[str] = []
    pairs: list[tuple[Requirement, pd.DataFrame]] = []
    warnings: list[str] = []
    fill_notes: list[str] = []
    for req in due:
        try:
            frame = provider(req)
        except Exception as exc:
            warnings.append(f"{req.series_id}: fetch/parse failed: {type(exc).__name__}")
            continue
        if frame is None or frame.empty:
            continue
        frame, notes = fill_declared_gaps(req.series_id, frame)
        fill_notes.extend(notes)
        catalog.register_series(req)
        catalog.write_observations(vintage, req.series_id, frame)
        written.append(req.series_id)
        pairs.append((req, frame))

    carried, carry_notes = _carry_forward(catalog, reqs, vintage, written)
    fill_notes.extend(carry_notes)

    qc = (
        run_qc(catalog, vintage, pairs, asof=asof, created_at=created_at) if pairs else QCReport([])
    )
    if qc.passed and written:
        catalog.advance_pointer(vintage, when=created_at)

    gaps_md = generate_gaps_md(gap_register(catalog, reqs, asof=asof))
    status_md = generate_data_status_md(catalog, reqs, asof=asof)
    return RefreshResult(
        vintage,
        planned,
        written,
        quarantined=not qc.passed,
        qc=qc,
        gaps_md=gaps_md,
        status_md=status_md,
        warnings=warnings,
        fill_notes=fill_notes,
        carried_forward=carried,
    )


def apply_intake_frames(
    catalog: Catalog,
    reqs: Requirements,
    *,
    frames: dict[str, pd.DataFrame],
    vintage: str,
    asof: str,
    created_at: str,
) -> RefreshResult:
    """The manual-intake last mile (WP2R.2, closing half of RFR-88).

    ``frames`` is :func:`ah.data.intake.to_series_frames`' output for an
    ACCEPTED drop — per-series ``(date, value)`` frames keyed by series id.
    This runs exactly :func:`refresh`'s sequence with the fetch replaced by the
    drop: write each frame under ``vintage``, carry forward everything the drop
    did not cover, run QC over the new pairs, advance the ``current`` pointer
    only if QC passes, regenerate the gap/status registers. Until this existed,
    ``ingest_file`` recorded a drop in ``intake_log`` and stopped — an accepted
    delivery never reached the vintage store.

    Every key in ``frames`` must be a registered series id: with the WP2R.2
    convention that the intake ``strategy`` code IS the id fragment, a drop
    whose codes are mapped (the WP2R.1 boundary) lands under registered ids by
    construction, and anything else is a loud error here rather than a silent
    new id in the store.
    """
    unknown = sorted(set(frames) - {r.series_id for r in reqs})
    if unknown:
        raise ValueError(
            f"intake frames carry series ids that requirements.yaml does not register: "
            f"{unknown} — register the series (or fix the strategy codes) before applying"
        )
    if catalog.vintage_status(vintage) is not None:
        # idempotent, exactly as refresh(): this vintage was already built
        return RefreshResult(vintage, sorted(frames), [], already_exists=True)

    catalog.create_vintage(vintage, created_at=created_at)
    written: list[str] = []
    pairs: list[tuple[Requirement, pd.DataFrame]] = []
    for series_id in sorted(frames):
        req = next(r for r in reqs if r.series_id == series_id)
        catalog.register_series(req)
        catalog.write_observations(vintage, series_id, frames[series_id])
        written.append(series_id)
        pairs.append((req, frames[series_id]))

    carried, carry_notes = _carry_forward(catalog, reqs, vintage, written)
    qc = run_qc(catalog, vintage, pairs, asof=asof, created_at=created_at)
    if qc.passed and written:
        catalog.advance_pointer(vintage, when=created_at)

    gaps_md = generate_gaps_md(gap_register(catalog, reqs, asof=asof))
    status_md = generate_data_status_md(catalog, reqs, asof=asof)
    return RefreshResult(
        vintage,
        sorted(frames),
        written,
        fill_notes=carry_notes,
        quarantined=not qc.passed,
        qc=qc,
        gaps_md=gaps_md,
        status_md=status_md,
        carried_forward=carried,
    )


def _carry_forward(
    catalog: Catalog, reqs: Requirements, vintage: str, written: list[str]
) -> tuple[list[str], list[str]]:
    """Copy every already-held series that this refresh did not fetch into ``vintage``.

    A vintage is documented as a complete as-of snapshot and every read pins one
    (``catalog.read_observations``/``read_asof`` resolve a single vintage id, with no
    per-series fallback). But ``plan`` only fetches series that are missing or stale,
    so without this step the first refresh after the initial build silently DROPS every
    series that happened to be fresh -- it disappears from pinned reads and is reported
    as absent with 0% coverage in GAPS.md even though its observations are still on
    disk under the older vintage. That is how ``fred.TEDRATE`` (retired 2022-01, so
    never stale under its 9999-day SLA) fell out of the 2026-07-26 vintage.

    Carrying forward re-stamps the rows with the new vintage id, which is a new
    ``(vintage, series)`` key -- immutability is untouched, nothing is overwritten, and
    the older vintage stays byte-identical. Carried rows are NOT re-submitted to QC:
    they passed when they were fetched, they are unchanged, and re-judging unchanged
    history against a later as-of date would quarantine a vintage for the sole reason
    that a retired series is still retired.
    """
    done = set(written)
    carried: list[str] = []
    notes: list[str] = []
    for req in reqs:
        if req.series_id in done:
            continue
        source_vintage = catalog.latest_vintage_with(req.series_id)
        if source_vintage is None or source_vintage == vintage:
            continue
        frame = catalog.read_observations(source_vintage, req.series_id)
        if frame.empty:
            continue
        # Keep the proxy flag across carries (a flagged synthetic observation
        # must never lose its flag), and apply declared gap fills here too — a
        # fresh series is carried, not refetched, so this is the only chance a
        # declared fill gets until the series next goes stale.
        cols = ["date", "value"] + (["is_proxy"] if "is_proxy" in frame.columns else [])
        filled, fill_notes = fill_declared_gaps(req.series_id, frame[cols])
        notes.extend(fill_notes)
        catalog.write_observations(vintage, req.series_id, filled)
        carried.append(req.series_id)
    return carried, notes


_SHARED_FILE_SOURCES = {"french", "jst", "shiller"}


def connector_provider(connectors: dict[str, Any]) -> Provider:
    """A live provider: fetch+parse via source connectors, caching shared-file artifacts.

    ``connectors`` maps ``source -> connector``. FRED/BIS/Treasury fetch per series;
    French/JST/Shiller download one file that serves many series (cached). Requires
    network — used only by ``ah data refresh --live``, never in tests.
    """
    cache: dict[tuple[str, str], object] = {}

    def _provider(req: Requirement) -> pd.DataFrame | None:  # pragma: no cover - network
        conn = connectors.get(req.source)
        if conn is None:
            return None
        if req.source in _SHARED_FILE_SOURCES:
            key = (req.source, "MOM" if req.code == "Mom" else "MAIN")
            if key not in cache:
                cache[key] = conn.fetch(req)
            raw = cache[key]
        else:
            raw = conn.fetch(req)
        return conn.parse(raw, req)

    return _provider


def csv_dir_provider(directory: str | Path) -> Provider:
    """A dev provider: read ``<dir>/<series_id>.csv`` (columns date,value) if present."""
    root = Path(directory)

    def _provider(req: Requirement) -> pd.DataFrame | None:
        path = root / f"{req.series_id}.csv"
        if not path.exists():
            return None
        return pd.read_csv(path)

    return _provider
