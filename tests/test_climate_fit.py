"""WP2.5 fit.py: data assembly through the sanctioned surface, leakage guards,
smoke NUTS fit, deterministic artifact, generated report.

The synthetic mini-world below is format-faithful to the campaign catalog: the
same series ids, units, and frequencies (monthly FRED/Shiller, quarterly BIS,
annual JST at Jan-1 dates), served through a real ``ah.splits.DataAccess`` so the
train/validation/holdout gate is the genuine article, not a stub.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from ah.gen.climate import fit as cf
from ah.gen.climate import model as cm
from ah.splits import TRAIN, DataAccess

# --------------------------------------------------------------------------- #
# the synthetic mini-world
# --------------------------------------------------------------------------- #

SPAN_START = "2001-01-01"
SPAN_END = "2021-01-01"  # exclusive == ah.splits.VALIDATION.end


def _monthly(start: str, end_excl: str) -> pd.DatetimeIndex:
    return pd.date_range(start, end_excl, freq="MS", inclusive="left")


def _frame(dates, values) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.DatetimeIndex(dates), "value": np.asarray(values, float)})


def _mini_series(
    *,
    cape_shift_validation: float = 0.0,
    holdout_rows: bool = False,
    cpi_start: str = "1999-01-01",
) -> dict[str, pd.DataFrame]:
    """Deterministic synthetic series covering 2001-01 .. 2020-12 (+ optional holdout)."""
    m_end = "2026-07-01" if holdout_rows else SPAN_END
    m = _monthly(cpi_start, m_end)
    t = np.arange(len(m))
    cpi = 100.0 * np.exp(0.025 * t / 12.0)  # 2.5%/yr inflation
    cape = 22.0 + 3.0 * np.sin(t / 17.0)
    mask_val = (pd.DatetimeIndex(m) >= "2011-01-01") & (pd.DatetimeIndex(m) < "2021-01-01")
    cape = np.where(mask_val, cape + cape_shift_validation, cape)
    fed = 3.0 + 1.5 * np.sin(t / 23.0)
    usrec = ((t % 60) < 9).astype(float)  # a 9-month recession every 5 years

    q = pd.date_range("2001-01-01", m_end, freq="QS", inclusive="left")
    bis = _frame(q, 2.0 * np.sin(np.arange(len(q)) / 7.0) * 5.0)

    years = list(range(1999, 2026 if holdout_rows else 2021))
    ydates = pd.DatetimeIndex([f"{y}-01-01" for y in years])
    ny = len(years)
    jst_cpi = 100.0 * np.exp(0.025 * np.arange(ny))
    jst_gdp = 9000.0 * np.exp(0.045 * np.arange(ny))
    jst_tloans = 6000.0 * np.exp(0.055 * np.arange(ny))
    jst_stir = 3.0 + 0.5 * np.sin(np.arange(ny))
    jst_ltrate = 4.0 + 0.4 * np.cos(np.arange(ny))
    jst_eq = 0.06 + 0.05 * np.sin(np.arange(ny) / 2.0)

    return {
        "fred.CPI": _frame(m, cpi),
        "fred.FEDFUNDS": _frame(m, fed),
        "shiller.cape": _frame(m, cape),
        "fred.USREC": _frame(m, usrec),
        "bis.credit_gap_us": bis,
        "jst.usa_cpi": _frame(ydates, jst_cpi),
        "jst.usa_stir": _frame(ydates, jst_stir),
        "jst.usa_ltrate": _frame(ydates, jst_ltrate),
        "jst.usa_gdp": _frame(ydates, jst_gdp),
        "jst.usa_tloans": _frame(ydates, jst_tloans),
        "jst.usa_eq_tr": _frame(ydates, jst_eq),
    }


def _access(series: dict[str, pd.DataFrame]) -> DataAccess:
    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in series:
            raise KeyError(series_id)
        return series[series_id]

    return DataAccess(reader)


def _mini_config() -> cm.ClimateConfig:
    cfg = cm.load_config()
    return cfg.model_copy(
        update={"span": cm.SpanSettings(start=SPAN_START, end=SPAN_END)}, deep=True
    )


# --------------------------------------------------------------------------- #
# data assembly
# --------------------------------------------------------------------------- #


class TestBuildFitData:
    def test_grid_and_shapes(self):
        fd = cf.build_fit_data(_access(_mini_series()), _mini_config())
        t_len = 240  # 2001-01 .. 2020-12
        assert len(fd.dates) == t_len
        assert fd.dates[0] == pd.Timestamp(SPAN_START)
        assert fd.dates[-1] == pd.Timestamp("2020-12-01")
        assert fd.kf.y.shape == (t_len, cm.N_CHANNELS)
        assert not np.isnan(fd.kf.y).any()
        assert set(np.unique(fd.kf.mask)) <= {0.0, 1.0}

    def test_monthly_inflation_is_yoy_log_diff(self):
        series = _mini_series()
        fd = cf.build_fit_data(_access(series), _mini_config())
        c = cm.CHANNELS.index("m_infl")
        # CPI starts 1999-01, so YoY exists on every grid month
        assert fd.kf.mask[:, c].all()
        # 2.5%/yr continuous growth -> YoY log-diff == 2.5 exactly
        np.testing.assert_allclose(fd.kf.y[:, c], 2.5, atol=1e-9)

    def test_policy_channel_mask_and_aux(self):
        fd = cf.build_fit_data(_access(_mini_series()), _mini_config())
        c = cm.CHANNELS.index("m_policy")
        assert fd.kf.mask[:, c].all()
        # aux_pi carries observed actual inflation for the anchor offset
        np.testing.assert_allclose(fd.kf.aux_pi[:, c], 2.5, atol=1e-9)
        # aux_c carries the cycle term
        assert set(np.unique(fd.kf.aux_c[:, c])) <= {-1.0, 1.0}

    def test_cycle_proxy_is_one_minus_two_usrec(self):
        series = _mini_series()
        fd = cf.build_fit_data(_access(series), _mini_config())
        usrec = series["fred.USREC"].set_index("date")["value"].reindex(fd.dates).to_numpy()
        np.testing.assert_allclose(fd.kf.cycle, 1.0 - 2.0 * usrec)

    def test_annual_channels_land_mid_year(self):
        fd = cf.build_fit_data(_access(_mini_series()), _mini_config())
        c = cm.CHANNELS.index("a_infl")
        obs_rows = np.nonzero(fd.kf.mask[:, c])[0]
        months = {pd.Timestamp(ts).month for ts in fd.dates[obs_rows]}
        assert months == {7}
        # value at July of year y is 100*(log cpi_y - log cpi_{y-1}) = 2.5
        np.testing.assert_allclose(fd.kf.y[obs_rows, c], 2.5, atol=1e-9)

    def test_annual_growth_is_deflated_gdp(self):
        fd = cf.build_fit_data(_access(_mini_series()), _mini_config())
        c = cm.CHANNELS.index("a_growth")
        obs = fd.kf.y[fd.kf.mask[:, c] == 1.0, c]
        # nominal 4.5% minus inflation 2.5% = 2.0% real, every year
        np.testing.assert_allclose(obs, 2.0, atol=1e-9)

    def test_credit_ratio_observation(self):
        fd = cf.build_fit_data(_access(_mini_series()), _mini_config())
        c = cm.CHANNELS.index("a_credit")
        rows = np.nonzero(fd.kf.mask[:, c])[0]
        years = np.array([pd.Timestamp(ts).year for ts in fd.dates[rows]])
        # 100*log(tloans/gdp): log(6000/9000)*100 + (0.055-0.045)*100*k
        k = years - 1999
        expected = 100.0 * (math.log(6000.0 / 9000.0)) + 1.0 * k
        np.testing.assert_allclose(fd.kf.y[rows, c], expected, atol=1e-6)

    def test_r10_forward_window_and_placement(self):
        fd = cf.build_fit_data(_access(_mini_series()), _mini_config())
        c = cm.CHANNELS.index("a_r10")
        rows = np.nonzero(fd.kf.mask[:, c])[0]
        stamps = [pd.Timestamp(ts) for ts in fd.dates[rows]]
        assert {ts.month for ts in stamps} == {12}
        # windows need years y+1..y+10 with data (JST ends 2020): last y = 2010
        assert max(ts.year for ts in stamps) == 2010
        # value: mean over 10 years of 100*(log(1+eq_tr) - dlog cpi)
        y0 = int(stamps[0].year)
        series = _mini_series()
        eq = series["jst.usa_eq_tr"].set_index("date")["value"]
        expected = float(
            np.mean(
                [100.0 * (math.log(1.0 + eq[f"{y}-01-01"]) - 0.025) for y in range(y0 + 1, y0 + 11)]
            )
        )
        assert fd.kf.y[rows[0], c] == pytest.approx(expected, abs=1e-6)

    def test_bis_quarterly_mask(self):
        fd = cf.build_fit_data(_access(_mini_series()), _mini_config())
        c = cm.CHANNELS.index("q_bis")
        rows = np.nonzero(fd.kf.mask[:, c])[0]
        assert {pd.Timestamp(ts).month for ts in fd.dates[rows]} == {1, 4, 7, 10}

    def test_missing_series_leaves_channel_unmasked(self):
        series = _mini_series()
        del series["bis.credit_gap_us"]
        fd = cf.build_fit_data(_access(series), _mini_config())
        c = cm.CHANNELS.index("q_bis")
        assert not fd.kf.mask[:, c].any()


# --------------------------------------------------------------------------- #
# normalization leakage (the WP2.5 plan demands this explicitly)
# --------------------------------------------------------------------------- #


class TestNormalizationLeakage:
    def test_cape_demean_constant_is_train_span_only(self):
        series = _mini_series()
        fd = cf.build_fit_data(_access(series), _mini_config())
        cape = series["shiller.cape"].set_index("date")["value"]
        train_rows = cape[(cape.index >= SPAN_START) & (cape.index < TRAIN.end)]
        assert fd.cape_demean_mean == pytest.approx(float(np.log(train_rows).mean()))
        assert fd.cape_demean_span == (SPAN_START, TRAIN.end)

    def test_validation_span_cape_cannot_move_the_demean(self):
        """Estimation sees validation CAPE, normalization must not."""
        fd_base = cf.build_fit_data(_access(_mini_series()), _mini_config())
        fd_shift = cf.build_fit_data(
            _access(_mini_series(cape_shift_validation=15.0)), _mini_config()
        )
        assert fd_shift.cape_demean_mean == fd_base.cape_demean_mean
        # ... while the observations themselves DO differ (validation is estimation data)
        c = cm.CHANNELS.index("m_cape")
        assert not np.allclose(fd_shift.kf.y[:, c], fd_base.kf.y[:, c])

    def test_holdout_rows_cannot_reach_the_fit_data_at_all(self):
        """Bit-identical FitData whether or not the store contains holdout-era rows."""
        fd_a = cf.build_fit_data(_access(_mini_series(holdout_rows=False)), _mini_config())
        fd_b = cf.build_fit_data(_access(_mini_series(holdout_rows=True)), _mini_config())
        np.testing.assert_array_equal(fd_a.kf.y, fd_b.kf.y)
        np.testing.assert_array_equal(fd_a.kf.mask, fd_b.kf.mask)
        np.testing.assert_array_equal(fd_a.kf.cycle, fd_b.kf.cycle)
        assert fd_a.cape_demean_mean == fd_b.cape_demean_mean

    def test_full_sample_demeaned_cape_is_distinguishable_and_refused(self):
        """The plan's explicit test: a fit fed full-sample-demeaned CAPE is refused.

        ``build_fit_data`` demeans internally (train span only), so the only way to
        feed a full-sample demean is to hand-construct FitData; ``fit_climate``
        cross-checks the recorded demean against the train-span mean of the raw
        series and refuses a mismatch.
        """
        series = _mini_series()
        access = _access(series)
        config = _mini_config()
        fd = cf.build_fit_data(access, config)
        cape = series["shiller.cape"].set_index("date")["value"]
        full_sample_mean = float(np.log(cape[cape.index >= SPAN_START]).mean())
        assert full_sample_mean != pytest.approx(fd.cape_demean_mean)
        poisoned = cf.FitData(
            dates=fd.dates,
            kf=fd.kf,
            cape_demean_mean=full_sample_mean,
            cape_demean_span=(SPAN_START, SPAN_END),
            cape_demean_n=fd.cape_demean_n,
            channel_counts=fd.channel_counts,
        )
        with pytest.raises(cf.NormalizationLeakageError):
            cf.assert_train_only_normalization(poisoned, access, config)


# --------------------------------------------------------------------------- #
# smoke fit + deterministic artifact + report
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def smoke_fit(tmp_path_factory):
    out = tmp_path_factory.mktemp("climate-smoke")
    config = _mini_config().model_copy(
        update={
            "fit": cm.FitSettings(
                chains=1,
                warmup=50,
                samples=50,
                target_accept=0.8,
                max_tree_depth=8,
                chain_method="sequential",
                artifact_draws=20,
                ppc_draws=10,
            )
        },
        deep=True,
    )
    result = cf.fit_climate(
        _access(_mini_series()),
        config,
        seed=1234,
        vintage_id="test-vintage",
        out_dir=out,
        created_at="2026-07-26",
    )
    return result


class TestSmokeFit:
    def test_diagnostics_present_and_finite(self, smoke_fit):
        d = smoke_fit.diagnostics
        assert d["divergences"] >= 0
        assert set(d["per_param"]) == set(cm.PARAM_NAMES)
        for row in d["per_param"].values():
            assert np.isfinite(row["mean"])
            assert np.isfinite(row["n_eff"])
        assert np.isfinite(d["max_rhat"])

    def test_artifact_saved_and_loads(self, smoke_fit):
        from ah.gen.climate import simulate as cs

        art = cs.load_artifact(smoke_fit.artifact_path)
        assert art.states.shape == (20, 240, cm.N_STATES)
        assert set(art.params) == set(cm.PARAM_NAMES)
        assert art.params["mu_r"].shape == (20,)
        assert art.meta["config_hash"].startswith("cfg:")
        assert art.meta["vintage_id"] == "test-vintage"
        assert art.meta["seed"] == 1234
        assert art.meta["cape_demean"]["span"] == [SPAN_START, TRAIN.end]

    def test_artifact_content_hash_verifies_and_detects_tamper(self, smoke_fit, tmp_path):
        from ah.gen.climate import simulate as cs

        art = cs.load_artifact(smoke_fit.artifact_path)
        assert art.meta["content_sha256"]
        # tamper: flip one byte of the states array and re-save raw
        data = dict(np.load(smoke_fit.artifact_path, allow_pickle=False))
        data["states"] = data["states"].copy()
        data["states"][0, 0, 0] += 1e-3
        bad = tmp_path / "tampered.npz"
        np.savez(bad, **data)
        with pytest.raises(cs.ArtifactError):
            cs.load_artifact(bad)

    def test_ppc_coverage_reported(self, smoke_fit):
        ppc = smoke_fit.diagnostics["ppc_coverage_90"]
        assert set(ppc) <= set(cm.CHANNELS)
        for frac in ppc.values():
            assert 0.0 <= frac <= 1.0

    def test_report_generated_with_required_sections(self, smoke_fit):
        text = smoke_fit.report_path.read_text(encoding="utf-8")
        for needle in (
            "# Climate model fit report",
            "R-hat",
            "ESS",
            "Divergences",
            "Posterior predictive",
            "half-life",
            "cfg:",
            "Train-only normalization",
        ):
            assert needle in text, needle

    def test_experiment_recorded(self, smoke_fit):
        meta = json.loads(
            (smoke_fit.artifact_path.parent / "meta.json").read_text(encoding="utf-8")
        )
        assert meta["seed"] == 1234
        assert meta["vintage_id"] == "test-vintage"
        assert meta["config_hash"].startswith("cfg:")
