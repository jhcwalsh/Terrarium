"""WP1.4 acceptance: QC rules + quarantine gate."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ah.data.catalog import Catalog, CatalogError
from ah.data.manifest import requirements
from ah.data.qc import (
    QCFinding,
    check_cross_series,
    check_series,
    run_qc,
)

REQ = requirements()
NOW = "2026-07-24T00:00:00"


def _monthly(values: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="MS")]
    return pd.DataFrame({"date": dates, "value": values})


def _finding(findings: list[QCFinding], rule: str) -> QCFinding:
    return next(f for f in findings if f.rule == rule)


@pytest.fixture
def cat(tmp_path: Path) -> Iterator[Catalog]:
    c = Catalog(tmp_path / "data")
    yield c
    c.close()


# --------------------------------------------------------------------------- #
# per-series rules
# --------------------------------------------------------------------------- #


def test_bounds_rate_in_and_out_of_range() -> None:
    ok = check_series(REQ["fred.DGS10"], _monthly([1.0, 2.0, 3.0]), asof=None)
    assert _finding(ok, "bounds_high").passed
    bad = check_series(REQ["fred.DGS10"], _monthly([1.0, 99.0]), asof=None)
    assert not _finding(bad, "bounds_high").passed
    assert _finding(bad, "bounds_high").severity == "enforce"  # DGS10 enforce=true


def test_spread_lower_bound_zero() -> None:
    findings = check_series(REQ["fred.HY_OAS"], _monthly([2.0, -1.0]), asof=None)
    assert not _finding(findings, "bounds_low").passed  # spread must be >= 0


def test_returns_bounds() -> None:
    findings = check_series(REQ["french.mkt_rf"], _monthly([0.05, 3.0]), asof=None)
    # french.mkt_rf units 'ret' -> upper 2.0
    assert not _finding(findings, "bounds_high").passed


def test_index_strictly_positive() -> None:
    findings = check_series(REQ["fred.CPI"], _monthly([100.0, 0.0]), asof=None)
    assert not _finding(findings, "positive").passed


def test_monotonic_and_duplicates() -> None:
    df = pd.DataFrame(
        {"date": ["2020-02-01", "2020-01-01", "2020-01-01"], "value": [1.0, 2.0, 3.0]}
    )
    findings = check_series(REQ["fred.DGS10"], df, asof=None)
    assert not _finding(findings, "monotonic").passed
    assert not _finding(findings, "no_duplicates").passed


def test_frequency_conformance() -> None:
    ok = check_series(REQ["fred.TB3MS"], _monthly([1.0, 1.1, 1.2]), asof=None)
    assert _finding(ok, "frequency").passed
    gapped = pd.DataFrame(
        {"date": ["2020-01-01", "2020-02-01", "2020-05-01"], "value": [1.0, 1.1, 1.2]}
    )
    assert not _finding(check_series(REQ["fred.TB3MS"], gapped, asof=None), "frequency").passed


def test_staleness() -> None:
    fresh = check_series(REQ["fred.DGS10"], _monthly([1.0, 2.0]), asof="2020-02-05")
    assert _finding(fresh, "staleness").passed
    stale = check_series(REQ["fred.DGS10"], _monthly([1.0, 2.0]), asof="2021-01-01")
    assert not _finding(stale, "staleness").passed


def test_jump_detection_is_warn() -> None:
    values = [1.0, 1.01, 0.99, 1.0, 1.02, 0.98, 1.0, 50.0]  # a huge spike
    findings = check_series(REQ["fred.DGS10"], _monthly(values), asof=None)
    jump = _finding(findings, "jump")
    assert not jump.passed
    assert jump.severity == "warn"


def test_revision_diff_public_warn_vs_licensed_enforce() -> None:
    prior = _monthly([1.0, 2.0, 3.0])
    revised = _monthly([1.0, 2.5, 3.0])  # a historical value changed
    pub = check_series(REQ["fred.DGS10"], revised, asof=None, prior=prior)
    assert _finding(pub, "revision_diff").severity == "warn"
    assert not _finding(pub, "revision_diff").passed

    lic = check_series(
        REQ["cliffwater.cdli_ret_q"],
        _monthly([0.02, 0.03]),
        asof=None,
        prior=_monthly([0.02, 0.04]),
    )
    assert _finding(lic, "revision_diff").severity == "enforce"
    assert not _finding(lic, "revision_diff").passed


# --------------------------------------------------------------------------- #
# cross-series
# --------------------------------------------------------------------------- #


def test_cross_series_baa_ge_aaa() -> None:
    frames = {
        "fred.BAA": _monthly([5.0, 6.0]),
        "fred.AAA": _monthly([4.0, 4.5]),
    }
    assert _finding(check_cross_series(frames), "identity_baa_ge_aaa").passed
    frames["fred.BAA"] = _monthly([3.0, 6.0])  # Baa < Aaa in month 1
    assert not _finding(check_cross_series(frames), "identity_baa_ge_aaa").passed


# --------------------------------------------------------------------------- #
# orchestration + quarantine gate
# --------------------------------------------------------------------------- #


def test_run_qc_clean_allows_pointer_advance(cat: Catalog) -> None:
    cat.register_series(REQ["fred.DGS10"])
    cat.create_vintage("v1", created_at=NOW)
    frame = _monthly([1.0, 2.0, 3.0])
    cat.write_observations("v1", "fred.DGS10", frame)
    report = run_qc(cat, "v1", [(REQ["fred.DGS10"], frame)], asof="2020-03-05", created_at=NOW)
    assert report.passed
    cat.advance_pointer("v1", when=NOW)
    assert cat.current_vintage() == "v1"
    # qc_results were written
    count = cat.con.execute("SELECT COUNT(*) FROM qc_results").fetchone()
    assert count is not None and count[0] > 0


def test_run_qc_enforce_failure_quarantines(cat: Catalog) -> None:
    cat.register_series(REQ["fred.DGS10"])
    cat.create_vintage("v1", created_at=NOW)
    frame = _monthly([1.0, 999.0])  # out of bounds (enforce)
    cat.write_observations("v1", "fred.DGS10", frame)
    report = run_qc(cat, "v1", [(REQ["fred.DGS10"], frame)], asof="2020-03-05", created_at=NOW)
    assert not report.passed
    assert cat.vintage_status("v1") == "quarantined"
    with pytest.raises(CatalogError):
        cat.advance_pointer("v1", when=NOW)
