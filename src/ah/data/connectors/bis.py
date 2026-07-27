"""BIS credit-to-GDP gap connector (BIS Data Portal bulk CSV).

Fetches the ``WS_CREDIT_GAP`` flat CSV (zipped) from the BIS Data Portal and selects
the US credit-to-GDP **gap** (borrowers = US, data type = gaps, private non-financial
sector, all lenders, quarterly), returning a long ``(date, value)`` frame. Pre-1961
history is extended from JST ``tloans/gdp`` in ``derive.py``.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from ah.data.connectors.base import ConnectorError, RawArtifact, fetch_with_retry, open_url
from ah.data.manifest import Requirement


class BisConnector:
    source = "bis"

    def fetch(self, req: Requirement) -> RawArtifact:  # pragma: no cover - network
        url = "https://data.bis.org/static/bulk/WS_CREDIT_GAP_csv_flat.zip"
        content = fetch_with_retry(lambda: open_url(url))
        return RawArtifact(self.source, req.series_id, content, url)

    def parse(self, raw: RawArtifact, req: Requirement) -> pd.DataFrame:
        if raw.content[:2] == b"PK":  # a zip
            with zipfile.ZipFile(io.BytesIO(raw.content)) as zf:
                name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
                data = zf.read(name)
        else:
            data = raw.content
        frame = pd.read_csv(io.BytesIO(data))
        # BIS Data Portal columns are "CODE:Label"; keep the code prefix.
        frame.columns = [str(c).split(":", 1)[0] for c in frame.columns]

        if "BORROWERS_CTY" in frame.columns and "CG_DTYPE" in frame.columns:
            mask = frame["BORROWERS_CTY"].astype(str).str.startswith("US") & frame[
                "CG_DTYPE"
            ].astype(str).str.startswith("C")  # C = Credit-to-GDP gaps (actual-trend)
            sub = frame[mask]
            if sub.empty:
                raise ConnectorError("BIS: no US credit-to-GDP gap rows found")
            periods = [str(p).replace("-Q", "Q") for p in sub["TIME_PERIOD"]]
            dates = [pd.Period(p, freq="Q").to_timestamp() for p in periods]
            values = pd.to_numeric(sub["OBS_VALUE"], errors="coerce")
            out = pd.DataFrame({"date": dates, "value": values.to_numpy()})
        else:  # legacy/simple long CSV (date,value)
            cols = {c.lower(): c for c in frame.columns}
            if "date" not in cols or "value" not in cols:
                raise ConnectorError(f"BIS CSV unrecognized columns: {list(frame.columns)}")
            out = pd.DataFrame(
                {
                    "date": pd.to_datetime(frame[cols["date"]]).to_numpy(),
                    "value": pd.to_numeric(frame[cols["value"]], errors="coerce").to_numpy(),
                }
            )
        return out.dropna(subset=["value"]).sort_values(by="date", ignore_index=True)
