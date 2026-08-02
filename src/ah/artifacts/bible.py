"""The World Bible validator (WP4.3) — checks B1-B6, screen, cast binding.

The bible is the continuity database and the safety enforcement point: no
entity may appear in any artifact unless it is here or on the generic
allowlist, and nothing here may collide with a real firm. The rules are the
vendored schema's own text (creation_checks description), plus B6 — the
referential-integrity check ratified at kickoff (D-K4-1) from the
reconstruction notes' recommendation:

- B1: every named entity passes the real-entity screen
- B2: arcs respect the world horizon and do not overlap contradictorily
- B3: arcs are economically consistent with the world's parameters — a
  lender cannot gate in a world with no credit stress unless the beat is
  flagged idiosyncratic
- B4: required research-house priors present (the fixed prior vocabulary)
- B5: masthead names pass the trade-dress screen
- B6: every ``relationships[].with`` resolves to a known id (cast ids or
  the literal ``institution``)

The screen's data is vendored under ``fixtures/entity_screen/`` with its
version recorded in every validation result (``manifest.yaml`` is the
provenance record; GLEIF integration is a stated deferral there, not a
silent absence).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = _REPO_ROOT / "schemas" / "world-bible-v1.0.schema.json"
SCREEN_DIR = _REPO_ROOT / "fixtures" / "entity_screen"
VALIDATOR_VERSION = "bible-val/1.1"  # 1.1 = B6 added (kickoff D-K4-1)

_LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "llc",
    "lp",
    "llp",
    "plc",
    "sa",
    "ag",
    "nv",
    "se",
    "holdings",
    "group",
}
_STRESS_KEYWORDS = ("gate", "default", "covenant breach", "workout", "keys", "restructur")


class BibleError(ValueError):
    """A bible the validator refuses outright (schema or blocking B-check)."""


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _strip_suffixes(normalized: str) -> str:
    words = normalized.split()
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


@dataclass(frozen=True)
class EntityScreen:
    """The real-entity screen: vendored snapshot, version recorded."""

    names: frozenset[str]
    media_tokens: tuple[str, ...]
    version: str

    @classmethod
    def load(cls, directory: Path | None = None) -> EntityScreen:
        d = directory or SCREEN_DIR
        manifest = yaml.safe_load((d / "manifest.yaml").read_text("utf-8"))
        sec = json.loads((d / "sec_company_tickers.json").read_text("utf-8"))
        names: set[str] = set()
        for entry in sec.values():
            n = _normalize(entry["title"])
            names.add(n)
            names.add(_strip_suffixes(n))
        for line in (d / "curated_financial_entities.txt").read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                n = _normalize(line)
                names.add(n)
                names.add(_strip_suffixes(n))
        tokens = tuple(
            _normalize(line.strip())
            for line in (d / "curated_media_tokens.txt").read_text("utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        )
        return cls(
            names=frozenset(names) - {""},
            media_tokens=tokens,
            version=manifest["screen_version"],
        )

    def passes(self, name: str) -> bool:
        """True = no collision with a real entity."""
        n = _normalize(name)
        return n not in self.names and _strip_suffixes(n) not in self.names

    def passes_trade_dress(self, name: str) -> bool:
        n = _normalize(name)
        return not any(token in n for token in self.media_tokens)


@dataclass
class ValidationReport:
    validator_version: str
    screen_version: str
    passed: list[str] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def _all_named_entities(doc: dict[str, Any]) -> list[str]:
    names = [doc["institution"]["name"]]
    names += [c["name"] for c in doc["cast"]]
    names += [h["name"] for h in doc["research_houses"]]
    media = doc["media"]
    names += [media["wire_name"], media["paper_name"]]
    names += [col["name"] for col in media.get("columnists", [])]
    return names


def validate_bible(
    doc: dict[str, Any],
    *,
    horizon_quarters: int,
    screen: EntityScreen | None = None,
    stress_quarters: set[int] | None = None,
) -> ValidationReport:
    """Schema first, then B1-B6. Returns the report; blocking is the
    caller's ``report.ok`` check (creation refuses, regeneration logs).

    ``stress_quarters``: the world's credit-stress window, derived by the
    caller from the WorldSpec (regime path / factor conditions). ``None``
    means B3 CANNOT be evaluated — it lands in warnings and stays out of
    ``passed`` rather than passing silently.
    """
    screen = screen or EntityScreen.load()
    schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)

    report = ValidationReport(VALIDATOR_VERSION, screen.version)

    # B1 — real-entity screen over every named entity
    collisions = [n for n in _all_named_entities(doc) if not screen.passes(n)]
    if collisions:
        report.failures.append({"rule": "B1", "message": f"real-entity collision: {collisions}"})
    else:
        report.passed.append("B1")

    # B2 — arcs inside the horizon, strictly ordered per entity
    b2_bad: list[str] = []
    for c in doc["cast"]:
        quarters = [b["from_quarter"] for b in c.get("arc", [])]
        if any(q > horizon_quarters for q in quarters):
            b2_bad.append(f"{c['id']}: beat beyond horizon {horizon_quarters}")
        if quarters != sorted(set(quarters)):
            b2_bad.append(f"{c['id']}: beats not strictly ordered")
    if b2_bad:
        report.failures.append({"rule": "B2", "message": "; ".join(b2_bad)})
    else:
        report.passed.append("B2")

    # B3 — economic consistency of stress beats against the world's window
    if stress_quarters is None:
        report.warnings.append(
            {
                "rule": "B3",
                "message": "not evaluated: no stress window supplied; B3 is NOT in passed",
            }
        )
    else:
        b3_bad: list[str] = []
        for c in doc["cast"]:
            for beat in c.get("arc", []):
                text = beat["beat"].lower()
                is_stress_beat = (
                    any(k in text for k in _STRESS_KEYWORDS) and "idiosyncratic" not in text
                )
                if is_stress_beat and beat["from_quarter"] < min(stress_quarters, default=0):
                    b3_bad.append(
                        f"{c['id']} Q{beat['from_quarter']}: stress beat before any "
                        "credit stress exists in this world"
                    )
        if b3_bad:
            report.failures.append({"rule": "B3", "message": "; ".join(b3_bad)})
        else:
            report.passed.append("B3")

    # B4 — required research-house priors present. The schema's enum already
    # guarantees each prior is VALID; what B4 adds is the disagreeing pair:
    # at least two houses, and their priors must not all coincide (the
    # authoring regression set's "the pair must not converge", enforced at
    # creation rather than discovered at review).
    priors = [h["prior"] for h in doc["research_houses"]]
    if len(priors) < 2 or len(set(priors)) < 2:
        report.failures.append(
            {"rule": "B4", "message": f"need >= 2 houses with non-identical priors, got {priors}"}
        )
    else:
        report.passed.append("B4")

    # B5 — trade-dress screen on mastheads
    media = doc["media"]
    dressed = [
        n for n in (media["wire_name"], media["paper_name"]) if not screen.passes_trade_dress(n)
    ]
    if dressed:
        report.failures.append({"rule": "B5", "message": f"trade-dress collision: {dressed}"})
    else:
        report.passed.append("B5")

    # B6 — referential integrity (kickoff D-K4-1; blocks on failure)
    known = {c["id"] for c in doc["cast"]} | {"institution"}
    dangling = [
        f"{c['id']} -> {r['with']}"
        for c in doc["cast"]
        for r in c.get("relationships", [])
        if r["with"] not in known
    ]
    if dangling:
        report.failures.append({"rule": "B6", "message": f"dangling relationship ids: {dangling}"})
    else:
        report.passed.append("B6")

    return report


def bind_cast(doc: dict[str, Any], hero_ids: list[str]) -> dict[str, str]:
    """Bind ``held_by_institution`` cast entities to Step 3 hero funds, 1:1.

    A named GP has numbers behind it or it does not exist: the binding is
    positional over deterministic orderings (cast order, hero order), and a
    count mismatch refuses — no unbacked GP, no orphan hero.
    """
    held = [c["id"] for c in doc["cast"] if c.get("held_by_institution")]
    if len(held) != len(hero_ids):
        raise BibleError(
            f"cast/hero mismatch: {len(held)} held entities {held} vs {len(hero_ids)} heroes"
        )
    return dict(zip(held, hero_ids, strict=True))
