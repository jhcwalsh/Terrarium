"""Generated world -> the monthly series the narration layer needs (task §1).

The mapping from what ``hier-flow-v1`` actually emits onto DN-9's input contract
is written down once, here, and stamped into every manifest. Three rules:

* **A required series that is not available fails, naming it.** It is never
  synthesised — a narration layer that invents its own inputs is a second
  generator (DN-9 §3.4).
* **Optional book series absent means the CAPITAL slot is omitted and the
  omission is stated on the artifact.** Never stubbed with zeros.
* **Every derived observable is registered** — name, source, transform,
  parameters, and the fact that it is derived — and every parameter of every
  transform comes from ``voices.yaml`` or the run does not start.

Nothing here reads unrevealed state: the whole path is in scope because the
workbench renders the whole decade at once, but each series at month *t* is a
function of factors at month *t* (or earlier) only. The reveal-clock scoping of
DN-9 §2.1 is the *session service's* job, not the workbench's, and is out of
this task's scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.gen.base import Ensemble, RegimeRecord, SlowStateRecord, UnknownFactorError
from ah.narration.constants import (
    BPS_PER_PP,
    EQUITY_INDEX_BASE,
    L1_STATE_NAMES,
    MONTHS_PER_QUARTER,
    MONTHS_PER_YEAR,
    OPTIONAL_SERIES,
    PERCENT,
    THOUSANDS_PER_MILLION,
)
from ah.narration.errors import MissingSeriesError, NarrationError

__all__ = ["WorldSeries", "build_world_series"]


@dataclass(frozen=True)
class WorldSeries:
    """The DN-9 §1 input contract for one realised path."""

    months: int
    series: dict[str, np.ndarray]
    regime: tuple[str, ...]
    l1_state: dict[str, np.ndarray]
    optional: dict[str, np.ndarray]
    absent_optional: tuple[str, ...]
    derived_register: tuple[dict[str, Any], ...]
    mapping_notes: tuple[str, ...]
    warmup_months: int
    extras: tuple[str, ...] = field(default_factory=tuple)

    @property
    def book_available(self) -> bool:
        """True when the optional book series are present.

        False here is not a degraded build: it is the stated condition under
        which CAPITAL is omitted and the omission is printed.
        """
        return bool(self.optional)


def _factor(ensemble: Ensemble, name: str, path_index: int, *, needed_for: str) -> np.ndarray:
    try:
        return np.asarray(ensemble.factor(name)[path_index], dtype=np.float64)
    except UnknownFactorError as exc:
        raise MissingSeriesError(
            needed_for,
            detail=(
                f"it maps from the generator factor '{name}', which this ensemble does not "
                f"carry. Available factors: {list(ensemble.factor_names)}. The adapter does "
                "not synthesise a missing input."
            ),
        ) from exc


def _yoy(level: np.ndarray, window: int, warmup_policy: str) -> tuple[np.ndarray, int]:
    """Year-on-year rate, in percent, from a level index.

    ``warmup_policy`` is a resolved value from ``voices.yaml`` — the first
    ``window`` months have no year-on-year figure and what happens there is a
    decision, not an implementation detail.
    """
    out = np.full(level.shape, np.nan, dtype=np.float64)
    out[window:] = (level[window:] / level[:-window] - 1.0) * PERCENT
    if warmup_policy == "nan_suppress":
        return out, window
    if warmup_policy == "annualise_available":
        months = np.arange(1, window + 1, dtype=np.float64)
        out[:window] = ((level[:window] / level[0]) ** (MONTHS_PER_YEAR / months) - 1.0) * PERCENT
        out[0] = out[1] if window > 1 else 0.0
        return out, 0
    if warmup_policy == "require_extra_history":
        raise NarrationError(
            "adapter.cpi_yoy_warmup is 'require_extra_history': the world must be generated "
            f"with {window} months of run-in ahead of the narrated decade. This world was "
            "not, and the adapter does not backfill. Regenerate the world or choose another "
            "warmup policy."
        )
    raise NarrationError(f"adapter.cpi_yoy_warmup: unknown policy '{warmup_policy}'")


def build_world_series(
    ensemble: Ensemble,
    *,
    path_index: int,
    params: dict[str, Any],
) -> WorldSeries:
    """Map one path of ``ensemble`` onto the input contract.

    ``params`` carries the already-resolved adapter and derived-observable
    parameters (see :func:`ah.narration.build.adapter_params`). This function
    never reads ``voices.yaml`` itself, so the "no value without a decision"
    rule is enforced in one place rather than at every call site.
    """
    notes: list[str] = []

    policy_rate = _factor(ensemble, "policy_rate", path_index, needed_for="policy_rate")
    ust_10y = _factor(ensemble, "ust_10y", path_index, needed_for="ust_10y")
    ust_2y = _factor(ensemble, "ust_2y", path_index, needed_for="curve_2s10s")
    hy_spread = _factor(ensemble, "hy_spread", path_index, needed_for="hy_oas")
    cpi_level = _factor(ensemble, "cpi", path_index, needed_for="cpi_yoy")
    equity_returns = _factor(ensemble, "equity_mkt", path_index, needed_for="equity_index")

    notes.append("policy_rate <- factor policy_rate (percent, direct)")
    notes.append("ust_10y <- factor ust_10y (percent, direct)")
    notes.append("curve_2s10s <- (ust_10y - ust_2y) * 100, basis points")
    notes.append("hy_oas <- hy_spread * 100, basis points")
    notes.append("equity_index <- cumulative product of equity_mkt returns, base 100")

    window = int(params["headline_cpi"]["yoy_window_months"])
    cpi_yoy, warmup = _yoy(cpi_level, window, str(params["cpi_yoy_warmup"]))
    notes.append(
        f"cpi_yoy <- {window}-month yoy of the cpi LEVEL index, percent; "
        f"warmup policy '{params['cpi_yoy_warmup']}' leaves {warmup} month(s) without a print"
    )

    if not isinstance(ensemble.regimes, RegimeRecord):
        reason = getattr(ensemble.regimes, "reason", "the ensemble carries no regime record")
        raise MissingSeriesError("regime", detail=reason)
    legend = ensemble.regimes.legend
    regime = tuple(str(legend[int(code)]) for code in ensemble.regimes.labels[path_index])
    notes.append("regime <- regimes.labels resolved through regimes.legend, per month (L2)")

    if not isinstance(ensemble.slow_states, SlowStateRecord):
        reason = getattr(ensemble.slow_states, "reason", "the ensemble carries no slow states")
        raise MissingSeriesError("l1_state", detail=reason)
    names = tuple(ensemble.slow_states.names)
    missing = [name for name in L1_STATE_NAMES if name not in names]
    if missing:
        raise MissingSeriesError(
            "l1_state",
            detail=f"slow states {missing} are absent; ensemble carries {list(names)}",
        )
    l1_state = {
        name: np.asarray(ensemble.slow_states.states[path_index, :, names.index(name)], np.float64)
        for name in L1_STATE_NAMES
    }
    notes.append(
        "l1_state <- SlowStateRecord (pi_star, r_star, g, v, credit_gap); DN-9's unnamed "
        "'L' slot is filled by credit_gap, which is what §D.1 describes it as"
    )

    equity_index = EQUITY_INDEX_BASE * np.cumprod(1.0 + equity_returns)

    series: dict[str, np.ndarray] = {
        "policy_rate": policy_rate,
        "cpi_yoy": cpi_yoy,
        "equity_index": equity_index,
        "equity_return": equity_returns,
        "hy_oas": hy_spread * BPS_PER_PP,
        "curve_2s10s": (ust_10y - ust_2y) * BPS_PER_PP,
        "ust_10y": ust_10y,
    }

    extras: list[str] = []
    if "equity_vol" in ensemble.factor_names:
        series["equity_vol"] = _factor(ensemble, "equity_vol", path_index, needed_for="equity_vol")
        extras.append("equity_vol")
        notes.append("equity_vol <- factor equity_vol (annualised percent); E09's only input")

    # ---- derived observables (DN-9 §3.4), each registered with its transform
    growth = l1_state["g"]
    okun = params["unemployment"]
    unemployment = np.maximum(
        0.0, float(okun["u_star"]) - float(okun["beta"]) * (growth - float(okun["g_star"]))
    )
    payroll_params = params["payrolls_change"]
    delta_u = np.diff(unemployment, prepend=unemployment[0])
    payrolls = float(payroll_params["trend_thousands"]) - delta_u * float(
        payroll_params["labour_force_millions"]
    ) * (THOUSANDS_PER_MILLION / PERCENT)

    growth_transform = str(params["growth_print"]["transform"])
    if growth_transform == "identity":
        growth_print = growth.copy()
    elif growth_transform == "annualised_qoq":
        growth_print = np.full_like(growth, np.nan)
        lag = MONTHS_PER_QUARTER
        growth_print[lag:] = growth[lag:] - growth[:-lag]
    else:
        raise NarrationError(
            f"derived_observables.growth_print: unknown transform '{growth_transform}'"
        )

    series["unemployment"] = unemployment
    series["payrolls_change"] = payrolls
    series["headline_cpi"] = cpi_yoy
    series["growth_print"] = growth_print

    register = (
        {
            "name": "unemployment",
            "source": "g",
            "source_kind": "l1_state",
            "transform": "okun",
            "params": dict(okun),
            "derived": True,
        },
        {
            "name": "payrolls_change",
            "source": "unemployment",
            "source_kind": "derived_observable",
            "transform": "labour_force_scaling",
            "params": dict(payroll_params),
            "derived": True,
        },
        {
            "name": "headline_cpi",
            "source": "cpi",
            "source_kind": "factor",
            "transform": "yoy",
            "params": dict(params["headline_cpi"]),
            "derived": True,
        },
        {
            "name": "growth_print",
            "source": "g",
            "source_kind": "l1_state",
            "transform": growth_transform,
            "params": dict(params["growth_print"]),
            "derived": True,
        },
    )

    optional: dict[str, np.ndarray] = {}
    absent = tuple(name for name in OPTIONAL_SERIES if name not in optional)
    if absent:
        notes.append(
            "book series absent from this generator: "
            + ", ".join(absent)
            + " — the CAPITAL slot is omitted and the omission is stated on the artifact"
        )

    return WorldSeries(
        months=int(ensemble.months),
        series=series,
        regime=regime,
        l1_state=l1_state,
        optional=optional,
        absent_optional=absent,
        derived_register=register,
        mapping_notes=tuple(notes),
        warmup_months=warmup,
        extras=tuple(extras),
    )
