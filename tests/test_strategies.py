"""WP2.1b Task 2 acceptance: the D4 benchmark-strategy set, loaded from
``pre-registration.yaml`` and defined purely over generated factors.

The D4 set is what tail-fidelity VaR/ES is computed on (``ah/eval/metrics/tails.py``)
and what the WP2.8 tail auxiliary loss optimizes. Both must load the *same object*
from the *same* ``pre-registration.yaml``, which is what test_load_d4_strategies_is_
cached_by_identity below stands in for (see Instructions/WP2.1b-PRE-SEAL-PATCH.md
Item 1 acceptance).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ah.factors import load_manifest
from ah.strategies import Strategy, StrategyError, load_d4_strategies

_EXPECTED_IDS = {"eqw_factors", "sixty_forty", "endowment_proxy", "momentum", "carry"}


def test_load_d4_strategies_returns_exactly_the_five_ids() -> None:
    strategies = load_d4_strategies()
    ids = {s.strategy_id for s in strategies}
    assert ids == _EXPECTED_IDS
    assert len(strategies) == 5


def test_load_d4_strategies_is_cached_by_identity() -> None:
    a = load_d4_strategies()
    b = load_d4_strategies()
    assert a is b


def test_static_weight_strategies_sum_to_one() -> None:
    for strategy in load_d4_strategies():
        if strategy.kind == "static_weights":
            total = sum(strategy.weights.values())
            assert total == pytest.approx(1.0, abs=1e-9), strategy.strategy_id


def test_rule_strategies_have_empty_weights() -> None:
    for strategy in load_d4_strategies():
        if strategy.kind == "rule":
            assert strategy.weights == {}


def test_every_referenced_factor_is_active() -> None:
    active = set(load_manifest().active_factors())
    for strategy in load_d4_strategies():
        for factor in strategy.weights:
            assert factor in active, f"{strategy.strategy_id} references inactive '{factor}'"


def test_unknown_factor_raises_strategy_error(tmp_path: Path) -> None:
    bad = tmp_path / "pre-registration.yaml"
    bad.write_text(
        "d4_strategies:\n"
        "  bogus:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights:\n"
        "      not_a_real_factor: 1.0\n"
        "    params: {}\n"
        "    notes: test fixture\n",
        encoding="utf-8",
    )
    with pytest.raises(StrategyError):
        load_d4_strategies(bad)


def test_static_weights_not_summing_to_one_raises(tmp_path: Path) -> None:
    bad = tmp_path / "pre-registration.yaml"
    bad.write_text(
        "d4_strategies:\n"
        "  bogus:\n"
        "    kind: static_weights\n"
        "    rebalance: monthly\n"
        "    lookback: null\n"
        "    rule: null\n"
        "    weights:\n"
        "      equity_mkt: 0.5\n"
        "      ust_10y: 0.2\n"
        "    params: {}\n"
        "    notes: test fixture\n",
        encoding="utf-8",
    )
    with pytest.raises(StrategyError):
        load_d4_strategies(bad)


def test_unknown_rule_raises(tmp_path: Path) -> None:
    bad = tmp_path / "pre-registration.yaml"
    bad.write_text(
        "d4_strategies:\n"
        "  bogus:\n"
        "    kind: rule\n"
        "    rebalance: monthly\n"
        "    lookback: 12\n"
        "    rule: not_a_real_rule\n"
        "    weights: {}\n"
        "    params: {}\n"
        "    notes: test fixture\n",
        encoding="utf-8",
    )
    with pytest.raises(StrategyError):
        load_d4_strategies(bad)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(StrategyError):
        load_d4_strategies(tmp_path / "does-not-exist.yaml")


def test_strategy_is_frozen_dataclass() -> None:
    strategy = load_d4_strategies()[0]
    assert isinstance(strategy, Strategy)
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError, dataclass-generated
        strategy.kind = "rule"  # type: ignore[misc]
