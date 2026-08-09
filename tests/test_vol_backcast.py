"""Stage 2 of WP-DATA-VOLEXT: the model-based equity_vol backcast.

All fixtures are synthetic (no network, per pytest-socket): daily prices with
clustered volatility, and a monthly implied-vol series built from the model's
own feature set plus a PERSISTENT (AR(1)) pricing error -- so the HAC test
exercises the property it claims, per the task file's test requirements.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ah.data import vol_backcast as vb

A_TRUE = 1.0
B_TRUE = (0.50, 0.25, 0.15, 2.0)  # log_rv22, log_rv66, log_rv252, log_maxdd


def _daily_prices(seed: int = 11) -> pd.DataFrame:
    """Daily closes 1985-01..2015-12 with clustered (AR-in-log-vol) returns."""
    rng = np.random.Generator(np.random.PCG64(seed))
    days = pd.bdate_range("1985-01-02", "2015-12-31")
    n = len(days)
    log_sig = np.empty(n)
    log_sig[0] = np.log(0.15)
    for t in range(1, n):
        log_sig[t] = 0.995 * log_sig[t - 1] + 0.005 * np.log(0.15) + 0.06 * rng.standard_normal()
    ret = np.exp(log_sig) / np.sqrt(vb.TRADING_DAYS) * rng.standard_normal(n)
    close = np.cumprod(1.0 + ret)
    return pd.DataFrame({"close": close}, index=days)


def _panel(seed: int = 11):
    """(features, vix) where log vix = A + B.x + AR(1) error."""
    px = _daily_prices(seed)
    features = vb.realized_features(px)
    rng = np.random.Generator(np.random.PCG64(seed + 1))
    e = np.empty(len(features))
    e[0] = 0.0
    for t in range(1, len(e)):
        e[t] = 0.85 * e[t - 1] + 0.08 * rng.standard_normal()
    x = features[list(vb.FEATURES)].to_numpy(float)
    log_vix = A_TRUE + x @ np.asarray(B_TRUE) + e
    vix = pd.Series(np.exp(log_vix), index=features.index, name="vix")
    return features, vix


@pytest.fixture(scope="module")
def panel():
    return _panel()


@pytest.fixture(scope="module")
def fitted(panel):
    features, vix = panel
    return vb.fit(features, vix)


def test_registered_thresholds_are_the_ratified_d4_values():
    assert vb.REGISTERED_THRESHOLDS == {
        "vxo_heldout_corr_log_min": 0.90,
        "oct1987_peak_ratio_min": 0.75,
        "oct1987_peak_ratio_max": 1.35,
        "stress_bias_log_abs_max": 0.20,
        "ensemble_vol_of_vol_ratio_min": 0.85,
        "coverage_80_tolerance": 0.10,
    }
    assert "downside" not in vb.FEATURES, "the dropped regressor must stay dropped"


def test_no_look_ahead_truncation_leaves_earlier_months_unchanged():
    px = _daily_prices()
    full = vb.realized_features(px)
    cut = pd.Timestamp("2005-06-30")
    truncated = vb.realized_features(px.loc[:cut])
    common = truncated.index[truncated.index <= pd.Timestamp("2005-04-30")]
    pd.testing.assert_frame_equal(full.loc[common], truncated.loc[common])


def test_fit_recovers_coefficients_and_hac_exceeds_naive_ols(fitted):
    coef = np.asarray(fitted.coef)
    assert np.allclose(coef[1:], B_TRUE, atol=0.35)
    # Persistent residuals understate plain OLS uncertainty exactly where the
    # regressor itself is persistent: the intercept and the annual RV window.
    # Fast regressors can sit near 1x -- the inflation is not uniform, and
    # asserting it uniformly would be asserting a falsehood about HAC.
    ratios = np.asarray(fitted.se_hac) / np.asarray(fitted.se_ols)
    by_name = dict(zip(("const", *vb.FEATURES), ratios, strict=True))
    assert by_name["const"] > 1.5 and by_name["log_rv252"] > 1.5, (
        f"HAC must materially exceed naive OLS on the persistent terms: {by_name}"
    )


def test_short_overlap_is_refused(panel):
    features, vix = panel
    with pytest.raises(ValueError, match="overlap too short"):
        vb.fit(features, vix.loc[: pd.Timestamp("1993-12-31")])


def test_range_estimator_refused_on_degenerate_ohlc():
    px = _daily_prices()
    px = px.assign(open=px["close"], high=px["close"], low=px["close"])
    with pytest.raises(ValueError, match="high <= low"):
        vb.realized_features(px, vb.RVConfig(estimator="parkinson"))
    with pytest.raises(ValueError, match="needs OHLC"):
        vb.realized_features(_daily_prices(), vb.RVConfig(estimator="garman_klass"))


def test_backcast_never_overwrites_and_flags_proxies(panel, fitted):
    features, vix = panel
    observed = vix.loc[pd.Timestamp("1990-01-01") :]
    frame, ensemble = vb.backcast(fitted, features, observed, n_draws=50, seed=3)
    proxy = frame.loc[frame["is_proxy"]]
    actual = frame.loc[~frame["is_proxy"], "value"]
    assert proxy["date"].max() < observed.index.min()
    assert (frame["rule_id"] == vb.RULE_ID).all()
    np.testing.assert_array_equal(actual.to_numpy(), observed.to_numpy())
    assert ensemble is not None and ensemble.shape == (50, len(proxy))


def test_ensemble_restores_vol_of_vol_and_the_mean_does_not(panel):
    features, vix = panel
    report = vb.validate(features, vix)
    # The mean discards residual variance by construction; the ensemble must
    # put it back. The synthetic panel's noise share is bounded above by the
    # registered 0.90 held-out correlation threshold (more noise would fail
    # it), so the mean's shortfall here is structural but modest -- the real
    # fit's gap is the reference sketch's 0.874 vs 1.034.
    assert report.vol_of_vol_ratio_mean < report.vol_of_vol_ratio_ensemble - 0.05
    assert report.vol_of_vol_ratio_ensemble >= 0.85
    assert report.vol_of_vol_ratio_mean < 1.0
    assert report.ok, f"clean synthetic panel must pass: {report.passes}"


def test_seed_determinism_and_seed_sensitivity(panel, fitted):
    features, vix = panel
    observed = vix.loc[pd.Timestamp("1990-01-01") :]
    f1, e1 = vb.backcast(fitted, features, observed, n_draws=20, seed=9)
    f2, e2 = vb.backcast(fitted, features, observed, n_draws=20, seed=9)
    _f3, e3 = vb.backcast(fitted, features, observed, n_draws=20, seed=10)
    pd.testing.assert_frame_equal(f1, f2)
    assert e1 is not None and e2 is not None and e3 is not None
    np.testing.assert_array_equal(e1.to_numpy(), e2.to_numpy())
    assert not np.array_equal(e1.to_numpy(), e3.to_numpy())


def test_n_draws_zero_is_the_bare_mean(panel, fitted):
    features, vix = panel
    observed = vix.loc[pd.Timestamp("1990-01-01") :]
    frame, ensemble = vb.backcast(fitted, features, observed, n_draws=0)
    assert ensemble is None
    pre = features.index[features.index < observed.index.min()]
    expected = np.exp(fitted.predict(features.loc[pre]).to_numpy())
    got = frame.loc[frame["is_proxy"], "value"].to_numpy()
    np.testing.assert_allclose(got, expected)


def test_validate_rejects_a_deliberately_broken_mapping(panel):
    features, vix = panel
    # A GLOBALLY inverted or rescaled target is NOT a good broken case: OLS
    # refits it perfectly (still linear in the features). Even an all-era
    # stress premium gets absorbed -- rv22 and maxdd can express it. The
    # break validate() exists to catch is a stress miss the TRAINING era
    # never saw: jack the top RV decile up by 0.6 log points only after the
    # split, so the fitted mapping walks into 2008+ calm-calibrated and the
    # out-of-sample stress bias must blow the registered 0.20 band.
    rv_post = features.loc[features.index > pd.Timestamp("2007-12-31"), "log_rv22"]
    bumped = rv_post.index[rv_post >= rv_post.quantile(0.90)]
    mult = pd.Series(1.0, index=features.index)
    mult.loc[bumped] = np.exp(0.6)
    broken = vix * mult
    report = vb.validate(features, broken)
    assert not report.ok
    assert not report.passes["stress_bias"], (
        f"a stress-conditional miss must fail the stress gate: {report.passes}"
    )


def test_vxo_heldout_scores_the_pre_overlap_era(panel, fitted):
    features, vix = panel
    # the "VXO-derived VIX-equivalent" for the held-out era: the true vix
    # itself (observed by construction pre-1990 in the synthetic world).
    equiv = vix.loc[: pd.Timestamp("1989-12-31")]
    report = vb.vxo_heldout(fitted, features, equiv)
    assert report.n_months >= 24
    assert report.passes["vxo_heldout_corr"], f"corr {report.corr_log}"
    assert report.passes["oct1987_peak"], f"ratio {report.oct1987_ratio}"
    assert report.ok
    # and a mangled mapping must fail the peak band
    mangled = vb.vxo_heldout(fitted, features, equiv * 3.0)
    assert not mangled.passes["oct1987_peak"]


def test_heldout_cannot_leak_fitted_months(panel, fitted):
    features, vix = panel
    # feed the FULL vix series as "equiv": the function must restrict itself
    # to months strictly before the overlap start.
    report = vb.vxo_heldout(fitted, features, vix)
    assert report.n_months == len(
        features.index[features.index < pd.Timestamp(fitted.spec.overlap_start)]
    )


def test_write_provenance_is_complete_and_clock_free(tmp_path, panel, fitted):
    features, vix = panel
    validation = vb.validate(features, vix)
    heldout = vb.vxo_heldout(fitted, features, vix.loc[: pd.Timestamp("1989-12-31")])
    out = tmp_path / "prov.json"
    vb.write_provenance(
        fitted,
        validation,
        heldout,
        out,
        fitted_at="2026-08-09T00:00:00+00:00",
        amendment_id="AM-TEST-000",
    )
    import json

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["artifact"] == vb.REGISTERED_OBJECT
    assert payload["registered_thresholds"] == vb.REGISTERED_THRESHOLDS
    assert payload["fitted_at"] == "2026-08-09T00:00:00+00:00"
    assert "MODEL OUTPUT" in payload["caveat"]
    assert len(payload["residuals"]) == fitted.n_obs
    # the D2 consumer contract: paths() regenerates bit-identically from seed
    p1 = vb.paths(fitted, 48, n_draws=8, seed=5)
    p2 = vb.paths(fitted, 48, n_draws=8, seed=5)
    np.testing.assert_array_equal(p1, p2)
