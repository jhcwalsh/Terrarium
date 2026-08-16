"""The input adapter: generator output -> the DN-9 §1 input contract.

Every ensemble here is built in-test. The workbench's real world needs a
gitignored campaign-2 checkpoint and a licensed catalog; a committed test that
needed either would be a test that only runs on one machine.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.base import AbsentLayer, Ensemble, EnsembleMeta, RegimeRecord, SlowStateRecord
from ah.narration.adapters.world import build_world_series
from ah.narration.constants import L1_STATE_NAMES, OPTIONAL_SERIES
from ah.narration.errors import MissingSeriesError

FACTORS = ["cpi", "equity_mkt", "equity_vol", "hy_spread", "policy_rate", "ust_10y", "ust_2y"]
MONTHS = 120
LEGEND = ("EXP", "SLOW", "REC", "CRI", "STAG", "REF")


def _ensemble(*, factors: list[str] | None = None, slow_states: object | None = None) -> Ensemble:
    """A synthetic ensemble shaped exactly like hier-flow-v1's, values arbitrary."""
    names = FACTORS if factors is None else factors
    rng = np.random.Generator(np.random.PCG64(4417))
    paths = np.zeros((1, MONTHS, len(names)), dtype=np.float64)
    for index, name in enumerate(names):
        if name == "cpi":
            paths[0, :, index] = np.cumprod(1.0 + rng.normal(0.005, 0.002, MONTHS))
        elif name == "equity_mkt":
            paths[0, :, index] = rng.normal(0.004, 0.04, MONTHS)
        elif name == "equity_vol":
            paths[0, :, index] = 18.0 + rng.normal(0.0, 3.0, MONTHS)
        elif name == "hy_spread":
            paths[0, :, index] = 4.0 + np.abs(rng.normal(0.0, 0.5, MONTHS))
        elif name == "policy_rate":
            paths[0, :, index] = 5.0 + np.cumsum(rng.normal(0.0, 0.1, MONTHS))
        elif name == "ust_10y":
            paths[0, :, index] = 6.5 + np.cumsum(rng.normal(0.0, 0.1, MONTHS))
        else:
            paths[0, :, index] = 5.5 + np.cumsum(rng.normal(0.0, 0.12, MONTHS))
    states = np.zeros((1, MONTHS, len(L1_STATE_NAMES)), dtype=np.float64)
    states[0, :, 0] = 4.0 + rng.normal(0.0, 0.2, MONTHS)
    states[0, :, 1] = 1.0 + rng.normal(0.0, 0.2, MONTHS)
    states[0, :, 2] = 2.5 + rng.normal(0.0, 0.3, MONTHS)
    states[0, :, 3] = 0.8 + rng.normal(0.0, 0.1, MONTHS)
    states[0, :, 4] = 4.0 + rng.normal(0.0, 0.5, MONTHS)
    slow = (
        SlowStateRecord(states=states, names=L1_STATE_NAMES, layer="simulated")
        if slow_states is None
        else slow_states
    )
    return Ensemble(
        paths=paths,
        factor_names=list(names),
        meta=EnsembleMeta(
            generator_id="test-gen",
            vintage_id="test-vintage",
            seed=4417,
            n_paths=1,
            months=MONTHS,
        ),
        regimes=RegimeRecord(
            labels=np.full((1, MONTHS), 4, dtype=np.int64),
            legend=LEGEND,
            mode="sequence",
            ruleset_version="test",
        ),
        slow_states=slow,  # pyright: ignore[reportArgumentType]
    )


def _params() -> dict[str, object]:
    """Resolved adapter parameters, supplied by the test rather than by the layer."""
    return {
        "cpi_yoy_warmup": "nan_suppress",
        "headline_cpi": {"yoy_window_months": 12},
        "unemployment": {"u_star": 5.0, "g_star": 2.5, "beta": 0.5},
        "payrolls_change": {"labour_force_millions": 165.0, "trend_thousands": 150.0},
        "growth_print": {"transform": "identity"},
    }


def test_required_series_are_all_present_and_120_months():
    world = build_world_series(_ensemble(), path_index=0, params=_params())
    for name in ("policy_rate", "cpi_yoy", "equity_index", "hy_oas", "curve_2s10s", "ust_10y"):
        assert world.series[name].shape == (MONTHS,)
    assert len(world.regime) == MONTHS
    assert set(world.l1_state) == set(L1_STATE_NAMES)


def test_units_are_converted_not_assumed():
    """hy_spread and the curve arrive in percent; the paper prints basis points."""
    ensemble = _ensemble()
    world = build_world_series(ensemble, path_index=0, params=_params())
    hy_pct = ensemble.factor("hy_spread")[0]
    np.testing.assert_allclose(world.series["hy_oas"], hy_pct * 100.0)
    curve_pct = ensemble.factor("ust_10y")[0] - ensemble.factor("ust_2y")[0]
    np.testing.assert_allclose(world.series["curve_2s10s"], curve_pct * 100.0)


def test_equity_index_is_cumulated_from_returns():
    ensemble = _ensemble()
    world = build_world_series(ensemble, path_index=0, params=_params())
    returns = ensemble.factor("equity_mkt")[0]
    index = world.series["equity_index"]
    np.testing.assert_allclose(index[1:] / index[:-1] - 1.0, returns[1:], atol=1e-12)


def test_cpi_yoy_warmup_is_suppressed_not_invented():
    """A 12-month transform has no value for 12 months. The adapter says so."""
    world = build_world_series(_ensemble(), path_index=0, params=_params())
    yoy = world.series["cpi_yoy"]
    assert np.all(np.isnan(yoy[:12]))
    assert np.all(np.isfinite(yoy[12:]))
    assert world.warmup_months == 12


def test_a_missing_required_series_fails_naming_it():
    without_2y = [f for f in FACTORS if f != "ust_2y"]
    with pytest.raises(MissingSeriesError) as excinfo:
        build_world_series(_ensemble(factors=without_2y), path_index=0, params=_params())
    assert excinfo.value.series == "curve_2s10s"
    assert "ust_2y" in str(excinfo.value)


def test_a_missing_l1_state_fails_naming_it():
    absent = AbsentLayer(reason="this generator has no climate layer")
    with pytest.raises(MissingSeriesError) as excinfo:
        build_world_series(_ensemble(slow_states=absent), path_index=0, params=_params())
    assert excinfo.value.series == "l1_state"
    assert "no climate layer" in str(excinfo.value)


def test_the_book_series_are_absent_and_the_absence_is_recorded():
    """Never stubbed. The omission is a fact the artifact has to state."""
    world = build_world_series(_ensemble(), path_index=0, params=_params())
    assert world.absent_optional == OPTIONAL_SERIES
    assert world.optional == {}
    assert not world.book_available


def test_every_derived_observable_is_registered_with_its_transform():
    """DN-9 §3.4: registered — name, source factor, transform, and the fact that
    it is derived — or it is not a rendering, it is a second generator."""
    world = build_world_series(_ensemble(), path_index=0, params=_params())
    register = {entry["name"]: entry for entry in world.derived_register}
    assert set(register) == {"unemployment", "payrolls_change", "headline_cpi", "growth_print"}
    for entry in register.values():
        assert entry["derived"] is True
        assert entry["source"] and entry["transform"] and entry["params"]
    assert register["unemployment"]["source"] == "g"


def test_derived_observables_are_deterministic_functions_of_revealed_state():
    """Same inputs, same outputs — twice, with no hidden state between calls."""
    first = build_world_series(_ensemble(), path_index=0, params=_params())
    second = build_world_series(_ensemble(), path_index=0, params=_params())
    for name, values in first.series.items():
        np.testing.assert_array_equal(values, second.series[name], err_msg=name)


def test_the_okun_map_moves_unemployment_against_growth():
    """The only claim made about the map: it is decreasing in growth. The
    coefficients are UNRESOLVED and the test must not pin them."""
    ensemble = _ensemble()
    params = _params()
    world = build_world_series(ensemble, path_index=0, params=params)
    growth = world.l1_state["g"]
    unemployment = world.series["unemployment"]
    order = np.argsort(growth)
    assert unemployment[order][0] > unemployment[order][-1]
