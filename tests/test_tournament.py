"""WP5.4 acceptance: the multi-agent comparative harness.

Same world, same seed, N participants; the three temporal formats are
configuration and MUST NOT move scores; the hold-course participant scores
exactly zero alpha; the leaderboard receives rows under the triple key; the
cohort-exercise export carries decisions, rationales, paths and dispersion.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from ah.cli import app
from ah.store.db import connect
from ah.store.leaderboard import scores
from ah.tournament import (
    FORMATS,
    TournamentError,
    band_rule_policy,
    hold_course_policy,
    random_policy,
    run_tournament,
)

RUNNER = CliRunner()


def _invoke(db: Path, *args: str):
    return RUNNER.invoke(app, ["--db", str(db), *args])


@pytest.fixture(scope="module")
def stored_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("tournament")
    db = tmp / "ah.db"
    assert _invoke(db, "world", "build", "--preset", "stagflation").exit_code == 0
    run = _invoke(db, "run", "--paths", "4")
    assert run.exit_code == 0
    return db, run.stdout.strip()


def _participants():
    return {
        "band-rule": band_rule_policy(),
        "luck": random_policy(base_seed=7),
        "hold-course": hold_course_policy(),
    }


class TestScoring:
    def test_hold_course_scores_exactly_zero_alpha(self, stored_run):
        db, rid = stored_run
        result = run_tournament(connect(db), rid, _participants(), submit=False)
        by_name = {r.participant: r for r in result.participants}
        assert by_name["hold-course"].alpha_vs_twin == 0.0
        assert by_name["hold-course"].final_value == result.twin_final

    def test_identical_revealed_path_only_decisions_differ(self, stored_run):
        """Two runs of the same tournament are byte-identical (determinism),
        and every participant's decisions land on the same window grid."""
        db, rid = stored_run
        a = run_tournament(connect(db), rid, _participants(), submit=False)
        b = run_tournament(connect(db), rid, _participants(), submit=False)
        for ra, rb in zip(a.participants, b.participants, strict=True):
            assert ra.decisions == rb.decisions
            assert np.array_equal(ra.total_path, rb.total_path)
        months = set(a.participants[0].decisions)
        assert all(set(r.decisions) == months for r in a.participants)

    def test_dispersion_statistics(self, stored_run):
        db, rid = stored_run
        result = run_tournament(connect(db), rid, _participants(), submit=False)
        d = result.dispersion
        assert d["n"] == 3.0
        assert d["min"] <= d["mean"] <= d["max"]
        assert d["spread"] == pytest.approx(d["max"] - d["min"])
        alphas = [r.alpha_vs_twin for r in result.participants]
        assert d["std"] == pytest.approx(float(np.std(alphas, ddof=1)))


class TestFormatsAreConfiguration:
    def test_scores_are_format_invariant(self, stored_run):
        """D-K5-5's three formats change scheduling, never outcomes."""
        db, rid = stored_run
        outcomes = {}
        for fmt in FORMATS:
            r = run_tournament(connect(db), rid, _participants(), fmt=fmt, submit=False)
            outcomes[fmt] = {p.participant: p.alpha_vs_twin for p in r.participants}
        assert outcomes["solo"] == outcomes["cohort-cadence"] == outcomes["simultaneous"]

    def test_unknown_format_refused(self, stored_run):
        db, rid = stored_run
        with pytest.raises(TournamentError, match="format"):
            run_tournament(connect(db), rid, _participants(), fmt="ladder", submit=False)


class TestInformationBasis:
    def test_reported_and_true_are_different_competitions(self, stored_run):
        """The DN-6 toggle arms: the band rule sees smoothed marks on one
        basis and true marks on the other, and (on a smoothing-heavy preset)
        the revealed trailing returns differ at some window."""
        db, rid = stored_run
        rep = run_tournament(connect(db), rid, {"band": band_rule_policy(0.02)}, submit=False)
        tru = run_tournament(
            connect(db), rid, {"band": band_rule_policy(0.02)}, basis="true", submit=False
        )
        assert rep.basis == "reported" and tru.basis == "true"
        # twins differ across bases (reported smoothing changes realized totals)
        assert rep.twin_final != tru.twin_final


class TestLeaderboardAndExport:
    def test_rows_land_under_the_triple_key(self, stored_run):
        db, rid = stored_run
        conn = connect(db)
        result = run_tournament(
            conn, rid, _participants(), submit=True, created_at="2026-08-03T00:00:00Z"
        )
        assert result.leaderboard_rows == 3
        rows = scores(
            conn,
            world_id=result.world_id,
            seed=result.seed,
            decision_alpha_version=result.decision_alpha_version,
        )
        assert {r["participant"] for r in rows} >= {"band-rule", "luck", "hold-course"}

    def test_submit_requires_created_at(self, stored_run):
        db, rid = stored_run
        with pytest.raises(TournamentError, match="created_at"):
            run_tournament(connect(db), rid, _participants(), submit=True)

    def test_export_is_the_wargame_record(self, stored_run):
        db, rid = stored_run
        result = run_tournament(connect(db), rid, _participants(), submit=False)
        ex = result.export
        assert ex["kind"] == "cohort-exercise-export"
        assert ex["twin_final_value"] == result.twin_final
        assert len(ex["participants"]) == 3
        # ranked by alpha, each entry self-contained
        alphas = [p["alpha_vs_twin"] for p in ex["participants"]]
        assert alphas == sorted(alphas, reverse=True)
        for p in ex["participants"]:
            assert p["decisions"] and p["rationales"]
            assert len(p["value_path"]) == len(result.participants[0].total_path)
        # rationales are the stated reasons, verbatim per window
        top = ex["participants"][0]
        assert all(isinstance(s, str) and s for s in top["rationales"].values())


class TestRefusals:
    def test_unknown_action_refused(self, stored_run):
        db, rid = stored_run
        with pytest.raises(TournamentError, match="unknown action"):
            run_tournament(
                connect(db),
                rid,
                {"bad": lambda s: ("yolo", "nope")},
                submit=False,
            )

    def test_missing_run_refused(self, stored_run):
        db, _rid = stored_run
        with pytest.raises(TournamentError, match="no run_record"):
            run_tournament(connect(db), "nope", _participants(), submit=False)

    def test_empty_field_refused(self, stored_run):
        db, rid = stored_run
        with pytest.raises(TournamentError, match="participant"):
            run_tournament(connect(db), rid, {}, submit=False)
