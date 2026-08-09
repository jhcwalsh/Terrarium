"""The pegged-era dollar index, 1953-04..1972-12 (WP-DATA-SPAN53).

Owner design ruling (2026-08-09, the 1953-04 span decision): before floating
began in 1973-03, the dollar's trade-weighted value against the majors was
FIXED by the Bretton Woods parity system — near-zero month-to-month movement
was not missing data, it was the reality. The honest pre-1973 ``fx_usd`` is
therefore a step function built from the PUBLISHED official parities: flat
between realignments, jumping on the documented revaluation dates. The
information content is the steps; the level is pinned to the observed
``fred.DTWEXM`` at its 1973-01 start (there is no overlap by construction —
the junction is a single-point level pin, disclosed as such).

Construction: a geometric equal-weight basket of six pegged majors (DEM,
JPY, GBP, FRF, CHF, ITL). Equal weights are a DOCUMENTED CHOICE — period
trade weights are not freely licensable, and with a step function the
weights only scale the step sizes. Canada is EXCLUDED and disclosed: the
CAD floated 1950-62, so it has no parity to tabulate, and its free market
series start 1971. The 1971-08..1971-11 interregnum (gold window closed,
Smithsonian not yet agreed) is carried at prior parities, disclosed.

Parities (units of foreign currency per USD; NEW francs throughout), from
the published IMF par-value record — historical facts, tabulated:

    DEM  4.20 -> 4.00 (1961-03) -> 3.66 (1969-10) -> 3.2225 (1971-12)
    JPY  360                    -> 308 (1971-12)
    GBP  (USD per GBP 2.80 -> 2.40 at 1967-11, i.e. 0.3571 -> 0.4167)
                                -> 0.3838 (1971-12, $2.6057)
    FRF  3.50 -> 4.20 (1957-08) -> 4.937 (1958-12) -> 5.554 (1969-08)
                                -> 5.1157 (1971-12)
    CHF  4.373                  -> 3.84 (1971-12)
    ITL  625                    -> 581.5 (1971-12)

Sealed surfaces untouched (tested); nothing consumed until ratification.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.splice import ProxyRule

__all__ = ["FX_PARITY_RULE", "PARITIES", "FxParityExtension", "extend_fx", "parity_index"]

FX_PARITY_RULE = ProxyRule(
    rule_id="PROXY-FX-PARITY-V1",
    target="fred.DTWEXM",
    donor="published Bretton Woods parities (vendored table)",
    transform="parity_step_index",
    doc=(
        "Geometric equal-weight USD index over six pegged majors from the "
        "published par-value record; flat between realignments, stepping on "
        "the documented dates; level-pinned to DTWEXM's first observation. "
        "Near-zero variance is the era's true value, not an artifact."
    ),
)

#: currency -> list of (effective month, foreign-currency units per USD).
PARITIES: dict[str, tuple[tuple[str, float], ...]] = {
    "DEM": (("1953-04", 4.20), ("1961-03", 4.00), ("1969-10", 3.66), ("1971-12", 3.2225)),
    "JPY": (("1953-04", 360.0), ("1971-12", 308.0)),
    "GBP": (("1953-04", 1.0 / 2.80), ("1967-11", 1.0 / 2.40), ("1971-12", 1.0 / 2.6057)),
    "FRF": (
        ("1953-04", 3.50),
        ("1957-08", 4.20),
        ("1958-12", 4.937),
        ("1969-08", 5.554),
        ("1971-12", 5.1157),
    ),
    "CHF": (("1953-04", 4.373), ("1971-12", 3.84)),
    "ITL": (("1953-04", 625.0), ("1971-12", 581.5)),
}

START, END = "1953-04-01", "1972-12-01"


@dataclass(frozen=True)
class FxParityExtension:
    series_id: str
    frame: pd.DataFrame
    #: The single-point junction scale applied to pin the index to DTWEXM.
    junction_scale: float


def parity_index() -> pd.Series:
    """The unscaled geometric equal-weight USD index, monthly, 1953-04..1972-12.

    Rebased so 1953-04 = 100; steps land on the documented realignment
    months. Rising = stronger dollar (more foreign units per USD).
    """
    months = pd.date_range(START, END, freq="MS")
    w = 1.0 / len(PARITIES)
    log_idx = np.zeros(len(months))
    for steps in PARITIES.values():
        rates = np.empty(len(months))
        for eff, rate in steps:  # steps are chronological; later entries overwrite
            rates[months >= pd.Timestamp(eff + "-01")] = rate
        log_idx += w * np.log(rates / steps[0][1])
    return pd.Series(100.0 * np.exp(log_idx), index=months, name="fx_parity")


def extend_fx(dtwexm: pd.DataFrame) -> FxParityExtension:
    """Prepend the parity index to observed DTWEXM, pinned at the junction.

    There is no overlap by construction (parities end when floating starts),
    so the pin is DTWEXM's first observation divided by the parity index's
    last value — a level continuity condition, not a fit, and disclosed as
    such. Observed months are never overwritten.
    """
    d = (
        dtwexm.assign(date=pd.to_datetime(dtwexm["date"]))
        .set_index("date")["value"]
        .astype(float)
        .dropna()
        .sort_index()
    )
    if not d.index.is_unique:
        raise ValueError("duplicate dates in input frame")
    par = parity_index()
    pre = par.loc[par.index < d.index.min()]
    if len(pre) == 0:
        raise ValueError("nothing to prepend: the observed series starts before the parity era")
    scale = float(d.iloc[0]) / float(pre.iloc[-1])
    proxy = pd.DataFrame({"date": pre.index, "value": (pre * scale).to_numpy(), "is_proxy": True})
    actual = pd.DataFrame({"date": d.index, "value": d.to_numpy(), "is_proxy": False})
    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = FX_PARITY_RULE.rule_id
    return FxParityExtension(f"{FX_PARITY_RULE.target}__extended", out, scale)
