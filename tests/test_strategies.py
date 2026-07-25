"""WP2.1b Task 2 acceptance: the D4 benchmark-strategy set and its derived series,
loaded from ``pre-registration.yaml`` and defined purely over generated factors.

The D4 set is what tail-fidelity VaR/ES is computed on (``ah/eval/metrics/tails.py``)
and what the WP2.8 tail auxiliary loss optimizes. Both must load the *same object*
from the *same* ``pre-registration.yaml``, which is what
``test_load_d4_strategies_is_cached_by_identity`` below stands in for (see
Instructions/WP2.1b-PRE-SEAL-PATCH.md Item 1 acceptance).

Everything this file asserts is about to be frozen by the WP2.3 seal, so the tests
lean hard on the properties that make the sealed file self-sufficient: no code-side
default for a sealed parameter, no silently-dropped key, no duplicate id, no rule
target factor hidden in code, and no level factor entering a portfolio except through
a declared derived series.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from ah.eval.metrics import tails
from ah.factors import load_manifest
from ah.strategies import (
    KNOWN_RULES,
    KNOWN_TRANSFORMS,
    Conventions,
    DerivedSeries,
    Strategy,
    StrategyError,
    load_conventions,
    load_d4_strategies,
    load_derived_series,
)

_EXPECTED_IDS = {"eqw_factors", "sixty_forty", "endowment_proxy", "momentum", "carry"}
_EXPECTED_DERIVED = {"govt_tr_10y", "credit_xs_hy", "cash_tr_1m"}

_DERIVED_BLOCK = """derived_series:
  govt_tr_10y:
    from: ust_10y
    transform: bond_total_return
    params: {duration_years: 8.5}
    formula: "r_t = 0.01 * ( y_{t-1}/12 - D*(y_t - y_{t-1}) )"
    notes: fixture
"""

# A complete, self-contained `conventions:` block for fixtures that exercise
# conventions-driven behaviour (level-factor rejection, rebalance cadences, ...). The
# factor classification must cover exactly the REAL active factor set: `load_manifest()`
# always reads the real repo-root `factors.yaml`, never a fixture-local one, so this
# has to match it (global + us blocks, 14 factors) regardless of which
# `pre-registration.yaml` fixture it is embedded in.
_CONVENTIONS_BLOCK = """conventions:
  percent_to_decimal: 0.01
  months_per_year: 12.0
  return_bearing_factors: [equity_mkt, smb, hml, mom, commodities]
  level_factors: [policy_rate, ust_2y, ust_10y, cpi, hqm_curve, ig_spread, hy_spread, funding_spread, equity_vol]
  rebalance_cadences: [monthly]
  static_weights_composition: fixture
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "pre-registration.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# the sealed set itself
# --------------------------------------------------------------------------- #


def test_load_d4_strategies_returns_exactly_the_five_ids() -> None:
    strategies = load_d4_strategies()
    assert {s.strategy_id for s in strategies} == _EXPECTED_IDS
    assert len(strategies) == 5


def test_load_d4_strategies_is_cached_by_identity() -> None:
    assert load_d4_strategies() is load_d4_strategies()


def test_load_derived_series_is_cached_by_identity() -> None:
    assert load_derived_series() is load_derived_series()


def test_static_weight_strategies_sum_to_one() -> None:
    for strategy in load_d4_strategies():
        if strategy.kind == "static_weights":
            assert sum(strategy.weights.values()) == pytest.approx(1.0, abs=1e-9), (
                strategy.strategy_id
            )


def test_rule_strategies_have_empty_weights() -> None:
    for strategy in load_d4_strategies():
        if strategy.kind == "rule":
            assert strategy.weights == {}


def test_every_referenced_series_is_an_active_factor_or_a_derived_series() -> None:
    """Replaces the older 'every referenced factor is active' assertion.

    A weight key may now name either an active factor or a declared derived series
    (CRITICAL 1), so the invariant is membership in the union -- and, separately, that
    every derived series sources an *active* factor.
    """
    active = set(load_manifest().active_factors())
    derived = load_derived_series()
    known = active | set(derived)
    for strategy in load_d4_strategies():
        for series in strategy.weights:
            assert series in known, f"{strategy.strategy_id} references unknown '{series}'"
    for series in derived.values():
        assert series.source_factor in active, series.series_id


def test_no_level_factor_is_weighted_directly() -> None:
    """The defect this whole layer exists to prevent: a level summed with returns.

    IMPORTANT 2 fix: driven from the sealed `conventions.level_factors`, not a
    hand-maintained frozenset duplicating the YAML prose in this test file.
    """
    level_factors = load_conventions().level_factors
    for strategy in load_d4_strategies():
        leaked = level_factors & set(strategy.weights)
        assert not leaked, (
            f"{strategy.strategy_id} weights level factor(s) {sorted(leaked)} directly; "
            f"levels may enter only through a declared derived series"
        )


# --------------------------------------------------------------------------- #
# CRITICAL 1 -- derived series
# --------------------------------------------------------------------------- #


def test_sealed_derived_series_are_exactly_the_three_declared() -> None:
    derived = load_derived_series()
    assert set(derived) == _EXPECTED_DERIVED
    assert all(isinstance(s, DerivedSeries) for s in derived.values())


def test_sealed_derived_series_parameters_are_the_sealed_values() -> None:
    derived = load_derived_series()
    assert derived["govt_tr_10y"].source_factor == "ust_10y"
    assert derived["govt_tr_10y"].transform == "bond_total_return"
    assert derived["govt_tr_10y"].params["duration_years"] == pytest.approx(8.5)
    assert derived["credit_xs_hy"].source_factor == "hy_spread"
    assert derived["credit_xs_hy"].transform == "spread_excess_return"
    assert derived["credit_xs_hy"].params["spread_duration_years"] == pytest.approx(4.0)
    # The funding leg of `carry`: cash is a zero-duration bond, so the general bond
    # formula collapses to pure carry -- no third transform needed.
    assert derived["cash_tr_1m"].source_factor == "policy_rate"
    assert derived["cash_tr_1m"].transform == "bond_total_return"
    assert derived["cash_tr_1m"].params["duration_years"] == pytest.approx(0.0)


def test_every_derived_series_states_its_formula() -> None:
    for series in load_derived_series().values():
        assert series.formula.strip(), series.series_id
        assert "r_t" in series.formula, series.series_id
        # The single percent-to-decimal conversion must be visible in the sealed formula.
        assert "0.01" in series.formula, series.series_id


def test_sixty_forty_holds_the_derived_government_total_return() -> None:
    strategy = {s.strategy_id: s for s in load_d4_strategies()}["sixty_forty"]
    assert dict(strategy.weights) == {"equity_mkt": 0.6, "govt_tr_10y": 0.4}


def test_endowment_proxy_holds_derived_govt_and_credit_legs() -> None:
    strategy = {s.strategy_id: s for s in load_d4_strategies()}["endowment_proxy"]
    assert dict(strategy.weights) == {
        "equity_mkt": 0.65,
        "govt_tr_10y": 0.10,
        "credit_xs_hy": 0.15,
        "commodities": 0.10,
    }


def test_carry_legs_are_both_derived_series() -> None:
    strategy = {s.strategy_id: s for s in load_d4_strategies()}["carry"]
    derived = load_derived_series()
    assert strategy.params["long_series"] == "govt_tr_10y"
    assert strategy.params["funding_series"] == "cash_tr_1m"
    assert strategy.params["long_series"] in derived
    assert strategy.params["funding_series"] in derived


def test_unknown_transform_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "derived_series:\n"
        "  x:\n"
        "    from: ust_10y\n"
        "    transform: not_a_transform\n"
        "    params: {duration_years: 8.5}\n"
        "    formula: whatever\n",
    )
    with pytest.raises(StrategyError, match="not implemented"):
        load_derived_series(bad)


def test_derived_series_from_inactive_factor_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "derived_series:\n"
        "  x:\n"
        "    from: gilt_nominal_10y\n"
        "    transform: bond_total_return\n"
        "    params: {duration_years: 8.5}\n"
        "    formula: f\n",
    )
    with pytest.raises(StrategyError, match="unknown or inactive"):
        load_derived_series(bad)


def test_derived_series_missing_required_param_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "derived_series:\n"
        "  x:\n"
        "    from: ust_10y\n"
        "    transform: bond_total_return\n"
        "    params: {}\n"
        "    formula: f\n",
    )
    with pytest.raises(StrategyError, match="missing required parameter"):
        load_derived_series(bad)


def test_derived_series_unknown_key_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "derived_series:\n"
        "  x:\n"
        "    from: ust_10y\n"
        "    transform: bond_total_return\n"
        "    params: {duration_years: 8.5}\n"
        "    formula: f\n"
        "    formla: typo\n",
    )
    with pytest.raises(StrategyError, match="unknown key"):
        load_derived_series(bad)


def test_strategy_may_weight_a_declared_derived_series(tmp_path: Path) -> None:
    good = _write(
        tmp_path,
        _DERIVED_BLOCK + "d4_strategies:\n"
        "  s:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 0.6, govt_tr_10y: 0.4}\n"
        "    params: {}\n"
        "    notes: fixture\n",
    )
    (strategy,) = load_d4_strategies(good)
    assert dict(strategy.weights) == {"equity_mkt": 0.6, "govt_tr_10y": 0.4}


def test_undeclared_derived_series_in_weights_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  s:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 0.6, govt_tr_10y: 0.4}\n"
        "    params: {}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="unknown series"):
        load_d4_strategies(bad)


# --------------------------------------------------------------------------- #
# existing validation, retained
# --------------------------------------------------------------------------- #


def test_unknown_factor_raises_strategy_error(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  bogus:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {not_a_real_factor: 1.0}\n"
        "    params: {}\n"
        "    notes: test fixture\n",
    )
    with pytest.raises(StrategyError):
        load_d4_strategies(bad)


def test_static_weights_not_summing_to_one_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  bogus:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 0.5, smb: 0.2}\n"
        "    params: {}\n"
        "    notes: test fixture\n",
    )
    with pytest.raises(StrategyError):
        load_d4_strategies(bad)


def test_unknown_rule_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  bogus:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: 12\n"
        "    rule: not_a_real_rule\n"
        "    weights: {}\n"
        "    params: {}\n"
        "    notes: test fixture\n",
    )
    with pytest.raises(StrategyError):
        load_d4_strategies(bad)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(StrategyError):
        load_d4_strategies(tmp_path / "does-not-exist.yaml")


def test_strategy_is_frozen_dataclass() -> None:
    strategy = load_d4_strategies()[0]
    assert isinstance(strategy, Strategy)
    with pytest.raises(dataclasses.FrozenInstanceError):
        strategy.kind = "rule"  # type: ignore[misc]


def test_derived_series_is_frozen_dataclass() -> None:
    series = load_derived_series()["govt_tr_10y"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        series.transform = "spread_excess_return"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# FINDING 4 -- lookback is declared exactly once
# --------------------------------------------------------------------------- #


def test_momentum_declares_lookback_in_the_field_not_in_params() -> None:
    strategy = {s.strategy_id: s for s in load_d4_strategies()}["momentum"]
    assert strategy.lookback == 12
    assert "lookback_months" not in strategy.params


def test_lookback_months_in_params_is_rejected(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  momentum:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: 12\n"
        "    rule: momentum_12_1\n"
        "    weights: {}\n"
        "    params: {target_series: equity_mkt, skip_months: 1, lookback_months: 12}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="declared exactly once"):
        load_d4_strategies(bad)


def test_rule_requiring_lookback_rejects_null(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  momentum:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: momentum_12_1\n"
        "    weights: {}\n"
        "    params: {target_series: equity_mkt, skip_months: 1}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="requires a non-null"):
        load_d4_strategies(bad)


# --------------------------------------------------------------------------- #
# FINDING 5 -- sealed parameters never fall back to code-side defaults
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("params", "missing"),
    [
        ("{funding_series: cash_tr_1m, long_weight: 1.0, funding_weight: -1.0}", "long_series"),
        (
            "{long_series: govt_tr_10y, funding_series: cash_tr_1m, funding_weight: -1.0}",
            "long_weight",
        ),
        (
            "{long_series: govt_tr_10y, funding_series: cash_tr_1m, long_weight: 1.0}",
            "funding_weight",
        ),
    ],
)
def test_missing_rule_parameter_raises_naming_it(tmp_path: Path, params: str, missing: str) -> None:
    bad = _write(
        tmp_path,
        _DERIVED_BLOCK + "  cash_tr_1m:\n"
        "    from: policy_rate\n"
        "    transform: bond_total_return\n"
        "    params: {duration_years: 0.0}\n"
        "    formula: f\n"
        "d4_strategies:\n"
        "  carry:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: term_structure_carry\n"
        "    weights: {}\n"
        f"    params: {params}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match=missing):
        load_d4_strategies(bad)


def test_extra_rule_parameter_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  momentum:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: 12\n"
        "    rule: momentum_12_1\n"
        "    weights: {}\n"
        "    params: {target_series: equity_mkt, skip_months: 1, gain: 2.0}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="unknown parameter"):
        load_d4_strategies(bad)


# --------------------------------------------------------------------------- #
# FINDING 6 -- unknown keys are a hard error
# --------------------------------------------------------------------------- #


def test_misspelled_weights_key_is_rejected(tmp_path: Path) -> None:
    """`weigths:` in a file whose entire purpose is to be hashed must not pass."""
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  s:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weigths: {equity_mkt: 1.0}\n"
        "    params: {}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="unknown key"):
        load_d4_strategies(bad)


def test_misspelled_params_key_is_rejected(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  momentum:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: 12\n"
        "    rule: momentum_12_1\n"
        "    weights: {}\n"
        "    parms: {target_series: equity_mkt, skip_months: 1}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="unknown key"):
        load_d4_strategies(bad)


def test_proxy_mapping_is_an_allowed_key() -> None:
    strategy = {s.strategy_id: s for s in load_d4_strategies()}["endowment_proxy"]
    assert set(strategy.proxy_mapping) == {"equity", "reits", "govt", "credit", "commodities"}


# --------------------------------------------------------------------------- #
# FINDING 7 -- rule target series are sealed data, validated at load
# --------------------------------------------------------------------------- #


def test_momentum_target_series_is_sealed_in_params() -> None:
    strategy = {s.strategy_id: s for s in load_d4_strategies()}["momentum"]
    assert strategy.params["target_series"] == "equity_mkt"


def test_rule_target_series_naming_an_inactive_factor_raises(tmp_path: Path) -> None:
    """Deactivating a block must break the load, not the metric run."""
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  momentum:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: 12\n"
        "    rule: momentum_12_1\n"
        "    weights: {}\n"
        "    params: {target_series: bank_rate, skip_months: 1}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="unknown series"):
        load_d4_strategies(bad)


def test_every_sealed_series_param_resolves() -> None:
    known = set(load_manifest().active_factors()) | set(load_derived_series())
    for strategy in load_d4_strategies():
        for key, value in strategy.params.items():
            if key.endswith("_series"):
                assert value in known, f"{strategy.strategy_id}.{key} -> {value!r}"


# --------------------------------------------------------------------------- #
# FINDING 9 -- duplicate ids
# --------------------------------------------------------------------------- #


def test_duplicate_strategy_id_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  momentum:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 1.0}\n"
        "    params: {}\n"
        "    notes: first\n"
        "  momentum:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {smb: 1.0}\n"
        "    params: {}\n"
        "    notes: second\n",
    )
    with pytest.raises(StrategyError, match="duplicate key 'momentum'"):
        load_d4_strategies(bad)


def test_duplicate_derived_series_id_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "derived_series:\n"
        "  govt_tr_10y:\n"
        "    from: ust_10y\n"
        "    transform: bond_total_return\n"
        "    params: {duration_years: 8.5}\n"
        "    formula: f\n"
        "  govt_tr_10y:\n"
        "    from: ust_2y\n"
        "    transform: bond_total_return\n"
        "    params: {duration_years: 1.9}\n"
        "    formula: f\n",
    )
    with pytest.raises(StrategyError, match="duplicate key 'govt_tr_10y'"):
        load_derived_series(bad)


# --------------------------------------------------------------------------- #
# M1 -- proxy_mapping rolls up to weights
# --------------------------------------------------------------------------- #


def test_proxy_mapping_rolls_up_to_the_flat_weights() -> None:
    strategy = {s.strategy_id: s for s in load_d4_strategies()}["endowment_proxy"]
    rollup: dict[str, float] = {}
    for sleeve in strategy.proxy_mapping.values():
        rollup[sleeve.factor] = rollup.get(sleeve.factor, 0.0) + sleeve.weight
    assert set(rollup) == set(strategy.weights)
    for series, weight in strategy.weights.items():
        assert rollup[series] == pytest.approx(weight, abs=1e-9), series
    assert sum(s.weight for s in strategy.proxy_mapping.values()) == pytest.approx(1.0, abs=1e-9)


def test_proxy_mapping_that_does_not_roll_up_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  s:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 0.6, smb: 0.4}\n"
        "    params: {}\n"
        "    proxy_mapping:\n"
        "      a: {weight: 0.5, factor: equity_mkt, reason: r}\n"
        "      b: {weight: 0.4, factor: smb, reason: r}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="rolls up to"):
        load_d4_strategies(bad)


def test_proxy_mapping_naming_a_series_absent_from_weights_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "d4_strategies:\n"
        "  s:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 1.0}\n"
        "    params: {}\n"
        "    proxy_mapping:\n"
        "      a: {weight: 1.0, factor: smb, reason: r}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="is not in"):
        load_d4_strategies(bad)


# --------------------------------------------------------------------------- #
# M2 -- the declaration and the dispatch agree
# --------------------------------------------------------------------------- #


def test_known_rules_matches_the_tails_dispatch() -> None:
    assert set(tails._DISPATCH) == KNOWN_RULES


def test_known_transforms_matches_the_tails_transform_dispatch() -> None:
    assert set(tails._TRANSFORM_DISPATCH) == KNOWN_TRANSFORMS


# --------------------------------------------------------------------------- #
# Fix pass 2, IMPORTANT 1 -- percent_to_decimal and months_per_year are sealed data
# --------------------------------------------------------------------------- #


def test_conventions_declares_percent_to_decimal_and_months_per_year() -> None:
    conventions = load_conventions()
    assert conventions.percent_to_decimal == pytest.approx(0.01)
    assert conventions.months_per_year == pytest.approx(12.0)


def test_tails_pct_to_decimal_and_months_per_year_match_sealed_conventions() -> None:
    """The claim `pre-registration.yaml` makes about itself, machine-checked: the
    transform module is driven by the sealed conventions, not by independent
    constants that an amendment could no-op past."""
    conventions = load_conventions()
    assert pytest.approx(conventions.percent_to_decimal) == tails._PCT_TO_DECIMAL
    assert pytest.approx(conventions.months_per_year) == tails._MONTHS_PER_YEAR


def test_conventions_missing_months_per_year_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "conventions:\n"
        "  percent_to_decimal: 0.01\n"
        "  return_bearing_factors: [equity_mkt]\n"
        "  level_factors: [ust_10y]\n"
        "  rebalance_cadences: [monthly]\n"
        "  static_weights_composition: fixture\n",
    )
    with pytest.raises(StrategyError, match="months_per_year"):
        load_conventions(bad)


def test_conventions_missing_percent_to_decimal_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "conventions:\n"
        "  months_per_year: 12.0\n"
        "  return_bearing_factors: [equity_mkt]\n"
        "  level_factors: [ust_10y]\n"
        "  rebalance_cadences: [monthly]\n"
        "  static_weights_composition: fixture\n",
    )
    with pytest.raises(StrategyError, match="percent_to_decimal"):
        load_conventions(bad)


def test_conventions_absent_block_loads_a_permissive_default(tmp_path: Path) -> None:
    """A file with no `conventions:` key at all (most hand-written test fixtures in
    this file) must not error -- only the real `pre-registration.yaml` is required to
    declare the full block."""
    bad = _write(tmp_path, "d4_strategies:\n  x:\n    kind: static_weights\n")
    conventions = load_conventions(bad)
    assert conventions == Conventions(
        percent_to_decimal=0.01,
        months_per_year=12.0,
        return_bearing_factors=frozenset(),
        level_factors=frozenset(),
        rebalance_cadences=frozenset(),
        static_weights_composition="",
    )


def test_load_conventions_is_cached_by_identity() -> None:
    assert load_conventions() is load_conventions()


# --------------------------------------------------------------------------- #
# Fix pass 2, IMPORTANT 2 (subsumes MINOR 3) -- level-vs-return classification is
# sealed data, exhaustive over the active factor set, and enforced at load time
# --------------------------------------------------------------------------- #


def test_conventions_classification_is_exhaustive_and_disjoint_over_active_factors() -> None:
    conventions = load_conventions()
    active = frozenset(load_manifest().active_factors())
    assert conventions.return_bearing_factors | conventions.level_factors == active
    assert not (conventions.return_bearing_factors & conventions.level_factors)


def test_conventions_level_factors_includes_cpi_and_equity_vol() -> None:
    """MINOR 3: the prose previously omitted these two; the sealed list must not."""
    assert {"cpi", "equity_vol"} <= load_conventions().level_factors


def test_level_factor_in_weights_raises_naming_it(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        _CONVENTIONS_BLOCK + "d4_strategies:\n"
        "  s:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 0.6, ust_10y: 0.4}\n"
        "    params: {}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="ust_10y"):
        load_d4_strategies(bad)


def test_conventions_classification_missing_a_factor_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "conventions:\n"
        "  percent_to_decimal: 0.01\n"
        "  months_per_year: 12.0\n"
        "  return_bearing_factors: [equity_mkt, smb, hml, mom, commodities]\n"
        "  level_factors: [policy_rate, ust_2y, ust_10y, cpi, hqm_curve, ig_spread, hy_spread, funding_spread]\n"
        "  rebalance_cadences: [monthly]\n"
        "  static_weights_composition: fixture\n",
    )
    with pytest.raises(StrategyError, match="equity_vol"):
        load_conventions(bad)


def test_conventions_classification_overlap_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        "conventions:\n"
        "  percent_to_decimal: 0.01\n"
        "  months_per_year: 12.0\n"
        "  return_bearing_factors: [equity_mkt, smb, hml, mom, commodities, ust_10y]\n"
        "  level_factors: [policy_rate, ust_2y, ust_10y, cpi, hqm_curve, ig_spread, hy_spread, funding_spread, equity_vol]\n"
        "  rebalance_cadences: [monthly]\n"
        "  static_weights_composition: fixture\n",
    )
    with pytest.raises(StrategyError, match="ust_10y"):
        load_conventions(bad)


# --------------------------------------------------------------------------- #
# Fix pass 2, MINOR 4 -- `rebalance` is sealed data the loader reads
# --------------------------------------------------------------------------- #


def test_conventions_declares_monthly_as_a_rebalance_cadence() -> None:
    assert "monthly" in load_conventions().rebalance_cadences


def test_every_sealed_strategy_uses_a_declared_rebalance_cadence() -> None:
    cadences = load_conventions().rebalance_cadences
    for strategy in load_d4_strategies():
        assert strategy.rebalance in cadences, strategy.strategy_id


def test_rebalance_outside_declared_cadences_raises(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        _CONVENTIONS_BLOCK + "d4_strategies:\n"
        "  s:\n"
        "    kind: static_weights\n"
        "    rebalance: quarterly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights: {equity_mkt: 1.0}\n"
        "    params: {}\n"
        "    notes: fixture\n",
    )
    with pytest.raises(StrategyError, match="rebalance"):
        load_d4_strategies(bad)


# --------------------------------------------------------------------------- #
# Fix pass 2, MINOR 5 -- a static_weights return's composition is sealed prose
# --------------------------------------------------------------------------- #


def test_conventions_states_static_weights_composition() -> None:
    text = load_conventions().static_weights_composition
    assert text.strip()
    assert "weighted sum" in text.lower()
    assert "compounding" in text.lower()


# --------------------------------------------------------------------------- #
# Fix pass 2, MINOR 7 -- sealed notes describe properties, not test function names
# --------------------------------------------------------------------------- #


def test_derived_series_notes_do_not_name_test_functions() -> None:
    for series in load_derived_series().values():
        assert "test_" not in series.notes, series.series_id
