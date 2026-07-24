"""WP1.10 acceptance: refresh orchestration (plan → QC → commit/quarantine)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.manifest import Requirement, requirements
from ah.data.refresh import csv_dir_provider, plan, refresh

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
