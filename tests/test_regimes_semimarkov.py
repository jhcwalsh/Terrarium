"""WP2.6 semimarkov.py: config validation, deterministic artifact load, seeded
semi-Markov simulation over L1 slow-state paths, the c_t cycle contract, and the
three WorldSpec regime modes (sequence exact, transition_matrix, unconditional).

Synthetic artifacts are built through ``ah.gen.regimes.fit.save_artifact`` so the
save/load/hash path under test is the production one.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.core.worldspec import Horizon, Regimes, SequenceSegment, TransitionMatrix
from ah.data.derive import REGIME_LABELS
from ah.gen.climate import fit as climate_fit
from ah.gen.climate import simulate as climate_sim
from ah.gen.regimes import fit as rf
from ah.gen.regimes import semimarkov as sm

# --------------------------------------------------------------------------- #
# synthetic artifact helpers
# --------------------------------------------------------------------------- #

N_DRAWS = 8
IDX = {label: i for i, label in enumerate(REGIME_LABELS)}


def _draws(
    *,
    alpha: np.ndarray | None = None,
    gamma: np.ndarray | None = None,
    r: np.ndarray | None = None,
    trans_a: np.ndarray | None = None,
    b_dest: np.ndarray | None = None,
    n_draws: int = N_DRAWS,
) -> dict[str, np.ndarray]:
    """Posterior draws, every draw identical unless a caller spreads one."""

    def tile(base: np.ndarray) -> np.ndarray:
        return np.broadcast_to(base, (n_draws, *base.shape)).astype(np.float64).copy()

    if alpha is None:
        alpha = np.zeros(6)
    if gamma is None:
        gamma = np.zeros((6, 4))
    if r is None:
        r = np.full(6, 3.0)
    if trans_a is None:
        trans_a = np.zeros((6, 6))
    if b_dest is None:
        b_dest = np.zeros((6, 4))
    return {
        "alpha": tile(alpha),
        "gamma": tile(gamma),
        "r": tile(r),
        "trans_a": tile(trans_a),
        "b_dest": tile(b_dest),
    }


def _artifact(tmp_path, draws: dict[str, np.ndarray] | None = None, **meta_extra):
    draws = draws if draws is not None else _draws()
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "regimes.npz"
    meta = {
        "schema_version": rf.ARTIFACT_SCHEMA_VERSION,
        "ruleset_version": "regime_ruleset_v1",
        "pi_target": 2.0,
        "slope_psi0": 0.7,
        "slope_phi_c0": 0.1,
        "climate_artifact_sha256": "test" * 16,
        **meta_extra,
    }
    rf.save_artifact(
        path,
        draws=draws,
        cov_mean=np.array([0.7, 0.0, 1.0, 0.0]),
        cov_sd=np.array([1.2, 5.0, 2.0, 1.0]),
        cycle_by_regime=np.array([1.0, 1.0, -0.6, -1.0, 1.0, 1.0]),
        init_freqs=np.array([0.5, 0.15, 0.12, 0.05, 0.1, 0.08]),
        meta=meta,
    )
    return sm.load_artifact(path)


def _states(n_decades: int, months: int, *, credit_gap: float = 0.0, pi_star: float = 3.0):
    states = np.zeros((n_decades, months, 5))
    states[:, :, 0] = pi_star
    states[:, :, 4] = credit_gap
    return states


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #


class TestConfig:
    def test_default_config_loads_and_validates(self):
        cfg = sm.load_config()
        assert set(cfg.priors.model_dump()) == {"alpha", "gamma", "log_r", "trans_a", "trans_b"}
        assert cfg.sensitivity.version == "regime_ruleset_v1b"
        assert cfg.sensitivity.growth_slow > cfg.sensitivity.growth_weak
        assert cfg.pi_target == 2.0

    def test_config_dict_is_hash_stable(self):
        from ah.experiment import config_hash

        a = config_hash(sm.config_dict(sm.load_config()))
        b = config_hash(sm.config_dict(sm.load_config()))
        assert a == b

    def test_sensitivity_thresholds_differ_from_v1(self):
        """The v1b variant must actually perturb the labeling boundaries."""
        from ah.data.derive import regime_thresholds

        v1 = regime_thresholds()
        v1b = sm.load_config().sensitivity.model_dump()
        assert v1b["version"] != v1["version"]
        changed = [
            k
            for k in ("cpi_high", "growth_weak", "growth_slow", "drawdown_crisis")
            if v1b[k] != v1[k]
        ]
        assert len(changed) >= 3

    def test_bad_sensitivity_band_ordering_refused(self):
        cfg = sm.load_config()
        with pytest.raises(ValueError, match="growth_slow"):
            sm.SensitivityThresholds(
                **{**cfg.sensitivity.model_dump(), "growth_slow": 0.0, "growth_weak": 0.5}
            )


# --------------------------------------------------------------------------- #
# artifact load
# --------------------------------------------------------------------------- #


class TestArtifact:
    def test_round_trip_and_hash(self, tmp_path):
        art = _artifact(tmp_path)
        assert art.n_draws == N_DRAWS
        assert art.alpha.shape == (N_DRAWS, 6)
        assert art.trans_a.shape == (N_DRAWS, 6, 6)
        assert art.meta["content_sha256"]

    def test_tampered_file_refused(self, tmp_path):
        art = _artifact(tmp_path)
        data = dict(np.load(art.path, allow_pickle=False))
        data["alpha"] = data["alpha"] + 1.0
        np.savez(art.path, **data)
        with pytest.raises(sm.RegimesError, match="hash mismatch"):
            sm.load_artifact(art.path)

    def test_missing_file_refused(self, tmp_path):
        with pytest.raises(sm.RegimesError, match="not found"):
            sm.load_artifact(tmp_path / "nope.npz")

    def test_resave_same_content_same_hash(self, tmp_path):
        a = _artifact(tmp_path / "a")
        b = _artifact(tmp_path / "b")
        assert a.meta["content_sha256"] == b.meta["content_sha256"]


# --------------------------------------------------------------------------- #
# simulation determinism + parameter uncertainty
# --------------------------------------------------------------------------- #


class TestSimulateDeterminism:
    def test_same_seed_bit_identical(self, tmp_path):
        art = _artifact(tmp_path)
        states = _states(6, 120)
        a = sm.simulate_regimes(art, states, seed=42)
        b = sm.simulate_regimes(art, states, seed=42)
        np.testing.assert_array_equal(a.labels, b.labels)
        np.testing.assert_array_equal(a.cycle, b.cycle)
        np.testing.assert_array_equal(a.theta_index, b.theta_index)

    def test_different_seed_differs(self, tmp_path):
        art = _artifact(tmp_path)
        states = _states(8, 120)
        a = sm.simulate_regimes(art, states, seed=42)
        b = sm.simulate_regimes(art, states, seed=43)
        assert not np.array_equal(a.labels, b.labels)

    def test_decade_seed_stride_independence(self, tmp_path):
        """Decade k depends only on base_seed + 7919*k, not on n_decades."""
        art = _artifact(tmp_path)
        small = sm.simulate_regimes(art, _states(2, 120), seed=7)
        large = sm.simulate_regimes(art, _states(5, 120), seed=7)
        np.testing.assert_array_equal(small.labels, large.labels[:2])

    def test_theta_varies_across_decades(self, tmp_path):
        alpha_spread = _draws()
        alpha_spread["alpha"] = np.linspace(-2.0, 2.0, N_DRAWS)[:, None] * np.ones((1, 6))
        art = _artifact(tmp_path, alpha_spread)
        sim = sm.simulate_regimes(art, _states(24, 120), seed=5)
        assert len(np.unique(sim.theta_index)) > 1

    def test_theta_index_pins(self, tmp_path):
        art = _artifact(tmp_path)
        sim = sm.simulate_regimes(art, _states(4, 60), seed=3, theta_index=2)
        assert set(sim.theta_index.tolist()) == {2}
        with pytest.raises(sm.RegimesError, match="theta_index"):
            sm.simulate_regimes(art, _states(1, 12), seed=1, theta_index=N_DRAWS)

    def test_labels_are_valid_and_cover_every_month(self, tmp_path):
        art = _artifact(tmp_path)
        sim = sm.simulate_regimes(art, _states(16, 120), seed=9)
        assert sim.labels.shape == (16, 120)
        assert sim.labels.min() >= 0 and sim.labels.max() <= 5

    def test_bad_states_shape_refused(self, tmp_path):
        art = _artifact(tmp_path)
        with pytest.raises(sm.RegimesError, match="states"):
            sm.simulate_regimes(art, np.zeros((4, 120)), seed=1)


# --------------------------------------------------------------------------- #
# the model responds to its inputs
# --------------------------------------------------------------------------- #


class TestModelBehavior:
    def test_sojourn_intercepts_move_durations(self, tmp_path):
        """Low logit p => long sojourns; high => short (the NegBin convention)."""
        short = _draws(alpha=np.full(6, 2.0))
        long = _draws(alpha=np.full(6, -2.0))
        art_s = _artifact(tmp_path / "s", short)
        art_l = _artifact(tmp_path / "l", long)
        states = _states(32, 120)
        mean_spell_s = _mean_complete_spell(sm.simulate_regimes(art_s, states, seed=11).labels)
        mean_spell_l = _mean_complete_spell(sm.simulate_regimes(art_l, states, seed=11).labels)
        assert mean_spell_l > 2.0 * mean_spell_s

    def test_crisis_hazard_rises_with_credit_gap(self, tmp_path):
        """b_dest[CRI] loaded on the (standardized) credit gap: high-gap decades
        must see more CRI months than low-gap decades (DN-1.1's stated direction)."""
        b = np.zeros((6, 4))
        b[IDX["CRI"], 1] = 2.0  # covariate 1 = credit_gap
        art = _artifact(tmp_path, _draws(alpha=np.full(6, 1.0), b_dest=b))
        hot = sm.simulate_regimes(art, _states(48, 120, credit_gap=15.0), seed=13)
        cold = sm.simulate_regimes(art, _states(48, 120, credit_gap=-15.0), seed=13)
        assert (hot.labels == IDX["CRI"]).mean() > 2.0 * (cold.labels == IDX["CRI"]).mean()

    def test_stag_sojourn_lengthens_with_pi_star(self, tmp_path):
        """gamma[STAG] < 0 on pi_gap: high trend inflation => longer STAG spells."""
        g = np.zeros((6, 4))
        g[IDX["STAG"], 2] = -2.0  # covariate 2 = pi_gap
        art = _artifact(tmp_path, _draws(gamma=g))
        hi = sm.simulate_regimes(art, _states(48, 120, pi_star=9.0), seed=17)
        lo = sm.simulate_regimes(art, _states(48, 120, pi_star=2.0), seed=17)
        assert (hi.labels == IDX["STAG"]).mean() > (lo.labels == IDX["STAG"]).mean()

    def test_transition_matrix_at_z0_respected(self, tmp_path):
        """A huge trans_a entry makes that destination dominate transitions."""
        a = np.zeros((6, 6))
        a[IDX["EXP"], IDX["STAG"]] = 8.0  # leaving EXP goes to STAG
        art = _artifact(tmp_path, _draws(alpha=np.full(6, 1.5), trans_a=a))
        sim = sm.simulate_regimes(art, _states(32, 120), seed=19)
        # every spell that follows an EXP spell should be STAG
        follows = _followers(sim.labels, IDX["EXP"])
        assert follows and all(f == IDX["STAG"] for f in follows)


def _mean_complete_spell(labels: np.ndarray) -> float:
    durs: list[int] = []
    for row in labels:
        spells = sm.spells_from_labels(row)
        durs.extend(d for _, _, d in spells[1:-1])
    return float(np.mean(durs)) if durs else float("nan")


def _followers(labels: np.ndarray, state: int) -> list[int]:
    from itertools import pairwise

    out: list[int] = []
    for row in labels:
        for (s, _, _), (nxt, _, _) in pairwise(sm.spells_from_labels(row)):
            if s == state:
                out.append(nxt)
    return out


# --------------------------------------------------------------------------- #
# the c_t cycle contract (what WP2.5 consumes)
# --------------------------------------------------------------------------- #


class TestCycleTerm:
    def test_cycle_is_the_per_regime_mapping(self, tmp_path):
        art = _artifact(tmp_path)
        sim = sm.simulate_regimes(art, _states(6, 120), seed=21)
        np.testing.assert_array_equal(sim.cycle, art.cycle_by_regime[sim.labels])

    def test_cycle_within_contract_bounds(self, tmp_path):
        art = _artifact(tmp_path)
        sim = sm.simulate_regimes(art, _states(6, 120), seed=21)
        assert np.all(np.abs(sim.cycle) <= 1.0)
        assert np.all(np.isfinite(sim.cycle))

    def test_recessionary_regimes_map_negative_expansion_positive(self, tmp_path):
        art = _artifact(tmp_path)
        c = art.cycle_by_regime
        assert c[IDX["EXP"]] > 0.5
        assert c[IDX["CRI"]] <= -0.5
        assert c[IDX["REC"]] < 0.0

    def test_climate_simulate_accepts_the_cycle(self, tmp_path):
        """End-to-end contract: L2's c_t feeds L1's simulate_decades unchanged."""
        art = _artifact(tmp_path / "l2")
        sim = sm.simulate_regimes(art, _states(3, 120), seed=23)
        climate_art = _tiny_climate_artifact(tmp_path / "l1")
        out = climate_sim.simulate_decades(climate_art, 3, seed=1, cycle=sim.cycle)
        assert out.states.shape == (3, 120, 5)


def _tiny_climate_artifact(tmp_path):
    import pandas as pd

    from ah.gen.climate.model import PARAM_NAMES

    rng = np.random.Generator(np.random.PCG64(3))
    # arbitrary positive values are fine: only the c_t contract is under test here
    params = {name: np.full(4, 0.5) for name in PARAM_NAMES}
    states = rng.standard_normal((4, 24, 5)) * 0.1
    dates = pd.date_range("2019-01-01", periods=24, freq="MS")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "climate.npz"
    climate_fit.save_artifact(path, params=params, states=states, dates=dates, meta={})
    return climate_sim.load_artifact(path)


# --------------------------------------------------------------------------- #
# WorldSpec modes
# --------------------------------------------------------------------------- #


def _horizon(quarters: int) -> Horizon:
    return Horizon(start="2025-Q1", quarters=quarters)


class TestSequenceMode:
    def test_sequence_mode_is_exact(self, tmp_path):
        """The plan's acceptance: mode=sequence pins R_t exactly."""
        art = _artifact(tmp_path)
        regimes = Regimes(
            mode="sequence",
            sequence=[
                SequenceSegment(regime="stagflation", from_quarter=0, to_quarter=3),
                SequenceSegment(regime="recession", from_quarter=4, to_quarter=5),
                SequenceSegment(regime="recovery", from_quarter=6, to_quarter=7),
            ],
        )
        paths = sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=3, seed=1)
        expected = [IDX["STAG"]] * 12 + [IDX["REC"]] * 6 + [IDX["EXP"]] * 6
        for k in range(3):
            assert paths.labels[k].tolist() == expected
        assert paths.mode == "sequence"

    def test_sequence_mode_seed_invariant(self, tmp_path):
        art = _artifact(tmp_path)
        regimes = Regimes(
            mode="sequence",
            sequence=[SequenceSegment(regime="crisis", from_quarter=0, to_quarter=7)],
        )
        a = sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=2, seed=1)
        b = sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=2, seed=99)
        np.testing.assert_array_equal(a.labels, b.labels)

    def test_gappy_sequence_refused(self, tmp_path):
        art = _artifact(tmp_path)
        regimes = Regimes(
            mode="sequence",
            sequence=[SequenceSegment(regime="expansion", from_quarter=0, to_quarter=3)],
        )
        with pytest.raises(sm.RegimesError, match="tile"):
            sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=1, seed=1)


class TestTransitionMatrixMode:
    def test_absorbing_state_respected(self, tmp_path):
        art = _artifact(tmp_path)
        regimes = Regimes(
            mode="transition_matrix",
            transition_matrix=TransitionMatrix(
                states=["expansion", "crisis"],
                matrix=[[0.0, 1.0], [0.0, 1.0]],  # everything falls into crisis and stays
                initial_state="expansion",
            ),
        )
        paths = sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=4, seed=2)
        for k in range(4):
            assert paths.labels[k, :3].tolist() == [IDX["EXP"]] * 3  # initial quarter
            assert paths.labels[k, 3:].tolist() == [IDX["CRI"]] * 21  # absorbed
        assert paths.mode == "transition_matrix"

    def test_quarterly_expansion_to_months(self, tmp_path):
        """Each quarterly chain step spans exactly three months."""
        art = _artifact(tmp_path)
        regimes = Regimes(
            mode="transition_matrix",
            transition_matrix=TransitionMatrix(
                states=["expansion", "recession"],
                matrix=[[0.5, 0.5], [0.5, 0.5]],
                initial_state="expansion",
            ),
        )
        paths = sm.regime_path_for_world(art, regimes, _horizon(20), n_paths=8, seed=3)
        arr = paths.labels.reshape(8, 20, 3)
        assert (arr == arr[:, :, :1]).all()  # constant within each quarter

    def test_deterministic_per_seed(self, tmp_path):
        art = _artifact(tmp_path)
        regimes = Regimes(
            mode="transition_matrix",
            transition_matrix=TransitionMatrix(
                states=["expansion", "recession"],
                matrix=[[0.7, 0.3], [0.4, 0.6]],
                initial_state="recession",
            ),
        )
        a = sm.regime_path_for_world(art, regimes, _horizon(12), n_paths=4, seed=5)
        b = sm.regime_path_for_world(art, regimes, _horizon(12), n_paths=4, seed=5)
        np.testing.assert_array_equal(a.labels, b.labels)
        assert (a.labels[:, :3] == IDX["REC"]).all()

    def test_bad_matrix_rows_refused(self, tmp_path):
        art = _artifact(tmp_path)
        regimes = Regimes(
            mode="transition_matrix",
            transition_matrix=TransitionMatrix(
                states=["expansion", "recession"],
                matrix=[[0.5, 0.2], [0.5, 0.5]],  # row 0 sums to 0.7
                initial_state="expansion",
            ),
        )
        with pytest.raises(sm.RegimesError, match="row"):
            sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=1, seed=1)


class TestUnconditionalMode:
    def test_frequencies_match_historical(self, tmp_path):
        art = _artifact(tmp_path)
        regimes = Regimes(mode="unconditional")
        paths = sm.regime_path_for_world(art, regimes, _horizon(40), n_paths=200, seed=7)
        freqs = np.bincount(paths.labels.ravel(), minlength=6) / paths.labels.size
        np.testing.assert_allclose(freqs, art.init_freqs, atol=0.02)
        assert paths.mode == "unconditional"

    def test_deterministic_per_seed(self, tmp_path):
        art = _artifact(tmp_path)
        regimes = Regimes(mode="unconditional")
        a = sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=3, seed=11)
        b = sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=3, seed=11)
        np.testing.assert_array_equal(a.labels, b.labels)

    def test_cycle_emitted_in_every_mode(self, tmp_path):
        art = _artifact(tmp_path)
        for regimes in (
            Regimes(
                mode="sequence",
                sequence=[SequenceSegment(regime="expansion", from_quarter=0, to_quarter=7)],
            ),
            Regimes(mode="unconditional"),
        ):
            paths = sm.regime_path_for_world(art, regimes, _horizon(8), n_paths=2, seed=1)
            np.testing.assert_array_equal(paths.cycle, art.cycle_by_regime[paths.labels])


# --------------------------------------------------------------------------- #
# spells helper + leakage guard
# --------------------------------------------------------------------------- #


class TestSpells:
    def test_runs_decomposed(self):
        labels = np.array([0, 0, 1, 1, 1, 3, 0, 0])
        assert sm.spells_from_labels(labels) == [(0, 0, 2), (1, 2, 3), (3, 5, 1), (0, 6, 2)]

    def test_single_run(self):
        assert sm.spells_from_labels(np.array([2, 2, 2])) == [(2, 0, 3)]


def test_regimes_modules_never_import_eval() -> None:
    """CLAUDE.md: ah.gen never imports ah.eval (the wider rule, not just g2)."""
    import re
    from pathlib import Path

    pkg = Path(sm.__file__).resolve().parent
    pattern = re.compile(r"^\s*(import\s+ah\.eval|from\s+ah\.eval)", re.MULTILINE)
    offenders = [p.name for p in pkg.glob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"ah.gen.regimes must not import ah.eval: {offenders}"
