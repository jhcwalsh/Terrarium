"""FRED connector (REST, batched, API key). Parses the observations JSON."""

from __future__ import annotations

import json

import pandas as pd

from ah.data.connectors.base import (
    RawArtifact,
    aggregate_daily_to_monthly,
    fetch_with_retry,
    normalize_monthly,
    open_url,
)
from ah.data.manifest import Requirement


class FredConnector:
    source = "fred"

    def fetch(self, req: Requirement) -> RawArtifact:  # pragma: no cover - network
        import os

        key = os.environ["FRED_API_KEY"]
        url = (
            "https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={req.code}&api_key={key}&file_type=json"
        )
        content = fetch_with_retry(lambda: open_url(url, timeout=30))
        return RawArtifact(self.source, req.series_id, content, url)

    def parse(self, raw: RawArtifact, req: Requirement) -> pd.DataFrame:
        obj = json.loads(raw.content.decode("utf-8"))
        rows = obj["observations"]
        dates = [r["date"] for r in rows]
        values = [None if r["value"] in (".", "") else float(r["value"]) for r in rows]
        df = pd.DataFrame({"date": pd.to_datetime(dates), "value": values})
        if req.frequency.startswith("D"):
            return aggregate_daily_to_monthly(df, req.series_id)
        return normalize_monthly(df)
