"""US Treasury HQM corporate spot-rate curve connector (xlsx).

The workbook is a maturity x month grid. The full curve is retained in the raw
artifact; ``parse`` returns the representative 10-year HQM spot rate as the
catalogued ``(date, value)`` series (the derive layer reconstructs the full curve
from raw when it needs other maturities).
"""

from __future__ import annotations

import io

import pandas as pd

from ah.data.connectors.base import ConnectorError, RawArtifact, fetch_with_retry, open_url
from ah.data.manifest import Requirement

_MATURITY = "10.0"


class TreasuryHqmConnector:
    source = "treasury_hqm"

    def fetch(self, req: Requirement) -> RawArtifact:  # pragma: no cover - network
        url = "https://home.treasury.gov/system/files/226/hqm_84_present.xls"
        content = fetch_with_retry(lambda: open_url(url))
        return RawArtifact(self.source, req.series_id, content, url)

    def parse(self, raw: RawArtifact, req: Requirement) -> pd.DataFrame:
        book = pd.read_excel(io.BytesIO(raw.content), sheet_name=0, header=None)
        header_idx = None
        header: list[str] = []
        for i in range(min(20, len(book))):
            row = [str(x).strip() for x in book.iloc[i].tolist()]
            if "Date" in row and _MATURITY in row:
                header_idx, header = i, row
                break
        if header_idx is None:
            raise ConnectorError(f"HQM header (Date, {_MATURITY}) not found")

        data = book.iloc[header_idx + 1 :].reset_index(drop=True)
        data.columns = pd.Index(header + [f"_c{j}" for j in range(len(data.columns) - len(header))])
        dates = pd.to_datetime(data["Date"], errors="coerce")
        values = pd.to_numeric(data[_MATURITY], errors="coerce")
        out = pd.DataFrame({"date": dates.to_numpy(), "value": values.to_numpy()})
        out = out.dropna(subset=["date", "value"])
        out["date"] = out["date"].dt.to_period("M").dt.to_timestamp()
        return out.sort_values(by="date", ignore_index=True)
