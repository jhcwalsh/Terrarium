"""WP1.1 acceptance: DuckDB catalog + immutable vintage store + as-of reads."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ah.data.catalog import Catalog, CatalogError, ImmutableVintageError
from ah.data.manifest import requirements

NOW = "2026-07-24T00:00:00"


@pytest.fixture
def cat(tmp_path: Path) -> Iterator[Catalog]:
    c = Catalog(tmp_path / "data")
    yield c
    c.close()


def _frame(values: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="MS")]
    return pd.DataFrame({"date": dates, "value": values})


def test_register_series_from_manifest(cat: Catalog) -> None:
    req = requirements()["fred.DGS10"]
    cat.register_series(req)
    row = cat.get_series("fred.DGS10")
    assert row is not None
    assert row["source"] == "fred"
    assert row["redistributable"] is True


def test_write_and_read_observations(cat: Catalog) -> None:
    cat.register_series(requirements()["fred.DGS10"])
    cat.create_vintage("2026-07-24", created_at=NOW)
    cat.write_observations("2026-07-24", "fred.DGS10", _frame([1.0, 2.0, 3.0]))
    df = cat.read_observations("2026-07-24", "fred.DGS10")
    assert list(df.columns) == ["date", "value", "series_id", "vintage"]
    assert df["value"].tolist() == [1.0, 2.0, 3.0]
    assert (df["vintage"] == "2026-07-24").all()


def test_vintage_immutability_second_write_fails(cat: Catalog) -> None:
    cat.register_series(requirements()["fred.DGS10"])
    cat.create_vintage("2026-07-24", created_at=NOW)
    cat.write_observations("2026-07-24", "fred.DGS10", _frame([1.0, 2.0]))
    with pytest.raises(ImmutableVintageError):
        cat.write_observations("2026-07-24", "fred.DGS10", _frame([9.0, 9.0]))


def test_duplicate_vintage_create_fails(cat: Catalog) -> None:
    cat.create_vintage("2026-07-24", created_at=NOW)
    with pytest.raises(ImmutableVintageError):
        cat.create_vintage("2026-07-24", created_at=NOW)


def test_pointer_advances_only_on_qc_pass(cat: Catalog) -> None:
    cat.register_series(requirements()["fred.DGS10"])
    cat.create_vintage("v1", created_at=NOW)
    cat.write_observations("v1", "fred.DGS10", _frame([1.0, 2.0]))

    # QC failed -> quarantine -> pointer must NOT advance
    cat.quarantine_vintage("v1")
    with pytest.raises(CatalogError):
        cat.advance_pointer("v1", when=NOW)
    assert cat.current_vintage() is None

    # a clean vintage advances
    cat.create_vintage("v2", created_at=NOW)
    cat.write_observations("v2", "fred.DGS10", _frame([1.0, 2.0, 3.0]))
    cat.advance_pointer("v2", when="2026-07-24T01:00:00")
    assert cat.current_vintage() == "v2"
    assert cat.vintage_status("v2") == "current"


def test_asof_resolves_through_pointer_history(cat: Catalog) -> None:
    cat.register_series(requirements()["fred.DGS10"])
    cat.create_vintage("2026-06-30", created_at="2026-06-30T00:00:00")
    cat.write_observations("2026-06-30", "fred.DGS10", _frame([1.0, 2.0]))
    cat.advance_pointer("2026-06-30", when="2026-06-30T00:00:00")

    cat.create_vintage("2026-07-31", created_at="2026-07-31T00:00:00")
    cat.write_observations("2026-07-31", "fred.DGS10", _frame([1.0, 2.0, 3.0]))
    cat.advance_pointer("2026-07-31", when="2026-07-31T00:00:00")

    # as of mid-July, the June vintage was current
    assert cat.asof("2026-07-15T00:00:00") == "2026-06-30"
    df = cat.read_asof("fred.DGS10", "2026-07-15T00:00:00")
    assert df["value"].tolist() == [1.0, 2.0]
    # latest reflects the July vintage
    assert cat.read_asof("fred.DGS10", "2026-08-01T00:00:00")["value"].tolist() == [1.0, 2.0, 3.0]


def test_asof_determinism(cat: Catalog) -> None:
    cat.register_series(requirements()["fred.DGS10"])
    cat.create_vintage("v1", created_at=NOW)
    cat.write_observations("v1", "fred.DGS10", _frame([1.0, 2.0, 3.0]))
    cat.advance_pointer("v1", when=NOW)
    a = cat.read_asof("fred.DGS10", "2026-12-01T00:00:00")
    b = cat.read_asof("fred.DGS10", "2026-12-01T00:00:00")
    pd.testing.assert_frame_equal(a, b)


def test_qc_and_intake_logs(cat: Catalog) -> None:
    cat.create_vintage("v1", created_at=NOW)
    cat.record_qc(
        vintage_id="v1",
        series_id="fred.DGS10",
        rule="bounds",
        severity="enforce",
        passed=True,
        detail="ok",
        created_at=NOW,
    )
    cat.record_intake(
        source="albourne",
        file="pm_2026Q2.csv",
        sha256="abc",
        received_at=NOW,
        status="accepted",
        report="clean",
    )
    qc_count = cat.con.execute("SELECT COUNT(*) FROM qc_results").fetchone()
    intake_count = cat.con.execute("SELECT COUNT(*) FROM intake_log").fetchone()
    assert qc_count is not None and qc_count[0] == 1
    assert intake_count is not None and intake_count[0] == 1
