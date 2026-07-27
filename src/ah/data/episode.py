"""Episode packs (STEP1-DATA-PLAN §WP1.8).

Dataset builders for the stress episodes that Gate G1's reproduction test consumes:
2008-10 (GFC), 2020 (COVID), 2022-23 (rates shock). Each pack resolves its inputs
**through the catalog** (no ad-hoc file reads), slices them to the episode window,
adds reported-vs-de-smoothed private-markets sleeves, attaches the cited
secondary-pricing table (docs/data/secondaries.md), and renders a markdown brief.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ah.data.catalog import Catalog, CatalogError
from ah.data.desmooth import desmooth_series

_EPISODES: dict[int, tuple[str, str, str]] = {
    2008: ("2008-07-01", "2010-12-31", "Global Financial Crisis"),
    2020: ("2020-01-01", "2020-12-31", "COVID shock"),
    2022: ("2022-01-01", "2023-12-31", "Rates shock"),
}

# Semi-annual secondary pricing (% of NAV), hand-entered with citations in
# docs/data/secondaries.md. These are episode anchors, not proprietary data.
_SECONDARY_PRICING: dict[int, list[tuple[str, float]]] = {
    2008: [("2008-H2", 0.70), ("2009-H1", 0.60), ("2009-H2", 0.75)],
    2020: [("2020-H1", 0.85), ("2020-H2", 0.90)],
    2022: [("2022-H1", 0.87), ("2022-H2", 0.81)],
}


@dataclass
class EpisodePack:
    year: int
    title: str
    start: str
    end: str
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    secondary_pricing: pd.DataFrame | None = None
    brief: str = ""


def episode_years() -> list[int]:
    return sorted(_EPISODES)


def secondary_pricing(year: int) -> pd.DataFrame:
    rows = _SECONDARY_PRICING.get(year, [])
    return pd.DataFrame(rows, columns=["period", "pct_of_nav"])


def _read_current(catalog: Catalog, series_id: str) -> pd.DataFrame | None:
    vintage = catalog.current_vintage()
    if vintage is None:
        return None
    try:
        return catalog.read_observations(vintage, series_id)
    except CatalogError:
        return None


def _slice(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    d = frame.assign(date=pd.to_datetime(frame["date"]))
    mask = (d["date"] >= pd.Timestamp(start)) & (d["date"] <= pd.Timestamp(end))
    return d[mask].reset_index(drop=True)


def build_episode(catalog: Catalog, year: int, series_ids: list[str]) -> EpisodePack:
    """Build the pack for ``year`` from series resolved through the catalog."""
    if year not in _EPISODES:
        raise KeyError(f"no episode for {year}; known: {episode_years()}")
    start, end, title = _EPISODES[year]
    pack = EpisodePack(year=year, title=title, start=start, end=end)

    for sid in series_ids:
        frame = _read_current(catalog, sid)
        if frame is None:
            continue
        sliced = _slice(frame, start, end)
        if sliced.empty:
            continue
        pack.frames[sid] = sliced
        # private-markets sleeves get a de-smoothed companion
        if sid.startswith("albourne.pm_") and len(sliced) >= 8:
            result = desmooth_series(sid, sliced, method="glm_ma")
            pack.frames[f"{sid}__desmoothed"] = pd.DataFrame(
                {"date": sliced["date"].to_numpy(), "value": result.truth}
            )

    pack.secondary_pricing = secondary_pricing(year)
    pack.brief = _brief(pack)
    return pack


def _brief(pack: EpisodePack) -> str:
    lines = [
        f"# Episode brief - {pack.year}: {pack.title}",
        "",
        f"- window: {pack.start} -> {pack.end}",
        f"- series in pack: {len(pack.frames)}",
        "",
        "## Series",
    ]
    for sid, frame in sorted(pack.frames.items()):
        lines.append(f"- `{sid}` — {len(frame)} obs")
    lines += [
        "",
        "## Secondary-market pricing (% of NAV)",
        "",
        "| period | % of NAV |",
        "| --- | --- |",
    ]
    if pack.secondary_pricing is not None:
        for _, row in pack.secondary_pricing.iterrows():
            lines.append(f"| {row['period']} | {row['pct_of_nav']:.2f} |")
    lines += ["", "> Secondary pricing hand-entered with citations in docs/data/secondaries.md."]
    return "\n".join(lines) + "\n"
