"""The sleeve taxonomy and the vendor-code boundary (WP2R.1, R1/R13).

``taxonomy/sleeves.yaml`` is the platform's own ``sleeve_id`` namespace;
``taxonomy/albourne_mapping.yaml`` maps vendor codes to it. This module is the
only reader of both: model code references sleeves by id and never sees a
vendor's classification (the spec's design principle — a taxonomy change is a
mapping-file change, not a refactor).

The intake boundary: :func:`unmapped_codes` is wired into
:func:`ah.data.intake.validate_file` for Albourne strategy-grouped schemas, so
an unmapped vendor code fails intake with a readable report instead of being
silently dropped or silently accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

__all__ = [
    "TAXONOMY_VERSION",
    "Sleeve",
    "Taxonomy",
    "TaxonomyError",
    "load_taxonomy",
    "sleeve_for_code",
    "unmapped_codes",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
SLEEVES_PATH = _REPO_ROOT / "taxonomy" / "sleeves.yaml"
MAPPING_PATH = _REPO_ROOT / "taxonomy" / "albourne_mapping.yaml"

TAXONOMY_VERSION = "taxonomy-v1.1"


class TaxonomyError(ValueError):
    """A taxonomy or mapping file that violates its own contract."""


@dataclass(frozen=True)
class Sleeve:
    sleeve_id: str
    group: str
    vehicle: str
    modeled_in_v1: bool
    definition: str
    aggregates: tuple[str, ...] = ()
    notes: str | None = None


@dataclass(frozen=True)
class Taxonomy:
    """The loaded, validated namespace + vendor mapping."""

    version: str
    sleeves: dict[str, Sleeve]
    series_to_sleeve: dict[str, str]
    non_sleeve_series: dict[str, str]
    code_to_sleeve: dict[str, str]  # union over vendor code families
    excluded_codes: dict[str, str]  # code -> reason

    def sleeve(self, sleeve_id: str) -> Sleeve:
        try:
            return self.sleeves[sleeve_id]
        except KeyError:
            raise TaxonomyError(
                f"unknown sleeve_id '{sleeve_id}'; known: {sorted(self.sleeves)}"
            ) from None

    @property
    def modeled_v1(self) -> tuple[str, ...]:
        return tuple(s.sleeve_id for s in self.sleeves.values() if s.modeled_in_v1)


def _load_sleeves(path: Path) -> tuple[str, dict[str, Sleeve]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    version = str(doc.get("version", ""))
    vehicle_types = set(doc.get("vehicle_types", ()))
    if not vehicle_types:
        raise TaxonomyError(f"{path}: vehicle_types missing or empty")
    sleeves: dict[str, Sleeve] = {}
    for entry in doc.get("sleeves", ()):
        sleeve = Sleeve(
            sleeve_id=str(entry["id"]),
            group=str(entry["group"]),
            vehicle=str(entry["vehicle"]),
            modeled_in_v1=bool(entry["modeled_in_v1"]),
            definition=str(entry["definition"]).strip(),
            aggregates=tuple(entry.get("aggregates", ())),
            notes=(str(entry["notes"]).strip() if entry.get("notes") else None),
        )
        if sleeve.sleeve_id in sleeves:
            raise TaxonomyError(f"{path}: duplicate sleeve_id '{sleeve.sleeve_id}'")
        if sleeve.vehicle not in vehicle_types:
            raise TaxonomyError(
                f"{path}: sleeve '{sleeve.sleeve_id}' has vehicle '{sleeve.vehicle}' "
                f"outside {sorted(vehicle_types)}"
            )
        if not sleeve.definition:
            raise TaxonomyError(f"{path}: sleeve '{sleeve.sleeve_id}' needs a definition")
        sleeves[sleeve.sleeve_id] = sleeve
    for sleeve in sleeves.values():
        for child in sleeve.aggregates:
            if child not in sleeves:
                raise TaxonomyError(
                    f"{path}: '{sleeve.sleeve_id}' aggregates unknown sleeve '{child}'"
                )
    return version, sleeves


def _load_mapping(
    path: Path, sleeves: dict[str, Sleeve]
) -> tuple[str, dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    version = str(doc.get("version", ""))

    series_to_sleeve: dict[str, str] = {}
    for series_id, sleeve_id in (doc.get("series") or {}).items():
        if sleeve_id not in sleeves:
            raise TaxonomyError(
                f"{path}: series '{series_id}' maps to unknown sleeve '{sleeve_id}'"
            )
        series_to_sleeve[str(series_id)] = str(sleeve_id)

    non_sleeve_series = {str(k): str(v) for k, v in (doc.get("non_sleeve_series") or {}).items()}
    overlap = set(series_to_sleeve) & set(non_sleeve_series)
    if overlap:
        raise TaxonomyError(f"{path}: series both mapped and non-sleeve: {sorted(overlap)}")

    code_to_sleeve: dict[str, str] = {}
    for family, codes in (doc.get("codes") or {}).items():
        for code, target in (codes or {}).items():
            sleeve_id = target["sleeve"] if isinstance(target, dict) else target
            if sleeve_id not in sleeves:
                raise TaxonomyError(
                    f"{path}: codes.{family}['{code}'] maps to unknown sleeve '{sleeve_id}'"
                )
            if code in code_to_sleeve and code_to_sleeve[code] != sleeve_id:
                raise TaxonomyError(
                    f"{path}: code '{code}' maps to two different sleeves across families"
                )
            code_to_sleeve[str(code)] = str(sleeve_id)

    excluded: dict[str, str] = {}
    for code, target in (doc.get("excluded_codes") or {}).items():
        reason = target["reason"] if isinstance(target, dict) else str(target)
        if not reason:
            raise TaxonomyError(f"{path}: excluded code '{code}' needs a reason")
        if code in code_to_sleeve:
            raise TaxonomyError(f"{path}: code '{code}' is both mapped and excluded")
        excluded[str(code)] = str(reason)

    return version, series_to_sleeve, non_sleeve_series, code_to_sleeve, excluded


@lru_cache(maxsize=1)
def load_taxonomy() -> Taxonomy:
    """Load + validate both files; raises :class:`TaxonomyError` on any breach."""
    sleeves_version, sleeves = _load_sleeves(SLEEVES_PATH)
    mapping_version, series, non_sleeve, codes, excluded = _load_mapping(MAPPING_PATH, sleeves)
    if sleeves_version != mapping_version:
        raise TaxonomyError(
            f"taxonomy version skew: sleeves.yaml={sleeves_version!r}, "
            f"albourne_mapping.yaml={mapping_version!r} — the two files version together"
        )
    if sleeves_version != TAXONOMY_VERSION:
        raise TaxonomyError(
            f"loaded taxonomy version {sleeves_version!r} != code's {TAXONOMY_VERSION!r}; "
            "bump ah.data.taxonomy.TAXONOMY_VERSION in the same change as the files"
        )
    return Taxonomy(
        version=sleeves_version,
        sleeves=sleeves,
        series_to_sleeve=series,
        non_sleeve_series=non_sleeve,
        code_to_sleeve=codes,
        excluded_codes=excluded,
    )


def sleeve_for_code(code: str) -> str:
    """Vendor code -> sleeve_id; raises with the full known vocabulary on a miss."""
    taxonomy = load_taxonomy()
    try:
        return taxonomy.code_to_sleeve[code]
    except KeyError:
        raise TaxonomyError(
            f"vendor code '{code}' is not mapped to any sleeve (and not excluded); "
            f"known codes: {sorted(taxonomy.code_to_sleeve)}; add it to "
            "taxonomy/albourne_mapping.yaml on delivery"
        ) from None


def unmapped_codes(values: object) -> list[str]:
    """The distinct values in ``values`` that map to no sleeve — the intake check.

    Excluded codes count as unmapped here deliberately: an excluded identifier
    (a composite benchmark) has no sleeve and must not enter a strategy-grouped
    intake either.
    """
    taxonomy = load_taxonomy()
    known = set(taxonomy.code_to_sleeve)
    seen: list[str] = []
    for value in values:  # type: ignore[attr-defined]
        code = str(value)
        if code not in known and code not in seen:
            seen.append(code)
    return seen
