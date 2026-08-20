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

import json
import sqlite3
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ah.cioview import PLANES, WATCH_FRACTION, build_cio_view
from ah.core.engine import run_path
from ah.core.institution import decision_months
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    _ANNUAL_COMMITMENT_RATE,
    COMMIT_CAP_MULTIPLE,
    PLAY_ALPHA_VERSION,
    PRIVATE_ASSETS,
    START_CASH,
    START_TARGETS,
    PlayQuarter,
    book_commitment_plan,
    default_commitment_plan,
    default_opening_book,
    plan_commitments,
    simulate_play,
    validate_commitments,
    window_contributions_play,
)
from ah.port.book import BookError, CommitmentPlan, OpeningBook, validate_book, validate_plan
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


def _build_bundle_bytes(conn: sqlite3.Connection, run_id: str) -> bytes:
    """The exact compressed bytes ``ah bundle`` would write for this run.

    Reuses ``ah.bundle.build_bundle`` + ``ah.bundle.write_bundle`` verbatim —
    not a reimplementation — so served bytes are byte-identical to the CLI
    path (sib-01). ``write_bundle`` only knows how to write to a path, so a
    TemporaryDirectory stands in for an in-memory buffer; cleanup is best-
    effort (Windows can leave a sqlite-adjacent handle open past the `with`,
    per the same quirk noted in ``scripts/gen_bundle_fixtures.py``).
    """
    from ah.bundle import build_bundle, write_bundle

    doc = build_bundle(conn, run_id)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        target = Path(tmp) / "bundle.gz"
        write_bundle(doc, target)
        return target.read_bytes()


def _world_sleeves(
    conn: sqlite3.Connection, run_id: str
) -> tuple[dict[str, float], tuple[str, ...], int]:
    """The world behind ``run_id``: its default targets, liquid sleeve set and
    horizon in months — the inputs both the default book and a book-derived
    plan recompute (app-open-03) resolve against."""
    rec = get_run_record(conn, run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no run_record {run_id}")
    world = get_world(conn, rec["world_id"])
    if world is None:  # pragma: no cover - FK'd at creation
        raise HTTPException(status_code=404, detail=f"missing world {rec['world_id']}")
    ws = WorldSpec.model_validate(world)
    targets = dict(START_TARGETS)
    if ws.engine_defaults.generator_id != "toy-v0":
        from ah.port.adapter import GEN_START_TARGETS

        targets = dict(GEN_START_TARGETS)
    liquid = tuple(a for a in targets if a not in PRIVATE_ASSETS)
    return targets, liquid, ws.horizon.quarters * 3


def _world_book(
    conn: sqlite3.Connection, run_id: str
) -> tuple[OpeningBook, CommitmentPlan, tuple[str, ...]]:
    """The derived default for the world behind ``run_id``, and its sleeve set."""
    targets, liquid, months = _world_sleeves(conn, run_id)
    # the plan carries ONE ENTRY PER DECISION WINDOW, not a fixed ten years —
    # default_commitment_plan's own docstring names this exact call for a
    # non-decade horizon. Getting it wrong here means the server's own
    # default 422s when POSTed straight back (all nine shipped presets are
    # 40 quarters, so this was previously invisible).
    plan = default_commitment_plan(targets, windows=len(decision_months(months)))
    return default_opening_book(targets), plan, liquid


def _policy_basis(
    book: OpeningBook | None, world_targets: Mapping[str, float] | None
) -> tuple[dict[str, float], float]:
    """The POLICY basis this session paces and caps against, and its cash.

    su-app-07 task 2. There are FOUR places on this service that need the
    same answer — ``validate_plan`` at kickoff, the decision door's
    ``validate_commitments``, and the two ``plan_commitments`` pre-fills —
    and su-app-06's worst defect (C1) was a plan the service displayed and
    the engine never applied. One function, so they cannot drift apart, and
    so the served pre-fill agrees with the multiplier ``simulate_play``
    computes for itself from ``OpeningBook.effective_targets()``.

    Targets and cash are returned together on purpose: the pacing
    denominator is ``sum(targets) + cash`` (Ruling C), so a caller that took
    one from the book and the other from the world default would produce a
    number neither of them means.

    ``world_targets`` is the engine's own default (``None`` for toy-v0,
    ``GEN_START_TARGETS`` for a generated world) and is used only when the
    session carries no book at all.
    """
    if book is not None:
        return book.effective_targets(), book.cash
    return (dict(world_targets) if world_targets is not None else dict(START_TARGETS)), START_CASH


def _alert_level(weight: float, target: float, lo: float, hi: float) -> str:
    """One sleeve's band status: ``"ok" | "watch" | "breach"``.

    The ``AlertLevel`` union declared at ``app/src/lib/cioView.ts:30-37``, and
    a generalisation of the dashboard's own fallback rule
    (``app/src/components/CioDashboard.tsx``'s ``alertLevel``) to an
    ASYMMETRIC band. That rule assumes the band is a symmetric half-width
    around the target and compares ``|current - target|`` to it; an entered
    range is ``[lo, hi]`` and need not be centred on the target at all. The
    meaning is unchanged: amber once the weight has used up ``WATCH_FRACTION``
    of the room its target leaves it on the edge it is approaching.

    ``WATCH_FRACTION`` is imported from ``ah.cioview`` (DN-8 section 3) rather
    than redeclared — a second copy of a display threshold is exactly the
    drift this work package exists to remove.

    **The target may sit OUTSIDE its own band.** Spec section 3 supports an
    institution holding a policy it is currently out of compliance with, and
    ``validate_book`` returns a warning string rather than refusing. The
    first version of this function picked ONE edge with
    ``room = (hi - target) if weight >= target else (target - lo)``, which
    inverts under that shape: with ``target > hi`` every in-band weight takes
    the ``else`` branch, so the room was measured to ``lo`` no matter which
    edge the weight was actually approaching. Probed at ``lo=10, hi=20,
    target=30`` it reported a mid-band 15.0 as ``watch`` and a 20.0 sitting
    exactly on the edge it was about to breach as ``ok`` — backwards on both.

    So: clamp the target into its own band, then test BOTH edges and take the
    more severe (both branches yield ``watch``, so the first hit returns).
    Written as the REMAINING margin — "within ``1 - WATCH_FRACTION`` of the
    way from ``t`` to this edge" — which is algebraically identical to
    ``dist >= WATCH_FRACTION * room`` for a target strictly inside its band,
    so nothing about the ordinary case moves.

    Degenerate cases, decided rather than fallen into:

    * ``t == hi`` (the target is at or above the ceiling): that edge's room
      is zero, so its watch zone collapses to the edge itself and only a
      weight exactly on ``hi`` is amber from that side. The LOWER zone is
      unaffected and still fires normally — where the old ``room > 0.0``
      guard suppressed the whole watch zone for this shape. Nothing divides
      by the room, so the collapse needs no special case.
    * ``t == lo``: the mirror image.
    * ``lo == t == hi`` is unreachable (``validate_book`` enforces
      ``lo < hi``); it would still be well defined here — a weight can only
      be that one value, and it reports ``watch``.
    * A weight exactly ON an edge is ``watch``, never ``ok``: it is as close
      to breaching as an in-band weight can get. This is also what the old
      single-edge form already returned for a target strictly inside, so the
      edge case is preserved rather than newly invented.

    Breach detection is untouched — it was correct in every probed case.
    """
    if weight < lo or weight > hi:
        return "breach"
    t = min(max(target, lo), hi)
    margin = 1.0 - WATCH_FRACTION
    if (hi - weight) <= margin * (hi - t):
        return "watch"
    if (weight - lo) <= margin * (t - lo):
        return "watch"
    return "ok"


def _band_report(
    book: OpeningBook | None,
    here: PlayQuarter,
    asset_order: Sequence[str],
) -> dict[str, Any] | None:
    """su-app-07 task 3: per-sleeve band status at the last CLOSED quarter.

    A READ of state ``simulate_play`` already recorded — ``liquid_values``,
    ``private_true``/``private_reported``, ``nav_true``/``nav_reported`` —
    and nothing more. Ranges are INERT by design: they are never handed to
    ``simulate_play`` or ``_build_portfolio``, so declaring a band cannot
    move a number in the decade. The test that pins this
    (``test_ranges_do_not_move_a_single_number``) is the load-bearing one.

    Units are POINTS out of 100 on both sides: an entered range and
    ``effective_targets()`` are already in points, so a weight is the
    sleeve's value over THAT PLANE'S NAV times 100. The denominator is the
    served ``nav_true`` / ``nav_reported``; ``cash + sum(liquid_values) +
    sum(private_*)`` reproduces it to 1e-9 (pinned by
    ``tests/test_cioview.py::test_per_asset_values_close_against_the_book``),
    so there is no residual to name.

    **``alert`` is AUTHORITATIVE and must not be recomputed client-side**
    (DN-3 W5: the server is the authority for value and scoring, and a band
    status is a judgement about value). It is computed on the UNROUNDED
    weight and target while the numbers served beside it are rounded to 4
    decimals, so a client re-running the rule on the served numbers can
    legitimately disagree within ~5e-5 of an edge. Render the ``alert`` this
    endpoint gives you; never derive it.

    ``None`` when there is no book, no ranges on it, or no closed quarter —
    the caller supplies the last of those by only calling here once a
    quarter has closed.

    Sleeve order is the world's own: liquid in ``paths.asset_order`` order,
    then the private sleeves in ``PRIVATE_ASSETS`` order. A sleeve with no
    declared range is absent from the list entirely rather than present with
    nulls, so the app never has to distinguish "no band" from "band unmet".
    """
    if book is None or not book.ranges:
        return None
    targets = book.effective_targets()
    order = [a for a in asset_order if a not in PRIVATE_ASSETS] + list(PRIVATE_ASSETS)
    sleeves: list[dict[str, Any]] = []
    for sleeve in order:
        band = book.ranges.get(sleeve)
        if band is None:
            continue
        lo, hi = float(band[0]), float(band[1])
        # every sleeve a range may name is in `effective_targets()`:
        # `validate_book` refuses a range outside the world's sleeve set and
        # both branches of `effective_targets()` cover that set exactly.
        target = float(targets[sleeve])
        entry: dict[str, Any] = {
            "sleeve": sleeve,
            "target": round(target, 4),
            "lo": round(lo, 4),
            "hi": round(hi, 4),
        }
        for plane, nav, private in (
            ("true", here.nav_true, here.private_true),
            ("reported", here.nav_reported, here.private_reported),
        ):
            value = private[sleeve] if sleeve in PRIVATE_ASSETS else here.liquid_values[sleeve]
            # a wiped plan reads as zero weight, which breaches any band with
            # a positive floor. That is the honest reading, not a guard.
            weight = (float(value) / float(nav) * 100.0) if nav > 0.0 else 0.0
            entry[plane] = {
                "weight": round(weight, 4),
                "alert": _alert_level(weight, target, lo, hi),
            }
        sleeves.append(entry)
    return {"watch_fraction": WATCH_FRACTION, "sleeves": sleeves}


def _window_ordinal(months: int, month: int) -> int | None:
    """The plan index a DECISION MONTH names, or None if it names no window.

    ``CommitmentPlan`` carries one entry per decision window (spec section 3):
    index ``k`` is the k-th window and drives the engine's vintage year
    ``k + 1``. ``decision_months`` is the one definition of that ordering, so
    the index is read off it rather than re-derived from arithmetic.
    """
    windows = decision_months(months)
    return windows.index(month) if month in windows else None


def _plan_window(doc: dict[str, Any], entries: int) -> int:
    """The plan index the lever is PRE-FILLING for: the next undecided window.

    Deliberately not derived from the reveal pointer's quarter. The old
    ``(quarter + 1) // 4`` was only correct when the pointer sat exactly on
    the window's own month; ``record_decision`` refuses a window until
    ``revealed_months >= month + 1`` and ``Play.tsx`` opens the lever on
    exactly that state, so at window 0 the real pointer is month 12, the last
    closed quarter is 3, and the formula returned 1 — next year's number,
    beside a commit of this year's. The window ordinal is a property of the
    window, so it is taken from the window (same source as ``decide()``'s fill
    below, which uses the decision's own month).

    Clamped to the stored plan's length for a non-decade horizon, and for the
    fully-decided session that has no next window.
    """
    windows = decision_months(doc["months"])
    undecided = [m for m in windows if str(m) not in doc["decisions"]]
    index = windows.index(undecided[0]) if undecided else len(windows) - 1
    return max(0, min(index, entries - 1))


_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = _REPO_ROOT / "data" / "ah.db"


class CreateSession(BaseModel):
    run_id: str
    basis: str = "reported"
    ranked: bool = False
    participant: str | None = None
    # su-app-06: an entered book and kickoff plan. Absent = the derived
    # default, which is every session that existed before this.
    book: OpeningBook | None = None
    plan: CommitmentPlan | None = None


class BookPlanRequest(BaseModel):
    """app-open-03: the entry screen's current (edited) book, posted whole so
    the SERVER derives the plan for it — the client never grows plan math."""

    run_id: str
    book: OpeningBook


class Advance(BaseModel):
    to_month: int = Field(ge=0)


# narr-02 (DN-9 N-af): the rationale tag enum, frozen in the task and
# extensible only by a version bump (rationale_schema_version) -- never in
# place. Do not derive tags from free_text; do not add tags here without a
# bump.
RationaleTag = Literal[
    "valuation",
    "liquidity",
    "policy_outlook",
    "peer_positioning",
    "risk_reduction",
    "risk_addition",
    "rebalancing_discipline",
    "pacing",
    "governance",
    "other",
]


class Rationale(BaseModel):
    """The player's stated reason for one window's decision (narr-02).

    Optional at every level -- a bare ``{}`` is valid (the player opened the
    box and said nothing). ``free_text`` is stored verbatim, never parsed,
    never scored, and never served on any surface another player can see
    (only the session's own owner, via GET /sessions/{sid} and its own
    outcome). ``tags`` is the closed enum above, at most 3, rejected (not
    coerced or dropped) if any tag falls outside it -- FastAPI/pydantic give
    the 422 for both constraints without custom validation code.
    """

    free_text: str | None = Field(default=None, max_length=600)
    tags: list[RationaleTag] | None = Field(default=None, max_length=3)


class Decide(BaseModel):
    month: int = Field(ge=0)
    action: str
    # sp-02 (E1): per-sleeve commitment points riding along with the action;
    # validated here against the world's own targets before storage.
    commitments: dict[str, float] | None = None
    # DN-6 §8 client telemetry, verbatim passthrough (never used for scoring):
    # time_on_window_ms, basis_toggles, ui_version, ...
    client_log: dict[str, Any] = Field(default_factory=dict)
    # narr-02: optional, null-valid; never reaches simulate_play (see
    # ah.store.sessions.record_decision's docstring).
    rationale: Rationale | None = None


def create_app(db_path: str | Path = DEFAULT_DB) -> FastAPI:
    app = FastAPI(title="ah session service", version="0.1.0")
    # sib-01: bundles are immutable per run_id, so this cache is never
    # invalidated — one entry per run, for the app's lifetime (dict[str, bytes]).
    app.state.bundle_cache = {}

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

    @app.get("/worlds")
    def list_worlds(conn: sqlite3.Connection = Depends(db)):
        """sib-01: the decade picker's data — distinct worlds from the store,
        each with its runs newest-first. No filtering by engine: toy and
        generated worlds are both listed exactly as the store holds them."""
        world_rows = conn.execute("SELECT world_id, json FROM worlds").fetchall()
        run_rows = conn.execute(
            "SELECT run_id, world_id, seed, created_at FROM run_records "
            "ORDER BY created_at DESC, run_id DESC"
        ).fetchall()
        runs_by_world: dict[str, list[dict[str, Any]]] = {}
        for r in run_rows:
            runs_by_world.setdefault(r["world_id"], []).append(
                {"run_id": r["run_id"], "seed": r["seed"], "created_at": r["created_at"]}
            )
        worlds = []
        for row in world_rows:
            doc = json.loads(row["json"])
            narrative = doc.get("narrative") or {}
            engine_defaults = doc.get("engine_defaults") or {}
            worlds.append(
                {
                    "world_id": row["world_id"],
                    "title": narrative.get("title"),
                    "generator_id": engine_defaults.get("generator_id"),
                    "runs": runs_by_world.get(row["world_id"], []),
                }
            )
        return {"worlds": worlds}

    @app.get("/book/default")
    def default_book(run_id: str, conn: sqlite3.Connection = Depends(db)):
        """su-app-06: the pre-fill the entry screen opens with — today's
        derived book and the flat fixed-rule plan, for THIS world's sleeve
        set. Built by the engine's own code, never a second implementation.

        Branch-review I2 (app-open-02): also carries ``plan_cap`` — the exact
        constants ``ah.port.book.validate_plan`` computes its per-window cap
        from (``cap = multiple * target * annual_rate``). This is additive:
        the entry screen mirrors ``validate_plan``'s arithmetic client-side
        (a pre-flight fault when a lowered target makes the SERVED plan
        exceed the cap it would be validated against at ``POST /sessions``),
        and must use these SAME values rather than re-derive its own copy of
        them — a server test pins that they equal ``ah.play``'s constants,
        so there is one source of truth, not two that can drift.
        """
        book, plan, liquid = _world_book(conn, run_id)
        return {
            "book": book.model_dump(),
            "plan": plan.model_dump(),
            "liquid_sleeves": list(liquid),
            "book_digest": book.digest(),
            "plan_digest": plan.digest(),
            "plan_cap": {"multiple": COMMIT_CAP_MULTIPLE, "annual_rate": _ANNUAL_COMMITMENT_RATE},
        }

    @app.get("/book/ladder")
    def rebuild_ladder(
        run_id: str, sleeve: str, value: float, conn: sqlite3.Connection = Depends(db)
    ):
        """app-open-02: rebuild ONE private sleeve's vintage ladder to sum to
        a NEW total value, so the entry screen can offer "set a value"
        instead of hand-editing rungs into shapes the pacing model was never
        fitted on (``ah.port.cashflow_tier1``).

        Built by ``ah.play._seed_ladder`` with ``value`` in place of the
        target points -- the SAME builder ``default_opening_book`` calls for
        the served default -- never a second implementation. The rung
        documents are ``ClosedEndCohort.to_document()``, exactly the shape
        ``/book/default`` serves under ``book.private[sleeve]``.
        """
        if get_run_record(conn, run_id) is None:
            raise HTTPException(status_code=404, detail=f"no run_record {run_id}")
        if sleeve not in PRIVATE_ASSETS:
            raise HTTPException(
                status_code=422,
                detail=f"sleeve must be one of {sorted(PRIVATE_ASSETS)}, got {sleeve!r}",
            )
        if value <= 0.0:
            raise HTTPException(status_code=422, detail=f"value must be > 0, got {value}")

        from ah.play import _doc, _seed_ladder

        base = _doc("closed-end-cohort.example.json")
        rungs = _seed_ladder(base, sleeve, value)
        return {"rungs": [c.to_document() for c in rungs]}

    @app.post("/book/plan")
    def plan_for_book(body: BookPlanRequest, conn: sqlite3.Connection = Depends(db)):
        """app-open-03: the commitment plan the server derives for the CURRENT
        (edited) book — targets, values and vintage ladders as they stand on
        the entry screen, not as they were served.

        The owner's report: "any changes to the weights and/or historical
        commitments need to be reflected in the commitment plan". The entry
        screen re-posts the book here after every edit and replaces its plan
        grid with the answer; the derivation itself
        (``ah.play.book_commitment_plan`` — the fixed default window rule
        with DN-5's policy flex evaluated at the book's own opening reported
        private weight) lives server-side because the server is the authority
        for the plan the session will be validated and played against
        (DN-3 W5). The posted book is validated with ``validate_book`` — the
        same door ``POST /sessions`` uses — so the plan is only ever derived
        for a book that could actually be played, and the refusal message is
        the same one the player would meet later.
        """
        _targets, liquid, months = _world_sleeves(conn, body.run_id)
        try:
            validate_book(body.book, liquid)  # band warnings don't gate a plan
        except BookError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        plan = book_commitment_plan(body.book, windows=len(decision_months(months)))
        return {"plan": plan.model_dump(), "plan_digest": plan.digest()}

    @app.get("/runs/{run_id}/bundle")
    def get_bundle(run_id: str, conn: sqlite3.Connection = Depends(db)):
        """sib-01: served bytes are byte-identical to ``ah bundle`` — same
        builder, cached per run_id since a RunRecord's bundle never changes."""
        cache: dict[str, bytes] = app.state.bundle_cache
        if run_id not in cache:
            if get_run_record(conn, run_id) is None:
                raise HTTPException(status_code=404, detail=f"no run_record {run_id}")
            cache[run_id] = _build_bundle_bytes(conn, run_id)
        return Response(content=cache[run_id], media_type="application/gzip")

    @app.post("/sessions", status_code=201)
    def create_session(body: CreateSession, conn: sqlite3.Connection = Depends(db)):
        """Create a session against the world's derived default book/plan, or
        an entered one.

        ER-15, ANNOUNCED (D-ER14-2, 2026-08-18): the ER-14 close-out gave the
        default opening book a fourth private sleeve (infra), so
        `default_opening_book`'s digest moved under every world -- any
        session created before this release (or any client still POSTing a
        stored three-sleeve book) no longer matches the served default.
        `OpeningBook`/`CommitmentPlan`'s own shape check (`set(book.private)
        == set(PRIVATE_SLEEVES)`) refuses a book that cannot name the
        world's full private set, so a legacy three-sleeve book 422s here
        rather than being silently accepted and demoted to practice -- a
        plan that cannot name the world's sleeves is malformed, not merely
        edited. This is a correct, accepted side effect of the fourth
        sleeve landing, not a defect; see CHANGELOG.md's ER-14 close-out
        entry.
        """
        rec = get_run_record(conn, body.run_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"no run_record {body.run_id}")
        world = get_world(conn, rec["world_id"])
        if world is None:
            raise HTTPException(status_code=404, detail=f"missing world {rec['world_id']}")
        months = WorldSpec.model_validate(world).horizon.quarters * 3

        default_book_, default_plan_, liquid = _world_book(conn, body.run_id)
        ranked = body.ranked
        book_json = plan_json = None
        if body.book is not None or body.plan is not None:
            book = body.book or default_book_
            plan = body.plan or default_plan_
            try:
                validate_book(book, liquid_sleeves=liquid)
                # su-app-07: the cap is measured against the book's POLICY
                # targets, not the NAV it happens to open at — an institution
                # holding 20 points of pe against a 30-point target paces
                # toward the 30. Same basis as the decision door below and as
                # `simulate_play`'s own check.
                #
                # `_policy_basis` is deliberately NOT used here: `book` is
                # `body.book or default_book_` and so is never None at this
                # site, which left the call passing a dummy `None` world
                # default. Harmless while the branch cannot admit `book is
                # None`, but if it ever did, a GENERATED world would fall
                # through to `START_TARGETS` instead of `GEN_START_TARGETS`
                # and cap a whole class of worlds wrongly, in silence. There
                # is no fallback to resolve here, so the single resolver
                # `effective_targets()` is called directly.
                validate_plan(plan, book.effective_targets())
            except BookError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            # CommitmentPlan._shape only checks the three sleeves AGREE in
            # length, not what that length should be against THIS world's
            # horizon — task 6 indexes into this stored plan by window
            # ordinal, so a wrong count must be refused here, at the boundary.
            expected = len(decision_months(months))
            for sleeve, years in plan.points.items():
                if len(years) != expected:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"plan {sleeve} has {len(years)} entries, expected {expected} "
                            "(one per decision window)"
                        ),
                    )
            # section 2: a custom book is PRACTICE ONLY. Enforced here, on the
            # authority, not in the app.
            if book.digest() != default_book_.digest() or plan.digest() != default_plan_.digest():
                ranked = False
            book_json = book.model_dump_json()
            plan_json = plan.model_dump_json()

        try:
            return session_store.create_session(
                conn,
                run_id=body.run_id,
                months=months,
                basis=body.basis,
                ranked=ranked,
                participant=body.participant,
                opening_book=book_json,
                commitment_plan=plan_json,
            )
        except session_store.SessionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _stored_opening_book(doc: dict[str, Any]) -> OpeningBook | None:
        """The session's entered book, or ``None`` for the derived default —
        su-app-06's single deserialization point, shared by every replay
        surface (`_mark_to_market`, `/outcome`, `/cio`) so a session's book
        is decoded the same way everywhere it is read back."""
        stored = doc.get("opening_book")
        return OpeningBook.model_validate_json(stored) if stored else None

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
            "expired_undrawn",
            "expired_undrawn_to_date",
            "spending_basis",
            "spending_rate_annual",
            "private_weight_reported",
            "next_plan_basis",
            "plan_pace",
            # su-app-07 task 3: always a KEY on the document, null until a
            # quarter has closed on a session whose book declares ranges —
            # a key that appears only after month 3 is a shape the app would
            # have to sniff for.
            "band_report",
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
        # su-app-06: the SAME stored book (or None for the derived default)
        # goes to both the active session and the twin — alpha must still
        # isolate decisions, not differences in opening state. Read here
        # rather than below the early return because su-app-07's pre-fill
        # needs the book's POLICY targets before any quarter has closed.
        book = _stored_opening_book(doc)
        policy_targets, policy_cash = _policy_basis(book, base_targets)
        doc["next_plan_commitments"] = {
            k: round(v, 4)
            for k, v in plan_commitments(
                0.0, policy_targets, pacing_rule="fixed", cash=policy_cash
            ).items()
        }
        if revealed < 3:  # nothing closes before the first quarter ends
            return doc
        nw = project_numeric(ws)
        paths, targets, _alpha = _resolve_engine(ws, nw, rec["seed"])
        use_reported = doc["basis"] == "reported"
        decisions = {int(m): a for m, a in doc["decisions"].items()}
        active = simulate_play(
            paths, decisions, use_reported=use_reported, start_targets=targets, opening_book=book
        )
        twin = simulate_play(
            paths, None, use_reported=use_reported, start_targets=targets, opening_book=book
        )
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
        # ER-6's visible lapse (audit F2): undrawn commitment CANCELLED at the
        # end of a cohort's life — it leaves the unfunded balance without a
        # call. It fires in one quarter of a decade, so the running total is
        # what keeps it visible after the quarter it happened in.
        doc["expired_undrawn"] = here.expired_undrawn
        doc["expired_undrawn_to_date"] = sum(
            active.quarters[i].expired_undrawn for i in range(q + 1)
        )
        doc["forced_sales"] = [e for e in active.sale_log if int(e["period"]) <= q + 1]
        # audit F4: spending is charged on a mean sampled INSIDE the waterfall,
        # so quarter-end nav_reported cannot reproduce it. Serve the basis and
        # the rate, and the charge closes on the surface that makes it.
        doc["spending_basis"] = here.spending_basis
        doc["spending_rate_annual"] = here.spending_rate_annual
        doc["private_weight_reported"] = here.private_weight_reported
        # su-app-07 task 3: reporting only. Computed from `here` — state the
        # replay above already produced — and fed to nothing.
        doc["band_report"] = _band_report(book, here, paths.asset_order)
        # su-app-07: the SAME basis `simulate_play` paces off (the book's
        # policy targets and its own cash), so the number the lever shows and
        # the number the engine commits are one number, not two.
        doc["next_plan_commitments"] = {
            k: round(v, 4)
            for k, v in plan_commitments(
                here.private_weight_reported, policy_targets, cash=policy_cash
            ).items()
        }
        # audit F4: the pre-fill is the plan AT THE LAST CLOSED QUARTER. The
        # engine commits on the weight at the commitment quarter — one quarter
        # later, up to 7.9% different — and that quarter's returns are
        # unrevealed here, so an exact pre-fill would leak the tape. It is
        # therefore DECLARED rather than silently approximate. An untouched
        # lever still commits the exact plan: the app sends no commitments and
        # the simulator recomputes.
        doc["next_plan_basis"] = {
            "as_of_quarter": here.quarter,
            "as_of_month": here.month,
            "private_weight_reported": here.private_weight_reported,
        }
        # su-app-06 section 4.3: with a stored plan the pre-fill is the
        # player's OWN number for this year - exact, so the audit-F4
        # staleness caveat does not apply - and the pacing rule's view rides
        # alongside as a comparison rather than acting as a silent default.
        # A session with no plan keeps today's behaviour verbatim.
        stored_plan = doc.get("commitment_plan")
        if stored_plan:
            plan = CommitmentPlan.model_validate_json(stored_plan)
            window = _plan_window(doc, len(next(iter(plan.points.values()))))
            doc["plan_pace"] = doc["next_plan_commitments"]
            doc["next_plan_commitments"] = {
                sleeve: round(points[window], 4) for sleeve, points in plan.points.items()
            }
            doc["next_plan_basis"] = None  # nothing is being approximated
        # sp-05 (E1's last gaps): the ladder by age and the trailing
        # distribution series, visible at the moment of decision.
        doc["vintage_nav"] = {k: round(float(v), 4) for k, v in here.vintage_nav.items()}
        doc["trailing_distributions"] = [
            round(float(active.quarters[i].distributions_received), 4)
            for i in range(max(0, q - 3), q + 1)
        ]
        return doc

    @app.get("/sessions/{sid}")
    def get_session(sid: str, conn: sqlite3.Connection = Depends(db)):
        doc = _get(conn, sid)
        doc["decision_windows"] = decision_months(doc["months"])
        return _mark_to_market(conn, doc)

    @app.get("/sessions/{sid}/cio")
    def cio_view(
        sid: str,
        plane: str = "reported",
        forecast_quarters: int = 4,
        conn: sqlite3.Connection = Depends(db),
    ):
        """cio-01: the CIO dashboard's payload — DN-8's CioView, built
        server-side from the same truncated replay `_mark_to_market` uses.
        The renderer computes nothing; plane change is a refetch."""
        if plane not in PLANES:
            raise HTTPException(status_code=422, detail=f"plane must be one of {PLANES}")
        if not 0 <= forecast_quarters <= 8:
            raise HTTPException(status_code=422, detail="forecast_quarters must be 0..8")
        doc = _get(conn, sid)
        revealed = int(doc.get("revealed_months") or 0)
        # app-open-01 (cio-05): revealed == 0 is the CIO's new front door — the
        # state right after the opening book is confirmed, before the player
        # has advanced at all. `build_cio_view` now serves that (populated
        # from the opening book + the inherited prehistory). 1 or 2 months
        # revealed is still mid-quarter with nothing closed, and stays a 409.
        if 0 < revealed < 3:
            raise HTTPException(status_code=409, detail="no closed quarter yet")
        rec = get_run_record(conn, doc["run_id"])
        assert rec is not None  # FK'd at creation
        world = get_world(conn, rec["world_id"])
        assert world is not None
        ws = WorldSpec.model_validate(world)
        nw = project_numeric(ws)
        paths, targets, alpha_version = _resolve_engine(ws, nw, rec["seed"])
        decisions = {int(m): a for m, a in doc["decisions"].items()}
        resolved = rec.get("resolved_engine") or {}
        # su-app-06: this is a LIVE surface, not just an endgame one — a
        # player on a custom book must see a dashboard for that book at
        # every reveal, matching the header's own value (task 5b).
        book = _stored_opening_book(doc)
        return build_cio_view(
            paths,
            decisions,
            run_id=doc["run_id"],
            seed=rec["seed"],
            world_title=str((world.get("narrative") or {}).get("title") or doc["run_id"]),
            world_version=str(resolved.get("generator_version") or ""),
            alpha_version=alpha_version,
            start_targets=targets,
            plane=plane,
            revealed_months=revealed,
            forecast_quarters=forecast_quarters,
            # cio-04: the inherited decade is always built by running the toy
            # engine internally, regardless of which engine produced `paths` —
            # splicing it onto a generated (non-toy-v0) world would stitch two
            # engines into one chart, so generated worlds opt out here.
            prehistory=(ws.engine_defaults.generator_id == "toy-v0"),
            opening_book=book,
        )

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
        commitments = body.commitments
        # su-app-06 section 4.3, and the fix for it: on a PLAN-CARRYING
        # session an untouched lever commits the plan's number for this
        # window, exactly. The client sends only the sleeves the player
        # edited (audit F4), so the sleeves it omits are filled here — on the
        # authority (DN-3 W5), not in the browser, or a scripted client would
        # keep the old silent behaviour. Without this the stored plan reached
        # the display and stopped: `simulate_play` fell through to the policy
        # pacing rule and committed a number the window never showed.
        #
        # The window is identified by the DECISION'S OWN MONTH, not by a
        # quarter pointer: `body.month` names the window exactly and the
        # pointer does not (see `_plan_window`). A month that names no window
        # is left alone — `record_decision` is the one place that refuses it.
        stored_plan = doc.get("commitment_plan")
        if stored_plan:
            plan = CommitmentPlan.model_validate_json(stored_plan)
            window = _window_ordinal(doc["months"], body.month)
            if window is not None:
                filled = dict(commitments or {})
                for sleeve, points in plan.points.items():
                    if sleeve not in filled and window < len(points):
                        filled[sleeve] = float(points[window])
                commitments = filled
        if commitments is not None:
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
            # su-app-06 (I1), re-based by su-app-07: `validate_plan` caps a
            # plan entry against the entered book's POLICY targets, so an
            # analyst targeting 30 points of pe may legally store 10.8 for a
            # window. Capping the same quantity here against a different
            # basis would have the server refuse a number it filled in
            # itself. The bound is re-based, never removed, and sessions with
            # no book are untouched — one helper, so the four sites that need
            # this answer cannot drift apart.
            targets = _policy_basis(_stored_opening_book(doc), targets)[0]
            try:
                validate_commitments(commitments, targets)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        # narr-02: pass the already-validated rationale through as a plain
        # dict (or None) -- the store layer stores it verbatim plus its own
        # server-clock recorded_at, never touching `decisions`.
        rationale = (
            None
            if body.rationale is None
            else {"free_text": body.rationale.free_text, "tags": body.rationale.tags}
        )
        try:
            return _mark_to_market(
                conn,
                session_store.record_decision(
                    conn,
                    sid,
                    month=body.month,
                    action=body.action,
                    client_log=body.client_log,
                    commitments=commitments,
                    rationale=rationale,
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
        # su-app-06: the SAME stored book (or None for the derived default)
        # goes to every replay below — active, twin, drift twin, the
        # per-window attribution and the annotations — so the endgame
        # verdict describes the book the player actually held (task 5b).
        book = _stored_opening_book(doc)
        active = simulate_play(
            paths, decisions, use_reported=use_reported, start_targets=targets, opening_book=book
        )
        twin = simulate_play(
            paths, None, use_reported=use_reported, start_targets=targets, opening_book=book
        )
        # sp-01: the DRIFT twin (DN-5's fixed nominal schedule) — E7's slot
        # receives its data at last; the difference between these two series
        # across a decade is the vintage-timing argument, drawn not argued.
        drift = simulate_play(
            paths,
            None,
            use_reported=use_reported,
            start_targets=targets,
            pacing_rule="fixed",
            opening_book=book,
        )
        attribution = window_contributions_play(
            paths, decisions, use_reported=use_reported, start_targets=targets, opening_book=book
        )

        # sp-03 (E4): the flinch cost and the arithmetic warning ride the
        # outcome — computed here (the server owns tone and number alike).
        from ah.annotations import post_game_annotations

        # su-app-06 (I2): the flinch cost measures a cut against the player's
        # OWN stored plan when the session carries one (spec section 2), not
        # against the model's pacing rule. None for every session without a
        # plan, which keeps that path exactly as it was.
        stored_plan = doc.get("commitment_plan")
        annotations = post_game_annotations(
            paths,
            decisions,
            use_reported=use_reported,
            start_targets=targets,
            opening_book=book,
            commitment_plan=(
                CommitmentPlan.model_validate_json(stored_plan) if stored_plan else None
            ),
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
            "annotations": annotations,
            "forced_secondaries": active.forced_secondaries,
        }

    return app


app = create_app()
