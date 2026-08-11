"""WP2.10: the five ablation systems A-E as named compositions.

Everything here runs on the synthetic joinery fixtures (``tests/joinery_common``) --
no catalog, no checkpoints, no network. The REAL artifacts are exercised only by
``scripts/run_ablation_grid.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import joinery_common as jc
from ah.gen import bootstrap as bs
from ah.gen import registry, systems
from ah.gen.joinery import assemble as asm
from ah.gen.joinery import bridge
from ah.gen.joinery import waypoints as wp
from ah.gen.regimes.semimarkov import REGIME_LABELS

MONTHS = 24


@pytest.fixture
def layers(tmp_path):
    climate = jc.make_climate_artifact(tmp_path / "c")
    regimes = jc.make_regimes_artifact(tmp_path / "r")
    source = jc.make_source(240)
    return climate, regimes, source


# --------------------------------------------------------------------------- #
# system A -- the Gaussian residual block sampler
# --------------------------------------------------------------------------- #


def _cond_for(label: str) -> bridge.BlockConditioning:
    onehot = np.zeros(6)
    onehot[REGIME_LABELS.index(label)] = 1.0
    return bridge.BlockConditioning(
        regime_onehot=onehot,
        state_snapshot=np.zeros(5),
        history_summary=np.zeros(3),
        waypoint_increments=np.zeros(4),
        start_month=0,
    )


def test_gaussian_sampler_satisfies_the_block_sampler_protocol(layers):
    _, _, source = layers
    sampler = systems.GaussianResidualBlockSampler(source)
    assert isinstance(sampler, bridge.BlockSampler)
    rng = np.random.Generator(np.random.PCG64(1))
    block = sampler.sample_block(_cond_for("EXP"), rng)
    assert block.shape == (sampler.block_months, len(source.factor_names))
    assert np.all(np.isfinite(block))


def test_gaussian_sampler_draws_every_number_from_the_passed_rng(layers):
    """The joinery owns the stream: same seed in, bit-identical block out."""
    _, _, source = layers
    sampler = systems.GaussianResidualBlockSampler(source)
    cond = _cond_for("REC")
    a = sampler.sample_block(cond, np.random.Generator(np.random.PCG64(11)))
    b = sampler.sample_block(cond, np.random.Generator(np.random.PCG64(11)))
    c = sampler.sample_block(cond, np.random.Generator(np.random.PCG64(12)))
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_gaussian_sampler_uses_a_regime_conditional_mean_when_the_stratum_is_big_enough():
    """The location channel is L2's; a thin stratum falls back to the pooled mean.

    Built with a source whose EXP stratum is large and whose STAG stratum is below
    :data:`systems.GAUSSIAN_MIN_REGIME_OBS`, so both branches are exercised at once.
    """
    labels = tuple(["EXP"] * 200 + ["STAG"] * 5 + ["REC"] * 35)
    source = jc.make_source(240, labels=labels)
    sampler = systems.GaussianResidualBlockSampler(source)
    record = sampler.fit_record
    assert record["by_regime"]["EXP"]["n_obs"] == 200
    assert record["by_regime"]["EXP"]["mean_source"] == "regime"
    assert record["by_regime"]["STAG"]["n_obs"] == 5
    assert record["by_regime"]["STAG"]["mean_source"] == "pooled"
    assert record["covariance_source"] == "pooled"

    # The sampler's moments are exact in ITS OWN coordinate (the constraints'
    # unconstrained space, campaign-3); comparisons happen there.
    from ah.gen.blocks import constraints as ct

    z_source = ct.panel_to_unconstrained(np.asarray(source.values), source.factor_names)
    eq = list(source.factor_names).index("equity_mkt")
    pooled_mean = float(z_source[:, eq].mean())
    exp_mean = float(z_source[np.array(labels) == "EXP", eq].mean())
    # A large draw's sample mean must track the regime mean, not the pooled one.
    rng = np.random.Generator(np.random.PCG64(3))
    draws = np.concatenate(
        [
            ct.panel_to_unconstrained(
                sampler.sample_block(_cond_for("EXP"), rng), source.factor_names
            )[:, eq]
            for _ in range(400)
        ]
    )
    assert abs(draws.mean() - exp_mean) < abs(draws.mean() - pooled_mean)

    stag = np.concatenate(
        [
            ct.panel_to_unconstrained(
                sampler.sample_block(_cond_for("STAG"), rng), source.factor_names
            )[:, eq]
            for _ in range(400)
        ]
    )
    assert abs(stag.mean() - pooled_mean) < 5e-4


def test_gaussian_sampler_reproduces_the_pooled_covariance(layers):
    """The dispersion/correlation channel is pooled and PSD by construction --
    exact in the sampler's own (unconstrained) coordinate, campaign-3."""
    from ah.gen.blocks import constraints as ct

    _, _, source = layers
    sampler = systems.GaussianResidualBlockSampler(source)
    rng = np.random.Generator(np.random.PCG64(5))
    draws = np.concatenate(
        [
            ct.panel_to_unconstrained(
                sampler.sample_block(_cond_for("EXP"), rng), source.factor_names
            )
            for _ in range(2000)
        ]
    )
    want = np.cov(
        ct.panel_to_unconstrained(np.asarray(source.values), source.factor_names), rowvar=False
    )
    got = np.cov(draws, rowvar=False)
    # Loose: 12k draws against a 12x12 covariance. The claim is "this is the pooled
    # covariance", not "this matches to five places".
    scale = float(np.sqrt(np.outer(np.diag(want), np.diag(want))).max())
    assert np.abs(got - want).max() < 0.15 * scale


def test_gaussian_sampler_never_emits_nonpositive_positive_levels():
    """The campaign-3 grid regression (2026-08-11): on the extended panel,
    cpi spans ~26..260 and RAW-SPACE Gaussian draws crossed zero, crashing
    the chaining rebase ('needs positive levels') in all three A cells --
    campaign-2's narrow window (~130..260) had merely masked it. The sampler
    now draws in the constraints' unconstrained coordinates (log space for
    positive levels, the trained samplers' own null geometry), so positivity
    is structural, not sampled luck."""
    from ah.gen.blocks import constraints as ct

    n = 480
    dates = pd.date_range("1953-04-01", periods=n, freq="MS")
    rng = np.random.Generator(np.random.PCG64(3))
    cpi = 26.0 * np.exp(0.005 * np.arange(n))  # ~26 -> ~260, the extended shape
    eq = rng.normal(0.007, 0.04, size=n)
    source = bs.BootstrapSource(
        factor_names=("cpi", "equity_mkt"),
        dates=dates,
        values=np.column_stack([cpi, eq]),
        labels=tuple(["EXP"] * n),
        ruleset_version="regime_ruleset_v1",
        vintage_id="test-v",
        active_blocks=("global",),
    )
    sampler = systems.GaussianResidualBlockSampler(source)
    draw_rng = np.random.Generator(np.random.PCG64(17))
    blocks = np.stack([sampler.sample_block(_cond_for("EXP"), draw_rng) for _ in range(500)])
    j = source.factor_names.index("cpi")
    assert "cpi" in ct.LOG_FACTORS
    assert np.all(blocks[..., j] > 0.0), "a positive level left its structural range"
    k = source.factor_names.index("equity_mkt")
    assert np.all(blocks[..., k] > -1.0)  # log1p returns: r > -1 by construction


def test_gaussian_sampler_rows_are_iid_within_a_block(layers):
    """System A carries NO block-level temporal structure -- that is the control."""
    _, _, source = layers
    sampler = systems.GaussianResidualBlockSampler(source, block_months=6)
    rng = np.random.Generator(np.random.PCG64(9))
    eq = list(source.factor_names).index("equity_mkt")
    blocks = np.stack([sampler.sample_block(_cond_for("EXP"), rng) for _ in range(4000)])
    a = blocks[:, :-1, eq].reshape(-1)
    b = blocks[:, 1:, eq].reshape(-1)
    assert abs(float(np.corrcoef(a, b)[0, 1])) < 0.05


# --------------------------------------------------------------------------- #
# the joinery ablation levers (systems B and C)
# --------------------------------------------------------------------------- #


def test_bind_waypoints_false_zeroes_every_waypoint_increment(layers):
    """System B's defining property, measured on c_b itself."""
    climate, regimes, source = layers
    sampler = bridge.BootstrapBlockSampler(source)
    seen: list[bridge.BlockConditioning] = []

    class _Spy:
        factor_names = sampler.factor_names
        block_months = sampler.block_months

        def sample_block(self, cond, rng):
            seen.append(cond)
            return sampler.sample_block(cond, rng)

    asm.assemble_decades(
        climate=climate,
        regimes_artifact=regimes,
        source=source,
        n_decades=2,
        seed=4,
        months=MONTHS,
        sampler=_Spy(),
        config=asm.JoineryConfig(acceptance_filter=False, bind_waypoints=False),
    )
    assert seen
    assert all(np.array_equal(c.waypoint_increments, np.zeros(4)) for c in seen)


def test_bind_waypoints_false_skips_denton_and_says_so(layers):
    climate, regimes, source = layers
    bound = asm.assemble_decades(
        climate=climate,
        regimes_artifact=regimes,
        source=source,
        n_decades=2,
        seed=4,
        months=MONTHS,
        config=asm.JoineryConfig(acceptance_filter=False),
    )
    unbound = asm.assemble_decades(
        climate=climate,
        regimes_artifact=regimes,
        source=source,
        n_decades=2,
        seed=4,
        months=MONTHS,
        config=asm.JoineryConfig(acceptance_filter=False, bind_waypoints=False),
    )
    bc = bound.meta.conditioning
    uc = unbound.meta.conditioning
    assert bc["reconciliation_applied"] is True
    assert bc["reconciliation"]["per_factor"] != {}
    assert uc["waypoints_bound"] is False
    assert uc["reconciliation_applied"] is False
    assert uc["floors_reapplied_post_denton"] is False
    assert uc["reconciliation"]["per_factor"] == {}
    # And the paths genuinely differ -- the lever is not cosmetic.
    assert not np.allclose(bound.paths, unbound.paths)


def test_use_climate_false_freezes_the_state_snapshot(layers):
    """System C's defining property: L1 contributes no variation to c_b."""
    climate, regimes, source = layers
    sampler = bridge.BootstrapBlockSampler(source)
    seen: list[bridge.BlockConditioning] = []

    class _Spy:
        factor_names = sampler.factor_names
        block_months = sampler.block_months

        def sample_block(self, cond, rng):
            seen.append(cond)
            return sampler.sample_block(cond, rng)

    ens = asm.assemble_decades(
        climate=climate,
        regimes_artifact=regimes,
        source=source,
        n_decades=3,
        seed=4,
        months=MONTHS,
        sampler=_Spy(),
        config=asm.JoineryConfig(acceptance_filter=False, bind_waypoints=False, use_climate=False),
    )
    snapshots = np.stack([c.state_snapshot for c in seen])
    assert np.allclose(snapshots, snapshots[0])
    assert ens.meta.conditioning["climate_layer"] == "frozen-posterior-mean"


def test_frozen_climate_is_the_posterior_mean_and_draws_no_rng(layers):
    climate, _, _ = layers
    sim = asm.frozen_climate(climate, months=MONTHS)
    assert sim.states.shape == (1, MONTHS, 5)
    assert np.allclose(sim.states, sim.states[0, 0])
    t0 = len(climate.dates) - 1
    assert np.allclose(sim.states[0, 0], climate.states[:, t0, :].mean(axis=0))
    assert int(sim.theta_index[0]) == -1
    assert np.allclose(sim.params["a_val"], float(np.mean(climate.params["a_val"])))
    again = asm.frozen_climate(climate, months=MONTHS)
    assert np.array_equal(sim.states, again.states)


def test_frozen_climate_rejects_an_off_grid_s0_date(layers):
    climate, _, _ = layers
    with pytest.raises(wp.JoineryError, match="monthly grid"):
        asm.frozen_climate(climate, months=MONTHS, s0_date="1800-01-01")


def test_the_default_joinery_config_is_unchanged_by_the_new_levers():
    """D and the WP2.7/2.8/2.9 runs must be byte-identical in configuration."""
    cfg = asm.JoineryConfig()
    assert cfg.bind_waypoints is True
    assert cfg.use_climate is True
    assert cfg.as_dict()["bind_waypoints"] is True
    assert cfg.as_dict()["use_climate"] is True


# --------------------------------------------------------------------------- #
# the named compositions
# --------------------------------------------------------------------------- #


def test_every_ablation_system_is_registered_and_resolvable_by_id():
    registered = set(registry.registered())
    for system_id in systems.REGISTERED_ABLATION_IDS:
        assert system_id in registered, system_id


def test_the_system_table_covers_the_sealed_letters_a_through_f():
    """Campaign-3 (AM-2026-08-10-001, ruling K3) added F -- through campaign-2
    this asserted exactly DN-1.1's A-E; the sealed ablation_systems grid is
    now six and the assertion is updated to the new truth, not relaxed."""
    letters = {row.letter for row in systems.SYSTEMS}
    assert letters == {"A", "B", "C", "D", "E", "F"}
    # Campaign-3: ONE trained D sampler, hier-flow-v2 (hier-diffusion does not
    # race; the campaign-2 table carried both v1 arms).
    d_ids = [row.system_id for row in systems.SYSTEMS if row.letter == "D"]
    assert d_ids == ["hier-flow-v2"]
    assert [row.system_id for row in systems.SYSTEMS if row.letter == "E"] == ["bootstrap-v1"]
    assert [row.system_id for row in systems.SYSTEMS if row.letter == "F"] == ["har-masked"]


def test_neural_rows_declare_training_seeds_and_deterministic_rows_do_not():
    for row in systems.SYSTEMS:
        if row.letter in {"B", "C", "D", "F"}:
            assert row.neural is True
            assert row.family in {"diffusion", "flow"}
        else:
            assert row.neural is False
            assert row.family is None


def test_the_seed_plan_gives_at_least_the_sealed_minimum_and_is_shared():
    assert len(systems.SEED_PLAN) >= 3  # multi_seed_decision_rule.minimum_seeds
    seeds = [s.sample_seed for s in systems.SEED_PLAN]
    assert len(set(seeds)) == len(seeds)
    assert [s.index for s in systems.SEED_PLAN] == list(range(len(seeds)))


def test_training_seeds_start_from_each_familys_own_committed_final_seed():
    """The two arms' primary seeds genuinely differ; indexing hides that, honestly."""
    assert systems.train_seed_for("diffusion", 0) == 20260727
    assert systems.train_seed_for("flow", 0) == 20260728
    for family in ("diffusion", "flow"):
        seeds = [systems.train_seed_for(family, k) for k in range(3)]
        assert len(set(seeds)) == 3
        assert seeds[1] - seeds[0] == systems.SEED_STRIDE


def test_train_seed_for_rejects_an_unknown_family_or_negative_index():
    with pytest.raises(wp.JoineryError, match="unknown L3 family"):
        systems.train_seed_for("gan", 0)
    with pytest.raises(wp.JoineryError, match="seed_index"):
        systems.train_seed_for("flow", -1)


def test_the_untested_arms_are_named_rather_than_left_implicit():
    tested = {row.system_id for row in systems.SYSTEMS}
    assert systems.UNTESTED_ARMS  # running one sampler through B/C leaves two behind
    assert not (set(systems.UNTESTED_ARMS) & tested)
    for system_id in systems.UNTESTED_ARMS:
        assert system_id in systems.REGISTERED_ABLATION_IDS


def test_system_a_builds_and_samples_end_to_end(layers):
    climate, regimes, source = layers
    system = systems.StructureOnlyV1(climate, regimes, source)
    ens = system.sample_months(MONTHS, 3, seed=7, unfiltered=True)
    assert ens.paths.shape == (3, MONTHS, len(source.factor_names))
    assert ens.meta.generator_id == systems.SYSTEM_A_ID
    cond = ens.meta.conditioning
    assert cond["reconciliation_applied"] is True  # A keeps Denton: floors
    assert cond["climate_layer"] == "simulated"
    assert cond["block_sampler"] == "GaussianResidualBlockSampler"
    assert cond["residual_model"]["covariance_source"] == "pooled"
    # deterministic per seed
    again = systems.StructureOnlyV1(climate, regimes, source).sample_months(
        MONTHS, 3, seed=7, unfiltered=True
    )
    assert np.array_equal(ens.paths, again.paths)


def test_system_a_never_violates_the_hard_floors(layers):
    """Gaussian draws are NOT floor-safe; Denton's floor re-application is why A binds."""
    climate, regimes, source = layers
    ens = systems.StructureOnlyV1(climate, regimes, source).sample_months(
        MONTHS, 4, seed=13, unfiltered=True
    )
    names = list(ens.factor_names)
    assert ens.factor("ig_spread").min() >= wp.SPREAD_FLOOR_PCT - 1e-9
    assert ens.factor("policy_rate").min() >= wp.RATE_FLOOR_PCT - 1e-9
    assert "cpi" in names


def test_ablation_rows_are_uniquely_keyed():
    keys = [(row.letter, row.system_id) for row in systems.SYSTEMS]
    assert len(keys) == len(set(keys))
    assert len({row.system_id for row in systems.SYSTEMS}) == len(systems.SYSTEMS)
