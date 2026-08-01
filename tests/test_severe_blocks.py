"""WP2.11 severe test, L3: the block-window drop rule.

Every training block whose WINDOW intersects the excluded decade goes -- not
merely those that START inside it -- and the train-only standardization
constants are re-derived on the reduced sample, because they are part of the
fit and not of the architecture.

The rule is exercised here on a SYNTHETIC panel that straddles the 1970s. It is
vacuous on the real campaign panel, whose span is the sealed
``block_draw_span`` 1990-01..2020-12; that fact is pinned by
:class:`TestTheRealPanelDoesNotReachTheDecade` because it is the single most
consequential fact about this leg of the severe test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.gen import bootstrap as bs
from ah.gen import severe
from ah.gen.blocks import data as bd
from ah.gen.joinery.waypoints import JoineryError
from joinery_common import make_climate_artifact, make_source


def _straddling_case(tmp_path):
    """A 1960-01-launched panel (300 months -> 1984-12) plus a covering climate."""
    source = make_source(300, start="1960-01-01")
    climate = make_climate_artifact(tmp_path, start="1959-01-01", t_months=360)
    return source, climate


class TestBlockWindowDropRule:
    def test_no_retained_block_touches_the_excluded_decade(self, tmp_path):
        source, climate = _straddling_case(tmp_path)
        ds = bd.build_dataset(
            source,
            climate,
            validation_start_date="1980-01-01",
            exclude=severe.SEVERE_TEST_EXCLUSION,
        )
        kept = np.concatenate([ds.train_index, *ds.fold_indices])
        starts = source.dates[ds.starts[kept]]
        touching = severe.SEVERE_TEST_EXCLUSION.window_intersects(starts, ds.block_months)
        assert not touching.any()

    def test_blocks_merely_ENDING_in_the_decade_are_dropped_too(self, tmp_path):
        source, climate = _straddling_case(tmp_path)
        ds = bd.build_dataset(
            source,
            climate,
            validation_start_date="1980-01-01",
            exclude=severe.SEVERE_TEST_EXCLUSION,
        )
        kept = set(np.concatenate([ds.train_index, *ds.fold_indices]).tolist())
        # a block starting 1969-09 with L=6 runs to 1970-02: it starts OUTSIDE the
        # decade but ends inside it, and must not survive
        row = int(np.flatnonzero(source.dates[ds.starts] == pd.Timestamp("1969-09-01"))[0])
        assert row not in kept

    def test_the_exclusion_actually_costs_blocks_and_the_count_is_recorded(self, tmp_path):
        source, climate = _straddling_case(tmp_path)
        base = bd.build_dataset(source, climate, validation_start_date="1980-01-01")
        cut = bd.build_dataset(
            source,
            climate,
            validation_start_date="1980-01-01",
            exclude=severe.SEVERE_TEST_EXCLUSION,
        )
        assert cut.n_dropped_excluded > 0
        base_kept = base.train_index.size + sum(f.size for f in base.fold_indices)
        cut_kept = cut.train_index.size + sum(f.size for f in cut.fold_indices)
        assert cut_kept == base_kept - cut.n_dropped_excluded

    def test_standardization_is_rederived_on_the_reduced_sample(self, tmp_path):
        source, climate = _straddling_case(tmp_path)
        base = bd.build_dataset(source, climate, validation_start_date="1980-01-01")
        cut = bd.build_dataset(
            source,
            climate,
            validation_start_date="1980-01-01",
            exclude=severe.SEVERE_TEST_EXCLUSION,
        )
        assert not np.allclose(base.standardization.x_mean, cut.standardization.x_mean)
        # and it is genuinely the reduced train set's own moments
        expected = cut.x[cut.train_index].mean(axis=(0, 1))
        np.testing.assert_allclose(cut.standardization.x_mean, expected)

    def test_the_block_aware_fold_structure_survives(self, tmp_path):
        source, climate = _straddling_case(tmp_path)
        cut = bd.build_dataset(
            source,
            climate,
            validation_start_date="1980-01-01",
            n_folds=3,
            exclude=severe.SEVERE_TEST_EXCLUSION,
        )
        assert len(cut.fold_indices) == 3
        # folds and train remain disjoint
        seen = np.concatenate([cut.train_index, *cut.fold_indices])
        assert seen.size == np.unique(seen).size
        # every train block still ends before the validation boundary
        assert (cut.starts[cut.train_index] + cut.block_months).max() <= (
            cut.validation_start_month
        )

    def test_the_primary_path_is_unchanged(self, tmp_path):
        source, climate = _straddling_case(tmp_path)
        a = bd.build_dataset(source, climate, validation_start_date="1980-01-01")
        b = bd.build_dataset(source, climate, validation_start_date="1980-01-01", exclude=None)
        np.testing.assert_array_equal(a.train_index, b.train_index)
        np.testing.assert_array_equal(a.standardization.x_mean, b.standardization.x_mean)
        assert a.n_dropped_excluded == 0

    def test_an_exclusion_that_empties_the_train_split_is_refused(self, tmp_path):
        # 1971-01 .. 1978-12: every month of the panel is inside the excluded span
        source = make_source(96, start="1971-01-01")
        climate = make_climate_artifact(tmp_path, start="1970-01-01", t_months=360)
        with pytest.raises(JoineryError):
            bd.build_dataset(
                source,
                climate,
                validation_start_date="1977-01-01",
                exclude=severe.SEVERE_TEST_EXCLUSION,
            )


class TestTheRealPanelDoesNotReachTheDecade:
    """The sealed block_draw_span is 1990-2020: the L3 leg of the severe test is
    STRUCTURALLY VACUOUS, for the same reason the sealed benchmark_exception says
    bootstrap-v1 cannot run this test at all. Pinned so it cannot be discovered
    late or glossed over."""

    def test_the_sealed_block_draw_span_misses_the_excluded_decade_entirely(self):
        # one month past the sealed inclusive end == the exclusive boundary
        assert not severe.SEVERE_TEST_EXCLUSION.intersects(bs.BLOCK_DRAW_SPAN_START, "2021-01-01")

    def test_no_block_of_the_sealed_span_can_intersect_it(self):
        starts = pd.date_range(bs.BLOCK_DRAW_SPAN_START, bs.BLOCK_DRAW_SPAN_END, freq="MS")
        assert not severe.SEVERE_TEST_EXCLUSION.window_intersects(starts, months=6).any()
