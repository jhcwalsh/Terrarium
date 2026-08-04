"""WP4.2 — Tier-1 templates: deterministic words from tape-shaped inputs.

Determinism is the anchor (same input, same text, twice); then each
builder's refusals, Delta 2's editorial rules (cash-account voice, the
forced sale reading like distress), the CB statement's rule-keyed stance,
the peer percentile computed from ensemble bands, and the board pack
refusing to assemble with a missing section.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from ah.artifacts import render
from ah.artifacts import templates as tpl


class TestDeterminismAndFrame:
    def test_same_tape_same_words_end_to_end(self):
        kwargs: dict[str, Any] = dict(
            world_id="w1", dateline="2028-03-15", sleeve="pm_buyout", amount=12.5
        )
        a = render.render("wire_item", tpl.capital_call_event(**kwargs))
        b = render.render("wire_item", tpl.capital_call_event(**kwargs))
        assert a == b
        assert render.WATERMARK_BANNER in a  # the frame comes with the renderer


class TestCashflowEvents:
    def test_cash_account_is_the_voice(self):
        call = tpl.capital_call_event(world_id="w1", dateline="d", sleeve="pm_buyout", amount=10.0)
        dist = tpl.distribution_event(world_id="w1", dateline="d", sleeve="pm_buyout", amount=3.0)
        assert "cash account paid" in call["body"]
        assert "cash account received" in dist["body"]

    def test_forced_sale_reads_like_distress_and_names_everything(self):
        event = tpl.forced_sale_event(
            world_id="w1",
            dateline="d",
            amount=20.0,
            cause="cash shortfall after calls and spending",
            sleeves_sold=["public_equity"],
            kind="liquid_pro_rata",
        )
        assert event["headline"].startswith("FORCED SALE")
        assert "cash shortfall after calls and spending" in event["headline"]
        assert "public_equity" in event["body"]

    def test_forced_secondary_states_its_haircut(self):
        event = tpl.forced_sale_event(
            world_id="w1",
            dateline="d",
            amount=8.1,
            cause="liquid sleeves exhausted; forced secondary",
            sleeves_sold=["v2015", "v2016"],
            kind="forced_secondary",
            haircut=0.19,
        )
        assert "81.0% of carrying value" in event["body"]
        assert "19.0% discount" in event["body"]
        with pytest.raises(tpl.TemplateError, match="haircut"):
            tpl.forced_sale_event(
                world_id="w1",
                dateline="d",
                amount=8.1,
                cause="c",
                sleeves_sold=["v2015"],
                kind="forced_secondary",
            )
        with pytest.raises(tpl.TemplateError, match="sleeves"):
            tpl.forced_sale_event(
                world_id="w1",
                dateline="d",
                amount=8.1,
                cause="c",
                sleeves_sold=[],
                kind="liquid_pro_rata",
            )

    def test_coverage_band_direction_validated(self):
        event = tpl.coverage_band_event(
            world_id="w1", dateline="d", coverage=0.43, band_edge=0.40, direction="above"
        )
        assert "43.0%" in event["headline"] and "40.0%" in event["headline"]
        with pytest.raises(tpl.TemplateError, match="direction"):
            tpl.coverage_band_event(
                world_id="w1", dateline="d", coverage=0.4, band_edge=0.4, direction="sideways"
            )


class TestFurniture:
    def test_digest_lists_items_and_survives_a_quiet_day(self):
        digest = tpl.morning_digest(
            world_id="w1",
            dateline="d",
            items=[{"headline": "Spreads widen"}, {"headline": "CPI released"}],
        )
        assert digest["lines"] == ["- Spreads widen", "- CPI released"]
        quiet = tpl.morning_digest(world_id="w1", dateline="d", items=[])
        assert quiet["lines"] == ["- (a quiet session)"]

    def test_release_rows_carry_prior_and_refuse_incomplete(self):
        page = tpl.release_page(
            world_id="w1",
            dateline="d",
            release_name="CPI, February",
            rows=[{"series": "cpi_yoy", "value": "3.1%", "prior": "3.4%"}],
        )
        assert page["rows"][0]["revision"] == ""
        with pytest.raises(tpl.TemplateError, match="prior"):
            tpl.release_page(
                world_id="w1",
                dateline="d",
                release_name="CPI",
                rows=[{"series": "cpi_yoy", "value": "3.1%"}],
            )

    def test_cb_statement_stance_is_keyed_on_the_move(self):
        """Narrates drift, never announces a decision: the toy rate is a
        continuous stance, so the statement reports the quarter's move in bp
        and the level — and moves under 5bp read as little changed."""
        hike = tpl.central_bank_statement(
            world_id="w1", dateline="d", policy_rate=0.0525, previous_rate=0.05
        )
        assert "tightened" in hike["lines"][0]
        assert "5.25%" in hike["lines"][0]
        assert "up 25bp" in hike["lines"][0]
        assert "firmer policy" in hike["lines"][1]
        hold = tpl.central_bank_statement(
            world_id="w1", dateline="d", policy_rate=0.0503, previous_rate=0.05
        )
        assert "little changed" in hold["lines"][0]
        assert "5.03%" in hold["lines"][0]
        cut = tpl.central_bank_statement(
            world_id="w1", dateline="d", policy_rate=0.0475, previous_rate=0.05
        )
        assert "eased" in cut["lines"][0]
        assert "down 25bp" in cut["lines"][0]


class TestNewspaper:
    def test_front_page_leads_with_its_lead(self):
        page = tpl.newspaper_front_page(
            world_id="w1",
            dateline="Y2M4",
            lead="Inflation tops 8% as price pressure broadens",
            stories=["Credit spreads blow through 800bp; borrowers priced out"],
        )
        assert page["title"] == "THE MARKET RECORD — Y2M4"
        assert page["lines"][0].startswith("Inflation tops 8%")
        assert len(page["lines"]) == 2

    def test_a_page_with_no_lead_is_refused(self):
        with pytest.raises(tpl.TemplateError, match="lead"):
            tpl.newspaper_front_page(world_id="w1", dateline="d", lead="   ")

    def test_secondary_stories_are_optional_and_deterministic(self):
        once = tpl.newspaper_front_page(world_id="w1", dateline="d", lead="Something happened")
        twice = tpl.newspaper_front_page(world_id="w1", dateline="d", lead="Something happened")
        assert once == twice
        assert once["lines"] == ["Something happened"]


class TestStatementAndBoardPack:
    BANDS: ClassVar[dict[str, float]] = {
        "p5": -0.10,
        "p25": -0.02,
        "p50": 0.01,
        "p75": 0.04,
        "p95": 0.12,
    }

    def test_percentile_is_computed_from_bands(self):
        assert tpl._percentile_from_bands(0.02, self.BANDS).startswith("above the peer median")
        assert tpl._percentile_from_bands(-0.15, self.BANDS) == "below the 5th percentile of peers"
        assert tpl._percentile_from_bands(0.20, self.BANDS) == "above the 95th percentile of peers"
        with pytest.raises(tpl.TemplateError, match="monotone"):
            tpl._percentile_from_bands(0.0, {**self.BANDS, "p25": 0.5})
        with pytest.raises(tpl.TemplateError, match="band_quantiles"):
            tpl._percentile_from_bands(0.0, {"p50": 0.0})

    def test_quarterly_statement_renders_with_peer_line(self):
        payload = tpl.quarterly_statement(
            world_id="w1",
            dateline="d",
            quarter_label="2028-Q1",
            return_q=0.02,
            return_ytd=0.02,
            total_value=1204.5,
            net_flow=-12.0,
            peer_bands=self.BANDS,
        )
        text = render.render("statement", payload)
        assert "+2.0%" in text and "above the peer median" in text

    def test_board_pack_requires_all_five_sections(self):
        kwargs: dict[str, Any] = dict(
            world_id="w1",
            dateline="d",
            performance=["Q1 net: +1.2%"],
            allocation=["private 38% vs range 15-40%"],
            liquidity=["coverage 0.43 on liquid"],
            wire_digest=["- Spreads widen"],
            consultant_recommendation=["hold course"],
        )
        payload = tpl.board_pack(**kwargs)
        assert [s["title"] for s in payload["sections"]] == [
            "Performance",
            "Allocation vs policy ranges",
            "Liquidity position",
            "The quarter on the wire",
            "Consultant recommendation",
        ]
        with pytest.raises(tpl.TemplateError, match="liquidity"):
            tpl.board_pack(**{**kwargs, "liquidity": []})
