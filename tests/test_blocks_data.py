"""WP2.8 data tests — cb-v1 reuse, train-only standardization, block-aware folds."""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.blocks import data as bd
from ah.gen.joinery import bridge
from ah.gen.joinery import waypoints as wp
from joinery_common import make_climate_artifact, make_source

VAL_DATE = "2005-01-01"  # month index 180 of a 1990-01 panel


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(
        tmp_path_factory.mktemp("clim"), start="1988-01-01", t_months=480, state_noise=0.05
    )


@pytest.fixture(scope="module")
def source():
    return make_source(n_rows=240)


@pytest.fixture(scope="module")
def dataset(source, climate):
    return bd.build_dataset(source, climate, validation_start_date=VAL_DATE)


class TestConditioningReusesBridge:
    def test_regime_onehot_matches_source_labels(self, dataset, source):
        labels = list(source.labels)
        for i, start in enumerate(dataset.starts[:40]):
            onehot = dataset.cond[i, :6]
            assert onehot.sum() == 1.0
            assert wp.REGIME_LABELS[int(np.argmax(onehot))] == labels[int(start)]

    def test_state_snapshot_is_posterior_mean_at_start(self, dataset, source, climate):
        idx = climate.dates.get_indexer(source.dates)
        states = climate.states.mean(axis=0)[idx]
        for i in (0, 7, 100):
            np.testing.assert_allclose(dataset.cond[i, 6:11], states[int(dataset.starts[i])])

    def test_history_summary_matches_hand_computation(self, dataset, source):
        names = list(source.factor_names)
        eq_col = names.index("equity_mkt")
        spread_col = names.index("ig_spread")
        start = 30
        i = int(np.flatnonzero(dataset.starts == start)[0])
        eq = np.log1p(source.values[start - 12 : start, eq_col])
        np.testing.assert_allclose(
            dataset.cond[i, 11:14],
            [eq.sum(), np.std(eq, ddof=1), source.values[start - 1, spread_col]],
        )

    def test_early_blocks_use_h0_fallback_per_contract(self, dataset):
        stats = dataset.stats
        for i, start in enumerate(dataset.starts):
            if start >= 12:
                continue
            np.testing.assert_allclose(
                dataset.cond[i, 11:14],
                [stats.h0_equity_ret_12m, stats.h0_equity_vol_12m, stats.h0_spread_level],
            )

    def test_dw_is_target_curve_increment_via_bridge_helper(self, dataset, source):
        # Train-segment curve (split hygiene): the panel's [0, 180) months.
        targets = bd.historical_monthly_targets(source, 0, dataset.validation_start_month)
        start, ell = 50, dataset.block_months
        i = int(np.flatnonzero(dataset.starts == start)[0])
        expected = bridge._waypoint_increments(targets, start, ell, dataset.validation_start_month)
        np.testing.assert_allclose(dataset.cond[i, 14:18], expected)

    def test_train_dw_curves_never_touch_validation_aggregates(self, dataset, source, climate):
        """The policy year-CENTER anchors must not interpolate a validation-year
        mean into late-train Δw conditioning (the split-hygiene channel)."""
        import dataclasses

        poisoned_values = source.values.copy()
        poisoned_values[dataset.validation_start_month :, :] *= 1.9
        poisoned = dataclasses.replace(
            source,
            values=poisoned_values,
            dates=source.dates,
            labels=source.labels,
        )
        after = bd.build_dataset(poisoned, climate, validation_start_date=VAL_DATE)
        np.testing.assert_array_equal(
            dataset.cond[dataset.train_index], after.cond[after.train_index]
        )

    def test_cond_dim_is_the_frozen_contract_dim(self, dataset):
        assert dataset.cond.shape[1] == bridge.C_B_DIM == 18


class TestTargets:
    def test_cpi_column_is_rebased_to_block_start(self, dataset, source):
        col = list(source.factor_names).index("cpi")
        np.testing.assert_allclose(dataset.x[:, 0, col], 0.0, atol=1e-14)

    def test_non_chained_factors_round_trip_to_panel_units(self, dataset, source):
        k = 0
        rows = dataset.fold_indices[k]
        units = dataset.fold_x_units(k)
        names = list(source.factor_names)
        for j, name in enumerate(names):
            if name in bridge.CHAINED_FACTORS:
                continue
            for r, row in enumerate(rows[:10]):
                s = int(dataset.starts[row])
                np.testing.assert_allclose(units[r, :, j], source.values[s : s + 6, j], rtol=1e-10)

    def test_historical_targets_hit_actual_annual_anchors(self, source):
        targets = bd.historical_monthly_targets(source)
        names = list(source.factor_names)
        cpi = source.values[:, names.index("cpi")]
        spread = source.values[:, names.index("ig_spread")]
        for yend in (11, 23, 119):
            np.testing.assert_allclose(
                targets.log_cpi[yend], np.log(cpi[yend]) - np.log(cpi[0]), rtol=1e-12
            )
            np.testing.assert_allclose(targets.spread_center_pct[yend], spread[yend], rtol=1e-12)


class TestFolds:
    def test_no_block_straddles_any_boundary(self, dataset):
        months = dataset.x.shape[0] + dataset.block_months - 1
        edges = bd._fold_boundaries(dataset.validation_start_month, months, 3)
        segments = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
        for rows in (dataset.train_index, *dataset.fold_indices):
            for row in rows:
                s = int(dataset.starts[row])
                assert any(lo <= s and s + dataset.block_months <= hi for lo, hi in segments)

    def test_straddling_blocks_dropped_from_both_sides(self, dataset):
        # 4 boundaries strictly inside the panel; L-1 = 5 straddling starts each.
        assert dataset.n_dropped_straddling == 3 * (dataset.block_months - 1)
        all_kept = np.concatenate([dataset.train_index, *dataset.fold_indices])
        assert np.unique(all_kept).size == all_kept.size

    def test_block_belongs_to_fold_containing_its_start(self, dataset):
        val = dataset.validation_start_month
        assert all(dataset.starts[r] < val for r in dataset.train_index)
        assert all(dataset.starts[r] >= val for r in np.concatenate(dataset.fold_indices))


class TestStandardization:
    def test_constants_are_train_only(self, source, climate):
        """WP2.5-style leakage test: perturbing validation-span data changes nothing."""
        base = bd.build_dataset(source, climate, validation_start_date=VAL_DATE)
        poisoned_values = source.values.copy()
        poisoned_values[181:, :] *= 1.7  # validation span only
        import dataclasses

        poisoned = dataclasses.replace(source, values=poisoned_values)
        after = bd.build_dataset(poisoned, climate, validation_start_date=VAL_DATE)
        np.testing.assert_array_equal(base.standardization.x_mean, after.standardization.x_mean)
        np.testing.assert_array_equal(base.standardization.x_std, after.standardization.x_std)
        np.testing.assert_array_equal(base.standardization.c_mean, after.standardization.c_mean)
        np.testing.assert_array_equal(base.standardization.c_std, after.standardization.c_std)

    def test_round_trips_and_serialization(self, dataset):
        st = dataset.standardization
        x = dataset.x[:5]
        np.testing.assert_allclose(st.destandardize_x(st.standardize_x(x)), x, rtol=1e-12)
        again = bd.Standardization.from_dict(st.to_dict())
        np.testing.assert_array_equal(again.x_mean, st.x_mean)
        c = dataset.cond[:5]
        s = st.standardize_cond(c)
        np.testing.assert_array_equal(s[:, :6], c[:, :6])  # one-hot untouched


class TestEffectiveSamples:
    def test_epoch_has_no_adjacent_overlap(self, dataset):
        rng = np.random.Generator(np.random.PCG64(3))
        rows = bd.epoch_starts(dataset, rng)
        starts = np.sort(dataset.starts[rows])
        assert np.all(np.diff(starts) >= dataset.block_months)

    def test_epoch_size_is_effective_not_raw(self, dataset):
        rng = np.random.Generator(np.random.PCG64(3))
        rows = bd.epoch_starts(dataset, rng)
        assert rows.size <= dataset.n_train_effective + 1
        assert dataset.n_train_raw > 2 * rows.size  # raw counts overstate massively

    def test_deterministic_given_seed(self, dataset):
        a = bd.epoch_starts(dataset, np.random.Generator(np.random.PCG64(9)))
        b = bd.epoch_starts(dataset, np.random.Generator(np.random.PCG64(9)))
        np.testing.assert_array_equal(a, b)
