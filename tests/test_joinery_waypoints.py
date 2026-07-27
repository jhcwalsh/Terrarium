"""WP2.7 waypoints: structural annual waypoints + WorldSpec factor_conditions binding."""

from __future__ import annotations

import numpy as np
import pytest

from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.worldspec import (
    Credit,
    CrisisWindow,
    Equity,
    FactorConditions,
    Inflation,
    PolicyRate,
)
from ah.gen.climate import simulate as cs
from ah.gen.joinery import waypoints as wp
from joinery_common import (
    CODE,
    EQUITY_BY_REGIME,
    SPREAD_BY_REGIME,
    make_climate_artifact,
    make_regime_paths,
    make_source,
    theta_base,
)

MONTHS = 120
N_YEARS = 10


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(tmp_path_factory.mktemp("climate"))


@pytest.fixture(scope="module")
def source():
    return make_source()


@pytest.fixture(scope="module")
def stats(source, climate):
    return wp.source_stats(source, climate)


def _sim(climate, n_decades=2, months=MONTHS, seed=11, **kw):
    return cs.simulate_decades(climate, n_decades, seed=seed, months=months, **kw)


def _flat_regimes(n_decades=2, months=MONTHS, label="EXP"):
    labels = np.full((n_decades, months), CODE[label], dtype=np.int64)
    return make_regime_paths(labels)


# --------------------------------------------------------------------------- #
# source_stats
# --------------------------------------------------------------------------- #


class TestSourceStats:
    def test_equity_mean_log_by_regime_recovers_construction(self, stats):
        # make_source: equity = EQUITY_BY_REGIME[label] + 0.001*sin(t); the sin term
        # averages out to ~0 within each stratum, so the regime means sit near the
        # constructed values.
        for label, value in EQUITY_BY_REGIME.items():
            got = stats.equity_mean_log_by_regime[CODE[label]]
            assert got == pytest.approx(np.log1p(value), abs=2e-3)

    def test_spread_mean_by_regime_recovers_construction(self, stats):
        for label, value in SPREAD_BY_REGIME.items():
            got = stats.spread_mean_by_regime[CODE[label]]
            assert got == pytest.approx(value, abs=0.05)

    def test_absent_regime_falls_back_to_overall_mean_and_is_recorded(self, climate):
        source = make_source(labels=tuple("EXP" for _ in range(240)))
        stats = wp.source_stats(source, climate)
        assert set(stats.absent_regimes) == set(wp.REGIME_LABELS) - {"EXP"}
        for label in stats.absent_regimes:
            assert stats.equity_mean_log_by_regime[CODE[label]] == pytest.approx(
                stats.equity_mean_log_overall
            )

    def test_spread_beta_recovers_a_planted_credit_gap_loading(self, tmp_path):
        # Plant credit_gap = sin(t/9) in the climate states and add 0.3*credit_gap to
        # the spread column: the regression must recover beta ~ 0.3.
        from joinery_common import make_planted_beta_pair

        climate2, source2 = make_planted_beta_pair(tmp_path, beta=0.3)
        stats = wp.source_stats(source2, climate2)
        assert stats.spread_beta_credit_gap == pytest.approx(0.3, abs=0.05)

    def test_missing_waypoint_factor_raises(self, climate):
        import ah.gen.bootstrap as bs

        src = make_source()
        names = tuple(n for n in src.factor_names if n != "policy_rate")
        keep = [i for i, n in enumerate(src.factor_names) if n != "policy_rate"]
        src2 = bs.BootstrapSource(
            factor_names=names,
            dates=src.dates,
            values=src.values[:, keep],
            labels=src.labels,
            ruleset_version=src.ruleset_version,
            vintage_id=src.vintage_id,
            active_blocks=src.active_blocks,
        )
        with pytest.raises(wp.JoineryError, match="policy_rate"):
            wp.source_stats(src2, climate)


# --------------------------------------------------------------------------- #
# structural waypoints (no world)
# --------------------------------------------------------------------------- #


class TestStructuralWaypoints:
    def test_policy_waypoint_is_the_annual_anchor_mean(self, climate, stats):
        sim = _sim(climate, theta_index=0)
        regimes = _flat_regimes()
        wps = wp.build_waypoints(sim, regimes, stats)
        anchor = cs.policy_anchor(sim, cycle=regimes.cycle)
        for k, one in enumerate(wps):
            for y, span in enumerate(wp.year_spans(MONTHS)):
                assert one.policy_pct[y] == pytest.approx(
                    max(float(anchor[k, span].mean()), wp.RATE_FLOOR_PCT)
                )

    def test_inflation_waypoint_is_the_annual_pi_star_mean(self, climate, stats):
        sim = _sim(climate)
        regimes = _flat_regimes()
        wps = wp.build_waypoints(sim, regimes, stats)
        pi = sim.state("pi_star")
        for k, one in enumerate(wps):
            for y, span in enumerate(wp.year_spans(MONTHS)):
                assert one.inflation_pct[y] == pytest.approx(float(pi[k, span].mean()))

    def test_equity_drift_formula_on_constant_states(self, climate, stats):
        # Constant states, theta pinned: annual drift = (a - b*v + pi*)/100 plus the
        # regime texture term (which is a constant offset under a flat regime path).
        sim = _sim(climate, theta_index=0)
        regimes = _flat_regimes(label="EXP")
        wps = wp.build_waypoints(sim, regimes, stats)
        theta = theta_base()
        pi = sim.state("pi_star")
        v = sim.state("v")
        mu_exp = stats.equity_mean_log_by_regime[CODE["EXP"]]
        for k, one in enumerate(wps):
            for y, span in enumerate(wp.year_spans(MONTHS)):
                base = (theta["a_val"] - theta["b_val"] * float(v[k, span].mean())) / 100.0 + float(
                    pi[k, span].mean()
                ) / 100.0
                texture = (mu_exp - stats.equity_mean_log_overall) * (span.stop - span.start)
                assert one.equity_log_drift[y] == pytest.approx(base + texture, rel=1e-9)

    def test_spread_band_center_and_width(self, climate, stats):
        sim = _sim(climate, theta_index=0)
        regimes = _flat_regimes(label="REC")
        wps = wp.build_waypoints(sim, regimes, stats)
        gap = sim.state("credit_gap")
        for k, one in enumerate(wps):
            for y, span in enumerate(wp.year_spans(MONTHS)):
                yend = span.stop - 1
                center = stats.spread_mean_by_regime[CODE["REC"]] + (
                    stats.spread_beta_credit_gap * float(gap[k, yend])
                )
                center = max(center, wp.SPREAD_FLOOR_PCT)
                assert one.spread_center_pct[y] == pytest.approx(center, rel=1e-9)
                assert one.spread_lo_pct[y] <= one.spread_center_pct[y] <= one.spread_hi_pct[y]
                assert one.spread_lo_pct[y] >= wp.SPREAD_FLOOR_PCT

    def test_deterministic(self, climate, stats):
        sim = _sim(climate)
        regimes = _flat_regimes()
        a = wp.build_waypoints(sim, regimes, stats)
        b = wp.build_waypoints(sim, regimes, stats)
        for one, two in zip(a, b, strict=True):
            np.testing.assert_array_equal(one.policy_pct, two.policy_pct)
            np.testing.assert_array_equal(one.equity_log_drift, two.equity_log_drift)
            np.testing.assert_array_equal(one.labels, two.labels)

    def test_floors_bind_when_anchor_dives(self, tmp_path, stats):
        # r* = -6, pi* = 0 makes the anchor sit at about -6: the policy waypoint must
        # be floored at the platform rate floor (-1).
        climate = make_climate_artifact(tmp_path, r_star=-6.0, pi_star=0.0)
        sim = _sim(climate, theta_index=0)
        regimes = _flat_regimes()
        wps = wp.build_waypoints(sim, regimes, stats)
        assert np.all(wps[0].policy_pct >= wp.RATE_FLOOR_PCT - 1e-12)
        assert np.any(wps[0].policy_pct == wp.RATE_FLOOR_PCT)


# --------------------------------------------------------------------------- #
# WorldSpec factor_conditions binding
# --------------------------------------------------------------------------- #


def _bind(climate, stats, fc: FactorConditions, *, regimes=None):
    sim = _sim(climate, n_decades=1, theta_index=0)
    regimes = _flat_regimes(n_decades=1) if regimes is None else regimes
    return wp.build_waypoints(sim, regimes, stats, conditions=fc)[0]


class TestWorldBinding:
    def test_policy_linear_start_end(self, climate, stats):
        fc = FactorConditions(policy_rate=PolicyRate(start_pct=5.0, end_pct=2.0))
        one = _bind(climate, stats, fc)
        tau = (np.arange(N_YEARS) + 0.5) / N_YEARS
        np.testing.assert_allclose(one.policy_pct, 5.0 + (2.0 - 5.0) * tau, rtol=1e-12)

    def test_policy_shapes_order(self, climate, stats):
        def mk(shape):
            return _bind(
                climate,
                stats,
                FactorConditions(
                    policy_rate=PolicyRate(start_pct=1.0, end_pct=5.0, path_shape=shape)
                ),
            ).policy_pct

        linear, front, back = mk("linear"), mk("front_loaded"), mk("back_loaded")
        mid = N_YEARS // 2
        assert front[mid] > linear[mid] > back[mid]
        for arr in (front, back):
            assert arr[0] == pytest.approx(linear[0], abs=0.5)
            assert arr[-1] == pytest.approx(linear[-1], abs=0.5)

    def test_policy_spike_and_settle_peaks_early_then_settles(self, climate, stats):
        one = _bind(
            climate,
            stats,
            FactorConditions(
                policy_rate=PolicyRate(start_pct=2.0, end_pct=3.0, path_shape="spike_and_settle")
            ),
        )
        p = one.policy_pct
        assert p.max() > max(2.0, 3.0)  # a genuine spike above both endpoints
        assert int(np.argmax(p)) <= N_YEARS // 2  # early
        assert p[-1] == pytest.approx(3.0, abs=0.5)  # settles to the endpoint

    def test_inflation_average_tilt(self, climate, stats):
        fc = FactorConditions(inflation=Inflation(average_pct=7.0))
        one = _bind(climate, stats, fc)
        assert float(one.inflation_pct.mean()) == pytest.approx(7.0)

    def test_inflation_peak_placed_and_average_preserved(self, climate, stats):
        fc = FactorConditions(inflation=Inflation(average_pct=5.0, peak_pct=12.0, peak_quarter=16))
        one = _bind(climate, stats, fc)
        y_peak = 16 // 4
        assert int(np.argmax(one.inflation_pct)) == y_peak
        assert float(one.inflation_pct[y_peak]) == pytest.approx(12.0)
        assert float(one.inflation_pct.mean()) == pytest.approx(5.0)

    def test_equity_drift_override_pins_the_decade_total(self, climate, stats):
        fc = FactorConditions(equity=Equity(drift_annual_pct=-4.0))
        one = _bind(climate, stats, fc)
        assert float(one.equity_log_drift.sum()) == pytest.approx(
            N_YEARS * np.log1p(-0.04), rel=1e-9
        )

    def test_equity_vol_and_correlation_pass_through_to_the_record(self, climate, stats):
        from ah.core.worldspec import Correlation

        fc = FactorConditions(
            equity=Equity(vol_annual_pct=30.0),
            correlation=Correlation(equity_bond_regime="positive", crisis_correlation_boost=0.2),
        )
        one = _bind(climate, stats, fc)
        assert one.record["equity_vol_target_annual_pct"] == 30.0
        assert one.record["correlation"]["equity_bond_regime"] == "positive"
        assert one.record["correlation"]["crisis_correlation_boost"] == 0.2

    def test_credit_and_commodities_overrides_recorded_unbound(self, climate, stats):
        from ah.core.worldspec import Commodities

        fc = FactorConditions(
            credit=Credit(hy_spread_start_bps=400, hy_spread_peak_bps=900, peak_quarter=8),
            commodities=Commodities(drift_annual_pct=10.0),
        )
        one = _bind(climate, stats, fc)
        assert one.record["credit_override"]["bound"] is False
        assert one.record["commodities_override"]["bound"] is False
        # The structural spread band is untouched by the unbindable hy override.
        base = _bind(climate, stats, FactorConditions())
        np.testing.assert_allclose(one.spread_center_pct, base.spread_center_pct)

    def test_crisis_window_overlays_cri_and_moves_the_spread_band(self, climate, stats):
        fc = FactorConditions(
            crisis_windows=[CrisisWindow(start_quarter=8, length_quarters=4, severity=0.7)]
        )
        one = _bind(climate, stats, fc)
        base = _bind(climate, stats, FactorConditions())
        # months 24..35 forced to CRI
        assert set(one.labels[24:36].tolist()) == {CODE["CRI"]}
        assert set(one.labels[:24].tolist()) == {CODE["EXP"]}
        # year 2's year-end (month 35) is inside the window: spread center jumps to the
        # CRI regime mean
        assert one.spread_center_pct[2] > base.spread_center_pct[2]
        assert one.record["crisis_windows"][0]["severity"] == 0.7
        # and the cycle used for the anchor flips to the CRI value (-1)
        assert one.policy_pct[2] != pytest.approx(base.policy_pct[2])

    def test_fixture_world_binds_through_project_numeric(self, climate, stats):
        from pathlib import Path

        fixture = (
            Path(__file__).resolve().parents[1]
            / "fixtures/worlds/conditional/rate_endpoints_mild.worldspec.json"
        )
        world = project_numeric(load_worldspec(fixture))
        sim = _sim(climate, n_decades=1, theta_index=0)
        regimes = _flat_regimes(n_decades=1)
        one = wp.build_waypoints(sim, regimes, stats, conditions=world.factor_conditions)[0]
        tau = (np.arange(N_YEARS) + 0.5) / N_YEARS
        np.testing.assert_allclose(one.policy_pct, 5.0 + (2.0 - 5.0) * tau, rtol=1e-12)


# --------------------------------------------------------------------------- #
# monthly targets
# --------------------------------------------------------------------------- #


class TestMonthlyTargets:
    def test_shapes_and_anchor_hits(self, climate, stats):
        sim = _sim(climate, n_decades=1, theta_index=0)
        regimes = _flat_regimes(n_decades=1)
        one = wp.build_waypoints(sim, regimes, stats)[0]
        targets = wp.monthly_targets(one, MONTHS)
        for arr in (
            targets.policy_pct,
            targets.log_cpi,
            targets.equity_cum_log,
            targets.spread_center_pct,
        ):
            assert arr.shape == (MONTHS,)
        # year-end log cpi equals the cumulative annual inflation target
        spans = wp.year_spans(MONTHS)
        cum = 0.0
        for y, span in enumerate(spans):
            n_m = span.stop - span.start
            cum += (n_m - (1 if y == 0 else 0)) / 12.0 * one.inflation_pct[y] / 100.0
            assert targets.log_cpi[span.stop - 1] == pytest.approx(cum, rel=1e-9)
        # year-end cumulative equity log drift equals the cumsum of annual drifts
        np.testing.assert_allclose(
            [targets.equity_cum_log[s.stop - 1] for s in spans],
            np.cumsum(one.equity_log_drift),
            rtol=1e-9,
        )
