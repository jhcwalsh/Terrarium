"""housekeeping-01: the citation checker — the G2 §7 defect class, owned.

"The seal asserts or assumes something nothing mechanically verifies" was
found seven times in three days and the class was left unowned. This is the
cheapest named fix: every repo path a LIVING document cites must exist.

Scope, deliberately: the living documents (CLAUDE.md, the registers,
NEXT-STEPS, the active plans). Historical evidence documents describe the
repo as it was and may cite files that legitimately no longer exist; they
get an allowlist with reasons, not silent passes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

LIVING_DOCS = [
    "CLAUDE.md",
    "NEXT-STEPS.md",
    "docs/engine-realism-register.md",
    "Instructions/experience-deltas-register.md",
    "docs/interpretation-guide.md",
    "docs/superpowers/plans/2026-08-11-su-generated-worlds.md",
    "docs/superpowers/plans/2026-08-12-er6-call-pacing-design.md",
    "docs/superpowers/plans/2026-08-12-finish-single-player.md",
]

# A cited path that is KNOWN not to exist, with the reason it stays cited.
ALLOWLIST: dict[str, str] = {
    "docs/tier1-synthesis-and-decisions.md": (
        "named by Step 2's vendoring list and recorded as missing in "
        "CLAUDE.md itself - the citation IS the record of the gap"
    ),
}

_PATH_RE = re.compile(
    r"(?<![\w/])((?:src|docs|tests|artifacts|mappings|governance|scripts|"
    r"Instructions|app|fixtures|schemas|githooks)/[A-Za-z0-9_\-./]+"
    r"\.(?:py|md|yaml|yml|json|lock|svg|tsx|ts|css|gz|sh))"
)


def _cited_paths(text: str) -> set[str]:
    return {m.group(1).rstrip(".") for m in _PATH_RE.finditer(text)}


@pytest.mark.parametrize("doc", LIVING_DOCS)
def test_every_cited_path_exists(doc: str):
    text = (ROOT / doc).read_text(encoding="utf-8")
    dangling = [
        p for p in sorted(_cited_paths(text)) if not (ROOT / p).exists() and p not in ALLOWLIST
    ]
    assert not dangling, f"{doc} cites paths that do not exist: {dangling}"


def test_the_allowlist_stays_honest():
    """An allowlisted path that comes back into existence must leave the
    allowlist — an exception for a real file is camouflage."""
    for p in ALLOWLIST:
        assert not (ROOT / p).exists(), f"{p} exists; remove it from ALLOWLIST"
