"""Does the de-smoother actually recover risk? The check, as pure functions.

``run_hf_desmoothing.py`` reports the hedge-fund sleeves' de-smoothing
diagnostics. This is the private-markets analogue, plus the thing HF has no
equivalent of: a MARKET-PRICED COMPARATOR. Where a listed vehicle tracks the
same underlying asset class, its volatility bounds how much risk an
appraisal-marked series should be hiding — an independent read on whether the
de-smoothing operator is doing anything at all.

Two findings this exists to keep visible, both measured 2026-08-08:

* A de-smoother can be a LITERAL NO-OP and say nothing about it. On
  ``albourne.pm_dl_ret_q`` both ``glm_ma`` and ``geltner_ar1`` returned the
  input unchanged to four decimal places, because the series' lag-1
  autocorrelation is NEGATIVE (-0.050) and both operators key on positive
  autocorrelation (Geltner clips phi to [0, 0.95], so phi=0, a=1,
  truth=obs). An operator that quietly does nothing looks identical to one
  that found nothing to do; ``is_noop`` separates them.
* A comparator ratio is NOT a correction target. Listed BDCs run ~2.75x the
  reported private-credit volatility, but they are levered roughly 1x and
  carry listing sentiment, so most of that gap is structural rather than
  smoothing. The ratio is an UPPER BOUND on what de-smoothing should recover.

Deliberately OUTSIDE the pre-registration seal: this reads sealed artifacts
and reports on them, it produces no judged input. Nothing here may be used to
tune a de-smoother — that would be fitting the estimator to its own audit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.desmooth import DesmoothResult, geltner_ar1, glm_ma

#: Appraisal-marked series -> the market-priced series that tracks the same
#: asset class. Adding an entry is a claim that the two are comparable AFTER
#: the caveats in this module's docstring; it is never automatic.
COMPARATORS: dict[str, str] = {
    "albourne.pm_dl_ret_q": "cliffwater.bdc_ret_m",
}

#: A ratio at or below this is treated as the operator having done nothing.
NOOP_TOLERANCE = 1e-6


def to_quarterly(values: pd.Series) -> pd.Series:
    """Compound a monthly return series into quarters (comparator alignment)."""
    quarters = pd.PeriodIndex(pd.DatetimeIndex(values.index), freq="Q")
    out = (1.0 + values).groupby(quarters).prod() - 1.0
    return out.sort_index()


def acf1(values: np.ndarray) -> float:
    """Lag-1 autocorrelation; nan for a series too short or flat to have one."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 3 or x.std() == 0.0:
        return float("nan")
    return float(pd.Series(x).autocorr(1))


@dataclass(frozen=True)
class SleeveCheck:
    """One appraisal-marked series, put through its own de-smoother."""

    series_id: str
    method: str
    n_obs: int
    sigma_reported: float
    sigma_desmoothed: float
    acf1_reported: float
    acf1_desmoothed: float
    comparator: str | None = None
    sigma_comparator: float | None = None
    n_overlap: int | None = None

    @property
    def sigma_ratio(self) -> float:
        """Volatility recovered by de-smoothing. 1.0 means nothing was."""
        if self.sigma_reported == 0.0:
            return float("nan")
        return self.sigma_desmoothed / self.sigma_reported

    @property
    def is_noop(self) -> bool:
        """The operator returned its input: no risk recovered, at all."""
        return bool(abs(self.sigma_ratio - 1.0) <= NOOP_TOLERANCE)

    @property
    def comparator_ratio(self) -> float | None:
        """Market-priced volatility over REPORTED volatility — an upper bound
        on what de-smoothing could justify recovering, never a target."""
        if self.sigma_comparator is None or self.sigma_reported == 0.0:
            return None
        return self.sigma_comparator / self.sigma_reported


def check_sleeve(
    series_id: str,
    reported: pd.Series,
    *,
    family: str,
    comparator: pd.Series | None = None,
    comparator_id: str | None = None,
) -> SleeveCheck:
    """Run the sleeve's OWN de-smoothing family over its reported returns and
    measure what came back. ``comparator`` is aligned to the reported series'
    own periods before its volatility is taken, so the two are contemporaneous.
    """
    values = pd.to_numeric(reported).to_numpy(dtype=float)
    fit: DesmoothResult = geltner_ar1(values) if family == "geltner" else glm_ma(values)

    sigma_comparator: float | None = None
    n_overlap: int | None = None
    if comparator is not None and len(comparator) > 1:
        common = comparator.index.intersection(reported.index)
        n_overlap = len(common)
        if n_overlap > 1:
            sigma_comparator = float(comparator.reindex(common).std(ddof=1))
            # measure the reported leg on the SAME quarters, or the ratio
            # compares different market histories
            values_common = pd.to_numeric(reported.reindex(common)).to_numpy(dtype=float)
            return SleeveCheck(
                series_id=series_id,
                method=fit.method,
                n_obs=len(values),
                sigma_reported=float(np.std(values_common, ddof=1)),
                sigma_desmoothed=float(np.std(fit.truth, ddof=1)),
                acf1_reported=acf1(values),
                acf1_desmoothed=acf1(fit.truth),
                comparator=comparator_id,
                sigma_comparator=sigma_comparator,
                n_overlap=n_overlap,
            )

    return SleeveCheck(
        series_id=series_id,
        method=fit.method,
        n_obs=len(values),
        sigma_reported=float(np.std(values, ddof=1)),
        sigma_desmoothed=float(np.std(fit.truth, ddof=1)),
        acf1_reported=acf1(values),
        acf1_desmoothed=acf1(fit.truth),
        comparator=comparator_id,
        sigma_comparator=sigma_comparator,
        n_overlap=n_overlap,
    )


def render_markdown(checks: list[SleeveCheck], *, vintage: str, as_of: str) -> str:
    """The exhibit. No-ops are called out in prose, not left to the reader."""
    lines = [
        "# De-smoothing validation — private markets",
        "",
        f"*Generated by `scripts/validate_desmoothing.py` from vintage `{vintage}`,",
        f"as of {as_of}. Regenerate it after every delivery; it is a DIAGNOSTIC and",
        "sits outside the pre-registration seal — nothing here may be used to tune a",
        "de-smoother, which would be fitting the estimator to its own audit.*",
        "",
        "**Span: FULL history, not train+validation.** The estimators that produce",
        "the sealed artifacts read `train_val` and therefore see fewer observations;",
        "an `n` here will not match the `n_obs` in the smoothing kernel, and the",
        "fitted parameters differ accordingly. That is deliberate — an audit should",
        "see everything the vendor delivered — but it means these numbers describe",
        "the data, not the sealed estimates.",
        "",
        "`sigma ratio` is de-smoothed volatility over reported. **1.00 means the",
        "operator recovered nothing.** `comparator ratio` is a market-priced proxy's",
        "volatility over the same reported series, on shared periods only — an UPPER",
        "bound on what de-smoothing could justify, never a target: listed vehicles",
        "carry leverage and listing sentiment the private index does not.",
        "",
        "| series | family | n | sigma reported | sigma de-smoothed | sigma ratio | "
        "ACF1 before | ACF1 after | comparator | comparator ratio |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in checks:
        comp = f"{c.comparator} (n={c.n_overlap})" if c.comparator else "—"
        comp_ratio = f"{c.comparator_ratio:.2f}x" if c.comparator_ratio is not None else "—"
        flag = " ⚠" if c.is_noop else ""
        lines.append(
            f"| {c.series_id} | {c.method} | {c.n_obs} | {c.sigma_reported:.4f} | "
            f"{c.sigma_desmoothed:.4f} | {c.sigma_ratio:.3f}{flag} | "
            f"{c.acf1_reported:+.3f} | {c.acf1_desmoothed:+.3f} | {comp} | {comp_ratio} |"
        )

    noops = [c for c in checks if c.is_noop]
    lines += ["", "## No-ops", ""]
    if noops:
        lines.append(
            "The following series came back from their de-smoother UNCHANGED. An "
            "operator that quietly does nothing looks identical to one that found "
            "nothing to do, so each is named here rather than left at ratio 1.00 in "
            "a table cell:"
        )
        lines.append("")
        for c in noops:
            lines.append(
                f"- **{c.series_id}** ({c.method}, n={c.n_obs}): lag-1 autocorrelation "
                f"{c.acf1_reported:+.3f}. Both operators key on POSITIVE "
                "autocorrelation — Geltner clips phi to [0, 0.95], so a non-positive "
                "ACF gives phi=0, a=1 and truth=obs exactly. Nothing was recovered "
                "because nothing of the shape they look for is present."
            )
    else:
        lines.append("None: every series' de-smoother moved its volatility.")

    lines += ["", "## How to read a comparator ratio", ""]
    have = [c for c in checks if c.comparator_ratio is not None]
    if have:
        for c in have:
            lines.append(
                f"- **{c.series_id}** vs `{c.comparator}`: {c.comparator_ratio:.2f}x on "
                f"{c.n_overlap} shared periods. A listed vehicle levered ~1x has roughly "
                "twice the volatility of its unlevered assets before any smoothing "
                "question arises, so a ratio near 2-3x is largely STRUCTURAL. Treat a "
                "ratio far above that, alongside a sigma ratio near 1.00, as the signal "
                "worth investigating."
            )
    else:
        lines.append("No market-priced comparator is registered for any checked series.")
    return "\n".join(lines) + "\n"
