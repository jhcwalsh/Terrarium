"""Extend ``funding_spread`` beyond TED's life with the CP-bill spread (WP-DATA-FSEXT).

Why this module exists
----------------------
``funding_spread`` is ``derive.funding_stress(fred.TEDRATE)``: observed
1986-01..2022-01 and then nothing -- TED died with LIBOR, and
``factors.yaml``'s own notes call the post-2022 history honestly incomplete.
The commercial-paper minus Treasury-bill spread is the same *kind* of
quantity on both missing ends: the literature-standard funding-stress
measure for the pre-LIBOR era, and the registered successor construction
(``fred.CPF3M`` - ``fred.TB3M_SEC``) after it. Owner rulings F1-F3
(2026-08-09, recorded in ``docs/superpowers/specs/2026-08-09-fsext-scoping.md``):
CP-bill is accepted as the funding-stress recreation where LIBOR does not
exist, with the instrument difference disclosed; the post-2022 repair is in
scope; the extension floor is 1934-01 (the bill leg's start).

The construction, all observation
---------------------------------
CP leg, three segments chained onto the LIVE leg's level by mean offset on
their overlaps (newest wins where segments coexist): ``fred.CPF3M``
(AA financial CP, 1997+), ``fred.CP3M`` (discontinued plain CP, 1971-1997),
``fred.CP3M_NBER`` (NBER prime CP, 1857-1971). Bill leg: ``fred.TB3M_SEC``
(daily secondary market, 1954+) with ``fred.TB3MS`` (its monthly-average
ancestor) before 1954. The CP-bill spread is then mapped onto TED by level
regression on their 1986-2022 overlap (~430 months, spanning two CP
segments), and the fitted spread fills BOTH ends -- 1934-01..1985-12
backward, 2022-02.. forward.

Discipline, following ``ah.data.vol_extend``
--------------------------------------------
``ah.data.splice`` and ``ah.data.derive`` are hashed by
``pre-registration.lock``, so this module consumes the splice framework
read-only and nothing sealed learns the rule (a test pins it). One recorded
DEVIATION from the splice framework's shape: splice fills pre-history only;
this rule fills both ends, because the post-2022 hole is half the point
(owner ruling F2). The invariant that matters is unchanged -- an observed
TED month is NEVER overwritten. Every filled row carries ``is_proxy=True``
and the rule id; nothing consumes the output until the owner ratifies the
span amendment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.splice import ProxyRule

__all__ = [
    "FUNDING_RULE",
    "MIN_OVERLAP_MONTHS",
    "MIN_SEGMENT_OVERLAP_MONTHS",
    "FundingExtension",
    "LevelFit",
    "bill_series",
    "cp_series",
    "extend_funding_spread",
    "fit_level",
    "overlap_stats",
]

#: The rule, in the sealed registry's own shape so ratification can move it
#: verbatim. ``transform`` names the link this module implements; the sealed
#: ``splice.fit_transform`` would reject it, which is correct.
FUNDING_RULE = ProxyRule(
    rule_id="PROXY-FUNDING-CPBILL-V1",
    target="fred.TEDRATE",
    donor="cp_bill_spread",
    transform="level_regression_both_ends",
    overlap_start="1986-01-01",
    overlap_end="2022-01-31",
    doc=(
        "CP minus 3m bill (CP leg: CPF3M/CP3M/NBER chained by mean offset; "
        "bill leg: TB3M_SEC with TB3MS before 1954) mapped onto TED by level "
        "regression on the 1986-2022 overlap; fills 1934+ backward and "
        "post-2022 forward. TED is unsecured BANK funding, CP-bill high-grade "
        "CORPORATE funding -- accepted as the recreation by owner ruling F1, "
        "difference disclosed."
    ),
)

#: Below this many TED-overlap months the level fit is refused.
MIN_OVERLAP_MONTHS = 60

#: Below this many months of overlap between adjacent CP (or bill) segments,
#: the chain offset cannot be estimated and the join is refused.
MIN_SEGMENT_OVERLAP_MONTHS = 6


@dataclass(frozen=True)
class LevelFit:
    """``target = a + b * donor``, OLS on the overlap."""

    a: float
    b: float
    n_obs: int
    overlap: tuple[str, str]

    def predict(self, donor_values: np.ndarray) -> np.ndarray:
        return self.a + self.b * donor_values


@dataclass(frozen=True)
class FundingExtension:
    """The extended series, splice-shaped: ``date, value, is_proxy, rule_id``."""

    series_id: str
    frame: pd.DataFrame
    fit: LevelFit
    #: Per-join diagnostics: offset applied and overlap RMSE, keyed by join name.
    segments: dict[str, dict[str, float]]


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


def _chain(
    base: pd.Series, older: pd.Series, join: str, diagnostics: dict[str, dict[str, float]]
) -> pd.Series:
    """Extend ``base`` backward with ``older``, offset-matched on the overlap.

    The offset (mean level difference on common months) maps the older
    segment onto the base's level; the join's residual RMSE is recorded so
    instrument drift is measured, not assumed away. Months the base already
    covers always win.
    """
    common = base.index.intersection(older.index)
    if len(common) < MIN_SEGMENT_OVERLAP_MONTHS:
        raise ValueError(
            f"segment join {join}: overlap {len(common)} months "
            f"(need >= {MIN_SEGMENT_OVERLAP_MONTHS})"
        )
    offset = float((base.loc[common] - older.loc[common]).mean())
    rmse = float(np.sqrt(np.mean((base.loc[common] - (older.loc[common] + offset)) ** 2)))
    diagnostics[join] = {"offset": offset, "overlap_rmse": rmse, "n_overlap": float(len(common))}
    extension = (older + offset).loc[older.index < base.index.min()]
    return pd.concat([extension, base]).sort_index()


def cp_series(
    cpf3m: pd.DataFrame,
    cp3m: pd.DataFrame,
    nber: pd.DataFrame,
    diagnostics: dict[str, dict[str, float]] | None = None,
) -> pd.Series:
    """The CP leg: three segments chained onto the live series' level."""
    diag = diagnostics if diagnostics is not None else {}
    out = _chain(_monthly(cpf3m), _monthly(cp3m), "cp3m_onto_cpf3m", diag)
    return _chain(out, _monthly(nber), "nber_onto_cp3m", diag)


def bill_series(
    tb3m_sec: pd.DataFrame,
    tb3ms: pd.DataFrame,
    diagnostics: dict[str, dict[str, float]] | None = None,
) -> pd.Series:
    """The bill leg: daily-secondary-market months, monthly-average before 1954."""
    diag = diagnostics if diagnostics is not None else {}
    return _chain(_monthly(tb3m_sec), _monthly(tb3ms), "tb3ms_onto_tb3m_sec", diag)


def fit_level(ted: pd.DataFrame, spread: pd.Series, rule: ProxyRule = FUNDING_RULE) -> LevelFit:
    """Fit ``TED = a + b * (CP - bill)`` on the overlap window.

    A LEVEL link, not log-log: spreads live near zero and occasionally cross
    it, so log space is the wrong geometry here.
    """
    t = _monthly(ted)
    common = t.index.intersection(spread.index)
    if rule.overlap_start is not None:
        common = common[common >= pd.Timestamp(rule.overlap_start)]
    if rule.overlap_end is not None:
        common = common[common <= pd.Timestamp(rule.overlap_end)]
    if len(common) < MIN_OVERLAP_MONTHS:
        raise ValueError(
            f"rule {rule.rule_id}: overlap too short to fit "
            f"({len(common)} months, need >= {MIN_OVERLAP_MONTHS})"
        )
    y = t.loc[common].to_numpy()
    x = spread.loc[common].to_numpy()
    b = float(np.cov(x, y, bias=True)[0, 1] / np.var(x))
    a = float(y.mean() - b * x.mean())
    return LevelFit(
        a=a, b=b, n_obs=len(common), overlap=(str(common.min().date()), str(common.max().date()))
    )


def extend_funding_spread(
    ted: pd.DataFrame,
    cpf3m: pd.DataFrame,
    cp3m: pd.DataFrame,
    nber: pd.DataFrame,
    tb3m_sec: pd.DataFrame,
    tb3ms: pd.DataFrame,
    rule: ProxyRule = FUNDING_RULE,
    floor: str = "1934-01-01",
) -> FundingExtension:
    """Extend observed TED on BOTH ends with the fitted CP-bill spread.

    The recorded deviation from ``ah.data.splice``: proxies fill every month
    the target does not cover on either side (owner ruling F2 -- the
    post-2022 hole is half the point), floored at ``floor`` (ruling F3: the
    bill leg's start; nothing before it). An observed TED month is never
    overwritten, which is the invariant that matters.
    """
    segments: dict[str, dict[str, float]] = {}
    cp = cp_series(cpf3m, cp3m, nber, segments)
    bill = bill_series(tb3m_sec, tb3ms, segments)
    spread = (cp - bill.reindex(cp.index)).dropna()
    spread = spread.loc[spread.index >= pd.Timestamp(floor)]

    fit = fit_level(ted, spread, rule)
    t = _monthly(ted)

    fill_idx = spread.index.difference(t.index)
    proxy = pd.DataFrame(
        {
            "date": fill_idx,
            "value": fit.predict(spread.loc[fill_idx].to_numpy()),
            "is_proxy": True,
        }
    )
    actual = pd.DataFrame({"date": t.index, "value": t.to_numpy(), "is_proxy": False})
    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = rule.rule_id
    return FundingExtension(f"{rule.target}__extended", out, fit, segments)


def overlap_stats(
    ted: pd.DataFrame, spread: pd.Series, rule: ProxyRule = FUNDING_RULE
) -> dict[str, float]:
    """The overlap scrutiny: RMSE and correlation of the fitted spread vs TED."""
    fit = fit_level(ted, spread, rule)
    t = _monthly(ted)
    common = t.index.intersection(spread.index)
    if rule.overlap_start is not None:
        common = common[common >= pd.Timestamp(rule.overlap_start)]
    if rule.overlap_end is not None:
        common = common[common <= pd.Timestamp(rule.overlap_end)]
    actual = t.loc[common].to_numpy()
    pred = fit.predict(spread.loc[common].to_numpy())
    return {
        "n_obs": float(fit.n_obs),
        "a": fit.a,
        "b": fit.b,
        "rmse": float(np.sqrt(np.mean((actual - pred) ** 2))),
        "corr": float(np.corrcoef(actual, pred)[0, 1]),
    }
