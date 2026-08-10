"""The datalab data layer: pure, read-only, streamlit-free (spec 2026-08-09).

Everything ``apps/datalab/app.py`` shows is computed HERE, over the same
surfaces the platform already trusts -- :class:`ah.data.catalog.Catalog`,
``requirements.yaml`` via :func:`ah.data.manifest.load_requirements`,
``factors.yaml`` via :func:`ah.factors.load_manifest`, and the sealed derived
-expr registry ``ah.eval.panel._DERIVED_EXPRS`` -- so the console can never
show a number the platform would not itself compute. This module imports no
streamlit and writes NOTHING: like ``ah.dataconsole`` it has zero store-write
call sites, and ``tests/test_datalab.py`` scans the source to keep it true.

Display posture (the ``ah data episode`` precedent): reads are FULL history,
not train+validation -- the app draws the split boundaries and marks the
holdout SPENT rather than hiding it. Proxy months are never silent: factor
frames carry ``is_proxy``/``rule_id`` recomputed at display time (the sealed
read surface deliberately strips per-row flags; the mask here is the splice
contract itself -- an actual is never overwritten, so any factor month absent
from the primary input series is proxy by construction), and CSV downloads
embed the licence tier of every contributing series plus the AQR attribution
whenever a REG series contributes (owner ruling 2, 2026-08-09).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.data.manifest import Requirement, Requirements, load_requirements
from ah.factors import FactorManifest, load_manifest

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = _REPO_ROOT / "data"
DEFAULT_PORT = 8795
WATERMARK = "DATALAB — read-only over the vintage store — simulated/licensed data"

__all__ = [
    "DEFAULT_DATA_ROOT",
    "DEFAULT_PORT",
    "FACTOR_RULE_LABELS",
    "WATERMARK",
    "FactorRead",
    "SpanAnnotations",
    "VintageDiff",
    "csv_bytes",
    "factor_read",
    "har_fan",
    "open_catalog",
    "proxy_share",
    "series_frame",
    "series_inventory",
    "span_annotations",
    "vintage_diff",
]


def open_catalog(data_root: str | Path = DEFAULT_DATA_ROOT) -> Catalog:
    """The one place the app touches the store. Read-only by contract."""
    return Catalog(Path(data_root))


# --------------------------------------------------------------------------- #
# series
# --------------------------------------------------------------------------- #


def _read(cat: Catalog, vintage: str, series_id: str) -> pd.DataFrame | None:
    """One vintage-pinned series read, ``None`` for absent/empty (a data gap)."""
    try:
        frame = cat.read_observations(vintage, series_id)
    except Exception:
        return None
    if frame is None or frame.empty:
        return None
    out = pd.DataFrame(
        {"date": pd.to_datetime(frame["date"]), "value": frame["value"].astype(float)}
    )
    return out.sort_values(by=["date"]).reset_index(drop=True)


def series_inventory(cat: Catalog, reqs: Requirements | None = None, *, asof: str) -> pd.DataFrame:
    """One row per registered series: coverage, staleness vs SLA, intake facts.

    ``asof`` is caller-supplied (the app passes today) -- this module reads no
    clock, the repo invariant. Staleness is ``asof - last observation`` in
    days, compared to the series' own ``sla_days``; discontinued donors
    (sla 99999) can never read stale, which is their registered posture.
    """
    reqs = reqs or load_requirements()
    vintage = cat.current_vintage()
    rows: list[dict[str, object]] = []
    for r in reqs:
        frame = _read(cat, vintage, r.series_id) if vintage else None
        first = frame["date"].min() if frame is not None else None
        last = frame["date"].max() if frame is not None else None
        stale_days = (pd.Timestamp(asof) - last).days if last is not None else None
        rows.append(
            {
                "series_id": r.series_id,
                "source": r.source,
                "code": r.code or "",
                "units": r.units,
                "license": r.license_tier,
                "intake": r.intake,
                "level": "enforce" if r.enforce else "warn",
                "first": None if first is None else str(first.date()),
                "last": None if last is None else str(last.date()),
                "n_obs": 0 if frame is None else len(frame),
                "staleness_days": stale_days,
                "sla_days": r.sla_days,
                "stale": (stale_days is not None and stale_days > r.sla_days),
                "in_store": frame is not None,
            }
        )
    return pd.DataFrame(rows)


def series_frame(
    cat: Catalog,
    series_id: str,
    *,
    vintage: str | None = None,
    asof: str | None = None,
) -> pd.DataFrame | None:
    """A series read pinned to a vintage, or resolved as-of through pointer history."""
    if vintage is not None and asof is not None:
        raise ValueError("pass vintage or asof, not both")
    if asof is not None:
        resolved = cat.asof(asof)
        if resolved is None:
            return None
        return _read(cat, resolved, series_id)
    resolved = vintage or cat.current_vintage()
    if resolved is None:
        return None
    return _read(cat, resolved, series_id)


# --------------------------------------------------------------------------- #
# factors
# --------------------------------------------------------------------------- #

#: rule_id labels for proxy months, applied in order: the FIRST entry whose
#: exclusive end-date bound covers the month labels it (None = no bound, the
#: terminal catch-all). Display metadata reconciled against the proxy_for
#: entries of factors.yaml (2026-08-09, the campaign-3 wiring); factors.yaml
#: is the truth and this table invents no provenance -- a factor absent here
#: renders its proxy months with rule_id "" rather than a guess.
FACTOR_RULE_LABELS: dict[str, tuple[tuple[str | None, str], ...]] = {
    "equity_vol": (
        ("1986-01-01", "PROXY-EQUITY-VOL-HAR-V1"),
        ("1990-01-01", "PROXY-EQUITY-VOL-VXO-V1"),
    ),
    "fx_usd": (
        ("1973-01-01", "PROXY-FX-PARITY-V1"),
        ("2006-01-01", "fx_usd_pre2006"),
    ),
    "funding_spread": ((None, "PROXY-FUNDING-CPBILL-V1"),),
    "hqm_curve": ((None, "PROXY-HQM10-AAA-V1"),),
    "ust_2y": ((None, "PROXY-UST2Y-GS1GS3-V1"),),
    "ust_10y": ((None, "PROXY-UST10Y-GS10-V1"),),
    "policy_rate": ((None, "fedfunds_pre1954"),),
    "hy_spread": ((None, "hy_oas_pre1996"),),
}


@dataclass(frozen=True)
class FactorRead:
    """One factor as the generator reads it, plus its display provenance.

    ``frame`` carries ``date, value, is_proxy, rule_id``; ``unextended`` is
    the same read with every optional donor input forced empty (the panel's
    own fallback semantics -- exactly the campaign-2 read), or ``None`` when
    the factor's expr declares no optional inputs; ``note`` is non-empty only
    when the factor could not be computed, and says why.
    """

    factor: str
    frame: pd.DataFrame | None
    unextended: pd.DataFrame | None
    note: str
    share: dict[str, object]


def _label_rules(factor: str, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["rule_id"] = ""
    labels = FACTOR_RULE_LABELS.get(factor, ())
    proxy = out["is_proxy"].to_numpy(dtype=bool)
    unlabeled = proxy.copy()
    for end, rule in labels:
        if end is None:
            mask = unlabeled
        else:
            mask = unlabeled & (out["date"] < pd.Timestamp(end)).to_numpy()
        out.loc[mask, "rule_id"] = rule
        unlabeled = unlabeled & ~mask
    return out


def _compute(
    cat: Catalog,
    vintage: str,
    manifest: FactorManifest,
    factor: str,
    *,
    blank_optional: bool,
) -> tuple[pd.DataFrame | None, str]:
    """One factor frame off the sealed expr registry; (None, why) on a gap."""
    # The sealed registry itself -- a display surface reads the same table the
    # panel dispatches on, so the two can never disagree about arity or expr.
    from ah.eval.panel import _DERIVED_EXPRS

    fs = manifest.sources[factor]
    if fs.kind == "unavailable":
        return None, f"unavailable -- {fs.reason}"
    if fs.kind == "series":
        assert fs.series_id is not None
        frame = _read(cat, vintage, fs.series_id)
        if frame is None:
            return None, f"{fs.series_id} absent from store"
        frame = frame.copy()
        frame["is_proxy"] = False
        frame["rule_id"] = ""
        return frame, ""
    spec = _DERIVED_EXPRS.get(fs.expr or "")
    if spec is None:
        return None, f"unknown expr {fs.expr!r}"
    empty = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})
    inputs: list[pd.DataFrame] = []
    for position, sid in enumerate(fs.inputs):
        frame = _read(cat, vintage, sid)
        if position in spec.optional_inputs and (blank_optional or frame is None):
            inputs.append(empty)
            continue
        if frame is None:
            return None, f"required input {sid} absent from store"
        inputs.append(frame)
    try:
        out = spec.fn(inputs)
    except Exception as exc:  # a display gap, not a crash page
        return None, f"derive.{fs.expr} failed: {type(exc).__name__}: {exc}"
    if out is None or out.empty:
        return None, f"derive.{fs.expr} returned no rows"
    out = (
        pd.DataFrame({"date": pd.to_datetime(out["date"]), "value": out["value"].astype(float)})
        .sort_values(by=["date"])
        .reset_index(drop=True)
    )
    primary = _read(cat, vintage, fs.inputs[0])
    primary_dates = set(pd.DatetimeIndex(primary["date"])) if primary is not None else set()
    out["is_proxy"] = [d not in primary_dates for d in pd.DatetimeIndex(out["date"])]
    return _label_rules(factor, out), ""


def factor_read(cat: Catalog, factor: str, *, vintage: str | None = None) -> FactorRead:
    """The factor as read on ``vintage`` (default: current), with provenance."""
    manifest = load_manifest()
    resolved = vintage or cat.current_vintage()
    if resolved is None:
        return FactorRead(factor, None, None, "the store has no current vintage", {})
    frame, note = _compute(cat, resolved, manifest, factor, blank_optional=False)
    unextended: pd.DataFrame | None = None
    fs = manifest.sources[factor]
    if frame is not None and fs.kind == "derived":
        from ah.eval.panel import _DERIVED_EXPRS

        spec = _DERIVED_EXPRS.get(fs.expr or "")
        if spec is not None and spec.optional_inputs:
            unextended, _ = _compute(cat, resolved, manifest, factor, blank_optional=True)
    share = proxy_share(frame) if frame is not None else {}
    return FactorRead(factor, frame, unextended, note, share)


def proxy_share(
    frame: pd.DataFrame, *, start: str | None = None, end: str | None = None
) -> dict[str, object]:
    """The AM-2026-08-09-002 disclosure quantity: proxy share, overall and by rule."""
    f = frame
    if start is not None:
        f = f.loc[f["date"] >= pd.Timestamp(start)]
    if end is not None:
        f = f.loc[f["date"] <= pd.Timestamp(end)]
    n = len(f)
    proxy_mask = (
        f["is_proxy"].to_numpy(dtype=bool) if "is_proxy" in f.columns else np.zeros(n, dtype=bool)
    )
    n_proxy = int(proxy_mask.sum())
    by_rule: dict[str, float] = {}
    if n and "rule_id" in f.columns:
        proxy_rows = f.loc[proxy_mask]
        for rule, group in proxy_rows.groupby("rule_id"):
            by_rule[str(rule) or "(unlabeled)"] = len(group) / n
    return {
        "n_months": n,
        "n_proxy": n_proxy,
        "share": (n_proxy / n) if n else float("nan"),
        "by_rule": by_rule,
    }


# --------------------------------------------------------------------------- #
# the HAR fan (owner decision D2: tail readers regenerate the ensemble)
# --------------------------------------------------------------------------- #


def har_fan(
    n_draws: int = 200,
    seed: int = 0,
    quantiles: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95),
) -> pd.DataFrame:
    """The regenerated HAR ensemble's per-month quantile fan beside the pinned draw.

    Fully OFFLINE: the conditional mean is recovered from the two committed
    artifacts alone -- ``log(pinned draw) - the seed-20260809 residual path``
    (both deterministic), so ``exp(mu + paths(fit, ., n_draws, seed))`` is the
    ensemble without refetching the donor features. Deterministic in
    ``(n_draws, seed)``. Every row is MODEL OUTPUT; the app says so.
    """
    from ah.data import vol_backcast as vb

    pinned = vb.pinned_draw_series()
    payload = json.loads(
        (_REPO_ROOT / "artifacts" / "volext" / "equity-vol-backcast-provenance.json").read_text(
            encoding="utf-8"
        )
    )
    fit = vb.fit_from_provenance(payload)
    n_months = len(pinned)
    resid0 = vb.paths(fit, n_months, 1, vb.PINNED_DRAW_SEED)[0]
    mu = np.log(pinned.to_numpy()) - resid0
    fan = np.exp(mu[None, :] + vb.paths(fit, n_months, n_draws, seed))
    out = pd.DataFrame({"date": pinned.index, "pinned": pinned.to_numpy()})
    for q in quantiles:
        out[f"q{round(q * 100):02d}"] = np.quantile(fan, q, axis=0)
    return out


# --------------------------------------------------------------------------- #
# vintages and spans
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class VintageDiff:
    a: str
    b: str
    status_a: str | None
    status_b: str | None
    table: pd.DataFrame  # series_id, n_obs_a, n_obs_b, delta, change


def vintage_diff(cat: Catalog, a: str, b: str) -> VintageDiff:
    """Per-registered-series observation deltas between two vintage ids."""
    reqs = load_requirements()
    rows: list[dict[str, object]] = []
    for r in reqs:
        fa, fb = _read(cat, a, r.series_id), _read(cat, b, r.series_id)
        na, nb = (0 if fa is None else len(fa)), (0 if fb is None else len(fb))
        if fa is None and fb is None:
            continue
        change = (
            "added"
            if fa is None
            else "removed"
            if fb is None
            else "grew"
            if nb > na
            else "shrank"
            if nb < na
            else "same"
        )
        rows.append(
            {
                "series_id": r.series_id,
                "n_obs_a": na,
                "n_obs_b": nb,
                "delta": nb - na,
                "change": change,
            }
        )
    table = pd.DataFrame(rows)
    return VintageDiff(a, b, cat.vintage_status(a), cat.vintage_status(b), table)


@dataclass(frozen=True)
class SpanAnnotations:
    """Split and span facts, read from the code that owns them, never restated."""

    train: tuple[str, str]
    validation: tuple[str, str]
    holdout: tuple[str, str]
    holdout_spent: bool
    campaign2_span: tuple[str, str]
    live_span: tuple[str, str]
    severe_exclusion: tuple[str, str]


def span_annotations() -> SpanAnnotations:
    from ah.gen import bootstrap as bs
    from ah.splits import HOLDOUT, TRAIN, VALIDATION

    return SpanAnnotations(
        train=(TRAIN.start, TRAIN.end),
        validation=(VALIDATION.start, VALIDATION.end),
        holdout=(HOLDOUT.start, HOLDOUT.end),
        holdout_spent=True,  # WP5.6; RESEARCH-EVIDENCE.md
        campaign2_span=(bs.CAMPAIGN2_DRAW_SPAN[0], bs.CAMPAIGN2_DRAW_SPAN[1]),
        live_span=(bs.BLOCK_DRAW_SPAN_START, bs.BLOCK_DRAW_SPAN_END),
        severe_exclusion=("1970-01-01", "1979-12-31"),
    )


# --------------------------------------------------------------------------- #
# downloads (owner ruling 2: licence discipline travels IN the bytes)
# --------------------------------------------------------------------------- #


def csv_bytes(frame: pd.DataFrame, contributing: list[Requirement]) -> bytes:
    """CSV with licence header lines; REG contribution embeds the attribution.

    A download whose bytes do not carry the attribution does not ship -- the
    header is part of the file, not of the page around it.
    """
    lines = [f"# {WATERMARK}"]
    for r in contributing:
        lines.append(f"# licence: {r.series_id} = {r.license_tier}")
    if any(r.license_tier == "REG" for r in contributing):
        from ah.data.cmdty_close import ATTRIBUTION

        lines.append(f"# ATTRIBUTION: {ATTRIBUTION}")
    header = "\n".join(lines) + "\n"
    # LF explicitly: the same frame must produce the same bytes on every
    # platform (the attribution promise is about the bytes, not the page).
    body = frame.to_csv(index=False, lineterminator="\n")
    return header.encode("utf-8") + body.encode("utf-8")
