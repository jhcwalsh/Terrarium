"""WP4.3 — the World Bible validator: B1-B6, the screen, cast binding.

The golden test is the owner-vendored credit-winter example (with its B6
inconsistency closed at WP4.3, per the reconstruction notes' own
recommendation). Then each rule's refusal, the screen's collision and
trade-dress behavior with the version recorded, B3's honest
cannot-evaluate path, and the 1:1 hero binding.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.artifacts import bible as wb

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "Instructions" / "example-bible-credit-winter.json"
CRISIS_WINDOW = set(range(4, 14))  # the example's own audit note: Q6-Q13, financing bites from Q4


def _example() -> dict:
    return json.loads(EXAMPLE.read_text("utf-8"))


@pytest.fixture(scope="module")
def screen() -> wb.EntityScreen:
    return wb.EntityScreen.load()


class TestGolden:
    def test_credit_winter_passes_all_six(self, screen):
        report = wb.validate_bible(
            _example(), horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert report.ok, report.failures
        assert report.passed == ["B1", "B2", "B3", "B4", "B5", "B6"]
        assert report.validator_version == "bible-val/1.1"
        assert report.screen_version == "sec-edgar-2026-08-02+curated-1.0"


class TestScreen:
    def test_real_names_collide_fictional_pass(self, screen):
        assert not screen.passes("Blackstone")
        assert not screen.passes("Apple Inc.")
        assert not screen.passes("Apollo Global Management LLC")  # suffix-stripped match
        assert screen.passes("Meridian Capital Partners")
        assert screen.passes("Stonebeck Credit")

    def test_trade_dress_tokens_block(self, screen):
        assert not screen.passes_trade_dress("The Bloomberg Ledger")
        assert not screen.passes_trade_dress("Financial Times of Harborlight")
        assert screen.passes_trade_dress("The Simulated Wire")

    def test_b1_blocks_a_real_collision(self, screen):
        doc = _example()
        doc["cast"][0]["name"] = "KKR"
        report = wb.validate_bible(
            doc, horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert not report.ok and report.failures[0]["rule"] == "B1"


class TestRules:
    def test_b2_blocks_beats_beyond_horizon_and_disorder(self, screen):
        # Meridian's Q30 beat is schema-valid but lands beyond a 20-quarter world
        report = wb.validate_bible(
            _example(), horizon_quarters=20, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert any(f["rule"] == "B2" for f in report.failures)
        doc = _example()
        doc["cast"][3]["arc"].append({"from_quarter": 12, "beat": "a duplicate quarter"})
        report = wb.validate_bible(
            doc, horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert any("ordered" in f["message"] for f in report.failures if f["rule"] == "B2")

    def test_b3_blocks_a_gate_before_any_stress(self, screen):
        doc = _example()
        # Stonebeck's gate at Q13 moved to Q2, before the world has credit stress
        doc["cast"][1]["arc"][2]["from_quarter"] = 2
        doc["cast"][1]["arc"] = sorted(doc["cast"][1]["arc"], key=lambda b: b["from_quarter"])
        report = wb.validate_bible(
            doc, horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert any(f["rule"] == "B3" for f in report.failures)

    def test_b3_idiosyncratic_flag_is_the_stated_exception(self, screen):
        doc = _example()
        doc["cast"][1]["arc"][2]["from_quarter"] = 2
        doc["cast"][1]["arc"][2]["beat"] += " (idiosyncratic operational failure)"
        doc["cast"][1]["arc"] = sorted(doc["cast"][1]["arc"], key=lambda b: b["from_quarter"])
        report = wb.validate_bible(
            doc, horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert not any(f["rule"] == "B3" for f in report.failures)

    def test_b3_without_stress_window_warns_and_never_passes_silently(self, screen):
        report = wb.validate_bible(_example(), horizon_quarters=40, screen=screen)
        assert "B3" not in report.passed
        assert any(w["rule"] == "B3" for w in report.warnings)

    def test_b4_blocks_a_converged_pair(self, screen):
        doc = _example()
        # schema-valid priors, but identical: the pair may not converge
        doc["research_houses"][1]["prior"] = doc["research_houses"][0]["prior"]
        report = wb.validate_bible(
            doc, horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert any(f["rule"] == "B4" for f in report.failures)

    def test_b5_blocks_a_dressed_masthead(self, screen):
        doc = _example()
        doc["media"]["paper_name"] = "The Reuters Ledger"
        report = wb.validate_bible(
            doc, horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert any(f["rule"] == "B5" for f in report.failures)

    def test_b6_blocks_a_dangling_relationship(self, screen):
        doc = _example()
        doc["cast"][0]["relationships"][0]["with"] = "nonexistent-id"
        report = wb.validate_bible(
            doc, horizon_quarters=40, screen=screen, stress_quarters=CRISIS_WINDOW
        )
        assert any(f["rule"] == "B6" for f in report.failures)


class TestCastBinding:
    def test_held_entities_bind_one_to_one(self):
        binding = wb.bind_cast(_example(), ["hero-meridian-2027", "hero-stonebeck-evergreen"])
        assert binding == {
            "meridian": "hero-meridian-2027",
            "stonebeck": "hero-stonebeck-evergreen",
        }

    def test_count_mismatch_refuses(self):
        with pytest.raises(wb.BibleError, match="mismatch"):
            wb.bind_cast(_example(), ["only-one-hero"])
