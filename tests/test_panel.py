"""WP2.2 Task 1 acceptance: the reference panel reader.

``ah.eval.panel.build_panel`` is the thin layer between ``DataAccess`` (``ah.splits``)
and ``ah.eval.reference``: it turns a ``FactorManifest`` into one date-indexed frame of
every available active factor, in the manifest's declared units, reusing
``ah.data.derive``'s existing helpers for ``kind: derived`` factors. It must never read
the holdout -- the leakage test here mirrors ``tests/test_reference.py``'s recording-
reader pattern, recording at ``frame()``, not ``train_val()``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.eval.panel import Panel, PanelError, build_panel
from ah.factors import FactorManifest, FactorSource, load_manifest
from ah.splits import HOLDOUT, DataAccess, FinalEvaluationToken, Reader


def _synthetic_frame(seed: int, start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="MS")
    rng = np.random.Generator(np.random.PCG64(seed))
    values = rng.normal(0.0, 1.0, size=len(dates))
    return pd.DataFrame({"date": dates, "value": values})


def _reader_from(frames: dict[str, pd.DataFrame]) -> Reader:
    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in frames:
            raise KeyError(series_id)
        return frames[series_id]

    return reader


class _RecordingAccess(DataAccess):
    """Records every date and series id returned by ``frame()``.

    Mirrors ``tests/test_reference.py``'s ``_RecordingAccess``: recording happens at
    ``frame()``, not ``train_val()``, so a direct/parallel holdout read would be caught
    even if it bypassed ``train_val()`` entirely (see that module's docstring for why).
    """

    def __init__(self, reader: Reader) -> None:
        super().__init__(reader)
        self.dates_returned: list[pd.Timestamp] = []
        self.series_requested: list[str] = []

    def frame(
        self, series_id: str, split: str, *, token: FinalEvaluationToken | None = None
    ) -> pd.DataFrame:
        self.series_requested.append(series_id)
        df = super().frame(series_id, split, token=token)
        self.dates_returned.extend(df["date"].tolist())
        return df


def _small_manifest() -> FactorManifest:
    """A four-factor manifest exercising all three ``factor_sources`` kinds."""
    return FactorManifest(
        blocks={"global": ("a_ret", "a_lvl", "a_gap"), "us": ("u_derived",)},
        active_blocks=("global", "us"),
        sources={
            "a_ret": FactorSource(kind="series", series_id="s.a_ret", units="ret"),
            "a_lvl": FactorSource(kind="series", series_id="s.a_lvl", units="pct"),
            "a_gap": FactorSource(kind="unavailable", reason="fixture"),
            "u_derived": FactorSource(
                kind="derived", expr="difference", inputs=("s.x", "s.y"), units="pct"
            ),
        },
    )


_START, _END = "1980-01-01", "2020-12-01"


def _full_frames() -> dict[str, pd.DataFrame]:
    return {
        "s.a_ret": _synthetic_frame(1, _START, _END),
        "s.a_lvl": _synthetic_frame(2, _START, _END),
        "s.x": _synthetic_frame(3, _START, _END),
        "s.y": _synthetic_frame(4, _START, _END),
    }


# --------------------------------------------------------------------------- #
# 1. available factors land in the frame; unavailable land in `missing`
# --------------------------------------------------------------------------- #


def test_available_factors_in_frame_unavailable_in_missing() -> None:
    manifest = _small_manifest()
    access = DataAccess(_reader_from(_full_frames()))

    panel = build_panel(access, manifest)

    assert isinstance(panel, Panel)
    assert panel.missing == ("a_gap",)
    assert set(panel.frame.columns) == {"date", "a_ret", "a_lvl", "u_derived"}
    assert len(panel.frame) == len(pd.date_range(_START, _END, freq="MS"))


def test_missing_is_ordered_by_active_factors_not_a_set() -> None:
    """`missing` must be a tuple in `active_factors()` order, not an unordered set."""
    manifest = _small_manifest()
    access = DataAccess(_reader_from({}))  # every series unknown

    panel = build_panel(access, manifest)

    assert panel.missing == manifest.active_factors()  # everything is missing, in order


# --------------------------------------------------------------------------- #
# 2. real-world data gaps (unknown series id / empty frame) are "missing", not errors
# --------------------------------------------------------------------------- #


def test_series_factor_missing_when_series_unregistered() -> None:
    manifest = _small_manifest()
    frames = _full_frames()
    del frames["s.a_ret"]
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    assert "a_ret" in panel.missing
    assert "a_ret" not in panel.frame.columns


def test_series_factor_missing_when_frame_is_empty() -> None:
    manifest = _small_manifest()
    frames = _full_frames()
    frames["s.a_ret"] = pd.DataFrame({"date": [], "value": []})
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    assert "a_ret" in panel.missing


def test_derived_factor_missing_if_any_input_is_missing() -> None:
    manifest = _small_manifest()
    frames = _full_frames()
    del frames["s.y"]  # one of u_derived's two inputs
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    assert "u_derived" in panel.missing
    assert "u_derived" not in panel.frame.columns
    # the other factors are unaffected by u_derived's missing input
    assert "a_ret" in panel.frame.columns
    assert "a_lvl" in panel.frame.columns


def test_all_factors_missing_yields_empty_dateless_panel() -> None:
    manifest = _small_manifest()
    access = DataAccess(_reader_from({}))

    panel = build_panel(access, manifest)

    assert set(panel.missing) == set(manifest.active_factors())
    assert list(panel.frame.columns) == ["date"]
    assert panel.frame.empty


# --------------------------------------------------------------------------- #
# 3. derived factors reuse ah.data.derive helpers, not a reimplementation
# --------------------------------------------------------------------------- #


def test_derived_factor_matches_derive_difference_directly() -> None:
    manifest = _small_manifest()
    frames = _full_frames()
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    from ah.data.derive import difference

    expected = difference(frames["s.x"], frames["s.y"])
    got = panel.frame[["date", "u_derived"]].rename(columns={"u_derived": "value"})  # type: ignore[call-overload]
    pd.testing.assert_frame_equal(
        got.reset_index(drop=True), expected.reset_index(drop=True), check_dtype=False
    )


def test_unknown_derived_expr_raises_panel_error() -> None:
    manifest = FactorManifest(
        blocks={"global": ("weird",)},
        active_blocks=("global",),
        sources={
            "weird": FactorSource(
                kind="derived", expr="not_a_real_expr", inputs=("s.a", "s.b"), units="pct"
            )
        },
    )
    frames = {"s.a": _synthetic_frame(1, _START, _END), "s.b": _synthetic_frame(2, _START, _END)}
    access = DataAccess(_reader_from(frames))

    with pytest.raises(PanelError, match="not_a_real_expr"):
        build_panel(access, manifest)


def test_derived_expr_arity_mismatch_raises_panel_error() -> None:
    manifest = FactorManifest(
        blocks={"global": ("weird",)},
        active_blocks=("global",),
        sources={
            "weird": FactorSource(kind="derived", expr="difference", inputs=("s.a",), units="pct")
        },
    )
    frames = {"s.a": _synthetic_frame(1, _START, _END)}
    access = DataAccess(_reader_from(frames))

    with pytest.raises(PanelError, match="expects 2"):
        build_panel(access, manifest)


# --------------------------------------------------------------------------- #
# 4. never reads the holdout
# --------------------------------------------------------------------------- #


def test_build_panel_never_reads_holdout() -> None:
    manifest = _small_manifest()
    frames = {
        "s.a_ret": _synthetic_frame(1, "1980-01-01", "2026-06-01"),
        "s.a_lvl": _synthetic_frame(2, "1980-01-01", "2026-06-01"),
        "s.x": _synthetic_frame(3, "1980-01-01", "2026-06-01"),
        "s.y": _synthetic_frame(4, "1980-01-01", "2026-06-01"),
    }
    access = _RecordingAccess(_reader_from(frames))

    build_panel(access, manifest)

    assert access.dates_returned, "expected build_panel to actually read data"
    holdout_start = pd.Timestamp(HOLDOUT.start)
    offenders = [d for d in access.dates_returned if d >= holdout_start]
    assert not offenders, f"holdout-era dates reached build_panel: {offenders[:5]}"


def test_build_panel_default_split_reader_is_train_val() -> None:
    """The default ``split_reader`` is ``DataAccess.train_val``, not ``frame(...,
    "holdout", ...)`` -- proved directly, not only inferred from the date bound above.
    """
    manifest = _small_manifest()
    frames = _full_frames()

    calls: list[tuple[str, str]] = []
    real_frame = DataAccess.frame

    class _SpyAccess(DataAccess):
        def frame(self, series_id, split, *, token=None):  # type: ignore[override]
            calls.append((series_id, split))
            return real_frame(self, series_id, split, token=token)

    access = _SpyAccess(_reader_from(frames))
    build_panel(access, manifest)

    assert calls
    assert {split for _, split in calls} == {"train", "validation"}


def test_custom_split_reader_is_used() -> None:
    manifest = _small_manifest()
    frames = _full_frames()
    seen: list[str] = []

    def custom_split_reader(access: DataAccess, series_id: str) -> pd.DataFrame:
        seen.append(series_id)
        return access.train_val(series_id)

    access = DataAccess(_reader_from(frames))
    build_panel(access, manifest, split_reader=custom_split_reader)

    assert set(seen) == {"s.a_ret", "s.a_lvl", "s.x", "s.y"}


# --------------------------------------------------------------------------- #
# 5. end-to-end over the real, committed factors.yaml
# --------------------------------------------------------------------------- #


def test_build_panel_over_real_manifest_end_to_end() -> None:
    manifest = load_manifest()
    needed_series: set[str] = set()
    for factor in manifest.active_factors():
        source = manifest.sources[factor]
        if source.kind == "series":
            assert source.series_id is not None
            needed_series.add(source.series_id)
        elif source.kind == "derived":
            needed_series.update(source.inputs)

    frames = {sid: _synthetic_frame(i, _START, _END) for i, sid in enumerate(sorted(needed_series))}
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    assert panel.missing == ("commodities",)  # the one known gap (RFR-1)
    expected_columns = {f for f in manifest.active_factors() if f != "commodities"}
    assert set(panel.frame.columns) - {"date"} == expected_columns
    assert not panel.frame.empty
