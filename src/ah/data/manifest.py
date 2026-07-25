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
