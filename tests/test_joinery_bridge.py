"""WP2.7 bridge: the frozen c_b contract, block sampling, cross-fade assembly."""

from __future__ import annotations

import json

import numpy as np
import pytest

from ah.gen.climate import simulate as cs
from ah.gen.joinery import bridge
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


def _decade(climate, source, stats, *, label="EXP", months=MONTHS, seed=5):
    sim = cs.simulate_decades(climate, 1, seed=seed, months=months, theta_index=0)
    regimes = make_regime_paths(np.full((1, months), CODE[label], dtype=np.int64))
    one = wp.build_waypoints(sim, regimes, stats)[0]
    targets = wp.monthly_targets(one, months)
    return sim, one, targets


# --------------------------------------------------------------------------- #
# the frozen c_b contract
# --------------------------------------------------------------------------- #


class TestConditioningContract:
    def test_component_layout_is_frozen(self):
        # WP2.8/2.9 train against this exact layout. Changing it is an interface
        # break for both, so the golden values live in a test, not only in code.
        assert bridge.C_B_DIM == 18
        assert bridge.C_B_COMPONENTS == (
            "regime_EXP",
            "regime_SLOW",
            "regime_REC",
            "regime_CRI",
            "regime_STAG",
            "regime_REF",
            "state_pi_star",
            "state_r_star",
            "state_g",
            "state_v",
            "state_credit_gap",
            "h_equity_ret_12m_log",
            "h_equity_vol_12m",
            "h_spread_level_pct",
            "dw_policy_rate_pct",
            "dw_log_cpi",
            "dw_equity_cum_log",
            "dw_spread_center_pct",
        )
        assert bridge.C_B_SCHEMA_VERSION == "cb-v1"

    def test_vector_order_and_roundtrip(self):
        cond = bridge.BlockConditioning(
            regime_onehot=np.eye(6)[CODE["REC"]],
            state_snapshot=np.array([3.0, 1.0, 2.0, 0.5, -0.2]),
            history_summary=np.array([0.08, 0.04, 1.2]),
            waypoint_increments=np.array([0.5, 0.01, 0.03, -0.1]),
            start_month=42,
        )
        vec = cond.to_vector()
        assert vec.shape == (18,)
        assert vec[CODE["REC"]] == 1.0
        np.testing.assert_allclose(vec[6:11], [3.0, 1.0, 2.0, 0.5, -0.2])
        np.testing.assert_allclose(vec[11:14], [0.08, 0.04, 1.2])
        np.testing.assert_allclose(vec[14:18], [0.5, 0.01, 0.03, -0.1])

        doc = json.loads(cond.to_json())
        assert doc["schema"] == bridge.C_B_SCHEMA_VERSION
        assert doc["start_month"] == 42
        back = bridge.BlockConditioning.from_json(cond.to_json())
        np.testing.assert_array_equal(back.to_vector(), vec)
        assert back.start_month == 42

    def test_continuous_vector_excludes_the_onehot(self):
        cond = bridge.BlockConditioning(
            regime_onehot=np.eye(6)[0],
            state_snapshot=np.arange(5.0),
            history_summary=np.arange(3.0),
            waypoint_increments=np.arange(4.0),
            start_month=0,
        )
        np.testing.assert_array_equal(
            cond.continuous_vector(),
            np.concatenate([np.arange(5.0), np.arange(3.0), np.arange(4.0)]),
        )

    def test_fingerprint_is_stable(self):
        # A deliberate tripwire: WP2.8/2.9 pin this fingerprint; a layout change
        # must change it, and an unchanged layout must reproduce it exactly.
        assert bridge.contract_fingerprint() == bridge.contract_fingerprint()
        assert len(bridge.contract_fingerprint()) == 64

    def test_rejects_malformed_shapes(self):
        with pytest.raises(wp.JoineryError):
            bridge.BlockConditioning(
                regime_onehot=np.zeros(5),
                state_snapshot=np.zeros(5),
                history_summary=np.zeros(3),
                waypoint_increments=np.zeros(4),
                start_month=0,
            )


# --------------------------------------------------------------------------- #
# the bootstrap stand-in sampler
# --------------------------------------------------------------------------- #


def _cond(label: str, start_month: int = 0) -> bridge.BlockConditioning:
    return bridge.BlockConditioning(
        regime_onehot=np.eye(6)[CODE[label]],
        state_snapshot=np.zeros(5),
        history_summary=np.zeros(3),
        waypoint_increments=np.zeros(4),
        start_month=start_month,
    )


class TestBootstrapBlockSampler:
    def test_blocks_are_contiguous_multivariate_rows_of_the_requested_regime(self):
        import ah.gen.bootstrap as bs

        # injective source: values[i, j] = i + 1000*j identifies the row
        n_rows = 60
        import pandas as pd

        values = np.arange(n_rows, dtype=np.float64)[:, None] + 1000.0 * np.arange(3)
        cycle = ("EXP", "EXP", "SLOW", "REC", "CRI", "STAG", "REF", "EXP")
        labels = tuple(cycle[i % len(cycle)] for i in range(n_rows))
        source = bs.BootstrapSource(
            factor_names=("a", "b", "c"),
            dates=pd.DatetimeIndex(pd.date_range("1990-01-01", periods=n_rows, freq="MS")),
            values=values,
            labels=labels,
            ruleset_version="regime_ruleset_v1",
            vintage_id="test",
            active_blocks=("global", "us"),
        )
        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        rng = np.random.Generator(np.random.PCG64(0))
        for _ in range(20):
            block = sampler.sample_block(_cond("REC"), rng)
            assert block.shape == (6, 3)
            rows = block[:, 0].astype(int)
            assert labels[rows[0]] == "REC"  # start month in the requested stratum
            np.testing.assert_array_equal(rows, (rows[0] + np.arange(6)) % n_rows)
            np.testing.assert_array_equal(block[:, 1] - block[:, 0], 1000.0)

    def test_missing_stratum_falls_back_unconditionally_and_records_it(self, source):
        no_stag = make_source(labels=tuple(label for label in ("EXP",) * 240))
        sampler = bridge.BootstrapBlockSampler(no_stag, block_months=6)
        rng = np.random.Generator(np.random.PCG64(1))
        block = sampler.sample_block(_cond("STAG"), rng)
        assert block.shape == (6, 12)
        assert sampler.fallback_counts == {"STAG": 1}

    def test_deterministic_given_rng_seed(self, source):
        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        a = sampler.sample_block(_cond("EXP"), np.random.Generator(np.random.PCG64(9)))
        b = sampler.sample_block(_cond("EXP"), np.random.Generator(np.random.PCG64(9)))
        np.testing.assert_array_equal(a, b)


# --------------------------------------------------------------------------- #
# decade assembly: cross-fade, conditioning construction, guidance hook
# --------------------------------------------------------------------------- #


class _ScriptedSampler:
    """Returns constant blocks (value = call index), capturing every conditioning."""

    def __init__(self, factor_names: tuple[str, ...], block_months: int = 6) -> None:
        self.factor_names = factor_names
        self.block_months = block_months
        self.conds: list[bridge.BlockConditioning] = []

    def sample_block(self, cond, rng) -> np.ndarray:
        self.conds.append(cond)
        value = float(len(self.conds))  # 1, 2, 3, ...
        return np.full((self.block_months, len(self.factor_names)), value)


class TestAssembleDecadePath:
    def test_shape_and_determinism(self, climate, source, stats):
        sim, one, targets = _decade(climate, source, stats)
        from typing import Any

        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        args: dict[str, Any] = dict(
            months=MONTHS,
            waypoints=one,
            targets=targets,
            states_row=sim.states[0],
            sampler=sampler,
            stats=stats,
        )
        path_a, conds_a = bridge.assemble_decade_path(
            rng=np.random.Generator(np.random.PCG64(3)), **args
        )
        path_b, conds_b = bridge.assemble_decade_path(
            rng=np.random.Generator(np.random.PCG64(3)), **args
        )
        assert path_a.shape == (MONTHS, 12)
        np.testing.assert_array_equal(path_a, path_b)
        assert len(conds_a) == len(conds_b) == len(range(0, MONTHS, 3))

    def test_cross_fade_weights_are_linear_on_the_overlap(self, climate, source, stats):
        sim, _one, _targets = _decade(climate, source, stats)
        sampler = _ScriptedSampler(source.factor_names)
        path, _ = bridge.assemble_decade_path(
            months=12,
            waypoints=wp.build_waypoints(
                cs.simulate_decades(climate, 1, seed=5, months=12, theta_index=0),
                make_regime_paths(np.full((1, 12), CODE["EXP"], dtype=np.int64)),
                stats,
            )[0],
            targets=None,
            states_row=sim.states[0][:12],
            sampler=sampler,
            stats=stats,
            rng=np.random.Generator(np.random.PCG64(0)),
        )
        # Block k (1-based value k) starts at month 3(k-1); overlap of 3 months,
        # weights 1/4, 2/4, 3/4 for the incoming block. Judged on equity_mkt —
        # cpi is a CHAINED factor (rebased at joins) and is tested separately.
        col = path[:, list(source.factor_names).index("equity_mkt")]
        np.testing.assert_allclose(col[:3], 1.0)  # block 1 alone
        np.testing.assert_allclose(col[3:6], [1 + 0.25, 1 + 0.5, 1 + 0.75])  # 1->2 fade
        np.testing.assert_allclose(col[6:9], [2.25, 2.5, 2.75])  # 2->3 fade
        np.testing.assert_allclose(col[9:12], [3.25, 3.5, 3.75])  # 3->4 fade (tail)
        # cpi: every incoming block is rebased to continue the assembled level, so
        # constant blocks chain to a constant level — no join discontinuities.
        cpi = path[:, list(source.factor_names).index("cpi")]
        np.testing.assert_allclose(cpi, 1.0)

    def test_cpi_chaining_preserves_within_block_inflation(self, climate, source, stats):
        # A block's information content for a price index is its within-block
        # inflation: the chained path's month-over-month log changes equal the
        # block's own log changes away from the cross-faded joins.
        sim, one, targets = _decade(climate, source, stats)
        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        path, _ = bridge.assemble_decade_path(
            months=MONTHS,
            waypoints=one,
            targets=targets,
            states_row=sim.states[0],
            sampler=sampler,
            stats=stats,
            rng=np.random.Generator(np.random.PCG64(3)),
        )
        cpi = path[:, list(source.factor_names).index("cpi")]
        assert np.all(cpi > 0)
        # a coherent index: no join jump anywhere near the source's own level range
        log_steps = np.abs(np.diff(np.log(cpi)))
        assert log_steps.max() < 0.05  # raw level resampling would show ~0.5 jumps

    def test_targets_none_means_zero_waypoint_increments(self, climate, source, stats):
        # targets=None is the "no Δw conditioning" mode used by the cross-fade test
        sim, _one, _ = _decade(climate, source, stats, months=12)
        sampler = _ScriptedSampler(source.factor_names)
        bridge.assemble_decade_path(
            months=12,
            waypoints=wp.build_waypoints(
                cs.simulate_decades(climate, 1, seed=5, months=12, theta_index=0),
                make_regime_paths(np.full((1, 12), CODE["EXP"], dtype=np.int64)),
                stats,
            )[0],
            targets=None,
            states_row=sim.states[0][:12],
            sampler=sampler,
            stats=stats,
            rng=np.random.Generator(np.random.PCG64(0)),
        )
        for cond in sampler.conds:
            np.testing.assert_array_equal(cond.waypoint_increments, np.zeros(4))

    def test_conditioning_construction(self, climate, source, stats):
        sim, one, targets = _decade(climate, source, stats)
        sampler = _ScriptedSampler(source.factor_names)
        path, conds = bridge.assemble_decade_path(
            months=MONTHS,
            waypoints=one,
            targets=targets,
            states_row=sim.states[0],
            sampler=sampler,
            stats=stats,
            rng=np.random.Generator(np.random.PCG64(0)),
        )
        eq_col = list(source.factor_names).index("equity_mkt")
        sp_col = list(source.factor_names).index("ig_spread")

        first = conds[0]
        # first block: no assembled history -> the documented h0 fallback
        np.testing.assert_allclose(
            first.history_summary,
            [stats.h0_equity_ret_12m, stats.h0_equity_vol_12m, stats.h0_spread_level],
        )
        np.testing.assert_array_equal(first.regime_onehot, np.eye(6)[CODE["EXP"]])
        np.testing.assert_array_equal(first.state_snapshot, sim.states[0][0])

        # a mid-decade block: h_t computed from the assembled path
        cond = next(c for c in conds if c.start_month == 24)
        eq = np.log1p(path[12:24, eq_col])
        np.testing.assert_allclose(
            cond.history_summary,
            [float(eq.sum()), float(np.std(eq, ddof=1)), float(path[23, sp_col])],
        )
        # Δw = target curve increments over the block window
        np.testing.assert_allclose(
            cond.waypoint_increments,
            [
                targets.policy_pct[29] - targets.policy_pct[23],
                targets.log_cpi[29] - targets.log_cpi[23],
                targets.equity_cum_log[29] - targets.equity_cum_log[23],
                targets.spread_center_pct[29] - targets.spread_center_pct[23],
            ],
        )

    def test_guidance_hook_present_stubbed_and_called(self, climate, source, stats):
        sim, _one, _targets = _decade(climate, source, stats, months=12)
        calls: list[int] = []

        class Hook:
            def adjust(self, block: np.ndarray, cond: bridge.BlockConditioning) -> np.ndarray:
                calls.append(cond.start_month)
                return block

        sampler = _ScriptedSampler(source.factor_names)
        one12 = wp.build_waypoints(
            cs.simulate_decades(climate, 1, seed=5, months=12, theta_index=0),
            make_regime_paths(np.full((1, 12), CODE["EXP"], dtype=np.int64)),
            stats,
        )[0]
        with_hook, _ = bridge.assemble_decade_path(
            months=12,
            waypoints=one12,
            targets=None,
            states_row=sim.states[0][:12],
            sampler=sampler,
            stats=stats,
            rng=np.random.Generator(np.random.PCG64(0)),
            guidance=Hook(),
        )
        assert calls == [0, 3, 6, 9]
        # guidance=None (the default) is a no-op: identical output
        sampler2 = _ScriptedSampler(source.factor_names)
        without, _ = bridge.assemble_decade_path(
            months=12,
            waypoints=one12,
            targets=None,
            states_row=sim.states[0][:12],
            sampler=sampler2,
            stats=stats,
            rng=np.random.Generator(np.random.PCG64(0)),
        )
        np.testing.assert_array_equal(with_hook, without)


# --------------------------------------------------------------------------- #
# WP2.8b: the batched (across-decades) assembly driver
# --------------------------------------------------------------------------- #


class _LoopBatchedSampler:
    """A BatchedBlockSampler whose batched entry point is EXACTLY a loop.

    The point of the fixture: ``sample_blocks`` is numerically identical to N
    calls of ``sample_block`` BY CONSTRUCTION, so any difference between the
    batched driver and the per-decade driver is a control-flow bug in the
    bridge, never float noise from a batched matmul.
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self.factor_names = inner.factor_names
        self.block_months = inner.block_months
        self.batch_calls: list[tuple[int, int]] = []  # (start_month, batch size)

    def sample_block(self, cond, rng) -> np.ndarray:
        return self._inner.sample_block(cond, rng)

    def sample_blocks(self, conds, rngs) -> np.ndarray:
        starts = {c.start_month for c in conds}
        assert len(starts) == 1, "a batch must be one block index across decades"
        self.batch_calls.append((starts.pop(), len(conds)))
        return np.stack([self._inner.sample_block(c, r) for c, r in zip(conds, rngs, strict=True)])


def _decade_inputs(climate, source, stats, seeds, *, months=MONTHS):
    """(DecadeAssembly list, per-decade kwargs list) driving the two code paths."""
    decades, kwargs = [], []
    for k, seed in enumerate(seeds):
        sim = cs.simulate_decades(climate, 1, seed=seed, months=months, theta_index=0)
        labels = np.full((1, months), CODE[("EXP", "REC", "CRI", "SLOW")[k % 4]], dtype=np.int64)
        one = wp.build_waypoints(sim, make_regime_paths(labels), stats)[0]
        targets = wp.monthly_targets(one, months)
        decades.append(
            bridge.DecadeAssembly(
                waypoints=one,
                targets=targets,
                states_row=sim.states[0],
                rng=np.random.Generator(np.random.PCG64(1000 + seed)),
            )
        )
        kwargs.append(
            dict(
                months=months,
                waypoints=one,
                targets=targets,
                states_row=sim.states[0],
                stats=stats,
                rng=np.random.Generator(np.random.PCG64(1000 + seed)),
            )
        )
    return decades, kwargs


class TestBatchedAssembly:
    def test_bootstrap_sampler_does_not_advertise_the_batched_entry_point(self, source):
        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        assert isinstance(sampler, bridge.BlockSampler)
        assert not isinstance(sampler, bridge.BatchedBlockSampler)

    def test_fallback_path_is_bit_identical_to_the_per_decade_driver(self, climate, source, stats):
        """A sampler with no batched entry point still goes decade by decade,
        block by block — exactly the committed WP2.7/2.8 behaviour."""
        decades, kwargs = _decade_inputs(climate, source, stats, [11, 12, 13])
        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        batched = bridge.assemble_decade_paths(
            months=MONTHS, decades=decades, sampler=sampler, stats=stats
        )
        reference = bridge.BootstrapBlockSampler(source, block_months=6)
        for (path, conds), kw in zip(batched, kwargs, strict=True):
            ref_path, ref_conds = bridge.assemble_decade_path(sampler=reference, **kw)
            np.testing.assert_array_equal(path, ref_path)
            for a, b in zip(conds, ref_conds, strict=True):
                np.testing.assert_array_equal(a.to_vector(), b.to_vector())
                assert a.start_month == b.start_month

    def test_batched_driver_is_bit_identical_to_the_per_decade_driver(self, climate, source, stats):
        """THE acceptance test for the restructure: with a batched entry point
        that is provably an exact loop, block-major assembly across decades
        reproduces decade-major assembly bit for bit — every path, every c_b."""
        decades, kwargs = _decade_inputs(climate, source, stats, [21, 22, 23, 24, 25])
        sampler = _LoopBatchedSampler(bridge.BootstrapBlockSampler(source, block_months=6))
        assert isinstance(sampler, bridge.BatchedBlockSampler)
        batched = bridge.assemble_decade_paths(
            months=MONTHS, decades=decades, sampler=sampler, stats=stats
        )
        reference = bridge.BootstrapBlockSampler(source, block_months=6)
        for (path, conds), kw in zip(batched, kwargs, strict=True):
            ref_path, ref_conds = bridge.assemble_decade_path(sampler=reference, **kw)
            np.testing.assert_array_equal(path, ref_path)
            for a, b in zip(conds, ref_conds, strict=True):
                np.testing.assert_array_equal(a.to_vector(), b.to_vector())
                assert a.start_month == b.start_month

    def test_the_batch_axis_is_decades_and_the_block_axis_stays_sequential(
        self, climate, source, stats
    ):
        """One sampler call per BLOCK INDEX carrying every decade — and the
        block indices are still visited in order (h_t depends on them)."""
        decades, _ = _decade_inputs(climate, source, stats, [31, 32, 33, 34], months=24)
        sampler = _LoopBatchedSampler(bridge.BootstrapBlockSampler(source, block_months=6))
        bridge.assemble_decade_paths(months=24, decades=decades, sampler=sampler, stats=stats)
        assert sampler.batch_calls == [(start, 4) for start in range(0, 24, 3)]

    def test_guidance_hook_is_applied_per_decade_in_the_batched_driver(
        self, climate, source, stats
    ):
        decades, _ = _decade_inputs(climate, source, stats, [41, 42], months=12)
        seen: list[tuple[int, int]] = []

        class Hook:
            def adjust(self, block, cond):
                seen.append((cond.start_month, int(block.shape[0])))
                return block * 0.0 + 1.0

        sampler = _LoopBatchedSampler(bridge.BootstrapBlockSampler(source, block_months=6))
        out = bridge.assemble_decade_paths(
            months=12, decades=decades, sampler=sampler, stats=stats, guidance=Hook()
        )
        assert seen == [(0, 6), (0, 6), (3, 6), (3, 6), (6, 6), (6, 6), (9, 6), (9, 6)]
        for path, _conds in out:
            np.testing.assert_allclose(path[:, list(source.factor_names).index("equity_mkt")], 1.0)

    def test_batched_sampler_returning_the_wrong_shape_raises(self, climate, source, stats):
        decades, _ = _decade_inputs(climate, source, stats, [51, 52], months=12)

        class Bad(_LoopBatchedSampler):
            def sample_blocks(self, conds, rngs):
                return np.zeros((len(conds), self.block_months + 1, len(self.factor_names)))

        sampler = Bad(bridge.BootstrapBlockSampler(source, block_months=6))
        with pytest.raises(wp.JoineryError, match="expected"):
            bridge.assemble_decade_paths(months=12, decades=decades, sampler=sampler, stats=stats)

    def test_empty_decade_list_is_a_no_op(self, source, stats):
        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        assert (
            bridge.assemble_decade_paths(months=12, decades=[], sampler=sampler, stats=stats) == []
        )

    def test_malformed_inputs_are_rejected_in_the_batched_driver_too(self, climate, source, stats):
        decades, _ = _decade_inputs(climate, source, stats, [61], months=12)
        sampler = bridge.BootstrapBlockSampler(source, block_months=6)
        bad = bridge.DecadeAssembly(
            waypoints=decades[0].waypoints,
            targets=decades[0].targets,
            states_row=np.zeros((11, 5)),
            rng=np.random.Generator(np.random.PCG64(0)),
        )
        with pytest.raises(wp.JoineryError, match="states_row"):
            bridge.assemble_decade_paths(months=12, decades=[bad], sampler=sampler, stats=stats)
