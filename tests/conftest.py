"""Shared test helpers (no fixtures with side effects live here).

``make_synthetic_source_16`` is the 16-factor synthetic ``BootstrapSource``
used by the adapter and console suites: per-factor realistic scales,
deterministic in the row index, no catalog, no network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import ah.gen.bootstrap as bs


def make_synthetic_source_16(n_rows: int = 72) -> bs.BootstrapSource:
    i = np.arange(n_rows, dtype=np.float64)
    cols = {
        "cape_v": 0.2 + 0.01 * np.sin(i / 5.0),
        "commodities": 0.02 * np.sin(i / 3.0),
        "cpi": 100.0 * (1.003**i),
        "equity_mkt": 0.015 * np.sin(i / 4.0) + 0.005,
        "equity_vol": 18.0 + 3.0 * np.sin(i / 6.0),
        "funding_spread": 0.7 + 0.1 * np.sin(i / 7.0),
        "fx_usd": 120.0 + 5.0 * np.sin(i / 9.0),
        "hml": 0.004 * np.sin(i / 5.5),
        "hqm_curve": 6.5 + 0.5 * np.sin(i / 8.0),
        "hy_spread": 4.0 + 1.0 * np.sin(i / 6.5),
        "ig_spread": 1.0 + 0.3 * np.sin(i / 6.0),
        "mom": 0.006 * np.sin(i / 4.5),
        "policy_rate": 5.0 + 1.0 * np.sin(i / 10.0),
        "smb": 0.003 * np.sin(i / 3.5),
        "ust_10y": 6.0 + 0.8 * np.sin(i / 11.0),
        "ust_2y": 5.5 + 0.9 * np.sin(i / 10.5),
    }
    names = tuple(sorted(cols))  # bootstrap panels are alphabetical
    values = np.column_stack([cols[n] for n in names])
    cycle = ("EXP", "EXP", "STAG", "STAG", "REC", "CRI", "REF", "SLOW")
    labels = tuple(cycle[k % len(cycle)] for k in range(n_rows))
    dates = pd.DatetimeIndex(pd.date_range("1970-01-01", periods=n_rows, freq="MS"))
    return bs.BootstrapSource(
        factor_names=names,
        dates=dates,
        values=values,
        labels=labels,
        ruleset_version="regime_ruleset_v1",
        vintage_id="test-vintage",
        active_blocks=("global", "us"),
    )
