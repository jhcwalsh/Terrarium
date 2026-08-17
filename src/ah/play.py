"""The playable institution, on the Step-3 twin (register ER-3).

The play surface used to score on :mod:`ah.core.institution` — Step 0's toy,
which holds eight asset weights, rebalances them, and has no cash. That made a
secondary sale a slider rather than a decision: nothing could ever *need* the
liquidity, because nothing was ever owed. Meanwhile Step 3 had already built
the real thing in :mod:`ah.port` — a cash account, commitment cohorts with
capital calls, distributions, spending off smoothed marks, and a forced-sale
waterfall — and the play surface was not using it.

This module is the orchestrator that connects them: it drives ``ah.port``'s
quarterly waterfall from a toy-engine tape, so the player's decisions land on
an institution that can actually run out of money.

**What is real here that was not before**

- Capital calls must be *funded*. Cash pays them, and if cash is short the
  waterfall sells — liquid holdings first, then a forced secondary at the
  policy haircut. A forced sale is a consequence, not a button.
- Distributions arrive on the cohort's own bow, accelerated or starved by the
  market state through tier 1's linkage (``f_call``/``f_dist`` consume
  CONTINUOUS states only — drawdown depth and spread ratio, never a regime
  label).
- Spending rides the **reported** trailing average, so it barely falls in a
  crash while true value does — §7's mechanic, and the reason coverage looks
  healthier than it is exactly when it matters.

**Scoring identity.** This changes what a decision is worth, so sessions
scored here carry :data:`PLAY_ALPHA_VERSION` rather than the toy's stamp, and
their leaderboard rows cannot mix with toy-scored ones. It deliberately does
NOT touch ``ah.eval.decision_metrics.DECISION_ALPHA_VERSION``: that names Step
5's research definition and sits inside the G5 seal
(``step5-evaluation-protocol.yaml``), where a change would need an amendment
and would mean something different from what happened here.

**Simplifications, stated.** Private cohorts start mid-life rather than as a
new programme, so the book opens at its target private weight instead of
ramping into it over a decade — an ongoing institution, which is what the
world describes. Reported marks come from the toy tape's own appraisal
smoothing rather than WP3.3's fitted kernel, because the tape is what the
player is shown and the two must agree.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ah.core.engine import EnginePaths
from ah.core.institution import decision_months
from ah.port.book import CommitmentPlan, OpeningBook, default_band
from ah.port.cashflow_tier1 import f_call as tier1_f_call
from ah.port.cashflow_tier1 import f_dist as tier1_f_dist
from ah.port.cohort import ClosedEndCohort
from ah.port.engine import Policy, PortfolioEngine
from ah.port.portfolio import Portfolio
from ah.port.sleeves import LiquidSleeve

__all__ = [
    "LIQUID_ASSETS",
    "PLAY_ALPHA_VERSION",
    "PRIVATE_ASSETS",
    "START_CASH",
    "START_TARGETS",
    "PlayAttribution",
    "PlayQuarter",
    "PlayResult",
    "default_commitment_plan",
    "default_opening_book",
    "play_alpha",
    "simulate_play",
    "window_contributions_play",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE = _REPO_ROOT / "fixtures" / "state"

#: The product's own alpha identity. NOT ah.eval.decision_metrics's constant,
#: which names Step 5's research definition and is sealed under G5.
# port-v4: the opening private book is a STAGGERED ladder of vintages rather
# than three clones of one mid-life cohort (ladder-01), so the twin the player
# is scored against holds a different institution from its first quarter —
# alpha changes meaning and old rows must not share a leaderboard with new
# ones. (port-v3 was sp-01's pacing flex + the lever; port-v2 the ER-6
# close-out; port-v1 the first cashflow twin. Leaderboards restart per stamp;
# old rows stay readable.)
PLAY_ALPHA_VERSION = "port-v4-ladder"

LIQUID_ASSETS: tuple[str, ...] = ("equity", "bonds", "hy", "commodities", "reits")
PRIVATE_ASSETS: tuple[str, ...] = ("pe", "pc", "re")

#: Opening book, in points of 100.
#:
#: NOT the toy's START_MIX, deliberately. The toy holds 45 points in private
#: assets, which is outside ``Policy.private_weight_range``'s (0.15, 0.40)
#: on day one — the toy could hold it because it had no policy band, no cash
#: account and nothing that could force a sale. On the real twin an opening
#: breach compounds: calls arrive against a shrinking liquid leg and the
#: waterfall force-sells, which was measured at 29 forced quarters out of 40
#: before this was corrected. The book now opens at 35 points private, inside
#: the band, with room for the denominator effect to move it without an
#: instant breach.
START_TARGETS: dict[str, float] = {
    "equity": 33.0,
    "bonds": 12.0,
    "hy": 5.0,
    "commodities": 5.0,
    "reits": 8.0,
    "pe": 20.0,
    "pc": 8.0,
    "re": 7.0,
}
START_CASH = 2.0

#: The spread a "normal" credit market prices, for tier 1's spread_ratio.
_SPREAD_REFERENCE_BPS = 400.0

#: A private programme is a LADDER, not a single fund. Without new vintages
#: the opening cohorts reach terminal liquidation around year 5 and the
#: institution spends the back half of the decade with no private assets, no
#: calls and no distributions at all — which is what the first run of this
#: module showed, and is not an institution anyone would recognise. Each year
#: a new vintage is committed at this fraction of the sleeve's target NAV,
#: which sustains the weight against a ten-year life.
_ANNUAL_COMMITMENT_RATE = 0.18
_COMMITMENT_QUARTERS = 4  # commit once a year

#: owner-ruled 2026-08-16 (D-SP-6 session): the default commitment schedule
#: escalates with the plan's expected growth so the programme keeps pace with
#: a growing book instead of shrinking relative to it.
EXPECTED_PLAN_GROWTH = 0.06

#: DN-5 §2.1 (sp-01): the POLICY twin flexes its pacing —
#: ``target = base_pace * g(w_policy - w_reported)`` with ``g`` clipped to
#: this band. Never zero (a twin that cuts to nothing reproduces 2009's
#: most-criticised behaviour), never doubled. DN-5 leaves g's form open;
#: DECLARED here: linear, ``1 + PACING_SENSITIVITY * gap`` — ten points
#: overweight throttles commitments by 40%. The policy private weight is the
#: t0 plan's own private share: the SAA expressed in commitment terms.
PACING_BAND: tuple[float, float] = (0.5, 1.5)
PACING_SENSITIVITY = 4.0

#: The player's commitment lever (E1): a structured decision
#: ``{"action": "commit", "commitments": {sleeve: points}}`` at a window
#: overrides the NEXT commitment event's per-sleeve points. DECLARED bounds
#: (recorded): 0 <= points <= COMMIT_CAP_MULTIPLE x the sleeve's plan pace.
COMMIT_CAP_MULTIPLE = 2.0


#: A structured decision may carry any public action (or plain "commit",
#: which trades nothing) alongside its commitments — the kickoff's "four
#: public actions PLUS the commitment lever" means plus, not instead.
_KNOWN_ACTIONS = frozenset({"hold", "derisk", "leanin", "secondary", "commit"})


def _action_name(action: str | Mapping[str, Any]) -> str:
    return action if isinstance(action, str) else str(action.get("action"))


def _policy_private_weight(targets: Mapping[str, float], cash: float = START_CASH) -> float:
    """DN-5 §2.1: the policy private weight is the t0 plan's own share.

    ``cash`` is the institution's own cash allocation, not a constant
    (su-app-07 Ruling C). ``targets`` sum to ``100 - cash`` once they are a
    book's own numbers, so hard-coding ``START_CASH`` here would skew the
    denominator — and therefore the pacing multiplier — for any book that
    holds cash other than 2.0 points.
    """
    return sum(targets[a] for a in PRIVATE_ASSETS) / (sum(targets.values()) + cash)


def _pacing_multiplier(
    w_reported: float,
    targets: Mapping[str, float],
    band: tuple[float, float],
    cash: float = START_CASH,
) -> float:
    gap = _policy_private_weight(targets, cash) - w_reported
    return min(band[1], max(band[0], 1.0 + PACING_SENSITIVITY * gap))


def plan_commitments(
    private_weight_reported: float,
    targets: Mapping[str, float] | None = None,
    *,
    pacing_rule: str = "policy",
    pacing_band: tuple[float, float] = PACING_BAND,
    cash: float = START_CASH,
) -> dict[str, float]:
    """The plan's next per-sleeve commitment points at the given reported
    weight — the server-computed pre-fill for the app's lever (sp-02).

    ``cash`` (su-app-07) is the policy cash allocation the ``targets`` sit
    beside; pass a book's own ``cash`` whenever ``targets`` came from that
    book, or the pre-fill and the engine's own multiplier disagree about the
    same number.
    """
    t = dict(targets) if targets is not None else dict(START_TARGETS)
    m = (
        1.0
        if pacing_rule == "fixed"
        else _pacing_multiplier(private_weight_reported, t, pacing_band, cash)
    )
    return {a: t[a] * _ANNUAL_COMMITMENT_RATE * m for a in PRIVATE_ASSETS}


def default_opening_book(targets: Mapping[str, float] | None = None) -> OpeningBook:
    """Today's DERIVED book, as an OpeningBook document (su-app-06).

    This is what the entry screen opens pre-filled with, and it is built by
    the same ``_seed_ladder`` the engine uses — never a second implementation,
    or the round-trip equivalence test would be comparing two copies of the
    same mistake.
    """
    t = dict(targets) if targets is not None else dict(START_TARGETS)
    base = _doc("closed-end-cohort.example.json")
    return OpeningBook(
        liquid={a: float(t[a]) for a in t if a not in PRIVATE_ASSETS},
        private={
            a: [c.to_document() for c in _seed_ladder(base, a, float(t[a]))] for a in PRIVATE_ASSETS
        },
        cash=START_CASH,
        # su-app-07 Ruling D: the entry screen pre-fills its target inputs
        # from this default and posts them back untouched by default. If the
        # served default carried `targets=None`, an untouched pre-fill would
        # digest differently from what was served, and `serve.py` would
        # demote it to practice-only.
        targets=dict(t),
        # app-open-01 delta 1 (owner-dictated 2026-08-16): the default
        # reporting band is +/-10% of the sleeve's own target, for every
        # sleeve `targets` names — cash excepted, it carries no target and
        # no band (BookEntry's own note). `default_band` is the single
        # source of this arithmetic; nothing here re-derives it.
        ranges={a: default_band(float(t[a])) for a in t},
    )


def default_commitment_plan(
    targets: Mapping[str, float] | None = None, windows: int = 9
) -> CommitmentPlan:
    """The kickoff plan: the FIXED-rule pace, escalated at the plan's own
    expected growth.

    ONE ENTRY PER DECISION WINDOW, not per calendar year. A 120-month decade
    has nine windows (months 11, 23, ... 107) and the engine fires exactly
    nine commitments (quarters 4, 8, ... 36 — ``q > 0 and q % 4 == 0``, so
    there is no commitment at q=0; the t0 book is the entered ladder, not a
    commitment). Plan index k is the k-th window, which drives the engine's
    vintage year k+1. Callers with a non-decade horizon pass
    ``windows=len(decision_months(months))``.

    The base pace uses the FIXED rule (not the POLICY flex) because the flex
    is a function of the realized reported private weight, which at kickoff
    cannot be known without simulating the tape — and simulating it here
    would leak it. ``serve.py`` already uses ``pacing_rule="fixed"`` for
    exactly this pre-quarter-0 case.

    Window k's pace is ``base * (1 + EXPECTED_PLAN_GROWTH) ** k`` —
    :data:`EXPECTED_PLAN_GROWTH` is an EXPECTATION constant declared once at
    module level, not a quantity derived from the tape, so this still does
    not leak. History: the plan was FLAT (every window equal to ``base``)
    until 2026-08-16, when the owner ruled that the default should escalate
    in line with the plan's own expected growth instead of shrinking relative
    to a growing book (D-SP-6 session) — ``CommitmentPlan``'s per-year shape
    already carried a non-flat schedule without needing a contract change.
    """
    base = plan_commitments(0.0, targets, pacing_rule="fixed")
    return CommitmentPlan(
        points={
            a: [base[a] * (1.0 + EXPECTED_PLAN_GROWTH) ** k for k in range(windows)]
            for a in PRIVATE_ASSETS
        }
    )


def validate_commitments(
    commitments: Mapping[str, float], targets: Mapping[str, float] | None = None
) -> None:
    """The lever's declared bounds, as a public check for the service layer."""
    t = dict(targets) if targets is not None else dict(START_TARGETS)
    _validate_commit_decisions({-1: {"action": "hold", "commitments": dict(commitments)}}, t)


def _validate_commit_decisions(decisions: Mapping[int, Any], targets: Mapping[str, float]) -> None:
    """Refuse malformed or out-of-bounds commit decisions loudly, up front."""
    for month, action in decisions.items():
        if isinstance(action, str):
            continue
        if not isinstance(action, Mapping) or action.get("action") not in _KNOWN_ACTIONS:
            raise ValueError(f"month {month}: unknown structured decision {action!r}")
        pts = action.get("commitments")
        if not isinstance(pts, Mapping):
            raise ValueError(f"month {month}: commit decision needs a commitments map")
        for asset, value in pts.items():
            if asset not in PRIVATE_ASSETS:
                raise ValueError(f"month {month}: commit names unknown sleeve '{asset}'")
            cap = COMMIT_CAP_MULTIPLE * targets[asset] * _ANNUAL_COMMITMENT_RATE
            if not 0.0 <= float(value) <= cap:
                raise ValueError(
                    f"month {month}: commit {asset}={value} outside [0, {cap:.4f}] "
                    "(0..2x the sleeve's plan pace, the declared bound)"
                )


#: Decision mechanics, matched to the surface's four actions.
_SHIFT_POINTS = 10.0
_SECONDARY_POINTS = 8.0

_GROWTH: tuple[str, ...] = ("equity", "pe")
_DEFENSIVE: tuple[str, ...] = ("bonds", "pc")


@dataclass(frozen=True)
class PlayQuarter:
    """One quarter of the institution's life, as the player could see it."""

    quarter: int
    month: int  # the month the quarter closes on
    cash: float
    nav_true: float
    nav_reported: float
    calls_paid: float
    distributions_received: float
    spending_paid: float
    forced_sale_total: float
    private_weight_true: float
    unfunded_total: float
    #: sp-02: the weight the COMMITTEE sees — the pacing flex reads this,
    #: and the app's lever pre-fill is computed from it server-side.
    private_weight_reported: float = 0.0
    # (defaults from here down)
    #: The two CONTINUOUS market states tier 1's linkage consumes, and the
    #: multipliers they produced. Records only — computed here already, and
    #: discarded until the credibility console needed to show the mechanism.
    #: No regime label reaches the linkage (DN-5 Delta 3, structural).
    drawdown_depth: float = 0.0
    spread_ratio: float = 1.0
    f_dist: float = 1.0
    f_call: float = 1.0
    #: New commitments made into the ladder this quarter (the pacing plan).
    new_commitments: float = 0.0
    #: What the spending rate was applied to this quarter, and the rate, so
    #: ``spending_paid`` is rederivable by anyone holding only these numbers
    #: (audit F4 — quarter-end ``nav_reported`` is sampled after the
    #: waterfall and does NOT reproduce the charge).
    spending_basis: float = 0.0
    spending_rate_annual: float = 0.0
    #: Undrawn commitment CANCELLED at terminal lapse this quarter (ER-6's
    #: close-out, ``CohortStep.expired_undrawn``). Zero in most quarters and
    #: a real release in the few where a cohort reaches the end of its
    #: contractual life: the balance leaves the unfunded total without ever
    #: being called. Carried here because the design's stated purpose was
    #: that it expire VISIBLY — computed but dropped until audit F2.
    expired_undrawn: float = 0.0
    #: The part of this quarter's distributions that was a fund WINDING UP —
    #: its whole remaining NAV paid out on the fund's clock, not the market's.
    #: Any statistic about distribution rates has to net this out or it
    #: measures the fund calendar (ER-12 follow-up; see `programme.py`).
    terminal_distributions: float = 0.0
    #: NAV by cohort id at quarter close, for the per-vintage stack.
    #:
    #: Snapshotted BEFORE ``engine.run_quarter`` runs, so a forced secondary
    #: in this same quarter reduces cohort NAV after this snapshot was taken.
    #: Deliberate: the stack shows the programme's own NAV, and the
    #: forced-sale block shows what liquidity did to it afterward.
    vintage_nav: dict[str, float] = field(default_factory=dict)
    #: cio-01: per-asset state the CIO view renders. Pure reads of the same
    #: book — recording them must not change a single quarterly numeric.
    liquid_values: dict[str, float] = field(default_factory=dict)
    private_true: dict[str, float] = field(default_factory=dict)
    private_reported: dict[str, float] = field(default_factory=dict)
    private_calls: dict[str, float] = field(default_factory=dict)
    private_distributions: dict[str, float] = field(default_factory=dict)
    private_unfunded: dict[str, float] = field(default_factory=dict)
    #: cio-03b: per-asset read of ``expired_undrawn`` (ER-6's terminal
    #: lapse), same pattern as ``private_calls``/``private_distributions``.
    #: A pure read — recording it does not change any existing numeric.
    private_expired: dict[str, float] = field(default_factory=dict)
    #: Three monthly NAV marks for the quarter. Months 0 and 1 mark the
    #: opening sleeves to the tape's monthly returns with flows pending;
    #: month 2 IS the post-waterfall quarter close, exactly.
    nav_true_months: tuple[float, ...] = ()
    nav_reported_months: tuple[float, ...] = ()


@dataclass(frozen=True)
class PlayResult:
    """The decade, and how close it came to the rocks.

    ``forced_sale_quarters`` counts every quarter the waterfall had to raise
    cash — mostly by selling liquid holdings, which is ordinary funding, not
    distress. ``forced_secondaries`` is the one that means trouble: liquid
    sleeves exhausted, private interests sold at the policy haircut. Keeping
    them apart matters, because a surface that calls routine funding a
    "forced sale" teaches the player to ignore the words.
    """

    quarters: list[PlayQuarter]
    final_value: float
    forced_sale_quarters: int
    total_forced_sales: float
    forced_secondaries: int = 0
    forced_secondary_nav: float = 0.0
    sale_log: list[dict[str, Any]] = field(default_factory=list)
    opening: dict[str, Any] = field(default_factory=dict)

    @property
    def months(self) -> int:
        return self.quarters[-1].month + 1 if self.quarters else 0


def _doc(name: str) -> dict[str, Any]:
    return json.loads((_STATE / name).read_text(encoding="utf-8"))


def _quarterly(monthly_pct: np.ndarray, n_quarters: int) -> np.ndarray:
    """Compound a monthly PERCENT series into quarterly decimal returns."""
    usable = monthly_pct[: n_quarters * 3].reshape(n_quarters, 3)
    return np.prod(1.0 + usable / 100.0, axis=1) - 1.0


def _drawdown_depth(quarterly: np.ndarray) -> np.ndarray:
    """Depth below the running peak, as a positive fraction — tier 1's state."""
    growth = np.cumprod(1.0 + quarterly)
    peak = np.maximum.accumulate(growth)
    return 1.0 - growth / peak


def _commit_new_vintage(
    portfolio: Portfolio,
    ladders: dict[str, list[ClosedEndCohort]],
    base: dict[str, Any],
    asset: str,
    year: int,
    amount: float,
) -> None:
    """Commit one year's new vintage of ``amount`` into the ladder."""
    if amount <= 0.0:
        return  # a cut-to-zero year: no vintage, honestly nothing
    # a fresh fund carries none of the example's history: no performance to
    # date, no accrued carry, and a real vintage year rather than an offset
    fresh = json.loads(json.dumps(base))
    fresh["identity"] = {**base["identity"], "sleeve_id": asset}
    fresh["performance"] = {"tvpi": 1.0, "dpi": 0.0, "rvpi": 1.0, "irr_to_date": 0.0, "pme": 1.0}
    fresh["fees"] = {**base["fees"], "accrued_carry": 0.0}
    cohort = ClosedEndCohort.new_commitment(
        fresh,
        committed=amount,
        vintage_year=int(base["identity"]["vintage_year"]) + year,
        cohort_id=f"{asset}-v{year}",
    )
    portfolio.add(f"{asset}-v{year}", cohort)
    ladders[asset].append(cohort)


#: The quarter-phase the committed fixture itself sits on (age 5.25), kept so
#: the seed ladder's rungs land on the same quarter boundary the document does.
_SEED_AGE_OFFSET = 0.25
#: The flat quarterly return the seed ladder is warmed forward at. NOT invented:
#: it is the rate that reproduces the committed fixture's OWN TVPI (1.44) at the
#: fixture's OWN age (5.25) through the same cohort model the game runs. Because
#: the finished ladder is then scaled to the sleeve's target weight, this rate
#: sets only the SHAPE across vintages — the J-curve staircase — never the level.
_WARMUP_QUARTERLY_RETURN = 0.026816


def _scaled_cohort(cohort: ClosedEndCohort, scale: float) -> ClosedEndCohort:
    """The same cohort with every monetary quantity multiplied by ``scale``.

    Round-trips through the state contract, so a scaled rung is re-validated
    rather than assumed — serialization IS the contract (``to_document``).
    """
    doc = cohort.to_document()
    for key in ("committed", "paid_in", "unfunded", "recallable_balance", "cumulative_recycled"):
        doc["commitment"][key] *= scale
    for key in ("nav_true", "nav_reported", "cumulative_distributions"):
        doc["value"][key] *= scale
    for key in doc["flows"]:
        doc["flows"][key] *= scale
    return ClosedEndCohort.from_document(doc)


def _seed_ladder(base: dict[str, Any], asset: str, target_nav: float) -> list[ClosedEndCohort]:
    """The opening book for one private sleeve: a STAGGERED ladder of vintages.

    An institution that has been committing for years holds one live vintage
    per year of a fund's contractual life — a staircase of ages, each at a
    different point on its J-curve. The play surface used to open with a
    single mid-life cohort per sleeve instead, cloned from the fixture at age
    5.25, which meant the ENTIRE opening private book reached the end of its
    life in the same quarter: all three sleeves lapsed together in quarter 19,
    expiring 9.0 of undrawn commitment (17% of the decade's calls) and winding
    up their NAV at once. Found 2026-08-14 by the audit-F2 expiry column, the
    first surface on which it was visible.

    Each rung is built by the model itself — a fresh commitment stepped
    forward to its age at ``_WARMUP_QUARTERLY_RETURN`` — so paid-in, unfunded,
    NAV and distributions-to-date are age-consistent by construction rather
    than invented per rung. Reported marks are set to true at the end of
    warm-up: under a constant return the appraisal filter has converged, so
    any lag would be an artifact of where warm-up happened to stop.

    The rungs are then scaled together so the sleeve opens at exactly the same
    private NAV as before — the ladder changes the SHAPE of the opening book,
    never the institution's allocation.
    """
    life = int(base["lifecycle"]["contractual_life_years"])
    vintage0 = int(base["identity"]["vintage_year"])
    rungs: list[ClosedEndCohort] = []
    for k in range(life):
        age = k + _SEED_AGE_OFFSET
        doc = json.loads(json.dumps(base))
        doc["identity"] = {**base["identity"], "sleeve_id": asset}
        cohort = ClosedEndCohort.new_commitment(
            doc,
            committed=1.0,
            vintage_year=vintage0 - k,
            cohort_id=f"{asset}-s{k}",
        )
        for _ in range(round(age * 4)):
            cohort.step(_WARMUP_QUARTERLY_RETURN)
        cohort.report(cohort.nav_true)
        rungs.append(cohort)

    total = sum(c.nav_true for c in rungs)
    if total <= 0.0:  # pragma: no cover - the warm-up return is positive
        raise ValueError("seed ladder warmed up to zero NAV")
    return [_scaled_cohort(c, target_nav / total) for c in rungs]


def _build_portfolio(
    policy: Policy,
    targets: Mapping[str, float],
    liquid: tuple[str, ...],
    book: OpeningBook | None = None,
) -> tuple[Portfolio, dict[str, list[ClosedEndCohort]]]:
    """An ongoing institution at its target weights, with a cash buffer.

    "Ongoing" now means a staggered ladder per private sleeve (see
    :func:`_seed_ladder`), not one mid-life cohort: the institution opens at
    the same allocation it always did, but its vintages mature one a year
    instead of all at once.

    su-app-06: when ``book`` is given, the liquid values, the cash and every
    private rung come from it instead of being derived. ``book=None`` is the
    derived path, unchanged — that is the whole feature's off switch.
    """
    portfolio = Portfolio(cash=START_CASH if book is None else book.cash)
    base = _doc("closed-end-cohort.example.json")
    liquid_doc = _doc("liquid-sleeve.example.json")

    for asset in liquid:
        sleeve = LiquidSleeve.from_document(liquid_doc)
        sleeve.value = float(targets[asset]) if book is None else float(book.liquid[asset])
        portfolio.add(asset, sleeve)

    cohorts: dict[str, list[ClosedEndCohort]] = {}
    for asset in PRIVATE_ASSETS:
        if book is None:
            rungs = _seed_ladder(base, asset, float(targets[asset]))
        else:
            rungs = book.cohorts(asset)
        for cohort in rungs:
            portfolio.add(cohort.contract.identity.cohort_id, cohort)
        cohorts[asset] = rungs
    return portfolio, cohorts


def _rebalance(
    portfolio: Portfolio, frm: tuple[str, ...], to: tuple[str, ...], points: float
) -> None:
    """Move value between LIQUID sleeves only.

    A private cohort's NAV is not a dial — you cannot move 10 points into
    private equity by deciding to. Growth/defensive shifts therefore act on
    the liquid leg of each pair, which is the honest version of the toy's
    instant reweighting.
    """
    liquid_from = [k for k in frm if k in LIQUID_ASSETS]
    liquid_to = [k for k in to if k in LIQUID_ASSETS]
    if not liquid_from or not liquid_to:
        return
    available = sum(portfolio.liquid[k].value for k in liquid_from)
    amount = min(points, available)
    if amount <= 0.0:
        return
    for key in liquid_from:
        share = portfolio.liquid[key].value / available
        portfolio.liquid[key].sell(amount * share)
    for key in liquid_to:
        portfolio.liquid[key].buy(amount / len(liquid_to))


def _secondary_sale(
    portfolio: Portfolio, cohorts: dict[str, list[ClosedEndCohort]], policy: Policy
) -> float:
    """Sell private equity interests on the secondary market for CASH.

    The point of the whole exercise: this now raises real money at a real
    discount, and the proceeds sit in the cash account where calls are paid
    from. Selling early is a liquidity decision with a price, not a weight
    tweak.
    """
    live = [c for c in cohorts.get("pe_ladder", []) if c.nav_true > 0.0]
    cohort = max(live, key=lambda c: c.nav_true) if live else None
    if cohort is None:
        return 0.0
    nav = cohort.nav_true
    if nav <= 0.0:
        return 0.0
    sold_nav = min(_SECONDARY_POINTS, nav)
    proceeds = sold_nav * (1.0 - policy.secondary_haircut)
    cohort.nav_true = nav - sold_nav
    cohort.report(max(0.0, cohort.nav_reported - sold_nav))
    portfolio.cash += proceeds
    return proceeds


def simulate_play(
    paths: EnginePaths,
    decisions: Mapping[int, str | Mapping[str, Any]] | None = None,
    *,
    use_reported: bool = True,
    policy: Policy | None = None,
    linkage: bool = True,
    start_targets: Mapping[str, float] | None = None,
    pacing_rule: str = "policy",
    pacing_band: tuple[float, float] = PACING_BAND,
    opening_book: OpeningBook | None = None,
) -> PlayResult:
    """Run the institution over a tape, quarter by quarter, with consequences.

    ``decisions`` maps a decision MONTH to one of hold / derisk / leanin /
    secondary, exactly as the session service records them. Pure and
    deterministic: the same tape and the same decisions give the same result.

    ``linkage=False`` runs the SAME recursion with ``f_call = f_dist = 1`` —
    tier 0's benchmark, the sealed "one model, linkage on or off" identity.
    It exists for the credibility console's counterfactual and is never used
    on the scored path.

    ``opening_book`` (su-app-06) replaces the DERIVED opening state with an
    entered one — liquid values, cash and every private rung. ``None`` is the
    derived path and is bit-identical to the behaviour before this parameter
    existed.

    su-app-07: a book also carries the institution's POLICY targets, which
    are a different number from the values it opens at. When one is given it
    OVERRIDES ``start_targets`` for both the pacing plan and the commitment
    cap — the book is the institution, and a world default cannot describe
    an institution the analyst entered. A book with no entered targets paces
    against its own opening values, which for the derived default book are
    ``START_TARGETS`` exactly.
    """
    if pacing_rule not in ("policy", "fixed"):
        raise ValueError(f"pacing_rule must be 'policy' or 'fixed', got {pacing_rule!r}")
    policy = policy or Policy()
    decisions = decisions or {}
    n_quarters = paths.months // 3
    # the tape's own sleeve set: liquid = asset_order minus the privates
    # (generated worlds drop reits per OD-3); targets default to the toy book
    liquid = tuple(a for a in paths.asset_order if a not in PRIVATE_ASSETS)
    targets = dict(start_targets) if start_targets is not None else dict(START_TARGETS)
    cash_policy = START_CASH
    # su-app-07: a book carries its own POLICY targets, which are a different
    # number from the values it opens at. They are resolved HERE rather than
    # in `ah.serve`, because `start_targets` and `opening_book` are
    # independent parameters threaded separately through `ah.cioview`,
    # `ah.annotations` and `window_contributions_play` — resolving at the
    # service would leave those surfaces pacing off the world default while
    # holding a book. `effective_targets()` is the single definition of the
    # fallback (entered targets, else the book's own opening values), so this
    # is a re-point, not a second rule.
    if opening_book is not None:
        targets = opening_book.effective_targets()
        cash_policy = opening_book.cash
    # su-app-06 (I1), re-based by su-app-07: the lever's declared bound is
    # measured against the POLICY targets — the same basis `validate_plan`
    # and the service's decision door use, so the three cannot disagree about
    # the same quantity, and the same basis the pacing rule below reads. One
    # number, one meaning. `opening_book=None` reads `targets` exactly as it
    # always did.
    _validate_commit_decisions(decisions, targets)
    portfolio, cohorts = _build_portfolio(policy, targets, liquid, opening_book)
    engine = PortfolioEngine(portfolio, policy)
    base_doc = _doc("closed-end-cohort.example.json")
    ladders: dict[str, list[ClosedEndCohort]] = {a: list(cohorts[a]) for a in PRIVATE_ASSETS}

    def _liquid_snapshot() -> dict[str, float]:
        return {a: float(portfolio.liquid[a].value) for a in liquid}

    def _private_snapshot(reported: bool) -> dict[str, float]:
        return {
            a: float(sum((c.nav_reported if reported else c.nav_true) for c in ladders[a]))
            for a in PRIVATE_ASSETS
        }

    def _unfunded_snapshot() -> dict[str, float]:
        return {a: float(sum(c.unfunded for c in ladders[a])) for a in PRIVATE_ASSETS}

    opening = {
        "nav_true": float(portfolio.nav_true()),
        "nav_reported": float(portfolio.nav_reported()),
        "cash": float(portfolio.cash),
        "liquid_values": _liquid_snapshot(),
        "private_true": _private_snapshot(False),
        "private_reported": _private_snapshot(True),
        "private_unfunded": _unfunded_snapshot(),
    }

    q_returns = {a: _quarterly(paths.returns[a], n_quarters) for a in paths.returns}
    q_reported = {a: _quarterly(paths.reported[a], n_quarters) for a in paths.reported}
    depth = _drawdown_depth(q_returns["equity"])
    spread_ratio = np.array(
        [
            float(paths.spread[min(q * 3 + 2, paths.months - 1)]) / _SPREAD_REFERENCE_BPS
            for q in range(n_quarters)
        ]
    )

    out: list[PlayQuarter] = []
    forced_quarters = 0
    forced_total = 0.0

    for q in range(n_quarters):
        closing_month = q * 3 + 2

        # A decision lands at the START of the quarter after the window it was
        # taken in: windows sit on month 11, 23, ... which are quarter-closing
        # months, so quarter q acts on the decision taken at month q*3 - 1.
        for month, action in sorted(decisions.items()):
            if month == q * 3 - 1:
                name = _action_name(action)
                if name == "derisk":
                    _rebalance(portfolio, _GROWTH, _DEFENSIVE, _SHIFT_POINTS)
                elif name == "leanin":
                    _rebalance(portfolio, _DEFENSIVE, _GROWTH, _SHIFT_POINTS)
                elif name == "secondary":
                    _secondary_sale(portfolio, {"pe_ladder": ladders["pe"]}, policy)

        liq_open = _liquid_snapshot()
        cash_open = float(portfolio.cash)

        for asset in liquid:
            portfolio.liquid[asset].apply_return(float(q_returns[asset][q]))

        # the pacing plan: a new vintage every year, in every private sleeve.
        # DN-5 §2.1 (sp-01): under the POLICY rule the year's pace flexes
        # toward the policy private weight on REPORTED marks (the books the
        # committee actually sees), clipped to the band; the FIXED rule is
        # the drift twin's nominal schedule. A player commit decision at the
        # immediately preceding window overrides the per-sleeve points.
        committed_this_quarter = 0.0
        if q > 0 and q % _COMMITMENT_QUARTERS == 0:
            if pacing_rule == "policy":
                multiplier = _pacing_multiplier(
                    portfolio.private_weight_reported(), targets, pacing_band, cash_policy
                )
            else:
                multiplier = 1.0
            override = decisions.get(q * 3 - 1)
            override_pts = override.get("commitments") if isinstance(override, Mapping) else None
            for asset in PRIVATE_ASSETS:
                plan_amount = targets[asset] * _ANNUAL_COMMITMENT_RATE * multiplier
                amount = (
                    float(override_pts[asset])
                    if override_pts is not None and asset in override_pts
                    else plan_amount
                )
                _commit_new_vintage(portfolio, ladders, base_doc, asset, q // 4, amount)
                committed_this_quarter += amount

        priv_true_open = _private_snapshot(False)
        priv_rep_open = _private_snapshot(True)

        calls = 0.0
        distributions = 0.0
        expired = 0.0
        terminal_dist = 0.0
        dd = float(depth[q])
        sr = float(spread_ratio[q])
        fc = tier1_f_call(dd) if linkage else 1.0
        fd = tier1_f_dist(dd, sr) if linkage else 1.0
        vintage_nav: dict[str, float] = {}
        calls_by: dict[str, float] = {a: 0.0 for a in PRIVATE_ASSETS}
        dists_by: dict[str, float] = {a: 0.0 for a in PRIVATE_ASSETS}
        expired_by: dict[str, float] = {a: 0.0 for a in PRIVATE_ASSETS}
        for asset in PRIVATE_ASSETS:
            for cohort in ladders[asset]:
                step = cohort.step(
                    float(q_returns[asset][q]),
                    f_call=fc,
                    f_dist=fd,
                )
                calls += step.call
                distributions += step.distribution_total
                expired += step.expired_undrawn
                calls_by[asset] += step.call
                dists_by[asset] += step.distribution_total
                expired_by[asset] += step.expired_undrawn
                if step.is_terminal:
                    terminal_dist += step.distribution_total
                # the reported mark follows the tape the player is shown
                grown = cohort.nav_reported * (1.0 + float(q_reported[asset][q]))
                cohort.report(max(0.0, grown + step.call - step.distribution_total))
                vintage_nav[cohort.contract.identity.cohort_id] = cohort.nav_true

        report = engine.run_quarter(distributions=distributions, calls=calls)
        if report.forced_sale_total > 0.0:
            forced_quarters += 1
            forced_total += report.forced_sale_total

        def _mark(
            month_in_q: int,
            reported: bool,
            *,
            _q: int = q,
            _liq_open: dict[str, float] = liq_open,
            _cash_open: float = cash_open,
            _priv_true_open: dict[str, float] = priv_true_open,
            _priv_rep_open: dict[str, float] = priv_rep_open,
        ) -> float:
            liq = sum(
                _liq_open[a]
                * float(np.prod(1.0 + paths.returns[a][_q * 3 : _q * 3 + month_in_q + 1] / 100.0))
                for a in liquid
            )
            tape = paths.reported if reported else paths.returns
            opens = _priv_rep_open if reported else _priv_true_open
            priv = sum(
                opens[a] * float(np.prod(1.0 + tape[a][_q * 3 : _q * 3 + month_in_q + 1] / 100.0))
                for a in PRIVATE_ASSETS
            )
            return liq + priv + _cash_open

        nav_true_months = (_mark(0, False), _mark(1, False), float(portfolio.nav_true()))
        nav_reported_months = (
            _mark(0, True),
            _mark(1, True),
            float(portfolio.nav_reported()),
        )

        out.append(
            PlayQuarter(
                quarter=q,
                month=closing_month,
                cash=portfolio.cash,
                nav_true=portfolio.nav_true(),
                nav_reported=portfolio.nav_reported(),
                calls_paid=report.calls_paid,
                distributions_received=report.distributions_received,
                spending_paid=report.spending_paid,
                forced_sale_total=report.forced_sale_total,
                private_weight_true=report.private_weight_true,
                private_weight_reported=portfolio.private_weight_reported(),
                unfunded_total=portfolio.total_unfunded(),
                spending_basis=report.spending_basis,
                spending_rate_annual=report.spending_rate_annual,
                expired_undrawn=expired,
                terminal_distributions=terminal_dist,
                drawdown_depth=dd,
                spread_ratio=sr,
                f_dist=fd,
                f_call=fc,
                new_commitments=committed_this_quarter,
                vintage_nav=vintage_nav,
                liquid_values=_liquid_snapshot(),
                private_true=_private_snapshot(False),
                private_reported=_private_snapshot(True),
                private_calls=calls_by,
                private_distributions=dists_by,
                private_expired=expired_by,
                private_unfunded=_unfunded_snapshot(),
                nav_true_months=nav_true_months,
                nav_reported_months=nav_reported_months,
            )
        )

    # app-open-01 (cio-05): a month-0 CIO view runs simulate_play with ZERO
    # world quarters and a forecast_quarters=0 caller on top of that, leaving
    # `out` empty (`_frozen_paths(paths, 0, 0)` -> paths.months=0 ->
    # n_quarters=0). Every OTHER caller has always had out non-empty
    # (months>=3 was enforced upstream), so this branch is new and additive:
    # it falls back to the opening state, which is exactly what "no quarter
    # has run yet" means.
    final = (
        (out[-1].nav_reported if use_reported else out[-1].nav_true)
        if out
        else (opening["nav_reported"] if use_reported else opening["nav_true"])
    )
    secondaries = [e for e in portfolio.forced_sales if e["kind"] == "forced_secondary"]
    return PlayResult(
        quarters=out,
        final_value=final,
        forced_sale_quarters=forced_quarters,
        total_forced_sales=forced_total,
        forced_secondaries=len(secondaries),
        forced_secondary_nav=sum(float(e["nav_sold"]) for e in secondaries),
        sale_log=list(portfolio.forced_sales),
        opening=opening,
    )


def play_alpha(
    paths: EnginePaths,
    decisions: Mapping[int, str | Mapping[str, Any]],
    *,
    use_reported: bool = True,
    policy: Policy | None = None,
) -> float:
    """Decision alpha on the real twin: active minus hold-course, same tape.

    The twin follows the pacing plan set at t=0 mechanically, regardless of
    conditions (liquidity-spine §5.1) — which here means it takes no action at
    any window. The cost of flinching needs that counterfactual to be defined.
    """
    active = simulate_play(paths, decisions, use_reported=use_reported, policy=policy)
    twin = simulate_play(paths, None, use_reported=use_reported, policy=policy)
    return active.final_value - twin.final_value


@dataclass(frozen=True)
class PlayAttribution:
    """DN-5's chain-link decomposition, on the real twin.

    ``contributions[j]`` is the j-th window's marginal effect: the value of
    playing the decision prefix up to and including window j, minus the value
    of the prefix before it. The chain telescopes to the terminal difference,
    so the parts sum to the whole by construction rather than by luck.
    """

    months: tuple[int, ...]
    actions: tuple[str, ...]
    contributions: tuple[float, ...]
    twin_final: float
    final_value: float

    @property
    def total_alpha(self) -> float:
        return self.final_value - self.twin_final


def window_contributions_play(
    paths: EnginePaths,
    decisions: Mapping[int, str | Mapping[str, Any]],
    *,
    use_reported: bool = True,
    policy: Policy | None = None,
    start_targets: Mapping[str, float] | None = None,
    opening_book: OpeningBook | None = None,
) -> PlayAttribution:
    """K+1 runs for K windows — exact, no sampling.

    Windows the participant left unmapped default to hold inside
    :func:`simulate_play` exactly as they did when the sequence was played, so
    a partial decision map still decomposes correctly.

    ``opening_book`` (su-app-06) rides along on the twin AND every prefix
    replay — the same entered book throughout, so the chain-link
    decomposition still isolates decisions rather than mixing institutions.
    """
    months_list = decision_months(paths.months)
    twin = simulate_play(
        paths,
        None,
        use_reported=use_reported,
        policy=policy,
        start_targets=start_targets,
        opening_book=opening_book,
    )
    prev_final = float(twin.final_value)

    contributions: list[float] = []
    actions: list[str] = []
    prefix: dict[int, str | Mapping[str, Any]] = {}
    for month in months_list:
        action = decisions.get(month, "hold")
        prefix[month] = action
        run = simulate_play(
            paths,
            dict(prefix),
            use_reported=use_reported,
            policy=policy,
            start_targets=start_targets,
            opening_book=opening_book,
        )
        final = float(run.final_value)
        contributions.append(final - prev_final)
        # the review line names the action; a structured commit renders as
        # its action word, the payload lives in the decision log
        actions.append(action if isinstance(action, str) else str(action.get("action")))
        prev_final = final

    return PlayAttribution(
        months=tuple(months_list),
        actions=tuple(actions),
        contributions=tuple(contributions),
        twin_final=float(twin.final_value),
        final_value=prev_final,
    )
