"""WP2.7 reconcile: Denton benchmarking to annual waypoints, floors, diagnostics."""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.climate import simulate as cs
from ah.gen.joinery import bridge
from ah.gen.joinery import reconcile as rc
from ah.gen.joinery import waypoints as wp
from joinery_common import CODE, make_climate_artifact, make_regime_paths, make_source

MONTHS = 120


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(tmp_path_factory.mktemp("climate"))


@pytest.fixture(scope="module")
def source():
    return make_source()


@pytest.fixture(scope="module")
def stats(source, climate):
    return wp.source_stats(source, climate)


def _decade(climate, source, stats, *, months=MONTHS, seed=5, label="EXP"):
    sim = cs.simulate_decades(climate, 1, seed=seed, months=months, theta_index=0)
    regimes = make_regime_paths(np.full((1, months), CODE[label], dtype=np.int64))
    one = wp.build_waypoints(sim, regimes, stats)[0]
    sampler = bridge.BootstrapBlockSampler(source, block_months=6)
    path, _ = bridge.assemble_decade_path(
        months=months,
        waypoints=one,
        targets=wp.monthly_targets(one, months),
        states_row=sim.states[0],
        sampler=sampler,
        stats=stats,
        rng=np.random.Generator(np.random.PCG64(17)),
    )
    return one, path


# --------------------------------------------------------------------------- #
# the Denton core
# --------------------------------------------------------------------------- #


class TestDentonAdditive:
    def test_flow_benchmarks_hit_exactly(self):
        rng = np.random.Generator(np.random.PCG64(0))
        z = rng.normal(0.0, 1.0, 48)
        targets = np.array([3.0, -2.0, 5.0, 0.5])
        spans = wp.year_spans(48)
        x = rc.denton_additive(z, [(s, t, "sum") for s, t in zip(spans, targets, strict=True)])
        for s, t in zip(spans, targets, strict=True):
            assert float(x[s].sum()) == pytest.approx(t, abs=1e-8)

    def test_stock_benchmarks_hit_exactly(self):
        rng = np.random.Generator(np.random.PCG64(1))
        z = 3.0 + rng.normal(0.0, 0.3, 48)
        spans = wp.year_spans(48)
        targets = np.array([2.0, 2.5, 4.0, 3.0])
        x = rc.denton_additive(
            z, [(slice(s.stop - 1, s.stop), t, "last") for s, t in zip(spans, targets, strict=True)]
        )
        for s, t in zip(spans, targets, strict=True):
            assert float(x[s.stop - 1]) == pytest.approx(t, abs=1e-8)

    def test_consistent_benchmarks_are_the_identity(self):
        rng = np.random.Generator(np.random.PCG64(2))
        z = rng.normal(0.0, 1.0, 36)
        spans = wp.year_spans(36)
        constraints = [(s, float(z[s].sum()), "sum") for s in spans]
        x = rc.denton_additive(z, constraints)
        np.testing.assert_allclose(x, z, atol=1e-8)

    def test_adjustment_spreads_smoothly_not_as_a_step(self):
        # A flat series benchmarked to a changed final-year sum: the movement-
        # preservation objective spreads the adjustment as a smooth ramp; the
        # month-to-month change of the adjustment stays small everywhere.
        z = np.zeros(36)
        spans = wp.year_spans(36)
        x = rc.denton_additive(
            z, [(spans[0], 0.0, "sum"), (spans[1], 0.0, "sum"), (spans[2], 12.0, "sum")]
        )
        adj = x - z
        steps = np.abs(np.diff(adj))
        assert steps.max() < 0.35  # a hard step at the year boundary would be ~1.0
        assert adj[0] < adj[-1]  # monotone ramp toward the constrained year


# --------------------------------------------------------------------------- #
# the per-factor variant table
# --------------------------------------------------------------------------- #


class TestVariants:
    def test_variant_table_is_stated(self):
        assert rc.VARIANT_BY_FACTOR == {
            "policy_rate": "additive",
            "cpi": "proportional_via_log",
            "equity_mkt": "additive_log_returns",
            "ig_spread": "additive_band",
        }

    def test_floors_match_the_sealed_eval_constants(self):
        # A test module may import both layers where a generator module may not
        # (the ah.gen.bootstrap layering precedent).
        from ah.eval.metrics import economics as eco

        assert set(wp.RATE_FLOOR_FACTORS) == set(eco.RATE_FLOOR_FACTORS)
        assert wp.RATE_FLOOR_PCT == eco.RATE_FLOOR_PCT
        assert set(wp.SPREAD_FLOOR_FACTORS) == set(eco.SPREAD_FLOOR_FACTORS)
        assert wp.SPREAD_FLOOR_PCT == eco.SPREAD_FLOOR_PCT


# --------------------------------------------------------------------------- #
# reconcile_decade: the acceptance tests
# --------------------------------------------------------------------------- #


class TestReconcileDecade:
    def test_annual_aggregates_hit_waypoints_within_tolerance(self, climate, source, stats):
        one, path = _decade(climate, source, stats)
        cfg = rc.ReconcileConfig()
        adjusted, diag = rc.reconcile_decade(path, source.factor_names, one, cfg)
        names = list(source.factor_names)
        spans = wp.year_spans(MONTHS)

        policy = adjusted[:, names.index("policy_rate")]
        for y, s in enumerate(spans):
            assert float(policy[s].mean()) == pytest.approx(
                one.policy_pct[y], abs=cfg.tol_policy_pct
            )

        cpi = adjusted[:, names.index("cpi")]
        cum = wp.cum_log_cpi_targets(one)
        for y, s in enumerate(spans):
            got = float(np.log(cpi[s.stop - 1]) - np.log(cpi[0]))
            assert got == pytest.approx(cum[y], abs=cfg.tol_cpi_log)

        eq = adjusted[:, names.index("equity_mkt")]
        for y, s in enumerate(spans):
            assert float(np.log1p(eq[s]).sum()) == pytest.approx(
                one.equity_log_drift[y], abs=cfg.tol_equity_log
            )

        spread = adjusted[:, names.index("ig_spread")]
        for y, s in enumerate(spans):
            assert (
                one.spread_lo_pct[y] - cfg.tol_spread_pct
                <= float(spread[s.stop - 1])
                <= one.spread_hi_pct[y] + cfg.tol_spread_pct
            )

        assert diag.tolerance_ok
        # every reconciled factor reports a per-year adjustment magnitude
        for name in rc.VARIANT_BY_FACTOR:
            assert diag.factors[name].adjustment_by_year.shape == (len(spans),)

    def test_unreconciled_factors_pass_through_untouched(self, climate, source, stats):
        one, path = _decade(climate, source, stats)
        adjusted, _ = rc.reconcile_decade(path, source.factor_names, one, rc.ReconcileConfig())
        names = list(source.factor_names)
        for name in names:
            if name not in rc.VARIANT_BY_FACTOR:
                np.testing.assert_array_equal(
                    adjusted[:, names.index(name)], path[:, names.index(name)]
                )

    def test_deliberately_inconsistent_waypoints_flag_large_adjustment(
        self, climate, source, stats
    ):
        # The plan's acceptance test: waypoints far from what the blocks deliver
        # must produce a LARGE, FLAGGED reconciliation — and a consistent pair a
        # small, unflagged one.
        one, path = _decade(climate, source, stats)
        cfg = rc.ReconcileConfig()
        _, diag_ok = rc.reconcile_decade(path, source.factor_names, one, cfg)

        broken = wp.DecadeWaypoints(
            policy_pct=one.policy_pct + 8.0,  # 800bp off every year
            inflation_pct=one.inflation_pct + 10.0,  # +10%/yr price level explosion
            equity_log_drift=one.equity_log_drift - 1.5,  # -150 log-pct per year
            spread_center_pct=one.spread_center_pct + 6.0,
            spread_lo_pct=one.spread_lo_pct + 6.0,
            spread_hi_pct=one.spread_hi_pct + 6.0,
            labels=one.labels,
            cycle=one.cycle,
            record={},
        )
        _, diag_bad = rc.reconcile_decade(path, source.factor_names, broken, cfg)
        for name in rc.VARIANT_BY_FACTOR:
            assert diag_bad.factors[name].flagged, f"{name} should flag"
            assert not diag_ok.factors[name].flagged, f"{name} flagged on consistent input"
            assert (
                diag_bad.factors[name].adjustment_by_year.mean()
                > 2.0 * diag_ok.factors[name].adjustment_by_year.mean()
            )
        assert diag_bad.any_flagged and not diag_ok.any_flagged

    def test_floors_reapplied_after_denton(self, climate, source, stats):
        # Drag the policy waypoints to the floor: Denton output dips below -1
        # nowhere after the floor pass, and the clamp is recorded.
        one, path = _decade(climate, source, stats)
        floored = wp.DecadeWaypoints(
            policy_pct=np.full_like(one.policy_pct, wp.RATE_FLOOR_PCT),
            inflation_pct=one.inflation_pct,
            equity_log_drift=one.equity_log_drift,
            spread_center_pct=np.full_like(one.spread_center_pct, wp.SPREAD_FLOOR_PCT),
            spread_lo_pct=np.full_like(one.spread_lo_pct, wp.SPREAD_FLOOR_PCT),
            spread_hi_pct=np.full_like(one.spread_hi_pct, wp.SPREAD_FLOOR_PCT + 1e-9),
            labels=one.labels,
            cycle=one.cycle,
            record={},
        )
        adjusted, diag = rc.reconcile_decade(
            path, source.factor_names, floored, rc.ReconcileConfig()
        )
        names = list(source.factor_names)
        for name in wp.RATE_FLOOR_FACTORS:
            if name in names:
                assert adjusted[:, names.index(name)].min() >= wp.RATE_FLOOR_PCT
        for name in wp.SPREAD_FLOOR_FACTORS:
            if name in names:
                assert adjusted[:, names.index(name)].min() >= wp.SPREAD_FLOOR_PCT
        assert diag.floor_clamped_cells > 0

    def test_spread_inside_band_is_untouched(self, climate, source, stats):
        one, path = _decade(climate, source, stats)
        names = list(source.factor_names)
        col = names.index("ig_spread")
        wide = wp.DecadeWaypoints(
            policy_pct=one.policy_pct,
            inflation_pct=one.inflation_pct,
            equity_log_drift=one.equity_log_drift,
            spread_center_pct=one.spread_center_pct,
            spread_lo_pct=np.zeros_like(one.spread_lo_pct),
            spread_hi_pct=np.full_like(one.spread_hi_pct, 50.0),
            labels=one.labels,
            cycle=one.cycle,
            record={},
        )
        adjusted, diag = rc.reconcile_decade(path, source.factor_names, wide, rc.ReconcileConfig())
        np.testing.assert_allclose(adjusted[:, col], path[:, col], atol=1e-9)
        assert float(diag.factors["ig_spread"].adjustment_by_year.max()) == pytest.approx(0.0)

    def test_zero_crossing_levels_do_not_blow_up(self, climate, source, stats):
        # policy_rate through zero: the additive variant must stay finite (a
        # proportional Denton divides by the level and cannot cross zero).
        one, path = _decade(climate, source, stats)
        names = list(source.factor_names)
        col = names.index("policy_rate")
        crossing = path.copy()
        crossing[:, col] = np.linspace(-0.5, 0.5, MONTHS)
        adjusted, _ = rc.reconcile_decade(crossing, source.factor_names, one, rc.ReconcileConfig())
        assert np.all(np.isfinite(adjusted))

    def test_deterministic(self, climate, source, stats):
        one, path = _decade(climate, source, stats)
        a, _ = rc.reconcile_decade(path, source.factor_names, one, rc.ReconcileConfig())
        b, _ = rc.reconcile_decade(path, source.factor_names, one, rc.ReconcileConfig())
        np.testing.assert_array_equal(a, b)

    def test_summary_is_json_safe(self, climate, source, stats):
        import json

        one, path = _decade(climate, source, stats)
        _, diag = rc.reconcile_decade(path, source.factor_names, one, rc.ReconcileConfig())
        json.dumps(diag.summary())  # must not raise
