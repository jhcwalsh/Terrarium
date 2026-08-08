"""Cliffwater BDC Index monthly total returns.

DISTINCT FROM ``cliffwater_cdli``, and the difference is the point. CDLI is the
Cliffwater Direct Lending Index: quarterly, asset-level, appraisal-marked. This
is the Cliffwater BDC Index: monthly, built from LISTED business-development-
company prices, so it is marked to market every day the exchange is open.

That makes it the de-smoothing VALIDATION ANCHOR for private credit rather
than another smoothed series to correct. Measured on the 2004-09..2026-07
delivery: annualized volatility 21.6%, March 2020 at -35.5%, skew -1.38,
excess kurtosis 8.0, and lag-1 autocorrelation of just +0.087 -- where an
appraisal-based private index shows 0.4-0.8. Read it as an UPPER bound on the
de-smoothed asset-level series, never as a target: BDCs are levered and
listed, so it carries both leverage and listing effects the private index
does not.
"""

from __future__ import annotations

from ah.data.schemas.base import ColumnSpec, IntakeSchema

SCHEMA = IntakeSchema(
    name="cliffwater_bdc",
    source="cliffwater",
    columns=[
        ColumnSpec("period", dtype="period"),
        # bounds admit the -35.5% COVID month with headroom, not nonsense
        ColumnSpec("ret", dtype="float", min=-0.5, max=0.5),
    ],
    period_col="period",
    frequency="M",
    notes=(
        "listed-BDC total return, market-priced; the de-smoothing anchor for "
        "private credit. Drop carries fractions; the vendor file's return "
        "columns are percent and its dividend_yield_pct column is a FRACTION "
        "despite the name -- scripts/ingest_cwbdc.py does the conversion."
    ),
)
