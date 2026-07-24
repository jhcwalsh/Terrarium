"""WP1.3 acceptance: manual-intake validation, rejection reports, parquet round-trip."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.intake import (
    IntakeError,
    ingest_file,
    parse_intake_filename,
    to_series_frames,
    validate_file,
)
from ah.data.schemas import SCHEMAS, get_schema
from ah.data.schemas.albourne_derived_cf import CF_A_LIFECYCLE, CF_B_CALENDAR
from ah.data.schemas.albourne_pm_returns import SCHEMA as PM
from ah.data.schemas.cliffwater_cdli import SCHEMA as CDLI

FX = Path(__file__).resolve().parent / "fixtures" / "data" / "intake"
NOW = "2026-07-24T00:00:00"


@pytest.fixture
def cat(tmp_path: Path) -> Iterator[Catalog]:
    c = Catalog(tmp_path / "data")
    yield c
    c.close()


# --------------------------------------------------------------------------- #
# registry + filenames
# --------------------------------------------------------------------------- #


def test_registry_has_all_schema_types() -> None:
    for name in (
        "albourne_pm_returns",
        "albourne_hf_returns",
        "albourne_cf_A_lifecycle",
        "albourne_cf_B_calendar_rates",
        "albourne_cf_C_age_calendar",
        "albourne_cf_D_vintage",
        "albourne_cf_E_episodes",
        "cliffwater_cdli",
        "nareit_returns",
        "ncreif_returns",
    ):
        assert name in SCHEMAS
        assert get_schema(name) is not None


def test_parse_intake_filename() -> None:
    assert parse_intake_filename("pm-returns_2026Q2.csv") == ("pm-returns", "2026Q2")
    with pytest.raises(IntakeError):
        parse_intake_filename("noasof.csv")


# --------------------------------------------------------------------------- #
# clean files accepted + round-trip
# --------------------------------------------------------------------------- #


def test_clean_pm_returns_accepted() -> None:
    r = validate_file(FX / "albourne" / "pm-returns_2026Q2.csv", PM)
    assert r.accepted
    assert r.violations == []
    assert r.frame is not None


def test_clean_lifecycle_and_calendar_accepted() -> None:
    assert validate_file(FX / "albourne" / "cf-lifecycle_2026Q2.csv", CF_A_LIFECYCLE).accepted
    assert validate_file(FX / "albourne" / "cf-calendar_2026Q2.csv", CF_B_CALENDAR).accepted


def test_clean_cdli_accepted() -> None:
    assert validate_file(FX / "cliffwater" / "cdli_2026Q2.csv", CDLI).accepted


def test_to_series_frames_pivots_by_strategy() -> None:
    r = validate_file(FX / "albourne" / "pm-returns_2026Q2.csv", PM)
    assert r.frame is not None
    frames = to_series_frames(PM, r.frame)
    assert set(frames) == {"albourne.buyout", "albourne.dl"}
    assert frames["albourne.buyout"]["value"].tolist() == [0.03, -0.02]


def test_clean_file_round_trips_to_parquet(tmp_path: Path) -> None:
    r = validate_file(FX / "albourne" / "pm-returns_2026Q2.csv", PM)
    assert r.frame is not None
    frame = to_series_frames(PM, r.frame)["albourne.buyout"]
    path = tmp_path / "buyout.parquet"
    frame.to_parquet(path, index=False)
    pd.testing.assert_frame_equal(frame, pd.read_parquet(path))


# --------------------------------------------------------------------------- #
# corrupted files rejected with a useful report
# --------------------------------------------------------------------------- #


def test_duplicate_period_rejected() -> None:
    r = validate_file(FX / "albourne" / "pm-returns-dup_2026Q2.csv", PM)
    assert not r.accepted
    assert any(v.kind == "duplicate_period" for v in r.violations)
    assert "REJECTED" in r.report


def test_out_of_bounds_rejected() -> None:
    r = validate_file(FX / "albourne" / "pm-returns-oob_2026Q2.csv", PM)
    assert not r.accepted
    assert any(v.kind == "out_of_bounds" for v in r.violations)


def test_missing_column_rejected() -> None:
    r = validate_file(FX / "albourne" / "pm-returns-missing_2026Q2.csv", PM)
    assert not r.accepted
    assert any(v.kind == "missing_column" and v.column == "ret" for v in r.violations)


def test_silent_gap_rejected() -> None:
    r = validate_file(FX / "albourne" / "cf-calendar-gap_2026Q2.csv", CF_B_CALENDAR)
    assert not r.accepted
    assert any(v.kind == "gap" for v in r.violations)


# --------------------------------------------------------------------------- #
# ingest records provenance
# --------------------------------------------------------------------------- #


def test_ingest_records_intake_log(cat: Catalog) -> None:
    accepted = ingest_file(cat, FX / "albourne" / "pm-returns_2026Q2.csv", PM, received_at=NOW)
    rejected = ingest_file(cat, FX / "albourne" / "pm-returns-oob_2026Q2.csv", PM, received_at=NOW)
    assert accepted.accepted and not rejected.accepted

    rows = cat.con.execute("SELECT status, sha256 FROM intake_log ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["accepted", "rejected"]
    assert all(len(r[1]) == 64 for r in rows)  # sha256 recorded
