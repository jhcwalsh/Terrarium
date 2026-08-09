"""Ken French data-library connector (zip/CSV).

Parses a research-factors CSV: a header preamble, a dated block (``YYYYMM``
rows monthly, ``YYYYMMDD`` in the daily file), then a trailing annual block
in the monthly file. We read the first dated block only (guarding the
annual-block quirk by matching the digit count and stopping at the first
non-matching row). Values are in percent; a single factor column is returned
per requirement (``req.code``). A requirement with ``frequency: "D"`` selects
the daily research-factors file and keeps daily rows -- no monthly
aggregation, because its only consumer (the equity_vol backcast,
WP-DATA-VOLEXT stage 2) needs the daily returns themselves.
"""

from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from ah.data.connectors.base import (
    ConnectorError,
    RawArtifact,
    fetch_with_retry,
    open_url,
    to_month_start,
)
from ah.data.manifest import Requirement

_MONTH_ROW = re.compile(r"^\s*(\d{6})\s*,")
_DAY_ROW = re.compile(r"^\s*(\d{8})\s*,")


class FrenchConnector:
    source = "french"

    def fetch(self, req: Requirement) -> RawArtifact:  # pragma: no cover - network
        base = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
        if req.frequency == "D":
            name = "F-F_Research_Data_Factors_daily_CSV.zip"
        elif req.code == "Mom":
            name = "F-F_Momentum_Factor_CSV.zip"
        else:
            name = "F-F_Research_Data_Factors_CSV.zip"
        url = f"{base}/{name}"
        content = fetch_with_retry(lambda: open_url(url))
        return RawArtifact(self.source, req.series_id, content, url)

    def _text(self, raw: RawArtifact) -> str:
        if raw.content[:2] == b"PK":  # a zip
            with zipfile.ZipFile(io.BytesIO(raw.content)) as zf:
                name = next(n for n in zf.namelist() if n.upper().endswith(".CSV"))
                return zf.read(name).decode("latin-1")
        return raw.content.decode("latin-1")

    def parse(self, raw: RawArtifact, req: Requirement) -> pd.DataFrame:
        text = self._text(raw)
        lines = text.splitlines()
        daily = req.frequency == "D"
        row_re = _DAY_ROW if daily else _MONTH_ROW

        header: list[str] | None = None
        records: list[tuple[str, list[str]]] = []
        for line in lines:
            if header is None:
                # the column header is the row just before the first dated row
                if row_re.match(line):
                    pass  # header stays None only if we never saw column names
                cols = [c.strip() for c in line.split(",")]
                if cols and cols[0] == "" and len(cols) > 1 and any(cols[1:]):
                    header = cols
                continue
            m = row_re.match(line)
            if not m:
                if records:  # reached the annual block / trailer -> stop
                    break
                continue
            records.append((m.group(1), [c.strip() for c in line.split(",")[1:]]))

        if header is None or not records:
            raise ConnectorError("could not locate the dated factor block")
        if req.code not in header:
            raise ConnectorError(f"factor {req.code} not in header {header}")
        col = header.index(req.code) - 1  # header[0] is the empty date column

        if daily:
            dates = [pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}") for d, _ in records]
        else:
            dates = [pd.Timestamp(f"{ym[:4]}-{ym[4:]}-01") for ym, _ in records]
        # Ken French factors are in PERCENT; the platform stores returns as decimals.
        values = [float(fields[col]) / 100.0 for _, fields in records]
        df = pd.DataFrame({"date": dates, "value": values})
        if not daily:
            df["date"] = to_month_start(df["date"])
        return df.sort_values(by="date", ignore_index=True)
