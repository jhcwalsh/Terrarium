"""WP2.6 fit.py: label assembly (pinned to the bootstrap's), spell construction,
the NegBin/multinomial likelihood against scipy ground truth, bootstrap bands,
the acceptance table, and a smoke NUTS fit end-to-end (artifacts + reports).

The synthetic mini-world is format-faithful to the campaign catalog (same series
ids, units, frequencies) and served through a real ``ah.splits.DataAccess``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

from ah.data.derive import REGIME_LABELS
from ah.gen import bootstrap as bs
from ah.gen.climate import fit as climate_fit
from ah.gen.climate import simulate as climate_sim
from ah.gen.climate.model import PARAM_NAMES
from ah.gen.regimes import fit as rf
from ah.gen.regimes import semimarkov as sm
from ah.splits import DataAccess

IDX = {label: i for i, label in enumerate(REGIME_LABELS)}

# --------------------------------------------------------------------------- #
# the synthetic mini-world
# --------------------------------------------------------------------------- #

SERIES_START = "1988-01-01"
SPAN_END = "2016-01-01"  # exclusive


def _level_from_yoy(yoy_pct: np.ndarray, base: float = 100.0) -> np.ndarray:
    """A level series whose trailing-12m percent change tracks ``yoy_pct``."""
    growth = (1.0 + yoy_pct / 100.0) ** (1.0 / 12.0)
    return base * np.cumprod(growth)


def _mini_series() -> dict[str, pd.DataFrame]:
    m = pd.date_range(SERIES_START, SPAN_END, freq="MS", inclusive="left")
    t = np.arange(len(m))
    cycle_pos = t % 96

    # inflation: 1.5% baseline; a 5% era; a 3.75% era (between the v1 and v1b
    # cpi_high thresholds, so the two rulesets disagree there)
    cpi_yoy = np.full(len(m), 1.5)
    cpi_yoy[(cycle_pos >= 16) & (cycle_pos < 36)] = 5.0
    cpi_yoy[(cycle_pos >= 36) & (cycle_pos < 52)] = 3.75
    cpi = _level_from_yoy(cpi_yoy)

    # growth: recessions (usrec) at -2%, one slowdown era at 1.0%, else 3%
    usrec = ((cycle_pos >= 40) & (cycle_pos < 48)).astype(float)
    growth_yoy = np.full(len(m), 3.0)
    growth_yoy[(cycle_pos >= 56) & (cycle_pos < 68)] = 1.0
    growth_yoy[usrec >= 0.5] = -2.0
    indpro = _level_from_yoy(growth_yoy)

    # equity: -5%/m in recessions (drawdown crosses both crisis thresholds),
    # +4%/m for a year after, else +1%/m
    ret = np.full(len(m), 0.01)
    ret[usrec >= 0.5] = -0.05
    recovery = np.zeros(len(m), dtype=bool)
    for lag in range(48, 60):
        recovery |= cycle_pos == lag
    ret[recovery] = 0.04
    rf_ret = np.full(len(m), 0.003)
    mkt_rf = ret - rf_ret

    # curve inputs: GS10 only from 1995 (the JST splice covers 1988-1994)
    gs10_dates = m[m >= "1995-01-01"]
    gs10 = 5.0 + np.sin(np.arange(len(gs10_dates)) / 7.0)
    tb3 = 3.0 + np.cos(t / 9.0)

    years = pd.DatetimeIndex([f"{y}-01-01" for y in range(1985, 2017)])
    ny = len(years)
    jst_lt = 6.0 + 0.3 * np.sin(np.arange(ny))
    jst_st = 4.0 + 0.2 * np.cos(np.arange(ny))

    def frame(dates, values):
        return pd.DataFrame({"date": pd.DatetimeIndex(dates), "value": np.asarray(values, float)})

    return {
        "fred.CPI": frame(m, cpi),
        "fred.INDPRO": frame(m, indpro),
        "fred.USREC": frame(m, usrec),
        "french.mkt_rf": frame(m, mkt_rf),
        "french.rf": frame(m, rf_ret),
        "fred.GS10": frame(gs10_dates, gs10),
        "fred.TB3MS": frame(m, tb3),
        "jst.usa_ltrate": frame(years, jst_lt),
        "jst.usa_stir": frame(years, jst_st),
    }


def _access(series: dict[str, pd.DataFrame]) -> DataAccess:
    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in series:
            raise KeyError(series_id)
        return series[series_id]

    return DataAccess(reader)


def _mini_climate_artifact(tmp_path) -> climate_sim.ClimateArtifact:
    """A synthetic L1 artifact whose grid covers the mini-world span."""
    dates = pd.date_range("1988-01-01", SPAN_END, freq="MS", inclusive="left")
    t = np.arange(len(dates))
    rng = np.random.Generator(np.random.PCG64(17))
    n_draws = 6
    base = np.zeros((len(dates), 5))
    base[:, 0] = 2.0 + np.sin(t / 11.0)  # pi_star
    base[:, 4] = 3.0 * np.sin(t / 13.0)  # credit_gap
    states = base[None, :, :] + 0.01 * rng.standard_normal((n_draws, len(dates), 5))
    params = {name: np.full(n_draws, 0.5) for name in PARAM_NAMES}
    params["psi"] = np.full(n_draws, 1.5)
    params["phi_c"] = np.full(n_draws, 0.4)
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "climate.npz"
    climate_fit.save_artifact(path, params=params, states=states, dates=dates, meta={"seed": 0})
    return climate_sim.load_artifact(path)


def _mini_config() -> sm.RegimesConfig:
    cfg = sm.load_config()
    return cfg.model_copy(
        update={
            "fit": sm.FitSettings(
                chains=1,
                warmup=150,
                samples=150,
                chain_method="sequential",
                artifact_draws=100,
                dense_mass=False,
            ),
            "acceptance": sm.AcceptanceSettings(
                n_boot=50,
                bootstrap_mean_block_months=60,
                bootstrap_seed=7,
                sim_n_decades=6,
                sim_months=60,
                sim_seed=7,
            ),
        },
        deep=True,
    )


# --------------------------------------------------------------------------- #
# label assembly
# --------------------------------------------------------------------------- #


class TestLabelAssembly:
    def test_labels_match_bootstrap_assembly(self, tmp_path):
        """The fit's label path and ah.gen.bootstrap.regime_labels_for must agree
        exactly under the default thresholds (the anti-drift pin)."""
        series = _mini_series()
        access = _access(series)
        art = _mini_climate_artifact(tmp_path)
        fd = rf.build_fit_data(access, _mini_config(), art)

        def monthly(sid: str) -> pd.Series:
            f = series[sid]
            values = pd.Series(f["value"].to_numpy(dtype=float), index=pd.DatetimeIndex(f["date"]))
            return values.sort_index()

        equity = monthly("french.mkt_rf") + monthly("french.rf")
        expected = bs.regime_labels_for(
            fd.dates,
            cpi_level=monthly("fred.CPI"),
            equity_returns=equity,
            usrec=monthly("fred.USREC"),
            indpro=monthly("fred.INDPRO"),
        )
        assert [REGIME_LABELS[c] for c in fd.labels] == list(expected)

    def test_span_is_maximal_complete_run(self, tmp_path):
        access = _access(_mini_series())
        art = _mini_climate_artifact(tmp_path)
        fd = rf.build_fit_data(access, _mini_config(), art)
        # yoy features need 12 lead months: complete span starts 1989-01
        assert fd.dates[0] == pd.Timestamp("1989-01-01")
        assert fd.dates[-1] == pd.Timestamp("2015-12-01")
        assert fd.labels.size == len(fd.dates)

    def test_multiple_regimes_present(self, tmp_path):
        access = _access(_mini_series())
        fd = rf.build_fit_data(access, _mini_config(), _mini_climate_artifact(tmp_path))
        present = {REGIME_LABELS[c] for c in np.unique(fd.labels)}
        assert {"EXP", "SLOW", "REC", "CRI"} <= present
        assert present & {"STAG", "REF"}

    def test_v1b_thresholds_change_labels(self, tmp_path):
        access = _access(_mini_series())
        art = _mini_climate_artifact(tmp_path)
        cfg = _mini_config()
        fd_v1 = rf.build_fit_data(access, cfg, art)
        fd_v1b = rf.build_fit_data(access, cfg, art, thr=cfg.sensitivity.model_dump())
        assert fd_v1b.ruleset_version == "regime_ruleset_v1b"
        agreement = float(np.mean(fd_v1.labels == fd_v1b.labels))
        assert 0.5 < agreement < 1.0  # perturbed, not scrambled
        # the 3.75% inflation era flips toward STAG/REF only under v1b
        v1b_infl = np.isin(fd_v1b.labels, [IDX["STAG"], IDX["REF"]]).sum()
        v1_infl = np.isin(fd_v1.labels, [IDX["STAG"], IDX["REF"]]).sum()
        assert v1b_infl > v1_infl

    def test_interior_feature_gap_refused(self, tmp_path):
        series = _mini_series()
        indpro = series["fred.INDPRO"]
        keep = (indpro["date"] != pd.Timestamp("2000-06-01")).to_numpy()
        series["fred.INDPRO"] = indpro.iloc[np.flatnonzero(keep)]
        with pytest.raises(sm.RegimesError, match="gap"):
            rf.build_fit_data(_access(series), _mini_config(), _mini_climate_artifact(tmp_path))

    def test_missing_series_refused(self, tmp_path):
        series = _mini_series()
        del series["fred.INDPRO"]
        with pytest.raises(sm.RegimesError, match=r"fred\.INDPRO"):
            rf.build_fit_data(_access(series), _mini_config(), _mini_climate_artifact(tmp_path))


# --------------------------------------------------------------------------- #
# covariates
# --------------------------------------------------------------------------- #


class TestCovariates:
    def test_slope_splice(self, tmp_path):
        """Monthly GS10-TB3MS where both exist; JST annual spread (ffilled) before."""
        series = _mini_series()
        access = _access(series)
        fd = rf.build_fit_data(access, _mini_config(), _mini_climate_artifact(tmp_path))
        raw_slope = fd.z[:, 0] * fd.cov_sd[0] + fd.cov_mean[0]

        gs10 = series["fred.GS10"].set_index("date")["value"]
        tb3 = series["fred.TB3MS"].set_index("date")["value"]
        i_1995 = fd.dates.get_loc(pd.Timestamp("1995-01-01"))
        expected_monthly = float(gs10[pd.Timestamp("1995-01-01")] - tb3[pd.Timestamp("1995-01-01")])
        assert raw_slope[i_1995] == pytest.approx(expected_monthly, abs=1e-9)

        lt = series["jst.usa_ltrate"].set_index("date")["value"]
        st = series["jst.usa_stir"].set_index("date")["value"]
        i_1990_06 = fd.dates.get_loc(pd.Timestamp("1990-06-01"))
        expected_annual = float(lt[pd.Timestamp("1990-01-01")] - st[pd.Timestamp("1990-01-01")])
        assert raw_slope[i_1990_06] == pytest.approx(expected_annual, abs=1e-9)

    def test_standardization_recorded_and_applied(self, tmp_path):
        fd = rf.build_fit_data(
            _access(_mini_series()), _mini_config(), _mini_climate_artifact(tmp_path)
        )
        # continuous covariates standardized on the fit span
        for col in range(3):
            assert fd.z[:, col].mean() == pytest.approx(0.0, abs=1e-9)
            assert fd.z[:, col].std() == pytest.approx(1.0, abs=1e-9)
        # the drawdown dummy stays 0/1
        assert set(np.unique(fd.z[:, 3])) <= {0.0, 1.0}
        assert fd.cov_mean[3] == 0.0 and fd.cov_sd[3] == 1.0

    def test_pi_gap_uses_posterior_mean_minus_target(self, tmp_path):
        art = _mini_climate_artifact(tmp_path)
        cfg = _mini_config()
        fd = rf.build_fit_data(_access(_mini_series()), cfg, art)
        raw_pi_gap = fd.z[:, 2] * fd.cov_sd[2] + fd.cov_mean[2]
        locs = art.dates.get_indexer(fd.dates)
        expected = art.states.mean(axis=0)[locs, 0] - cfg.pi_target
        np.testing.assert_allclose(raw_pi_gap, expected, atol=1e-9)

    def test_climate_artifact_sha_recorded(self, tmp_path):
        art = _mini_climate_artifact(tmp_path)
        fd = rf.build_fit_data(_access(_mini_series()), _mini_config(), art)
        assert fd.climate_artifact_sha256 == art.meta["content_sha256"]

    def test_cycle_mapping_is_usrec_conditional_mean(self, tmp_path):
        fd = rf.build_fit_data(
            _access(_mini_series()), _mini_config(), _mini_climate_artifact(tmp_path)
        )
        # by ruleset construction: CRI months always have usrec=1; EXP always 0
        assert fd.cycle_by_regime[IDX["CRI"]] == -1.0
        assert fd.cycle_by_regime[IDX["EXP"]] == 1.0
        assert np.all(np.abs(fd.cycle_by_regime) <= 1.0)


# --------------------------------------------------------------------------- #
# spells
# --------------------------------------------------------------------------- #


class TestSpellData:
    def test_spell_bookkeeping(self, tmp_path):
        fd = rf.build_fit_data(
            _access(_mini_series()), _mini_config(), _mini_climate_artifact(tmp_path)
        )
        spells = sm.spells_from_labels(fd.labels)
        n = len(spells)
        assert fd.spells.soj_state.size == n - 1  # first spell dropped
        assert fd.spells.soj_censored.sum() == 1 and fd.spells.soj_censored[-1]
        assert fd.spells.trans_from.size == n - 1
        assert int(fd.transition_counts.sum()) == n - 1
        np.testing.assert_array_equal(fd.spells.soj_dur, np.array([d for _, _, d in spells[1:]]))
        # transitions never self-transition
        assert np.all(fd.spells.trans_from != fd.spells.trans_to)

    def test_sojourn_covariates_at_spell_start(self, tmp_path):
        fd = rf.build_fit_data(
            _access(_mini_series()), _mini_config(), _mini_climate_artifact(tmp_path)
        )
        spells = sm.spells_from_labels(fd.labels)
        for i, (_, start, _) in enumerate(spells[1:]):
            np.testing.assert_array_equal(fd.spells.soj_z[i], fd.z[start])


# --------------------------------------------------------------------------- #
# likelihood ground truth (scipy)
# --------------------------------------------------------------------------- #


class TestLikelihood:
    def test_loglik_matches_scipy(self):
        rng = np.random.Generator(np.random.PCG64(5))
        alpha = rng.normal(size=6)
        gamma = rng.normal(size=(6, 4)) * 0.3
        r = np.exp(rng.normal(size=6) * 0.3 + 1.0)
        trans_a = rf.scatter_trans_a(rng.normal(size=24))
        b_dest = rf.scatter_trans_b(rng.normal(size=20) * 0.5)

        soj_state = np.array([2, 0, 3, 1])
        soj_dur = np.array([5, 24, 1, 7])
        soj_z = rng.normal(size=(4, 4))
        soj_censored = np.array([False, False, False, True])
        trans_from = np.array([2, 0, 3])
        trans_to = np.array([0, 3, 1])
        trans_z = rng.normal(size=(3, 4))
        spells = rf.SpellData(
            soj_state=soj_state,
            soj_dur=soj_dur,
            soj_z=soj_z,
            soj_censored=soj_censored,
            trans_from=trans_from,
            trans_to=trans_to,
            trans_z=trans_z,
        )
        params = {"alpha": alpha, "gamma": gamma, "r": r, "trans_a": trans_a, "b_dest": b_dest}
        got = float(rf.semimarkov_loglik(params, spells))

        expected = 0.0
        for i in range(4):
            k = soj_state[i]
            p = 1.0 / (1.0 + np.exp(-(alpha[k] + gamma[k] @ soj_z[i])))
            x = soj_dur[i] - 1
            if soj_censored[i]:
                # P(D >= d) = P(X >= d-1) = sf(d-2)
                expected += float(np.log(sps.nbinom.sf(x - 1, r[k], p)))
            else:
                expected += float(sps.nbinom.logpmf(x, r[k], p))
        for i in range(3):
            k = trans_from[i]
            logits = trans_a[k] + b_dest @ trans_z[i]
            logits[k] = -np.inf
            shifted = logits - logits.max()
            log_probs = shifted - np.log(np.exp(shifted).sum())
            expected += float(log_probs[trans_to[i]])

        assert got == pytest.approx(expected, rel=1e-8)

    def test_censored_duration_one_contributes_zero(self):
        """P(D >= 1) = 1: a censored 1-month final spell must add nothing."""
        spells = rf.SpellData(
            soj_state=np.array([0]),
            soj_dur=np.array([1]),
            soj_z=np.zeros((1, 4)),
            soj_censored=np.array([True]),
            trans_from=np.array([], dtype=np.int64),
            trans_to=np.array([], dtype=np.int64),
            trans_z=np.zeros((0, 4)),
        )
        params = {
            "alpha": np.zeros(6),
            "gamma": np.zeros((6, 4)),
            "r": np.full(6, 2.0),
            "trans_a": np.zeros((6, 6)),
            "b_dest": np.zeros((6, 4)),
        }
        assert float(rf.semimarkov_loglik(params, spells)) == pytest.approx(0.0, abs=1e-12)

    def test_scatter_identification(self):
        """Reference cells stay zero: a_{k,EXP} (a_{EXP,SLOW} for row EXP), b_EXP."""
        a = rf.scatter_trans_a(np.arange(1.0, 25.0))
        assert a[0, 1] == 0.0  # EXP row's reference is SLOW
        assert np.all(a[1:, 0] == 0.0)  # every other row's reference is EXP
        assert np.all(np.diag(a) == 0.0)
        assert np.count_nonzero(a) == 24
        b = rf.scatter_trans_b(np.arange(1.0, 21.0))
        assert np.all(b[0] == 0.0)
        assert np.count_nonzero(b) == 20


# --------------------------------------------------------------------------- #
# bootstrap bands + acceptance table
# --------------------------------------------------------------------------- #


def _toy_labels(n: int = 600, seed: int = 3) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(seed))
    labels = []
    state = 0
    while len(labels) < n:
        labels.extend([state] * int(rng.integers(3, 30)))
        state = int(rng.choice([s for s in range(4) if s != state]))
    return np.asarray(labels[:n], dtype=np.int64)


class TestBootstrapBands:
    def test_deterministic_per_seed(self):
        labels = _toy_labels()

        def bands():
            return rf.bootstrap_label_bands(
                labels, n_boot=40, mean_block_months=60, seed=9, band_lo=0.025, band_hi=0.975
            )

        a = bands()
        b = bands()
        for name in ("freq", "median_dur", "p90_dur"):
            np.testing.assert_array_equal(a[name]["lo"], b[name]["lo"])
            np.testing.assert_array_equal(a[name]["hi"], b[name]["hi"])

    def test_historical_frequencies_inside_own_bands(self):
        labels = _toy_labels()
        bands = rf.bootstrap_label_bands(
            labels, n_boot=200, mean_block_months=60, seed=9, band_lo=0.025, band_hi=0.975
        )
        hist = rf.label_run_stats(labels)
        for k in range(4):  # states actually present
            assert bands["freq"]["lo"][k] <= hist["freq"][k] <= bands["freq"]["hi"][k]

    def test_absent_state_bands_are_nan(self):
        labels = _toy_labels()  # states 4, 5 never occur
        bands = rf.bootstrap_label_bands(
            labels, n_boot=40, mean_block_months=60, seed=9, band_lo=0.025, band_hi=0.975
        )
        assert np.isnan(bands["median_dur"]["lo"][5])
        assert bands["median_dur"]["n_valid"][5] == 0


class TestLabelRunStats:
    def test_interior_spells_only(self):
        labels = np.array([0] * 10 + [1] * 4 + [2] * 6 + [0] * 3)
        stats = rf.label_run_stats(labels)
        # first (0 x10) and last (0 x3) runs are dropped as censored
        assert stats["n_spells"][0] == 0
        assert stats["median_dur"][1] == 4.0
        assert stats["median_dur"][2] == 6.0
        assert stats["freq"][0] == pytest.approx(13 / 23)

    def test_pooled_rows(self):
        rows = [np.array([0] * 5 + [1] * 3 + [0] * 5), np.array([1] * 4 + [2] * 7 + [1] * 4)]
        stats = rf.label_run_stats(rows)
        assert stats["n_spells"][1] == 1  # interior run of row 0
        assert stats["n_spells"][2] == 1  # interior run of row 1
        assert stats["freq"][1] == pytest.approx(11 / 28)


class TestAcceptanceRows:
    def test_inside_outside_and_nan(self):
        hist = {
            "freq": np.full(6, 0.2),
            "median_dur": np.full(6, 10.0),
            "p90_dur": np.full(6, 30.0),
        }
        bands = {
            name: {"lo": np.full(6, 5.0), "hi": np.full(6, 15.0), "n_valid": np.full(6, 10)}
            for name in ("freq", "median_dur", "p90_dur")
        }
        bands["freq"] = {"lo": np.full(6, 0.1), "hi": np.full(6, 0.3), "n_valid": np.full(6, 10)}
        sim = {
            "freq": np.array([0.2, 0.05, 0.2, 0.2, 0.2, 0.2]),
            "median_dur": np.array([10.0, 10.0, 40.0, np.nan, 10.0, 10.0]),
            "p90_dur": np.full(6, np.nan),
        }
        rows = rf.acceptance_rows(hist, bands, sim)
        by_key = {(r["stat"], r["regime"]): r for r in rows}
        assert by_key[("freq", "EXP")]["inside"] is True
        assert by_key[("freq", "SLOW")]["inside"] is False
        assert by_key[("median_dur", "REC")]["inside"] is False  # 40 > 15
        assert by_key[("median_dur", "CRI")]["inside"] is None  # NaN
        assert all(r["inside"] is None for r in rows if r["stat"] == "p90_dur")


# --------------------------------------------------------------------------- #
# the smoke fit (end-to-end: NUTS, artifacts, reports, sensitivity)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def smoke_fit(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("regimes-smoke")
    art = _mini_climate_artifact(tmp / "climate")
    access = _access(_mini_series())
    out_dir = tmp / "experiments" / "regimes-smoke"
    result = rf.fit_regimes(
        access,
        _mini_config(),
        climate_artifact=art,
        seed=11,
        vintage_id="test-vintage",
        out_dir=out_dir,
        created_at="2026-07-27",
        report_copy_path=tmp / "regime-fit-report.md",
        sensitivity_report_copy_path=tmp / "regime-sensitivity-report.md",
    )
    return tmp, art, result


class TestFitSmoke:
    def test_artifact_written_and_loadable(self, smoke_fit):
        _, _, result = smoke_fit
        art = sm.load_artifact(result.artifact_path)
        assert art.meta["ruleset_version"] == "regime_ruleset_v1"
        assert art.meta["schema_version"] == rf.ARTIFACT_SCHEMA_VERSION
        assert art.n_draws > 0

    def test_climate_lineage_recorded(self, smoke_fit):
        _, climate_art, result = smoke_fit
        art = sm.load_artifact(result.artifact_path)
        assert art.meta["climate_artifact_sha256"] == climate_art.meta["content_sha256"]
        assert art.meta["slope_psi0"] == pytest.approx(1.5)
        assert art.meta["slope_phi_c0"] == pytest.approx(0.4)

    def test_diagnostics_present(self, smoke_fit):
        _, _, result = smoke_fit
        d = result.diagnostics
        assert np.isfinite(d["max_rhat"]) and d["max_rhat"] > 0.9
        assert d["min_ess"] > 0
        assert d["divergences"] >= 0
        assert len(d["per_param"]) == 6 + 24 + 6 + 24 + 20

    def test_sensitivity_ran(self, smoke_fit):
        _tmp, _, result = smoke_fit
        assert result.label_agreement_v1b is not None
        assert 0.5 < result.label_agreement_v1b < 1.0
        assert result.diagnostics_v1b is not None
        v1b_path = result.artifact_path.with_name(rf.SENSITIVITY_ARTIFACT_FILENAME)
        v1b = sm.load_artifact(v1b_path)
        assert v1b.meta["ruleset_version"] == "regime_ruleset_v1b"

    def test_reports_written_with_copies(self, smoke_fit):
        tmp, _, result = smoke_fit
        report = result.report_path.read_text(encoding="utf-8")
        assert "Empirical transition counts" in report
        assert "generator-side" in report.lower()
        assert "cycle term c_t" in report
        assert (tmp / "regime-fit-report.md").read_text(encoding="utf-8") == report
        sens = result.sensitivity_report_path.read_text(encoding="utf-8")
        assert "regime_ruleset_v1b" in sens
        assert "label agreement rate" in sens
        assert (tmp / "regime-sensitivity-report.md").exists()

    def test_acceptance_table_produced(self, smoke_fit):
        _, _, result = smoke_fit
        assert result.acceptance is not None
        assert len(result.acceptance) == 3 * 6
        judged = [r for r in result.acceptance if r["inside"] is not None]
        assert judged  # at least some bands are judgeable

    def test_experiment_recorded(self, smoke_fit):
        _, _, result = smoke_fit
        exp_dir = result.artifact_path.parent
        assert (exp_dir / "meta.json").exists()
        assert (exp_dir / "config.json").exists()
        metrics = (exp_dir / "metrics.json").read_text(encoding="utf-8")
        assert "max_rhat" in metrics and "label_agreement_v1b" in metrics

    def test_fitted_artifact_simulates(self, smoke_fit):
        """The saved posterior drives the sampler: seeds are reproducible."""
        _, climate_art, result = smoke_fit
        art = sm.load_artifact(result.artifact_path)
        climate = climate_sim.simulate_decades(climate_art, 4, seed=2, months=60)
        a = sm.simulate_regimes(art, climate.states, seed=31)
        b = sm.simulate_regimes(art, climate.states, seed=31)
        np.testing.assert_array_equal(a.labels, b.labels)
        assert np.all(np.abs(a.cycle) <= 1.0)
