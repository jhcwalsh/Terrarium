"""WP4.5 — the regression set's freeze, coverage, and offline replay.

The manifest's hashes ARE the freeze: any drift in any payload fails
here. Coverage asserts the frozen membership rule's grid is actually
present. Recorded live outputs (when present) replay through the gate
offline — a draft recorded as a pass must still pass, deterministically,
with no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ah.artifacts.gate import run_gate
from ah.artifacts.prompts import render_prompt

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "fixtures" / "authoring_regression"
BIBLE = ROOT / "Instructions" / "example-bible-credit-winter.json"

SCENARIOS = ("bull", "crash", "gate_event", "comp_gap", "quiet")


def _manifest() -> dict:
    return yaml.safe_load((REG / "manifest.yaml").read_text("utf-8"))


def _allowed() -> tuple[list[str], list[str]]:
    bible = json.loads(BIBLE.read_text("utf-8"))
    allowed = (
        [bible["institution"]["name"]]
        + [c["name"] for c in bible["cast"]]
        + [h["name"] for h in bible["research_houses"]]
        + [bible["media"]["wire_name"], bible["media"]["paper_name"]]
    )
    return allowed, list(bible["safety"]["generic_allowlist"])


class TestFreeze:
    def test_every_payload_matches_its_frozen_hash(self):
        manifest = _manifest()
        assert manifest["payload_count"] == 30
        bad = []
        for payload_id, declared in manifest["payloads"].items():
            path = REG / "payloads" / f"{payload_id}.json"
            actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != declared:
                bad.append(payload_id)
        assert not bad, f"frozen payloads drifted: {bad}"

    def test_no_unfrozen_payload_files(self):
        on_disk = {p.stem for p in (REG / "payloads").glob("*.json")}
        assert on_disk == set(_manifest()["payloads"])

    def test_ship_gate_is_the_frozen_value(self):
        assert _manifest()["ship_gate_first_pass"] == 0.95


class TestCoverage:
    def test_the_membership_grid_is_complete(self):
        ids = set(_manifest()["payloads"])
        for scenario in SCENARIOS:
            for entity in ("meridian", "stonebeck"):
                assert f"letter-{scenario}-{entity}" in ids
            for house in ("calder", "grimshaw"):
                for subject in ("private_credit", "stonebeck"):
                    assert f"note-{scenario}-{house}-{subject}" in ids

    def test_every_payload_renders_its_prompt_fully(self):
        allowed, _ = _allowed()
        for path in (REG / "payloads").glob("*.json"):
            payload = json.loads(path.read_text("utf-8"))
            kind = "letter" if path.stem.startswith("letter-") else "note"
            text = render_prompt(kind, payload, allowed_entities=allowed)
            assert "{{" not in text, path.stem

    def test_the_house_pair_disagrees_by_construction(self):
        priors = set()
        for path in (REG / "payloads").glob("note-bull-*-private_credit.json"):
            priors.add(json.loads(path.read_text("utf-8"))["house"]["prior"])
        assert len(priors) == 2  # the pair must not converge, starting from the priors


class TestRecordedReplay:
    def test_recorded_passes_still_pass_offline(self):
        """Every recorded tier-2 pass re-gates clean, deterministically.
        Zero recordings = zero iterations (the live run fills this in);
        the evidence file's presence demands recordings exist."""
        allowed, generic = _allowed()
        recorded = sorted((REG / "recorded").glob("*.json")) if (REG / "recorded").exists() else []
        evidence = ROOT / "governance" / "evidence" / "AUTHORING-REGRESSION.md"
        if evidence.exists():
            assert recorded, "evidence exists but no recorded outputs are committed"
        for path in recorded:
            record = json.loads(path.read_text("utf-8"))
            if record["author_tier"] != 2:
                continue  # fallbacks are tier-1 substitutes, not gated prose
            payload = json.loads(
                (REG / "payloads" / f"{record['payload_id']}.json").read_text("utf-8")
            )
            report = run_gate(
                record["text"],
                payload,
                allowed_entities=allowed,
                generic_allowlist=generic,
                is_note=(record["kind"] == "note"),
            )
            assert not report.blocked, (record["payload_id"], report.violations)
            assert record["prompt_version"].startswith("author-prompt/")
            assert record["model_id"]
