"""The datalab data layer (spec 2026-08-09; owner rulings 1-3).

Offline throughout: a tiny two-vintage store built by the TEST through the
catalog's own API (writing happens here, never in the module -- the zero-
write guard at the bottom is the contract), plus the two committed volext
artifacts for the HAR fan.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ah import datalab as dl
from ah.data.manifest import load_requirements

ROOT = Path(__file__).resolve().parents[1]


def _frame(dates: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "value": values})


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    from ah.data.catalog import Catalog

    reqs = load_requirements()
    cat = Catalog(tmp_path)
    months = [f"2020-{m:02d}-01" for m in range(1, 7)]

    cat.create_vintage("v1", created_at="2026-08-09T00:00:00Z", status="pending")
    for sid, vals in [
        ("fred.CPI", [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]),
        ("french.mkt_rf", [0.01, -0.02, 0.03, 0.01, 0.00, 0.02]),
        ("french.rf", [0.001] * 6),
        ("fred.VIX", [20.0, 25.0, 22.0, 30.0, 28.0, 21.0]),
    ]:
        cat.register_series(reqs[sid])
        cat.write_observations("v1", sid, _frame(months, vals))
    cat.advance_pointer("v1", when="2026-08-09T00:00:00Z")

    # v2 grows CPI by one month and adds a series; VIX is carried identically
    cat.create_vintage("v2", created_at="2026-08-10T00:00:00Z", status="pending")
    cat.write_observations("v2", "fred.CPI", _frame([*months, "2020-07-01"], [*range(100, 107)]))
    for sid in ("french.mkt_rf", "french.rf", "fred.VIX"):
        prior = pd.DataFrame(cat.read_observations("v1", sid))
        cat.write_observations("v2", sid, prior.loc[:, ["date", "value"]])
    cat.register_series(reqs["fred.TB3MS"])
    cat.write_observations("v2", "fred.TB3MS", _frame(months, [1.5] * 6))
    cat.advance_pointer("v2", when="2026-08-10T00:00:00Z")
    cat.close()
    return tmp_path


def test_series_inventory_coverage_and_staleness(store: Path) -> None:
    with dl.open_catalog(store) as cat:
        inv = dl.series_inventory(cat, asof="2020-07-15")
    row = inv[inv["series_id"] == "fred.CPI"].iloc[0]
    assert row["in_store"] and row["n_obs"] == 7 and row["last"] == "2020-07-01"
    assert row["staleness_days"] == 14
    # fred.CPI's sla is far above 14 days on a monthly series
    assert not row["stale"]
    absent = inv[inv["series_id"] == "fred.GS1"].iloc[0]
    assert not absent["in_store"] and absent["n_obs"] == 0


def test_series_frame_vintage_pin_and_asof(store: Path) -> None:
    with dl.open_catalog(store) as cat:
        pinned = dl.series_frame(cat, "fred.CPI", vintage="v1")
        current = dl.series_frame(cat, "fred.CPI")
        asof = dl.series_frame(cat, "fred.CPI", asof="2026-08-09T12:00:00Z")
        with pytest.raises(ValueError):
            dl.series_frame(cat, "fred.CPI", vintage="v1", asof="2026-08-09")
    assert pinned is not None and len(pinned) == 6
    assert current is not None and len(current) == 7
    assert asof is not None and len(asof) == 6  # pointer history resolves to v1


def test_factor_read_matches_the_sealed_derive(store: Path) -> None:
    from ah.data import derive

    with dl.open_catalog(store) as cat:
        fr = dl.factor_read(cat, "equity_mkt")
        mkt = dl.series_frame(cat, "french.mkt_rf")
        rf = dl.series_frame(cat, "french.rf")
    assert fr.frame is not None and fr.note == ""
    assert mkt is not None and rf is not None
    expected = derive.add(mkt, rf)
    np.testing.assert_allclose(fr.frame["value"].to_numpy(), expected["value"].to_numpy())
    # both inputs cover every month -> nothing is proxy
    assert not bool(fr.frame["is_proxy"].any())


def test_factor_read_blanks_absent_optional_donor(store: Path) -> None:
    """equity_vol with fred.VXO absent must be the plain VIX read (campaign-2)."""
    with dl.open_catalog(store) as cat:
        fr = dl.factor_read(cat, "equity_vol")
        vix = dl.series_frame(cat, "fred.VIX")
    assert fr.frame is not None and vix is not None
    np.testing.assert_allclose(fr.frame["value"].to_numpy(), vix["value"].to_numpy())
    assert not bool(fr.frame["is_proxy"].any())
    # the unextended overlay is the same read here, so it exists and agrees
    assert fr.unextended is not None
    np.testing.assert_allclose(fr.unextended["value"].to_numpy(), vix["value"].to_numpy())


def test_proxy_share_arithmetic() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("1985-01-01", periods=10, freq="MS"),
            "value": np.arange(10.0),
            "is_proxy": [True] * 4 + [False] * 6,
            "rule_id": ["A"] * 2 + ["B"] * 2 + [""] * 6,
        }
    )
    share = dl.proxy_share(frame)
    assert share["n_months"] == 10 and share["n_proxy"] == 4
    assert share["share"] == pytest.approx(0.4)
    assert share["by_rule"] == {"A": pytest.approx(0.2), "B": pytest.approx(0.2)}
    windowed = dl.proxy_share(frame, start="1985-05-01")
    assert windowed["n_months"] == 6 and windowed["n_proxy"] == 0


def test_har_fan_is_deterministic_and_carries_the_pinned_draw() -> None:
    from ah.data.vol_backcast import pinned_draw_series

    a = dl.har_fan(n_draws=16, seed=7)
    b = dl.har_fan(n_draws=16, seed=7)
    pd.testing.assert_frame_equal(a, b)
    np.testing.assert_allclose(a["pinned"].to_numpy(), pinned_draw_series().to_numpy())
    assert len(a) == 393
    q = a[[c for c in a.columns if c.startswith("q")]]
    assert (q["q05"] <= q["q50"]).all() and (q["q50"] <= q["q95"]).all()


def test_vintage_diff(store: Path) -> None:
    with dl.open_catalog(store) as cat:
        diff = dl.vintage_diff(cat, "v1", "v2")
    by_id = diff.table.set_index("series_id")
    assert by_id.loc["fred.CPI", "change"] == "grew"
    assert by_id.loc["fred.CPI", "delta"] == 1
    assert by_id.loc["fred.TB3MS", "change"] == "added"
    assert by_id.loc["fred.VIX", "change"] == "same"
    assert diff.status_a == "current" or diff.status_a is not None


def test_span_annotations_come_from_the_owning_code() -> None:
    from ah.gen import bootstrap as bs
    from ah.splits import HOLDOUT, TRAIN

    spans = dl.span_annotations()
    assert spans.train == (TRAIN.start, TRAIN.end)
    assert spans.holdout == (HOLDOUT.start, HOLDOUT.end)
    assert spans.holdout_spent is True
    assert spans.campaign2_span == ("1990-01-01", "2020-12-01")
    assert spans.live_span == (bs.BLOCK_DRAW_SPAN_START, bs.BLOCK_DRAW_SPAN_END)
    assert spans.severe_exclusion == ("1970-01-01", "1979-12-31")


def test_csv_bytes_carries_licence_and_reg_attribution() -> None:
    reqs = load_requirements()
    frame = _frame(["2020-01-01"], [1.0])
    free = dl.csv_bytes(frame, [reqs["fred.CPI"]])
    assert b"licence: fred.CPI = FREE" in free
    assert b"ATTRIBUTION" not in free
    reg = dl.csv_bytes(frame, [reqs["fred.CPI"], reqs["aqr.cmdty_ew_excess"]])
    assert b"licence: aqr.cmdty_ew_excess = REG" in reg
    assert b"ATTRIBUTION" in reg and b"Commodities for the Long Run" in reg
    # the data itself follows the header
    assert reg.endswith(b"2020-01-01,1.0\n")


def test_zero_write_guard() -> None:
    """Neither datalab.py nor the app may touch a store-write call site."""
    write_names = (
        "create_vintage",
        "write_observations",
        "advance_pointer",
        "quarantine_vintage",
        "record_qc",
        "register_series",
        "apply_intake_frames",
    )
    for rel in ("src/ah/datalab.py", "apps/datalab/app.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for name in write_names:
            assert not re.search(rf"\.{name}\(", text), f"{rel} calls {name}"


def test_inline_backgrounds_pin_their_text_color() -> None:
    """Streamlit renders in the viewer's theme: a light inline background
    with the theme's default (near-white) text is invisible in dark mode.
    Any style string painting a background must set color explicitly.

    History: the Series-page staleness highlight shipped as bare
    'background-color: #fee' and its rows were unreadable in dark theme
    (2026-08-10)."""
    text = (ROOT / "apps/datalab/app.py").read_text(encoding="utf-8")
    styles = re.findall(r"['\"]([^'\"]*background-color[^'\"]*)['\"]", text)
    assert styles, "expected at least one inline background style in app.py"
    for style in styles:
        assert re.search(r"(?<!background-)color\s*:", style), (
            f"style {style!r} paints a background without pinning text color"
        )


def test_streamlit_is_not_imported_by_the_package() -> None:
    """The console group stays optional: no src/ah module imports streamlit."""
    for path in (ROOT / "src" / "ah").rglob("*.py"):
        assert "import streamlit" not in path.read_text(encoding="utf-8"), str(path)
