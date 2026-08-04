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
from ah.core.institution import decision_months, simulate_institution
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.density import window_contributions
from ah.store import sessions as session_store
from ah.store.db import connect
from ah.store.runrecords import get_run_record
from ah.store.worlds import get_world

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"

# DN-5's board key includes the alpha definition; runs stamped before the
# retrofit carry NULL, so ranked outcomes computed by THIS module declare the
# definition they actually used.
_ALPHA_VERSION_FALLBACK = "dn5-v0.2-chainlink"


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
    # DN-6 §8 client telemetry, verbatim passthrough (never used for scoring):
    # time_on_window_ms, basis_toggles, ui_version, ...
    client_log: dict[str, Any] = Field(default_factory=dict)


def create_app(db_path: str | Path = DEFAULT_DB) -> FastAPI:
    app = FastAPI(title="ah session service", version="0.1.0")

    @contextmanager
    def _conn() -> Iterator[sqlite3.Connection]:
        conn = connect(db_path)
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

    @app.get("/sessions/{sid}")
    def get_session(sid: str, conn: sqlite3.Connection = Depends(db)):
        doc = _get(conn, sid)
        doc["decision_windows"] = decision_months(doc["months"])
        return doc

    @app.post("/sessions/{sid}/advance")
    def advance(sid: str, body: Advance, conn: sqlite3.Connection = Depends(db)):
        _get(conn, sid)
        try:
            return session_store.advance_reveal(conn, sid, body.to_month)
        except session_store.SessionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/sessions/{sid}/decisions")
    def decide(sid: str, body: Decide, conn: sqlite3.Connection = Depends(db)):
        _get(conn, sid)
        try:
            return session_store.record_decision(
                conn, sid, month=body.month, action=body.action, client_log=body.client_log
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
        nw = project_numeric(WorldSpec.model_validate(world))
        paths = run_path(nw, rec["seed"])
        use_reported = doc["basis"] == "reported"
        decisions = {int(m): a for m, a in doc["decisions"].items()}
        active = simulate_institution(paths, decisions, use_reported=use_reported)
        twin = simulate_institution(paths, None, use_reported=use_reported)
        attribution = window_contributions(paths, decisions, use_reported=use_reported)

        alpha = active.final_value - twin.final_value
        alpha_version = rec.get("decision_alpha_version") or _ALPHA_VERSION_FALLBACK

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
            # interface change.
            "series": {
                "active": [round(float(v), 4) for v in active.total],
                "twin": [round(float(v), 4) for v in twin.total],
                "drift_twin": None,
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
        }

    return app


app = create_app()
