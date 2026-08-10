"""WP2.10: the tabulation that carries WP2.11's sealed decision-rule inputs.

These tests are about FIDELITY TO THE SEAL, not about numbers: that the comparison
set is the sealed set, that clause (i)'s NaN rule propagates, that clause (ii) is
measured over the whole comparison set rather than assumed onto family (b), that
the pooled inequality is the sealed inequality, and that the dated historical
reconstruction agrees with the sealed helper element for element.
"""

from __future__ import annotations

import math
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest
import yaml

from ah.eval import ablation as ab
from ah.eval.reference import ReferenceStats

REPO_PREREG = "pre-registration.yaml"


# --------------------------------------------------------------------------- #
# a hand-built report document (the battery's own to_dict() shape)
# --------------------------------------------------------------------------- #


def _row(name, suite, tier, value, *, band=None, severity="report", passed=None, mc=0.0):
    return {
        "name": name,
        "suite": suite,
        "tier": tier,
        "value": value,
        "mc_error": mc,
        "band": band,
        "severity": severity,
        "passed": passed,
        "status": "ok",
        "metadata": {},
    }


def _band(lo, hi, value):
    degenerate = lo == hi
    outside = (
        False
        if (degenerate or not math.isfinite(lo) or not math.isfinite(hi))
        else (math.isnan(value) or not (lo <= value <= hi))
    )
    return {
        "point": (lo + hi) / 2 if math.isfinite(lo) and math.isfinite(hi) else float("nan"),
        "lo": lo,
        "hi": hi,
        "n_resamples": 1000,
        "level": 0.9,
        "tier": "monthly",
        "resample_length": 120,
        "n_valid_resamples": 1000,
        "band_distance": 0.0,
        "band_degenerate": degenerate,
        "band_outside": outside,
    }


D4 = ("sixty_forty", "momentum", "carry", "eqw_factors", "endowment_proxy")
UNCOMPUTABLE = ("eqw_factors", "endowment_proxy")

STRATEGY_STATS = (
    "var_95",
    "es_95",
    "var_99",
    "es_99",
    "elicitability_score",
    "kupiec_pof_lr_1path",
    "kupiec_pof_chi2_tail_1path",
    "christoffersen_independence_lr_1path",
    "christoffersen_independence_chi2_tail_1path",
    "christoffersen_conditional_coverage_lr_1path",
    "christoffersen_conditional_coverage_chi2_tail_1path",
)


def make_report(
    *,
    elicitability=(1.0, 2.0, 3.0),
    td_values=(0.1, 0.2, 0.9),
    td_bands=((0.0, 0.5), (0.0, 0.5), (0.0, 0.5)),
    strategy_bands=False,
    n_paths=1024,
    months=120,
    vintage_id="2026-07-26.1",
    criterion_bearing=True,
    money_pump=0.0,
    floors=0.0,
    memorization_passed=True,
):
    rows = []
    for sid, elic in zip(D4[:3], elicitability, strict=True):
        for stat in STRATEGY_STATS:
            value = {"var_95": 0.06, "es_95": 0.09}.get(stat, 0.5)
            if stat == "elicitability_score":
                value = elic
            band = _band(-10.0, 10.0, value) if strategy_bands else None
            rows.append(_row(f"{sid}.{stat}", "tails", "monthly", value, band=band))
    for sid in D4[3:]:
        for stat in STRATEGY_STATS:
            rows.append(_row(f"{sid}.{stat}", "tails", "monthly", float("nan")))
    pairs = ("cpi~equity_mkt", "cpi~ig_spread", "equity_mkt~ust_10y")
    for pair, value, (lo, hi) in zip(pairs, td_values, td_bands, strict=True):
        rows.append(
            _row(
                f"{pair}.tail_dependence_lower",
                "tails",
                "monthly",
                value,
                band=_band(lo, hi, value),
            )
        )
        rows.append(
            _row(
                f"{pair}.tail_dependence_upper",
                "tails",
                "monthly",
                value,
                band=_band(lo, hi, value),
            )
        )
    rows.append(
        _row(
            "moment_band_exceedance_fraction",
            "monthly",
            "monthly",
            0.3,
            severity="enforce",
            passed=True,
        )
    )
    rows.append(
        _row(
            "variance_ratio_band_exceedance_fraction",
            "horizon",
            "1_5yr",
            0.2,
            severity="enforce",
            passed=True,
        )
    )
    rows.append(
        _row(
            "near_duplicate_fraction",
            "memorization",
            "monthly",
            0.07,
            severity="enforce",
            passed=memorization_passed,
        )
    )
    rows.append(
        _row(
            "membership_inference_auc",
            "memorization",
            "monthly",
            0.51,
            severity="enforce",
            passed=memorization_passed,
        )
    )
    rows.append(
        _row(
            "money_pump_violations",
            "economics",
            "economic",
            money_pump,
            severity="enforce",
            passed=money_pump == 0.0,
        )
    )
    rows.append(
        _row(
            "floor_violations",
            "economics",
            "economic",
            floors,
            severity="enforce",
            passed=floors == 0.0,
        )
    )
    tiers: dict[str, list] = {}
    for row in rows:
        tiers.setdefault(row["tier"], []).append(row)
    return {
        "n_paths": n_paths,
        "months": months,
        "vintage_id": vintage_id,
        "criterion_bearing": criterion_bearing,
        "prereg_verified": True,
        "prereg_digest": "sha256:deadbeef",
        "unfiltered": {"tiers": tiers},
        "filtered": {"tiers": tiers},
    }


# --------------------------------------------------------------------------- #
# the comparison set
# --------------------------------------------------------------------------- #


def test_the_comparison_set_keeps_the_computable_strategies_and_drops_the_others():
    """The seal says 'the five d4_strategies MINUS uncomputable', so what remains on
    this vintage is sixty_forty / momentum / carry -- not the other way round."""
    cset = ab.comparison_set(
        make_report(), d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE
    )
    assert cset.strategy_ids == ("sixty_forty", "momentum", "carry")
    assert cset.excluded_strategy_ids == ("endowment_proxy", "eqw_factors")
    assert cset.elicitability_names == (
        "sixty_forty.elicitability_score",
        "momentum.elicitability_score",
        "carry.elicitability_score",
    )
    # family (a) restricted: eleven names per kept strategy, and nothing else
    assert len(cset.strategy_names) == 3 * len(STRATEGY_STATS)
    assert not any("eqw_factors" in n for n in cset.strategy_names)
    # family (b): every cross-block tail-dependence name
    assert len(cset.band_names) == 6
    assert all(n.rsplit(".", 1)[-1] in ab.BAND_FAMILY_SUFFIXES for n in cset.band_names)


def test_the_sealed_documents_uncomputable_list_is_the_one_this_module_expects():
    """Pinned against the real sealed file, so a vintage change is caught here --
    and one did: campaign-3 (AM-2026-08-10-001) emptied the list. Through
    campaign-2 this asserted {eqw_factors, endowment_proxy}; commodities'
    sourcing (ruling K2) restored both, so ALL FIVE strategies are kept and
    the assertion is updated to the new truth rather than relaxed."""
    import pathlib

    doc = yaml.safe_load(pathlib.Path(REPO_PREREG).read_text(encoding="utf-8"))
    uncomputable = tuple(doc["reference_run"]["uncomputable_d4_strategies"])
    sealed_ids = tuple(doc["d4_strategies"])
    assert len(sealed_ids) == 5
    assert uncomputable == ()
    kept = [sid for sid in sealed_ids if sid not in set(uncomputable)]
    assert sorted(kept) == ["carry", "endowment_proxy", "eqw_factors", "momentum", "sixty_forty"]


def test_the_comparison_set_raises_when_a_named_metric_is_absent():
    report = make_report()
    for tier_rows in report["unfiltered"]["tiers"].values():
        tier_rows[:] = [r for r in tier_rows if r["name"] != "carry.elicitability_score"]
    with pytest.raises(ab.AblationError, match="missing comparison-set metrics"):
        ab.comparison_set(report, d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE)


# --------------------------------------------------------------------------- #
# clause (i)
# --------------------------------------------------------------------------- #


def test_clause_i_is_the_mean_over_the_comparison_sets_strategies():
    report = make_report(elicitability=(1.0, 2.0, 6.0))
    cset = ab.comparison_set(report, d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE)
    out = ab.clause_i(report, cset)
    assert out["n_strategies"] == 3
    assert out["mean"] == pytest.approx(3.0)
    assert out["has_nan"] is False


def test_clause_i_propagates_a_nan_rather_than_dropping_the_strategy():
    """The sealed NaN rule: a NaN makes the seed NOT a beat -- not a tie, not an
    exclusion. A nanmean here would silently convert a non-beat into a beat."""
    report = make_report(elicitability=(1.0, float("nan"), 3.0))
    cset = ab.comparison_set(report, d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE)
    out = ab.clause_i(report, cset)
    assert out["has_nan"] is True
    assert math.isnan(out["mean"])


# --------------------------------------------------------------------------- #
# clause (ii)
# --------------------------------------------------------------------------- #


def test_clause_ii_counts_only_usable_bands():
    report = make_report(
        td_values=(0.9, 0.2, 0.9),
        td_bands=((0.0, 0.5), (0.0, 0.5), (0.3, 0.3)),  # third is DEGENERATE
    )
    cset = ab.comparison_set(report, d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE)
    out = ab.clause_ii(report, cset)
    assert out["n_usable_cross_block_bands"] == 4  # the degenerate pair's two drop out
    assert out["count"] == 2  # only the first pair's lower+upper are outside
    assert out["outside_names"] == [
        "cpi~equity_mkt.tail_dependence_lower",
        "cpi~equity_mkt.tail_dependence_upper",
    ]


def test_clause_ii_measures_the_seals_disclosure_rather_than_assuming_it():
    """The seal DISCLOSES that zero strategy-level metrics enter clause (ii). The
    loop must range over the whole comparison set so that is a finding."""
    plain = make_report()
    cset = ab.comparison_set(plain, d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE)
    out = ab.clause_ii(plain, cset)
    assert out["n_usable_strategy_bands"] == 0
    assert out["seal_disclosure_holds"] is True
    assert out["n_comparison_set_names"] == len(cset.strategy_names) + len(cset.band_names)

    # If a strategy statistic ever DID acquire a band, the count would notice.
    banded = make_report(strategy_bands=True)
    cset2 = ab.comparison_set(banded, d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE)
    out2 = ab.clause_ii(banded, cset2)
    assert out2["n_usable_strategy_bands"] == 33
    assert out2["seal_disclosure_holds"] is False


def test_clause_ii_treats_a_nan_value_inside_a_usable_band_as_outside():
    """``outside_band``'s NaN half: the battery already recorded it; do not undo it."""
    report = make_report(td_values=(float("nan"), 0.2, 0.2))
    cset = ab.comparison_set(report, d4_strategy_ids=D4, uncomputable_strategy_ids=UNCOMPUTABLE)
    assert ab.clause_ii(report, cset)["count"] == 2


# --------------------------------------------------------------------------- #
# the pooled route
# --------------------------------------------------------------------------- #


def test_pooled_difference_is_the_sealed_inequality_with_ddof_one():
    out = ab.pooled_difference([-1.0, -2.0, -3.0])
    assert out["mean_d"] == pytest.approx(-2.0)
    assert out["sd_d_ddof1"] == pytest.approx(1.0)
    assert out["mean_is_negative"] is True
    assert out["abs_mean_exceeds_sd"] is True
    assert out["pooled_beat"] is True


def test_pooled_difference_fails_when_dispersion_swamps_the_mean():
    out = ab.pooled_difference([-1.0, 4.0, -6.0])
    assert out["mean_d"] == pytest.approx(-1.0)
    assert out["sd_d_ddof1"] == pytest.approx(float(np.std([-1.0, 4.0, -6.0], ddof=1)))
    assert out["pooled_beat"] is False


def test_pooled_difference_does_not_beat_on_a_positive_mean():
    assert ab.pooled_difference([1.0, 1.0, 1.0])["pooled_beat"] is False


def test_pooled_difference_reports_nan_sd_for_a_single_seed():
    out = ab.pooled_difference([-1.0])
    assert math.isnan(out["sd_d_ddof1"])
    assert out["pooled_beat"] is False


# --------------------------------------------------------------------------- #
# clauses (2)-(4) and criterion_bearing
# --------------------------------------------------------------------------- #


def test_enforce_rows_can_be_restricted_to_the_regression_tiers():
    rows = ab.enforce_rows(make_report(), tiers=ab.REGRESSION_TIERS)
    assert {r["tier"] for r in rows} == {"monthly", "1_5yr"}
    assert all(r["passed"] is not None for r in rows)


def test_memorization_enforce_lists_every_memorization_threshold():
    rows = ab.memorization_enforce(make_report())
    assert [r["name"] for r in rows] == ["membership_inference_auc", "near_duplicate_fraction"]
    assert all(r["passed"] is True for r in rows)
    assert all(
        r["passed"] is False
        for r in ab.memorization_enforce(make_report(memorization_passed=False))
    )


def test_constraint_violations_demands_exact_zero():
    ok = ab.constraint_violations(make_report())
    assert ok["all_zero"] is True
    bad = ab.constraint_violations(make_report(floors=1.0))
    assert bad["floor_violations"]["is_zero"] is False
    assert bad["all_zero"] is False


def test_constraint_violations_refuses_a_report_that_simply_lacks_the_metric():
    report = make_report()
    for tier_rows in report["unfiltered"]["tiers"].values():
        tier_rows[:] = [r for r in tier_rows if r["name"] != "floor_violations"]
    with pytest.raises(ab.AblationError, match="clause \\(4\\) is unevaluable"):
        ab.constraint_violations(report)


def test_criterion_bearing_names_the_condition_that_failed():
    def check(report):
        return ab.criterion_bearing(
            report,
            expected_n_paths=1024,
            expected_months=120,
            expected_vintage_id="2026-07-26.1",
        )

    assert check(make_report())["ok"] is True
    small = check(make_report(n_paths=64, criterion_bearing=False))
    assert small["ok"] is False
    assert small["n_paths"] is False
    assert small["months"] is True
    stale = check(make_report(vintage_id="2026-07-24.1", criterion_bearing=False))
    assert stale["vintage_id"] is False


def test_criterion_bearing_refuses_a_report_with_no_ensemble_size():
    """``BatteryReport.to_dict()`` does not serialize n_paths/months. Echoing the
    composite flag alone would defeat the point of naming the failing condition."""
    report = make_report()
    del report["n_paths"]
    with pytest.raises(ab.AblationError, match="carries no ensemble size"):
        ab.criterion_bearing(
            report,
            expected_n_paths=1024,
            expected_months=120,
            expected_vintage_id="2026-07-26.1",
        )


# --------------------------------------------------------------------------- #
# the draw-span-restricted elicitability
# --------------------------------------------------------------------------- #


def _synthetic_reference(months: int = 480) -> ReferenceStats:
    dates = pd.date_range("1981-01-01", periods=months, freq="MS")
    rng = np.random.Generator(np.random.PCG64(4))
    series = {
        "equity_mkt": pd.Series(rng.normal(0.006, 0.04, months), index=dates),
        "ust_10y": pd.Series(4.0 + rng.normal(0, 0.2, months), index=dates),
        "policy_rate": pd.Series(3.0 + rng.normal(0, 0.2, months), index=dates),
    }
    return ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=("global", "us"),
        vintage_id="test-vintage",
        n_resamples=10,
        seed=1,
        missing_factors=(),
        historical_series=MappingProxyType(series),
    )


def test_the_dated_reconstruction_agrees_with_the_sealed_helper_element_for_element():
    """This is the load-bearing test for the draw-span disclosure: the restricted
    score is only trustworthy if the UNRESTRICTED reconstruction is the sealed one."""
    from ah.eval.metrics.tails import _historical_strategy_returns
    from ah.strategies import load_d4_strategies, load_derived_series

    reference = _synthetic_reference()
    derived = load_derived_series()
    checked = 0
    for strategy in load_d4_strategies():
        sealed = _historical_strategy_returns(reference, strategy, derived)
        mine = ab.historical_strategy_returns_dated(reference, strategy, derived)
        if sealed is None:
            assert mine is None
            continue
        assert mine is not None
        index, values = mine
        assert len(index) == values.size
        np.testing.assert_array_equal(values, np.asarray(sealed).reshape(-1))
        checked += 1
    assert checked >= 1, "no D4 strategy was computable on the synthetic reference"


def test_restricting_the_window_changes_the_score_and_uses_the_sealed_function():
    from ah.eval.metrics.tails import elicitability_score

    rng = np.random.Generator(np.random.PCG64(9))
    realizations = rng.normal(0.005, 0.05, 480)
    full = ab.restricted_elicitability(realizations, 0.08, 0.11)
    assert full == pytest.approx(elicitability_score(realizations, 0.08, 0.11, 0.95))
    window = ab.restricted_elicitability(realizations[120:], 0.08, 0.11)
    assert window != pytest.approx(full)


def test_strategy_forecast_pair_reads_the_reports_own_var95_es95():
    report = make_report()
    var, es = ab.strategy_forecast_pair(report, "momentum")
    assert (var, es) == (0.06, 0.09)
    with pytest.raises(ab.AblationError, match="no var_95/es_95"):
        ab.strategy_forecast_pair(report, "not_a_strategy")


# --------------------------------------------------------------------------- #
# the leakage guard still holds
# --------------------------------------------------------------------------- #


def test_ablation_never_reaches_the_holdout_token():
    """``ah.eval.ablation`` reads stored reports. It must not import the mint."""
    import ast
    import pathlib

    src = pathlib.Path("src/ah/eval/ablation.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "ah.eval.g2" not in imported
    assert "FinalEvaluationToken" not in src
