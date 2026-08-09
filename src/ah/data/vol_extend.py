"""Extend ``equity_vol`` backward with observed VXO (WP-DATA-VOLEXT stage 1).

Why this module exists, and why it is not in ``ah.data.splice``
---------------------------------------------------------------
``equity_vol`` (`fred.VIX`) starts 1990-01 and binds
``bootstrap_v1.block_draw_span`` (see ``pre-registration.yaml``,
``block_draw_span_consequence``). `fred.VXO` -- the original S&P 100
implied-vol index -- is observed from 1986-01, free and licence-clean:
four more years of real implied-vol prints, reaching exactly where
``funding_spread`` (TED, 1986-01) binds next. Observation is preferred to
modelling wherever it exists; the model-based backcast below 1986 is stage 2
(`Instructions/TASK-vol-backcast-claude-code.md`).

``ah.data.splice`` (including its ``PROXY_RULES`` registry) and
``ah.data.derive`` are hashed by ``pre-registration.lock``. This module
therefore consumes the splice framework READ-ONLY: the rule is declared here
in the registry's own :class:`~ah.data.splice.ProxyRule` shape, and the fit
is implemented here because the sealed ``"regression"`` transform is
level-space while VXO needs a log-log link (VXO is ATM S&P 100 implied vol
and runs systematically ABOVE VIX; the relationship is multiplicative, not
additive). Moving the rule into the sealed registry and wiring the factor
read path happens once, under the proposed ``block_draw_span`` amendment
(``governance/proposed/``), if the owner ratifies it. Until then nothing
sealed consumes this module's output.

Discipline, identical to ``ah.data.splice``
-------------------------------------------
A synthetic observation is never silent: every extension row carries
``is_proxy=True`` and the rule id; a proxy NEVER overwrites an observed
month; and the fit must clear :func:`overlap_stats` scrutiny before anyone
accepts the output. Owner decisions D1-D5 for this work package are recorded
in ``docs/superpowers/specs/2026-08-09-volext-decisions.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.splice import ProxyRule

__all__ = [
    "MIN_OVERLAP_MONTHS",
    "VXO_RULE",
    "LogLogFit",
    "VolExtension",
    "extend_equity_vol",
    "fit_loglog",
    "overlap_stats",
]

#: The rule, in the sealed registry's own shape so ratification can move it
#: verbatim. ``transform`` names the link this module implements; the sealed
#: ``splice.fit_transform`` would reject it, which is correct -- this rule is
#: not applied by sealed code.
VXO_RULE = ProxyRule(
    rule_id="PROXY-EQUITY-VOL-VXO-V1",
    target="fred.VIX",
    donor="fred.VXO",
    transform="log_regression",
    overlap_start="1990-01-01",
    doc=(
        "ATM S&P 100 implied vol (VXO, observed from 1986-01) mapped to VIX "
        "by log-log regression on the 1990+ overlap. VXO runs systematically "
        "above VIX, so the link is multiplicative: log VIX = a + b log VXO."
    ),
)

#: Below this many overlapping months the fit is refused outright. Five years
#: of monthly data is the floor for estimating a two-parameter log link whose
#: output feeds a tail-sensitive panel.
MIN_OVERLAP_MONTHS = 60


@dataclass(frozen=True)
class LogLogFit:
    """``log(target) = a + b * log(donor)``, OLS on the overlap."""

    a: float
    b: float
    n_obs: int
    overlap: tuple[str, str]

    def predict_level(self, donor_values: np.ndarray) -> np.ndarray:
        return np.exp(self.a + self.b * np.log(np.clip(donor_values, 1e-6, None)))


@dataclass(frozen=True)
class VolExtension:
    """The extended series, splice-shaped: ``date, value, is_proxy, rule_id``."""

    series_id: str
    frame: pd.DataFrame
    fit: LogLogFit


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


def _overlap_index(target: pd.Series, donor: pd.Series, rule: ProxyRule) -> pd.DatetimeIndex:
    common = target.index.intersection(donor.index)
    if rule.overlap_start is not None:
        common = common[common >= pd.Timestamp(rule.overlap_start)]
    if rule.overlap_end is not None:
        common = common[common <= pd.Timestamp(rule.overlap_end)]
    return common


def fit_loglog(target: pd.DataFrame, donor: pd.DataFrame, rule: ProxyRule = VXO_RULE) -> LogLogFit:
    """Fit ``log(target) = a + b log(donor)`` on the overlap window.

    Refuses to fit on fewer than :data:`MIN_OVERLAP_MONTHS` common months --
    a short overlap gives a link whose extrapolation into the 1986-89 tail
    (the whole point of the rule) is unsupported.
    """
    t, d = _monthly(target), _monthly(donor)
    common = _overlap_index(t, d, rule)
    if len(common) < MIN_OVERLAP_MONTHS:
        raise ValueError(
            f"rule {rule.rule_id}: overlap too short to fit "
            f"({len(common)} months, need >= {MIN_OVERLAP_MONTHS})"
        )
    y = np.log(np.clip(t.loc[common].to_numpy(), 1e-6, None))
    x = np.log(np.clip(d.loc[common].to_numpy(), 1e-6, None))
    b = float(np.cov(x, y, bias=True)[0, 1] / np.var(x))
    a = float(y.mean() - b * x.mean())
    return LogLogFit(
        a=a,
        b=b,
        n_obs=len(common),
        overlap=(str(common.min().date()), str(common.max().date())),
    )


def extend_equity_vol(
    target: pd.DataFrame, donor: pd.DataFrame, rule: ProxyRule = VXO_RULE
) -> VolExtension:
    """Extend the target backward with the transformed donor.

    Same two invariants as ``ah.data.splice.splice``: proxies fill only
    pre-history the target does not cover, and no observed month is ever
    overwritten. The output frame is splice-shaped so downstream tooling
    cannot tell the two frameworks apart.
    """
    fit = fit_loglog(target, donor, rule)
    t, d = _monthly(target), _monthly(donor)
    target_min = t.index.min()

    pre = d[d.index < target_min]
    proxy = pd.DataFrame(
        {
            "date": pre.index,
            "value": fit.predict_level(pre.to_numpy()),
            "is_proxy": True,
        }
    )
    actual = pd.DataFrame({"date": t.index, "value": t.to_numpy(), "is_proxy": False})
    out = pd.concat([proxy, actual], ignore_index=True).sort_values(by="date", ignore_index=True)
    out["rule_id"] = rule.rule_id
    return VolExtension(f"{rule.target}__extended", out, fit)


def overlap_stats(
    target: pd.DataFrame, donor: pd.DataFrame, rule: ProxyRule = VXO_RULE
) -> dict[str, float]:
    """The overlap-fit scrutiny the task requires before anyone accepts this.

    Returns RMSE in log space (proportional error), RMSE in level points, and
    the log-level correlation on the overlap window.
    """
    fit = fit_loglog(target, donor, rule)
    t, d = _monthly(target), _monthly(donor)
    common = _overlap_index(t, d, rule)
    actual = t.loc[common].to_numpy()
    pred = fit.predict_level(d.loc[common].to_numpy())
    log_err = np.log(actual) - np.log(np.clip(pred, 1e-6, None))
    corr = float(np.corrcoef(np.log(actual), np.log(pred))[0, 1])
    return {
        "n_obs": float(fit.n_obs),
        "a": fit.a,
        "b": fit.b,
        "rmse_log": float(np.sqrt(np.mean(log_err**2))),
        "rmse_level": float(np.sqrt(np.mean((actual - pred) ** 2))),
        "corr_log": corr,
    }
