"""WP2R.2 — the manual-intake last mile (apply_intake_frames).

Half of RFR-88's fix, as tests: an accepted drop's frames reach the vintage
store through exactly refresh()'s discipline — registered ids only, QC judged,
pointer advanced on pass and held on quarantine, idempotent per vintage.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.manifest import requirements
from ah.data.refresh import apply_intake_frames

REQ = requirements()
NOW = "2026-08-01T00:00:00"
ASOF = "2026-08-01"
SID = "albourne.hf_us_ls_ret_m"  # a registered WP2R.2 sub-strategy series


@pytest.fixture
def cat(tmp_path: Path) -> Iterator[Catalog]:
    c = Catalog(tmp_path / "data")
    yield c
    c.close()


def _monthly(values: list[float], start: str) -> pd.DataFrame:
    dates = [ts.date() for ts in pd.date_range(start, periods=len(values), freq="MS")]
    return pd.DataFrame({"date": dates, "value": values})


def test_unregistered_series_id_is_a_loud_error(cat: Catalog) -> None:
    with pytest.raises(ValueError, match=r"albourne\.not_registered"):
        apply_intake_frames(
            cat,
            REQ,
            frames={"albourne.not_registered": _monthly([0.01], "2026-06-01")},
            vintage="v1",
            asof=ASOF,
            created_at=NOW,
        )


def test_fresh_accepted_frames_advance_the_pointer(cat: Catalog) -> None:
    frames = {SID: _monthly([0.01, -0.02, 0.005], "2026-05-01")}  # last obs 2026-07: fresh
    result = apply_intake_frames(cat, REQ, frames=frames, vintage="v1", asof=ASOF, created_at=NOW)
    assert result.written == [SID]
    assert not result.quarantined
    assert cat.current_vintage() == "v1"
    stored = cat.read_observations("v1", SID)
    assert len(stored) == 3


def test_stale_frames_quarantine_and_hold_the_pointer(cat: Catalog) -> None:
    frames = {SID: _monthly([0.01, 0.02], "2020-01-01")}  # years stale vs 75d SLA
    result = apply_intake_frames(cat, REQ, frames=frames, vintage="v1", asof=ASOF, created_at=NOW)
    assert result.quarantined
    assert cat.current_vintage() is None  # never advanced


def test_idempotent_per_vintage(cat: Catalog) -> None:
    frames = {SID: _monthly([0.01], "2026-07-01")}
    apply_intake_frames(cat, REQ, frames=frames, vintage="v1", asof=ASOF, created_at=NOW)
    again = apply_intake_frames(cat, REQ, frames=frames, vintage="v1", asof=ASOF, created_at=NOW)
    assert again.already_exists and again.written == []
