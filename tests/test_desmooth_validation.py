"""The de-smoothing validation exhibit: does it catch a no-op, and does it
refuse to present a comparator ratio as a target? Offline, synthetic."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data.desmooth_validation import (
    COMPARATORS,
    SleeveCheck,
    acf1,
    check_sleeve,
    render_markdown,
    to_quarterly,
)


def _quarters(n: int) -> pd.PeriodIndex:
    return pd.period_range("2011Q2", periods=n, freq="Q")


def _smoothed(n: int = 80, phi: float = 0.6, seed: int = 0) -> pd.Series:
    """An appraisal-style series: AR(1)-smoothed, so a de-smoother has work."""
    rng = np.random.default_rng(seed)
    true = rng.normal(0.02, 0.05, n)
    obs = np.empty(n)
    obs[0] = true[0]
    for i in range(1, n):
        obs[i] = phi * obs[i - 1] + (1.0 - phi) * true[i]
    return pd.Series(obs, index=_quarters(n))


def test_a_working_desmoother_recovers_volatility():
    check = check_sleeve("x.smoothed_q", _smoothed(), family="geltner")
    assert check.sigma_ratio > 1.05  # risk came back
    assert not check.is_noop
    assert check.acf1_desmoothed < check.acf1_reported  # smoothing removed


def test_a_noop_is_detected_and_named():
    """Negative autocorrelation gives both operators nothing to key on, so
    truth == obs. The exhibit must say so rather than print ratio 1.00."""
    alternating = pd.Series([0.05, -0.05] * 30, index=_quarters(60))
    check = check_sleeve("x.noop_q", alternating, family="geltner")
    assert check.acf1_reported < 0
    assert check.sigma_ratio == pytest.approx(1.0, abs=1e-9)
    assert check.is_noop
    md = render_markdown([check], vintage="v", as_of="2026-08-08")
    assert "## No-ops" in md
    assert "x.noop_q" in md.split("## No-ops")[1]
    assert "nothing was recovered" in md.lower() or "nothing of the shape" in md.lower()


def test_comparator_is_measured_on_shared_periods_only():
    reported = pd.Series([0.01, 0.02, -0.01, 0.03], index=_quarters(4))
    # comparator overlaps the last two quarters only, and is far more volatile
    comparator = pd.Series([0.20, -0.25], index=_quarters(4)[2:])
    check = check_sleeve(
        "x.rep_q", reported, family="glm", comparator=comparator, comparator_id="y.listed"
    )
    assert check.n_overlap == 2
    assert check.comparator_ratio is not None and check.comparator_ratio > 1.0
    # the reported leg is measured on the SAME quarters, not its full history
    assert check.sigma_reported == pytest.approx(float(np.std(np.array([-0.01, 0.03]), ddof=1)))


def test_no_comparator_means_no_ratio_not_a_zero():
    check = check_sleeve("x.rep_q", _smoothed(), family="glm")
    assert check.comparator is None
    assert check.sigma_comparator is None
    assert check.comparator_ratio is None
    assert "—" in render_markdown([check], vintage="v", as_of="2026-08-08")


def test_the_exhibit_refuses_to_call_a_comparator_ratio_a_target():
    """The leverage caveat is the difference between a useful bound and a
    number someone tunes an estimator toward; it must be in the document."""
    md = render_markdown(
        [
            SleeveCheck(
                series_id="x.rep_q",
                method="glm_ma",
                n_obs=60,
                sigma_reported=0.03,
                sigma_desmoothed=0.03,
                acf1_reported=-0.05,
                acf1_desmoothed=-0.05,
                comparator="y.listed",
                sigma_comparator=0.09,
                n_overlap=60,
            )
        ],
        vintage="v",
        as_of="2026-08-08",
    )
    assert "UPPER" in md and "never a target" in md
    assert "levered" in md.lower()
    assert "outside the pre-registration seal" in md


def test_to_quarterly_compounds_within_the_quarter():
    monthly = pd.Series(
        [0.01, 0.01, 0.01], index=pd.to_datetime(["2026-01-31", "2026-02-28", "2026-03-31"])
    )
    q = to_quarterly(monthly)
    assert len(q) == 1
    assert q.iloc[0] == pytest.approx(1.01**3 - 1.0)


def test_acf1_is_nan_when_undefined_rather_than_zero():
    assert np.isnan(acf1(np.array([1.0, 2.0])))
    assert np.isnan(acf1(np.full(10, 0.5)))  # flat series has no autocorrelation


def test_registered_comparators_are_real_series_ids():
    from ah.data.manifest import load_requirements

    reqs = load_requirements()
    for appraised, listed in COMPARATORS.items():
        assert appraised in reqs, f"{appraised} is not a registered series"
        assert listed in reqs, f"comparator {listed} is not a registered series"
