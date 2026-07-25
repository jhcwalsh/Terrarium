"""The D4 benchmark-strategy set and its derived series (WP2.1b Item 1).

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

Levels are not returns
----------------------
The generator emits some factors as period returns (``equity_mkt``, ``smb``, ...) and
others as *levels quoted in percent* (``ust_10y``, ``hy_spread``, ``policy_rate``,
...). Summing the two is a units error with a sign consequence: a bond leg weighted on
the raw yield level *rises* when yields rise, and a credit leg weighted on the raw
spread level books spread widening as a gain. A D4 strategy's ``weights`` may
therefore name only a return-bearing active factor or a **declared derived series** --
a named, fully specified transform of exactly one level factor into a monthly decimal
return, declared in ``pre-registration.yaml``'s ``derived_series`` block and sealed
alongside the strategies. :class:`DerivedSeries` loads those declarations;
``ah/eval/metrics/tails.py`` implements the transforms.

The pre-registration is the authority
-------------------------------------
``pre-registration.yaml`` must be sufficient on its own to reconstruct the D4 set,
with no reference to code outside the sealed hash. Consequences enforced here:

* every rule's target series is sealed *data* (a ``params`` key ending in
  ``_series``), not a constant in the metric module;
* no sealed parameter has a code-side default -- a missing one raises
  :class:`StrategyError` naming it, rather than silently substituting a number;
* unknown keys are a hard error, so a ``weigths:``-style typo in a file whose whole
  purpose is to be hashed cannot pass unnoticed;
* duplicate mapping keys are a hard error (``yaml.safe_load`` would otherwise keep
  the last silently, losing a whole sealed definition);
* ``lookback`` is declared exactly once -- ``params`` may not also carry
  ``lookback_months``;
* ``endowment_proxy``'s sleeve-level ``proxy_mapping`` is rolled up and checked
  against the flat ``weights`` table it documents.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from ah.factors import load_manifest

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "pre-registration.yaml"

_WEIGHT_SUM_TOL = 1e-9
_PROXY_ROLLUP_TOL = 1e-9

# Rule ids implemented by ah.eval.metrics.tails' rule dispatch, mapped to the exact
# set of `params` keys each one requires. Exact: a missing key and an unknown key are
# both StrategyError, so no sealed knob can fall back to a code-side default and no
# typo can slip through. Kept here -- not in tails.py -- so this module can validate a
# rule strategy without importing ah.eval (which would make ah.gen import ah.eval
# transitively through this module; see the module docstring). tails.py imports
# KNOWN_RULES, and a test asserts it equals the dispatch table's keys.
_RULE_PARAMS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "momentum_12_1": frozenset({"target_series", "skip_months"}),
        "term_structure_carry": frozenset(
            {"long_series", "funding_series", "long_weight", "funding_weight"}
        ),
    }
)
KNOWN_RULES: frozenset[str] = frozenset(_RULE_PARAMS)

# Rules whose behaviour depends on `lookback`; for these the field must be non-null.
_RULES_REQUIRING_LOOKBACK: frozenset[str] = frozenset({"momentum_12_1"})

# Transform ids implemented by ah.eval.metrics.tails' transform dispatch, mapped to
# the exact set of `params` keys each requires. Same contract as _RULE_PARAMS.
_TRANSFORM_PARAMS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "bond_total_return": frozenset({"duration_years"}),
        "spread_excess_return": frozenset({"spread_duration_years"}),
    }
)
KNOWN_TRANSFORMS: frozenset[str] = frozenset(_TRANSFORM_PARAMS)

_VALID_KINDS = ("static_weights", "rule")

# Allow-lists. Any other key in these mappings is a hard error (finding 6).
_STRATEGY_KEYS = frozenset(
    {"kind", "rebalance", "lookback", "rule", "weights", "params", "notes", "proxy_mapping"}
)
_DERIVED_KEYS = frozenset({"from", "transform", "params", "formula", "notes"})
_PROXY_SLEEVE_KEYS = frozenset({"weight", "factor", "reason"})

# `params` keys ending in this suffix name a series the rule reads; their values are
# validated against the active factors plus the declared derived series. See
# `conventions.series_parameters` in pre-registration.yaml.
_SERIES_PARAM_SUFFIX = "_series"

# `lookback` is declared once, in the strategy's own field. Rejected inside `params`.
_FORBIDDEN_PARAM_KEYS = frozenset({"lookback_months"})


class StrategyError(ValueError):
    """Raised when ``pre-registration.yaml``'s sealed D4 content fails validation."""


class _DuplicateKey(Exception):
    """Internal: a duplicate mapping key seen while parsing. Re-raised with the path."""

    def __init__(self, key: object, line: int) -> None:
        super().__init__(key)
        self.key = key
        self.line = line


class _UniqueKeyLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` that refuses duplicate mapping keys.

    ``yaml.safe_load`` silently keeps the last of a set of duplicate keys, so a sealed
    file declaring ``momentum:`` twice would lose one definition with no diagnostic.
    """

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise _DuplicateKey(key, key_node.start_mark.line + 1)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)  # type: ignore[no-any-return]


@dataclass(frozen=True)
class ProxySleeve:
    """One sleeve of ``endowment_proxy``'s ``proxy_mapping``: what it is a proxy *for*."""

    sleeve_id: str
    weight: float
    factor: str
    reason: str


@dataclass(frozen=True)
class DerivedSeries:
    """A declared transform of one level factor into a monthly decimal return.

    ``source_factor`` must be an active factor; ``transform`` names a member of
    :data:`KNOWN_TRANSFORMS`; ``params`` carries exactly that transform's required
    parameters; ``formula`` is the closed form, verbatim from the sealed file, so the
    series is reconstructible from ``pre-registration.yaml`` alone.
    """

    series_id: str
    source_factor: str
    transform: str
    params: Mapping[str, float]
    formula: str
    notes: str


@dataclass(frozen=True)
class Strategy:
    """One D4 benchmark strategy, fully reconstructible from ``pre-registration.yaml``.

    ``weights`` maps *series id* -> weight, where a series id is either a return-bearing
    active factor or a declared :class:`DerivedSeries`; empty for ``kind == "rule"``.
    ``rule`` names a rule in :data:`KNOWN_RULES`, set only for ``kind == "rule"``.
    ``params`` carries the rule's sealed knobs -- including its target series, under
    keys ending in ``_series`` -- and is empty for static-weight strategies.
    ``lookback`` is the single declaration of a rule's lookback window.
    ``proxy_mapping`` is the optional sleeve-level breakdown behind a flat ``weights``
    table; when present it is checked to roll up to ``weights`` within 1e-9.
    """

    strategy_id: str
    kind: str
    weights: Mapping[str, float]
    rebalance: str
    lookback: int | None
    rule: str | None
    params: Mapping[str, float | str]
    notes: str
    proxy_mapping: Mapping[str, ProxySleeve] = MappingProxyType({})


def _require_mapping(value: object, what: str, source: Path) -> dict[Any, Any]:
    if not isinstance(value, dict):
        raise StrategyError(f"{source}: {what} must be a mapping, got {type(value).__name__}")
    return value


def _reject_unknown_keys(
    entry: Mapping[Any, Any], allowed: frozenset[str], what: str, source: Path
) -> None:
    unknown = sorted(str(k) for k in entry if k not in allowed)
    if unknown:
        raise StrategyError(
            f"{source}: {what} has unknown key(s) {unknown}; allowed: {sorted(allowed)}"
        )


def _require_number(value: object, what: str, source: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StrategyError(f"{source}: {what} must be numeric, got {value!r}")
    return float(value)


def _require_text(value: object, what: str, source: Path) -> str:
    if not isinstance(value, str) or not value:
        raise StrategyError(f"{source}: {what} must be a non-empty string, got {value!r}")
    return value


# --------------------------------------------------------------------------- #
# derived_series
# --------------------------------------------------------------------------- #


def _validate_derived_series(
    entry: object, series_id: object, active_factors: frozenset[str], source: Path
) -> DerivedSeries:
    if not isinstance(series_id, str) or not series_id:
        raise StrategyError(f"{source}: derived_series has a non-string/empty id {series_id!r}")
    entry_map = _require_mapping(entry, f"derived_series.{series_id}", source)
    _reject_unknown_keys(entry_map, _DERIVED_KEYS, f"derived_series.{series_id}", source)

    source_factor = _require_text(entry_map.get("from"), f"derived_series.{series_id}.from", source)
    if source_factor not in active_factors:
        raise StrategyError(
            f"{source}: derived_series.{series_id}.from references unknown or inactive "
            f"factor '{source_factor}'"
        )

    transform = _require_text(
        entry_map.get("transform"), f"derived_series.{series_id}.transform", source
    )
    if transform not in KNOWN_TRANSFORMS:
        raise StrategyError(
            f"{source}: derived_series.{series_id} transform '{transform}' is not "
            f"implemented; known transforms: {sorted(KNOWN_TRANSFORMS)}"
        )

    raw_params = _require_mapping(
        entry_map.get("params") or {}, f"derived_series.{series_id}.params", source
    )
    params: dict[str, float] = {}
    for key, value in raw_params.items():
        key_str = _require_text(key, f"derived_series.{series_id}.params key", source)
        params[key_str] = _require_number(
            value, f"derived_series.{series_id}.params['{key_str}']", source
        )
    _require_exact_params(
        frozenset(params),
        _TRANSFORM_PARAMS[transform],
        f"derived_series.{series_id} (transform '{transform}')",
        source,
    )

    formula = _require_text(entry_map.get("formula"), f"derived_series.{series_id}.formula", source)

    notes = entry_map.get("notes", "")
    if not isinstance(notes, str):
        raise StrategyError(f"{source}: derived_series.{series_id}.notes must be a string")

    return DerivedSeries(
        series_id=series_id,
        source_factor=source_factor,
        transform=transform,
        params=MappingProxyType(params),
        formula=formula,
        notes=notes,
    )


def _require_exact_params(
    present: frozenset[str], required: frozenset[str], what: str, source: Path
) -> None:
    """Sealed parameters are exact: none missing (no code-side defaults), none extra."""
    missing = sorted(required - present)
    if missing:
        raise StrategyError(
            f"{source}: {what} is missing required parameter(s) {missing}; sealed "
            f"parameters have no code-side default"
        )
    extra = sorted(present - required)
    if extra:
        raise StrategyError(f"{source}: {what} has unknown parameter(s) {extra}")


# --------------------------------------------------------------------------- #
# d4_strategies
# --------------------------------------------------------------------------- #


def _validate_weights(
    raw: object, strategy_id: str, known_series: frozenset[str], source: Path
) -> dict[str, float]:
    raw_map = _require_mapping(raw or {}, f"d4_strategies.{strategy_id}.weights", source)
    weights: dict[str, float] = {}
    for series, w in raw_map.items():
        if not isinstance(series, str) or not series:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.weights has a non-string/empty "
                f"key {series!r}"
            )
        if series not in known_series:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} references unknown series "
                f"'{series}' -- must be an active factor or a declared derived series"
            )
        weights[series] = _require_number(
            w, f"d4_strategies.{strategy_id}.weights['{series}']", source
        )
    return weights


def _validate_params(
    raw: object, strategy_id: str, known_series: frozenset[str], source: Path
) -> dict[str, float | str]:
    raw_map = _require_mapping(raw or {}, f"d4_strategies.{strategy_id}.params", source)
    params: dict[str, float | str] = {}
    for key, v in raw_map.items():
        key_str = _require_text(key, f"d4_strategies.{strategy_id}.params key", source)
        if key_str in _FORBIDDEN_PARAM_KEYS:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.params declares '{key_str}'; "
                f"lookback is declared exactly once, in the strategy's own 'lookback' "
                f"field, and must not be duplicated in params"
            )
        if key_str.endswith(_SERIES_PARAM_SUFFIX):
            series = _require_text(v, f"d4_strategies.{strategy_id}.params['{key_str}']", source)
            if series not in known_series:
                raise StrategyError(
                    f"{source}: d4_strategies.{strategy_id}.params['{key_str}'] names "
                    f"unknown series '{series}' -- must be an active factor or a "
                    f"declared derived series"
                )
            params[key_str] = series
        else:
            params[key_str] = _require_number(
                v, f"d4_strategies.{strategy_id}.params['{key_str}']", source
            )
    return params


def _validate_proxy_mapping(
    raw: object, strategy_id: str, weights: Mapping[str, float], source: Path
) -> dict[str, ProxySleeve]:
    raw_map = _require_mapping(raw, f"d4_strategies.{strategy_id}.proxy_mapping", source)
    sleeves: dict[str, ProxySleeve] = {}
    rollup: dict[str, float] = {}
    for sleeve_id, entry in raw_map.items():
        sleeve_str = _require_text(
            sleeve_id, f"d4_strategies.{strategy_id}.proxy_mapping key", source
        )
        what = f"d4_strategies.{strategy_id}.proxy_mapping.{sleeve_str}"
        entry_map = _require_mapping(entry, what, source)
        _reject_unknown_keys(entry_map, _PROXY_SLEEVE_KEYS, what, source)
        weight = _require_number(entry_map.get("weight"), f"{what}.weight", source)
        factor = _require_text(entry_map.get("factor"), f"{what}.factor", source)
        if factor not in weights:
            raise StrategyError(
                f"{source}: {what}.factor '{factor}' is not in d4_strategies.{strategy_id}.weights"
            )
        reason = _require_text(entry_map.get("reason"), f"{what}.reason", source)
        sleeves[sleeve_str] = ProxySleeve(
            sleeve_id=sleeve_str, weight=weight, factor=factor, reason=reason
        )
        rollup[factor] = rollup.get(factor, 0.0) + weight

    for series, weight in weights.items():
        rolled = rollup.get(series, 0.0)
        if abs(rolled - weight) > _PROXY_ROLLUP_TOL:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.proxy_mapping rolls up to "
                f"{rolled} for '{series}' but weights declares {weight}"
            )
    return sleeves


def _validate_strategy(
    entry: object, strategy_id: object, known_series: frozenset[str], source: Path
) -> Strategy:
    if not isinstance(strategy_id, str) or not strategy_id:
        raise StrategyError(f"{source}: d4_strategies has a non-string/empty id {strategy_id!r}")
    entry_map = _require_mapping(entry, f"d4_strategies.{strategy_id}", source)
    _reject_unknown_keys(entry_map, _STRATEGY_KEYS, f"d4_strategies.{strategy_id}", source)

    kind = entry_map.get("kind")
    if kind not in _VALID_KINDS:
        raise StrategyError(
            f"{source}: d4_strategies.{strategy_id}.kind must be one of {_VALID_KINDS}, "
            f"got {kind!r}"
        )

    rebalance = _require_text(
        entry_map.get("rebalance"), f"d4_strategies.{strategy_id}.rebalance", source
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

    weights = _validate_weights(entry_map.get("weights"), strategy_id, known_series, source)
    params = _validate_params(entry_map.get("params"), strategy_id, known_series, source)
    raw_proxy = entry_map.get("proxy_mapping")

    if kind == "static_weights":
        if rule is not None:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} is static_weights but declares a rule"
            )
        if not weights:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} (static_weights) must declare weights"
            )
        if params:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} (static_weights) must not declare "
                f"params; got {sorted(params)}"
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
        if raw_proxy is not None:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} (rule) must not declare proxy_mapping"
            )
        if rule not in KNOWN_RULES:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} rule '{rule}' is not implemented; "
                f"known rules: {sorted(KNOWN_RULES)}"
            )
        _require_exact_params(
            frozenset(params),
            _RULE_PARAMS[rule],
            f"d4_strategies.{strategy_id} (rule '{rule}')",
            source,
        )
        if rule in _RULES_REQUIRING_LOOKBACK and lookback is None:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id} rule '{rule}' requires a non-null "
                f"'lookback'"
            )

    proxy_mapping = (
        _validate_proxy_mapping(raw_proxy, strategy_id, weights, source)
        if raw_proxy is not None
        else {}
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
        proxy_mapping=MappingProxyType(proxy_mapping),
    )


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #


@lru_cache
def _read_doc(resolved_path: Path) -> Mapping[str, Any]:
    if not resolved_path.exists():
        raise StrategyError(f"{resolved_path}: not found")
    text = resolved_path.read_text(encoding="utf-8")
    try:
        doc = yaml.load(text, Loader=_UniqueKeyLoader)
    except _DuplicateKey as exc:
        raise StrategyError(
            f"{resolved_path}: duplicate key '{exc.key}' at line {exc.line}; a sealed "
            f"file must not declare the same id twice"
        ) from exc
    if doc is None:
        return MappingProxyType({})
    if not isinstance(doc, dict):
        raise StrategyError(f"{resolved_path}: top level must be a mapping")
    return MappingProxyType(doc)


@lru_cache
def _load_derived_series_cached(resolved_path: Path) -> Mapping[str, DerivedSeries]:
    raw = _read_doc(resolved_path).get("derived_series")
    if raw is None:
        return MappingProxyType({})
    raw_map = _require_mapping(raw, "'derived_series'", resolved_path)
    active_factors = frozenset(load_manifest().active_factors())
    series = {
        str(series_id): _validate_derived_series(entry, series_id, active_factors, resolved_path)
        for series_id, entry in raw_map.items()
    }
    collisions = sorted(set(series) & active_factors)
    if collisions:
        raise StrategyError(
            f"{resolved_path}: derived series {collisions} collide with active factor ids"
        )
    return MappingProxyType(series)


def load_derived_series(path: Path | None = None) -> Mapping[str, DerivedSeries]:
    """Load and validate the ``derived_series`` block, defaulting to the repo-root file.

    Cached by resolved path, like :func:`load_d4_strategies`, so every caller receives
    the *same* mapping object (identity, not just equality).
    """
    resolved = (path if path is not None else _DEFAULT_PATH).resolve()
    return _load_derived_series_cached(resolved)


@lru_cache
def _load_d4_strategies_cached(resolved_path: Path) -> tuple[Strategy, ...]:
    raw = _read_doc(resolved_path).get("d4_strategies")
    if not isinstance(raw, dict) or not raw:
        raise StrategyError(f"{resolved_path}: 'd4_strategies' must be a non-empty mapping")

    active_factors = frozenset(load_manifest().active_factors())
    derived = _load_derived_series_cached(resolved_path)
    known_series = active_factors | frozenset(derived)
    return tuple(
        _validate_strategy(entry, strategy_id, known_series, resolved_path)
        for strategy_id, entry in raw.items()
    )


def load_d4_strategies(path: Path | None = None) -> tuple[Strategy, ...]:
    """Load and validate the D4 strategy set, defaulting to the repo-root ``pre-registration.yaml``.

    Cached by resolved path (:func:`functools.lru_cache`) so every caller -- the
    battery and the WP2.8 tail auxiliary loss alike -- receives the *same*
    ``tuple[Strategy, ...]`` object (identity, not just equality).
    """
    resolved = (path if path is not None else _DEFAULT_PATH).resolve()
    return _load_d4_strategies_cached(resolved)
