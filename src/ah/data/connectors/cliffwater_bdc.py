"""Cliffwater BDC Index: vendor file -> intake drop (pure, offline).

The parse half of the delivery, kept in the package rather than in the script
so it is importable and testable — same split as
``ah.data.connectors.albourne_primars``. ``scripts/ingest_cwbdc.py`` is the
thin driver. There is no ``fetch``: the vendor delivers a file, there is no
API.

UNITS, because the vendor file mixes them and the column names do not say so:

* ``total_return_pct`` / ``price_return_pct`` / ``income_return_pct`` are
  PERCENT (a -0.066 row is -0.066%, and the index columns rebuild from them).
* ``dividend_yield_pct`` is a FRACTION despite the ``_pct`` suffix — it
  averages 0.101 across the delivery, i.e. 10.1%, right for listed BDCs and
  absurd read as a percent.

Only the total return is converted and ingested. The price/income
decomposition and the yield stay in the vendor file: registering them would be
three more series with no consumer, and the WP1.9 rule asks for series a
workstream actually needs.
"""

from __future__ import annotations

import pandas as pd

from ah.data.connectors.base import ConnectorError

SERIES_ID = "cliffwater.bdc_ret_m"


def to_drop_frame(vendor: pd.DataFrame) -> pd.DataFrame:
    """Vendor rows -> ``(period, ret)``, percent converted to fraction.

    The vendor's first row is the index base (1000.0 with an empty return); it
    carries no observation and is dropped rather than coerced to zero.
    """
    missing = {"date", "total_return_pct"} - set(vendor.columns)
    if missing:
        raise ConnectorError(f"vendor file missing column(s): {sorted(missing)}")
    rows = vendor.dropna(subset=["total_return_pct"]).copy()
    if rows.empty:
        raise ConnectorError("vendor file carries no total-return observations")
    period = pd.PeriodIndex(pd.to_datetime(rows["date"]), freq="M")
    if period.duplicated().any():
        dupes = sorted({str(p) for p in period[period.duplicated()]})
        raise ConnectorError(f"vendor file has duplicate months: {dupes}")
    return pd.DataFrame(
        {"period": period.astype(str), "ret": rows["total_return_pct"].astype(float) / 100.0}
    ).sort_values(by="period", ignore_index=True)
