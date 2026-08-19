"""AM-2026-08-15-001, extended by AM-2026-08-18-001 (ER-14 close-out,
D-ER14-2, 2026-08-18): the v1.2 PM estimator's pure functions, plus the
extended-C1 / F5 tests that read the real written artifact.

Pure-function tests -- no catalog, no network, no RNG -- cover build_row,
loss_series (kept for when C2 lands), the v1.1 reproduction machinery, and
the two defect-reproduction regressions kept whole from the drop review. The
artifact-reading tests (C1 extension, F5a/b/c, the C2 deferral) run against
the REAL file written by ``uv run python scripts/estimate_sleeve_mappings_v1_2.py``
against the sealed campaign vintage -- this module does not run the script
itself; run it first (no network, deterministic, no RNG).

Two of the pure-function tests pin defects found reviewing the drop rather
than properties of a working design, and say so in their docstrings: the
``_to_quarterly`` gap test (the reimplementation fabricated 0.0% quarters)
and the naive half of the sum-beta test (the drop kept the assertion that
the fix works and dropped the one proving the defect was there to fix).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "estimate_v12", _ROOT / "scripts" / "estimate_sleeve_mappings_v1_2.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

OUT_PATH = _mod.OUT_PATH


def _idx(n: int) -> pd.DatetimeIndex:
    return pd.date_range("1990-03-31", periods=n, freq="QE")


#: A v1.1 row, shaped exactly as mappings/sleeve-mappings-v1.1.yaml writes them.
_V11_ROW = {
    "family": "glm",
    "n_quarters": 125,
    "route": "sum-beta(4)",
    "alpha_quarterly": 0.019441,
    "loadings": {
        "equity_mkt": 0.8362,
        "smb": 0.0,
        "hml": 0.0,
        "mom": 0.0,
        "d_level": 0.0,
        "d_slope": 0.0,
        "d_ig": -0.0279,
    },
    "residual_sigma_annual": 0.1225,
}


# ------------------------------------------------------------------- C2 form
# C2 is DEFERRED this release (ask A7, D-ER14-2); the machinery is kept
# whole -- unit-tested here -- for the day the CDLI export lands.


def test_loss_series_shape_and_floor():
    """Below s_bar the loss is exactly zero; above, linear in the excess,
    keyed to the spread as it stood LOSS_LAG_Q quarters earlier."""
    spread = pd.Series([1.0] * 8 + [3.0] * 8, index=_idx(16))
    out = _mod.loss_series(spread, theta=0.01, s_bar=1.5)
    assert float(out.iloc[0]) == 0.0
    assert float(out.iloc[-1]) == pytest.approx(0.015)
    first_nonzero = out[out > 0].index[0]
    assert first_nonzero == spread.index[8 + _mod.LOSS_LAG_Q]


def test_build_row_rebases_alpha_by_mean_loss_when_theta_is_supplied():
    """The note's SS4.1 rule, applied by the code rather than by the test:
    alpha_adj = alpha_v11 + mean(loss_q), so the sleeve's unconditional mean
    survives adoption and the term only redistributes across states. This
    path is exercised only when the caller explicitly supplies theta/s_bar
    (the future CDLI-adoption event); this release's own run does not."""
    row = _mod.build_row(
        "pm_direct_lending",
        _V11_ROW,
        r2=None,
        c_anchor=0.033,
        theta=0.0123,
        s_bar=1.4,
        mean_loss=0.0025,
        theta_source="theta-provenance.json",
    )
    assert row["alpha_v11"] == pytest.approx(0.019441)
    assert row["alpha_quarterly"] == pytest.approx(0.019441 + 0.0025)
    # mean(alpha_adj - loss) recovers the original alpha: the point of the rule
    assert row["alpha_quarterly"] - 0.0025 == pytest.approx(0.019441, abs=1e-9)
    assert row["credit_loss"]["lag_quarters"] == _mod.LOSS_LAG_Q
    assert row["credit_loss"]["theta"] == pytest.approx(0.0123)


def test_build_row_leaves_a_non_c1_non_c2_sleeve_alpha_untouched():
    """pm_vc carries neither term; adoption must not move its alpha at all."""
    row = _mod.build_row("pm_vc", _V11_ROW, r2=0.61, c_anchor=0.033)
    assert row["alpha_quarterly"] == _V11_ROW["alpha_quarterly"]
    assert "credit_loss" not in row
    assert "alpha_v11" not in row
    assert "inflation_passthrough" not in row


def test_build_row_omits_credit_loss_when_theta_is_not_supplied():
    """C2 deferred (ask A7, D-ER14-2, AM-2026-08-18-001): a loss sleeve built
    WITHOUT theta/s_bar (this release's own invocation) gets no credit_loss
    block and no error -- a clean deferral, not a crash.

    INVERTS the pre-D-ER14-2 behaviour: the AM-2026-08-15-001 drop raised
    ValueError here, back when C1 and C2 were declared as one adoption
    event. D-ER14-2 (ask A7) decoupled them so C1 could ship without
    waiting on the Cliffwater export; a loss sleeve is therefore
    legitimately built with no theta now, and that must not be an error."""
    row = _mod.build_row("pm_direct_lending", _V11_ROW, r2=None, c_anchor=0.033)
    assert "credit_loss" not in row
    assert "alpha_v11" not in row
    assert row["alpha_quarterly"] == _V11_ROW["alpha_quarterly"]


def test_build_row_refuses_theta_without_s_bar_or_vice_versa():
    """A partial pair is a programming error, not a deferred adoption."""
    with pytest.raises(ValueError, match="theta and s_bar must be supplied together"):
        _mod.build_row("pm_mezzanine", _V11_ROW, r2=None, c_anchor=0.033, theta=0.01)


# ------------------------------------------------------------------- C1 form


def test_build_row_writes_the_declared_c1_block_on_declared_sleeves_only():
    """The loading is applied to (trail - c_anchor), so the anchor has to reach
    the artifact -- a b_infl written without its anchor is not reproducible."""
    infra = _mod.build_row("pm_infra", _V11_ROW, r2=0.42, c_anchor=0.03343)
    block = infra["inflation_passthrough"]
    assert block["b_infl"] == 0.6
    assert block["k_quarters"] == _mod.CPI_TRAIL_K == 8
    assert block["c_anchor"] == pytest.approx(0.03343)
    assert "chosen" in block["provenance"]

    assert "inflation_passthrough" not in _mod.build_row(
        "pm_vc", _V11_ROW, r2=0.5, c_anchor=0.03343
    )


def test_build_row_writes_the_c1_block_on_the_extended_buyout_sleeve():
    """A6 / AM-2026-08-18-001: C1 now covers pm_buyout too, at the ratified
    lambda_PE toy value -- without this the generated plane's own private
    equity stays inflation-blind (AT-10)."""
    row = _mod.build_row("pm_buyout", _V11_ROW, r2=0.61, c_anchor=0.03343)
    block = row["inflation_passthrough"]
    assert block["b_infl"] == 0.35
    assert "D-ER14-2" in block["provenance"] or "lambda_PE" in block["provenance"]


def test_b_infl_covers_exactly_the_three_c1_sleeves():
    assert set(_mod.B_INFL) == {"pm_infra", "pm_re_value_add", "pm_buyout"}
    assert _mod.B_INFL["pm_buyout"] == 0.35  # lambda_PE, the ratified toy value
    assert set(_mod.LOSS_SLEEVES) == {"pm_direct_lending", "pm_mezzanine", "pm_distressed"}
    # the remaining PE sleeves carry neither term -- the SS1 scope table, machine-checked
    for s in ("pm_growth", "pm_vc", "pm_secondaries"):
        assert s not in _mod.B_INFL and s not in _mod.LOSS_SLEEVES


# ----------------------------------------------------- the v1.1 reproduction


def test_check_reproduction_refuses_drift_beyond_tolerance():
    """The R2 is only meaningful if it comes from the fit that produced the
    shipped loadings. A drifted reproduction must stop the script, not publish
    an R2 for a different regression."""
    good = dict(_V11_ROW["loadings"])
    assert _mod.check_reproduction("pm_buyout", good, _V11_ROW["loadings"]) == 0.0

    drifted = dict(good)
    drifted["equity_mkt"] += _mod.BETA_MATCH_TOL * 10
    with pytest.raises(SystemExit, match="reproduction drift"):
        _mod.check_reproduction("pm_buyout", drifted, _V11_ROW["loadings"])

    # just inside tolerance still passes -- the bound is not decorative
    near = dict(good)
    near["equity_mkt"] += _mod.BETA_MATCH_TOL / 2
    assert _mod.check_reproduction("pm_buyout", near, _V11_ROW["loadings"]) > 0.0


def test_build_row_records_an_unusable_r2_with_the_route_that_caused_it():
    row = _mod.build_row(
        "pm_direct_lending",
        {**_V11_ROW, "route": "bdc-anchor*0.5"},
        r2=None,
        c_anchor=0.033,
        theta=0.01,
        s_bar=1.4,
        mean_loss=0.002,
    )
    assert row["r2_train_val"] is None
    assert "bdc-anchor*0.5" in row["r2_note"]  # the reason names the actual route


def test_sum_beta_recovers_beta_hidden_by_appraisal_lag():
    """v1.1's defect-reproduction test, kept whole. The drop shipped only the
    second assertion; without the first, the test passes for a fit that never
    recovers anything and the Dimson sum is unproven."""
    rng = np.random.default_rng(7)
    n = 400
    f = rng.standard_normal(n) * 0.05
    true = 1.0 * f
    obs = 0.5 * true + 0.3 * np.roll(true, 1) + 0.2 * np.roll(true, 2)
    obs[:2] = true[:2]
    idx = pd.date_range("1950-01-01", periods=n, freq="QS")
    x = pd.DataFrame({r: np.zeros(n) for r in _mod.REGRESSORS}, index=idx)
    x["equity_mkt"] = f
    y = pd.Series(obs, index=idx)
    spec = {r: (0.0, 0.0, 0.0) for r in _mod.REGRESSORS}
    spec["equity_mkt"] = (0.0, float("inf"), 1.0)
    summed, _a, _r, _yv = _mod.fit_sum_beta(y, x, spec, n_lags=2)
    naive, _, _, _ = _mod.fit_sum_beta(y, x, spec, n_lags=0)
    assert naive[0] < 0.7  # the defect reproduced
    assert abs(summed[0] - 1.0) < 0.15  # the fix recovers it


def test_to_quarterly_omits_gaps_rather_than_fabricating_zero_quarters():
    """The drop reimplemented this with ``resample("QE")``. On a gapped series
    resample materialises the empty quarter and ``(1+s).prod()`` returns 1.0 --
    a fabricated 0.0% quarter that v1.1's groupby simply omits. Since this
    function exists to REPRODUCE v1.1, the two must not disagree."""
    idx = pd.to_datetime(
        [
            "1990-01-31",
            "1990-02-28",
            "1990-03-31",  # Q1
            "1990-07-31",
            "1990-08-31",
            "1990-09-30",
        ]  # Q3 -- Q2 absent entirely
    )
    s = pd.Series(0.01, index=idx)
    out = _mod._to_quarterly(s, "compound")

    assert len(out) == 2, "the absent quarter must not appear at all"
    assert pd.Timestamp("1990-04-01") not in out.index
    assert float(out.iloc[0]) == pytest.approx(1.01**3 - 1.0)

    # and the resample form really does differ -- the defect, demonstrated
    fabricated = (1.0 + s).resample("QE").prod() - 1.0
    assert len(fabricated) == 3
    assert float(fabricated.iloc[1]) == 0.0


# --------------------------------------------- the real written artifact
# These read mappings/sleeve-mappings-v1.2.yaml as WRITTEN by running
# scripts/estimate_sleeve_mappings_v1_2.py against the sealed campaign
# vintage (no --theta: this release's own invocation, C2 deferred).


def test_c1_now_covers_buyout():
    """A6, ratified: without the extension the generated path's private
    equity stays inflation-blind and ER-14 closes on one plane only.
    AM-2026-08-15-001 scoped C1 to pm_infra and pm_re_value_add;
    PM_SLEEVE_FOR_ASSET maps the product's pe to pm_buyout."""
    assert set(_mod.B_INFL) == {"pm_infra", "pm_re_value_add", "pm_buyout"}
    assert _mod.B_INFL["pm_buyout"] == 0.35  # lambda_PE, the ratified toy value


def test_the_artifact_ships_without_the_cdli_blocked_credit_loss_block():
    """A7 / D-ER14-2: CDLI decoupled. C1 (+ the buyout extension and F5)
    adopts now; C2's measured half adopts when the Cliffwater export lands.
    The toy plane's convexity is a DECLARED engine constant
    (theta_toy = 0.10) and does not enter this sealed artifact."""
    doc = yaml.safe_load(OUT_PATH.read_text())
    assert all("credit_loss" not in row for row in doc["pm_sleeves"].values())
    assert doc["c2_status"] == "deferred: awaiting Cliffwater CDLI export (AM-... / D-ER14-2)"


def test_f5b_restores_r2_but_moves_no_coefficient():
    """F5b: record only. Adjusting a MEASURED beta toward a prior is precisely
    the tuning the seal exists to prevent. v1.1's loadings are carried
    verbatim; the estimator refuses (tol 1e-3) if the reproduced betas
    drift."""
    v11 = yaml.safe_load(Path("mappings/sleeve-mappings-v1.1.yaml").read_text())
    v12 = yaml.safe_load(OUT_PATH.read_text())
    for name, row in v11["pm_sleeves"].items():
        assert v12["pm_sleeves"][name]["loadings"] == row["loadings"]
    assert v12["pm_sleeves"]["pm_buyout"]["r2_train_val"] is not None


def test_f5c_declares_student_t_residuals_and_a_pm_block_correlation():
    """DN5 section 9 SM-8 seals 'Student-t, df ~ 5; block correlation within
    style family and within PM asset type'. adapter.py drew standard_normal,
    independent across sleeves - thin tails and no co-movement on the path
    players actually play. df = 5 per SM-8 (A9: a seal beats a convenience;
    the toy engine's 6.0 is disclosed as a divergence)."""
    doc = yaml.safe_load(OUT_PATH.read_text())
    assert doc["pm_residuals"]["df"] == 5
    assert doc["pm_residuals"]["rescaled_to_unit_variance"] is True
    corr = doc["pm_residuals"]["block_correlation"]
    assert corr["pm_buyout"]["pm_buyout"] == 1.0


def test_f5a_declares_an_ewma_vol_and_a_position_cap():
    """The CTA rule realises 0.1595 annualised vol against a declared 0.10
    target on the 1974 world: position size is per_inst_target / sigma with a
    trailing 12-month sigma, so a vol jump leaves the denominator stale for up
    to a year."""
    rule = yaml.safe_load(OUT_PATH.read_text())["cta_rule"]
    assert rule["vol_estimator"] == "ewma" and rule["halflife_months"] > 0
    assert rule["position_cap"] > 0
