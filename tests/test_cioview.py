"""cio-01: the CIO view builder and the play-state exposure it rides on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ah.cioview import BAND_PCT, _frozen_paths, build_cio_view, validate_cio_view
from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import (
    PRIVATE_ASSETS,
    START_CASH,
    START_TARGETS,
    default_opening_book,
    simulate_play,
)
from ah.port.book import OpeningBook

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(preset: str = "stagflation"):
    doc: dict[str, Any] = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


def test_per_asset_private_flows_sum_to_totals():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert abs(sum(q.private_calls.values()) - q.calls_paid) < 1e-9
        assert abs(sum(q.private_distributions.values()) - q.distributions_received) < 1e-9
        assert abs(sum(q.private_unfunded.values()) - q.unfunded_total) < 1e-9
        assert set(q.private_calls) == set(PRIVATE_ASSETS)


def test_per_asset_expired_sums_to_the_quarter_total():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert abs(sum(q.private_expired.values()) - q.expired_undrawn) < 1e-9
        assert set(q.private_expired) == set(PRIVATE_ASSETS)


def test_per_asset_values_close_against_the_book():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        total = q.cash + sum(q.liquid_values.values()) + sum(q.private_true.values())
        assert abs(total - q.nav_true) < 1e-9
        total_rep = q.cash + sum(q.liquid_values.values()) + sum(q.private_reported.values())
        assert abs(total_rep - q.nav_reported) < 1e-9


def test_monthly_marks_close_on_the_quarter():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert len(q.nav_true_months) == 3
        assert len(q.nav_reported_months) == 3
        assert abs(q.nav_true_months[2] - q.nav_true) < 1e-9
        assert abs(q.nav_reported_months[2] - q.nav_reported) < 1e-9
        assert all(v > 0 for v in q.nav_true_months)


def test_opening_book_recorded():
    result = simulate_play(_paths(), None)
    op = result.opening
    total = op["cash"] + sum(op["liquid_values"].values()) + sum(op["private_true"].values())
    assert abs(total - op["nav_true"]) < 1e-9
    assert set(op["private_unfunded"]) == set(PRIVATE_ASSETS)


def _pq(label: str, forecast: bool) -> dict[str, Any]:
    return {
        "label": label,
        "forecast": forecast,
        "calls": 1.0,
        "distributions": 1.5,
        "net": 0.5,
        "navOpen": 30.0,
        "navClose": 30.5,
        "unfundedOpen": 15.0,
        "unfundedClose": 14.0,
        "callRateUnfunded": 0.0667,
        "callRateNav": 0.0333,
        "coverage": 0.459,
        "expiredUndrawn": 0.0,
    }


def _minimal_view() -> dict[str, Any]:
    """Smallest payload that passes every check — the seed for defect tests."""
    return {
        "meta": {
            "runId": "r1",
            "seed": "42",
            "worldTitle": "t",
            "worldVersion": "toy-v0.6",
            "linkageVersion": "public-0.1",
            "decisionAlphaVersion": "port-v4-ladder",
            "asOfLabel": "Y1 Q1",
            "asOfMonth": 2,
            "plane": "reported",
            "planesAvailable": ["reported", "true"],
            "unitLabel": "$m",
            "unitSuffix": "m",
            "currency": "USD",
            "watermark": "w",
            "disclaimer": "d",
        },
        "plan": {
            "totalValue": 100.0,
            "growthPct": None,
            "netOfFlows": None,
            "windowLabel": "Since inception",
            "history": {"values": [100.0, 100.5, 100.0 + 1e-9], "worldStartIndex": 0},
        },
        "allocation": {
            "goals": [{"id": "growth", "label": "Growth", "tolerancePct": 5.0}],
            "classes": [
                {
                    "id": "equity",
                    "label": "Equity",
                    "goalId": "growth",
                    "targetPct": 100.0,
                    "bandLoPct": 95.0,
                    "bandHiPct": 100.0,
                    "currentPct": 100.0,
                    "value": 100.0,
                    "returns": [1.0],
                }
            ],
            "alertPolicy": {"watchFraction": 0.75},
        },
        "performance": {
            "periods": ["1Q"],
            "annualisedFromIndex": 1,
            "total": [1.2],
            "benchmark": [1.1],
        },
        "liquidity": {
            "tiers": [{"id": "t1", "tier": 1, "label": "T1", "note": "", "value": 100.0}],
            "forecast12m": {
                "distributions": 2.0,
                "income": 0.0,
                "calls": 3.0,
                "payout": 1.0,
                "net": -2.0,
            },
        },
        "privateCashflows": {
            "histCount": 1,
            "classes": [{"id": "pe", "label": "PE"}],
            "series": {
                "aggregate": [_pq("Y1Q1", False)],
                "pe": [_pq("Y1Q1", False)],
            },
        },
    }


def test_validator_passes_a_well_formed_view():
    assert validate_cio_view(_minimal_view()) == []


def test_validator_catches_unbalanced_weights():
    v = _minimal_view()
    v["allocation"]["classes"][0]["currentPct"] = 90.0
    assert any("currentPct sums" in e for e in validate_cio_view(v))


def test_validator_catches_forecast_flag_mismatch():
    v = _minimal_view()
    v["privateCashflows"]["series"]["pe"][0]["forecast"] = True
    assert any("forecast flag" in e for e in validate_cio_view(v))


def test_validator_catches_expired_undrawn_aggregate_mismatch():
    v = _minimal_view()
    v["privateCashflows"]["series"]["aggregate"][0]["expiredUndrawn"] = 9.0
    assert any("expiredUndrawn" in e for e in validate_cio_view(v))


def test_validator_catches_net_identity_break():
    v = _minimal_view()
    v["liquidity"]["forecast12m"]["net"] = 5.0
    assert any("components imply" in e for e in validate_cio_view(v))


def test_validator_catches_plane_not_available():
    v = _minimal_view()
    v["meta"]["plane"] = "true"
    v["meta"]["planesAvailable"] = ["reported"]
    assert any("planesAvailable" in e for e in validate_cio_view(v))


def test_validator_rejects_lo_hi_out_of_order():
    v = _minimal_view()
    v["allocation"]["classes"][0]["bandLoPct"] = 50.0
    v["allocation"]["classes"][0]["bandHiPct"] = 50.0
    errors = validate_cio_view(v)
    assert any("band" in e for e in errors)


def test_validator_rejects_lo_greater_than_hi():
    v = _minimal_view()
    v["allocation"]["classes"][0]["bandLoPct"] = 60.0
    v["allocation"]["classes"][0]["bandHiPct"] = 40.0
    errors = validate_cio_view(v)
    assert any("band" in e for e in errors)


def test_validator_rejects_a_band_on_a_cash_class():
    v = _minimal_view()
    v["allocation"]["classes"][0]["id"] = "cash"
    v["allocation"]["classes"][0]["bandLoPct"] = 0.0
    v["allocation"]["classes"][0]["bandHiPct"] = 10.0
    errors = validate_cio_view(v)
    assert any("cash" in e and "band" in e for e in errors)


def _view(
    plane: str = "reported",
    revealed: int = 60,
    fq: int = 4,
    preset: str = "stagflation",
    prehistory: bool = True,
    book: OpeningBook | None = None,
):
    return build_cio_view(
        _paths(preset),
        {},
        run_id="r-test",
        seed=42,
        world_title="Stagflation",
        world_version="toy-v0.6",
        alpha_version="port-v4-ladder",
        start_targets=None,
        plane=plane,
        revealed_months=revealed,
        forecast_quarters=fq,
        prehistory=prehistory,
        opening_book=book,
    )


def test_target_pct_follows_the_entered_books_policy_targets():
    """su-app-07 Ruling G. Since task 2 the engine paces and caps off the
    book's ``effective_targets()``. A dashboard whose ``targetPct`` still read
    the world default would state a policy the institution is not running —
    su-app-06's worst defect class (displayed one thing, applied another),
    reappearing on the CIO surface.

    Values are left exactly as the derived book has them; only the AIM moves,
    so nothing but the target basis can explain a change here."""
    book = default_opening_book(START_TARGETS)
    tilted = book.model_copy(deep=True)
    tilted.targets = {**START_TARGETS, "equity": 23.0, "pe": 30.0}
    assert tilted.liquid == book.liquid and tilted.private == book.private

    default_classes = {c["id"]: c for c in _view()["allocation"]["classes"]}
    assert default_classes["pe"]["targetPct"] == pytest.approx(20.0)
    assert default_classes["equity"]["targetPct"] == pytest.approx(33.0)

    v = _view(book=tilted)
    classes = {c["id"]: c for c in v["allocation"]["classes"]}
    assert classes["pe"]["targetPct"] == pytest.approx(30.0)
    assert classes["equity"]["targetPct"] == pytest.approx(23.0)
    assert validate_cio_view(v) == []


def test_the_target_cash_addend_follows_the_entered_books_cash():
    """The denominator is ``sum(targets) + cash`` (Ruling C), so the cash
    addend has to travel with the targets: a book holding 5 points of cash
    normalised against ``START_CASH``'s 2.0 would print percentages that sum
    past 100."""
    book = default_opening_book(START_TARGETS)
    heavy = book.model_copy(deep=True)
    heavy.liquid = {**book.liquid, "equity": book.liquid["equity"] - 3.0}
    heavy.cash = book.cash + 3.0
    heavy.targets = {**START_TARGETS, "equity": START_TARGETS["equity"] - 3.0}

    v = _view(book=heavy)
    classes = {c["id"]: c for c in v["allocation"]["classes"]}
    assert classes["cash"]["targetPct"] == pytest.approx(5.0)
    assert sum(c["targetPct"] for c in v["allocation"]["classes"]) == pytest.approx(100.0)
    assert validate_cio_view(v) == []


def test_a_book_with_no_entered_targets_still_targets_its_own_values():
    """``effective_targets()``'s fallback reaches the dashboard too: a 0.1-era
    book (``targets=None``) aims at the allocation it opened holding, which is
    exactly what ``simulate_play`` paces against for it."""
    book = default_opening_book(START_TARGETS)
    untargeted = book.model_copy(deep=True)
    untargeted.targets = None
    untargeted.liquid = {
        **book.liquid,
        "equity": book.liquid["equity"] - 4.0,
        "bonds": book.liquid["bonds"] + 4.0,
    }

    classes = {c["id"]: c for c in _view(book=untargeted)["allocation"]["classes"]}
    assert classes["equity"]["targetPct"] == pytest.approx(29.0)
    assert classes["bonds"]["targetPct"] == pytest.approx(16.0)


def test_bands_follow_the_books_own_asymmetric_range():
    """app-open-02 task 2: the book's own ``ranges`` (absolute allocation
    POINTS, same scale as ``targets``) travel straight through to
    ``bandLoPct``/``bandHiPct``, converted exactly like ``targetPct`` — a
    ``points / target_total * 100`` scaling, NOT a symmetric half-width. An
    entered range need not be centred on the target at all (serve.py's
    ``_alert_level`` docstring: the target may legally sit outside its own
    band), so an asymmetric range must show up asymmetric on the wire."""
    book = default_opening_book(START_TARGETS)
    custom = book.model_copy(deep=True)
    # deliberately asymmetric around the 33.0 target, and NOT containing it
    # on one side check below (lo=20 hi=45 still contains 33 — asymmetry is
    # the point here, not out-of-band; that shape is exercised in serve.py's
    # own tests for _alert_level).
    custom.ranges = {**(book.ranges or {}), "equity": (20.0, 45.0)}

    v = _view(book=custom)
    equity = next(c for c in v["allocation"]["classes"] if c["id"] == "equity")
    # target_total is exactly 100.0 for the default book (98 points of
    # targets + 2.0 cash), so points convert to percent 1:1 here.
    assert equity["bandLoPct"] == pytest.approx(20.0)
    assert equity["bandHiPct"] == pytest.approx(45.0)
    assert validate_cio_view(v) == []


def test_bands_fall_back_to_band_pct_around_target_with_no_book():
    """No opening book at all -> the OLD behaviour shape: a symmetric
    half-width from the module-level ``BAND_PCT`` dict, around whatever
    ``targetPct`` this view computed."""
    v = _view()
    classes = {c["id"]: c for c in v["allocation"]["classes"]}
    for cid, half in BAND_PCT.items():
        if cid == "cash":
            continue
        c = classes[cid]
        assert c["bandLoPct"] == pytest.approx(c["targetPct"] - half)
        assert c["bandHiPct"] == pytest.approx(c["targetPct"] + half)


def test_bands_fall_back_when_the_book_has_no_range_for_a_named_sleeve():
    """A book can carry ``ranges`` for some sleeves and not others (or none
    at all) — a sleeve the book is silent on still gets the BAND_PCT
    fallback around its own (book-derived) targetPct, not a missing field."""
    book = default_opening_book(START_TARGETS)
    partial = book.model_copy(deep=True)
    partial.ranges = {"equity": (20.0, 45.0)}  # every other sleeve is silent

    v = _view(book=partial)
    classes = {c["id"]: c for c in v["allocation"]["classes"]}
    assert classes["equity"]["bandLoPct"] == pytest.approx(20.0)
    assert classes["equity"]["bandHiPct"] == pytest.approx(45.0)
    bonds = classes["bonds"]
    assert bonds["bandLoPct"] == pytest.approx(bonds["targetPct"] - BAND_PCT["bonds"])
    assert bonds["bandHiPct"] == pytest.approx(bonds["targetPct"] + BAND_PCT["bonds"])
    assert validate_cio_view(v) == []


def test_cash_band_is_always_none():
    """Cash carries no target band (BookEntry says so on-screen) — true with
    no book, with a book carrying no cash range (the book model has no
    concept of one), and regardless of the BAND_PCT fallback that used to
    apply to cash too."""
    for book in (None, default_opening_book(START_TARGETS)):
        v = _view(book=book)
        cash = next(c for c in v["allocation"]["classes"] if c["id"] == "cash")
        assert cash["bandLoPct"] is None
        assert cash["bandHiPct"] is None


def test_view_validates_clean_on_both_planes():
    for plane in ("reported", "true"):
        assert validate_cio_view(_view(plane)) == []


def test_plan_history_is_monthly_and_truncated_at_the_pointer():
    """cio-04 made pre-history the default (``prehistory=True``); this test
    now pins the ``prehistory=False`` opt-out — the shape it always pinned,
    just no longer the default."""
    v = _view(revealed=60, prehistory=False)
    assert len(v["plan"]["history"]["values"]) == 60  # 20 closed quarters * 3
    assert v["plan"]["history"]["worldStartIndex"] == 0
    assert v["meta"]["asOfLabel"] == "Y5 Q4"


def test_planes_disagree_where_smoothing_bites():
    rep, tru = _view("reported"), _view("true")
    assert rep["plan"]["totalValue"] != tru["plan"]["totalValue"]
    # plane-invariant: the cash account has no planes (DN-8 section 4)
    rep_cash = next(t for t in rep["liquidity"]["tiers"] if "cash" in t["classIds"])
    tru_cash = next(t for t in tru["liquidity"]["tiers"] if "cash" in t["classIds"])
    assert rep_cash["value"] == tru_cash["value"]


def test_unreached_windows_are_null_not_zero():
    """cio-04 made pre-history the default (``prehistory=True``), which
    supplies 40 quarters of its own and would make 3Y/5Y/10Y reachable here
    regardless of the world's own revealed window; this test now pins the
    ``prehistory=False`` opt-out so "unreached" still means what it says."""
    v = _view(revealed=15, prehistory=False)  # 5 closed quarters: 3Y/5Y/10Y unreachable
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    for p in ("3Y", "5Y", "10Y"):
        assert v["performance"]["total"][idx[p]] is None
    for p in ("1Q", "1Y"):
        assert v["performance"]["total"][idx[p]] is not None


def test_month_zero_builds_a_valid_view_populated_from_the_opening_book():
    """app-open-01 (cio-05): the CIO is the front door — the first thing a
    player sees after the opening book is confirmed, before any advance().
    ``revealed_months=0`` used to raise ("no closed quarter inside the
    revealed window") for every caller; now it builds a real payload off
    ``active.opening`` (never ``active.quarters[-1]``, which would silently
    read the FURTHEST forecast quarter as "now")."""
    v = _view(revealed=0)
    assert validate_cio_view(v) == []
    assert v["meta"]["asOfLabel"] == "T0"
    assert v["meta"]["asOfMonth"] == 0
    assert v["privateCashflows"]["histCount"] == 0
    # "now" is the opening state exactly: zero elapsed growth on a real
    # (nonzero) total, not a null placeholder.
    assert v["plan"]["growthPct"] == 0.0
    assert v["plan"]["netOfFlows"] == 0.0
    assert v["plan"]["totalValue"] > 0
    # allocation is POPULATED, not empty or null — the whole point of
    # "starting values" (item 1).
    cur = sum(c["currentPct"] for c in v["allocation"]["classes"])
    assert abs(cur - 100.0) < 0.1
    assert all(c["currentPct"] is not None for c in v["allocation"]["classes"])


def test_month_zero_ytd_is_null_but_the_inherited_decade_still_feeds_1q_1y():
    """YTD is a "this calendar year of the WORLD" concept; at month 0 there
    is no world-year to speak of, so it must be null regardless of
    prehistory. 1Q/1Y are plain trailing windows and, with prehistory on,
    are already-established policy (cio-04) to blend from the inherited
    decade whenever fewer world quarters exist than the window needs — at
    month 0 that blend is total, not partial, but the rule is the same
    one already documented in performance.footnote."""
    v = _view(revealed=0, prehistory=True)
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    assert v["performance"]["total"][idx["YTD"]] is None
    assert v["performance"]["total"][idx["1Q"]] is not None
    assert v["performance"]["total"][idx["1Y"]] is not None


def test_month_zero_without_prehistory_has_no_null_crash_and_one_chart_point():
    """A generated (non-toy-v0) world opts out of the inherited decade
    (serve.py). At month 0 that leaves nothing of the world's own tape
    either — the chart still needs at least the opening point to draw, and
    every performance column is honestly null (nothing has been reached at
    all, inherited or otherwise)."""
    v = _view(revealed=0, prehistory=False)
    assert validate_cio_view(v) == []
    assert v["plan"]["history"]["values"] == [round(v["plan"]["totalValue"], 4)]
    assert v["plan"]["history"]["worldStartIndex"] == 0
    assert all(x is None for x in v["performance"]["total"])
    assert "preRunLabel" not in v["plan"]


def test_month_zero_with_forecast_quarters_zero_does_not_crash():
    """The fully degenerate case: no closed quarter AND no forecast
    requested. Every downstream table is legitimately empty rather than
    fabricated — this used to be unreachable (n_q was always >= 1), so
    nothing enforced Python/JS validator parity on an empty (but present)
    aggregate series until this shape became real."""
    v = _view(revealed=0, fq=0)
    assert validate_cio_view(v) == []
    assert v["privateCashflows"]["series"]["aggregate"] == []
    assert v["liquidity"]["forecast12m"] == {
        "distributions": 0.0,
        "income": 0.0,
        "calls": 0.0,
        "payout": 0.0,
        "net": 0.0,
    }


def test_month_zero_with_a_custom_book_shows_the_books_own_values():
    """su-app-06/07's book-carrying dashboard promise extends to month 0: a
    player who entered a custom book must see THAT book's starting values,
    not the world default's."""
    book = default_opening_book()
    book.liquid["equity"] = book.liquid["equity"] + 1.0
    book.cash = book.cash - 1.0
    v = _view(revealed=0, book=book)
    assert validate_cio_view(v) == []
    equity = next(c for c in v["allocation"]["classes"] if c["id"] == "equity")
    default_equity = next(
        c for c in _view(revealed=0)["allocation"]["classes"] if c["id"] == "equity"
    )
    assert equity["currentPct"] != default_equity["currentPct"]


def test_revealed_one_or_two_still_refuses_no_closed_quarter():
    """Mid-quarter (unreachable through the UI's quarterly rhythm, but not
    through direct calls) still has nothing closed — the guard month 0 now
    bypasses must stay in place for 1 and 2."""
    for revealed in (1, 2):
        with pytest.raises(ValueError, match="no closed quarter"):
            _view(revealed=revealed)


def test_benchmark_is_the_twin():
    v = _view()
    assert v["performance"]["benchmarkLabel"] == "Policy twin (hold course)"
    assert v["performance"]["benchmark"][0] is not None


def test_forecast_rows_are_flagged_and_suppressable():
    v = _view(fq=4)
    pcf = v["privateCashflows"]
    n_hist = pcf["histCount"]
    for _key, rows in pcf["series"].items():
        assert len(rows) == n_hist + 4
        assert all(r["forecast"] is (i >= n_hist) for i, r in enumerate(rows))
    v0 = _view(fq=0)
    assert all(
        not r["forecast"] for rows in v0["privateCashflows"]["series"].values() for r in rows
    )
    assert len(v0["privateCashflows"]["series"]["aggregate"]) == v0["privateCashflows"]["histCount"]


def test_aggregate_private_series_is_the_sum_of_classes():
    v = _view()
    pcf = v["privateCashflows"]
    ids = [c["id"] for c in pcf["classes"]]
    for i, agg in enumerate(pcf["series"]["aggregate"]):
        for field_name in ("calls", "distributions", "navClose", "unfundedClose", "expiredUndrawn"):
            s = sum(pcf["series"][cid][i][field_name] for cid in ids)
            assert abs(s - agg[field_name]) < 0.51, (i, field_name)


def test_expired_undrawn_is_a_positive_magnitude_present_on_every_row():
    v = _view()
    pcf = v["privateCashflows"]
    for rows in pcf["series"].values():
        for r in rows:
            assert r["expiredUndrawn"] >= 0.0


def test_vintage_ladder_is_nonempty_and_ordered_oldest_first():
    """The ladder renders oldest vintage first.

    I-3: a prior version of this test defined a local ``chrono_key`` that was
    a verbatim reimplementation of ``_vintage_sort_key`` and then asserted
    ``keys == sorted(keys)`` — "sorted by f is sorted by f", true by
    construction regardless of whether the s/v sign convention inside
    ``_vintage_sort_key`` is right or backwards, since the same (possibly
    inverted) convention would appear on both sides of the comparison and
    the test could never catch it.

    This version asserts literal, meaning-derived orderings instead, read
    off what the ids mean rather than off the function under test: ``pe-s3``
    (a seeded rung three years older than ``pe-s0``) must precede
    ``pe-s0``, and ``pe-s0`` (the newest seeded rung) must precede
    ``pe-v1`` (the first commitment made during play — necessarily newer
    than every seeded rung).

    Confirmed to bite (manual check, not committed as a test): with
    ``_vintage_sort_key``'s sign flipped (``key = n if tag[0] == "s" else
    -n``) monkeypatched in, both assertions below fail. And reproducing the
    original vulnerability exactly — the OLD test's hardcoded ``chrono_key``
    ALSO rewritten with the same flipped convention, simulating the sign
    having been backwards in both places from day one — the old
    ``keys == sorted(keys)`` form still PASSES (vacuously; both sides share
    the same wrong convention), while the two assertions below both
    correctly fail, because they derive from the cohorts' actual
    ``vintage_year`` construction in ``play.py`` (``_seed_ladder``,
    ``_commit_new_vintage``), not from ``_vintage_sort_key``'s own formula.
    """
    v = _view()
    vintages = v["privateCashflows"]["vintages"]
    assert vintages
    ids = [x["id"] for x in vintages]
    assert "pe-s3" in ids and "pe-s0" in ids and "pe-v1" in ids
    # pe-s3 is three years older than pe-s0 (both seeded rungs; s-K: larger
    # K is older) -- must render before it.
    assert ids.index("pe-s3") < ids.index("pe-s0")
    # pe-s0 is the newest seeded rung; pe-v1 is the first vintage committed
    # during play, strictly newer than any seeded rung -- must render after it.
    assert ids.index("pe-s0") < ids.index("pe-v1")
    for x in vintages:
        assert x["navTrue"] >= 0.0
        assert x["label"]
        # honesty: reported NAV per cohort is not tracked by the engine, so
        # it must not appear as a fabricated figure.
        assert "navReported" not in x


def test_vintage_ladder_ids_are_the_as_of_quarters_cohorts():
    v = _view()
    result = simulate_play(_paths(), {})
    n_q = v["meta"]["asOfMonth"] // 3 + 1
    expected = set(result.quarters[n_q - 1].vintage_nav)
    got = {x["id"] for x in v["privateCashflows"]["vintages"]}
    assert got == expected


def test_liquidity_carries_the_coverage_line():
    """cov-01: unfundedToLiquid/breachLine/worstUnfundedToLiquid are served
    alongside the existing unfundedToNav/coverageAnchor, unchanged."""
    v = _view()
    liq = v["liquidity"]
    assert abs(liq["unfundedToNav"] - 0.224) < 0.01
    assert liq["coverageAnchor"] == 0.5
    assert liq["breachLine"] == 1.0
    assert liq["unfundedToLiquid"] is not None and liq["unfundedToLiquid"] >= 0.0
    assert liq["worstUnfundedToLiquid"] is not None and liq["worstUnfundedToLiquid"] >= 0.0
    # the running max over closed quarters is at least the as-of ratio
    assert liq["worstUnfundedToLiquid"] >= liq["unfundedToLiquid"] - 1e-9


def test_worst_unfunded_to_liquid_is_the_running_max_over_closed_quarters():
    v15 = _view(revealed=15, prehistory=False)  # 5 closed quarters
    v60 = _view(revealed=60, prehistory=False)  # 20 closed quarters
    # more history can only raise (or hold) the running maximum
    assert (
        v60["liquidity"]["worstUnfundedToLiquid"]
        >= v15["liquidity"]["worstUnfundedToLiquid"] - 1e-9
    )


def test_validator_catches_negative_coverage_fields():
    v = _minimal_view()
    v["liquidity"]["unfundedToLiquid"] = -0.1
    assert any("unfundedToLiquid" in e for e in validate_cio_view(v))
    v = _minimal_view()
    v["liquidity"]["worstUnfundedToLiquid"] = -0.1
    assert any("worstUnfundedToLiquid" in e for e in validate_cio_view(v))


def test_validator_catches_breach_line_not_one():
    v = _minimal_view()
    v["liquidity"]["breachLine"] = 0.9
    errors = validate_cio_view(v)
    assert any("breachLine" in e for e in errors)


def test_forecast12m_net_identity_and_signs():
    v = _view()
    f = v["liquidity"]["forecast12m"]
    for k in ("distributions", "income", "calls", "payout"):
        assert f[k] >= 0.0
    assert abs(f["net"] - (f["distributions"] + f["income"] - f["calls"] - f["payout"])) < 1.0


def test_tiers_close_on_plan_total_and_privates_are_illiquid():
    v = _view()
    tiers = v["liquidity"]["tiers"]
    assert (
        abs(sum(t["value"] for t in tiers) - v["plan"]["totalValue"])
        < v["plan"]["totalValue"] * 0.005
    )
    illiquid = [t for t in tiers if t.get("liquid") is False]
    assert illiquid and set(illiquid[0]["classIds"]) == set(PRIVATE_ASSETS)


def test_markets_has_no_conditions_and_paths_match_history():
    v = _view()
    assert "conditions" not in v.get("markets", {})
    h = len(v["plan"]["history"]["values"])
    for s in v["markets"]["returns"]:
        assert len(s["path"]) == h


def test_listed_and_private_classes_have_returns_on_both_planes():
    # liquid sleeves have no reporting plane (port/portfolio.py:73 - "liquid
    # marks are true"); the reported-plane allocation tape must still carry
    # them from the true tape, or six of nine classes ship null columns.
    for plane in ("reported", "true"):
        v = _view(plane)
        by_id = {c["id"]: c for c in v["allocation"]["classes"]}
        assert by_id["equity"]["returns"][0] is not None
        assert by_id["pe"]["returns"][0] is not None


def test_frozen_paths_agree_with_the_live_run_over_the_revealed_window():
    paths = _paths()
    live = simulate_play(paths, None)
    frozen = simulate_play(_frozen_paths(paths, 60, 4), None)
    for i in range(20):
        lq, fq = live.quarters[i], frozen.quarters[i]
        assert abs(lq.nav_true - fq.nav_true) < 1e-9
        assert abs(lq.nav_reported - fq.nav_reported) < 1e-9
        assert abs(lq.calls_paid - fq.calls_paid) < 1e-9
        assert abs(lq.distributions_received - fq.distributions_received) < 1e-9


def test_allocation_guards_zero_total_instead_of_raising():
    from ah.cioview import _allocation
    from ah.play import PlayQuarter, PlayResult

    zeroed = PlayQuarter(
        quarter=0,
        month=2,
        cash=0.0,
        nav_true=0.0,
        nav_reported=0.0,
        calls_paid=0.0,
        distributions_received=0.0,
        spending_paid=0.0,
        forced_sale_total=0.0,
        private_weight_true=0.0,
        unfunded_total=0.0,
        liquid_values={"equity": 0.0},
        private_true={},
        private_reported={},
    )
    active = PlayResult(
        quarters=[zeroed], final_value=0.0, forced_sale_quarters=0, total_forced_sales=0.0
    )
    # su-app-07 Ruling G added `cash_target` between `targets` and `plane`:
    # the policy cash the targets are normalised against. START_CASH here
    # keeps this test on exactly the basis it always ran on.
    alloc = _allocation(active, {"equity": 0.0}, START_CASH, "true", 1, {})
    equity = next(c for c in alloc["classes"] if c["id"] == "equity")
    assert equity["currentPct"] is None


def test_view_is_byte_deterministic():
    a = json.dumps(_view(), sort_keys=True, separators=(",", ":"))
    b = json.dumps(_view(), sort_keys=True, separators=(",", ":"))
    assert a == b


def test_golden_views_validate_on_every_preset():
    for preset in ("stagflation", "goldilocks"):
        for plane in ("reported", "true"):
            for revealed in (0, 12, 60, 120):
                errors = validate_cio_view(_view(plane, revealed, preset=preset))
                assert errors == [], (preset, plane, revealed, errors)


def test_committed_cio_fixtures_match_the_builder():
    """The app's renderer tests consume these fixtures; drift is a contract
    break. Regenerate with scripts/gen_cio_fixture.py when the builder
    legitimately changes."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from gen_cio_fixture import _decided_map, build  # type: ignore
    finally:
        sys.path.pop(0)
    for plane in ("reported", "true"):
        committed = (ROOT / "app" / "fixtures" / f"cio-sample.{plane}.json").read_text(
            encoding="utf-8"
        )
        assert committed == build(plane), f"{plane} fixture is stale - regenerate"
    committed_decided = (ROOT / "app" / "fixtures" / "cio-sample.decided.json").read_text(
        encoding="utf-8"
    )
    assert committed_decided == build("reported", _decided_map()), (
        "decided fixture is stale - regenerate"
    )


def test_decided_fixture_actually_diverges_from_the_twin():
    """The Excess row is the product's argument as a number; a fixture where
    it is identically zero pins nothing."""
    import json

    doc = json.loads(
        (ROOT / "app" / "fixtures" / "cio-sample.decided.json").read_text(encoding="utf-8")
    )
    total = doc["performance"]["total"]
    bench = doc["performance"]["benchmark"]
    diffs = [
        abs(t - b) for t, b in zip(total, bench, strict=True) if t is not None and b is not None
    ]
    assert diffs, "no comparable periods in the decided fixture"
    assert max(diffs) > 0.05, f"decided fixture does not diverge from the twin: {diffs}"
