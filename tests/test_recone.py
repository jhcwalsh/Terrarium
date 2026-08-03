"""wp5-03 acceptance: exact re-coning + the was-it-a-good-call metric.

The kickoff's gate for this WP was a VERIFICATION ("hier-flow-v1 mid-path
conditioning cleanly supports re-coning ... do not approximate silently").
These tests pin the exactness claims one by one: the L1 from-state entry, the
truncated-NegBin remaining-sojourn arithmetic, spell-state reconstruction,
bit-exact theta recovery from recorded lineage, prefix-fixity and seam
chaining in the bridge continuation, end-to-end determinism, and every
documented refusal.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.eval.counterfactual import CounterfactualError, score_decision
from ah.gen import recone as rc
from ah.gen import systems
from ah.gen.base import Ensemble, EnsembleMeta
from ah.gen.climate.simulate import simulate_decades, simulate_decades_from_state
from ah.gen.joinery.assemble import LAYER_SEED_OFFSETS, SEED_STRIDE
from ah.gen.regimes import semimarkov as sm
from joinery_common import make_climate_artifact, make_regimes_artifact, make_source

SEED = 20260803


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(
        tmp_path_factory.mktemp("clim"), start="1988-01-01", t_months=480, state_noise=0.05
    )


@pytest.fixture(scope="module")
def regimes_artifact(tmp_path_factory):
    return make_regimes_artifact(tmp_path_factory.mktemp("reg"))


@pytest.fixture(scope="module")
def system(climate, regimes_artifact):
    return systems.StructureOnlyV1(climate, regimes_artifact, make_source(n_rows=240))


@pytest.fixture(scope="module")
def ensemble(system):
    return system.sample_months(120, 3, SEED)


class TestL1FromState:
    def test_theta_pinned_and_deterministic(self, climate):
        s0 = np.array([2.0, 1.0, 1.5, 0.0, 0.0])
        a = simulate_decades_from_state(climate, 4, seed=7, s0=s0, theta_index=2, months=24)
        b = simulate_decades_from_state(climate, 4, seed=7, s0=s0, theta_index=2, months=24)
        assert np.array_equal(a.states, b.states)
        assert (a.theta_index == 2).all()
        # per-continuation innovation streams differ across k
        assert not np.array_equal(a.states[0], a.states[1])

    def test_the_state_is_the_callers_not_a_grid_months(self, climate):
        s_hot = np.array([8.0, 1.0, 1.5, 0.0, 0.0])  # pi_star far from any fitted month
        s_cold = np.array([0.5, 1.0, 1.5, 0.0, 0.0])
        hot = simulate_decades_from_state(climate, 8, seed=9, s0=s_hot, theta_index=0, months=12)
        cold = simulate_decades_from_state(climate, 8, seed=9, s0=s_cold, theta_index=0, months=12)
        pi = 0  # STATE_NAMES order starts at pi_star
        assert hot.states[:, 0, pi].mean() > cold.states[:, 0, pi].mean() + 3.0

    def test_refusals(self, climate):
        s0 = np.zeros(5)
        with pytest.raises(ValueError, match="theta_index"):
            simulate_decades_from_state(
                climate, 1, seed=1, s0=s0, theta_index=climate.n_draws, months=12
            )
        with pytest.raises(ValueError, match="shape"):
            simulate_decades_from_state(climate, 1, seed=1, s0=np.zeros(3), theta_index=0)


class TestTruncatedNegBin:
    def test_conditional_mean_matches_analytic(self):
        r, p, elapsed = 3.0, 0.35, 9
        # analytic conditional mean of S - elapsed given S = 1 + X, X >= elapsed
        pmf = p**r
        probs = [pmf]
        for k in range(2000):
            pmf *= (k + r) / (k + 1.0) * (1.0 - p)
            probs.append(pmf)
        x = np.arange(len(probs))
        tail = x >= elapsed
        analytic = float(
            ((1 + x[tail] - elapsed) * np.array(probs)[tail]).sum() / np.array(probs)[tail].sum()
        )
        rng = np.random.Generator(np.random.PCG64(11))
        draws = [sm._truncated_negbin_remaining(rng, r, p, elapsed) for _ in range(20000)]
        assert np.mean(draws) == pytest.approx(analytic, rel=0.02)
        assert min(draws) >= 1

    def test_deep_tail_returns_at_least_one_month(self):
        rng = np.random.Generator(np.random.PCG64(3))
        assert sm._truncated_negbin_remaining(rng, 2.0, 0.9, 500) >= 1

    def test_running_spell_required(self):
        rng = np.random.Generator(np.random.PCG64(3))
        with pytest.raises(sm.RegimesError, match="elapsed"):
            sm._truncated_negbin_remaining(rng, 2.0, 0.5, 0)


class TestSpellState:
    def test_reconstruction(self):
        labels = np.array([0, 0, 2, 2, 2, 1, 1, 1, 1])
        assert rc._spell_state(labels, 9) == (1, 4, 5)
        assert rc._spell_state(labels, 5) == (2, 3, 2)
        assert rc._spell_state(labels, 2) == (0, 2, 0)


class TestThetaRecovery:
    def test_bit_exact_against_the_simulation_stream(self, climate, regimes_artifact):
        base = SEED
        for decade in range(3):
            l1_seed = base + LAYER_SEED_OFFSETS["climate"] + SEED_STRIDE * decade
            direct = simulate_decades(climate, 1, seed=l1_seed, months=1)
            assert rc.recover_theta_index(base, "climate", decade, climate.n_draws) == int(
                direct.theta_index[0]
            )
            l2_seed = base + LAYER_SEED_OFFSETS["regimes"] + SEED_STRIDE * decade
            direct_r = sm.simulate_regimes(regimes_artifact, direct.states[:, :1, :], seed=l2_seed)
            assert rc.recover_theta_index(base, "regimes", decade, regimes_artifact.n_draws) == int(
                direct_r.theta_index[0]
            )


class TestReconeEndToEnd:
    def test_shape_lineage_and_determinism(self, system, ensemble):
        cone = rc.recone(system, ensemble, path_index=1, at_month=60, n_paths=4, seed=99)
        assert cone.paths.shape == (4, 60, len(ensemble.factor_names))
        assert cone.factor_names == ensemble.factor_names
        meta = cone.meta.conditioning["recone"]
        assert meta["path_index"] == 1 and meta["at_month"] == 60
        assert meta["source_seed"] == SEED
        assert cone.meta.generator_id.endswith(rc.RECONE_GENERATOR_SUFFIX)
        again = rc.recone(system, ensemble, path_index=1, at_month=60, n_paths=4, seed=99)
        assert np.array_equal(cone.paths, again.paths)
        other = rc.recone(system, ensemble, path_index=1, at_month=60, n_paths=4, seed=100)
        assert not np.array_equal(cone.paths, other.paths)

    def test_source_ensemble_is_untouched(self, system, ensemble):
        before = ensemble.paths.copy()
        rc.recone(system, ensemble, path_index=0, at_month=48, n_paths=2, seed=5)
        assert np.array_equal(ensemble.paths, before)

    def test_cpi_chains_exactly_at_the_seam(self, system, ensemble):
        """The chained factor's continuation month 0 rebases to the prefix's
        last level -- integrate()'s anchor arithmetic makes them EQUAL."""
        cone = rc.recone(system, ensemble, path_index=1, at_month=60, n_paths=3, seed=42)
        cpi = ensemble.factor_names.index("cpi")
        anchor = float(ensemble.paths[1, 59, cpi])
        for k in range(cone.n_paths):
            assert float(cone.paths[k, 0, cpi]) == pytest.approx(anchor, rel=1e-9)

    def test_regime_continuation_starts_in_the_running_spell(self, system, ensemble):
        cone = rc.recone(system, ensemble, path_index=2, at_month=72, n_paths=4, seed=13)
        current = int(ensemble.regimes.labels[2, 71])
        assert all(int(cone.regimes.labels[k, 0]) == current for k in range(4))

    def test_refusals(self, system, ensemble):
        with pytest.raises(rc.ReconeError, match="year boundaries"):
            rc.recone(system, ensemble, path_index=0, at_month=61, n_paths=2, seed=1)
        with pytest.raises(rc.ReconeError, match="path_index"):
            rc.recone(system, ensemble, path_index=9, at_month=60, n_paths=2, seed=1)
        stripped = Ensemble(
            paths=ensemble.paths,
            factor_names=ensemble.factor_names,
            meta=ensemble.meta,
            regimes=None,
            slow_states=None,
        )
        with pytest.raises(rc.ReconeError, match="records"):
            rc.recone(system, stripped, path_index=0, at_month=60, n_paths=2, seed=1)


class TestWasItAGoodCall:
    def _cone(self, paths: np.ndarray) -> Ensemble:
        n, months, f = paths.shape
        return Ensemble(
            paths=paths,
            factor_names=[f"f{i}" for i in range(f)],
            meta=EnsembleMeta(
                "test+recone",
                "v",
                0,
                n,
                months,
                conditioning={"recone": {"at_month": 24}},
            ),
        )

    def test_worked_example(self):
        """Four continuations; V_action = terminal f0, V_baseline = 1.0 flat.
        deltas = [1, -1, 3, 1] -> good_call 1.0, win_rate 0.75, median 1.0."""
        paths = np.zeros((4, 12, 2))
        paths[:, -1, 0] = [2.0, 0.0, 4.0, 2.0]
        cone = self._cone(paths)
        score = score_decision(cone, lambda p: float(p[-1, 0]), lambda p: 1.0)
        assert score.good_call == pytest.approx(1.0)
        assert score.win_rate == pytest.approx(0.75)
        assert score.q50 == pytest.approx(1.0)
        assert score.n_paths == 4 and score.at_month == 24
        assert score.deltas.tolist() == [1.0, -1.0, 3.0, 1.0]

    def test_paired_on_the_same_path(self):
        """The baseline is evaluated on the SAME continuation as the action --
        a shared shock cancels in every delta (DN-6's design advantage)."""
        rng = np.random.Generator(np.random.PCG64(1))
        shock = rng.normal(0.0, 5.0, size=8)
        paths = np.zeros((8, 6, 1))
        paths[:, -1, 0] = shock
        cone = self._cone(paths)
        score = score_decision(cone, lambda p: float(p[-1, 0]) + 0.5, lambda p: float(p[-1, 0]))
        assert np.allclose(score.deltas, 0.5)
        assert score.win_rate == 1.0

    def test_refuses_an_unconditional_ensemble(self):
        paths = np.zeros((4, 12, 1))
        plain = Ensemble(paths=paths, factor_names=["f0"], meta=EnsembleMeta("g", "v", 0, 4, 12))
        with pytest.raises(CounterfactualError, match="re-cone"):
            score_decision(plain, lambda p: 0.0, lambda p: 0.0)

    def test_refuses_nan_deltas(self):
        paths = np.zeros((3, 12, 1))
        cone = self._cone(paths)
        with pytest.raises(CounterfactualError, match="non-finite"):
            score_decision(cone, lambda p: float("nan"), lambda p: 0.0)
