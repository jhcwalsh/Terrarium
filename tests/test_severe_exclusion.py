"""WP2.11 severe test: the fitting-sample exclusion, per layer.

The sealed ``severe_test_protocol`` says "exclude the 1970s (1970-01-01 to
1979-12-31 inclusive) from the fitting sample". Three layers read the fitting
sample in three different shapes, so "exclude" has to mean three concrete
things. This module pins all three, plus the one span constant they share.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.gen import severe
from ah.gen.climate import fit as cf
from ah.gen.climate import model as cm
from ah.splits import DataAccess

# --------------------------------------------------------------------------- #
# a synthetic L1 panel that STRADDLES the excluded decade (1960-01 .. 2020-12)
# --------------------------------------------------------------------------- #

_L1_START = "1960-01-01"
_L1_END = "2021-01-01"  # exclusive


def _frame(dates, values) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.DatetimeIndex(dates), "value": np.asarray(values, float)})


def _climate_case() -> tuple[DataAccess, cm.ClimateConfig]:
    m = pd.date_range(_L1_START, _L1_END, freq="MS", inclusive="left")
    t = np.arange(len(m), dtype=float)
    series = {
        "fred.CPI": _frame(m, 100.0 * np.exp(0.03 * t / 12.0)),
        "fred.FEDFUNDS": _frame(m, 4.0 + 1.5 * np.sin(t / 29.0)),
        "shiller.cape": _frame(m, 20.0 + 4.0 * np.sin(t / 53.0)),
        "fred.USREC": _frame(m, ((t % 72) < 9).astype(float)),
    }
    q = pd.date_range(_L1_START, _L1_END, freq="QS", inclusive="left")
    series["bis.credit_gap_us"] = _frame(q, 5.0 * np.sin(np.arange(len(q)) / 9.0))

    years = list(range(1959, 2021))
    ydates = pd.DatetimeIndex([f"{y}-01-01" for y in years])
    n = np.arange(len(years), dtype=float)
    series |= {
        "jst.usa_cpi": _frame(ydates, 100.0 * np.exp(0.03 * n)),
        "jst.usa_stir": _frame(ydates, 4.0 + 0.5 * np.sin(n)),
        "jst.usa_ltrate": _frame(ydates, 5.0 + 0.4 * np.cos(n)),
        "jst.usa_gdp": _frame(ydates, 9000.0 * np.exp(0.05 * n)),
        "jst.usa_tloans": _frame(ydates, 6000.0 * np.exp(0.06 * n)),
        "jst.usa_eq_tr": _frame(ydates, 0.07 + 0.05 * np.sin(n / 2.0)),
    }

    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in series:
            raise KeyError(series_id)
        return series[series_id]

    config = cm.load_config().model_copy(
        update={"span": cm.SpanSettings(start=_L1_START, end=_L1_END)}, deep=True
    )
    return DataAccess(reader), config


class TestExclusionSpan:
    def test_the_sealed_decade_is_the_default_span(self):
        span = severe.SEVERE_TEST_EXCLUSION
        assert span.start == "1970-01-01"
        # inclusive end 1979-12-31 == exclusive month boundary 1980-01-01
        assert span.end_exclusive == "1980-01-01"
        assert span.label == "1970-01-01..1979-12-31"

    def test_month_membership_is_by_date_not_by_index(self):
        dates = pd.date_range("1968-01-01", "1982-01-01", freq="MS", inclusive="left")
        inside = severe.SEVERE_TEST_EXCLUSION.contains(dates)
        assert inside.sum() == 120
        assert not inside[dates.get_loc(pd.Timestamp("1969-12-01"))]
        assert inside[dates.get_loc(pd.Timestamp("1970-01-01"))]
        assert inside[dates.get_loc(pd.Timestamp("1979-12-01"))]
        assert not inside[dates.get_loc(pd.Timestamp("1980-01-01"))]

    def test_mid_year_annual_placements_are_caught(self):
        """JST annual channels land in July; excluding by date must catch them."""
        julys = pd.DatetimeIndex([pd.Timestamp(year=y, month=7, day=1) for y in range(1965, 1985)])
        inside = severe.SEVERE_TEST_EXCLUSION.contains(julys)
        assert [int(ts.year) for ts in julys[inside]] == list(range(1970, 1980))

    def test_december_placements_are_caught(self):
        decs = pd.DatetimeIndex([pd.Timestamp(year=y, month=12, day=1) for y in range(1965, 1985)])
        inside = severe.SEVERE_TEST_EXCLUSION.contains(decs)
        assert [int(ts.year) for ts in decs[inside]] == list(range(1970, 1980))

    def test_window_intersection_is_any_overlap_not_containment(self):
        span = severe.SEVERE_TEST_EXCLUSION
        # a window ENDING inside the decade intersects it
        assert span.intersects("1968-01-01", "1971-01-01")
        # a window STARTING inside it intersects it
        assert span.intersects("1979-01-01", "1985-01-01")
        # a window straddling it entirely intersects it
        assert span.intersects("1960-01-01", "1990-01-01")
        # touching the boundary from outside does not
        assert not span.intersects("1960-01-01", "1970-01-01")
        assert not span.intersects("1980-01-01", "1990-01-01")

    def test_block_window_intersection_drops_straddlers_not_just_starters(self):
        """L3's rule: a block whose WINDOW touches the decade goes, not only one
        whose START is inside it."""
        span = severe.SEVERE_TEST_EXCLUSION
        starts = pd.DatetimeIndex(["1968-01-01", "1969-06-01", "1975-01-01", "1980-01-01"])
        drop = span.window_intersects(starts, months=24)
        # 1968-01 + 24m ends 1969-12 -> no overlap; 1969-06 + 24m reaches 1971-05 -> overlap
        assert list(drop) == [False, True, True, False]


class TestSegmentsOutsideExclusion:
    def test_a_span_straddling_the_decade_splits_in_two(self):
        dates = pd.date_range("1960-01-01", "1990-01-01", freq="MS", inclusive="left")
        segs = severe.segments_outside(dates, severe.SEVERE_TEST_EXCLUSION)
        assert len(segs) == 2
        (a0, a1), (b0, b1) = segs
        assert dates[a0] == pd.Timestamp("1960-01-01")
        assert dates[a1 - 1] == pd.Timestamp("1969-12-01")
        assert dates[b0] == pd.Timestamp("1980-01-01")
        assert dates[b1 - 1] == pd.Timestamp("1989-12-01")

    def test_a_span_entirely_outside_stays_one_segment(self):
        dates = pd.date_range("1990-01-01", "2021-01-01", freq="MS", inclusive="left")
        segs = severe.segments_outside(dates, severe.SEVERE_TEST_EXCLUSION)
        assert segs == [(0, len(dates))]

    def test_a_span_entirely_inside_yields_no_segment(self):
        dates = pd.date_range("1971-01-01", "1975-01-01", freq="MS", inclusive="left")
        assert severe.segments_outside(dates, severe.SEVERE_TEST_EXCLUSION) == []

    def test_no_excluded_month_survives_in_any_segment(self):
        dates = pd.date_range("1955-01-01", "2000-01-01", freq="MS", inclusive="left")
        segs = severe.segments_outside(dates, severe.SEVERE_TEST_EXCLUSION)
        kept = np.concatenate([np.arange(lo, hi) for lo, hi in segs])
        assert not severe.SEVERE_TEST_EXCLUSION.contains(dates[kept]).any()
        assert len(kept) == len(dates) - 120


class TestExclusionIsOptIn:
    """Nothing may change for the primary (full-sample) path."""

    def test_none_exclusion_is_the_identity(self):
        dates = pd.date_range("1960-01-01", "1990-01-01", freq="MS", inclusive="left")
        assert severe.segments_outside(dates, None) == [(0, len(dates))]

    def test_contains_is_all_false_for_no_exclusion(self):
        dates = pd.date_range("1960-01-01", "1990-01-01", freq="MS", inclusive="left")
        assert not severe.contains_or_false(None, dates).any()


class TestClimateExclusionMasksRatherThanDeletes:
    """L1: the excluded decade leaves the mask, not the grid."""

    def test_grid_is_unchanged_and_only_the_mask_moves(self):
        access, config = _climate_case()
        base = cf.build_fit_data(access, config)
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)

        # SAME monthly grid -- the state must still evolve through the gap
        assert list(cut.dates) == list(base.dates)
        assert cut.kf.y.shape == base.kf.y.shape
        assert cut.kf.mask.shape == base.kf.mask.shape

    def test_every_excluded_month_is_unmasked_on_every_channel(self):
        access, config = _climate_case()
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)
        inside = severe.SEVERE_TEST_EXCLUSION.contains(cut.dates)
        assert inside.any()
        assert cut.kf.mask[inside].sum() == 0.0

    def test_no_month_outside_the_decade_loses_an_observation(self):
        access, config = _climate_case()
        base = cf.build_fit_data(access, config)
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)
        outside = ~severe.SEVERE_TEST_EXCLUSION.contains(cut.dates)
        np.testing.assert_array_equal(cut.kf.mask[outside], base.kf.mask[outside])

    def test_the_exclusion_actually_costs_observations(self):
        access, config = _climate_case()
        base = cf.build_fit_data(access, config)
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)
        assert cut.kf.mask.sum() < base.kf.mask.sum()
        assert cut.excluded_observations > 0
        assert cut.excluded_observations == int(base.kf.mask.sum() - cut.kf.mask.sum())

    def test_annual_july_channels_are_excluded_by_date(self):
        """a_infl lands in July; a date rule must clear exactly the ten 1970s Julys."""
        access, config = _climate_case()
        base = cf.build_fit_data(access, config)
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)
        j = cm.CHANNELS.index("a_infl")
        lost = int(base.kf.mask[:, j].sum() - cut.kf.mask[:, j].sum())
        assert lost == 10

    def test_cape_demean_is_rederived_on_the_reduced_sample(self):
        """The demean constant is part of the FIT, so it must not see the decade."""
        access, config = _climate_case()
        base = cf.build_fit_data(access, config)
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)
        assert cut.cape_demean_n == base.cape_demean_n - 120
        assert cut.cape_demean_mean != base.cape_demean_mean

    def test_train_only_normalization_guard_accepts_the_matching_exclusion(self):
        access, config = _climate_case()
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)
        cf.assert_train_only_normalization(
            cut, access, config, exclude=severe.SEVERE_TEST_EXCLUSION
        )

    def test_a_full_sample_demean_under_an_exclusion_is_refused(self):
        """A severe-test fit carrying the PRIMARY demean constant is leakage."""
        import dataclasses

        access, config = _climate_case()
        base = cf.build_fit_data(access, config)
        cut = cf.build_fit_data(access, config, exclude=severe.SEVERE_TEST_EXCLUSION)
        contaminated = dataclasses.replace(
            cut,
            cape_demean_mean=base.cape_demean_mean,
            cape_demean_n=base.cape_demean_n,
        )
        with pytest.raises(cf.NormalizationLeakageError):
            cf.assert_train_only_normalization(
                contaminated, access, config, exclude=severe.SEVERE_TEST_EXCLUSION
            )

    def test_the_primary_path_is_bit_identical_to_before(self):
        """exclude=None must change nothing at all."""
        access, config = _climate_case()
        a = cf.build_fit_data(access, config)
        b = cf.build_fit_data(access, config, exclude=None)
        np.testing.assert_array_equal(a.kf.y, b.kf.y)
        np.testing.assert_array_equal(a.kf.mask, b.kf.mask)
        assert a.cape_demean_mean == b.cape_demean_mean
        assert a.excluded_observations == 0


class TestSpanValidation:
    def test_an_inverted_span_is_refused(self):
        with pytest.raises(ValueError):
            severe.ExclusionSpan(start="1980-01-01", end_exclusive="1970-01-01")

    def test_an_empty_span_is_refused(self):
        with pytest.raises(ValueError):
            severe.ExclusionSpan(start="1970-01-01", end_exclusive="1970-01-01")
