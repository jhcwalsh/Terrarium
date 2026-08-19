"""su-eng-02 acceptance, HTTP layer: the session service end to end.

Socket opt-in, stated: TestClient drives the ASGI app IN-PROCESS — no bytes
leave the interpreter — but asyncio's Windows event loop needs an internal
``socket.socketpair`` as its wakeup pipe, which pytest-socket blocks by
default. ``enable_socket`` is the invariant's sanctioned loopback opt-in
(pyproject: "tests that need a loopback socket can opt in explicitly");
the no-NETWORK rule stands untouched.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from ah.cli import app as cli_app
from ah.core.engine import run_path
from ah.core.institution import decision_months
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.prehistory import PREHISTORY_QUARTERS
from ah.serve import create_app
from ah.store import sessions as session_store
from ah.store.db import connect
from ah.store.runrecords import get_run_record
from ah.store.worlds import get_world

RUNNER = CliRunner()

pytestmark = pytest.mark.enable_socket


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("serve")
    db = tmp / "ah.db"
    assert (
        RUNNER.invoke(
            cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation"]
        ).exit_code
        == 0
    )
    run = RUNNER.invoke(cli_app, ["--db", str(db), "run", "--paths", "8"])
    assert run.exit_code == 0
    client = TestClient(create_app(db))
    return client, db, run.stdout.strip()


def _play_through(
    client, rid: str, actions: dict[int, str], first_commitments=None, **create_kwargs
):
    r = client.post("/sessions", json={"run_id": rid, **create_kwargs})
    assert r.status_code == 201, r.text
    sid = r.json()["session_id"]
    months = r.json()["months"]
    for i, m in enumerate(decision_months(months)):
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1}).status_code == 200
        body = {
            "month": m,
            "action": actions.get(m, "hold"),
            "client_log": {"time_on_window_ms": 1000},
        }
        if i == 0 and first_commitments is not None:
            body["commitments"] = first_commitments
        r = client.post(f"/sessions/{sid}/decisions", json=body)
        assert r.status_code == 200, r.text
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": months}).status_code == 200
    assert client.post(f"/sessions/{sid}/complete").status_code == 200
    return sid


@pytest.fixture(scope="module")
def gen_service(tmp_path_factory):
    """A session service over the GENERATED 1974 world (su-gen-03), against
    the synthetic bootstrap source — no vintage store, no network."""
    import ah.gen.bootstrap as bs
    from ah.gen import registry
    from conftest import make_synthetic_source_16

    saved = registry.snapshot()
    registry.register("bootstrap-v1", lambda: bs.BootstrapV1(make_synthetic_source_16()))
    tmp = tmp_path_factory.mktemp("gen-serve")
    db = tmp / "ah.db"
    try:
        assert (
            RUNNER.invoke(
                cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation_1974"]
            ).exit_code
            == 0
        )
        run = RUNNER.invoke(cli_app, ["--db", str(db), "run", "--paths", "8"])
        assert run.exit_code == 0
        client = TestClient(create_app(db))
        yield client, db, run.stdout.strip().splitlines()[-1]
    finally:
        registry.restore(saved)


def _patch_factor_lineage(monkeypatch) -> None:
    """Bundle-building a generated world reads the REAL local vintage catalog
    (OD-4) for factor lineage; tests inject a fake behind that seam instead
    of requiring ``data/catalog.duckdb`` to exist, same as ``test_bundle.py``
    (``test_generated_bundle_carries_factor_lineage``)."""
    import ah.bundle as bundle_mod
    import ah.gen.bootstrap as bs

    fake_lineage = {
        "vintage_id": "test-vintage",
        "units": {n: "test-units" for n in bs.FACTOR_SET},
        "proxy_shares": {
            n: {"n_months": 72, "n_proxy": 0, "share": 0.0, "by_rule": {}} for n in bs.FACTOR_SET
        },
    }
    monkeypatch.setattr(bundle_mod, "factor_lineage", lambda vintage_id: fake_lineage)


@pytest.fixture(scope="module")
def client_with_gen_run(gen_service):
    """Adapts ``gen_service`` into the (client, run_id, world_id, seed) shape
    Task 1's endpoints are exercised against — reuses the same generated-world
    fixture as TestGeneratedSessions rather than standing up a second store."""
    client, db, rid = gen_service
    conn = connect(db)
    rec = get_run_record(conn, rid)
    assert rec is not None
    return client, rid, rec["world_id"], rec["seed"]


class TestWorldsAndBundles:
    """Task 1 (sib-01): the two read-only listing endpoints — server-listed
    decades (GET /worlds) and CLI-identical bundle bytes (GET /runs/{id}/bundle)."""

    def test_worlds_lists_the_run_with_its_seed(self, client_with_gen_run):
        client, run_id, world_id, seed = client_with_gen_run
        doc = client.get("/worlds").json()
        world = next(w for w in doc["worlds"] if w["world_id"] == world_id)
        run = next(r for r in world["runs"] if r["run_id"] == run_id)
        assert run["seed"] == seed
        assert "created_at" in run

    def test_worlds_entry_carries_title_and_generator_id(self, client_with_gen_run):
        client, _run_id, world_id, _seed = client_with_gen_run
        doc = client.get("/worlds").json()
        world = next(w for w in doc["worlds"] if w["world_id"] == world_id)
        assert world["title"]  # stagflation_1974 -> "Nineteen Seventy-Four"
        assert world["generator_id"] and world["generator_id"] != "toy-v0"

    def test_worlds_lists_toy_worlds_too_no_filtering(self, service):
        """The store is the truth: toy AND generated worlds both appear."""
        client, _db, rid = service
        doc = client.get("/worlds").json()
        assert any(w["generator_id"] == "toy-v0" for w in doc["worlds"])
        assert any(rid == r["run_id"] for w in doc["worlds"] for r in w["runs"])

    def test_worlds_with_no_runs_returns_empty_runs_list(self, tmp_path):
        db = tmp_path / "empty.db"
        assert (
            RUNNER.invoke(
                cli_app, ["--db", str(db), "world", "build", "--preset", "stagflation"]
            ).exit_code
            == 0
        )
        client = TestClient(create_app(db))
        doc = client.get("/worlds").json()
        assert len(doc["worlds"]) == 1
        assert doc["worlds"][0]["runs"] == []

    def test_worlds_runs_are_newest_first(self, client_with_gen_run):
        client, run_id, world_id, _seed = client_with_gen_run
        doc = client.get("/worlds").json()
        world = next(w for w in doc["worlds"] if w["world_id"] == world_id)
        created = [r["created_at"] for r in world["runs"]]
        assert created == sorted(created, reverse=True)
        assert run_id in [r["run_id"] for r in world["runs"]]

    def test_bundle_bytes_match_the_cli_builder_exactly(self, gen_service, tmp_path, monkeypatch):
        _patch_factor_lineage(monkeypatch)
        client, db, run_id = gen_service
        served = client.get(f"/runs/{run_id}/bundle")
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("application/gzip")

        # authority check: identical bytes to the library builder the CLI
        # itself calls (ah.cli's bundle_cmd -> build_bundle + write_bundle)
        from ah.bundle import build_bundle, write_bundle

        conn = connect(db)
        doc = build_bundle(conn, run_id)
        out = tmp_path / "w.bundle.gz"
        write_bundle(doc, out)
        assert served.content == out.read_bytes()

    def test_unknown_run_is_404(self, client_with_gen_run):
        client, *_ = client_with_gen_run
        assert client.get("/runs/no-such-run/bundle").status_code == 404

    def test_bundle_is_cached_not_rebuilt(self, client_with_gen_run, monkeypatch):
        _patch_factor_lineage(monkeypatch)  # in case this run is not yet cached
        client, run_id, _world_id, _seed = client_with_gen_run
        first = client.get(f"/runs/{run_id}/bundle").content

        import ah.serve as serve_mod

        real = serve_mod._build_bundle_bytes
        calls = {"n": 0}

        def spy(conn, rid):
            calls["n"] += 1
            return real(conn, rid)

        monkeypatch.setattr(serve_mod, "_build_bundle_bytes", spy)
        second = client.get(f"/runs/{run_id}/bundle").content
        assert second == first
        assert calls["n"] == 0  # cache hit: the (patched) builder never ran


class TestGeneratedSessions:
    """su-gen-03: the server is the authority for generated worlds too."""

    def test_generated_session_plays_end_to_end(self, gen_service):
        client, _db, rid = gen_service
        sid = _play_through(client, rid, {})
        outcome = client.get(f"/sessions/{sid}/outcome").json()
        assert outcome["alpha"] == pytest.approx(0.0, abs=1e-9)  # hold == twin
        assert outcome["final_value"] > 0

    def test_generated_outcome_carries_its_own_alpha_version(self, gen_service):
        """Scores from generated worlds must never share a leaderboard row
        with toy scores: a DISTINCT alpha version, not a bump (survey S3)."""
        from ah.port.adapter import GEN_PLAY_ALPHA_VERSION

        client, _db, rid = gen_service
        sid = _play_through(client, rid, {23: "derisk"})
        outcome = client.get(f"/sessions/{sid}/outcome").json()
        assert outcome["decision_alpha_version"] == GEN_PLAY_ALPHA_VERSION
        from ah.play import PLAY_ALPHA_VERSION

        assert outcome["decision_alpha_version"] != PLAY_ALPHA_VERSION

    def test_generated_book_marks_to_market(self, gen_service):
        client, _db, rid = gen_service
        r = client.post("/sessions", json={"run_id": rid})
        assert r.status_code == 201, r.text
        sid = r.json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 11}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        assert doc["value"] is not None and doc["value"] > 0
        assert doc["twin_value"] is not None


class TestCommitmentLeverAPI:
    """sp-02: the lever reaches the session service — the server stays the
    authority (it computes the flexed plan; the app renders and asks)."""

    def test_session_exposes_the_next_plan_commitments(self, service):
        client, _db, rid = service
        r = client.post("/sessions", json={"run_id": rid})
        sid = r.json()["session_id"]
        client.post(f"/sessions/{sid}/advance", json={"to_month": 12})
        doc = client.get(f"/sessions/{sid}").json()
        plan = doc["next_plan_commitments"]
        assert set(plan) == {"pe", "pc", "re", "infra"}
        assert all(v > 0 for v in plan.values())

    def test_decide_accepts_commitments_and_scores_them(self, service):
        client, _db, rid = service
        sid = _play_through(
            client,
            rid,
            {},
            first_commitments={"pe": 0.0, "pc": 0.0, "re": 0.0},
        )
        out = client.get(f"/sessions/{sid}/outcome").json()
        assert out["alpha"] != 0.0  # cutting to zero departs the plan
        session = client.get(f"/sessions/{sid}").json()
        first = session["window_log"][0]
        assert first["commitments"] == {"pe": 0.0, "pc": 0.0, "re": 0.0}

    def test_session_exposes_the_vintage_stack_and_trailing_distributions(self, service):
        """sp-05, closing E1's last engine-side gaps: at the moment of
        decision the player can see the ladder BY AGE and the trailing
        distribution series, both server-computed."""
        client, _db, rid = service
        r = client.post("/sessions", json={"run_id": rid})
        sid = r.json()["session_id"]
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
        assert (
            client.post(
                f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"}
            ).status_code
            == 200
        )
        assert client.post(f"/sessions/{sid}/advance", json={"to_month": 24}).status_code == 200
        doc = client.get(f"/sessions/{sid}").json()
        stack = doc["vintage_nav"]
        assert stack and all(v >= 0 for v in stack.values())
        # the opening cohorts and at least one committed vintage by year 2.
        # The opening book is a staggered LADDER now (ladder-01), so the seed
        # rungs are `<sleeve>-s<k>` — one per year of a fund's life — where
        # there used to be a single `<sleeve>-play` clone.
        assert sum(1 for k in stack if "-s" in k) > 3
        assert any("-v" in k for k in stack)
        trailing = doc["trailing_distributions"]
        assert len(trailing) == 4  # four closed quarters of history
        assert all(v >= 0 for v in trailing)

    def test_out_of_bounds_commitments_are_422(self, service):
        client, _db, rid = service
        r = client.post("/sessions", json={"run_id": rid})
        sid = r.json()["session_id"]
        client.post(f"/sessions/{sid}/advance", json={"to_month": 12})
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={"month": 11, "action": "hold", "commitments": {"pe": 99.0}},
        )
        assert r.status_code == 422
        assert "commit" in r.json()["detail"]


def test_request_survives_a_threadpool_thread_hop(service):
    """Regression (found live, not by tests): FastAPI's threadpool can open
    the per-request connection on one worker thread and run the endpoint on
    another; SQLite's default same-thread guard then 500s the first real
    browser request while sequential tests pass. Force the hop explicitly."""
    from concurrent.futures import ThreadPoolExecutor

    _client, db, rid = service
    conn = connect(db, check_same_thread=False)
    with ThreadPoolExecutor(max_workers=1) as pool:
        row = pool.submit(
            lambda: conn.execute(
                "SELECT run_id FROM run_records WHERE run_id = ?", (rid,)
            ).fetchone()
        ).result()
    assert row["run_id"] == rid


class TestEndpoints:
    def test_create_and_get(self, service):
        client, _db, rid = service
        r = client.post("/sessions", json={"run_id": rid})
        assert r.status_code == 201
        doc = r.json()
        got = client.get(f"/sessions/{doc['session_id']}").json()
        assert got["status"] == "active"
        assert got["decision_windows"] == decision_months(got["months"])

    def test_book_is_marked_to_market_on_the_real_twin(self, service):
        """The rail's headline number, now with a cash account behind it."""
        from ah.core.engine import run_path
        from ah.core.numericworld import project_numeric
        from ah.core.worldspec import WorldSpec
        from ah.play import simulate_play
        from ah.store.db import connect
        from ah.store.runrecords import get_run_record
        from ah.store.worlds import get_world

        client, db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        assert client.get(f"/sessions/{sid}").json()["value"] is None

        doc = client.post(f"/sessions/{sid}/advance", json={"to_month": 6}).json()
        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        world = get_world(conn, rec["world_id"])
        assert world is not None
        paths = run_path(project_numeric(WorldSpec.model_validate(world)), rec["seed"])
        twin = simulate_play(paths, None, use_reported=True)
        # month 6 revealed -> quarter index 1 closed (months 3,4,5)
        assert doc["value"] == pytest.approx(twin.quarters[1].nav_reported)
        assert doc["cash"] == pytest.approx(twin.quarters[1].cash)
        assert doc["calls_paid"] >= 0.0
        assert 0.0 <= doc["private_weight_true"] <= 1.0

    def test_expired_commitment_reaches_the_player_and_stays_visible(self, service):
        """Audit F2: ER-6's terminal lapse was computed and dropped, so the
        player could watch unfunded commitment vanish with no line item saying
        it had been cancelled rather than called. It fires in ONE quarter of a
        decade, so the running total is what keeps it on the page afterwards.
        """
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        # unrevealed: masked like every other mark-to-market field
        assert client.get(f"/sessions/{sid}").json()["expired_undrawn"] is None

        # quarter by quarter, holding at every window (the reveal pointer
        # refuses to pass an undecided one)
        pending = set(decision_months(120))
        seen: list[float] = []
        for month in range(3, 121, 3):
            r = client.post(f"/sessions/{sid}/advance", json={"to_month": month})
            assert r.status_code == 200, r.json()
            doc = r.json()
            seen.append(doc["expired_undrawn"])
            # the running total never goes backwards and always covers the quarter
            assert doc["expired_undrawn_to_date"] >= doc["expired_undrawn"] - 1e-9
            for window in sorted(pending):
                if window < month:  # revealed, so decidable
                    client.post(
                        f"/sessions/{sid}/decisions", json={"month": window, "action": "hold"}
                    )
                    pending.discard(window)
        assert any(v > 0.0 for v in seen), "the lapse never reached the player"
        final = client.get(f"/sessions/{sid}").json()
        assert final["expired_undrawn_to_date"] == pytest.approx(sum(seen), abs=1e-6)
        # and it outlives the quarter it happened in: with a staggered ladder
        # (ladder-01) a rung retires once a year, so most quarters release
        # nothing while the running total still carries what the earlier ones
        # did. (This used to check the FINAL quarter, which held under the old
        # single mid-decade lapse and is now itself a lapse quarter.)
        quiet_after_a_lapse = [
            i for i, v in enumerate(seen) if v == 0.0 and any(e > 0.0 for e in seen[:i])
        ]
        assert quiet_after_a_lapse, "no quarter follows a lapse without one of its own"

    def test_spending_is_rederivable_from_what_the_session_exposes(self, service):
        """Audit F4: spending is correct internally (4.4e-16) but no exposed
        series let an outside party CHECK it. The value the rate is applied to
        is the trailing twelve-quarter mean of reported NAV as sampled INSIDE
        the waterfall (after calls, before spending and any forced sale) — not
        the quarter-end `nav_reported` the session serves, which is sampled
        after both. Averaging the served series lands 1-3% out and there was
        no way to tell which side was wrong.

        The basis is now served, so the charge closes on the surface that
        makes it: spending_paid == (rate / 4) * spending_basis, exactly.
        """
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        assert client.get(f"/sessions/{sid}").json()["spending_basis"] is None

        pending = set(decision_months(120))
        for month in range(3, 121, 3):
            doc = client.post(f"/sessions/{sid}/advance", json={"to_month": month}).json()
            assert doc["spending_basis"] > 0.0
            assert doc["spending_paid"] == pytest.approx(
                doc["spending_rate_annual"] / 4.0 * doc["spending_basis"], rel=1e-12
            )
            for window in sorted(pending):
                if window < month:
                    client.post(
                        f"/sessions/{sid}/decisions", json={"month": window, "action": "hold"}
                    )
                    pending.discard(window)

    def test_the_plan_prefill_declares_the_state_it_was_computed_from(self, service):
        """Audit F4: the lever's pre-fill is computed at the last CLOSED
        quarter, while the engine commits using the weight at the commitment
        quarter — one quarter later, and up to 7.9% different.

        It cannot be made exact: the commitment quarter's own returns are
        unrevealed at decision time, so computing the pre-fill from them would
        leak the tape. The honest fix is disclosure — the session states the
        weight and the quarter its pre-fill came from, and the app labels it.
        """
        from ah.play import plan_commitments

        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        doc = client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).json()

        basis = doc["next_plan_basis"]
        assert basis["as_of_quarter"] == 3  # months 9-11, the last closed
        assert basis["as_of_month"] == doc["revealed_months"] - 1
        assert basis["private_weight_reported"] == pytest.approx(doc["private_weight_reported"])
        # the pre-fill is exactly the plan AT THAT STATE, and says so
        expected = plan_commitments(basis["private_weight_reported"])
        for sleeve, points in doc["next_plan_commitments"].items():
            assert points == pytest.approx(expected[sleeve], abs=1e-4)

    def test_session_carries_the_product_alpha_version(self, service):
        from ah.play import PLAY_ALPHA_VERSION

        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        for month in decision_months(120):
            client.post(f"/sessions/{sid}/advance", json={"to_month": month + 1})
            client.post(f"/sessions/{sid}/decisions", json={"month": month, "action": "hold"})
        client.post(f"/sessions/{sid}/advance", json={"to_month": 120})
        client.post(f"/sessions/{sid}/complete")
        out = client.get(f"/sessions/{sid}/outcome").json()
        assert out["decision_alpha_version"] == PLAY_ALPHA_VERSION
        assert out["alpha"] == pytest.approx(0.0, abs=1e-9)

    def test_attribution_sums_to_the_alpha_reported(self, service):
        """The reckoning must add up on the surface, not just in the library."""
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        windows = decision_months(120)
        for i, month in enumerate(windows):
            client.post(f"/sessions/{sid}/advance", json={"to_month": month + 1})
            action = "derisk" if i == 0 else "hold"
            client.post(f"/sessions/{sid}/decisions", json={"month": month, "action": action})
        client.post(f"/sessions/{sid}/advance", json={"to_month": 120})
        client.post(f"/sessions/{sid}/complete")
        out = client.get(f"/sessions/{sid}/outcome").json()
        assert sum(out["window_contributions"]) == pytest.approx(out["alpha"], abs=1e-9)

    def test_a_decision_moves_the_book_away_from_the_twin(self, service):
        """Hold-course and the twin agree by construction; acting must not."""
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(120)[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        doc = client.post(
            f"/sessions/{sid}/decisions", json={"month": first, "action": "derisk"}
        ).json()
        # at the window itself the rebalance has just happened
        after = client.post(f"/sessions/{sid}/advance", json={"to_month": first + 7}).json()
        assert after["value"] != pytest.approx(after["twin_value"])
        assert doc["value"] is not None

    def test_unknown_run_404(self, service):
        client, _db, _rid = service
        assert client.post("/sessions", json={"run_id": "nope"}).status_code == 404

    def test_unknown_session_404(self, service):
        client, _db, _rid = service
        assert client.get("/sessions/nope").status_code == 404

    def test_invariant_violations_are_409(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(120)[0]
        # deciding an unrevealed window
        r = client.post(f"/sessions/{sid}/decisions", json={"month": first, "action": "hold"})
        assert r.status_code == 409
        # revealing past an undecided window
        r = client.post(f"/sessions/{sid}/advance", json={"to_month": first + 2})
        assert r.status_code == 409
        # outcome before completion
        assert client.get(f"/sessions/{sid}/outcome").status_code == 409


class TestOutcome:
    def test_outcome_matches_the_twin_exactly(self, service):
        """Same claim as before (WP2's toy-engine version), on the real twin:
        the session's outcome must equal ``ah.play.simulate_play`` run
        independently over the same tape and decisions."""
        from ah.play import simulate_play

        client, db, rid = service
        actions = {11: "derisk", 35: "leanin"}
        sid = _play_through(client, rid, actions)
        out = client.get(f"/sessions/{sid}/outcome").json()

        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        world = get_world(conn, rec["world_id"])
        assert world is not None
        nw = project_numeric(WorldSpec.model_validate(world))
        paths = run_path(nw, rec["seed"])
        decisions = {m: actions.get(m, "hold") for m in decision_months(paths.months)}
        active = simulate_play(paths, decisions, use_reported=True)
        twin = simulate_play(paths, None, use_reported=True)

        assert out["final_value"] == pytest.approx(active.final_value)
        assert out["twin_final_value"] == pytest.approx(twin.final_value)
        assert out["alpha"] == pytest.approx(active.final_value - twin.final_value)
        # DN-5 chain-link: the windows telescope exactly to the terminal alpha
        assert sum(w["contribution"] for w in out["windows"]) == pytest.approx(out["alpha"])
        assert [w["action"] for w in out["windows"]][:1] == ["derisk"]

    def test_outcome_series_carry_three_slots(self, service):
        """E7 (DN-5 R-1): active + twin value series, one point per CLOSED
        quarter (the twin's own cadence). INVERTED at sp-01: this test
        previously asserted ``drift_twin is None`` — the slot existed before
        its data so the arrival would be a deliberate data change. The data
        arrived (the fixed-schedule drift twin), so the assertion flips: the
        third series is populated on the same cadence."""
        client, _db, rid = service
        sid = _play_through(client, rid, {11: "derisk"})
        out = client.get(f"/sessions/{sid}/outcome").json()
        series = out["series"]
        months = client.get(f"/sessions/{sid}").json()["months"]
        assert len(series["active"]) == months // 3
        assert len(series["twin"]) == months // 3
        assert series["active"][-1] == pytest.approx(out["final_value"], abs=1e-3)
        assert series["twin"][-1] == pytest.approx(out["twin_final_value"], abs=1e-3)
        assert len(series["drift_twin"]) == months // 3
        assert all(isinstance(v, float) for v in series["drift_twin"])

    def test_ranked_completion_writes_the_board_once(self, service):
        client, db, rid = service
        sid = _play_through(client, rid, {11: "leanin"}, ranked=True, participant="james")
        out1 = client.get(f"/sessions/{sid}/outcome").json()
        out2 = client.get(f"/sessions/{sid}/outcome").json()  # re-read, no dup
        assert out1["alpha"] == out2["alpha"]
        conn = connect(db)
        rows = conn.execute(
            "SELECT participant, score, decision_alpha_version FROM leaderboard"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["participant"] == "james"
        assert rows[0]["score"] == pytest.approx(out1["alpha"])

    def test_leaderboard_reads_under_the_triple_key(self, service):
        """DN-5 R-1 read-side: the board query REQUIRES world+seed+alpha —
        and a different alpha version is a different (empty) board."""
        client, db, rid = service
        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        sid = _play_through(client, rid, {11: "derisk"}, ranked=True, participant="ada")
        out = client.get(f"/sessions/{sid}/outcome").json()
        board = client.get(
            f"/leaderboard/{rec['world_id']}",
            params={"seed": rec["seed"], "alpha_version": out["decision_alpha_version"]},
        ).json()
        assert any(r["participant"] == "ada" for r in board["rows"])
        scores = [r["score"] for r in board["rows"]]
        assert scores == sorted(scores, reverse=True)
        other = client.get(
            f"/leaderboard/{rec['world_id']}",
            params={"seed": rec["seed"], "alpha_version": "some-other-alpha"},
        ).json()
        assert other["rows"] == []  # boards never mix scoring versions
        missing_key = client.get(f"/leaderboard/{rec['world_id']}")
        assert missing_key.status_code == 422  # the triple key is not optional

    def test_dn6_s8_log_is_complete_on_a_ranked_run(self, service):
        """The register's requirement: full research logging from the FIRST
        ranked run. Every window row must carry the arm assignment (basis,
        ranked), the authoritative server timestamp, and the client telemetry
        fields — the analysis dataset is not recoverable retroactively."""
        client, db, rid = service
        sid = _play_through(client, rid, {}, ranked=True, participant="grace")
        conn = connect(db)
        doc = session_store.get_session(conn, sid)
        assert len(doc["window_log"]) == len(decision_months(doc["months"]))
        for row in doc["window_log"]:
            assert set(row) >= {"month", "action", "server_received_at", "basis", "ranked"}
            assert row["ranked"] is True and row["basis"] == "reported"
            assert row["server_received_at"]
            assert "time_on_window_ms" in row["client"]

    def test_practice_never_touches_the_board(self, service):
        client, db, rid = service
        before = connect(db).execute("SELECT COUNT(*) c FROM leaderboard").fetchone()["c"]
        sid = _play_through(client, rid, {})
        client.get(f"/sessions/{sid}/outcome")
        after = connect(db).execute("SELECT COUNT(*) c FROM leaderboard").fetchone()["c"]
        assert after == before


class TestRationale:
    """narr-02 (DN-9 N-af): the rationale field on decision windows, at the
    HTTP door. Task-mapped onto the session store (see the module docstring
    in ``ah.store.sessions``); scope is server-side only for this WP -- no
    Board, no UI, no scoring."""

    # The exact key set GET /sessions/{sid} served for a completed session
    # BEFORE this change (captured against the unmodified code, then frozen
    # here) -- acceptance 2's "byte-identical except the version stamp" made
    # concrete, without needing two code versions in one test run.
    # su-app-06: now includes opening_book and commitment_plan (both null for old sessions).
    # task 6: now also includes plan_pace (null for a session with no stored plan).
    # su-app-07 task 3: now also includes band_report (null unless the session's
    # book declares ranges AND a quarter has closed). The constant is EXTENDED,
    # never the `==` loosened: this test's job is to notice a new key.
    _PRE_NARR02_SESSION_KEYS: ClassVar[set[str]] = {
        "band_report",
        "basis",
        "calls_paid",
        "cash",
        "commitment_plan",
        "coverage_reported",
        "coverage_true",
        "created_at",
        "decision_windows",
        "decisions",
        "distributions_received",
        "expired_undrawn",
        "expired_undrawn_to_date",
        "forced_sale_total",
        "forced_sales",
        "months",
        "next_plan_basis",
        "next_plan_commitments",
        "opening_book",
        "participant",
        "plan_pace",
        "private_weight_reported",
        "private_weight_true",
        "ranked",
        "revealed_months",
        "run_id",
        "session_id",
        "spending_basis",
        "spending_paid",
        "spending_rate_annual",
        "status",
        "trailing_distributions",
        "twin_value",
        "updated_at",
        "value",
        "vintage_nav",
        "window_log",
        "world_id",
    }
    _PRE_NARR02_WINDOW_LOG_KEYS: ClassVar[set[str]] = {
        "action",
        "basis",
        "client",
        "commitments",
        "month",
        "ranked",
        "server_received_at",
    }

    def test_session_without_rationale_serializes_like_before(self, service):
        client, _db, rid = service
        sid = _play_through(client, rid, {})
        doc = client.get(f"/sessions/{sid}").json()
        assert set(doc) == self._PRE_NARR02_SESSION_KEYS | {"rationale_schema_version"}
        assert doc["rationale_schema_version"] == "1.0"
        for row in doc["window_log"]:
            assert set(row) == self._PRE_NARR02_WINDOW_LOG_KEYS  # no "rationale" key at all

    def test_rationale_round_trips_through_http_incl_unicode_and_newlines(self, service):
        client, _db, rid = service
        text = "café — the case for de-risking\nsecond line: 日本語のテキスト\ttabbed"
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(client.get(f"/sessions/{sid}").json()["months"])[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={
                "month": first,
                "action": "derisk",
                "rationale": {"free_text": text, "tags": ["valuation", "pacing"]},
            },
        )
        assert r.status_code == 200, r.text
        doc = client.get(f"/sessions/{sid}").json()
        row = doc["window_log"][0]
        assert row["rationale"]["free_text"] == text
        assert row["rationale"]["tags"] == ["valuation", "pacing"]
        assert row["rationale"]["recorded_at"]

    def test_rationale_null_by_default(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(client.get(f"/sessions/{sid}").json()["months"])[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        r = client.post(f"/sessions/{sid}/decisions", json={"month": first, "action": "hold"})
        assert r.status_code == 200
        row = client.get(f"/sessions/{sid}").json()["window_log"][0]
        assert "rationale" not in row

    def test_unknown_tag_rejected_with_explicit_422(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(client.get(f"/sessions/{sid}").json()["months"])[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={"month": first, "action": "hold", "rationale": {"tags": ["vibes"]}},
        )
        assert r.status_code == 422
        detail = str(r.json()["detail"])
        assert "tags" in detail
        # not silently coerced or dropped: the window must remain undecided
        after = client.get(f"/sessions/{sid}").json()
        assert after["window_log"] == []

    def test_too_many_tags_rejected_with_422(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(client.get(f"/sessions/{sid}").json()["months"])[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={
                "month": first,
                "action": "hold",
                "rationale": {"tags": ["valuation", "liquidity", "pacing", "governance"]},
            },
        )
        assert r.status_code == 422

    def test_free_text_over_600_chars_rejected_with_422(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(client.get(f"/sessions/{sid}").json()["months"])[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={"month": first, "action": "hold", "rationale": {"free_text": "x" * 601}},
        )
        assert r.status_code == 422
        # not silently truncated: the window must remain undecided
        after = client.get(f"/sessions/{sid}").json()
        assert after["window_log"] == []

    def test_free_text_at_600_chars_accepted(self, service):
        client, _db, rid = service
        sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
        first = decision_months(client.get(f"/sessions/{sid}").json()["months"])[0]
        client.post(f"/sessions/{sid}/advance", json={"to_month": first + 1})
        r = client.post(
            f"/sessions/{sid}/decisions",
            json={"month": first, "action": "hold", "rationale": {"free_text": "x" * 600}},
        )
        assert r.status_code == 200, r.text

    def test_rationale_never_leaks_to_outcome_leaderboard_or_bundle(self, service, monkeypatch):
        """The finding the task asks for, verified rather than reviewed: a
        distinctive marker planted in free_text must not surface on ANY
        shared payload -- the outcome endpoint (checked for a DIFFERENT
        session than the one that wrote it, since a player's own outcome MAY
        carry their own rationale), the leaderboard, or the world bundle."""
        import gzip

        client, db, rid = service
        marker = "SECRET-RATIONALE-MARKER-should-never-leak-9f3a"

        # session A: writes the marker, ranked (so it also reaches the board)
        sid_a = client.post(
            "/sessions", json={"run_id": rid, "ranked": True, "participant": "leak-writer"}
        ).json()["session_id"]
        months = client.get(f"/sessions/{sid_a}").json()["months"]
        windows = decision_months(months)
        for i, m in enumerate(windows):
            client.post(f"/sessions/{sid_a}/advance", json={"to_month": m + 1})
            body = {"month": m, "action": "hold"}
            if i == 0:
                body["rationale"] = {"free_text": marker, "tags": ["valuation"]}
            r = client.post(f"/sessions/{sid_a}/decisions", json=body)
            assert r.status_code == 200, r.text
        client.post(f"/sessions/{sid_a}/advance", json={"to_month": months})
        client.post(f"/sessions/{sid_a}/complete")

        outcome_a = client.get(f"/sessions/{sid_a}/outcome")
        assert outcome_a.status_code == 200
        assert marker not in outcome_a.text  # own outcome payload: not exposed by this WP

        conn = connect(db)
        rec = get_run_record(conn, rid)
        assert rec is not None
        board = client.get(
            f"/leaderboard/{rec['world_id']}",
            params={
                "seed": rec["seed"],
                "alpha_version": outcome_a.json()["decision_alpha_version"],
            },
        )
        assert marker not in board.text

        # session B (a different "player"): its own outcome must not see A's rationale
        sid_b = _play_through(client, rid, {})
        outcome_b = client.get(f"/sessions/{sid_b}/outcome")
        assert marker not in outcome_b.text

        bundle = client.get(f"/runs/{rid}/bundle")
        assert bundle.status_code == 200
        assert marker.encode() not in bundle.content
        assert marker not in gzip.decompress(bundle.content).decode("utf-8", errors="ignore")

    def test_decision_replay_bit_identical_with_and_without_rationale(self, service):
        """rationale must never reach ``simulate_play``: a session decided
        WITH rationale on every window must produce a bit-identical outcome
        to the same action sequence decided with none."""
        client, _db, rid = service
        actions = {}
        months = client.get(
            f"/sessions/{client.post('/sessions', json={'run_id': rid}).json()['session_id']}"
        ).json()["months"]
        windows = decision_months(months)
        for i, m in enumerate(windows):
            actions[m] = "derisk" if i == 0 else "hold"

        def play(with_rationale: bool) -> dict:
            sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
            for i, m in enumerate(windows):
                client.post(f"/sessions/{sid}/advance", json={"to_month": m + 1})
                body = {"month": m, "action": actions[m]}
                if with_rationale:
                    body["rationale"] = {
                        "free_text": f"reasoning for window {i}",
                        "tags": ["valuation", "pacing"],
                    }
                r = client.post(f"/sessions/{sid}/decisions", json=body)
                assert r.status_code == 200, r.text
            client.post(f"/sessions/{sid}/advance", json={"to_month": months})
            client.post(f"/sessions/{sid}/complete")
            return client.get(f"/sessions/{sid}/outcome").json()

        without = play(False)
        with_r = play(True)
        assert with_r["final_value"] == without["final_value"]
        assert with_r["alpha"] == without["alpha"]
        assert with_r["series"] == without["series"]
        assert with_r["window_contributions"] == without["window_contributions"]


def test_cio_view_endpoint(service):
    """cio-04 made ``build_cio_view``'s ``prehistory`` default to True, and
    the endpoint now passes ``prehistory=(generator_id == "toy-v0")``
    explicitly. The ``service`` fixture's world is ``toy-v0`` (stagflation),
    so the flag resolves True either way and the inherited decade lands
    here — the plan history is now the pre-history's 40 quarters plus the 4
    revealed world quarters, not the 4 world quarters alone."""
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
    r = client.get(f"/sessions/{sid}/cio")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["meta"]["plane"] == "reported"
    assert v["meta"]["planesAvailable"] == ["reported", "true"]
    assert v["plan"]["history"]["worldStartIndex"] == PREHISTORY_QUARTERS * 3
    assert len(v["plan"]["history"]["values"]) == PREHISTORY_QUARTERS * 3 + 12
    r_true = client.get(f"/sessions/{sid}/cio", params={"plane": "true"})
    assert r_true.status_code == 200
    assert r_true.json()["meta"]["plane"] == "true"
    assert r_true.json()["plan"]["totalValue"] != v["plan"]["totalValue"]


def test_cio_view_rejects_bad_params(service):
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 6}).status_code == 200
    assert client.get(f"/sessions/{sid}/cio", params={"plane": "both"}).status_code == 422
    assert client.get(f"/sessions/{sid}/cio", params={"forecast_quarters": 9}).status_code == 422
    assert client.get("/sessions/nope/cio").status_code == 404


def test_cio_view_needs_a_closed_quarter(service):
    """Was: a FRESH session (revealed_months == 0) 409ed here — "no closed
    quarter yet". app-open-01 (cio-05) makes the CIO the front door: the
    first thing a player sees after the opening book is confirmed is this
    dashboard, populated with STARTING values, not an error screen. Inverted
    (CLAUDE.md: invert, don't delete, when the thing a test pinned changes on
    purpose) — see test_cio_view_at_month_zero below for the new contract.
    The still-true half of the old claim survives: mid-quarter (1 or 2
    months revealed — unreachable through the UI's quarterly rhythm, but not
    through the raw API) still has no closed quarter and still 409s."""
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    assert client.get(f"/sessions/{sid}/cio").status_code == 200
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 2}).status_code == 200
    assert client.get(f"/sessions/{sid}/cio").status_code == 409


def test_cio_view_at_month_zero(service):
    """app-open-01 (cio-05): the CIO is now the front door. A session that
    has never advanced still returns a full, valid CioView — populated from
    the opening book (the derived default here) and, for this toy-v0 world,
    the inherited decade (ER-13), not the world's own (nonexistent) tape."""
    client, _db, rid = service
    sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
    r = client.get(f"/sessions/{sid}/cio")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["meta"]["asOfLabel"] == "T0"
    assert v["privateCashflows"]["histCount"] == 0
    # "now" IS the opening state: zero elapsed growth, a real (non-null,
    # non-fabricated) total, and an allocation that closes on 100 — the
    # dashboard's STARTING values, not an empty payload.
    assert v["plan"]["growthPct"] == 0.0
    assert v["plan"]["totalValue"] > 0
    cur = sum(c["currentPct"] for c in v["allocation"]["classes"])
    assert abs(cur - 100.0) < 0.1
    # the inherited decade (this world is toy-v0) still lands: the chart has
    # something to draw and the honesty label is present, same as any other
    # reveal (cio-04's contract, unchanged by this WP).
    assert v["plan"]["history"]["values"]
    assert v["plan"]["preRunLabel"]
    # no world quarter has closed, so YTD (a "this calendar year" concept)
    # cannot mean anything yet — null, not a value borrowed from the
    # inherited decade the way 1Q/1Y legitimately are.
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    assert v["performance"]["total"][idx["YTD"]] is None


def test_cio_view_parity_with_mark_to_market(service):
    """The two payloads can never disagree on the book (spec section 5)."""
    client, _db, rid = service
    r = client.post("/sessions", json={"run_id": rid})
    sid = r.json()["session_id"]
    # Decision window 11 blocks the reveal pointer past month 12 (the game's
    # commit-before-you-see-it rule) — deciding it is required to reach
    # month 24, not part of the parity claim under test.
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
    assert (
        client.post(f"/sessions/{sid}/decisions", json={"month": 11, "action": "hold"}).status_code
        == 200
    )
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 24}).status_code == 200
    doc = client.get(f"/sessions/{sid}").json()
    v = client.get(f"/sessions/{sid}/cio").json()
    # build_cio_view rounds every figure to 4dp (its published contract);
    # _mark_to_market does not, so parity is exact up to that rounding, not
    # to float epsilon. Tolerance set to the max single-figure rounding error
    # (5e-5) with margin, not the un-rounded 1e-6 the brief's draft assumed.
    assert abs(v["plan"]["totalValue"] - doc["value"]) < 1e-4
    cash_class = next(c for c in v["allocation"]["classes"] if c["id"] == "cash")
    assert abs(cash_class["value"] - doc["cash"]) < 1e-4
    priv = sum(c["value"] for c in v["allocation"]["classes"] if c.get("isPrivate"))
    assert abs(priv / v["plan"]["totalValue"] - doc["private_weight_reported"]) < 1e-4


def test_cio_view_carries_the_inherited_decade(service):
    """cio-04's endpoint wiring: a toy-v0 world's /cio response splices in
    the inherited decade, so the plan history starts before world month 0
    and the long return windows (e.g. 10Y) are no longer null this early."""
    client, _db, rid = service
    sid = client.post("/sessions", json={"run_id": rid}).json()["session_id"]
    assert client.post(f"/sessions/{sid}/advance", json={"to_month": 12}).status_code == 200
    v = client.get(f"/sessions/{sid}/cio").json()
    assert v["plan"]["history"]["worldStartIndex"] > 0
    assert v["plan"]["preRunLabel"]
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    assert v["performance"]["total"][idx["10Y"]] is not None
