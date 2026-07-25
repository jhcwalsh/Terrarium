"""Jordà-Schularick-Taylor Macrohistory Database connector (.dta / Stata).

Keeps all countries in the raw artifact; ``parse`` filters to USA (start country)
and extracts one annual variable. Year is labelled at Jan 1.
"""

from __future__ import annotations

import io

import pandas as pd

from ah.data.connectors.base import ConnectorError, RawArtifact, fetch_with_retry, open_url
from ah.data.manifest import Requirement

_COUNTRY = "USA"


class JstConnector:
    source = "jst"

    def fetch(self, req: Requirement) -> RawArtifact:  # pragma: no cover - network
        url = "https://www.macrohistory.net/app/download/9834512469/JSTdatasetR6.dta"
        content = fetch_with_retry(lambda: open_url(url))
        return RawArtifact(self.source, req.series_id, content, url)

    def parse(self, raw: RawArtifact, req: Requirement) -> pd.DataFrame:
        frame = pd.read_stata(io.BytesIO(raw.content))
        country_col = "iso" if "iso" in frame.columns else "country"
        if country_col not in frame.columns or "year" not in frame.columns:
            raise ConnectorError("JST frame missing country/year columns")
        var = req.code
        if var not in frame.columns:
            raise ConnectorError(f"JST variable {var} not present: {list(frame.columns)}")

        usa = frame[frame[country_col] == _COUNTRY]
        dates = pd.to_datetime(usa["year"].astype(int).astype(str) + "-01-01")
        out = pd.DataFrame({"date": dates.to_numpy(), "value": pd.to_numeric(usa[var]).to_numpy()})
        return out.dropna(subset=["value"]).sort_values(by="date", ignore_index=True)
