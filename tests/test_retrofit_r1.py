"""Retrofit R-1 (DN-5) — shape only, every acceptance item testable here.

Decision contract: actions are a list (singleton included), empty-list
reached is distinct from not_reached, unimplemented verbs reject loudly,
client-supplied cost_charged rejects. Stamps: three inert fields on every
new RunRecord; a pre-change database upgrades in place and old rows read
back stampless. Leaderboard: the triple scope key is in the unique
constraint and required by every query path.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from ah.artifacts import decisions as dec
from ah.store import leaderboard as lb
from ah.store import runrecords as rr
from ah.store.db import connect, migrate


def _window(actions: list[dict[str, Any]], status: str = "reached") -> dict[str, Any]:
    return {
        "window_id": 3,
        "actions": actions,
        "submitted_at": "2026-08-02T12:00:00+00:00",
        "status": status,
    }


ACTION = {"verb": "rebalance_public", "payload": {"target_weights": {"public_equity": 0.6}}}


class TestDecisionContract:
    def test_singleton_is_a_list_not_a_special_case(self):
        w = dec.window_from_client(_window([ACTION]))
        assert isinstance(w.actions, tuple) and len(w.actions) == 1
        assert w.actions[0].verb == "rebalance_public"

    def test_empty_reached_round_trips_and_differs_from_not_reached(self):
        reached = dec.window_from_client(_window([]))
        not_reached = dec.window_from_client(_window([], status="not_reached"))
        assert reached.actions == () and reached.status == "reached"
        assert not_reached.status == "not_reached"
        assert reached != not_reached  # the distinction the retrofit exists for
        doc = dec.window_to_document(reached)
        assert doc == _window([])  # byte-stable round trip
        assert dec.window_from_client(doc) == reached

    def test_not_reached_with_actions_refuses(self):
        with pytest.raises(dec.DecisionError, match="not_reached"):
            dec.window_from_client(_window([ACTION], status="not_reached"))

    def test_declared_unimplemented_verbs_reject_loudly(self):
        for verb in ("set_pacing", "sell_secondary"):
            with pytest.raises(dec.UnimplementedVerbError, match="not yet implemented"):
                dec.window_from_client(_window([{"verb": verb, "payload": {}}]))
        with pytest.raises(dec.DecisionError, match="unknown verb"):
            dec.action_from_client({"verb": "buy_lottery_tickets", "payload": {}})

    def test_client_supplied_cost_charged_rejects(self):
        with pytest.raises(dec.DecisionError, match="engine-written"):
            dec.action_from_client({**ACTION, "cost_charged": 0.0})

    def test_engine_charge_is_the_only_writer(self):
        action = dec.action_from_client(ACTION)
        assert action.cost_charged is None
        charged = dec.engine_charge(action, 1.25)
        assert charged.cost_charged == 1.25
        w = dec.DecisionWindow(1, (charged,), "2026-08-02T12:00:00+00:00", "reached")
        assert dec.window_to_document(w)["actions"][0]["cost_charged"] == 1.25


class TestRunRecordStamps:
    def _save(self, conn):
        conn.execute(
            "INSERT INTO worlds(world_id, spec_version, status, json, created_at) "
            "VALUES ('w1', '1.0.0', 'active', '{}', 't0')"
        )
        rr.save_run_record(
            conn,
            run_id="r1",
            world_id="w1",
            resolved_engine={"engine_id": "toy-v0"},
            seed=42,
            n_paths=8,
            overrides={},
            outputs_digest="sha256:" + "0" * 64,
            summary_stats={"mean": 0.0},
            created_at="2026-08-02T12:00:00+00:00",
        )

    def test_every_new_record_carries_the_three_stamps(self):
        conn = connect(":memory:")
        self._save(conn)
        rec = rr.get_run_record(conn, "r1")
        assert rec is not None
        assert rec["decision_schema_version"] == "1.0"
        assert rec["decision_alpha_version"] == "1.0"
        assert rec["twin_definition"] == "policy"

    def test_record_is_unchanged_except_the_stamps(self):
        conn = connect(":memory:")
        self._save(conn)
        rec = rr.get_run_record(conn, "r1")
        assert rec is not None
        legacy_fields = {
            "run_id",
            "world_id",
            "resolved_engine",
            "seed",
            "n_paths",
            "overrides",
            "outputs_digest",
            "summary_stats",
            "created_at",
        }
        new_fields = set(rec) - legacy_fields
        assert new_fields == {
            "decision_schema_version",
            "decision_alpha_version",
            "twin_definition",
        }

    def test_a_pre_change_database_upgrades_in_place(self):
        """Simulate a database created before the retrofit: no stamp columns,
        one legacy row. migrate() adds the columns; the old row reads back
        stampless (NULL), the next save carries stamps. No version break."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE worlds (world_id TEXT PRIMARY KEY, spec_version TEXT NOT NULL,
                status TEXT NOT NULL, json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE run_records (run_id TEXT PRIMARY KEY, world_id TEXT NOT NULL,
                resolved_engine TEXT NOT NULL, seed INTEGER NOT NULL,
                n_paths INTEGER NOT NULL, overrides TEXT NOT NULL,
                outputs_digest TEXT NOT NULL, summary_stats TEXT NOT NULL,
                created_at TEXT NOT NULL);
            INSERT INTO worlds VALUES ('w0', '1.0.0', 'active', '{}', 't0');
            INSERT INTO run_records VALUES ('legacy', 'w0', '{}', 1, 2, '{}',
                'sha256:legacy', '{}', 't0');
            """
        )
        migrate(conn)
        migrate(conn)  # idempotent
        legacy = rr.get_run_record(conn, "legacy")
        assert legacy is not None and legacy["decision_schema_version"] is None
        self._save(conn)
        assert rr.get_run_record(conn, "r1")["decision_schema_version"] == "1.0"  # type: ignore[index]


class TestLeaderboardScope:
    def test_triple_key_is_the_unique_constraint(self):
        conn = connect(":memory:")
        kwargs: dict[str, Any] = dict(
            world_id="w1",
            seed=42,
            decision_alpha_version="1.0",
            participant="team-a",
            score=10.0,
            created_at="t0",
        )
        lb.submit_score(conn, **kwargs)
        with pytest.raises(lb.LeaderboardError, match="duplicate"):
            lb.submit_score(conn, **kwargs)
        # a different decision-alpha definition is a DIFFERENT competition
        lb.submit_score(conn, **{**kwargs, "decision_alpha_version": "2.0"})
        assert len(lb.scores(conn, world_id="w1", seed=42, decision_alpha_version="1.0")) == 1
        assert len(lb.scores(conn, world_id="w1", seed=42, decision_alpha_version="2.0")) == 1

    def test_no_query_path_omits_the_version(self):
        conn = connect(":memory:")
        with pytest.raises(TypeError):
            lb.scores(conn, world_id="w1", seed=42)  # type: ignore[call-arg]
        with pytest.raises(lb.LeaderboardError, match="decision_alpha_version"):
            lb.submit_score(
                conn,
                world_id="w1",
                seed=42,
                decision_alpha_version="",
                participant="team-a",
                score=1.0,
                created_at="t0",
            )

    def test_board_orders_best_first(self):
        conn = connect(":memory:")
        for participant, score in (("b", 5.0), ("a", 9.0)):
            lb.submit_score(
                conn,
                world_id="w1",
                seed=1,
                decision_alpha_version="1.0",
                participant=participant,
                score=score,
                created_at="t0",
            )
        board = lb.scores(conn, world_id="w1", seed=1, decision_alpha_version="1.0")
        assert [r["participant"] for r in board] == ["a", "b"]
