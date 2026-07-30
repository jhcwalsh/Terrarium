"""WP2.11 severe test, L2: the segmented spell rule.

The excluded decade splits the contiguous label history into two observation
SEGMENTS. Each segment is treated exactly as the primary fit treats the whole
sample -- first spell dropped (left-truncated), last spell right-censored -- so
a spell that straddles a boundary is handled by machinery that already exists
rather than by a new rule, and no transition is ever invented across the gap.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen import severe
from ah.gen.regimes import fit as rfit
from ah.gen.regimes import semimarkov as sm


def _labels(runs: list[tuple[int, int]]) -> np.ndarray:
    """Build a label sequence from ``(state, duration)`` runs."""
    return np.concatenate([np.full(d, s, dtype=np.int64) for s, d in runs])


class TestSegmentedSpells:
    def test_one_segment_reproduces_the_primary_convention(self):
        labels = _labels([(0, 5), (1, 7), (2, 3), (0, 4)])
        spells = rfit.segmented_spell_observations(labels, [(0, labels.size)])
        # first spell dropped, three sojourns, the last censored
        assert spells.soj_state.tolist() == [1, 2, 0]
        assert spells.soj_dur.tolist() == [7, 3, 4]
        assert spells.soj_censored.tolist() == [False, False, True]
        # three interior boundaries -> three transitions
        assert spells.trans_from.tolist() == [0, 1, 2]
        assert spells.trans_to.tolist() == [1, 2, 0]

    def test_two_segments_each_get_their_own_truncation_and_censoring(self):
        # segment A: [0,10) states 0,1 ; segment B: [20,32) states 2,3,0
        labels = _labels([(0, 5), (1, 5), (4, 10), (2, 4), (3, 4), (0, 4)])
        segments = [(0, 10), (20, 32)]
        spells = rfit.segmented_spell_observations(labels, segments)
        # A contributes only spell 1 (censored at the gap); B drops its first
        # spell and censors its last
        assert spells.soj_state.tolist() == [1, 3, 0]
        assert spells.soj_dur.tolist() == [5, 4, 4]
        assert spells.soj_censored.tolist() == [True, False, True]

    def test_no_transition_is_invented_across_the_gap(self):
        labels = _labels([(0, 5), (1, 5), (4, 10), (2, 4), (3, 4), (0, 4)])
        spells = rfit.segmented_spell_observations(labels, [(0, 10), (20, 32)])
        pairs = list(zip(spells.trans_from.tolist(), spells.trans_to.tolist(), strict=True))
        # within A: 0->1 ; within B: 2->3, 3->0. Never 1->2 (the straddle).
        assert pairs == [(0, 1), (2, 3), (3, 0)]

    def test_a_segment_with_a_single_spell_contributes_nothing(self):
        """A lone spell is BOTH left-truncated and right-censored: its start is
        unobserved and its end is unobserved, so "duration >= d from an unknown
        start" carries no usable information and the segment is dropped whole."""
        labels = _labels([(0, 8), (4, 10), (1, 6)])
        spells = rfit.segmented_spell_observations(labels, [(0, 8), (18, 24)])
        assert spells.soj_state.size == 0
        assert spells.trans_from.size == 0

    def test_segment_indices_are_absolute_so_covariate_lookup_stays_correct(self):
        labels = _labels([(0, 5), (1, 5), (4, 10), (2, 4), (3, 4)])
        spells = rfit.segmented_spell_observations(labels, [(0, 10), (20, 28)])
        # z rows are looked up at ABSOLUTE month indices; the second segment's
        # first retained sojourn starts at absolute month 24, not 4
        assert spells.soj_start.tolist() == [5, 24]

    def test_an_empty_segment_list_is_refused(self):
        with pytest.raises(sm.RegimesError):
            rfit.segmented_spell_observations(_labels([(0, 4)]), [])


class TestExclusionCostAccounting:
    def test_spells_lost_are_counted_and_attributed_by_regime(self):
        labels = _labels([(0, 5), (1, 5), (4, 10), (2, 4), (3, 4)])
        full = rfit.segmented_spell_observations(labels, [(0, labels.size)])
        cut = rfit.segmented_spell_observations(labels, [(0, 10), (20, 28)])
        assert cut.soj_state.size < full.soj_state.size
        assert cut.trans_from.size < full.trans_from.size

    def test_a_regime_seen_only_inside_the_excluded_span_disappears(self):
        """The 1970s carry the STAG evidence; the test must SHOW an empty stratum."""
        # state 4 (STAG's slot) lives only inside the gap
        labels = _labels([(0, 5), (1, 5), (4, 6), (2, 5), (3, 5)])
        full = rfit.segmented_spell_observations(labels, [(0, labels.size)])
        cut = rfit.segmented_spell_observations(labels, [(0, 10), (16, 26)])
        assert 4 in set(full.soj_state.tolist())
        assert 4 not in set(cut.soj_state.tolist())
        # and no transition INTO or OUT OF it survives either
        assert 4 not in set(cut.trans_from.tolist()) | set(cut.trans_to.tolist())


class TestSegmentsComeFromTheSharedSpan:
    def test_the_1970s_split_a_1926_2020_history_in_two(self):
        import pandas as pd

        dates = pd.date_range("1926-01-01", "2021-01-01", freq="MS", inclusive="left")
        segs = severe.segments_outside(dates, severe.SEVERE_TEST_EXCLUSION)
        assert len(segs) == 2
        assert dates[segs[0][1] - 1] == pd.Timestamp("1969-12-01")
        assert dates[segs[1][0]] == pd.Timestamp("1980-01-01")


# --------------------------------------------------------------------------- #
# end-to-end on the WP2.6 mini-world, with the exclusion span moved INSIDE it
# --------------------------------------------------------------------------- #


class TestBuildFitDataUnderAnExclusion:
    """`build_fit_data` end to end: index arithmetic, re-derived normalization
    constants, and the cost record. The mini-world spans 1988-2016, so the span
    used here is a stand-in placed inside it; the sealed 1970s span is exercised
    against the real panel by the run itself."""

    SPAN = severe.ExclusionSpan(start="2000-01-01", end_exclusive="2010-01-01")

    def _case(self, tmp_path):
        from test_regimes_fit import _access, _mini_climate_artifact, _mini_config, _mini_series

        return _access(_mini_series()), _mini_config(), _mini_climate_artifact(tmp_path)

    def test_it_builds_and_records_two_segments(self, tmp_path):
        access, config, climate = self._case(tmp_path)
        fd = rfit.build_fit_data(access, config, climate, exclude=self.SPAN)
        assert fd.exclusion == self.SPAN
        assert len(fd.segments) == 2
        assert fd.exclusion_cost["months_excluded"] == 120

    def test_no_retained_month_is_inside_the_span(self, tmp_path):
        access, config, climate = self._case(tmp_path)
        fd = rfit.build_fit_data(access, config, climate, exclude=self.SPAN)
        for lo, hi in fd.segments:
            assert not self.SPAN.contains(fd.dates[lo:hi]).any()

    def test_covariate_standardization_is_rederived_on_retained_months(self, tmp_path):
        access, config, climate = self._case(tmp_path)
        base = rfit.build_fit_data(access, config, climate)
        cut = rfit.build_fit_data(access, config, climate, exclude=self.SPAN)
        assert not np.allclose(base.cov_mean[:3], cut.cov_mean[:3])
        assert cut.cov_mean[3] == 0.0 and cut.cov_sd[3] == 1.0  # the dummy stays 0/1

    def test_sojourns_and_transitions_shrink_and_are_counted(self, tmp_path):
        access, config, climate = self._case(tmp_path)
        base = rfit.build_fit_data(access, config, climate)
        cut = rfit.build_fit_data(access, config, climate, exclude=self.SPAN)
        assert cut.spells.soj_state.size < base.spells.soj_state.size
        c = cut.exclusion_cost
        assert c["sojourns_retained"] == int(cut.spells.soj_state.size)
        assert c["transitions_retained"] == int(cut.spells.trans_from.size)
        assert c["sojourns_full_sample"] == int(base.spells.soj_state.size)

    def test_more_than_one_spell_is_right_censored(self, tmp_path):
        """Two segments -> two censored terms, not the single sample-end one."""
        access, config, climate = self._case(tmp_path)
        base = rfit.build_fit_data(access, config, climate)
        cut = rfit.build_fit_data(access, config, climate, exclude=self.SPAN)
        # the primary fit censors exactly one spell (the sample end); two
        # segments censor one each
        assert int(base.spells.soj_censored.sum()) == 1
        assert int(cut.spells.soj_censored.sum()) == 2

    def test_covariate_rows_line_up_with_absolute_month_indices(self, tmp_path):
        access, config, climate = self._case(tmp_path)
        cut = rfit.build_fit_data(access, config, climate, exclude=self.SPAN)
        for row, start in zip(cut.spells.soj_z, cut.spells.soj_start, strict=True):
            np.testing.assert_allclose(row, cut.z[int(start)])

    def test_the_primary_path_is_untouched(self, tmp_path):
        access, config, climate = self._case(tmp_path)
        a = rfit.build_fit_data(access, config, climate)
        b = rfit.build_fit_data(access, config, climate, exclude=None)
        np.testing.assert_array_equal(a.labels, b.labels)
        np.testing.assert_allclose(a.cov_mean, b.cov_mean)
        np.testing.assert_array_equal(a.spells.soj_dur, b.spells.soj_dur)
        assert a.exclusion is None and a.segments == ((0, len(a.dates)),)
