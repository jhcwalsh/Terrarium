"""Robert Shiller ie_data.xls connector.

The workbook has merged headers and footnote rows, so we locate the header row by
content (a row containing ``Date`` and ``P``) rather than by position, then map the
requested series to a column. The ``Date`` column is a fractional year (1871.01 =
Jan 1871). Column drift is guarded by asserting the target column is present.
"""

from __future__ import annotations

import io

import pandas as pd

from ah.data.connectors.base import ConnectorError, RawArtifact, fetch_with_retry, open_url
from ah.data.manifest import Requirement

_COLMAP = {"price": "P", "dividend": "D", "earnings": "E", "cape": "CAPE"}


class ShillerConnector:
    source = "shiller"

    def fetch(self, req: Requirement) -> RawArtifact:  # pragma: no cover - network
        url = (
            "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53"
            "/downloads/ie_data.xls"
        )
        content = fetch_with_retry(lambda: open_url(url))
        return RawArtifact(self.source, req.series_id, content, url)

    def parse(self, raw: RawArtifact, req: Requirement) -> pd.DataFrame:
        # The workbook has a Disclaimer sheet then a Data sheet; find the sheet whose
        # first ~20 rows contain the (Date, P) header (robust to sheet reordering).
        xls = pd.ExcelFile(io.BytesIO(raw.content))
        book = None
        header_idx = None
        header: list[str] = []
        for sheet in xls.sheet_names:
            candidate = xls.parse(sheet, header=None)
            for i in range(min(20, len(candidate))):
                row = [str(x).strip() for x in candidate.iloc[i].tolist()]
                if "Date" in row and "P" in row:
                    book, header_idx, header = candidate, i, row
                    break
            if header_idx is not None:
                break
        if book is None or header_idx is None:
            raise ConnectorError("Shiller header row (Date, P) not found in any sheet")

        key = req.series_id.split(".", 1)[1]
        target = _COLMAP[key]
        if target not in header:
            raise ConnectorError(f"Shiller column {target} missing (drift?): {header}")

        data = book.iloc[header_idx + 1 :].reset_index(drop=True)
        data.columns = pd.Index(header + [f"_c{j}" for j in range(len(data.columns) - len(header))])
        date_frac = pd.to_numeric(data["Date"], errors="coerce")
        values = pd.to_numeric(data[target], errors="coerce")
        frame = pd.DataFrame({"frac": date_frac, "value": values}).dropna(subset=["frac"])

        years = frame["frac"].astype(int)
        months = (frame["frac"].sub(years).mul(100).round().astype(int)).clip(1, 12)
        dates = pd.to_datetime({"year": years, "month": months, "day": [1] * len(frame)})
        out = pd.DataFrame({"date": dates.to_numpy(), "value": frame["value"].to_numpy()})
        return out.dropna(subset=["value"]).sort_values(by="date", ignore_index=True)
