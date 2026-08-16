"""Event detection: the point/state distinction, and anchors on every event.

The load-bearing test here is ``test_a_twelve_month_drawdown_fires_once_per_
milestone``. The spike hit exactly this defect — state conditions firing every
period they hold — and it produced 72 severity-3 events per decade against a
target of 4-10. It was invisible in prose and obvious on the first calibration
run, which is why it is pinned here rather than described.

Synthetic worlds throughout; no catalog, no checkpoint.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.narration.adapters.world import WorldSeries
from ah.narration.constants import MONTHS_PER_YEAR
from ah.narration.events import AnchorParams, ConsensusParams, EventParams, detect

MONTHS = 120


def _params(**overrides: object) -> EventParams:
    """Resolved event parameters. Values are the test's, never the layer's."""
    base = {
        "cuts": (1.0, 2.0, 3.0),
        "class_scale": dict.fromkeys(
            ["E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10", "E11"], 1.0
        ),
        "hard_overrides": {"E16": 3, "E18": 3},
        "z_window_months": 24,
        "thresholds": {
            "E01": 0.18,
            "E02": 0.30,
            "E03": 0.20,
            "E04": 0.50,
            "E05": 1.5,
            "E06": 25.0,
            "E07": 0.0,
            "E08": [400, 600, 800],
            "E09": [15, 25],
            "E11": 0.20,
        },
        "milestones": (0.10, 0.20, 0.30),
        "meeting_months": (1, 3, 5, 6, 8, 9, 11, 12),
        "anchor": AnchorParams(
            rho=0.85, quantise_bp=25.0, phi_pi=0.55, phi_c=0.80, cycle_source="credit_gap"
        ),
        "consensus": ConsensusParams(
            persistence_weight=0.5, bias=0.0, dispersion=0.4, n_forecasters=41
        ),
        "book_available": False,
    }
    base.update(overrides)
    return EventParams(**base)  # pyright: ignore[reportArgumentType]


def _world(**overrides: np.ndarray) -> WorldSeries:
    """A calm world: nothing fires unless a test makes it fire."""
    flat = np.zeros(MONTHS)
    series = {
        "policy_rate": np.full(MONTHS, 5.0),
        "cpi_yoy": np.full(MONTHS, 3.0),
        "equity_index": np.full(MONTHS, 100.0),
        "equity_return": flat.copy(),
        "hy_oas": np.full(MONTHS, 350.0),
        "curve_2s10s": np.full(MONTHS, 50.0),
        "ust_10y": np.full(MONTHS, 6.0),
        "equity_vol": np.full(MONTHS, 18.0),
        "unemployment": np.full(MONTHS, 5.0),
        "payrolls_change": np.full(MONTHS, 150.0),
        "headline_cpi": np.full(MONTHS, 3.0),
        "growth_print": np.full(MONTHS, 2.5),
    }
    series.update(overrides)
    l1 = {
        "pi_star": np.full(MONTHS, 3.0),
        "r_star": np.full(MONTHS, 1.0),
        "g": np.full(MONTHS, 2.5),
        "v": np.full(MONTHS, 0.8),
        "credit_gap": np.full(MONTHS, 0.0),
    }
    return WorldSeries(
        months=MONTHS,
        series=series,
        regime=tuple(["EXP"] * MONTHS),
        l1_state=l1,
        optional={},
        absent_optional=("cash_pct",),
        derived_register=(),
        mapping_notes=(),
        warmup_months=0,
        extras=("equity_vol",),
    )


def _drawdown_world() -> WorldSeries:
    """A twelve-month drawdown to -35%, then a partial recovery.

    Straight-line down so the milestone months are arithmetic rather than
    guessed: it crosses -10%, -20% and -30% exactly once each.
    """
    index = np.full(MONTHS, 100.0)
    depth = np.linspace(0.0, 0.35, 13)[1:]
    index[24:36] = 100.0 * (1.0 - depth)
    index[36:] = 100.0 * (1.0 - 0.35)
    returns = np.zeros(MONTHS)
    returns[1:] = index[1:] / index[:-1] - 1.0
    return _world(equity_index=index, equity_return=returns)


def test_a_twelve_month_drawdown_fires_once_per_milestone():
    """One event per milestone crossed. Not one per period it holds."""
    events = detect(_drawdown_world(), _params())
    e10 = [e for e in events if e.cls == "E10"]
    assert len(e10) == 3, [(e.month, e.trigger_values) for e in e10]
    assert [e.trigger_values["milestone"] for e in e10] == [0.10, 0.20, 0.30]
    assert len({e.month for e in e10}) == 3


def test_a_drawdown_episode_is_one_episode_with_running_months():
    events = detect(_drawdown_world(), _params())
    e10 = [e for e in events if e.cls == "E10"]
    assert len({e.episode_id for e in e10}) == 1
    assert all(e.episode_id is not None for e in e10)
    assert [e.episode_month for e in e10] == sorted(e.episode_month for e in e10)


def test_a_new_high_closes_the_episode_and_the_next_drawdown_is_a_new_one():
    index = np.full(MONTHS, 100.0)
    index[10:20] = 85.0
    index[20:40] = 120.0
    index[40:60] = 100.0
    returns = np.zeros(MONTHS)
    returns[1:] = index[1:] / index[:-1] - 1.0
    events = detect(_world(equity_index=index, equity_return=returns), _params())
    e10 = [e for e in events if e.cls == "E10"]
    assert len(e10) == 2
    assert len({e.episode_id for e in e10}) == 2


def _jitter(base: np.ndarray) -> np.ndarray:
    """A trace of noise, so the trailing window has a standard deviation.

    Severity is z-scored against trailing history; a perfectly constant series
    has no scale to score against and nothing fires (pinned by
    ``test_a_constant_series_produces_no_z_scored_events``). Real generated
    paths are never constant, but synthetic ones are unless told otherwise.
    """
    rng = np.random.Generator(np.random.PCG64(11))
    return base + rng.normal(0.0, 0.05, base.shape)


def test_a_sustained_inversion_is_one_episode_not_sixty_events():
    curve = np.full(MONTHS, 50.0)
    curve[30:90] = -40.0
    events = detect(_world(curve_2s10s=_jitter(curve)), _params())
    e07 = [e for e in events if e.cls == "E07"]
    assert len(e07) == 2, [(e.month, e.trigger_values) for e in e07]
    assert {e.trigger_values["direction"] for e in e07} == {"inversion", "re-steepening"}


def test_a_sustained_vol_state_is_one_episode_per_transition():
    vol = np.full(MONTHS, 18.0)
    vol[40:80] = 32.0
    events = detect(_world(equity_vol=_jitter(vol)), _params())
    e09 = [e for e in events if e.cls == "E09"]
    assert len(e09) == 2
    assert [e.trigger_values["state"] for e in e09] == ["elevated", "ordinary"]


def test_a_constant_series_produces_no_z_scored_events():
    """Documented, not accidental: a series with no variation has no scale to
    score a move against, so the z-scored classes stay silent. Synthetic worlds
    hit this; generated ones do not."""
    vol = np.full(MONTHS, 18.0)
    vol[40:80] = 32.0
    events = detect(_world(equity_vol=vol), _params())
    assert not [e for e in events if e.cls == "E09"]


def test_every_event_carries_a_non_null_panel_and_delta():
    """DN-9 §B.2: an announcement with no anchor is a defect, not a warning."""
    events = detect(_drawdown_world(), _params())
    assert events
    for event in events:
        assert event.panel, event
        assert event.delta is not None, event
        assert event.delta["label"], event


def test_policy_events_fire_only_on_meeting_months():
    events = detect(_world(), _params())
    e01 = [e for e in events if e.cls == "E01"]
    months_in_year = {(e.month - 1) % MONTHS_PER_YEAR + 1 for e in e01}
    assert months_in_year <= {1, 3, 5, 6, 8, 9, 11, 12}
    assert len(e01) == 8 * (MONTHS // MONTHS_PER_YEAR)


def test_a_hard_override_beats_the_cut_points():
    params = _params(hard_overrides={"E10": 3})
    events = detect(_drawdown_world(), params)
    assert all(e.severity == 3 for e in events if e.cls == "E10")


def test_detection_is_deterministic():
    world = _drawdown_world()
    first = detect(world, _params())
    second = detect(world, _params())
    assert [e.as_record() for e in first] == [e.as_record() for e in second]


def test_events_are_emitted_in_a_stable_documented_order():
    events = detect(_drawdown_world(), _params())
    keys = [(e.month, e.cls) for e in events]
    assert keys == sorted(keys)


def test_book_classes_never_fire_without_the_book():
    events = detect(_drawdown_world(), _params())
    assert not [e for e in events if e.cls in {"E12", "E15", "E16", "E17", "E18", "E19"}]


def test_an_unknown_cycle_source_is_refused_rather_than_defaulted():
    params = _params(
        anchor=AnchorParams(
            rho=0.85, quantise_bp=25.0, phi_pi=0.55, phi_c=0.80, cycle_source="vibes"
        )
    )
    with pytest.raises(Exception, match="vibes"):
        detect(_world(), params)
