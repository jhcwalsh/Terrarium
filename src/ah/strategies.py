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
  against the flat ``weights`` table it documents;
* the ``conventions`` block is itself sealed data, not prose: :class:`Conventions`
  (via :func:`load_conventions`) is the return-bearing/level classification that
  gates a strategy's ``weights`` (a level factor never appears there directly), the
  ``rebalance`` values the loader accepts, and the ``percent_to_decimal`` /
  ``months_per_year`` numbers ``ah.eval.metrics.tails`` is driven by at import time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from ah.factors import FactorManifest, load_manifest

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
_DERIVED_KEYS = frozenset({"from", "transform", "params", "formula", "notes", "numeraire"})
_PROXY_SLEEVE_KEYS = frozenset({"weight", "factor", "reason"})

# `params` keys ending in this suffix name a series the rule reads; their values are
# validated against the active factors plus the declared derived series. See
# `conventions.series_parameters` in pre-registration.yaml.
_SERIES_PARAM_SUFFIX = "_series"

# The numeraire a fully-invested D4 portfolio may be quoted on. `zero_cost` is not in
# this set: it is not a portfolio numeraire, it is the property of a self-financing
# overlay leg that makes the leg numeraire-neutral (see _validate_numeraires).
_PORTFOLIO_NUMERAIRES = frozenset({"total_return", "excess_return"})

# Every numeraire a single leg may declare, portfolio numeraires plus `zero_cost`. Kept
# identical to ah.factors._NUMERAIRES -- a test asserts the two agree, so the factor
# side and the derived-series side of a D4 leg can never drift into different
# vocabularies.
_LEG_NUMERAIRES = frozenset({"total_return", "excess_return", "zero_cost"})

# `lookback` is declared once, in the strategy's own field. Rejected inside `params`.
_FORBIDDEN_PARAM_KEYS = frozenset({"lookback_months"})

# Allow-list for the top-level `conventions:` block. Some entries are prose-only
# (read by nobody, kept for human context); the ones below are load-bearing and
# validated by `_validate_conventions`.
_CONVENTIONS_KEYS = frozenset(
    {
        "units_of_return_bearing_factors",
        "return_bearing_factors",
        "units_of_level_factors",
        "level_factors",
        "percent_to_decimal",
        "months_per_year",
        "percent_to_decimal_statement",
        "warm_up",
        "loss_sign",
        "series_parameters",
        "rebalance_cadences",
        "rebalance_convention",
        "static_weights_composition",
        "numeraire",
        "numeraire_zero_cost_legs",
        "numeraire_statement",
        "nan_metric_rule",
        # WP2.2 Task 2 fix pass: the sealed metric-estimator statements. Prose-only to
        # this module (D4 strategy loading does not read them), but they must be
        # ALLOWED here or the whole pre-registration fails to load -- and they belong
        # in the sealed file rather than only in a docstring, because a band is
        # meaningless without the estimator that produced it. `ah.eval.reference` is
        # the implementation they describe and is itself a hashed judged source, so
        # the two cannot drift without a lock violation.
        "acf_estimator",
        "estimator_length_matching",
        "acf_abs_decay_estimator",
        "hill_tail_index_estimator",
        "agg_gaussianity_estimator",
        "leverage_correlation_estimator",
        "cross_block_corr_matrix_distance_estimator",
        # WP2.2 Task 3 and its fix pass: the horizon-tier estimators, plus the two
        # cross-cutting statements that had no home before (the elementary population
        # moments every other definition builds on, and why a Monte-Carlo error over
        # 1000 generated paths is NOT the small-n historical uncertainty DN-1.1 asks to
        # be reported). `ah.eval.prereg.ESTIMATOR_CONVENTION_KEYS` maps every registered
        # statistic to the block that defines it, and a test asserts the mapping is
        # total in both directions -- so this list cannot fall behind the registry
        # silently.
        "elementary_moment_estimators",
        "crisis_corr_lift_estimator",
        "variance_ratio_estimator",
        "mean_reversion_halflife_estimator",
        "drawdown_episode_estimator",
        "lost_decade_frequency_estimator",
        "long_inflation_era_frequency_estimator",
        "ergodicity_gap_estimator",
        "regime_duration_estimator",
        "ten_year_return_vs_valuation_estimator",
        "mc_error_is_not_the_small_n_band",
    }
)


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
    numeraire: str = ""


@dataclass(frozen=True)
class Conventions:
    """The sealed ``conventions`` block: values transforms and the loader are driven by.

    ``percent_to_decimal`` and ``months_per_year`` are read by
    ``ah.eval.metrics.tails`` at import time to drive every derived-series transform
    -- there is no independent copy of either number in that module.
    ``return_bearing_factors`` and ``level_factors`` partition the active factor set
    (:func:`ah.factors.load_manifest`'s ``active_factors()``) exactly; every active
    factor is in exactly one of the two, checked at load time, and ``level_factors``
    is the sealed source the loader uses to reject a strategy that weights a level
    factor directly. ``rebalance_cadences`` is every ``rebalance`` value the loader
    accepts. ``static_weights_composition`` is the sealed prose statement of how a
    ``static_weights`` strategy's return is computed.
    """

    percent_to_decimal: float
    months_per_year: float
    return_bearing_factors: frozenset[str]
    level_factors: frozenset[str]
    rebalance_cadences: frozenset[str]
    static_weights_composition: str
    numeraire: str = ""
    zero_cost_legs: frozenset[str] = frozenset()


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


def _require_string_set(value: object, what: str, source: Path) -> frozenset[str]:
    """A non-empty YAML list of distinct non-empty strings, as a ``frozenset``."""
    if not isinstance(value, list) or not value:
        raise StrategyError(f"{source}: {what} must be a non-empty list, got {value!r}")
    items: set[str] = set()
    for entry in value:
        text = _require_text(entry, f"{what} entry", source)
        if text in items:
            raise StrategyError(f"{source}: {what} lists '{text}' more than once")
        items.add(text)
    return frozenset(items)


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

    numeraire = entry_map.get("numeraire", "")
    if not isinstance(numeraire, str):
        raise StrategyError(f"{source}: derived_series.{series_id}.numeraire must be a string")
    if numeraire and numeraire not in _LEG_NUMERAIRES:
        raise StrategyError(
            f"{source}: derived_series.{series_id}.numeraire must be one of "
            f"{sorted(_LEG_NUMERAIRES)}, got {numeraire!r}"
        )

    return DerivedSeries(
        series_id=series_id,
        source_factor=source_factor,
        transform=transform,
        params=MappingProxyType(params),
        formula=formula,
        notes=notes,
        numeraire=numeraire,
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
# conventions
# --------------------------------------------------------------------------- #

# A file with no `conventions:` block at all (every hand-written test fixture that
# predates this block) is treated as declaring no structured conventions rather than
# as an error: the fields below only gate behaviour -- the level-factor guard in
# `_validate_weights` and the rebalance-cadence guard in `_validate_strategy` -- when
# the sealed file actually declares them. The real `pre-registration.yaml` always
# declares a full block, exhaustive over the active factor set, so this default is
# never load-bearing for it.
_DEFAULT_CONVENTIONS = Conventions(
    percent_to_decimal=0.01,
    months_per_year=12.0,
    return_bearing_factors=frozenset(),
    level_factors=frozenset(),
    rebalance_cadences=frozenset(),
    static_weights_composition="",
    numeraire="",
    zero_cost_legs=frozenset(),
)


def _validate_conventions(raw: object, active_factors: frozenset[str], source: Path) -> Conventions:
    if raw is None:
        return _DEFAULT_CONVENTIONS
    entry_map = _require_mapping(raw, "'conventions'", source)
    _reject_unknown_keys(entry_map, _CONVENTIONS_KEYS, "'conventions'", source)

    percent_to_decimal = _require_number(
        entry_map.get("percent_to_decimal"), "conventions.percent_to_decimal", source
    )
    months_per_year = _require_number(
        entry_map.get("months_per_year"), "conventions.months_per_year", source
    )

    return_bearing_factors = _require_string_set(
        entry_map.get("return_bearing_factors"), "conventions.return_bearing_factors", source
    )
    level_factors = _require_string_set(
        entry_map.get("level_factors"), "conventions.level_factors", source
    )
    overlap = sorted(return_bearing_factors & level_factors)
    if overlap:
        raise StrategyError(
            f"{source}: conventions.return_bearing_factors and conventions.level_factors "
            f"both classify {overlap}; a factor must be exactly one"
        )
    classified = return_bearing_factors | level_factors
    unclassified = sorted(active_factors - classified)
    if unclassified:
        raise StrategyError(
            f"{source}: conventions does not classify active factor(s) {unclassified} as "
            f"return_bearing_factors or level_factors"
        )
    inactive = sorted(classified - active_factors)
    if inactive:
        raise StrategyError(
            f"{source}: conventions classifies non-active factor(s) {inactive} -- "
            f"return_bearing_factors and level_factors must cover exactly the active "
            f"factor set, no more"
        )

    rebalance_cadences = _require_string_set(
        entry_map.get("rebalance_cadences"), "conventions.rebalance_cadences", source
    )

    static_weights_composition = _require_text(
        entry_map.get("static_weights_composition"),
        "conventions.static_weights_composition",
        source,
    )

    # The sealed numeraire (WP2.2 Task 1 fix pass, Critical 3). Optional at the block
    # level so the many hand-written fixtures that predate it keep loading unchanged;
    # once declared it is fully enforced, and ah.eval.prereg.verify() requires the real
    # pre-registration to declare it, so the sealed document can never silently drop it.
    numeraire = entry_map.get("numeraire")
    if numeraire is None:
        numeraire_value = ""
        zero_cost_legs: frozenset[str] = frozenset()
    else:
        numeraire_value = _require_text(numeraire, "conventions.numeraire", source)
        if numeraire_value not in _PORTFOLIO_NUMERAIRES:
            raise StrategyError(
                f"{source}: conventions.numeraire must be one of "
                f"{sorted(_PORTFOLIO_NUMERAIRES)}, got {numeraire_value!r}"
            )
        zero_cost_legs = _require_string_set(
            entry_map.get("numeraire_zero_cost_legs") or ["__none__"],
            "conventions.numeraire_zero_cost_legs",
            source,
        )
        if zero_cost_legs == frozenset({"__none__"}):
            zero_cost_legs = frozenset()

    return Conventions(
        percent_to_decimal=percent_to_decimal,
        months_per_year=months_per_year,
        return_bearing_factors=return_bearing_factors,
        level_factors=level_factors,
        rebalance_cadences=rebalance_cadences,
        static_weights_composition=static_weights_composition,
        numeraire=numeraire_value,
        zero_cost_legs=zero_cost_legs,
    )


# --------------------------------------------------------------------------- #
# d4_strategies
# --------------------------------------------------------------------------- #


def _validate_weights(
    raw: object,
    strategy_id: str,
    known_series: frozenset[str],
    level_factors: frozenset[str],
    source: Path,
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
        if series in level_factors:
            raise StrategyError(
                f"{source}: d4_strategies.{strategy_id}.weights names level factor "
                f"'{series}' directly; a level factor may enter a D4 portfolio only "
                f"through a declared derived_series (conventions.level_factors)"
            )
        weights[series] = _require_number(
            w, f"d4_strategies.{strategy_id}.weights['{series}']", source
        )
    return weights


def _validate_params(
    raw: object,
    strategy_id: str,
    known_series: frozenset[str],
    level_factors: frozenset[str],
    source: Path,
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
            if series in level_factors:
                raise StrategyError(
                    f"{source}: d4_strategies.{strategy_id}.params['{key_str}'] names level factor "
                    f"'{series}' directly; a level factor may enter a D4 portfolio only "
                    f"through a declared derived_series (conventions.level_factors)"
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
    entry: object,
    strategy_id: object,
    known_series: frozenset[str],
    conventions: Conventions,
    source: Path,
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
    if conventions.rebalance_cadences and rebalance not in conventions.rebalance_cadences:
        raise StrategyError(
            f"{source}: d4_strategies.{strategy_id}.rebalance '{rebalance}' is not a "
            f"declared cadence; conventions.rebalance_cadences = "
            f"{sorted(conventions.rebalance_cadences)}"
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

    weights = _validate_weights(
        entry_map.get("weights"), strategy_id, known_series, conventions.level_factors, source
    )
    params = _validate_params(
        entry_map.get("params"), strategy_id, known_series, conventions.level_factors, source
    )
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
def _load_conventions_cached(resolved_path: Path) -> Conventions:
    raw = _read_doc(resolved_path).get("conventions")
    active_factors = frozenset(load_manifest().active_factors())
    return _validate_conventions(raw, active_factors, resolved_path)


def load_conventions(path: Path | None = None) -> Conventions:
    """Load and validate the ``conventions`` block, defaulting to the repo-root file.

    Cached by resolved path, like :func:`load_d4_strategies`. A file with no
    top-level ``conventions:`` key at all loads a permissive default (percent_to_decimal
    0.01, months_per_year 12.0, no declared factor classification, no declared
    rebalance cadence) rather than raising -- most hand-written test fixtures predate
    this block and are unaffected by it. ``pre-registration.yaml`` always declares the
    full block.
    """
    resolved = (path if path is not None else _DEFAULT_PATH).resolve()
    return _load_conventions_cached(resolved)


def strategy_legs(strategy: Strategy) -> tuple[str, ...]:
    """Every series a strategy actually holds, in a stable order.

    A ``static_weights`` strategy's legs are its ``weights`` keys; a ``rule``
    strategy's are the values of every ``params`` key ending in ``_series`` (the sealed
    ``conventions.series_parameters`` rule -- a rule's target series is data in the
    pre-registration, never a constant in code). Deduplicated, first-seen order
    preserved, so a caller iterating legs gets a reproducible sequence.
    """
    legs: list[str] = list(strategy.weights)
    for key, value in strategy.params.items():
        if key.endswith(_SERIES_PARAM_SUFFIX) and isinstance(value, str):
            legs.append(value)
    seen: set[str] = set()
    ordered: list[str] = []
    for leg in legs:
        if leg not in seen:
            seen.add(leg)
            ordered.append(leg)
    return tuple(ordered)


def _validate_numeraires(
    strategies: tuple[Strategy, ...],
    derived: Mapping[str, DerivedSeries],
    conventions: Conventions,
    manifest: FactorManifest,
    source: Path,
) -> None:
    """Every D4 strategy leg must be on ONE numeraire (WP2.2 Task 1 fix pass, Critical 3).

    Before this check, ``equity_mkt`` mapped to Fama-French ``Mkt-RF`` -- an EXCESS
    return -- while ``govt_tr_10y`` is a long-government TOTAL return, and
    ``sixty_forty`` (0.6/0.4) and ``endowment_proxy`` weighted the two together. A
    fully-invested portfolio that sums an excess-return leg with a total-return leg is
    mis-specified by the risk-free rate on the excess leg, and the prose claiming all
    five strategies "inherit the excess-return interpretation" contradicted the sibling
    ``govt_tr_10y`` note. It was about to be sealed.

    The rule, stated once in ``conventions.numeraire`` and enforced here:

    - every leg must **declare** a numeraire -- a factor via ``factors.yaml``'s
      ``factor_sources.<factor>.numeraire``, a derived series via its own
      ``numeraire:`` field. An undeclared leg is rejected, so adding a leg silently
      cannot bypass the rule;
    - a leg is either ``conventions.numeraire`` (``total_return``) or ``zero_cost``.
      An ``excess_return`` leg -- capital-committing but quoted net of a rate -- is
      exactly the error and is rejected;
    - a ``zero_cost`` leg is a self-financing, long-short overlay (``smb``, ``hml``,
      ``mom``; ``credit_xs_hy``, the duration-hedged high-yield leg). It commits no
      capital, so it is numeraire-neutral and may be combined with total-return legs,
      and its weight is a notional/risk budget rather than a capital share. Because
      that is a real economic claim rather than an escape hatch, every zero-cost leg
      must ALSO be named in ``conventions.numeraire_zero_cost_legs``, and every entry
      of that list must be a leg that actually declares ``zero_cost`` -- no silent
      additions, no dead entries.

    Skipped entirely when ``conventions.numeraire`` is undeclared (the permissive
    default for minimal hand-written fixtures that predate the block).
    ``ah.eval.prereg.verify()`` requires the real pre-registration to declare it.
    """
    if not conventions.numeraire:
        return

    declared_zero_cost: set[str] = set()
    for strategy in strategies:
        for leg in strategy_legs(strategy):
            if leg in derived:
                leg_numeraire = derived[leg].numeraire
                where = f"derived_series.{leg}.numeraire"
            else:
                leg_numeraire = manifest.sources[leg].numeraire or ""
                where = f"factors.yaml factor_sources.{leg}.numeraire"
            if not leg_numeraire:
                raise StrategyError(
                    f"{source}: d4_strategies.{strategy.strategy_id} leg '{leg}' declares "
                    f"no numeraire ({where} is unset); conventions.numeraire is "
                    f"'{conventions.numeraire}', so every leg must state which numeraire "
                    f"it is on"
                )
            if leg_numeraire == "zero_cost":
                declared_zero_cost.add(leg)
                if leg not in conventions.zero_cost_legs:
                    raise StrategyError(
                        f"{source}: d4_strategies.{strategy.strategy_id} leg '{leg}' is "
                        f"'zero_cost' but is not listed in "
                        f"conventions.numeraire_zero_cost_legs; a self-financing overlay "
                        f"combined with total-return legs must be declared, not merely tagged"
                    )
            elif leg_numeraire != conventions.numeraire:
                raise StrategyError(
                    f"{source}: d4_strategies.{strategy.strategy_id} leg '{leg}' is on "
                    f"numeraire '{leg_numeraire}', but conventions.numeraire is "
                    f"'{conventions.numeraire}'; a fully-invested portfolio may not sum "
                    f"legs quoted on different numeraires ({where})"
                )

    dead = sorted(set(conventions.zero_cost_legs) - declared_zero_cost)
    if dead:
        raise StrategyError(
            f"{source}: conventions.numeraire_zero_cost_legs names {dead}, which no D4 "
            f"strategy leg declares as 'zero_cost'; the list must name exactly the "
            f"zero-cost legs actually held"
        )


@lru_cache
def _load_d4_strategies_cached(resolved_path: Path) -> tuple[Strategy, ...]:
    raw = _read_doc(resolved_path).get("d4_strategies")
    if not isinstance(raw, dict) or not raw:
        raise StrategyError(f"{resolved_path}: 'd4_strategies' must be a non-empty mapping")

    manifest = load_manifest()
    active_factors = frozenset(manifest.active_factors())
    derived = _load_derived_series_cached(resolved_path)
    known_series = active_factors | frozenset(derived)
    conventions = _load_conventions_cached(resolved_path)
    strategies = tuple(
        _validate_strategy(entry, strategy_id, known_series, conventions, resolved_path)
        for strategy_id, entry in raw.items()
    )
    _validate_numeraires(strategies, derived, conventions, manifest, resolved_path)
    return strategies


def load_d4_strategies(path: Path | None = None) -> tuple[Strategy, ...]:
    """Load and validate the D4 strategy set, defaulting to the repo-root ``pre-registration.yaml``.

    Cached by resolved path (:func:`functools.lru_cache`) so every caller -- the
    battery and the WP2.8 tail auxiliary loss alike -- receives the *same*
    ``tuple[Strategy, ...]`` object (identity, not just equality).
    """
    resolved = (path if path is not None else _DEFAULT_PATH).resolve()
    return _load_d4_strategies_cached(resolved)
