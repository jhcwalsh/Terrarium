"""The PriMaRS -> albourne_pm_returns intake path, offline end to end.

The payload fixtures mirror the live response shape verbatim (probed
2026-08-08: string TWR fractions, Java-toString QUARTER dates, per-index
objects with indexId/asOfDate). No network anywhere; the live fetch is
``# pragma: no cover`` and never imported by these tests beyond the module,
whose import has no side effects.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ah.data.catalog import Catalog
from ah.data.connectors.albourne_primars import (
    PM_INDEX_MAP,
    parse_java_date_quarter,
    payload_to_intake_frame,
)
from ah.data.connectors.base import ConnectorError
from ah.data.intake import ingest_file, to_series_frames
from ah.data.manifest import load_requirements
from ah.data.refresh import apply_intake_frames
from ah.data.schemas import get_schema


def _payload_entry(pid: int, quarters: list[tuple[str, str]]) -> dict:
    return {
        "indexId": pid,
        "published": False,
        "asOfDate": 1785715200000,
        "indexData": [{"QUARTER": q, "TWR": twr} for q, twr in quarters],
    }


def test_parse_java_date_quarter():
    assert parse_java_date_quarter("Fri Mar 31 00:00:00 UTC 2023") == "2023Q1"
    assert parse_java_date_quarter("Sun Dec 31 00:00:00 UTC 2023") == "2023Q4"
    with pytest.raises(ConnectorError):
        parse_java_date_quarter("31/03/2023")


def test_payload_to_intake_frame_maps_every_registered_series():
    payload = [
        _payload_entry(pid, [("Fri Mar 31 00:00:00 UTC 2023", "0.0326")])
        for pid, _, _ in PM_INDEX_MAP.values()
    ]
    frame = payload_to_intake_frame(payload)
    assert list(frame.columns) == ["period", "strategy", "ret"]
    assert sorted(frame["strategy"]) == sorted(PM_INDEX_MAP)
    assert set(frame["period"]) == {"2023Q1"}
    assert frame["ret"].tolist() == pytest.approx([0.0326] * len(PM_INDEX_MAP))


def test_null_twr_is_skipped_as_no_observation():
    """The live feed carries null TWR for pre-inception/unpublished quarters
    (hit on the first real download, 2026-08-08): a null is an absent
    observation, not a malformed row, and must not become NaN in the store."""
    payload = [
        {
            "indexId": 547791,
            "published": False,
            "asOfDate": 0,
            "indexData": [
                {"QUARTER": "Fri Mar 31 00:00:00 UTC 2023", "TWR": None},
                {"QUARTER": "Fri Jun 30 00:00:00 UTC 2023", "TWR": "0.02"},
            ],
        }
    ]
    frame = payload_to_intake_frame(payload)
    assert len(frame) == 1
    assert frame["period"].tolist() == ["2023Q2"]


def test_unknown_index_id_is_an_error_not_a_skip():
    with pytest.raises(ConnectorError, match="unmapped"):
        payload_to_intake_frame(
            [_payload_entry(999999, [("Fri Mar 31 00:00:00 UTC 2023", "0.01")])]
        )


def test_empty_payload_is_an_error():
    with pytest.raises(ConnectorError, match="no observations"):
        payload_to_intake_frame([_payload_entry(547791, [])])


def test_drop_lands_in_the_store_through_the_standard_intake_path(tmp_path):
    """frame -> csv drop -> ingest_file -> apply_intake_frames -> vintage store,
    exactly the pipeline scripts/download_primars.py drives."""
    # Quarters chosen fresh relative to the applied asof (2026-08-08): QC's
    # enforce-level staleness rule (SLA 120d) quarantines an old-tailed drop,
    # which an earlier version of this fixture proved by accident.
    quarters = [
        ("Tue Mar 31 00:00:00 UTC 2026", "0.0326"),
        ("Tue Jun 30 00:00:00 UTC 2026", "-0.0210"),
    ]
    payload = [_payload_entry(pid, quarters) for pid, _, _ in PM_INDEX_MAP.values()]
    frame = payload_to_intake_frame(payload)
    drop = tmp_path / "albourne-pm-returns_2026-08-08.csv"
    frame.to_csv(drop, index=False)

    schema = get_schema("albourne_pm_returns")
    assert schema is not None
    cat = Catalog(tmp_path / "store")
    try:
        result = ingest_file(cat, drop, schema, received_at="2026-08-08T00:00:00Z")
        assert result.accepted, result.report
        assert result.frame is not None
        frames = to_series_frames(schema, result.frame)
        assert set(frames) == {f"albourne.{s}" for s in PM_INDEX_MAP}
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
        stored = cat.read_observations("2026-08-08.1", "albourne.pm_buyout_ret_q")
        assert len(stored) == 2
        assert stored["value"].tolist() == pytest.approx([0.0326, -0.0210])
        assert pd.Timestamp(stored["date"].iloc[0]) == pd.Timestamp("2026-01-01")
    finally:
        cat.close()
