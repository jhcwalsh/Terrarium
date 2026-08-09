"""Connector protocol, raw-artifact type, and shared aggregation rules.

D->M aggregation rule (fixed, STEP1-DATA-PLAN §WP1.2): **monthly mean** for rates
and spreads, **month-end (last)** for VIX. Both are period-end dated (first of
month is used as the period label consistently across the platform).
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from ah.data.manifest import Requirement


class ConnectorError(RuntimeError):
    pass


@dataclass
class RawArtifact:
    source: str
    series_id: str
    content: bytes
    url: str = ""
    fetched_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@runtime_checkable
class Connector(Protocol):
    source: str

    def fetch(self, req: Requirement) -> RawArtifact: ...

    def parse(self, raw: RawArtifact, req: Requirement) -> pd.DataFrame: ...


# --------------------------------------------------------------------------- #
# aggregation
# --------------------------------------------------------------------------- #


def to_month_start(dates: pd.Series) -> pd.Series:
    """Normalize any date to the first day of its month (the period label)."""
    dt = pd.to_datetime(dates)
    return dt.dt.to_period("M").dt.to_timestamp()


def normalize_monthly(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop missing values and label each observation at month start."""
    df = frame.dropna(subset=["value"]).copy()
    df["date"] = to_month_start(df["date"])
    return df.sort_values(by="date", ignore_index=True)


def to_monthly_mean(frame: pd.DataFrame) -> pd.DataFrame:
    """Daily -> monthly by mean; period-labelled at month start."""
    df = frame.dropna(subset=["value"]).copy()
    df["date"] = to_month_start(df["date"])
    out = df.groupby("date", as_index=False)["value"].mean()
    return out.sort_values(by="date", ignore_index=True)


def to_monthly_last(frame: pd.DataFrame) -> pd.DataFrame:
    """Daily -> monthly by last observation (month-end value); month-start label."""
    df = frame.dropna(subset=["value"]).copy()
    df = df.sort_values(by="date")
    df["date"] = to_month_start(df["date"])
    out = df.groupby("date", as_index=False)["value"].last()
    return out.sort_values(by="date", ignore_index=True)


def aggregate_daily_to_monthly(frame: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """Apply the fixed D->M rule: month-end for the implied-vol indices (VIX and
    its VXO splice donor -- both must aggregate the same way or the overlap fit
    compares a month-end print to a monthly average), monthly mean otherwise."""
    lowered = series_id.lower()
    if "vix" in lowered or "vxo" in lowered:
        return to_monthly_last(frame)
    return to_monthly_mean(frame)


# --------------------------------------------------------------------------- #
# network helper (never exercised in tests)
# --------------------------------------------------------------------------- #


_USER_AGENT = "Mozilla/5.0 (compatible; AlternateHistories/0.2 data connector)"


def open_url(url: str, *, timeout: int = 60) -> bytes:  # pragma: no cover - network path
    """GET ``url`` with a browser-like User-Agent (some hosts 403 the default UA)."""
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read()


def fetch_with_retry(
    thunk: Callable[[], bytes], *, max_attempts: int = 5, base_delay: float = 0.5
) -> bytes:  # pragma: no cover - network path
    """Call ``thunk`` with exponential backoff (politeness + resilience, §1)."""
    last: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return thunk()
        except Exception as exc:
            last = exc
            time.sleep(base_delay * (2**attempt))
    raise ConnectorError(f"fetch failed after {max_attempts} attempts: {last}")
