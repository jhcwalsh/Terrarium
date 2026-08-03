"""WP2.2 Task 1 acceptance: the reference panel reader.

``ah.eval.panel.build_panel`` is the thin layer between ``DataAccess`` (``ah.splits``)
and ``ah.eval.reference``: it turns a ``FactorManifest`` into one date-indexed frame of
every available active factor, in the manifest's declared units, reusing
``ah.data.derive``'s existing helpers for ``kind: derived`` factors. It must never read
the holdout -- the leakage test here mirrors ``tests/test_reference.py``'s recording-
reader pattern, recording at ``frame()``, not ``train_val()``.
"""

from __future__ import annotations

from pathlib import Path

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


def test_derived_expr_output_missing_columns_raises_panel_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MINOR 4: a derived expr's *output* is column-checked like every input frame.

    ``_read_series`` validates ``date``/``value`` on every input; before this fix
    ``_compute_derived`` handed its helper's return value straight to
    ``set_index("date")["value"]`` with no check at all. Safe today only because every
    registered ``_DERIVED_EXPRS`` entry happens to call ``ah.data.derive._frame()``,
    which always returns exactly those two columns -- a future transform that didn't
    would fall through this hole silently. Monkeypatch a broken entry into the
    dispatch table to exercise the defence directly, without depending on any real
    helper misbehaving.
    """
    import ah.eval.panel as panel_mod

    broken_spec = panel_mod.DerivedExpr(
        arity=1,
        fn=lambda frames: pd.DataFrame({"date": frames[0]["date"]}),  # no `value`
    )
    monkeypatch.setitem(panel_mod._DERIVED_EXPRS, "broken_no_value", broken_spec)

    manifest = FactorManifest(
        blocks={"global": ("weird",)},
        active_blocks=("global",),
        sources={
            "weird": FactorSource(
                kind="derived", expr="broken_no_value", inputs=("s.a",), units="pct"
            )
        },
    )
    frames = {"s.a": _synthetic_frame(1, _START, _END)}
    access = DataAccess(_reader_from(frames))

    with pytest.raises(PanelError, match="missing required column"):
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
    """End to end over the committed ``factors.yaml``, with DELIBERATELY STAGGERED starts.

    Fix pass 1 (minor): every series used to be given the identical start and end date,
    so the test could not exercise ``assemble_panel``'s leading-gap behaviour at all --
    which is the behaviour real Step-1 data always has (``fred.CPI`` starts 1913,
    ``fred.HY_OAS`` 1996). Starts are now spread across four decades. End dates stay
    common, because ``assemble_panel`` rejects a *trailing* gap by design (see its
    docstring); that constraint is asserted separately below.
    """
    manifest = load_manifest()
    needed_series: set[str] = set()
    for factor in manifest.active_factors():
        source = manifest.sources[factor]
        if source.kind == "series":
            assert source.series_id is not None
            needed_series.add(source.series_id)
        elif source.kind == "derived":
            needed_series.update(source.inputs)

    starts = ["1960-01-01", "1975-01-01", "1990-01-01", "2000-01-01"]
    frames = {
        sid: _synthetic_frame(i, starts[i % len(starts)], _END)
        for i, sid in enumerate(sorted(needed_series))
    }
    # shiller.cape is a positive valuation ratio; a signed N(0,1) frame would hit
    # demeaned_log_cape's positivity filter and manufacture gaps no real CAPE has.
    frames["shiller.cape"] = frames["shiller.cape"].assign(
        value=20.0 + frames["shiller.cape"]["value"]
    )
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    assert panel.missing == ("commodities",)  # the one known gap (RFR-1)
    assert panel.missing_declared == ("commodities",)
    assert panel.missing_no_data == ()
    expected_columns = {f for f in manifest.active_factors() if f != "commodities"}
    assert set(panel.frame.columns) - {"date"} == expected_columns
    assert not panel.frame.empty

    # The staggered starts really are staggered: the panel spans the earliest series
    # and later-starting columns carry leading NaNs rather than truncating the panel.
    assert panel.frame["date"].min() == pd.Timestamp(starts[0])
    first_valid = {
        col: panel.frame[col].first_valid_index() for col in panel.frame.columns if col != "date"
    }
    assert len(set(first_valid.values())) > 1, "expected columns to start at different dates"


def test_assemble_panel_rejects_a_trailing_gap() -> None:
    """The constraint Tasks 2-6 will hit, asserted rather than left in a scratchpad.

    ``derive.assemble_panel`` tolerates a column starting late but not one *ending*
    early: once a column has started it must have an observation in every month of the
    shared index, including the last. Real Step-1 series all extend to "now", so this
    only bites synthetic panels -- loudly, which is the point.
    """
    from ah.data.derive import assemble_panel

    with pytest.raises(ValueError, match="gap"):
        assemble_panel(
            {
                "long": _synthetic_frame(1, "1980-01-01", "2020-12-01"),
                "stops_early": _synthetic_frame(2, "1980-01-01", "2010-12-01"),
            }
        )


# --------------------------------------------------------------------------- #
# 6. fix pass 1: the two kinds of "missing", the malformed-frame error, and the
#    shared read surface compute_reference goes through.
# --------------------------------------------------------------------------- #


def test_missing_declared_and_missing_no_data_are_not_conflated() -> None:
    """I3: `Panel.missing` merged "declared unavailable" with "declared available, no
    data". The second is the dangerous one -- FRED serves only ~3 years of
    BAMLH0A0HYM2, so a non-splice-aware read leaves `hy_spread` silently joining
    `commodities` in one flat list and WP2.3 seals bands over a panel quietly lacking a
    factor.
    """
    manifest = _small_manifest()
    frames = _full_frames()
    del frames["s.a_lvl"]  # declared available, but the reader has nothing for it
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    assert panel.missing_declared == ("a_gap",)  # kind: unavailable
    assert panel.missing_no_data == ("a_lvl",)  # a real series id with no rows
    # union, in active_factors() order -- a_lvl is declared before a_gap in the block
    assert panel.missing == ("a_lvl", "a_gap")


def test_derived_factor_with_a_missing_input_is_no_data_not_declared() -> None:
    manifest = _small_manifest()
    frames = _full_frames()
    del frames["s.y"]
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)

    assert panel.missing_no_data == ("u_derived",)
    assert panel.missing_declared == ("a_gap",)


def test_malformed_frame_raises_panel_error_naming_factor_and_series() -> None:
    manifest = _small_manifest()
    frames = _full_frames()
    frames["s.a_ret"] = frames["s.a_ret"].rename(columns={"value": "not_value"})
    access = DataAccess(_reader_from(frames))

    with pytest.raises(PanelError, match="a_ret"):
        build_panel(access, manifest)


def test_read_factor_frames_is_the_surface_compute_reference_uses() -> None:
    """Critical 1, from the panel side: one resolution surface, not two.

    ``build_panel`` and ``compute_reference`` must agree about which factors resolved
    and which did not, because one produces the panel a generator is fitted against and
    the other produces the bands WP2.3 seals. Proved by running both over the same
    manifest and reader and comparing their missing accounting exactly.
    """
    from ah.eval.reference import compute_reference

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
    frames["shiller.cape"] = frames["shiller.cape"].assign(
        value=20.0 + frames["shiller.cape"]["value"]
    )  # positive ratio, as in the end-to-end test above
    access = DataAccess(_reader_from(frames))

    panel = build_panel(access, manifest)
    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=5, block_length=12
    )

    assert panel.missing == ref.missing_factors
    assert panel.missing_declared == ref.missing_declared
    assert panel.missing_no_data == ref.missing_no_data


def test_panel_module_never_imports_g2_or_names_the_token() -> None:
    """The same import-graph proof ``tests/test_reference.py`` applies to reference.py.

    ``panel.py`` is now the module that actually performs every read, so the guard has
    to cover it: it must never import the holdout-token mint, and must never reference
    ``FinalEvaluationToken`` in code (a docstring mention is fine, and this module has
    one explaining why it holds none).
    """
    import ast

    path = Path(__file__).resolve().parents[1] / "src" / "ah" / "eval" / "panel.py"
    text = path.read_text(encoding="utf-8")
    assert "import ah.eval.g2" not in text
    assert "from ah.eval.g2" not in text

    tree = ast.parse(text, filename=str(path))
    offenders = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id == "FinalEvaluationToken")
        or (isinstance(node, ast.Attribute) and node.attr == "FinalEvaluationToken")
        or (
            isinstance(node, ast.ImportFrom)
            and any(a.name == "FinalEvaluationToken" for a in node.names)
        )
    ]
    assert not offenders, "panel.py must never reference FinalEvaluationToken in code"
