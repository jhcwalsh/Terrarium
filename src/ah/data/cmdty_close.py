"""The commodities total-return construction from AQR CFTLR (WP-DATA-CMDTY).

Why this module exists
----------------------
``commodities`` is the platform's sealed missing factor
(``factors.yaml`` ``kind: unavailable``; named in ``pre-registration.yaml``
``missing_factors``): the free commodity series are PRICE indices, and the
sealed factor spec demands ``numeraire: total_return``. The owner-supplied
AQR Commodities-for-the-Long-Run set carries the monthly EXCESS return of an
investable equal-weight futures portfolio from 1877-02 — and excess plus the
registered risk-free leg IS total return. Owner rulings C1-C3 (2026-08-09,
``docs/superpowers/specs/2026-08-09-cmdty-scoping.md``): the equal-weight
excess leg is the factor's basis; REG licence posture (attribution, no
redistribution, workbook in gitignored ``data/aqr/``); this WP delivers the
verified series and a PROPOSED amendment only — the sealed
``missing_factors`` entry, the re-seal, and the factor's activation are all
the owner's ratification, not this module's doing.

Discipline, following the extension family
------------------------------------------
``factors.yaml``, ``splice.py`` and ``derive.py`` are hashed by
``pre-registration.lock``; nothing sealed learns this construction (a test
pins that ``commodities`` is still ``kind: unavailable``). Every derived
frame carries the rule id and the attribution string. The pre-1926 months
(before the registered risk-free leg begins) remain EXCESS-only and are
excluded from the total-return frame rather than silently zero-filled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "ATTRIBUTION",
    "RULE_ID",
    "CmdtySeries",
    "cross_check",
    "total_return",
]

RULE_ID = "CMDTY-CFTLR-EW-TR-V1"

#: Rides in every derived artifact, per the REG licence terms.
ATTRIBUTION = (
    "Underlying commodity portfolio returns (c)2018 Ari Levine, Yao Hua Ooi, "
    "Matthew Richardson -- 'Commodities for the Long Run', AQR data library. "
    "Raw data not redistributed."
)


@dataclass(frozen=True)
class CmdtySeries:
    """The constructed factor series: ``date, value`` plus provenance."""

    series_id: str
    frame: pd.DataFrame
    rule_id: str
    attribution: str
    #: Months the source covers that the construction had to EXCLUDE because
    #: the risk-free leg does not reach them (excess-only pre-history).
    excess_only: tuple[str, str] | None


def _monthly(frame: pd.DataFrame) -> pd.Series:
    s = (
        frame.assign(date=pd.to_datetime(frame["date"]))
        .set_index("date")["value"]
        .astype(float)
        .dropna()
        .sort_index()
    )
    if not s.index.is_unique:
        raise ValueError("duplicate dates in input frame")
    return s


def total_return(excess: pd.DataFrame, rf: pd.DataFrame) -> CmdtySeries:
    """``total_return = excess + rf`` on their common months.

    ``excess`` is ``aqr.cmdty_ew_excess``; ``rf`` is the registered risk-free
    leg (``french.rf``, monthly decimal, 1926-07+). Source months before the
    risk-free leg begins are excluded and recorded in ``excess_only`` — never
    zero-filled, because a zero collateral yield is a claim, not a fact.
    """
    e, r = _monthly(excess), _monthly(rf)
    common = e.index.intersection(r.index)
    if len(common) < 12:
        raise ValueError(f"excess and rf share only {len(common)} months")
    values = e.loc[common] + r.loc[common]
    frame = pd.DataFrame({"date": common, "value": values.to_numpy()})

    pre = e.index[e.index < common.min()]
    excess_only = (str(pre.min().date()), str(pre.max().date())) if len(pre) else None
    return CmdtySeries(
        series_id="aqr.cmdty_ew_tr",
        frame=frame.reset_index(drop=True),
        rule_id=RULE_ID,
        attribution=ATTRIBUTION,
        excess_only=excess_only,
    )


def cross_check(spot: pd.DataFrame, price_index: pd.DataFrame) -> dict[str, float]:
    """Correlate the CFTLR spot RETURN with a free price INDEX's log returns.

    The only licence-free validation that exists: the registered
    ``fred.CMDTY_*`` indices are levels, so their month-over-month log
    returns should co-move with the portfolio's spot return on the overlap.
    A weak correlation here means the workbook was mis-parsed or the
    instruments diverge — either way a finding, not a formality.
    """
    s = _monthly(spot)
    level = _monthly(price_index)
    idx_ret = np.log(level.clip(lower=1e-9)).diff().dropna()
    common = s.index.intersection(idx_ret.index)
    if len(common) < 24:
        raise ValueError(f"cross-check overlap too short: {len(common)} months")
    corr = float(np.corrcoef(s.loc[common], idx_ret.loc[common])[0, 1])
    return {"n_obs": float(len(common)), "corr": corr}
