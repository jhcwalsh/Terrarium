"""AQR Commodities-for-the-Long-Run workbook parser (manual intake, REG licence).

NOT a refresh connector: there is no ``fetch`` and never will be -- the
workbook is owner-supplied (Levine, Ooi, Richardson (c)2018; the AQR data
library set behind the 2018 FAJ paper), lives in gitignored ``data/aqr/``,
and is never committed or redistributed (owner ruling C2, WP-DATA-CMDTY;
``docs/superpowers/specs/2026-08-09-cmdty-scoping.md``). Attribution rides
in every derived artifact.

The sheet layout is a preamble of notes, a header row whose first cell is
blank and whose named columns carry the portfolio returns, then monthly data
rows (dates in column 0, decimal returns). The header row is located by
content, Shiller-style, so AQR reordering their preamble does not silently
shift columns; the registered columns are matched by header PREFIX and each
must match exactly one column.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from ah.data.connectors.base import ConnectorError, to_month_start

WORKBOOK_NAME = "Commodities for the Long Run Index Level Data Monthly.xlsx"

#: Registered code -> the unambiguous header prefix it matches.
COLUMN_PREFIXES: dict[str, str] = {
    "ew_excess": "Excess return of equal-weight",
    "ew_spot": "Spot return of equal-weight",
}


def parse_workbook(source: Path | bytes) -> dict[str, pd.DataFrame]:
    """Parse the workbook into one ``(date, value)`` frame per registered code.

    ``source`` is the workbook path (normal use: ``data/aqr/``) or raw bytes
    (tests). Values are decimal monthly returns; dates are normalized to
    month start like every other monthly series in the store.
    """
    buf: Path | io.BytesIO = source if isinstance(source, Path) else io.BytesIO(source)
    xls = pd.ExcelFile(buf)
    sheet = xls.sheet_names[0]
    raw = xls.parse(sheet, header=None)

    header_idx: int | None = None
    for i in range(min(len(raw), 30)):
        cells = [str(c) for c in raw.iloc[i].tolist()]
        if any(c.startswith(COLUMN_PREFIXES["ew_excess"]) for c in cells):
            header_idx = i
            break
    if header_idx is None:
        raise ConnectorError("could not locate the CFTLR header row by content")
    header = [str(c) for c in raw.iloc[header_idx].tolist()]

    out: dict[str, pd.DataFrame] = {}
    for code, prefix in COLUMN_PREFIXES.items():
        matches = [j for j, c in enumerate(header) if c.startswith(prefix)]
        if len(matches) != 1:
            raise ConnectorError(
                f"column prefix {prefix!r} matched {len(matches)} headers -- "
                "the workbook layout changed; refusing to guess"
            )
        col = matches[0]
        body = raw.iloc[header_idx + 1 :, [0, col]].copy()
        body.columns = ["date", "value"]
        body["date"] = pd.to_datetime(body["date"], errors="coerce")
        body["value"] = pd.to_numeric(body["value"], errors="coerce")
        body = body.dropna(subset=["date", "value"]).reset_index(drop=True)
        if body.empty:
            raise ConnectorError(f"no data rows parsed for {code}")
        body["date"] = to_month_start(body["date"])
        out[code] = body.sort_values(by="date", ignore_index=True)
    return out
