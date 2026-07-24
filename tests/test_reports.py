"""WP1.9 acceptance: gap register + status reports."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.manifest import Requirements, requirements
from ah.data.reports import (
    ANTICIPATED_ADDITIONS,
    gap_register,
    generate_data_status_md,
    generate_gaps_md,
    series_gap,
)

REQ = requirements()
NOW = "2026-07-24T00:00:00"
ASOF = "2026-07-01"


@pytest.fixture
def cat(tmp_path: Path) -> Iterator[Catalog]:
    c = Catalog(tmp_path / "data")
    yield c
    c.close()


def _monthly(values: list[float], start: str) -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="MS")]
    return pd.DataFrame({"date": dates, "value": values})


def test_absent_series_is_full_gap(cat: Catalog) -> None:
    cat.create_vintage("v1", created_at=NOW)
    cat.advance_pointer("v1", when=NOW)
    g = series_gap(cat, REQ["fred.DGS10"], asof=ASOF)
    assert not g.present
    assert g.coverage_pct == 0.0
    assert g.missing_head and g.stale


def test_licensed_manual_blocker(cat: Catalog) -> None:
    cat.create_vintage("v1", created_at=NOW)
    cat.advance_pointer("v1", when=NOW)
    g = series_gap(cat, REQ["albourne.pm_buyout_ret_q"], asof=ASOF)
    assert g.license_blocker is not None
    assert g.license_tier == "COMM"


def test_present_series_coverage_and_freshness(cat: Catalog) -> None:
    cat.register_series(REQ["fred.DGS10"])
    cat.create_vintage("v1", created_at=NOW)
    # 6 recent months up to mid-2026
    cat.write_observations("v1", "fred.DGS10", _monthly([2.0] * 6, "2026-01-01"))
    cat.advance_pointer("v1", when=NOW)
    g = series_gap(cat, REQ["fred.DGS10"], asof=ASOF)
    assert g.present
    assert g.n_obs == 6
    assert g.missing_head  # min_start 1962 but data starts 2026 -> head missing
    assert 0.0 <= g.coverage_pct <= 100.0
    assert g.stale  # 6-month-old last obs vs a 7-day SLA


def test_generate_gaps_md_has_anticipated(cat: Catalog) -> None:
    cat.create_vintage("v1", created_at=NOW)
    cat.advance_pointer("v1", when=NOW)
    gaps = gap_register(cat, REQ, asof=ASOF)
    md = generate_gaps_md(gaps)
    assert "GAPS.md" in md
    assert "Anticipated additions" in md
    assert "MSCI World" in md
    assert "emergent-requirements" in md.lower() or "unregistered series" in md
    assert len(ANTICIPATED_ADDITIONS) >= 8


def test_generate_data_status_md(cat: Catalog) -> None:
    cat.register_series(REQ["fred.DGS10"])
    cat.create_vintage("v1", created_at=NOW)
    cat.write_observations("v1", "fred.DGS10", _monthly([2.0, 2.1], "2026-05-01"))
    cat.record_qc(
        vintage_id="v1",
        series_id="fred.DGS10",
        rule="bounds_high",
        severity="enforce",
        passed=True,
        detail="ok",
        created_at=NOW,
    )
    cat.advance_pointer("v1", when=NOW)
    md = generate_data_status_md(cat, REQ, asof=ASOF)
    assert "DATA-STATUS.md" in md
    assert "v1" in md
    assert "fred" in md
    assert "QC summary" in md


def test_gap_register_covers_all_requirements(cat: Catalog) -> None:
    cat.create_vintage("v1", created_at=NOW)
    cat.advance_pointer("v1", when=NOW)
    gaps = gap_register(cat, REQ, asof=ASOF)
    assert len(gaps) == len(REQ)
    assert isinstance(REQ, Requirements)
