"""WP5.7 acceptance: RESEARCH-EVIDENCE.md is generated and reproducible."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_regenerates_byte_identical_and_carries_the_contract():
    doc_path = ROOT / "RESEARCH-EVIDENCE.md"
    before = doc_path.read_text(encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_research_evidence.py")],
        check=True,
        capture_output=True,
    )
    after = doc_path.read_text(encoding="utf-8")
    assert after == before  # byte-identical regeneration from committed artifacts

    flat = " ".join(after.split())
    for marker in (
        "RQ1 ",
        "RQ2 ",
        "RQ3 ",
        "RQ4 ",
        "RQ5 ",
        "tested against the policy AND the generator together",
        "The negative results, collected",
        "INCONCLUSIVE",
        "2022 replay: FAIL",
        "holdout (wp5-06) is UNSPENT",
    ):
        assert marker in flat, marker
