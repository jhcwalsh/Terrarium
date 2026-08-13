"""AM-2026-08-12-001: the v1.1 PM estimator's pure functions.

The defect being fixed is the test: a contemporaneous-only regression on
appraisal-lagged observations understates beta; the Dimson sum recovers it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "estimate_v11", _ROOT / "scripts" / "estimate_sleeve_mappings_v1_1.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_lag_count_follows_the_declared_rule():
    assert _mod.lag_count(125) == 4
    assert _mod.lag_count(80) == 4
    assert _mod.lag_count(60) == 2
    assert _mod.lag_count(40) == 2
    assert _mod.lag_count(39) == 0  # refused -> prior adopted


def test_dimson_frame_adds_lagged_equity_columns_only():
    idx = pd.date_range("2000-01-01", periods=10, freq="QS")
    x = pd.DataFrame({r: np.arange(10.0) for r in _mod.REGRESSORS}, index=idx)
    out = _mod.dimson_frame(x, 2)
    assert list(out.columns) == [*_mod.REGRESSORS, "equity_mkt_lag1", "equity_mkt_lag2"]
    assert out["equity_mkt_lag1"].iloc[3] == x["equity_mkt"].iloc[4]
    assert len(out) == 8  # lagged rows dropped, never zero-filled


def test_sum_beta_recovers_beta_hidden_by_appraisal_lag():
    """The defect, synthesized: true beta 1.0, observations a (0.5, 0.3, 0.2)
    moving average of truth. Contemporaneous-only fit sees ~0.5; the summed
    Dimson betas must recover ~1.0."""
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
    summed, _alpha, _resid, _per_lag = _mod.fit_sum_beta(y, x, spec, n_lags=2)
    naive, _, _, _ = _mod.fit_sum_beta(y, x, spec, n_lags=0)
    assert naive[0] < 0.7  # the defect reproduced
    assert abs(summed[0] - 1.0) < 0.15  # the fix recovers it


def test_delever_scales_betas_and_sigma_not_alpha():
    loadings = {"equity_mkt": 0.8, "d_ig": -0.4, "smb": 0.0}
    out, sigma = _mod.delever(loadings, sigma=0.20, factor=0.5)
    assert out == {"equity_mkt": 0.4, "d_ig": -0.2, "smb": 0.0}
    assert sigma == 0.10


def test_merge_artifact_replaces_pm_rows_and_copies_hf_verbatim():
    v10 = {
        "mapping_version": "map-2026.08",
        "sleeves": {"hf_event": {"alpha_monthly": 0.001}},
        "pm_sleeves": {"pm_buyout": {"alpha_quarterly": 0.033}},
        "residual_correlation": {"hf_event": {"hf_event": 1.0}},
        "cta_rule": {"kind": "tsm_overlay"},
    }
    new_pm = {"pm_buyout": {"alpha_quarterly": 0.010, "loadings": {"equity_mkt": 1.1}}}
    out = _mod.merge_artifact(v10, new_pm)
    assert out["mapping_version"] == _mod.MAPPING_VERSION
    assert out["sleeves"] == v10["sleeves"]  # verbatim
    assert out["residual_correlation"] == v10["residual_correlation"]
    assert out["cta_rule"] == v10["cta_rule"]
    assert out["pm_sleeves"]["pm_buyout"]["alpha_quarterly"] == 0.010
