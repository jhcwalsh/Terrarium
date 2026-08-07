"""Tests for the generator-input data console. Read-only; no network.

``enable_socket`` is the same sanctioned opt-in ``test_serve.py`` uses: the
TestClient's event loop needs an in-process socketpair on Windows, which
pytest-socket blocks by default. Nothing here touches the network.
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ah.dataconsole import (
    coverage_pct,
    create_app,
    gap_ranges,
    moments,
    proxy_pct,
    staleness_days,
)

pytestmark = pytest.mark.enable_socket


def test_gap_ranges_finds_missing_months():
    dates = pd.Series(pd.to_datetime(["2020-01-01", "2020-02-01", "2020-05-01"]))
    assert gap_ranges(dates) == [("2020-03", "2020-04")]
    assert coverage_pct(dates) == pytest.approx(3 / 5)


def test_staleness_and_proxy_pct():
    assert staleness_days("2026-06-01", "2026-08-07") == 67
    f = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0], "is_proxy": [True, True, False, False]})
    assert proxy_pct(f) == pytest.approx(0.5)
    assert proxy_pct(pd.DataFrame({"value": [1.0]})) == 0.0  # no column -> all actual


def test_moments_shapes():
    m = moments(np.array([0.01, -0.02, 0.03, 0.005, -0.01]))
    assert set(m) == {"mean", "vol", "skew", "excess_kurtosis"}


def _tiny_store(tmp_path):
    """A real Catalog with two series across one vintage; built with the
    store's own API (writing happens in the TEST, never in the module)."""
    from ah.data.catalog import Catalog
    from ah.data.manifest import load_requirements

    cat = Catalog(tmp_path)
    reqs = load_requirements()
    cat.create_vintage("v1", created_at="2026-08-07T00:00:00Z", status="pending")
    for sid, vals in [("fred.CPI", [100.0, 101.0, 102.0]), ("french.mkt_rf", [0.01, -0.02, 0.03])]:
        cat.register_series(reqs[sid])
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
                "value": vals,
                "series_id": sid,
                "vintage": "v1",
            }
        )
        cat.write_observations("v1", sid, frame)
    cat.record_qc(
        vintage_id="v1",
        series_id="fred.CPI",
        rule="bounds",
        severity="enforce",
        passed=True,
        detail="",
        created_at="2026-08-07",
    )
    cat.advance_pointer("v1", when="2026-08-07T00:00:00Z")
    cat.close()
    return tmp_path


def test_series_page_renders_chart_gaps_and_manifest(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/series/fred.CPI")
    assert r.status_code == 200
    assert "<svg" in r.text
    assert "CPIAUCNS" in r.text  # manifest entry verbatim (code)
    assert "bounds" in r.text  # its QC finding
    assert c.get("/series/no.such").status_code == 404


def test_proxy_shading_present_when_flagged():
    from ah.dataconsole import line_svg

    f = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
            "value": [1.0, 2.0, 3.0],
            "is_proxy": [True, False, False],
        }
    )
    out = line_svg(f, title="t")
    assert "proxy" in out  # shaded region carries a class/label
    assert line_svg(f.drop(columns=["is_proxy"]), title="t").count("proxy") == 0


def test_inventory_page(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/")
    assert r.status_code == 200
    assert "DATA INSPECTION" in r.text  # watermark
    assert "v1" in r.text  # current vintage
    assert "fred.CPI" in r.text and "french.mkt_rf" in r.text
    assert "registered, never fetched" in r.text  # the other manifest series


def test_empty_store_is_a_card_not_a_traceback(tmp_path):
    c = TestClient(create_app(data_root=tmp_path / "empty"))
    r = c.get("/")
    assert r.status_code == 200
    assert "Not available" in r.text
