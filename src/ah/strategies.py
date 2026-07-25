"""The D4 benchmark-strategy set, defined over generated factors only (WP2.1b Item 1).

The D4 set is what VaR/ES tail-fidelity metrics are computed on
(``ah/eval/metrics/tails.py``) and what the WP2.8 tail auxiliary loss
(``ah/gen/blocks/losses.py``) optimizes. Both must load the *same* strategy objects
from the *same* ``pre-registration.yaml`` -- this module is that single source, cached
by resolved path so repeated calls return identical objects (not just equal ones).

Top-level (a peer of :mod:`ah.factors` and :mod:`ah.splits`), not under ``ah.eval``:
``ah/gen/blocks/losses.py`` must import these definitions without ``ah.gen`` depending
on ``ah.eval`` -- that import boundary is one step from the holdout-leakage guard in
:mod:`ah.splits`. See ``Instructions/WP2.1b-PRE-SEAL-PATCH.md`` Item 1 and
``tests/test_tails_import_graph.py`` for the import-graph proof that this module (and
``ah/eval/metrics/tails.py``) never import portfolio or sleeve machinery.

Previously the D4 set included an "endowment mix" defined over portfolio sleeves,
which required Step-3 machinery the generator layer cannot see and a sleeve taxonomy
not frozen until Step 2R. Every D4 strategy is now weights over generated factors
(``kind: "static_weights"``) or a stated rule over factor slabs
(``kind: "rule"``) -- see ``pre-registration.yaml``'s ``d4_strategies`` block for the
five definitions this loads, each reconstructible from the YAML alone.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

import yaml

from ah.factors import load_manifest

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "pre-registration.yaml"

_WEIGHT_SUM_TOL = 1e-9

# Rule ids implemented by ah.eval.metrics.tails.strategy_returns' rule dispatch.
# Kept here -- not in tails.py -- so this module can validate a rule strategy's
# `rule` field without importing ah.eval (which would make ah.gen import ah.eval
# transitively through this module; see the module docstring). tails.py imports
# this set to keep the two from drifting apart.
KNOWN_RULES: frozenset[str] = frozenset({"momentum_12_1", "term_structure_carry"})

_VALID_KINDS = ("static_weights", "rule")


class StrategyError(ValueError):
    """Raised when ``pre-registration.yaml``'s ``d4_strategies`` block fails validation."""


@dataclass(frozen=True)
class Strategy:
    """One D4 benchmark strategy, fully reconstructible from ``pre-registration.yaml``.

    ``weights`` maps active factor id -> weight; empty for ``kind == "rule"`` (a rule
    strategy's target factor(s) are fixed by the rule id itself, not parametrized
    here -- see ``ah/eval/metrics/tails.py``). ``rule`` names a rule in
    :data:`KNOWN_RULES`, set only for ``kind == "rule"``. ``params`` carries a rule's
    numeric knobs (e.g. lookback/skip months, long/funding weights); always present,
    empty for static-weight strategies with no extra parameters.
    """

    strategy_id: str
    kind: str
    weights: Mapping[str, float]
    rebalance: str
    lookback: int | None
    rule: str | None
    params: Mapping[str, float]
    notes: str


def _require_mapping(value: object, what: str, source: Path) -> dict[object, object]:
    if not isinstance(value, dict):
        raise StrategyError(f"{source}: {what} must be a mapping, got {type(value).__name__}")
    return value


def _validate_weights(
    raw: object, strategy_id: str, active_factors: frozenset[str], source: Path
) -> dict[str, float]:
    raw = raw or {}
    raw_map = _require_mapping(raw, f"d4_strategies.{strategy_id}.weights", source)
    weights: dict[str, float] = {}
    for factor, w in raw_map.items():
        if not isinstance(factor, str) or not factor:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.weights has a non-string/empty "
                f"factor key {factor!r}"
            )
        if factor not in active_factors:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} references unknown or inactive "
                f"factor '{factor}'"
            )
        if isinstance(w, bool) or not isinstance(w, (int, float)):
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.weights['{factor}'] must be numeric, "
                f"got {w!r}"
            )
        weights[factor] = float(w)
    return weights


def _validate_params(raw: object, strategy_id: str, source: Path) -> dict[str, float]:
    raw = raw or {}
    raw_map = _require_mapping(raw, f"d4_strategies.{strategy_id}.params", source)
    params: dict[str, float] = {}
    for key, v in raw_map.items():
        if not isinstance(key, str) or not key:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.params has a non-string/empty key {key!r}"
            )
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.params['{key}'] must be numeric, got {v!r}"
            )
        params[key] = float(v)
    return params


def _validate_strategy(
    entry: object, strategy_id: str, active_factors: frozenset[str], source: Path
) -> Strategy:
    if not isinstance(strategy_id, str) or not strategy_id:
        raise StrategyError(f"{source}: d4_strategies has a non-string/empty id {strategy_id!r}")
    entry_map = _require_mapping(entry, f"d4_strategies.{strategy_id}", source)

    kind = entry_map.get("kind")
    if kind not in _VALID_KINDS:
        raise StrategyError(
            f"{source}: d4_strategies.{strategy_id}.kind must be one of {_VALID_KINDS}, "
            f"got {kind!r}"
        )

    rebalance = entry_map.get("rebalance")
    if not isinstance(rebalance, str) or not rebalance:
        raise StrategyError(
            f"{source}: d4_strategies.{strategy_id}.rebalance must be a non-empty string"
        )

    lookback = entry_map.get("lookback")
    if lookback is not None and (isinstance(lookback, bool) or not isinstance(lookback, int)):
        raise StrategyError(
            f"{source}: d4_strategies.{strategy_id}.lookback must be an int or null, "
            f"got {lookback!r}"
        )

    rule = entry_map.get("rule")
    if rule is not None and (not isinstance(rule, str) or not rule):
        raise StrategyError(
            f"{source}: d4_strategies.{strategy_id}.rule must be a non-empty string or null"
        )

    notes = entry_map.get("notes", "")
    if not isinstance(notes, str):
        raise StrategyError(f"{source}: d4_strategies.{strategy_id}.notes must be a string")

    weights = _validate_weights(entry_map.get("weights"), strategy_id, active_factors, source)
    params = _validate_params(entry_map.get("params"), strategy_id, source)

    if kind == "static_weights":
        if rule is not None:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} is static_weights but declares a rule"
            )
        if not weights:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} (static_weights) must declare weights"
            )
        total = sum(weights.values())
        if abs(total - 1.0) > _WEIGHT_SUM_TOL:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} weights sum to {total}, expected 1.0"
            )
    else:  # kind == "rule"
        if weights:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} (rule) must not declare weights"
            )
        if rule not in KNOWN_RULES:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} rule '{rule}' is not implemented; "
                f"known rules: {sorted(KNOWN_RULES)}"
            )

    return Strategy(
        strategy_id=strategy_id,
        kind=kind,
        weights=MappingProxyType(weights),
        rebalance=rebalance,
        lookback=lookback,
        rule=rule,
        params=MappingProxyType(params),
        notes=notes,
    )


@lru_cache
def _load_d4_strategies_cached(resolved_path: Path) -> tuple[Strategy, ...]:
    if not resolved_path.exists():
        raise StrategyError(f"{resolved_path}: not found")
    doc = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    raw = doc.get("d4_strategies")
    if not isinstance(raw, dict) or not raw:
        raise StrategyError(f"{resolved_path}: 'd4_strategies' must be a non-empty mapping")

    active_factors = frozenset(load_manifest().active_factors())
    strategies = tuple(
        _validate_strategy(entry, strategy_id, active_factors, resolved_path)
        for strategy_id, entry in raw.items()
    )
    return strategies


def load_d4_strategies(path: Path | None = None) -> tuple[Strategy, ...]:
    """Load and validate the D4 strategy set, defaulting to the repo-root ``pre-registration.yaml``.

    Cached by resolved path (:func:`functools.lru_cache`) so every caller -- the
    battery and the WP2.8 tail auxiliary loss alike -- receives the *same*
    ``tuple[Strategy, ...]`` object (identity, not just equality).
    """
    resolved = (path if path is not None else _DEFAULT_PATH).resolve()
    return _load_d4_strategies_cached(resolved)
