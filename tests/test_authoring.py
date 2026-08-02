"""WP4.4 — the Tier-2 pipeline: payloads, prompts, the gate, retry/fallback.

No network anywhere (pytest-socket enforces): authors are injected
callables. The template-hash pin is the G4-pre freeze made executable —
editing a prompt without bumping its version fails here first.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from ah.artifacts import author as au
from ah.artifacts import payloads as pl
from ah.artifacts import prompts as pr
from ah.artifacts.gate import run_gate

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "Instructions" / "example-bible-credit-winter.json"

ALLOWED = [
    "Meridian Capital Partners",
    "Stonebeck Credit",
    "Kestrel Advisory",
    "Aline Vessey",
    "Calder & Root",
    "Grimshaw Partners",
    "The Harborlight Pension Trust",
    "The Simulated Wire",
    "The Ledger",
]
GENERIC = ["the central bank", "the statistics office", "the finance ministry", "the regulator"]

GOOD_DRAFT = (
    "Markets tested conviction this quarter, and the temporary dislocation in "
    "credit weighed on sentiment. Our reported return of +2.0% compares to "
    "+5.5% for public equities; we believe the difference reflects marks that "
    "arrive on their own schedule rather than impairment. Meridian Capital "
    "Partners remains focused on operations. The outlook may prove bumpy, and "
    "we expect discipline to matter more than forecasts. Onward."
)


def _bible() -> dict:
    return json.loads(EXAMPLE.read_text("utf-8"))


def _letter_payload(**overrides: Any) -> dict[str, Any]:
    entity = next(c for c in _bible()["cast"] if c["id"] == "meridian")
    kwargs: dict[str, Any] = dict(
        entity=entity,
        dateline="2028-03-15",
        dateline_quarter=8,
        quarter_label="2028-Q1",
        reported_return_q=0.02,
        reported_return_ytd=0.02,
        reported_return_si=0.31,
        nav_index=104.2,
        distributions_flag=True,
        calls_flag=False,
        gate_status="open",
        secondary_market_context="secondaries quoted low-80s vs NAV",
        public_equity_q=0.055,
        hy_spread_now_bps=450.0,
        policy_rate_now=0.05,
        cpi_now=0.031,
        chronicle_extracts=["Spreads widen 40bps", "CPI prints 3.1%"],
    )
    kwargs.update(overrides)
    return pl.build_p_letter(**kwargs)


class TestPayloads:
    def test_arc_beats_strip_at_the_dateline(self):
        payload = _letter_payload(dateline_quarter=8)
        assert any("Q4" in b for b in payload["arc_beats_to_date"])
        assert not any("Q9" in b for b in payload["arc_beats_to_date"])  # the leak, closed
        assert payload["comp_gap_exceeds_3pts"] is True

    def test_claims_are_preformatted_strings(self):
        claims = _letter_payload()["checkable_claims_table"]
        assert claims["reported_return_q"] == "+2.0%"
        assert claims["hy_spread_now_bps"] == "450bps"
        assert claims["policy_rate_now"] == "5.00%"


class TestPrompts:
    def test_letter_prompt_renders_fully(self):
        text = pr.render_prompt("letter", _letter_payload(), allowed_entities=ALLOWED)
        assert "{{" not in text  # every placeholder resolved
        assert "reported_return_q: +2.0%" in text
        assert "Meridian Capital Partners" in text
        assert "2028-03-15" in text

    def test_unresolved_placeholder_refuses(self):
        with pytest.raises(pr.PromptError, match="unresolved"):
            pr.render_prompt("note", _letter_payload(), allowed_entities=ALLOWED)

    def test_template_hash_pin_the_freeze_made_executable(self):
        assert (
            hashlib.sha256(pr.T_LETTER.encode()).hexdigest()
            == "58b0d9bc171648ee5664237ae0fc15de143e85d1e48bae6ac78a0289a7325cbe"
        ), "T-LETTER edited: bump author-prompt/letter version and re-run the regression set"
        assert (
            hashlib.sha256(pr.T_NOTE.encode()).hexdigest()
            == "3cb150e0f8390a003a196aad8663e7e2844759872361d9babc5a23c79e2f370a"
        ), "T-NOTE edited: bump author-prompt/note version and re-run the regression set"
        # versions bumped WITH their edits (the frozen rule, both levers)
        assert pr.PROMPT_VERSIONS["letter"] == "author-prompt/letter@1.4"
        assert pr.PROMPT_VERSIONS["note"] == "author-prompt/note@1.5"


class TestGate:
    def _run(self, draft: str, **kwargs: Any):
        return run_gate(
            draft,
            _letter_payload(),
            allowed_entities=ALLOWED,
            generic_allowlist=GENERIC,
            **kwargs,
        )

    def test_a_compliant_draft_passes(self):
        report = self._run(GOOD_DRAFT)
        assert not report.blocked, report.violations
        assert {"G1", "G2", "G3", "G4", "G5"} <= set(report.passed)

    def test_g1_blocks_a_derived_number(self):
        report = self._run(GOOD_DRAFT + " Annualized, that is +8.2% on our math.")
        assert any(v["rule"] == "G1" for v in report.violations)

    def test_g2_blocks_an_unsubstantiated_event(self):
        report = self._run(GOOD_DRAFT + " Peers face a bear market in credit.")
        assert any(v["rule"] == "G2" for v in report.violations)
        report = self._run(GOOD_DRAFT + " Rivals gated redemptions across the sector.")
        assert any(v["rule"] == "G2" for v in report.violations)

    def test_g2_ignores_gate_as_a_common_noun(self):
        # run-1 fix: 'gate' polices the redemption-gating EVENT, not vocabulary
        report = self._run(GOOD_DRAFT + " The gate between hope and evidence stays open.")
        assert not any(v["rule"] == "G2" for v in report.violations)

    def test_g2_modality_guard_outlook_is_not_an_event_claim(self):
        # run-2 fix: 'defaults may rise' speculates; 'defaults rose' claims
        report = self._run(GOOD_DRAFT + " If conditions worsen, defaults could follow.")
        assert not any(v["rule"] == "G2" for v in report.violations)
        report = self._run(GOOD_DRAFT + " Defaults rose across the book.")
        assert any(v["rule"] == "G2" for v in report.violations)


    def test_g4_sentence_starters_before_allowed_entities(self):
        # run-6 fix: 'Where Grimshaw sees rot' is the rival plus an adverb
        report = self._run(GOOD_DRAFT + " Where Meridian Capital Partners leads, we watch.")
        assert not any(v["rule"] == "G4" for v in report.violations)

    def test_g5_ordinary_cautious_prose_is_hedging(self):
        # run-6 fix: 'watching closely' hedges without the old lexicon
        draft = "A quarter of +2.0% against +5.5% for equities. We are watching closely. Onward."
        report = self._run(draft)
        assert not any("hedging" in v["message"] for v in report.violations if v["rule"] == "G5")

    def test_g2_pricing_in_is_an_expectation_not_an_event(self):
        report = self._run(GOOD_DRAFT + " Markets are pricing in rate cuts by year-end.")
        assert not any(v["rule"] == "G2" for v in report.violations)

    def test_g4_market_terms_are_subjects_not_entities(self):
        report = self._run(GOOD_DRAFT + " Private Credit repriced while Public Markets cleared.")
        assert not any(v["rule"] == "G4" for v in report.violations)

    def test_g3_blocks_a_future_reference(self):
        report = self._run(GOOD_DRAFT + " We are positioned for Q9 and beyond.")
        assert any(v["rule"] == "G3" for v in report.violations)

    def test_g4_blocks_an_unknown_proper_noun(self):
        report = self._run(
            GOOD_DRAFT.replace("Meridian Capital Partners", "Blackrock Global Advisors")
        )
        assert any(v["rule"] == "G4" for v in report.violations)

    def test_g4_exempts_salutations_and_letter_furniture(self):
        # run-1's dominant false positive (18/30): 'Dear Partners' is prose
        # furniture, not an entity reference
        drafted = "Dear Partners,\n" + GOOD_DRAFT + "\nSincerely Yours,\nThe Team"
        report = self._run(drafted)
        assert not any(v["rule"] == "G4" for v in report.violations), report.violations
        report = self._run("Dear Limited Partners,\n" + GOOD_DRAFT)
        assert not any(v["rule"] == "G4" for v in report.violations)

    def test_g5_blocks_promises_and_missing_hedge(self):
        report = self._run(GOOD_DRAFT + " We guarantee recovery.")
        assert any(v["rule"] == "G5" for v in report.violations)
        report = self._run("A quarter of +2.0% against +5.5% for equities. Onward.")
        assert any("hedging" in v["message"] for v in report.violations if v["rule"] == "G5")

    def test_g6_is_advisory_and_says_when_it_cannot_check(self):
        report = self._run(GOOD_DRAFT)
        assert any(w["rule"] == "G6" and "not evaluated" in w["message"] for w in report.warnings)
        assert not any(v["rule"] == "G6" for v in report.violations)

    def test_g7_fog_needs_marker_and_resolver(self):
        report = self._run(GOOD_DRAFT, fog={"resolver_scheduled": False})
        assert any(v["rule"] == "G7" for v in report.violations)
        fogged = GOOD_DRAFT + " People familiar with the fund describe unconfirmed interest."
        report = self._run(fogged, fog={"resolver_scheduled": True})
        assert "G7" in report.passed

    def test_g8_checks_the_rendered_marking(self):
        report = self._run(GOOD_DRAFT, rendered="stripped page")
        assert any(v["rule"] == "G8" for v in report.violations)


class TestPipeline:
    def _author_always(self, text: str) -> au.AuthorFn:
        return lambda prompt: text

    def test_pass_first_try(self):
        result = au.author_artifact(
            "letter",
            _letter_payload(),
            author=self._author_always(GOOD_DRAFT),
            model_id="fake-deterministic-author",
            allowed_entities=ALLOWED,
            generic_allowlist=GENERIC,
        )
        assert result.gate_result == "pass" and result.retry_count == 0
        assert result.author_tier == 2
        assert result.prompt_version == "author-prompt/letter@1.4"

    def test_pipeline_v2_self_check_runs_inside_the_submission(self):
        """AM-2026-08-02-004: the self-check repairs the draft BEFORE the
        gate sees it; the result records pipeline v2; without a checker the
        pipeline records v1 unchanged."""
        bad_then_fixed = GOOD_DRAFT + " We guarantee recovery."

        def checker(review_prompt: str) -> str:
            assert "FACTS TABLE" in review_prompt
            return GOOD_DRAFT  # the self-review strips the promise

        result = au.author_artifact(
            "letter",
            _letter_payload(),
            author=self._author_always(bad_then_fixed),
            model_id="fake",
            allowed_entities=ALLOWED,
            generic_allowlist=GENERIC,
            self_check=checker,
        )
        assert result.gate_result == "pass" and result.retry_count == 0
        assert result.pipeline_version == "author-pipeline/2.0"
        v1 = au.author_artifact(
            "letter",
            _letter_payload(),
            author=self._author_always(GOOD_DRAFT),
            model_id="fake",
            allowed_entities=ALLOWED,
            generic_allowlist=GENERIC,
        )
        assert v1.pipeline_version == "author-pipeline/1.0"

    def test_retry_prompt_carries_the_violation_then_passes(self):
        calls: list[str] = []

        def flaky(prompt: str) -> str:
            calls.append(prompt)
            return GOOD_DRAFT if len(calls) > 1 else GOOD_DRAFT + " Roughly +8.2% annualized."

        result = au.author_artifact(
            "letter",
            _letter_payload(),
            author=flaky,
            model_id="fake",
            allowed_entities=ALLOWED,
            generic_allowlist=GENERIC,
        )
        assert result.gate_result == "pass" and result.retry_count == 1
        assert "REJECTED by the consistency gate" in calls[1]
        assert "G1" in calls[1]

    def test_two_retries_then_tier1_fallback(self):
        attempts: list[int] = []
        result = au.author_artifact(
            "letter",
            _letter_payload(),
            author=self._author_always(GOOD_DRAFT + " A stubborn +9.9% appears."),
            model_id="fake",
            allowed_entities=ALLOWED,
            generic_allowlist=GENERIC,
            on_retry=lambda attempt, report: attempts.append(attempt),
        )
        assert result.gate_result == "fallback"
        assert result.retry_count == au.MAX_RETRIES == 2
        assert attempts == [0, 1, 2]
        assert result.author_tier == 1  # the substitute is Tier-1 authorship
        assert result.text.startswith("[Tier-1 substitute]")
        assert "reported_return_q: +2.0%" in result.text  # facts, plainly
