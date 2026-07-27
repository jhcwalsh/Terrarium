"""WP1.10 acceptance: refresh orchestration (plan → QC → commit/quarantine)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.manifest import Requirement, requirements
from ah.data.refresh import connector_provider, csv_dir_provider, plan, refresh

REQ = requirements()
NOW = "2026-06-05T00:00:00"
ASOF = "2026-06-05"


@pytest.fixture
def cat(tmp_path: Path) -> Iterator[Catalog]:
    c = Catalog(tmp_path / "data")
    yield c
    c.close()


def _monthly(values: list[float], start: str = "2026-01-01") -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="MS")]
    return pd.DataFrame({"date": dates, "value": values})


def _provider(frames: dict[str, pd.DataFrame]):
    def p(req: Requirement) -> pd.DataFrame | None:
        return frames.get(req.series_id)

    return p


def test_plan_includes_auto_excludes_manual(cat: Catalog) -> None:
    due = plan(REQ, cat, asof=ASOF)
    ids = {r.series_id for r in due}
    assert "fred.DGS10" in ids  # auto + not present -> due
    assert "albourne.pm_buyout_ret_q" not in ids  # manual -> never auto-refreshed


def test_plan_source_filter(cat: Catalog) -> None:
    due = plan(REQ, cat, asof=ASOF, sources=["fred"])
    assert all(r.source == "fred" for r in due)


def test_refresh_commits_and_advances(cat: Catalog) -> None:
    frames = {"fred.DGS10": _monthly([2.0, 2.1, 2.2])}  # last obs 2026-03, fresh vs ASOF? no
    frames = {"fred.DGS10": _monthly([2.0, 2.1], start="2026-05-01")}  # last 2026-06-01
    result = refresh(
        cat,
        REQ,
        vintage="2026-06-05",
        asof=ASOF,
        provider=_provider(frames),
        created_at=NOW,
        sources=["fred"],
    )
    assert "fred.DGS10" in result.written
    assert not result.quarantined
    assert cat.current_vintage() == "2026-06-05"
    assert result.gaps_md and result.status_md


def test_refresh_is_idempotent(cat: Catalog) -> None:
    frames = {"fred.DGS10": _monthly([2.0, 2.1], start="2026-05-01")}
    first = refresh(
        cat,
        REQ,
        vintage="v1",
        asof=ASOF,
        provider=_provider(frames),
        created_at=NOW,
        sources=["fred"],
    )
    assert not first.already_exists
    second = refresh(
        cat,
        REQ,
        vintage="v1",
        asof=ASOF,
        provider=_provider(frames),
        created_at=NOW,
        sources=["fred"],
    )
    assert second.already_exists  # detected, no duplicate vintage
    assert second.written == []


def test_refresh_carries_forward_series_it_did_not_fetch(cat: Catalog) -> None:
    """A vintage is a complete snapshot: a fresh, non-due series must not vanish.

    ``plan`` only fetches missing-or-stale series, and every read pins one vintage, so
    without carry-forward the second refresh drops everything the first one made fresh.
    """
    frames = {
        "fred.DGS10": _monthly([2.0, 2.1], start="2026-05-01"),
        "fred.GS10": _monthly([3.0, 3.1], start="2026-05-01"),
    }
    first = refresh(
        cat,
        REQ,
        vintage="v1",
        asof=ASOF,
        provider=_provider(frames),
        created_at=NOW,
        sources=["fred"],
    )
    assert {"fred.DGS10", "fred.GS10"} <= set(first.written)

    # Second refresh: both are present and fresh, so neither is due and the provider
    # offers nothing at all. They must still be readable from the new vintage.
    second = refresh(
        cat, REQ, vintage="v2", asof=ASOF, provider=_provider({}), created_at=NOW, sources=["fred"]
    )
    assert "fred.DGS10" not in second.written
    assert {"fred.DGS10", "fred.GS10"} <= set(second.carried_forward)
    carried = cat.read_observations("v2", "fred.DGS10")
    original = cat.read_observations("v1", "fred.DGS10")
    assert len(carried) == len(original)
    assert list(carried["value"]) == list(original["value"])
    assert set(carried["vintage"]) == {"v2"}  # re-stamped, not a rewrite of v1
    assert set(original["vintage"]) == {"v1"}  # the older vintage is untouched


def test_refresh_dry_run_writes_nothing(cat: Catalog) -> None:
    result = refresh(
        cat, REQ, vintage="v1", asof=ASOF, provider=_provider({}), created_at=NOW, dry_run=True
    )
    assert result.dry_run
    assert result.planned  # some series are due
    assert cat.vintage_status("v1") is None  # no vintage created


def test_refresh_quarantines_on_qc_failure(cat: Catalog) -> None:
    frames = {"fred.DGS10": _monthly([2.0, 999.0], start="2026-05-01")}  # out of bounds
    result = refresh(
        cat,
        REQ,
        vintage="v1",
        asof=ASOF,
        provider=_provider(frames),
        created_at=NOW,
        sources=["fred"],
    )
    assert result.quarantined
    assert cat.current_vintage() is None  # pointer not advanced
    assert cat.vintage_status("v1") == "quarantined"


def test_csv_dir_provider(tmp_path: Path) -> None:
    _monthly([1.0, 2.0]).to_csv(tmp_path / "fred.DGS10.csv", index=False)
    provider = csv_dir_provider(tmp_path)
    assert provider(REQ["fred.DGS10"]) is not None
    assert provider(REQ["fred.GS10"]) is None  # absent


class _FakeConn:
    def __init__(self, source: str) -> None:
        self.source = source
        self.fetches = 0

    def fetch(self, req: Requirement) -> str:
        self.fetches += 1
        return f"raw:{req.series_id}"

    def parse(self, raw: str, req: Requirement) -> pd.DataFrame:
        return _monthly([1.0])


def test_connector_provider_maps_and_caches_shared_files() -> None:
    fred, french = _FakeConn("fred"), _FakeConn("french")
    provider = connector_provider({"fred": fred, "french": french})

    assert provider(REQ["fred.DGS10"]) is not None
    assert provider(REQ["shiller.price"]) is None  # no connector for that source

    # French (shared file) is fetched once even across multiple series
    provider(REQ["french.mkt_rf"])
    provider(REQ["french.smb"])
    assert french.fetches == 1
    # FRED fetches per series
    provider(REQ["fred.GS10"])
    assert fred.fetches == 2
