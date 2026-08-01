"""WP2.11: the executable form of ``multi_seed_decision_rule``.

Every test here pins ONE sealed sentence. The rule was frozen in words before any
evidence existed; ``ah/eval/g2.py`` is the executable form and is itself hashed, so it
cannot drift from those words without a dated amendment. These tests are what makes
"it does not diverge" checkable rather than asserted.

The report builder is ``tests/test_ablation.py``'s, reused deliberately: the arithmetic
under test lives in ``ah.eval.ablation`` and is exercised there, so a second builder
here would be a second thing that can disagree about what a report looks like.
"""

from __future__ import annotations

import math

import pytest

from ah.eval import g2
from test_ablation import D4, UNCOMPUTABLE, make_report

SEALED = dict(
    d4_strategy_ids=D4,
    uncomputable_strategy_ids=UNCOMPUTABLE,
    minimum_seeds=3,
    expected_n_paths=1024,
    expected_months=120,
    expected_vintage_id="2026-07-26.1",
)


def _evaluate(challenger, benchmark, **over):
    kwargs = {**SEALED, **over}
    return g2.evaluate(
        challenger_id="challenger",
        benchmark_id="bootstrap-v1",
        challenger_reports=challenger,
        benchmark_reports=benchmark,
        **kwargs,
    )


def _winning_pair(n=3):
    """A challenger that beats the benchmark on every route, at ``n`` seeds."""
    challenger = [make_report(elicitability=(1.0, 1.0, 1.0)) for _ in range(n)]
    benchmark = [make_report(elicitability=(2.0, 2.0, 2.0)) for _ in range(n)]
    return challenger, benchmark


# --------------------------------------------------------------------------- #
# the verdict
# --------------------------------------------------------------------------- #


def test_all_four_clauses_holding_gives_promote() -> None:
    v = _evaluate(*_winning_pair())
    assert v.verdict == g2.PROMOTE
    assert v.promoted is True
    assert all(c["holds"] for c in v.clauses.values())


def test_the_verdict_is_ship_benchmark_when_any_single_clause_fails() -> None:
    """ "PROMOTE ... only if ALL FOUR of the following hold ... Otherwise
    SHIP-BENCHMARK." Each clause is failed in isolation, so no clause can be
    carried by another."""
    challenger, benchmark = _winning_pair()
    assert _evaluate(challenger, benchmark).verdict == g2.PROMOTE

    # clause (4): a single money-pump violation, everything else untouched.
    c4 = [make_report(elicitability=(1.0, 1.0, 1.0), money_pump=1.0) for _ in range(3)]
    assert _evaluate(c4, benchmark).verdict == g2.SHIP_BENCHMARK

    # clause (3): memorization enforce failing.
    c3 = [make_report(elicitability=(1.0, 1.0, 1.0), memorization_passed=False) for _ in range(3)]
    assert _evaluate(c3, benchmark).verdict == g2.SHIP_BENCHMARK


def test_a_ship_benchmark_verdict_still_reports_every_clause() -> None:
    """A SHIP-BENCHMARK is "a successful outcome of Step 2, not a failure of it", so
    the evidence for it must be as complete as for a promotion."""
    challenger = [make_report(elicitability=(9.0, 9.0, 9.0)) for _ in range(3)]
    benchmark = [make_report(elicitability=(1.0, 1.0, 1.0)) for _ in range(3)]
    v = _evaluate(challenger, benchmark)
    assert v.verdict == g2.SHIP_BENCHMARK
    assert set(v.clauses) == {
        "1_tail_superiority",
        "2_no_enforce_regression",
        "3_memorization_below_floor",
        "4_zero_constraint_violations",
    }
    assert v.clauses["1_tail_superiority"]["per_seed"]
    assert v.to_dict()["verdict"] == g2.SHIP_BENCHMARK


# --------------------------------------------------------------------------- #
# beats_definition
# --------------------------------------------------------------------------- #


def test_a_tie_is_not_a_beat_because_the_seal_says_strictly_lower() -> None:
    """(i) OBJECTIVE: "C's mean elicitability_score ... is STRICTLY LOWER than B's"."""
    same = [make_report(elicitability=(2.0, 2.0, 2.0)) for _ in range(3)]
    other = [make_report(elicitability=(2.0, 2.0, 2.0)) for _ in range(3)]
    v = _evaluate(same, other)
    c1 = v.clauses["1_tail_superiority"]
    assert [s["is_beat"] for s in c1["per_seed"]] == [False, False, False]
    assert c1["route_every_seed"] is False
    assert c1["holds"] is False


def test_a_nan_on_either_side_makes_the_seed_not_a_beat_not_a_tie() -> None:
    """ "if either side's elicitability_score is NaN for any strategy in the comparison
    set, the seed is NOT a beat -- not a tie, not an exclusion.\""""
    challenger = [make_report(elicitability=(1.0, float("nan"), 1.0))] + [
        make_report(elicitability=(1.0, 1.0, 1.0)) for _ in range(2)
    ]
    benchmark = [make_report(elicitability=(2.0, 2.0, 2.0)) for _ in range(3)]
    v = _evaluate(challenger, benchmark)
    c1 = v.clauses["1_tail_superiority"]
    assert c1["per_seed"][0]["has_nan"] is True
    assert c1["per_seed"][0]["is_beat"] is False
    # NOT an exclusion: the seed stays in the pooled arithmetic and poisons it.
    assert math.isnan(c1["per_seed"][0]["d"])
    assert c1["nan_rule_fired"] is True
    assert c1["route_every_seed"] is False
    assert c1["route_pooled"] is False
    assert v.verdict == g2.SHIP_BENCHMARK


def test_a_nan_on_the_benchmark_side_also_kills_the_seed() -> None:
    """ "either side" -- the rule is symmetric, and a benchmark NaN is not a free win."""
    challenger = [make_report(elicitability=(1.0, 1.0, 1.0)) for _ in range(3)]
    benchmark = [make_report(elicitability=(2.0, float("nan"), 2.0))] + [
        make_report(elicitability=(2.0, 2.0, 2.0)) for _ in range(2)
    ]
    v = _evaluate(challenger, benchmark)
    c1 = v.clauses["1_tail_superiority"]
    assert c1["per_seed"][0]["has_nan"] is True
    assert c1["per_seed"][0]["is_beat"] is False
    assert v.verdict == g2.SHIP_BENCHMARK


# --------------------------------------------------------------------------- #
# clause (1): the two routes
# --------------------------------------------------------------------------- #


def test_the_pooled_route_requires_clause_ii_in_every_seed() -> None:
    """ "Clause (ii) must still hold in every seed for the pooled route -- the pooled
    arm relaxes the objective, not the band-regression check."

    This is the sentence that separates this executor from ABLATION.md's table, which
    reports the pooled beat and clause (ii) as independent columns.
    """
    # Challenger wins the objective everywhere, but regresses on bands in seed 1.
    challenger = [
        make_report(elicitability=(1.0, 1.0, 1.0), td_values=(0.1, 0.2, 0.3)),
        make_report(elicitability=(1.0, 1.0, 1.0), td_values=(0.9, 0.9, 0.9)),
        make_report(elicitability=(1.0, 1.0, 1.0), td_values=(0.1, 0.2, 0.3)),
    ]
    benchmark = [
        make_report(elicitability=(2.0, 2.0, 2.0), td_values=(0.1, 0.2, 0.3)) for _ in range(3)
    ]
    v = _evaluate(challenger, benchmark)
    c1 = v.clauses["1_tail_superiority"]
    assert c1["clause_ii_every_seed"] is False
    assert c1["pooled_arithmetic"]["pooled_beat"] is True  # the objective half alone
    assert c1["route_pooled"] is False  # ...but clause (ii) vetoes it
    assert c1["route_every_seed"] is False
    assert c1["holds"] is False
    assert v.verdict == g2.SHIP_BENCHMARK


def test_the_pooled_route_can_carry_clause_one_without_every_seed() -> None:
    """ "or, pooled across seeds, beats it by more than the cross-seed dispersion" --
    the two routes are alternatives, and the note says which one carried."""
    # Seed 0 ties (not a beat); the other two win by enough that the pooled mean
    # exceeds the dispersion.
    challenger = [
        make_report(elicitability=(2.0, 2.0, 2.0)),
        make_report(elicitability=(1.0, 1.0, 1.0)),
        make_report(elicitability=(1.0, 1.0, 1.0)),
    ]
    benchmark = [make_report(elicitability=(2.0, 2.0, 2.0)) for _ in range(3)]
    v = _evaluate(challenger, benchmark)
    c1 = v.clauses["1_tail_superiority"]
    assert c1["route_every_seed"] is False
    if c1["route_pooled"]:
        assert c1["holds"] is True
        assert any("POOLED route only" in n for n in v.notes)


def test_the_pooled_inequality_is_both_halves_at_ddof_one() -> None:
    """ "C beats B pooled iff mean_s(d_s) < 0 AND |mean_s(d_s)| > sd_s(d_s) with sd
    computed at ddof=1." Both halves are reported separately."""
    challenger, benchmark = _winning_pair()
    pa = _evaluate(challenger, benchmark).clauses["1_tail_superiority"]["pooled_arithmetic"]
    assert pa["mean_is_negative"] is True
    assert pa["n_seeds"] == 3
    assert "sd_d_ddof1" in pa
    assert pa["pooled_beat"] is (pa["mean_is_negative"] and pa["abs_mean_exceeds_sd"])


# --------------------------------------------------------------------------- #
# clause (2): the two readings, reported rather than silently narrowed
# --------------------------------------------------------------------------- #


def test_clause_two_reports_both_readings_and_flags_a_disagreement() -> None:
    """ "NO ENFORCE-TIER REGRESSION on the monthly or 1_5yr tiers relative to
    bootstrap-v1" admits a by-count and a by-metric reading. Choosing one with results
    in hand is the forking path the seal exists to close (cf. S2-HORIZON-TIER), so both
    are computed and a disagreement is surfaced as a note."""
    challenger, benchmark = _winning_pair()
    c2 = _evaluate(challenger, benchmark).clauses["2_no_enforce_regression"]
    assert set(c2) >= {"route_by_count", "route_by_metric", "readings_agree", "per_seed"}
    assert c2["tiers"] == ["monthly", "1_5yr"]
    assert c2["readings_agree"] is True
    assert c2["holds"] is True


def test_clause_two_holds_is_the_stricter_reading() -> None:
    """Where the readings could differ, ``holds`` is their AND -- the by-metric
    reading, which forbids trading one failure for another."""
    challenger, benchmark = _winning_pair()
    c2 = _evaluate(challenger, benchmark).clauses["2_no_enforce_regression"]
    assert c2["holds"] == (c2["route_by_count"] and c2["route_by_metric"])


# --------------------------------------------------------------------------- #
# clauses (3) and (4): absolute, not comparative
# --------------------------------------------------------------------------- #


def test_clause_three_is_absolute_not_relative_to_the_benchmark() -> None:
    """ "every memorization-tier enforce threshold passes, in every seed" -- the
    benchmark resamples history verbatim and is not the standard here."""
    challenger = [
        make_report(elicitability=(1.0, 1.0, 1.0), memorization_passed=False) for _ in range(3)
    ]
    benchmark = [
        make_report(elicitability=(2.0, 2.0, 2.0), memorization_passed=False) for _ in range(3)
    ]
    v = _evaluate(challenger, benchmark)
    assert v.clauses["3_memorization_below_floor"]["holds"] is False
    assert v.verdict == g2.SHIP_BENCHMARK


def test_clause_four_demands_exact_zero_in_every_seed() -> None:
    """ "money_pump_violations and floor_violations are exactly 0 in every seed"."""
    challenger = [
        make_report(elicitability=(1.0, 1.0, 1.0)),
        make_report(elicitability=(1.0, 1.0, 1.0), money_pump=1.0),
        make_report(elicitability=(1.0, 1.0, 1.0)),
    ]
    benchmark = [make_report(elicitability=(2.0, 2.0, 2.0)) for _ in range(3)]
    v = _evaluate(challenger, benchmark)
    c4 = v.clauses["4_zero_constraint_violations"]
    assert c4["holds"] is False
    assert c4["per_seed"][1]["money_pump_violations"]["value"] == 1.0
    assert v.verdict == g2.SHIP_BENCHMARK


def test_clause_three_refuses_a_report_with_no_memorization_thresholds() -> None:
    """Clause (3) "cannot be satisfied by absence" -- the same posture
    ``constraint_violations`` takes for a missing metric."""
    rep = make_report(elicitability=(1.0, 1.0, 1.0))
    tiers = rep["unfiltered"]["tiers"]
    for tier, rows in tiers.items():
        tiers[tier] = [r for r in rows if r["suite"] != "memorization"]
    with pytest.raises(g2.G2Error, match="cannot be satisfied by absence"):
        g2.clause_3_memorization([rep])


# --------------------------------------------------------------------------- #
# criterion_bearing_runs_only -- the refusal the seal REQUIRED of WP2.11
# --------------------------------------------------------------------------- #


def test_a_wrong_size_run_is_refused_rather_than_judged() -> None:
    """``criterion_bearing_runs_only``: g2.py "MUST refuse a report where it is
    false". Before WP2.11 no such refusal existed anywhere."""
    challenger, benchmark = _winning_pair()
    challenger[1] = make_report(elicitability=(1.0, 1.0, 1.0), n_paths=64)
    with pytest.raises(g2.G2Error, match="not criterion-bearing"):
        _evaluate(challenger, benchmark)


def test_a_superseded_vintage_is_refused_rather_than_judged() -> None:
    """The vintage half of the same check -- added at the WP2.3 final pass (RFR-71),
    and the reason a full-size run against a superseded vintage is not admissible."""
    challenger, benchmark = _winning_pair()
    challenger[0] = make_report(elicitability=(1.0, 1.0, 1.0), vintage_id="2026-07-24")
    with pytest.raises(g2.G2Error, match="not criterion-bearing"):
        _evaluate(challenger, benchmark)


def test_the_benchmark_side_is_refused_too() -> None:
    """The refusal is over every report entering the verdict, not only the
    challenger's -- a verdict against an inadmissible benchmark is inadmissible."""
    challenger, benchmark = _winning_pair()
    benchmark[2] = make_report(elicitability=(2.0, 2.0, 2.0), months=60)
    with pytest.raises(g2.G2Error, match="bootstrap-v1:s2"):
        _evaluate(challenger, benchmark)


# --------------------------------------------------------------------------- #
# admissibility of the inputs themselves
# --------------------------------------------------------------------------- #


def test_fewer_than_minimum_seeds_is_refused() -> None:
    """ "minimum_seeds: 3" -- and the plan's reason: "the multi-seed rule exists because
    one seed's victory is noise; do not argue with it at G2 time.\""""
    challenger, benchmark = _winning_pair(n=2)
    with pytest.raises(g2.G2Error, match="minimum_seeds"):
        _evaluate(challenger, benchmark)


def test_unequal_report_counts_are_refused() -> None:
    """The rule pairs a benchmark seed with each challenger seed; an unpaired seed has
    no d_s and must not be silently dropped."""
    challenger, benchmark = _winning_pair()
    with pytest.raises(g2.G2Error, match="pairs them per seed"):
        _evaluate(challenger, benchmark[:2])


def test_a_comparison_set_mismatch_is_refused() -> None:
    """Clause (ii) counts comparison-set names outside their bands, so two reports
    carrying DIFFERENT names produce counts that are not comparable.

    The guard is on the resolved NAMES, not on ``strategy_ids``: the latter are derived
    from the sealed arguments alone and are identical by construction, so a guard on
    them would never fire. This test exists partly to keep that true -- if it starts
    passing for the wrong reason, the guard has moved back to the vacuous check.
    """
    challenger, benchmark = _winning_pair()
    tiers = benchmark[0]["unfiltered"]["tiers"]
    for tier, rows in tiers.items():
        tiers[tier] = [r for r in rows if not r["name"].endswith("tail_dependence_upper")]
    with pytest.raises(g2.G2Error, match="comparison sets differ"):
        g2.seed_beat(
            challenger[0],
            benchmark[0],
            seed_index=0,
            d4_strategy_ids=D4,
            uncomputable_strategy_ids=UNCOMPUTABLE,
            which="unfiltered",
        )


def test_clause_one_needs_at_least_one_seed() -> None:
    with pytest.raises(g2.G2Error, match="at least one seed"):
        g2.clause_1_tail_superiority([])


# --------------------------------------------------------------------------- #
# the token boundary, unchanged by WP2.11
# --------------------------------------------------------------------------- #


def test_the_token_mint_still_exists_and_is_not_used_by_the_rule() -> None:
    """``AM-2026-07-31-002``: the holdout was not spent and remains unspent. The
    capability stays so a later gate that SPECIFIES the evaluation can use it; no
    clause reads it, and nothing in :func:`ah.eval.g2.evaluate` mints one."""
    import inspect

    token = g2.final_evaluation_token()
    assert token.purpose == "final-evaluation"
    source = inspect.getsource(g2.evaluate)
    assert "final_evaluation_token" not in source
    assert "holdout" not in source.lower()
