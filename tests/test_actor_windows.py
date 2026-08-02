"""WP4.7 — windows, triggers, the playbook, wargames.

The FIRST test is the RFR-89 re-check, by name: this WP is the first
consumer of the retrofit's decision contract, and the register demanded
proof that no single-action-per-window assumption crept in at the moment
of consumption. Then: calendar/event scheduling, the playbook's t0
freeze and measured-when-fired discipline (output shapes verified
against the SEALED metric's expectations — imported in the TEST only,
never in production code), and the wargame's identical-worlds refusals.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from ah.artifacts import windows as win
from ah.artifacts.decisions import window_from_client
from ah.eval import decision_metrics as dm

ACTION = {"verb": "rebalance_public", "payload": {"target_weights": {"public_equity": 0.55}}}
ACTION2 = {"verb": "rebalance_public", "payload": {"target_weights": {"public_equity": 0.60}}}


def _window(window_id: int, actions: list, status: str = "reached"):
    return window_from_client(
        {
            "window_id": window_id,
            "actions": actions,
            "submitted_at": "2026-08-02T12:00:00+00:00",
            "status": status,
        }
    )


class TestRFR89Recheck:
    def test_multi_action_windows_flow_end_to_end_unspecial(self):
        """RFR-89: the first real consumer, checked at the moment of
        consumption. Two actions in one window survive record, count,
        and export with nothing collapsing them to one."""
        session = win.WargameSession("w1", 42, "1.0")
        log = session.add_team("team-a")
        slot = win.calendar_windows(8)[0]
        log.record(slot, _window(1, [ACTION, ACTION2]))
        assert log.actions_total() == 2  # a LIST sum, not a window count
        exported = session.export()
        assert len(exported["teams"]["team-a"]["windows"][0]["actions"]) == 2

    def test_empty_reached_and_not_reached_stay_distinct_downstream(self):
        log = win.WindowLog()
        slots = win.calendar_windows(8)
        log.record(slots[0], _window(1, []))  # reached, chose to do nothing
        log.record(slots[1], _window(2, [], status="not_reached"))
        recorded = log.windows()
        assert recorded[0].status == "reached" and recorded[1].status == "not_reached"
        assert log.actions_total() == 0


class TestScheduling:
    def test_calendar_windows_are_deterministic(self):
        slots = win.calendar_windows(12, cadence_quarters=4)
        assert [(s.window_id, s.quarter) for s in slots] == [(1, 0), (2, 4), (3, 8)]

    def test_event_windows_use_the_closed_trigger_list(self):
        slot = win.event_window(window_id=9, quarter=13, trigger="gating")
        assert slot.kind == "event" and slot.trigger == "gating"
        with pytest.raises(win.WindowError, match="unknown trigger"):
            win.event_window(window_id=9, quarter=13, trigger="vibes")

    def test_log_is_append_only_and_id_checked(self):
        log = win.WindowLog()
        slot = win.calendar_windows(4)[0]
        log.record(slot, _window(1, [ACTION]))
        with pytest.raises(win.WindowError, match="append-only"):
            log.record(slot, _window(1, []))
        with pytest.raises(win.WindowError, match="mismatch"):
            log.record(win.calendar_windows(8)[1], _window(1, []))


class TestPlaybook:
    RULES: ClassVar[list[win.PlaybookRule]] = [
        win.PlaybookRule("r-spread", "spread_breach", "cut private commitments 25%"),
        win.PlaybookRule("r-gate", "gating", "do not chase liquidity; hold plan"),
        win.PlaybookRule("r-margin", "collateral_call", "post from cash before selling"),
    ]

    def test_t0_hash_freezes_the_rules(self):
        a = win.Playbook(list(self.RULES))
        b = win.Playbook(list(self.RULES))
        assert a.t0_hash == b.t0_hash and a.t0_hash.startswith("sha256:")
        reordered = win.Playbook(list(reversed(self.RULES)))
        assert reordered.t0_hash != a.t0_hash  # the committee's ordering is content

    def test_adherence_is_measured_when_fired_never_on_paper(self):
        book = win.Playbook(list(self.RULES))
        with pytest.raises(win.WindowError, match="never triggered"):
            book.record_execution("r-spread", followed=True)
        assert book.fire("spread_breach") == ["r-spread"]
        assert book.fire("gating") == ["r-gate"]
        book.record_execution("r-spread", followed=True)
        book.record_execution("r-gate", followed=False)
        # the shapes feed the SEALED metric directly (imported here, in the
        # test, to prove format compatibility — production never imports it)
        assert dm.precommitment_adherence(book.planned(), book.executed()) == pytest.approx(0.5)

    def test_playbook_refusals(self):
        with pytest.raises(win.WindowError, match="not a playbook"):
            win.Playbook([])
        with pytest.raises(win.WindowError, match="duplicate"):
            win.Playbook([self.RULES[0], self.RULES[0]])
        with pytest.raises(win.WindowError, match="empty intent"):
            win.PlaybookRule("r-x", "gating", "   ")


class TestWargame:
    def test_teams_share_one_world_and_seed_by_construction(self):
        session = win.WargameSession("w1", 42, "1.0")
        a = session.add_team("alpha")
        b = session.add_team("bravo")
        slot = win.calendar_windows(4)[0]
        a.record(slot, _window(1, [ACTION]))
        b.record(slot, _window(1, []))
        exported = session.export()
        assert exported["world_id"] == "w1" and exported["seed"] == 42
        assert exported["decision_alpha_version"] == "1.0"  # the leaderboard scope key
        assert set(exported["teams"]) == {"alpha", "bravo"}
        with pytest.raises(win.WindowError, match="duplicate team"):
            session.add_team("alpha")
