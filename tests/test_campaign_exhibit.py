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
    with pytest.raises(ValueError, match=r"prior|measured"):
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


def _window_frame() -> pd.DataFrame:
    """Twelve months, calm lead-in, one violent equity quarter (Q3); ig_level
    is a STATE column (feeds f_dist), not a mapping regressor. The calm
    lead-in matters: the kernel backfills pre-history with the first
    observation, so a window that OPENS with the shock reports it 1:1 — real
    windows open calm, and this fixture mirrors that."""
    idx = pd.date_range("2020-01-31", periods=12, freq="ME")
    zeros = {c: [0.0] * 12 for c in ("smb", "hml", "mom", "d_level", "d_slope", "d_ig")}
    equity = [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, -0.20, -0.10, 0.01, 0.02, 0.02, 0.01]
    ig = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.5, 2.0, 1.5, 1.2, 1.0, 1.0]
    return pd.DataFrame({**zeros, "equity_mkt": equity, "ig_level": ig}, index=idx)


def test_run_window_reports_shallower_marks_and_is_deterministic():
    mapping = ce.load_real_mapping()
    a = ce.run_window("test", _window_frame(), mapping, source="prior")
    b = ce.run_window("test", _window_frame(), mapping, source="prior")
    assert a == b
    assert a.window == "test" and a.source == "prior"
    assert a.quarters == 4
    # marks are shallower than truth (magnitudes)
    assert abs(a.max_dd_reported) <= abs(a.max_dd_true)
    assert a.calls_paid > 0.0 and a.distributions > 0.0


def test_run_window_toggle_changes_the_result():
    mapping = ce.load_real_mapping()
    prior = ce.run_window("test", _window_frame(), mapping, source="prior")
    measured = ce.run_window("test", _window_frame(), mapping, source="measured")
    assert prior != measured


def test_run_window_refuses_windows_beyond_the_cohorts_contract():
    """FOUND on the first real run: full_span (146 quarters) through a single
    mid-life fixture cohort drains the book negative and prints drawdowns
    like -994% - domain artifacts, not results. The loop refuses."""
    mapping = ce.load_real_mapping()
    idx = pd.date_range("1990-01-31", periods=480, freq="ME")
    zeros = {c: [0.0] * 480 for c in ("smb", "hml", "mom", "d_level", "d_slope", "d_ig")}
    frame = pd.DataFrame({**zeros, "equity_mkt": [0.005] * 480, "ig_level": [1.0] * 480}, index=idx)
    with pytest.raises(SystemExit, match="cannot carry"):
        ce.run_window("full_span", frame, mapping, source="prior")


def test_pm_plane_stats_cover_every_mapped_sleeve_and_damp_volatility():
    mapping = ce.load_real_mapping()
    rows = ce.pm_plane_stats("full_span", _window_frame(), mapping, source="prior")
    assert {r.sleeve for r in rows} == set(mapping["pm_sleeves"])
    smoothed = [r for r in rows if r.sleeve != "pm_direct_lending"]  # dl kernel is identity
    assert all(r.vol_reported_annual <= r.vol_true_annual + 1e-12 for r in smoothed)


def test_render_pins_the_guard_text():
    mapping = ce.load_real_mapping()
    results = [
        ce.run_window("gfc", _window_frame(), mapping, source="prior"),
        ce.run_window("gfc", _window_frame(), mapping, source="measured"),
    ]
    text = ce.render_markdown(results, vintage="2026-08-07.5")
    assert "NOT ADOPTED" in text
    assert "2026-08-01.2" in text  # cashflow tiers unchanged by design
    assert "rc_curve" in text and "ER-6" in text
    assert "2026-08-07.5" in text
    assert "exhibit" in text.lower() and "not a gate" in text.lower()
    # every measured row is labelled, every window has a delta row
    assert text.count("NOT ADOPTED") >= 2  # header note + at least the row label
    # ASCII only (the report is served to a cp1252 console world)
    text.encode("ascii")


def test_report_is_committed_and_carries_the_toggle():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "data" / "CAMPAIGN-R1-TRANSLATION.md"
    assert path.exists(), "run scripts/campaign_r1_translation.py"
    text = path.read_text(encoding="utf-8")
    assert "NOT ADOPTED" in text and "2026-08-07.5" in text
    assert "2026-08-01.2" in text and "rc_curve" in text
    for window in ("full_span", "gfc", "covid", "y2022"):
        assert f"`{window}`" in text, f"window {window} missing from the report"


def test_hub_serves_the_campaign_r1_report():
    from ah.hub import DOCS

    rel, title, _ = DOCS["campaign-r1-translation"]
    assert rel == "docs/data/CAMPAIGN-R1-TRANSLATION.md"
    assert "Campaign R1" in title
