"""WP1.8 acceptance: episode packs resolve through the catalog and render a brief."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.episode import (
    EpisodePack,
    build_episode,
    episode_years,
    secondary_pricing,
)
from ah.data.manifest import requirements

REQ = requirements()
NOW = "2026-07-24T00:00:00"


@pytest.fixture
def cat(tmp_path: Path) -> Iterator[Catalog]:
    c = Catalog(tmp_path / "data")
    yield c
    c.close()


def _monthly(values: list[float], start: str) -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="MS")]
    return pd.DataFrame({"date": dates, "value": values})


def _quarterly(values: list[float], start: str) -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="QS")]
    return pd.DataFrame({"date": dates, "value": values})


def _populate_2022(cat: Catalog) -> None:
    cat.register_series(REQ["fred.HY_OAS"])
    cat.register_series(REQ["albourne.pm_buyout_ret_q"])
    cat.create_vintage("2024-01-01", created_at=NOW)
    # HY OAS monthly across 2021-2023
    cat.write_observations(
        "2024-01-01", "fred.HY_OAS", _monthly([4.0 + 0.1 * i for i in range(36)], "2021-01-01")
    )
    # a smoothed PM buyout series (quarterly) across 2021-2023
    rng = np.random.Generator(np.random.PCG64(0))
    truth = rng.normal(0, 0.05, 12)
    obs = np.array(
        [
            0.5 * truth[t] + 0.3 * truth[t - 1] + 0.2 * truth[t - 2] if t >= 2 else truth[t]
            for t in range(12)
        ]
    )
    cat.write_observations(
        "2024-01-01", "albourne.pm_buyout_ret_q", _quarterly(list(obs), "2021-01-01")
    )
    cat.advance_pointer("2024-01-01", when=NOW)


def test_episode_years() -> None:
    assert episode_years() == [2008, 2020, 2022]


def test_secondary_pricing_2022_anchor() -> None:
    sp = secondary_pricing(2022)
    assert list(sp["period"]) == ["2022-H1", "2022-H2"]
    assert sp["pct_of_nav"].iloc[-1] == 0.81  # the ~81% NAV anchor


def test_build_episode_resolves_through_catalog(cat: Catalog) -> None:
    _populate_2022(cat)
    pack = build_episode(cat, 2022, ["fred.HY_OAS", "albourne.pm_buyout_ret_q"])
    assert isinstance(pack, EpisodePack)
    assert pack.year == 2022
    # HY OAS sliced to the 2022-2023 window (24 of 36 months)
    assert "fred.HY_OAS" in pack.frames
    assert pack.frames["fred.HY_OAS"]["date"].min() >= pd.Timestamp("2022-01-01")
    # PM sleeve gets a de-smoothed companion
    assert "albourne.pm_buyout_ret_q" in pack.frames
    assert "albourne.pm_buyout_ret_q__desmoothed" in pack.frames


def test_build_episode_brief_renders(cat: Catalog) -> None:
    _populate_2022(cat)
    pack = build_episode(cat, 2022, ["fred.HY_OAS", "albourne.pm_buyout_ret_q"])
    assert "Episode brief - 2022" in pack.brief
    assert "Secondary-market pricing" in pack.brief
    assert "0.81" in pack.brief
    assert "secondaries.md" in pack.brief


def test_build_episode_unknown_year_raises(cat: Catalog) -> None:
    with pytest.raises(KeyError):
        build_episode(cat, 1999, [])


def test_build_episode_skips_absent_series(cat: Catalog) -> None:
    _populate_2022(cat)
    pack = build_episode(cat, 2022, ["fred.DGS10"])  # not populated
    assert "fred.DGS10" not in pack.frames  # gracefully skipped, no crash
    assert pack.secondary_pricing is not None
