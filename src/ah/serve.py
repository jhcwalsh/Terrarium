"""The session service (su-eng-02) — DN-3's client-plane server, minimal cut.

FastAPI app over the existing SQLite stores. The server is the AUTHORITY for
everything that scores (W5): the reveal pointer, the decision log, the outcome
computation. The bundle (su-eng-01) is what the browser renders; this service
is what the browser must convince to change state.

v0.1 scope (PD-3): no auth — single-user, local. The app binds to localhost;
ranked rows carry a self-declared participant name. Auth joins at the M4
boundary with the consent clause, before ANY external user.

Endpoints:
- ``POST /sessions``                  open a session over a RunRecord
- ``GET  /sessions/{sid}``            session state (pointer, decisions, status)
- ``POST /sessions/{sid}/advance``    move the reveal pointer (monotonic, capped)
- ``POST /sessions/{sid}/decisions``  commit one window (final, timestamped)
- ``POST /sessions/{sid}/complete``   close out a fully-played session
- ``GET  /sessions/{sid}/outcome``    alpha vs twin + DN-5 chain-link
                                      per-window contributions (completed only;
                                      ranked sessions write the leaderboard)

Wall-clock: sanctioned here per DN-6 §8 (server timestamps are research
fields); the engine underneath remains clock-free.

Run locally:  uv run uvicorn ah.serve:app --port 8787
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from ah.core.engine import run_path
from ah.core.institution import decision_months
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    PLAY_ALPHA_VERSION,
    plan_commitments,
    simulate_play,
    validate_commitments,
    window_contributions_play,
)
from ah.store import sessions as session_store
from ah.store.db import connect
from ah.store.runrecords import get_run_record
from ah.store.worlds import get_world


def _resolve_engine(ws: WorldSpec, nw, seed: int):
    """(paths, start_targets, alpha_version) for the world's generator.

    su-gen-03: generated worlds route through the adapter with the generated
    opening book, and their sessions score under a DISTINCT alpha version so
    no leaderboard row can mix engines. Toy worlds are byte-identical to
    before this dispatch existed.
    """
    if ws.engine_defaults.generator_id == "toy-v0":
        return run_path(nw, seed), None, PLAY_ALPHA_VERSION
    from ah.port.adapter import GEN_PLAY_ALPHA_VERSION, GEN_START_TARGETS, run_gen_path

    return run_gen_path(nw, seed), GEN_START_TARGETS, GEN_PLAY_ALPHA_VERSION


_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"


class CreateSession(BaseModel):
    run_id: str
    basis: str = "reported"
    ranked: bool = False
    participant: str | None = None


class Advance(BaseModel):
    to_month: int = Field(ge=0)


class Decide(BaseModel):
    month: int = Field(ge=0)
    action: str
    # sp-02 (E1): per-sleeve commitment points riding along with the action;
    # validated here against the world's own targets before storage.
    commitments: dict[str, float] | None = None
    # DN-6 §8 client telemetry, verbatim passthrough (never used for scoring):
    # time_on_window_ms, basis_toggles, ui_version, ...
    client_log: dict[str, Any] = Field(default_factory=dict)


def create_app(db_path: str | Path = DEFAULT_DB) -> FastAPI:
    app = FastAPI(title="ah session service", version="0.1.0")

    @contextmanager
    def _conn() -> Iterator[sqlite3.Connection]:
        # check_same_thread=False: FastAPI's threadpool may open and use this
        # per-request connection on different worker threads (found live: the
        # browser's first real request 500'd where sequential tests passed).
        conn = connect(db_path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    def db() -> Iterator[sqlite3.Connection]:
        with _conn() as conn:
            yield conn

    def _get(conn: sqlite3.Connection, sid: str) -> dict[str, Any]:
        try:
            return session_store.get_session(conn, sid)
        except session_store.SessionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/sessions", status_code=201)
    def create_session(body: CreateSession, conn: sqlite3.Connection = Depends(db)):
        rec = get_run_record(conn, body.run_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"no run_record {body.run_id}")
        world = get_world(conn, rec["world_id"])
        if world is None:
            raise HTTPException(status_code=404, detail=f"missing world {rec['world_id']}")
        months = WorldSpec.model_validate(world).horizon.quarters * 3
        try:
            return session_store.create_session(
                conn,
                run_id=body.run_id,
                months=months,
                basis=body.basis,
                ranked=body.ranked,
                participant=body.participant,
            )
        except session_store.SessionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _mark_to_market(conn: sqlite3.Connection, doc: dict[str, Any]) -> dict[str, Any]:
        """Attach the book's value AS AT the reveal pointer, and the twin's.

        Computed here rather than in the browser on purpose: the institution
        simulator is the authority for value (W5), and a client-side mirror of
        it would be a second implementation to drift. The app already mirrors
        the TARGET weights, which are simple bookkeeping; value is not.

        Only revealed months are used, so this leaks nothing: it is the same
        simulation the outcome runs, truncated at the pointer.
        """
        revealed = int(doc.get("revealed_months") or 0)
        for key in (
            "value",
            "twin_value",
            "cash",
            "coverage_true",
            "coverage_reported",
            "private_weight_true",
            "calls_paid",
            "distributions_received",
            "spending_paid",
            "forced_sale_total",
        ):
            doc[key] = None
        doc["forced_sales"] = []
        rec = get_run_record(conn, doc["run_id"])
        if rec is None:  # pragma: no cover - FK'd at creation
            return doc
        world = get_world(conn, rec["world_id"])
        if world is None:  # pragma: no cover - FK'd at creation
            return doc
        ws = WorldSpec.model_validate(world)
        # sp-02: the app's lever pre-fill is SERVER-computed — the plan the
        # player would be holding to. Before any quarter closes it is the t0
        # base pace; after, it flexes with the reported weight at the pointer.
        base_targets = None
        if ws.engine_defaults.generator_id != "toy-v0":
            from ah.port.adapter import GEN_START_TARGETS

            base_targets = GEN_START_TARGETS
        doc["next_plan_commitments"] = {
            k: round(v, 4)
            for k, v in plan_commitments(0.0, base_targets, pacing_rule="fixed").items()
        }
        if revealed < 3:  # nothing closes before the first quarter ends
            return doc
        nw = project_numeric(ws)
        paths, targets, _alpha = _resolve_engine(ws, nw, rec["seed"])
        use_reported = doc["basis"] == "reported"
        decisions = {int(m): a for m, a in doc["decisions"].items()}
        active = simulate_play(paths, decisions, use_reported=use_reported, start_targets=targets)
        twin = simulate_play(paths, None, use_reported=use_reported, start_targets=targets)
        # only quarters that have CLOSED inside the revealed window
        q = min(revealed // 3, len(active.quarters)) - 1
        here, twin_here = active.quarters[q], twin.quarters[q]
        doc["value"] = here.nav_reported if use_reported else here.nav_true
        doc["twin_value"] = twin_here.nav_reported if use_reported else twin_here.nav_true
        doc["cash"] = here.cash
        doc["coverage_true"] = here.unfunded_total / here.nav_true if here.nav_true > 0 else None
        doc["coverage_reported"] = (
            here.unfunded_total / here.nav_reported if here.nav_reported > 0 else None
        )
        doc["private_weight_true"] = here.private_weight_true
        doc["calls_paid"] = here.calls_paid
        doc["distributions_received"] = here.distributions_received
        doc["spending_paid"] = here.spending_paid
        doc["forced_sale_total"] = here.forced_sale_total
        doc["forced_sales"] = [e for e in active.sale_log if int(e["period"]) <= q + 1]
        doc["next_plan_commitments"] = {
            k: round(v, 4)
            for k, v in plan_commitments(here.private_weight_reported, targets).items()
        }
        return doc

    @app.get("/sessions/{sid}")
    def get_session(sid: str, conn: sqlite3.Connection = Depends(db)):
        doc = _get(conn, sid)
        doc["decision_windows"] = decision_months(doc["months"])
        return _mark_to_market(conn, doc)

    @app.post("/sessions/{sid}/advance")
    def advance(sid: str, body: Advance, conn: sqlite3.Connection = Depends(db)):
        _get(conn, sid)
        try:
            return _mark_to_market(conn, session_store.advance_reveal(conn, sid, body.to_month))
        except session_store.SessionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/sessions/{sid}/decisions")
    def decide(sid: str, body: Decide, conn: sqlite3.Connection = Depends(db)):
        doc = _get(conn, sid)
        if body.commitments is not None:
            # sp-02: the lever's bounds are checked HERE, against the world's
            # own targets — a bad commit is a 422 at the door, never a 500
            # inside the simulator.
            rec = get_run_record(conn, doc["run_id"])
            assert rec is not None  # FK'd at creation
            world = get_world(conn, rec["world_id"])
            assert world is not None
            ws = WorldSpec.model_validate(world)
            targets = None
            if ws.engine_defaults.generator_id != "toy-v0":
                from ah.port.adapter import GEN_START_TARGETS

                targets = GEN_START_TARGETS
            try:
                validate_commitments(body.commitments, targets)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            return _mark_to_market(
                conn,
                session_store.record_decision(
                    conn,
                    sid,
                    month=body.month,
                    action=body.action,
                    client_log=body.client_log,
                    commitments=body.commitments,
                ),
            )
        except session_store.SessionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/sessions/{sid}/complete")
    def complete(sid: str, conn: sqlite3.Connection = Depends(db)):
        _get(conn, sid)
        try:
            return session_store.complete_session(conn, sid)
        except session_store.SessionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/leaderboard/{world_id}")
    def leaderboard(
        world_id: str,
        seed: int,
        alpha_version: str,
        conn: sqlite3.Connection = Depends(db),
    ):
        """One board per (world, seed, alpha-version) — the triple key is in
        the query, REQUIRED (DN-5 R-1): scores produced under different alpha
        definitions or different histories never share a table. The UNIQUE
        constraint enforces this write-side; this endpoint enforces it
        read-side by refusing to aggregate."""
        rows = conn.execute(
            "SELECT participant, score, created_at FROM leaderboard "
            "WHERE world_id = ? AND seed = ? AND decision_alpha_version = ? "
            "ORDER BY score DESC, created_at ASC",
            (world_id, seed, alpha_version),
        ).fetchall()
        return {
            "world_id": world_id,
            "seed": seed,
            "decision_alpha_version": alpha_version,
            "rows": [dict(r) for r in rows],
        }

    @app.get("/sessions/{sid}/outcome")
    def outcome(sid: str, conn: sqlite3.Connection = Depends(db)):
        doc = _get(conn, sid)
        if doc["status"] != "completed":
            raise HTTPException(
                status_code=409, detail="outcome is available only for completed sessions"
            )
        rec = get_run_record(conn, doc["run_id"])
        assert rec is not None  # FK'd at creation
        world = get_world(conn, rec["world_id"])
        assert world is not None
        ws = WorldSpec.model_validate(world)
        nw = project_numeric(ws)
        paths, targets, alpha_version = _resolve_engine(ws, nw, rec["seed"])
        use_reported = doc["basis"] == "reported"
        decisions = {int(m): a for m, a in doc["decisions"].items()}
        active = simulate_play(paths, decisions, use_reported=use_reported, start_targets=targets)
        twin = simulate_play(paths, None, use_reported=use_reported, start_targets=targets)
        # sp-01: the DRIFT twin (DN-5's fixed nominal schedule) — E7's slot
        # receives its data at last; the difference between these two series
        # across a decade is the vintage-timing argument, drawn not argued.
        drift = simulate_play(
            paths, None, use_reported=use_reported, start_targets=targets, pacing_rule="fixed"
        )
        attribution = window_contributions_play(
            paths, decisions, use_reported=use_reported, start_targets=targets
        )

        alpha = active.final_value - twin.final_value

        if doc["ranked"] and doc["participant"]:
            # One row per (world, seed, alpha-version, participant): a replayed
            # ranked session must not silently overwrite a prior score.
            try:
                conn.execute(
                    "INSERT INTO leaderboard (world_id, seed, decision_alpha_version,"
                    " participant, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        doc["world_id"],
                        rec["seed"],
                        alpha_version,
                        doc["participant"],
                        alpha,
                        doc["updated_at"],
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # score already on the board; first play stands

        return {
            "session_id": sid,
            "basis": doc["basis"],
            "ranked": doc["ranked"],
            "decision_alpha_version": alpha_version,
            "final_value": active.final_value,
            "twin_final_value": twin.final_value,
            "alpha": alpha,
            # E7 (DN-5 R-1): THREE series by contract — the drift twin's slot
            # exists before its data, so its arrival is a data change, not an
            # interface change. One point per CLOSED quarter, on the twin's
            # own cadence (nav_reported/nav_true per the session's basis).
            "series": {
                "active": [
                    round(float(q.nav_reported if use_reported else q.nav_true), 4)
                    for q in active.quarters
                ],
                "twin": [
                    round(float(q.nav_reported if use_reported else q.nav_true), 4)
                    for q in twin.quarters
                ],
                "drift_twin": [
                    round(float(q.nav_reported if use_reported else q.nav_true), 4)
                    for q in drift.quarters
                ],
            },
            "windows": [
                {"month": m, "action": a, "contribution": c}
                for m, a, c in zip(
                    attribution.months,
                    attribution.actions,
                    attribution.contributions,
                    strict=True,
                )
            ],
            "window_contributions": list(attribution.contributions),
            "forced_secondaries": active.forced_secondaries,
        }

    return app


app = create_app()
