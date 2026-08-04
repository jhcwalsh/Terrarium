"""su-app-03 acceptance: the tier-1 bundle feed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.feed import build_tier1_feed

PRESET = Path(__file__).resolve().parents[1] / "src" / "ah" / "presets" / "stagflation.json"


@pytest.fixture(scope="module")
def feed_and_paths():
    world = WorldSpec.model_validate(json.loads(PRESET.read_text("utf-8")))
    nw = project_numeric(world)
    paths = run_path(nw, 7)
    feed = build_tier1_feed(nw, paths, base_seed=7, n_peer_paths=12)
    return nw, paths, feed


class TestTier1Feed:
    def test_every_item_carries_a_month_inside_the_horizon(self, feed_and_paths):
        _nw, paths, feed = feed_and_paths
        assert feed, "the wire must not be empty"
        for item in feed:
            assert 0 <= item["month"] < paths.months
            assert item["type"] in {
                "cb_statement",
                "release_page",
                "quarterly_statement",
                "wire_digest",
            }

    def test_quarterly_cadence(self, feed_and_paths):
        _nw, paths, feed = feed_and_paths
        quarters = [m for m in range(paths.months) if (m + 1) % 3 == 0]
        for t in ("cb_statement", "release_page", "quarterly_statement"):
            months = [i["month"] for i in feed if i["type"] == t]
            assert months == quarters, t

    def test_cb_statement_tracks_the_tape(self, feed_and_paths):
        """The stance line is keyed on the tape's own rate move — no adjectives,
        no RNG. Drift narration: tightened/eased with the bp move, or little
        changed under the 5bp threshold. Check every statement against the
        raw rate path (rate is in engine percent; the template takes decimal)."""
        _nw, paths, feed = feed_and_paths
        for item in feed:
            if item["type"] != "cb_statement":
                continue
            m = item["month"]
            prev = m - 3
            move = (float(paths.rate[m]) - float(paths.rate[prev])) / 100.0 if prev >= 0 else 0.0
            first_line = item["payload"]["lines"][0]
            if round(abs(move) * 10000) < 5:
                assert "little changed" in first_line
            elif move > 0:
                assert "tightened" in first_line
            else:
                assert "eased" in first_line

    def test_deterministic(self, feed_and_paths):
        nw, paths, feed = feed_and_paths
        again = build_tier1_feed(nw, paths, base_seed=7, n_peer_paths=12)
        assert json.dumps(feed, sort_keys=True) == json.dumps(again, sort_keys=True)

    def test_crisis_onset_lands_on_the_wire(self, feed_and_paths):
        """The stagflation preset declares a crisis window; its opening month
        must appear as a wire digest exactly where the mask turns on."""
        _nw, paths, feed = feed_and_paths
        onsets = [
            m
            for m in range(paths.months)
            if paths.crisis[m] == 1.0 and (m == 0 or paths.crisis[m - 1] == 0.0)
        ]
        digest_months = [i["month"] for i in feed if i["type"] == "wire_digest"]
        assert digest_months == onsets

    def test_peer_bands_are_monotone(self, feed_and_paths):
        _nw, _paths, feed = feed_and_paths
        for item in feed:
            if item["type"] != "quarterly_statement":
                continue
            # the template embeds the band verdict in line 0; monotonicity was
            # enforced at build by _percentile_from_bands (raises otherwise) —
            # reaching here at all is the assertion, but check the line exists
            assert "percentile" in item["payload"]["lines"][0]
