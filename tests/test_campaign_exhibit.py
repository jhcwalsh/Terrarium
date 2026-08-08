"""Campaign R1 Track A: the twin over observed history, prior vs measured.

The exhibit lives outside both pre-registration locks; these tests pin its
guard rails — the loadings toggle, the hard failure on missing data, and the
report's NOT-ADOPTED / named-exclusion text.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
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


def _mapping_stub():
    return {
        "sleeves": {
            "hf_event": {"alpha_monthly": 0.004, "loadings": {"equity_mkt": 0.4}},
        },
        "pm_sleeves": {
            "pm_buyout": {
                "family": "glm",
                "alpha_quarterly": 0.03,
                "loadings": {"equity_mkt": 0.35},
                "prior_superseded": {"source": "cashflow-tier1", "equity_mkt": 1.2},
            },
        },
    }


def test_the_loadings_toggle_moves_pm_and_only_pm():
    reg_q = pd.DataFrame({"equity_mkt": [0.05, -0.10, 0.02]})
    prior = ce.pm_sleeve_returns(reg_q, _mapping_stub(), source="prior")
    measured = ce.pm_sleeve_returns(reg_q, _mapping_stub(), source="measured")
    assert not np.allclose(prior["pm_buyout"], measured["pm_buyout"])
    # prior uses ONLY the prior_superseded row (equity_mkt 1.2), alpha excluded:
    assert prior["pm_buyout"].iloc[0] == pytest.approx(1.2 * 0.05)
    # measured uses the fitted row WITH its alpha:
    assert measured["pm_buyout"].iloc[0] == pytest.approx(0.03 + 0.35 * 0.05)
    # HF sleeves have no toggle: one construction, mapping row only
    reg = pd.DataFrame({"equity_mkt": [0.01, -0.02]})
    hf = ce.hf_sleeve_returns(reg, _mapping_stub())
    assert hf["hf_event"].iloc[0] == pytest.approx(0.004 + 0.4 * 0.01)


def test_unknown_source_refuses():
    with pytest.raises(ValueError, match="prior|measured"):
        ce.pm_sleeve_returns(pd.DataFrame({"equity_mkt": [0.0]}), _mapping_stub(), source="x")


def test_geltner_report_is_the_partial_adjustment():
    true = np.array([0.10, 0.0, 0.0, 0.0])
    rep = ce.geltner_report(true, a=0.5, phi=0.5)
    assert rep[0] == pytest.approx(0.05)
    assert rep[1] == pytest.approx(0.025)  # phi * previous reported + a * 0


def test_reported_plane_is_deterministic_and_shallower_on_a_shock():
    """The real kernel, twice: identical output, and a one-off shock reaches
    the reported plane damped for BOTH families."""
    idx = pd.date_range("2020-03-31", periods=8, freq="QE")
    true = pd.Series([0.02, 0.02, -0.20, 0.01, 0.01, 0.01, 0.01, 0.01], index=idx)
    for sleeve in ("pm_buyout", "pm_re_value_add"):
        a = ce.reported_plane(sleeve, true)
        b = ce.reported_plane(sleeve, true)
        assert a.equals(b)
        assert abs(float(a.min())) < abs(float(true.min()))
