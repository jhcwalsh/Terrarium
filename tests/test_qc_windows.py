"""D-QC-1 acceptance criterion 1: the quarterly window grid."""

from __future__ import annotations

import pytest

from ah.core.institution import decision_months, quarterly_decision_months


class TestQuarterlyGrid:
    def test_decade_grid_is_the_39_quarter_closes(self):
        got = quarterly_decision_months(120)
        assert got == list(range(2, 117, 3))
        assert len(got) == 39

    @pytest.mark.parametrize("nm", [12, 60, 118, 120, 240])
    def test_final_quarter_close_is_never_a_window(self, nm):
        closes = [m for m in range(nm) if m % 3 == 2]
        got = quarterly_decision_months(nm)
        assert got == closes[:-1]
        assert closes[-1] not in got

    @pytest.mark.parametrize("nm", [0, 1, 2, 3, 5])
    def test_horizons_too_short_for_a_meaningful_window_are_empty(self, nm):
        # one quarter-close or none: that close is the final tick, so no window
        assert quarterly_decision_months(nm) == []

    def test_year_closes_are_a_subset_and_are_the_annual_grid(self):
        q = quarterly_decision_months(120)
        assert [m for m in q if m % 12 == 11] == decision_months(120)

    def test_every_window_has_a_full_following_quarter(self):
        # criterion 2's precondition: window m governs months m+1..m+3,
        # which must exist inside the horizon
        for nm in (120, 240):
            assert all(m + 3 < nm for m in quarterly_decision_months(nm))

    def test_annual_grid_is_untouched(self):
        # the toy/vintage grid must not have moved with this release
        assert decision_months(120) == [12 * y - 1 for y in range(1, 10)]
