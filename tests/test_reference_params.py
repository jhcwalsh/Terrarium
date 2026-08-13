"""housekeeping-01: the RFR-96 class, checked from the unsealed side.

Campaign-2's disclosure: ``criterion_bearing`` verifies ensemble size,
vintage and prereg digest but NOT the reference-band parameters — an
invalid run whose reference was drawn at the wrong ``resample_length``
sailed through it. The sealed eval code cannot be edited without an
amendment, so this check lives where checks are free: a test that the
committed reference artifact's parameters equal the sealed declaration,
field by field.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

_SEALED_FIELDS = ("vintage_id", "seed", "n_resamples", "level", "block_length", "resample_length")


def _sealed_reference_block() -> dict:
    doc = yaml.safe_load((ROOT / "pre-registration.yaml").read_text(encoding="utf-8"))

    def find(node):
        if isinstance(node, dict):
            if all(f in node for f in _SEALED_FIELDS):
                return node
            for v in node.values():
                got = find(v)
                if got is not None:
                    return got
        elif isinstance(node, list):
            for v in node:
                got = find(v)
                if got is not None:
                    return got
        return None

    block = find(doc)
    assert block is not None, "no sealed reference block with all six parameter fields"
    return block


def test_the_committed_reference_run_matches_the_sealed_parameters():
    sealed = _sealed_reference_block()
    artifact = json.loads(
        (ROOT / "artifacts" / "campaign3" / "reference-run.json").read_text(encoding="utf-8")
    )
    recorded = artifact["reference_run"]
    for field in _SEALED_FIELDS:
        assert recorded[field] == sealed[field], (
            f"reference-run.json {field}={recorded[field]!r} != sealed "
            f"{sealed[field]!r} - the RFR-96 defect class, live"
        )
    # the artifact's own top-level echo must agree with its inner record
    assert artifact["n_resamples"] == recorded["n_resamples"]
    assert artifact["seed"] == recorded["seed"]
    assert artifact["vintage_id"] == recorded["vintage_id"]
