"""Campaign R1 Track A: the twin over observed history, prior vs measured.

The exhibit lives outside both pre-registration locks; these tests pin its
guard rails — the loadings toggle, the hard failure on missing data, and the
report's NOT-ADOPTED / named-exclusion text.
"""

from __future__ import annotations

import pytest

from ah.port import campaign_exhibit as ce


def test_windows_are_the_specd_four():
    assert set(ce.WINDOWS) == {"full_span", "gfc", "covid", "y2022"}
    assert ce.WINDOWS["y2022"] == ("2021-12-01", "2023-12-31")
    assert ce.CAMPAIGN_VINTAGE == "2026-08-07.5"


def test_load_regressors_refuses_a_missing_series():
    class FakeCatalog:
        def read_observations(self, vintage, sid):
            raise KeyError(sid)

    with pytest.raises(SystemExit, match="equity_mkt"):
        ce.load_regressors(FakeCatalog(), "2026-08-07.5")
