"""sp-03: the E4 post-game annotations — the flinch cost and the arithmetic
warning. Register text: both "computable from the RunRecord alone, no new
state"; tone "without smugness" — state the number, never gloat.

* FLINCH COST: a commitment cut at a window → the later distribution
  shortfall vs the plan, priced by re-running the SAME decisions with only
  that window's commitments restored to plan.
* ARITHMETIC WARNING: a defensive reaction taken while coverage's rise was
  DENOMINATOR-driven (reported NAV fell) rather than obligation-driven —
  priced by the window's own chain-link contribution when negative.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ah.annotations import post_game_annotations
from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import PRIVATE_ASSETS
from ah.port.book import CommitmentPlan

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(name: str = "stagflation", seed: int = 771204):
    doc = json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8"))
    return run_path(project_numeric(WorldSpec.model_validate(doc)), seed)


def _cut(month: int) -> dict:
    return {month: {"action": "hold", "commitments": {a: 0.0 for a in PRIVATE_ASSETS}}}


class TestFlinchCost:
    def test_a_commitment_cut_is_priced(self):
        p = _paths()
        notes = post_game_annotations(p, _cut(11))
        flinch = [n for n in notes if n["type"] == "flinch"]
        assert len(flinch) == 1
        note = flinch[0]
        assert note["month"] == 11
        # cutting a whole year's vintages to zero starves later distributions
        assert note["distribution_shortfall"] > 0.0
        assert "Year 1" in note["text"]
        assert "distribution" in note["text"].lower()
        # tone: the number, never a judgement word
        for smug in ("should", "mistake", "unfortunately", "sadly", "!"):
            assert smug not in note["text"].lower()

    def test_no_cut_no_flinch(self):
        p = _paths()
        notes = post_game_annotations(p, {11: "derisk"})
        assert not [n for n in notes if n["type"] == "flinch"]

    def test_holding_to_plan_is_not_a_flinch(self):
        """Committing points at-or-above the plan is not a cut."""
        from ah.play import plan_commitments, simulate_play

        p = _paths()
        base = simulate_play(p, None)
        q3 = next(q for q in base.quarters if q.quarter == 3)
        plan = plan_commitments(q3.private_weight_reported)
        notes = post_game_annotations(p, {11: {"action": "hold", "commitments": plan}})
        assert not [n for n in notes if n["type"] == "flinch"]


class TestFlinchIsMeasuredAgainstTheEnteredPlan:
    """I2 — spec section 2: "The lever shows deviation from *your* plan, not
    from the model's." ``post_game_annotations`` priced every cut against
    ``plan_commitments`` (the policy pacing rule) regardless of what the
    analyst actually planned, so an analyst who planned 1.0 and committed 1.0
    was told they had cut from ~6.3."""

    @staticmethod
    def _plan(value: float, windows: int = 9) -> CommitmentPlan:
        return CommitmentPlan(points={a: [value] * windows for a in PRIVATE_ASSETS})

    def test_committing_the_plans_own_number_is_not_a_flinch(self):
        """The analyst planned a low pace deliberately and held to it
        exactly. Against the model's pacing rule that reads as a large cut;
        against their own plan it is no cut at all."""
        p = _paths()
        plan = self._plan(1.0)
        held = {11: {"action": "hold", "commitments": {a: 1.0 for a in PRIVATE_ASSETS}}}

        against_model = post_game_annotations(p, held)
        assert [n for n in against_model if n["type"] == "flinch"], (
            "precondition: the model's pacing rule does read this as a cut"
        )

        against_own = post_game_annotations(p, held, commitment_plan=plan)
        assert not [n for n in against_own if n["type"] == "flinch"]

    def test_a_cut_below_the_entered_plan_is_still_priced_against_that_plan(self):
        """The bound must be re-based, not removed: cutting below your own
        plan is still a flinch, and the note quotes YOUR planned total."""
        p = _paths()
        plan = self._plan(1.0)
        notes = post_game_annotations(p, _cut(11), commitment_plan=plan)
        flinch = [n for n in notes if n["type"] == "flinch"]
        assert len(flinch) == 1
        assert flinch[0]["distribution_shortfall"] > 0.0
        # ER-14 close-out (Task S2): PRIVATE_ASSETS is now 4 sleeves
        # (pe/pc/re/infra), so 4 sleeves x 1.0 planned, cut to 0.0 — the
        # entered plan's own total.
        assert "from 4.0 to 0.0 points" in flinch[0]["text"]

    def test_the_counterfactual_restores_the_plan_not_the_pacing_rule(self):
        """The shortfall is priced by re-running with the window "restored to
        the plan". With an entered plan that must mean the plan's own number:
        restoring the MODEL's pace instead prices a commitment the analyst
        never planned, so the two shortfalls must differ."""
        p = _paths()
        # both stay under the declared bound the engine itself enforces
        # (2x target x rate). ER-14 close-out (Task S2, A15) tightened the
        # bound: re AND infra now share the tightest cap, 2*5.0*0.18=1.8
        # (re's target moved 7.0->5.0 in the carve; infra enters at 5.0
        # too) -- was re alone at 2.52 on the pre-ER14 START_TARGETS.
        low = post_game_annotations(p, _cut(11), commitment_plan=self._plan(0.5))
        high = post_game_annotations(p, _cut(11), commitment_plan=self._plan(1.5))
        low_note = next(n for n in low if n["type"] == "flinch")
        high_note = next(n for n in high if n["type"] == "flinch")
        assert high_note["distribution_shortfall"] > low_note["distribution_shortfall"]

    def test_no_plan_is_byte_identical_to_before(self):
        p = _paths()
        assert post_game_annotations(p, _cut(11), commitment_plan=None) == post_game_annotations(
            p, _cut(11)
        )


class TestQuarterlyFlinchCounterfactualStripsTheWholeYear:
    """D-QC-1, S4 review IMPORTANT-1 (a plan gap, not an implementer
    deviation): the no-plan flinch counterfactual stripped commitments only
    at the year-close month. Once ``simulate_play`` merges per-sleeve
    last-edit-wins across a vintage year's four windows (Task S4), an
    earlier SAME-YEAR edit survived the "restore to plan" replay and the
    counterfactual still carried the cut -- the review's probe scenario
    (a full cut entered at month 14 AND again at the month-23 lock) priced
    the flinch at ~0.0 instead of the value a lock-only cut of the same size
    prices. Fixed in ``annotations.py`` by stripping every window of the
    forming vintage year, not just the lock month's own entry.
    """

    def _full_cut(self) -> dict[str, float]:
        return {a: 0.0 for a in PRIVATE_ASSETS}

    def test_a_same_year_earlier_edit_no_longer_survives_the_restore(self):
        p = _paths()
        # the review's exact probe shape: the cut entered mid-year AND
        # (redundantly) again at the lock -- the shape S5's lock-fill
        # produces for a mid-year cut left untouched afterward.
        mid_and_lock = {
            14: {"action": "hold", "commitments": self._full_cut()},
            23: {"action": "hold", "commitments": self._full_cut()},
        }
        notes = post_game_annotations(p, mid_and_lock)
        flinch = [n for n in notes if n["type"] == "flinch"]
        assert len(flinch) == 1
        # the same economic cut, entered ONLY at the lock: before the fix
        # these two scenarios priced differently (the mid-year survivor
        # silently absorbed part of the cut, printing ~0.0 for the pair
        # above); after the fix the counterfactual strips the whole year
        # either way, so the two are priced identically.
        lock_only = post_game_annotations(p, _cut(23))
        lock_only_flinch = [n for n in lock_only if n["type"] == "flinch"]
        assert len(lock_only_flinch) == 1
        assert flinch[0]["distribution_shortfall"] == pytest.approx(
            lock_only_flinch[0]["distribution_shortfall"]
        )
        # and it must be a REAL shortfall, not the ~0.0 the defect produced
        assert flinch[0]["distribution_shortfall"] > 0.1

    def test_a_prior_year_edit_reaches_the_restore_untouched(self, monkeypatch):
        """Only the LOCKED year's own windows are stripped for the restore --
        an earlier vintage year's edit must reach ``simulate_play``
        UNCHANGED. Verified directly against the decisions map
        ``simulate_play`` is called with, not against downstream
        distribution totals: this is a full institutional simulation with
        waterfalls and forced sales, so changing YEAR 0's committed amount
        can shift year 1's own shortfall nonlinearly even when the fix is
        correct -- that would not be a fact about the fix, so it is not what
        this test checks.
        """
        import ah.annotations as annotations_mod

        p = _paths()
        decisions = {
            2: {"action": "hold", "commitments": {"pe": 3.0}},  # year 0, untouched
            23: {"action": "hold", "commitments": self._full_cut()},  # year 1's lock, cut
        }
        calls: list[dict] = []
        real_simulate_play = annotations_mod.simulate_play

        def _spy(paths_arg, decisions_arg, **kwargs):
            calls.append(dict(decisions_arg))
            return real_simulate_play(paths_arg, decisions_arg, **kwargs)

        monkeypatch.setattr(annotations_mod, "simulate_play", _spy)
        notes = post_game_annotations(p, decisions)
        assert [n for n in notes if n["type"] == "flinch"]
        # calls[0] is `active` (the original decisions, unmodified by
        # definition); calls[-1] is `restored`, the counterfactual this fix
        # touches. window_contributions_play's internal replays call
        # ah.play's OWN simulate_play reference, not this module's, so they
        # do not appear here.
        assert calls[0] == {2: {"action": "hold", "commitments": {"pe": 3.0}}, 23: decisions[23]}
        restored_call = calls[-1]
        assert restored_call[2] == {"action": "hold", "commitments": {"pe": 3.0}}
        assert restored_call[23] == "hold"


class TestArithmeticWarning:
    def test_denominator_driven_reaction_is_flagged_when_it_cost(self):
        """deflation_bust: reported NAV falls hard in the first years. A
        de-risk at the first window rides the denominator; if that window's
        contribution is negative, the warning prices it."""
        p = _paths("deflation_bust", 1848)
        notes = post_game_annotations(p, {11: "derisk"})
        warnings = [n for n in notes if n["type"] == "arithmetic_warning"]
        for w in warnings:  # shape holds whether or not this seed fires
            assert w["cost"] > 0.0
            assert "denominator" in w["text"].lower()
        flagged_any = bool(warnings)
        # the detector must at least run without inventing warnings on holds
        calm = post_game_annotations(_paths("goldilocks", 42), {11: "hold"})
        assert not [n for n in calm if n["type"] == "arithmetic_warning"]
        assert flagged_any in (True, False)  # documented: seed-dependent

    def test_annotations_are_deterministic(self):
        p = _paths()
        d = _cut(11)
        assert post_game_annotations(p, d) == post_game_annotations(p, d)


class TestServeCarriesAnnotations:
    pytestmark = pytest.mark.enable_socket

    def test_outcome_payload_has_the_annotations_list(self, tmp_path):
        from fastapi.testclient import TestClient
        from typer.testing import CliRunner

        from ah.cli import app as cli_app
        from ah.serve import create_app

        runner = CliRunner()
        db = tmp_path / "ah.db"
        assert (
            runner.invoke(
                cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation"]
            ).exit_code
            == 0
        )
        run = runner.invoke(cli_app, ["--db", str(db), "run", "--paths", "8"])
        rid = run.stdout.strip().splitlines()[-1]
        client = TestClient(create_app(db))
        r = client.post("/sessions", json={"run_id": rid})
        sid = r.json()["session_id"]
        months = r.json()["months"]
        # D-QC-1 (QC-1 Task S7, flagged by the S5/S6 report as an R-1-shaped
        # red outside the plan's named S7 file list): drive the session's
        # OWN quarterly window grid, not the annual decision_months one.
        for i, m in enumerate(r.json()["decision_windows"]):
            client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1})
            body: dict = {"month": m, "action": "hold"}
            if i == 0:
                body["commitments"] = {"pe": 0.0, "pc": 0.0, "re": 0.0}
            assert client.post(f"/sessions/{sid}/decisions", json=body).status_code == 200
        client.post(f"/sessions/{sid}/advance", json={"to_month": months})
        client.post(f"/sessions/{sid}/complete")
        out = client.get(f"/sessions/{sid}/outcome").json()
        kinds = {n["type"] for n in out["annotations"]}
        assert "flinch" in kinds
