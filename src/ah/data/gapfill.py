"""Declared interior-gap interpolation, applied at refresh time (WP primars-intake-01).

The October-2025 US government shutdown cancelled the BLS releases, leaving a
one-month hole in four federal series that is genuinely absent UPSTREAM — the
vendor will never publish it. Owner decision 2026-08-08: interpolate the
missing month linearly between its neighbors (2025-09 and 2025-11).

Discipline, same as ``ah.data.splice``: a synthetic observation is never
silent. Fills happen only for gaps DECLARED here (series id + month), the
filled row carries ``is_proxy=True`` in the stored frame (the data console
shades it), and a fill only applies when BOTH neighbors exist — a declared
gap at the edge of a series stays a gap. Vintages remain immutable: fills
land in the NEXT vintage written, never retroactively.
"""

from __future__ import annotations

import pandas as pd

#: (series_id -> months "YYYY-MM") with a reason each. Adding an entry here is
#: a reviewed change, not a runtime behavior.
GAP_FILL_RULES: dict[str, dict[str, str]] = {
    "fred.CPI": {"2025-10": "BLS release cancelled (2025 US government shutdown)"},
    "fred.CPI_CORE": {"2025-10": "BLS release cancelled (2025 US government shutdown)"},
    "fred.UNRATE": {"2025-10": "BLS release cancelled (2025 US government shutdown)"},
    "fred.SAHMREALTIME": {"2025-10": "BLS release cancelled (2025 US government shutdown)"},
}


def fill_declared_gaps(series_id: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Fill this series' declared gaps by linear interpolation of the adjacent
    months. Returns ``(frame, notes)`` — the frame gains an ``is_proxy`` column
    only when a fill actually happened; untouched frames pass through as-is.
    """
    rules = GAP_FILL_RULES.get(series_id)
    if not rules or frame.empty:
        return frame, []

    dates = pd.DatetimeIndex(pd.to_datetime(frame["date"]))
    by_month = {str(d)[:7]: i for i, d in enumerate(dates)}
    notes: list[str] = []
    additions: list[dict[str, object]] = []
    for month, reason in rules.items():
        if month in by_month:
            continue  # the vendor published after all; nothing to invent
        ts = pd.Timestamp(month + "-01")
        prev_m = str(ts - pd.offsets.MonthBegin(1))[:7]
        next_m = str(ts + pd.offsets.MonthBegin(1))[:7]
        if prev_m not in by_month or next_m not in by_month:
            notes.append(f"{series_id} {month}: declared gap NOT filled (missing neighbor)")
            continue
        lo = float(frame["value"].iloc[by_month[prev_m]])
        hi = float(frame["value"].iloc[by_month[next_m]])
        value = (lo + hi) / 2.0
        additions.append({"date": ts, "value": value, "is_proxy": True})
        notes.append(
            f"{series_id} {month}: filled {value:.4f} = midpoint({prev_m}={lo:.4f}, "
            f"{next_m}={hi:.4f}) - {reason}"  # ASCII: this string reaches the console
        )
    if not additions:
        return frame, notes

    out = frame.copy()
    out["is_proxy"] = False
    add = pd.DataFrame(additions)
    for col in out.columns:
        if col not in add.columns:
            add[col] = out[col].iloc[0] if col in ("series_id", "vintage") else pd.NA
    out = pd.concat([out, add[out.columns.tolist()]], ignore_index=True).sort_values(
        by="date", ignore_index=True
    )
    return out, notes
