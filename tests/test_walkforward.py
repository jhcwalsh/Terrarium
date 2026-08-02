"""WP5.1 — the harness implements the seal; it never redefines it.

Folds are the AM-2026-08-02-005 pin verbatim and cannot reach the
holdout; policies see trailing data only; stochastic policies are
seed-deterministic; the effect size always rides with the p-value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.eval import walkforward as wf

RNG = np.random.Generator(np.random.PCG64(17))
INDEX = pd.date_range("1990-01-01", "2020-12-01", freq="MS")
RETURNS = pd.DataFrame(
    {
        "equity": RNG.normal(0.006, 0.04, len(INDEX)),
        "bonds": RNG.normal(0.003, 0.015, len(INDEX)),
        "commodities": RNG.normal(0.002, 0.05, len(INDEX)),
        "credit": RNG.normal(0.004, 0.02, len(INDEX)),
    },
    index=INDEX,
)


class TestFolds:
    def test_folds_are_the_amendment_pin_verbatim(self):
        fs = wf.folds()
        assert len(fs) == 10
        assert [f.test_year for f in fs] == list(range(2011, 2021))
        assert all(f.train_start == "1871-01" for f in fs)
        assert all(f.train_end == f.test_start for f in fs)  # expanding, no gap

    def test_the_holdout_is_unreachable(self):
        assert max(f.test_year for f in wf.folds()) == 2020
        assert all(f.test_end <= "2021-01" for f in wf.folds())  # never touches 2021+

    def test_protocol_loads_only_if_the_lock_verifies(self):
        doc = wf.load_protocol()
        assert doc["protocol_version"] == "g5-protocol-1.0"
        assert doc["metrics"]["primary"] == "drawdown_surprise"


class TestPolicies:
    def test_static_policies_sum_to_one_and_name_their_assets(self):
        rng = np.random.Generator(np.random.PCG64(1))
        w = wf.static_60_40(RETURNS, rng=rng)
        assert w.sum() == pytest.approx(1.0)
        assert w[list(RETURNS.columns).index("equity")] == pytest.approx(0.60)
        w = wf.static_endowment_mix(RETURNS, rng=rng)
        assert w.sum() == pytest.approx(1.0)
        with pytest.raises(wf.WalkForwardError, match="needs asset columns"):
            wf.static_60_40(RETURNS.loc[:, ["commodities"]], rng=rng)

    def test_optimizers_are_long_only_fully_invested(self):
        for fn in (wf.history_only_optimization, wf.gaussian_monte_carlo, wf.bootstrap_ensemble):
            w = fn(RETURNS, rng=np.random.Generator(np.random.PCG64(2)))
            assert w.sum() == pytest.approx(1.0)
            assert (w >= 0.0).all()

    def test_stochastic_policies_are_seed_deterministic(self):
        a = wf.gaussian_monte_carlo(RETURNS, rng=np.random.Generator(np.random.PCG64(7)))
        b = wf.gaussian_monte_carlo(RETURNS, rng=np.random.Generator(np.random.PCG64(7)))
        np.testing.assert_array_equal(a, b)
        c = wf.bootstrap_ensemble(RETURNS, rng=np.random.Generator(np.random.PCG64(7)))
        d = wf.bootstrap_ensemble(RETURNS, rng=np.random.Generator(np.random.PCG64(7)))
        np.testing.assert_array_equal(c, d)

    def test_heuristic_holds_inside_the_band(self):
        rng = np.random.Generator(np.random.PCG64(3))
        calm = RETURNS.copy()
        calm.iloc[-12:] = 0.0  # no drift at all -> hold the drifted (= target) weights
        w = wf.fixed_heuristic_rules(calm, rng=rng)
        assert w.sum() == pytest.approx(1.0)


class TestHarness:
    def test_end_to_end_is_deterministic_and_complete(self):
        r1 = wf.run_walkforward(RETURNS, base_seed=42)
        r2 = wf.run_walkforward(RETURNS, base_seed=42)
        assert r1.fold_results == r2.fold_results
        # synthetic data spans 1990.. so all ten folds have test data
        per = r1.per_policy("terminal_log_wealth")
        assert set(per) == set(wf.BENCHMARK_POLICIES)
        assert all(len(v) == 10 for v in per.values())
        assert r1.protocol_version == "g5-protocol-1.0"

    def test_wilcoxon_always_carries_its_effect_size(self):
        a = np.array([0.5, 0.7, 0.9, 0.6, 0.8, 0.75, 0.65, 0.85, 0.7, 0.6])
        b = a - 0.1
        out = wf.wilcoxon_with_effect(a, b)
        assert out["p_value"] < 0.05
        assert out["effect_size_rank_biserial"] == pytest.approx(1.0)  # b always loses
        assert wf.wilcoxon_with_effect(a, a)["effect_size_rank_biserial"] == 0.0
        with pytest.raises(wf.WalkForwardError):
            wf.wilcoxon_with_effect(a[:2], b[:2])
