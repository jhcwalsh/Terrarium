"""Generator console: the four-stage decade build and the runs monitor."""

from __future__ import annotations

import json

import pytest

from ah import genconsole as gc


@pytest.fixture(scope="module")
def events() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    gc.build_decade(3, 0, on_stage=lambda name, payload: out.append((name, payload)))
    return out


def test_stages_arrive_in_order_with_real_shapes(events):
    assert [e[0] for e in events] == ["climate", "seasons", "weather", "joinery"]
    climate = events[0][1]
    assert len(climate["months"]) == 120 and climate["states"], "L1 slow states missing"
    seasons = events[1][1]
    assert len(seasons["labels"]) == 120 and seasons["durations"]
    weather = events[2][1]
    assert weather["block_months"] >= 1 and weather["factors"]
    assert all(len(v) == 120 for v in weather["factors"].values())
    joinery = events[3][1]
    assert "reconciliation" in joinery and "filter_stats" in joinery


def test_same_seed_is_bit_identical():
    def run(seed: int) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        gc.build_decade(seed, 0, on_stage=lambda name, payload: out.append((name, payload)))
        return out

    a, b = run(7), run(7)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
        b, sort_keys=True, default=str
    )
