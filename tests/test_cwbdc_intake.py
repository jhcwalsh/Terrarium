"""The Cliffwater BDC delivery: units conversion and the intake path. Offline."""

from __future__ import annotations

import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.connectors.base import ConnectorError
from ah.data.connectors.cliffwater_bdc import to_drop_frame
from ah.data.intake import ingest_file, to_series_frames
from ah.data.manifest import load_requirements
from ah.data.refresh import apply_intake_frames
from ah.data.schemas import get_schema


def _vendor_rows() -> pd.DataFrame:
    """The vendor shape verbatim: a base row with no return, then percents."""
    return pd.DataFrame(
        {
            "date": ["2004-09-30", "2004-10-29", "2004-11-30", "2020-03-31"],
            "total_return_pct": [None, -0.06603614873, 3.6384583173159, -35.4812],
            "total_return_index": [1000.0, 999.3396385127, 1035.7001947084, 2000.0],
            "dividend_yield_pct": [None, 0.0456370629208594, 0.0444041812086363, 0.1500],
        }
    )


def test_percent_becomes_fraction_and_the_base_row_is_dropped():
    out = to_drop_frame(_vendor_rows())
    assert list(out.columns) == ["period", "ret"]
    assert len(out) == 3  # the index-base row carries no observation
    assert out["period"].tolist() == ["2004-10", "2004-11", "2020-03"]
    assert out["ret"].iloc[0] == pytest.approx(-0.0006603614873)
    assert out["ret"].iloc[1] == pytest.approx(0.036384583173159)
    # the COVID month must survive the schema bounds as a fraction, not a percent
    assert out["ret"].iloc[2] == pytest.approx(-0.354812)


def test_malformed_deliveries_are_named_not_swallowed():
    with pytest.raises(ConnectorError, match="missing column"):
        to_drop_frame(pd.DataFrame({"date": ["2004-10-29"]}))
    with pytest.raises(ConnectorError, match="no total-return"):
        to_drop_frame(pd.DataFrame({"date": ["2004-09-30"], "total_return_pct": [None]}))
    with pytest.raises(ConnectorError, match="duplicate months"):
        to_drop_frame(
            pd.DataFrame({"date": ["2004-10-29", "2004-10-30"], "total_return_pct": [1.0, 2.0]})
        )


def test_schema_admits_the_covid_month_and_rejects_a_percent_slip():
    schema = get_schema("cliffwater_bdc")
    assert schema is not None and schema.frequency == "M"
    good = pd.DataFrame({"period": ["2020-03"], "ret": [-0.354812]})
    assert schema.validate(good) == []
    # -35.48 (a percent left unconverted) is out of bounds and must be caught
    bad = pd.DataFrame({"period": ["2020-03"], "ret": [-35.4812]})
    assert any(v.column == "ret" for v in schema.validate(bad))


def test_drop_lands_in_the_store_through_the_standard_intake_path(tmp_path):
    frame = to_drop_frame(
        pd.DataFrame(
            {
                "date": pd.date_range("2026-01-31", periods=6, freq="ME"),
                "total_return_pct": [1.0, -2.0, 0.5, 1.5, -0.75, 2.25],
            }
        )
    )
    drop = tmp_path / "cliffwater-bdc_2026-08-08.csv"
    frame.to_csv(drop, index=False)

    schema = get_schema("cliffwater_bdc")
    assert schema is not None
    cat = Catalog(tmp_path / "store")
    try:
        result = ingest_file(cat, drop, schema, received_at="2026-08-08T00:00:00Z")
        assert result.accepted, result.report
        assert result.frame is not None
        frames = {
            "cliffwater.bdc_ret_m": next(iter(to_series_frames(schema, result.frame).values()))
        }
        outcome = apply_intake_frames(
            cat,
            load_requirements(),
            frames=frames,
            vintage="2026-08-08.1",
            asof="2026-08-08",
            created_at="2026-08-08T00:00:00Z",
        )
        assert not outcome.already_exists
        assert not outcome.quarantined, outcome.qc
        stored = cat.read_observations("2026-08-08.1", "cliffwater.bdc_ret_m")
        assert len(stored) == 6
        assert stored["value"].iloc[0] == pytest.approx(0.01)
    finally:
        cat.close()


def test_bdc_is_registered_as_its_own_series_not_as_cdli():
    """The delivery is the BDC index; CDLI stays unfetched and separately
    registered. Conflating them would file listed, levered, market-priced
    returns under an asset-level appraisal-marked series id."""
    reqs = load_requirements()
    bdc, cdli = reqs["cliffwater.bdc_ret_m"], reqs["cliffwater.cdli_ret_q"]
    assert (bdc.frequency, bdc.code) == ("M", "CWBDC")
    assert (cdli.frequency, cdli.code) == ("Q", "CDLI")
    assert bdc.units == cdli.units == "ret"
    assert "VALIDATION ANCHOR" in (bdc.notes or "")
