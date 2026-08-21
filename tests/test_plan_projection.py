"""app-open-04 Item H — per-class projected NAV behind the Cashflow panels.

``plan_projection`` runs the entered ladders and the plan's own vintages
through the SAME cohort recursion the engine plays (``ClosedEndCohort.step``,
``f_call = f_dist = 1`` — tier 0, the transparent benchmark) at tier-0's
frozen constant G. Display-surface math, server-side (DN-3 W5); nothing here
scores. The serve tests pin that both book endpoints carry the projection
and that a posted hand-edited plan is the one projected.
"""

from __future__ import annotations

import json

import pytest

from ah.play import (
    PRIVATE_ASSETS,
    START_TARGETS,
    default_commitment_plan,
    default_opening_book,
    plan_projection,
)
from ah.port.book import CommitmentPlan

# reuse the established app/client fixture — see tests/test_serve.py. Import
# ONLY the fixture name, never the Test* classes.
from test_serve import service  # noqa: F401  (pytest fixture)

pytestmark = pytest.mark.enable_socket


def _zero_plan(plan: CommitmentPlan) -> CommitmentPlan:
    return CommitmentPlan(points={s: [0.0] * len(v) for s, v in plan.points.items()})


class TestPlanProjection:
    def test_ten_year_paths_for_every_private_sleeve(self):
        proj = plan_projection(
            default_opening_book(START_TARGETS), default_commitment_plan(START_TARGETS)
        )
        assert set(proj) == set(PRIVATE_ASSETS)
        for sleeve in PRIVATE_ASSETS:
            nav = proj[sleeve]["nav_years"]
            assert len(nav) == 10
            assert all(x >= 0.0 for x in nav)

    def test_deterministic(self):
        book = default_opening_book(START_TARGETS)
        plan = default_commitment_plan(START_TARGETS)
        assert plan_projection(book, plan) == plan_projection(book, plan)

    def test_commitments_feed_the_path_a_zero_plan_runs_off(self):
        # the plan's vintages are the difference between a sustained
        # programme and a runoff: by year 10 the planned path must sit
        # clearly above the committed-nothing path in every sleeve.
        book = default_opening_book(START_TARGETS)
        plan = default_commitment_plan(START_TARGETS)
        with_plan = plan_projection(book, plan)
        without = plan_projection(book, _zero_plan(plan))
        for sleeve in PRIVATE_ASSETS:
            assert with_plan[sleeve]["nav_years"][-1] > without[sleeve]["nav_years"][-1]

    def test_a_heavier_plan_projects_a_higher_terminal_nav(self):
        book = default_opening_book(START_TARGETS)
        plan = default_commitment_plan(START_TARGETS)
        heavier = CommitmentPlan(points={s: [x * 1.5 for x in v] for s, v in plan.points.items()})
        base = plan_projection(book, plan)
        more = plan_projection(book, heavier)
        for sleeve in PRIVATE_ASSETS:
            assert more[sleeve]["nav_years"][-1] > base[sleeve]["nav_years"][-1]

    def test_the_projection_mutates_nothing(self):
        # book.cohorts() hands back fresh runtime objects, so projecting must
        # leave the BOOK document byte-identical — a projection that moved
        # the entered ladder would corrupt every later consumer.
        book = default_opening_book(START_TARGETS)
        before = book.model_dump_json()
        plan_projection(book, default_commitment_plan(START_TARGETS))
        assert book.model_dump_json() == before


class TestServedProjection:
    def test_book_default_carries_the_projection(self, service):
        client, _db, rid = service
        body = client.get(f"/book/default?run_id={rid}").json()
        assert set(body["projection"]) == set(PRIVATE_ASSETS)
        for sleeve in PRIVATE_ASSETS:
            assert len(body["projection"][sleeve]["nav_years"]) == 10

    def test_book_plan_carries_the_projection_of_the_derived_plan(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        r = client.post("/book/plan", json={"run_id": rid, "book": default["book"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body["projection"]) == set(PRIVATE_ASSETS)
        # the untouched default's derived plan reproduces the served default
        # projection to the served rounding
        for sleeve in PRIVATE_ASSETS:
            assert body["projection"][sleeve]["nav_years"] == pytest.approx(
                default["projection"][sleeve]["nav_years"], abs=1e-3
            )

    def test_a_posted_hand_edited_plan_is_the_one_projected(self, service):
        # the response's `plan` stays the server's derivation; the
        # PROJECTION follows the grid the analyst is looking at.
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        edited = json.loads(json.dumps(default["plan"]))
        edited["points"]["pe"] = [0.0] * len(edited["points"]["pe"])  # a pe freeze
        r = client.post("/book/plan", json={"run_id": rid, "book": default["book"], "plan": edited})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["plan"]["points"]["pe"] != edited["points"]["pe"], (
            "the served plan stays the derivation"
        )
        assert (
            body["projection"]["pe"]["nav_years"][-1] < default["projection"]["pe"]["nav_years"][-1]
        ), "the projection must reflect the posted freeze"

    def test_a_posted_plan_over_the_cap_is_422(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        bad = json.loads(json.dumps(default["plan"]))
        bad["points"]["pe"] = [999.0] * len(bad["points"]["pe"])
        r = client.post("/book/plan", json={"run_id": rid, "book": default["book"], "plan": bad})
        assert r.status_code == 422
        assert "declared bound" in r.json()["detail"]

    def test_a_posted_plan_with_the_wrong_window_count_is_422(self, service):
        client, _db, rid = service
        default = client.get(f"/book/default?run_id={rid}").json()
        short = json.loads(json.dumps(default["plan"]))
        for sleeve in short["points"]:
            short["points"][sleeve] = short["points"][sleeve][:-1]
        r = client.post("/book/plan", json={"run_id": rid, "book": default["book"], "plan": short})
        assert r.status_code == 422
        assert "decision window" in r.json()["detail"]
