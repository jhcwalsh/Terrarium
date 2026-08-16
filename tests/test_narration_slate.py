"""Slate assembly: the quarterly slot contest (DN-9 Appendix B).

Two properties matter more than the rest and both are pinned here: the contest
is **deterministic** — ties resolve by a documented rule, never by dict ordering
or set iteration — and **slate size is a function of that quarter's own events
and nothing else**, because a slate builder that could save a slot for something
coming would make slate size a forward signal (§B.1).
"""

from __future__ import annotations

import pytest

from ah.narration.constants import PANEL_OF_SLOT
from ah.narration.events import Event
from ah.narration.slate import SlateParams, build_slates


def _event(month: int, cls: str, slot: str, severity: int, value: float = 1.0) -> Event:
    return Event(
        month=month,
        cls=cls,
        severity=severity,
        kind="point",
        slot=slot,
        panel=PANEL_OF_SLOT[slot],
        delta={"label": f"{cls} {value:+.1f}", "value": value, "units": "pp"},
        trigger_values={"x": value},
    )


def _params(**overrides: object) -> SlateParams:
    base = {
        "contest_rule": "severity_then_abs_delta",
        "tie_break": "lowest_class_id_then_lowest_month",
        "min_slots": 3,
        "capital_drop_rule": "drop_when_max_severity_zero",
        "special_edition_severity": 3,
        "capital_absent_message": "CAPITAL omitted — portfolio layer not wired to this world",
        "book_available": False,
    }
    base.update(overrides)
    return SlateParams(**base)  # pyright: ignore[reportArgumentType]


def test_one_slate_per_quarter_over_the_decade():
    events = [_event(m, "E02", "DATA", 1) for m in range(1, 121)]
    slates = build_slates(events, _params(), months=120)
    assert len(slates) == 40
    assert [s.quarter for s in slates] == list(range(1, 41))
    assert slates[0].months == (1, 2, 3)
    assert slates[14].year == 4 and slates[14].quarter_of_year == 3


def test_the_highest_severity_candidate_wins_its_slot():
    events = [
        _event(1, "E05", "MARKETS", 1),
        _event(2, "E08", "MARKETS", 3),
        _event(3, "E05", "MARKETS", 2),
    ]
    slate = build_slates(events, _params(), months=3)[0]
    winner = {a.slot: a for a in slate.announcements}["MARKETS"]
    assert winner.event.cls == "E08"


def test_losers_become_one_line_notes_rather_than_disappearing():
    events = [
        _event(1, "E05", "MARKETS", 1),
        _event(2, "E08", "MARKETS", 3),
    ]
    slate = build_slates(events, _params(), months=3)[0]
    winner = {a.slot: a for a in slate.announcements}["MARKETS"]
    assert len(winner.also_this_quarter) == 1
    assert winner.also_this_quarter[0].cls == "E05"


def test_ties_resolve_by_the_documented_rule_not_by_iteration_order():
    """Same severity, same |delta|: the tie-break decides, and reversing the
    input order must not change the winner."""
    forward = [
        _event(1, "E08", "MARKETS", 2, value=1.0),
        _event(1, "E05", "MARKETS", 2, value=1.0),
    ]
    backward = list(reversed(forward))
    params = _params(tie_break="lowest_class_id_then_lowest_month")
    a = build_slates(forward, params, months=3)[0]
    b = build_slates(backward, params, months=3)[0]
    assert a.announcements[0].event.cls == b.announcements[0].event.cls == "E05"


def test_a_different_tie_break_gives_a_different_winner():
    events = [
        _event(1, "E05", "MARKETS", 2, value=1.0),
        _event(3, "E08", "MARKETS", 2, value=1.0),
    ]
    lowest_month = build_slates(
        events, _params(tie_break="lowest_month_then_lowest_class_id"), months=3
    )[0]
    lowest_class = build_slates(
        events, _params(tie_break="lowest_class_id_then_lowest_month"), months=3
    )[0]
    assert lowest_month.announcements[0].event.month == 1
    assert lowest_class.announcements[0].event.cls == "E05"


def test_capital_is_omitted_and_the_omission_is_stated_when_the_book_is_absent():
    events = [_event(1, "E02", "DATA", 1), _event(2, "E05", "MARKETS", 2)]
    slate = build_slates(events, _params(book_available=False), months=3)[0]
    assert "CAPITAL" in slate.omitted_slots
    assert any("CAPITAL omitted" in note for note in slate.omission_notes)
    assert all(a.slot != "CAPITAL" for a in slate.announcements)


def test_severity_three_opens_the_special_band():
    quiet = build_slates([_event(1, "E05", "MARKETS", 2)], _params(), months=3)[0]
    loud = build_slates([_event(1, "E08", "MARKETS", 3)], _params(), months=3)[0]
    assert not quiet.special
    assert loud.special
    assert loud.lead is not None and loud.lead.event.cls == "E08"


def test_a_quarter_below_the_minimum_is_recorded_not_padded():
    slate = build_slates([_event(1, "E02", "DATA", 1)], _params(min_slots=3), months=3)[0]
    assert len(slate.announcements) == 1
    assert slate.below_minimum


def test_every_announcement_names_the_panel_and_the_delta_it_explains():
    events = [_event(1, "E02", "DATA", 1), _event(2, "E05", "MARKETS", 2)]
    slate = build_slates(events, _params(), months=3)[0]
    for announcement in slate.announcements:
        assert announcement.panel == PANEL_OF_SLOT[announcement.slot]
        assert announcement.delta["label"]


def test_slate_size_depends_only_on_this_quarters_events():
    """Adding a severity-3 event in a LATER quarter must not change this one."""
    base = [_event(1, "E02", "DATA", 1)]
    later = [*base, _event(50, "E08", "MARKETS", 3)]
    first_alone = build_slates(base, _params(), months=120)[0]
    first_with_later = build_slates(later, _params(), months=120)[0]
    assert [a.event.cls for a in first_alone.announcements] == [
        a.event.cls for a in first_with_later.announcements
    ]
    assert first_alone.special == first_with_later.special


def test_an_unknown_contest_rule_is_refused_rather_than_defaulted():
    with pytest.raises(Exception, match="coin_flip"):
        build_slates([_event(1, "E02", "DATA", 1)], _params(contest_rule="coin_flip"), months=3)
