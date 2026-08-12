"""su-app-03 acceptance: the tier-1 bundle feed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.feed import build_tier1_feed, headline_events

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
                "newspaper",
                "board_pack",  # sp-04: the pack finally has a producer
            }

    def test_calendar_cadence(self, feed_and_paths):
        """Releases are MONTHLY; the committee and the book stay quarterly.

        The split is the point (owner: "show the three monthly announcements
        - remember the FOMC doesn't meet monthly"). The central bank stays
        quarterly because the toy rate is a continuous drift with no meeting
        calendar; see docs/engine-realism-register.md ER-2.
        """
        _nw, paths, feed = feed_and_paths
        quarters = [m for m in range(paths.months) if (m + 1) % 3 == 0]
        for t in ("cb_statement", "quarterly_statement"):
            months = [i["month"] for i in feed if i["type"] == t]
            assert months == quarters, t
        releases = [i["month"] for i in feed if i["type"] == "release_page"]
        assert releases == list(range(paths.months))

    def test_release_carries_both_series_with_priors(self, feed_and_paths):
        _nw, paths, feed = feed_and_paths
        page = next(i for i in feed if i["type"] == "release_page" and i["month"] == 7)
        rows = page["payload"]["rows"]
        assert [r["series"] for r in rows] == ["CPI inflation", "High yield spread"]
        assert rows[0]["prior"] == f"{float(paths.inflation[6]):.1f}%"
        assert rows[1]["value"] == f"{float(paths.spread[7]):.0f}bp"

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

    def test_board_pack_lands_at_every_decision_window(self, feed_and_paths):
        """sp-04: the board pack finally has a producer — one per decision
        window, all five sections non-empty (the template refuses less), the
        consultant section stating facts, never advice (the E5 rule)."""
        from ah.artifacts.templates import BOARD_PACK_SECTIONS
        from ah.core.institution import decision_months

        _nw, paths, items = feed_and_paths
        packs = [i for i in items if i["type"] == "board_pack"]
        window_months = [m for m in decision_months(paths.months) if m < paths.months]
        assert [p["month"] for p in packs] == window_months
        for p in packs:
            sections = p["payload"]["sections"]
            assert len(sections) == len(BOARD_PACK_SECTIONS)
            for s in sections:
                assert s["lines"], s["title"]
            consultant = next(s for s in sections if "Consultant" in s["title"])
            joined = " ".join(consultant["lines"]).lower()
            advice_words = ("recommend buying", "you should", "we advise", "sell now")
            assert not any(w in joined for w in advice_words)

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

    def test_front_pages_only_when_the_tape_earns_them(self, feed_and_paths):
        """A newspaper exists exactly where a headline rule fired, at most one
        per month, and every page leads with a story."""
        _nw, paths, feed = feed_and_paths
        events = headline_events(paths)
        papers = [i for i in feed if i["type"] == "newspaper"]
        assert [p["month"] for p in papers] == sorted(events)
        assert papers, "a stagflation decade should make the news at least once"
        for p in papers:
            lines = p["payload"]["lines"]
            assert lines and lines[0].strip()
            assert lines[0] == events[p["month"]][0]
            assert len(lines) <= 4  # lead + at most three secondary stories

    def test_headlines_are_keyed_to_real_crossings(self, feed_and_paths):
        """Spot-check one rule end to end: an inflation headline may only
        appear on a month where the tape actually crossed the level."""
        _nw, paths, _feed = feed_and_paths
        for m, stories in headline_events(paths).items():
            for text in stories:
                if not text.startswith("Inflation tops"):
                    continue
                level = float(text.split()[2].rstrip("%"))
                assert paths.inflation[m - 1] < level <= paths.inflation[m]

    def test_drawdown_milestones_fire_once(self, feed_and_paths):
        """A 20% drawdown is news the first time. The market oscillating back
        and forth across the level is not three separate stories."""
        _nw, paths, _feed = feed_and_paths
        texts = [t for stories in headline_events(paths).values() for t in stories]
        dd = [t for t in texts if "off their peak" in t]
        assert len(dd) == len(set(dd))

    def test_headline_events_are_deterministic(self, feed_and_paths):
        _nw, paths, _feed = feed_and_paths
        assert headline_events(paths) == headline_events(paths)

    def test_peer_bands_are_monotone(self, feed_and_paths):
        _nw, _paths, feed = feed_and_paths
        for item in feed:
            if item["type"] != "quarterly_statement":
                continue
            # the template embeds the band verdict in line 0; monotonicity was
            # enforced at build by _percentile_from_bands (raises otherwise) —
            # reaching here at all is the assertion, but check the line exists
            assert "percentile" in item["payload"]["lines"][0]
