"""The G2 decision rule + the sanctioned holdout-token mint (STEP2 §WP2.1, §WP2.11).

This module is deliberately the *only* place a :class:`~ah.splits.FinalEvaluationToken`
is created: the touch-once holdout is reachable only from here, and the import-graph
test proves no training/generator module imports this module.

WP2.11 adds the executable form of ``multi_seed_decision_rule``. What that block seals
is the rule IN WORDS, frozen before any evidence existed; this module must not diverge
from those words, and ``g2.py`` is itself hashed so it cannot without a dated amendment
and a re-seal. Every clause below quotes the sentence it implements.

**The arithmetic lives in** :mod:`ah.eval.ablation` **and is not restated here.**
``comparison_set``, ``clause_i``, ``clause_ii``, ``pooled_difference``, ``enforce_rows``,
``memorization_enforce``, ``constraint_violations`` and ``criterion_bearing`` are that
module's, sealed alongside this one since ``AM-2026-07-31-001``. This module composes
them into a verdict and adds the one check the seal demands of WP2.11 specifically —
the refusal of any report that is not criterion-bearing. Composing rather than
reimplementing is deliberate: two implementations of one sealed inequality is two things
that can disagree.

**THE HOLDOUT IS NOT READ HERE, AND NO CLAUSE NEEDS IT.** All four clauses are computed
from stored battery reports of the WP2.10 ablation grid, judged against a
train+validation reference. ``AM-2026-07-31-002`` records that the holdout was not spent
at G2 and remains unspent: the seal specified its span, its guard and its at-most-once
budget, but never what the one permitted evaluation computes. :func:`final_evaluation_token`
is left intact and unused — the capability stays, so that a later gate which *does*
specify the test can use it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ah.eval import ablation
from ah.splits import FinalEvaluationToken

#: ``rule`` clause (2) names these two tiers and no others.
REGRESSION_TIERS: tuple[str, ...] = ("monthly", "1_5yr")

PROMOTE = "PROMOTE"
SHIP_BENCHMARK = "SHIP-BENCHMARK"


class G2Error(RuntimeError):
    """Raised when the rule cannot be executed as sealed."""


def final_evaluation_token() -> FinalEvaluationToken:
    """Mint the one-time holdout access token. Call site is WP2.11's G2 evaluation only."""
    return FinalEvaluationToken(purpose="final-evaluation")


# --------------------------------------------------------------------------- #
# criterion_bearing_runs_only -- the refusal the seal requires of WP2.11
# --------------------------------------------------------------------------- #


def require_criterion_bearing(
    reports: Mapping[str, Mapping[str, Any]],
    *,
    expected_n_paths: int,
    expected_months: int,
    expected_vintage_id: str,
) -> dict[str, Any]:
    """Refuse any non-criterion-bearing report. Sealed requirement, previously absent.

    ``multi_seed_decision_rule.criterion_bearing_runs_only`` says WP2.11's ``g2.py``
    "MUST refuse a report where it is false", and states in the same breath that the
    refusal "does not exist yet -- g2.py contains only the holdout-token mint today --
    so THAT part remains a sealed REQUIREMENT on WP2.11, not a description of a check
    already in place". This is that check.

    Raises on the first offending report rather than collecting: a run judged against
    the wrong ensemble size or a superseded vintage is not a weaker input to a verdict,
    it is not an input at all.
    """
    detail: dict[str, Any] = {}
    for label, report in reports.items():
        got = ablation.criterion_bearing(
            report,
            expected_n_paths=expected_n_paths,
            expected_months=expected_months,
            expected_vintage_id=expected_vintage_id,
        )
        detail[label] = got
        if not got.get("ok", False):
            raise G2Error(
                f"{label}: report is not criterion-bearing and may not enter the G2 "
                f"verdict (multi_seed_decision_rule.criterion_bearing_runs_only). "
                f"Conditions: {got}"
            )
    return detail


# --------------------------------------------------------------------------- #
# clause (1): tail superiority
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SeedBeat:
    """``beats_definition`` resolved for one seed."""

    seed_index: int
    #: (i) mean elicitability_score over the comparison set, challenger and benchmark.
    challenger_mean: float
    benchmark_mean: float
    #: d_s, the difference the pooled route averages. NaN if either side is NaN.
    d: float
    #: (i) holds: challenger's mean is STRICTLY LOWER.
    objective_lower: bool
    #: the sealed NaN rule fired on either side.
    has_nan: bool
    #: (ii) holds: challenger's out-of-band count <= benchmark's.
    no_band_regression: bool
    challenger_out_of_band: int
    benchmark_out_of_band: int

    @property
    def is_beat(self) -> bool:
        """A seed is a beat iff (i) AND (ii), and never when the NaN rule fired.

        ``beats_definition``: "if either side's elicitability_score is NaN for any
        strategy in the comparison set, the seed is NOT a beat -- not a tie, not an
        exclusion."
        """
        if self.has_nan:
            return False
        return self.objective_lower and self.no_band_regression


def seed_beat(
    challenger_report: Mapping[str, Any],
    benchmark_report: Mapping[str, Any],
    *,
    seed_index: int,
    d4_strategy_ids: Sequence[str],
    uncomputable_strategy_ids: Sequence[str],
    which: str = "unfiltered",
) -> SeedBeat:
    """Resolve ``beats_definition`` for one (challenger, benchmark) seed pair.

    The comparison set is resolved SEPARATELY against each report and the two must
    agree. They are built from the same sealed field, so disagreement means the two
    reports were produced against different vintages or different strategy sets — a
    condition under which "C's mean over the comparison set" and "B's mean over the
    comparison set" are not the same quantity and must not be subtracted.
    """
    c_set = ablation.comparison_set(
        challenger_report,
        d4_strategy_ids=d4_strategy_ids,
        uncomputable_strategy_ids=uncomputable_strategy_ids,
        which=which,
    )
    b_set = ablation.comparison_set(
        benchmark_report,
        d4_strategy_ids=d4_strategy_ids,
        uncomputable_strategy_ids=uncomputable_strategy_ids,
        which=which,
    )
    # NOT a check on strategy_ids: those are derived from the sealed arguments alone
    # and are identical by construction here, so guarding them would be unreachable.
    # What CAN differ is the resolved metric NAMES, which are read off each report --
    # and clause (ii) counts names outside their bands, so two reports carrying
    # different comparison-set names produce two counts that are not comparable.
    if c_set.names != b_set.names:
        only_c = sorted(set(c_set.names) - set(b_set.names))
        only_b = sorted(set(b_set.names) - set(c_set.names))
        raise G2Error(
            f"seed {seed_index}: comparison sets differ between the reports "
            f"(challenger-only {only_c}, benchmark-only {only_b}); clause (ii) would "
            f"count over different names and the two counts may not be compared"
        )

    c_i = ablation.clause_i(challenger_report, c_set, which)
    b_i = ablation.clause_i(benchmark_report, b_set, which)
    c_ii = ablation.clause_ii(challenger_report, c_set, which)
    b_ii = ablation.clause_ii(benchmark_report, b_set, which)

    has_nan = bool(c_i["has_nan"] or b_i["has_nan"])
    c_mean = float(c_i["mean"])
    b_mean = float(b_i["mean"])
    d = c_mean - b_mean
    c_out = int(c_ii["count"])
    b_out = int(b_ii["count"])
    return SeedBeat(
        seed_index=seed_index,
        challenger_mean=c_mean,
        benchmark_mean=b_mean,
        d=d,
        # STRICTLY lower, per the seal. A tie is not a beat.
        objective_lower=bool(c_mean < b_mean) and not has_nan,
        has_nan=has_nan,
        no_band_regression=bool(c_out <= b_out),
        challenger_out_of_band=c_out,
        benchmark_out_of_band=b_out,
    )


def clause_1_tail_superiority(beats: Sequence[SeedBeat]) -> dict[str, Any]:
    """``rule`` (1): beats in EVERY seed, OR the pooled route.

    Sealed: "the challenger beats bootstrap-v1 on the tail tier in EVERY seed; or,
    pooled across seeds, beats it by more than the cross-seed dispersion of the
    difference." And, from ``beats_definition``: "Clause (ii) must still hold in every
    seed for the pooled route -- the pooled arm relaxes the objective, not the
    band-regression check."

    Both routes are reported whatever the outcome, so a reader sees which one carried
    the verdict rather than only that one did.
    """
    if not beats:
        raise G2Error("clause (1) needs at least one seed")
    every_seed = all(b.is_beat for b in beats)

    ds = [b.d for b in beats]
    any_nan = any(b.has_nan for b in beats)
    pooled = ablation.pooled_difference(ds)
    clause_ii_every_seed = all(b.no_band_regression for b in beats)
    # A NaN anywhere makes no seed a beat, and mean_s(d_s) is NaN too, so the pooled
    # inequality is False by construction — asserted rather than assumed.
    pooled_route = bool(pooled["pooled_beat"] and clause_ii_every_seed and not any_nan)
    if any_nan and pooled_route:  # pragma: no cover - defensive
        raise G2Error("NaN present yet the pooled route reported a beat; refusing")

    return {
        "n_seeds": len(beats),
        "per_seed": [
            {
                "seed_index": b.seed_index,
                "challenger_mean": b.challenger_mean,
                "benchmark_mean": b.benchmark_mean,
                "d": b.d,
                "objective_lower": b.objective_lower,
                "has_nan": b.has_nan,
                "no_band_regression": b.no_band_regression,
                "challenger_out_of_band": b.challenger_out_of_band,
                "benchmark_out_of_band": b.benchmark_out_of_band,
                "is_beat": b.is_beat,
            }
            for b in beats
        ],
        "route_every_seed": every_seed,
        "route_pooled": pooled_route,
        "pooled_arithmetic": pooled,
        "clause_ii_every_seed": clause_ii_every_seed,
        "nan_rule_fired": any_nan,
        "holds": bool(every_seed or pooled_route),
    }


# --------------------------------------------------------------------------- #
# clause (2): no enforce-tier regression
# --------------------------------------------------------------------------- #


def clause_2_no_enforce_regression(
    challenger_reports: Sequence[Mapping[str, Any]],
    benchmark_reports: Sequence[Mapping[str, Any]],
    *,
    which: str = "unfiltered",
) -> dict[str, Any]:
    """``rule`` (2): "NO ENFORCE-TIER REGRESSION on the monthly or 1_5yr tiers
    relative to bootstrap-v1."

    THE SENTENCE ADMITS TWO READINGS AND THIS FUNCTION COMPUTES BOTH, because choosing
    one with results in hand is the forking path the seal exists to close — the same
    posture ``S2-HORIZON-TIER`` took for "the horizon tier":

    * BY COUNT: the challenger's number of failing enforce metrics on those tiers is
      ``<=`` the benchmark's, per seed.
    * BY METRIC: no metric that the benchmark PASSES is FAILED by the challenger, per
      seed. Strictly stronger — it forbids trading one failure for another.

    ``holds`` is the AND of both, i.e. the stricter reading, because where the two
    disagree only the stricter one is a regression-free result under every reading.
    ``readings_agree`` is reported so a disagreement is visible rather than silently
    resolved; if they ever disagree, that is a finding for the evidence document and
    the narrowing belongs in a dated amendment, not here.
    """
    if len(challenger_reports) != len(benchmark_reports):
        raise G2Error("clause (2) needs one benchmark report per challenger report")

    per_seed: list[dict[str, Any]] = []
    for idx, (c_rep, b_rep) in enumerate(zip(challenger_reports, benchmark_reports, strict=True)):
        c_rows = {
            r["name"]: r for r in ablation.enforce_rows(c_rep, tiers=REGRESSION_TIERS, which=which)
        }
        b_rows = {
            r["name"]: r for r in ablation.enforce_rows(b_rep, tiers=REGRESSION_TIERS, which=which)
        }
        c_failed = {n for n, r in c_rows.items() if r["passed"] is False}
        b_failed = {n for n, r in b_rows.items() if r["passed"] is False}
        newly_failed = sorted(c_failed - b_failed)
        by_count = bool(len(c_failed) <= len(b_failed))
        by_metric = not newly_failed
        per_seed.append(
            {
                "seed_index": idx,
                "challenger_failures": sorted(c_failed),
                "benchmark_failures": sorted(b_failed),
                "n_challenger_failures": len(c_failed),
                "n_benchmark_failures": len(b_failed),
                "newly_failed_vs_benchmark": newly_failed,
                "by_count": by_count,
                "by_metric": by_metric,
                "readings_agree": bool(by_count == by_metric),
            }
        )

    by_count_all = all(s["by_count"] for s in per_seed)
    by_metric_all = all(s["by_metric"] for s in per_seed)
    return {
        "tiers": list(REGRESSION_TIERS),
        "per_seed": per_seed,
        "route_by_count": by_count_all,
        "route_by_metric": by_metric_all,
        "readings_agree": bool(by_count_all == by_metric_all),
        "holds": bool(by_count_all and by_metric_all),
    }


# --------------------------------------------------------------------------- #
# clauses (3) and (4): absolute, not comparative
# --------------------------------------------------------------------------- #


def clause_3_memorization(
    challenger_reports: Sequence[Mapping[str, Any]], *, which: str = "unfiltered"
) -> dict[str, Any]:
    """``rule`` (3): "every memorization-tier enforce threshold passes, in every seed."

    Absolute, not relative to the benchmark: the benchmark resamples history verbatim
    and is not the standard a challenger's memorization is measured against.
    """
    per_seed = []
    for idx, rep in enumerate(challenger_reports):
        rows = ablation.memorization_enforce(rep, which)
        failed = [r["name"] for r in rows if r["passed"] is False]
        per_seed.append(
            {
                "seed_index": idx,
                "n_thresholds": len(rows),
                "failed": failed,
                "holds": not failed,
            }
        )
        if not rows:
            raise G2Error(
                f"seed {idx}: no memorization enforce thresholds found; clause (3) "
                f"cannot be satisfied by absence"
            )
    return {"per_seed": per_seed, "holds": all(s["holds"] for s in per_seed)}


def clause_4_constraints(
    challenger_reports: Sequence[Mapping[str, Any]], *, which: str = "unfiltered"
) -> dict[str, Any]:
    """``rule`` (4): "money_pump_violations and floor_violations are exactly 0 in every
    seed." A missing metric raises in :func:`ah.eval.ablation.constraint_violations`."""
    per_seed = []
    for idx, rep in enumerate(challenger_reports):
        got = ablation.constraint_violations(rep, which)
        per_seed.append({"seed_index": idx, **got})
    return {"per_seed": per_seed, "holds": all(s["all_zero"] for s in per_seed)}


# --------------------------------------------------------------------------- #
# the verdict
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Verdict:
    """The sealed rule's output. ``PROMOTE`` only if all four clauses hold."""

    challenger_id: str
    benchmark_id: str
    verdict: str
    clauses: dict[str, Any] = field(default_factory=dict)
    criterion_bearing: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @property
    def promoted(self) -> bool:
        return self.verdict == PROMOTE

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenger_id": self.challenger_id,
            "benchmark_id": self.benchmark_id,
            "verdict": self.verdict,
            "clauses": self.clauses,
            "criterion_bearing": self.criterion_bearing,
            "notes": list(self.notes),
        }


def evaluate(
    *,
    challenger_id: str,
    benchmark_id: str,
    challenger_reports: Sequence[Mapping[str, Any]],
    benchmark_reports: Sequence[Mapping[str, Any]],
    d4_strategy_ids: Sequence[str],
    uncomputable_strategy_ids: Sequence[str],
    minimum_seeds: int,
    expected_n_paths: int,
    expected_months: int,
    expected_vintage_id: str,
    which: str = "unfiltered",
) -> Verdict:
    """Execute ``multi_seed_decision_rule`` and return the verdict.

    "PROMOTE the challenger over bootstrap-v1 only if ALL FOUR of the following hold
    ... Otherwise SHIP-BENCHMARK: bootstrap-v1 remains the default generator_id and
    G2-EVIDENCE.md says so plainly. A SHIP-BENCHMARK verdict is a successful outcome of
    Step 2, not a failure of it."

    Order of operations is deliberate: ``minimum_seeds`` and the criterion-bearing
    refusal are checked BEFORE any clause is computed, so an inadmissible input never
    produces a number that could be quoted.
    """
    if len(challenger_reports) != len(benchmark_reports):
        raise G2Error(
            f"{len(challenger_reports)} challenger reports against "
            f"{len(benchmark_reports)} benchmark reports; the rule pairs them per seed"
        )
    if len(challenger_reports) < minimum_seeds:
        raise G2Error(
            f"multi_seed_decision_rule.minimum_seeds is {minimum_seeds}; got "
            f"{len(challenger_reports)} seeds. The multi-seed rule exists because one "
            f"seed's victory is noise; it may not be executed on fewer."
        )

    labelled: dict[str, Mapping[str, Any]] = {}
    for idx, rep in enumerate(challenger_reports):
        labelled[f"{challenger_id}:s{idx}"] = rep
    for idx, rep in enumerate(benchmark_reports):
        labelled[f"{benchmark_id}:s{idx}"] = rep
    cb = require_criterion_bearing(
        labelled,
        expected_n_paths=expected_n_paths,
        expected_months=expected_months,
        expected_vintage_id=expected_vintage_id,
    )

    beats = [
        seed_beat(
            c_rep,
            b_rep,
            seed_index=idx,
            d4_strategy_ids=d4_strategy_ids,
            uncomputable_strategy_ids=uncomputable_strategy_ids,
            which=which,
        )
        for idx, (c_rep, b_rep) in enumerate(
            zip(challenger_reports, benchmark_reports, strict=True)
        )
    ]

    c1 = clause_1_tail_superiority(beats)
    c2 = clause_2_no_enforce_regression(challenger_reports, benchmark_reports, which=which)
    c3 = clause_3_memorization(challenger_reports, which=which)
    c4 = clause_4_constraints(challenger_reports, which=which)
    clauses = {
        "1_tail_superiority": c1,
        "2_no_enforce_regression": c2,
        "3_memorization_below_floor": c3,
        "4_zero_constraint_violations": c4,
    }
    all_hold = all(c["holds"] for c in clauses.values())

    notes: list[str] = []
    if not c2["readings_agree"]:
        notes.append(
            "clause (2)'s two readings DISAGREE (by-count vs by-metric); the stricter "
            "by-metric reading governs `holds`. This is a finding for G2-EVIDENCE.md "
            "and narrowing the sealed sentence belongs in a dated amendment."
        )
    if c1["route_pooled"] and not c1["route_every_seed"]:
        notes.append(
            "clause (1) carried on the POOLED route only, not in every seed. Read it "
            "with benchmark_draw_span_bias and the restricted-window comparison."
        )
    if any(math.isnan(b.d) for b in beats):  # pragma: no cover - defensive
        notes.append("a per-seed difference is NaN; the NaN rule made that seed not a beat.")

    return Verdict(
        challenger_id=challenger_id,
        benchmark_id=benchmark_id,
        verdict=PROMOTE if all_hold else SHIP_BENCHMARK,
        clauses=clauses,
        criterion_bearing=cb,
        notes=tuple(notes),
    )
