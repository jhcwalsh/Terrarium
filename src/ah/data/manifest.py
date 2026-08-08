"""Load ``requirements.yaml`` into a typed :class:`Requirements` (STEP1-DATA-PLAN §WP1.1).

The manifest is the single source of truth for what series the platform requires.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

LicenseTier = Literal["FREE", "REG", "COMM"]
Priority = Literal["P0", "P1", "P2"]
Intake = Literal["auto", "manual"]


def _repo_root() -> Path:
    # src/ah/data/manifest.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def requirements_path() -> Path:
    return _repo_root() / "requirements.yaml"


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)  # frozen -> hashable

    series_id: str
    source: str
    code: str | None = None
    frequency: str
    units: str
    min_start: str | None = None
    sla_days: int
    license_tier: LicenseTier
    priority: Priority
    intake: Intake = "auto"
    enforce: bool = True
    notes: str | None = None
    #: Optional per-entry override for the human-facing source page; when
    #: absent, :func:`source_link` resolves through SOURCE_URL_TEMPLATES.
    source_url: str | None = None

    @property
    def redistributable(self) -> bool:
        """Only FREE data may be redistributed (licensing discipline, §1)."""
        return self.license_tier == "FREE"


class Requirements:
    """A queryable collection of requirements keyed by ``series_id``."""

    def __init__(self, entries: dict[str, Requirement]) -> None:
        self._entries = entries

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries.values())

    def __contains__(self, series_id: str) -> bool:
        return series_id in self._entries

    def __getitem__(self, series_id: str) -> Requirement:
        return self._entries[series_id]

    def get(self, series_id: str) -> Requirement | None:
        return self._entries.get(series_id)

    @property
    def series_ids(self) -> list[str]:
        return list(self._entries)

    def by_source(self, source: str) -> list[Requirement]:
        return [r for r in self if r.source == source]

    def by_intake(self, intake: Intake) -> list[Requirement]:
        return [r for r in self if r.intake == intake]

    def sources(self) -> set[str]:
        return {r.source for r in self}


#: Human-facing landing page per source. DELIBERATELY not the connectors'
#: fetch endpoints: FRED's fetch URL carries the API key as a query parameter
#: and must never be rendered; bulk-zip/blob endpoints are backend details.
#: ``{code}`` interpolates the entry's upstream code where a per-series page
#: exists.
SOURCE_URL_TEMPLATES: dict[str, str] = {
    "fred": "https://fred.stlouisfed.org/series/{code}",
    "french": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
    "shiller": "http://www.econ.yale.edu/~shiller/data.htm",
    "bis": "https://data.bis.org/topics/CREDIT_GAPS",
    "jst": "https://www.macrohistory.net/database/",
    "albourne": "https://village.albourne.com",
    "cliffwater": "https://www.cliffwater.com",
    "nareit": "https://www.reit.com/data-research",
    "ncreif": "https://www.ncreif.org",
    "treasury": "https://fred.stlouisfed.org/series/{code}",  # HQM served via FRED
}


def source_link(req: Requirement) -> str | None:
    """The human-facing source page for a registered series, or None.

    Per-entry ``source_url`` wins; otherwise the source template resolves,
    interpolating ``{code}`` where the template has one (entries without an
    upstream code fall back to the template minus interpolation only when the
    template needs none).
    """
    if req.source_url:
        return req.source_url
    template = SOURCE_URL_TEMPLATES.get(req.source)
    if template is None:
        return None
    if "{code}" in template:
        return template.format(code=req.code) if req.code else None
    return template


def _normalize_date(value: object) -> str | None:
    """YAML parses bare YYYY-MM-DD as a date; keep min_start as a 'YYYY-MM' string."""
    if value is None:
        return None
    text = str(value)
    return text[:7] if len(text) >= 7 else text


def load_requirements(path: str | Path | None = None) -> Requirements:
    """Load and validate the requirements manifest."""
    p = Path(path) if path is not None else requirements_path()
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw = doc.get("series", {})
    entries: dict[str, Requirement] = {}
    for series_id, fields in raw.items():
        data = dict(fields)
        data["series_id"] = series_id
        data["min_start"] = _normalize_date(data.get("min_start"))
        entries[series_id] = Requirement.model_validate(data)
    return Requirements(entries)


@lru_cache(maxsize=1)
def requirements() -> Requirements:
    """Cached default manifest."""
    return load_requirements()
