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
    for sid, vals in [
        ("fred.CPI", [100.0, 101.0, 102.0]),
        ("french.mkt_rf", [0.01, -0.02, 0.03]),
        ("french.rf", [0.001, 0.001, 0.001]),
    ]:
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


def _add_albourne(root, sid, n=40):
    """Append a quarterly private-markets series to vintage v1: AR(1)-smoothed
    seeded returns, so de-smoothing has structure to recover. Deterministic."""
    from numpy.random import PCG64, Generator

    from ah.data.catalog import Catalog
    from ah.data.manifest import load_requirements

    rng = Generator(PCG64(0))
    true = rng.normal(0.02, 0.06, n)
    obs = np.empty(n)
    obs[0] = true[0]
    for i in range(1, n):
        obs[i] = 0.6 * obs[i - 1] + 0.4 * true[i]
    cat = Catalog(root)
    cat.register_series(load_requirements()[sid])
    frame = pd.DataFrame(
        {
            "date": pd.period_range("2010Q1", periods=n, freq="Q").to_timestamp(),
            "value": obs,
            "series_id": sid,
            "vintage": "v1",
        }
    )
    cat.write_observations("v1", sid, frame)
    cat.close()
    return root


def test_class_page_lists_raw_and_factors(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/class/equities")
    assert r.status_code == 200
    assert "french.mkt_rf" in r.text
    assert "registered, never fetched" in r.text  # shiller series absent from tiny store
    assert c.get("/class/no-such").status_code == 404


def test_factors_page_renders_every_declared_factor(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    r = c.get("/factors")
    assert r.status_code == 200
    assert "train" in r.text and "validation" in r.text
    assert "SPENT" in r.text  # holdout labeling
    assert "absent" in r.text or "unavailable" in r.text  # tiny store lacks most inputs


def test_factor_frame_derived_matches_derive(tmp_path):
    """A derived factor recomputed through _factor_frame == calling derive directly."""
    from ah.data import derive
    from ah.data.catalog import Catalog
    from ah.dataconsole import _factor_frame
    from ah.factors import load_manifest

    root = _tiny_store(tmp_path)
    manifest = load_manifest()
    # equity_mkt is derived: add(french.mkt_rf, french.rf) — both in the tiny store
    fs = manifest.sources["equity_mkt"]
    assert fs.kind == "derived"
    cat = Catalog(root)
    try:
        frame, note = _factor_frame(cat, "v1", fs)
        assert note == "" and frame is not None
        direct = getattr(derive, str(fs.expr))(
            *[cat.read_observations("v1", sid) for sid in fs.inputs]
        )
        pd.testing.assert_frame_equal(frame, direct)
    finally:
        cat.close()


def test_privates_page_shows_desmoothing_overlay(tmp_path):
    root = _add_albourne(_tiny_store(tmp_path), "albourne.pm_buyout_ret_q", n=40)
    c = TestClient(create_app(data_root=root))
    r = c.get("/class/privates")
    assert r.status_code == 200
    assert "de-smoothed" in r.text
    assert "reported" in r.text
    assert "<table" in r.text  # side-by-side moments table


def test_proxy_factor_gets_mechanical_proxy_mask(tmp_path):
    """hy_spread (proxy: true) — the sealed derive strips is_proxy by design,
    so the console recomputes the mask from the splice contract itself:
    actuals are never touched, so any factor date absent from the target
    series (inputs[0]) is proxy by construction."""
    from ah.data.catalog import Catalog
    from ah.data.manifest import load_requirements
    from ah.dataconsole import _factor_frame
    from ah.factors import load_manifest

    root = _tiny_store(tmp_path)
    cat = Catalog(root)
    reqs = load_requirements()
    months = pd.to_datetime(
        ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01", "2020-05-01", "2020-06-01"]
    )
    for sid, vals in [
        ("fred.BAA", [5.0, 5.1, 5.2, 5.3, 5.4, 5.5]),
        ("fred.AAA", [4.0, 4.0, 4.1, 4.1, 4.2, 4.2]),
    ]:
        cat.register_series(reqs[sid])
        cat.write_observations(
            "v1",
            sid,
            pd.DataFrame({"date": months, "value": vals, "series_id": sid, "vintage": "v1"}),
        )
    # target series exists only for the last two months -> first four are proxy
    cat.register_series(reqs["fred.HY_OAS"])
    cat.write_observations(
        "v1",
        "fred.HY_OAS",
        pd.DataFrame(
            {
                "date": months[-2:],
                "value": [3.5, 3.6],
                "series_id": "fred.HY_OAS",
                "vintage": "v1",
            }
        ),
    )
    try:
        fs = load_manifest().sources["hy_spread"]
        frame, note = _factor_frame(cat, "v1", fs)
        assert note == "" and frame is not None
        assert "is_proxy" in frame.columns
        flags = frame.sort_values("date")["is_proxy"].tolist()
        assert flags[:4] == [True, True, True, True]
        assert flags[-2:] == [False, False]
    finally:
        cat.close()


def test_source_links_resolve_for_every_registered_series():
    """Owner request 2026-08-08: every series carries its source link. The
    resolver must cover all 79 registered entries, never render an API key,
    and give fred.BAA its exact per-series page."""
    from ah.data.manifest import Requirement, load_requirements, source_link

    reqs = load_requirements()
    for r in reqs:
        url = source_link(r)
        assert url, f"{r.series_id}: no source link resolves"
        assert url.startswith(("http://", "https://"))
        assert "api_key" not in url and "apikey" not in url.lower()
    assert source_link(reqs["fred.BAA"]) == "https://fred.stlouisfed.org/series/BAA"
    # per-entry override wins over the template
    override = Requirement(
        series_id="x.y",
        source="fred",
        code="Z",
        frequency="M",
        units="pct",
        sla_days=1,
        license_tier="FREE",
        priority="P2",
        source_url="https://example.org/custom",
    )
    assert source_link(override) == "https://example.org/custom"


def test_series_page_and_inventory_render_the_link(tmp_path):
    c = TestClient(create_app(data_root=_tiny_store(tmp_path)))
    assert "https://fred.stlouisfed.org/series/CPIAUCNS" in c.get("/series/fred.CPI").text
    assert "https://fred.stlouisfed.org/series/CPIAUCNS" in c.get("/").text


def test_dataconsole_is_read_only():
    """The data console's contract: zero write call sites, ever.

    Same source-scan technique as the programme/buildconsole guards: a future
    edit that adds any store-writing call fails loudly here.
    """
    import inspect

    import ah.dataconsole as dc

    src = inspect.getsource(dc)
    for needle in (
        "write_observations(",
        "create_vintage(",
        "advance_pointer(",
        "quarantine_vintage(",
        "record_qc(",
        "record_intake(",
        "register_series(",
        "INSERT",
        "UPDATE",
        "DELETE",
        "to_parquet(",
        ".save_",
    ):
        assert needle not in src, f"read-only surface contains {needle}"
