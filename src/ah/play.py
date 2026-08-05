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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ah.core.engine import EnginePaths
from ah.core.institution import decision_months
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
    "START_TARGETS",
    "PlayAttribution",
    "PlayQuarter",
    "PlayResult",
    "play_alpha",
    "simulate_play",
    "window_contributions_play",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE = _REPO_ROOT / "fixtures" / "state"

#: The product's own alpha identity. NOT ah.eval.decision_metrics's constant,
#: which names Step 5's research definition and is sealed under G5.
PLAY_ALPHA_VERSION = "port-v1-cashflow"

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
    #: NAV by cohort id at quarter close, for the per-vintage stack.
    #:
    #: Snapshotted BEFORE ``engine.run_quarter`` runs, so a forced secondary
    #: in this same quarter reduces cohort NAV after this snapshot was taken.
    #: Deliberate: the stack shows the programme's own NAV, and the
    #: forced-sale block shows what liquidity did to it afterward.
    vintage_nav: dict[str, float] = field(default_factory=dict)


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
) -> None:
    """Commit one year's new vintage into the ladder."""
    amount = START_TARGETS[asset] * _ANNUAL_COMMITMENT_RATE
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


def _build_portfolio(policy: Policy) -> tuple[Portfolio, dict[str, ClosedEndCohort]]:
    """An ongoing institution at its target weights, with a cash buffer."""
    portfolio = Portfolio(cash=START_CASH)
    base = _doc("closed-end-cohort.example.json")
    liquid_doc = _doc("liquid-sleeve.example.json")

    for asset in LIQUID_ASSETS:
        sleeve = LiquidSleeve.from_document(liquid_doc)
        sleeve.value = START_TARGETS[asset]
        portfolio.add(asset, sleeve)

    cohorts: dict[str, ClosedEndCohort] = {}
    for asset in PRIVATE_ASSETS:
        # scale the example cohort so its NAV lands on the target weight; it
        # keeps the document's age and unfunded ratio, so the institution opens
        # mid-programme rather than ramping in from nothing
        scale = START_TARGETS[asset] / float(base["value"]["nav_true"])
        doc = json.loads(json.dumps(base))
        doc["identity"] = {**base["identity"], "sleeve_id": asset, "cohort_id": f"{asset}-play"}
        for key in ("committed", "paid_in", "unfunded", "recallable_balance"):
            doc["commitment"][key] = base["commitment"][key] * scale
        doc["commitment"]["cumulative_recycled"] = base["commitment"]["cumulative_recycled"] * scale
        for key in ("nav_true", "nav_reported", "cumulative_distributions"):
            doc["value"][key] = base["value"][key] * scale
        cohort = ClosedEndCohort.from_document(doc)
        portfolio.add(asset, cohort)
        cohorts[asset] = cohort
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
    decisions: dict[int, str] | None = None,
    *,
    use_reported: bool = True,
    policy: Policy | None = None,
    linkage: bool = True,
) -> PlayResult:
    """Run the institution over a tape, quarter by quarter, with consequences.

    ``decisions`` maps a decision MONTH to one of hold / derisk / leanin /
    secondary, exactly as the session service records them. Pure and
    deterministic: the same tape and the same decisions give the same result.

    ``linkage=False`` runs the SAME recursion with ``f_call = f_dist = 1`` —
    tier 0's benchmark, the sealed "one model, linkage on or off" identity.
    It exists for the credibility console's counterfactual and is never used
    on the scored path.
    """
    policy = policy or Policy()
    decisions = decisions or {}
    n_quarters = paths.months // 3
    portfolio, cohorts = _build_portfolio(policy)
    engine = PortfolioEngine(portfolio, policy)
    base_doc = _doc("closed-end-cohort.example.json")
    ladders: dict[str, list[ClosedEndCohort]] = {a: [cohorts[a]] for a in PRIVATE_ASSETS}

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
                if action == "derisk":
                    _rebalance(portfolio, _GROWTH, _DEFENSIVE, _SHIFT_POINTS)
                elif action == "leanin":
                    _rebalance(portfolio, _DEFENSIVE, _GROWTH, _SHIFT_POINTS)
                elif action == "secondary":
                    _secondary_sale(portfolio, {"pe_ladder": ladders["pe"]}, policy)

        for asset in LIQUID_ASSETS:
            portfolio.liquid[asset].apply_return(float(q_returns[asset][q]))

        # the pacing plan: a new vintage every year, in every private sleeve
        committed_this_quarter = 0.0
        if q > 0 and q % _COMMITMENT_QUARTERS == 0:
            for asset in PRIVATE_ASSETS:
                _commit_new_vintage(portfolio, ladders, base_doc, asset, q // 4)
                committed_this_quarter += START_TARGETS[asset] * _ANNUAL_COMMITMENT_RATE

        calls = 0.0
        distributions = 0.0
        dd = float(depth[q])
        sr = float(spread_ratio[q])
        fc = tier1_f_call(dd) if linkage else 1.0
        fd = tier1_f_dist(dd, sr) if linkage else 1.0
        vintage_nav: dict[str, float] = {}
        for asset in PRIVATE_ASSETS:
            for cohort in ladders[asset]:
                step = cohort.step(
                    float(q_returns[asset][q]),
                    f_call=fc,
                    f_dist=fd,
                )
                calls += step.call
                distributions += step.distribution_total
                # the reported mark follows the tape the player is shown
                grown = cohort.nav_reported * (1.0 + float(q_reported[asset][q]))
                cohort.report(max(0.0, grown + step.call - step.distribution_total))
                vintage_nav[cohort.contract.identity.cohort_id] = cohort.nav_true

        report = engine.run_quarter(distributions=distributions, calls=calls)
        if report.forced_sale_total > 0.0:
            forced_quarters += 1
            forced_total += report.forced_sale_total

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
                unfunded_total=portfolio.total_unfunded(),
                drawdown_depth=dd,
                spread_ratio=sr,
                f_dist=fd,
                f_call=fc,
                new_commitments=committed_this_quarter,
                vintage_nav=vintage_nav,
            )
        )

    final = out[-1].nav_reported if use_reported else out[-1].nav_true
    secondaries = [e for e in portfolio.forced_sales if e["kind"] == "forced_secondary"]
    return PlayResult(
        quarters=out,
        final_value=final,
        forced_sale_quarters=forced_quarters,
        total_forced_sales=forced_total,
        forced_secondaries=len(secondaries),
        forced_secondary_nav=sum(float(e["nav_sold"]) for e in secondaries),
        sale_log=list(portfolio.forced_sales),
    )


def play_alpha(
    paths: EnginePaths,
    decisions: dict[int, str],
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
    decisions: dict[int, str],
    *,
    use_reported: bool = True,
    policy: Policy | None = None,
) -> PlayAttribution:
    """K+1 runs for K windows — exact, no sampling.

    Windows the participant left unmapped default to hold inside
    :func:`simulate_play` exactly as they did when the sequence was played, so
    a partial decision map still decomposes correctly.
    """
    months_list = decision_months(paths.months)
    twin = simulate_play(paths, None, use_reported=use_reported, policy=policy)
    prev_final = float(twin.final_value)

    contributions: list[float] = []
    actions: list[str] = []
    prefix: dict[int, str] = {}
    for month in months_list:
        action = decisions.get(month, "hold")
        prefix[month] = action
        run = simulate_play(paths, dict(prefix), use_reported=use_reported, policy=policy)
        final = float(run.final_value)
        contributions.append(final - prev_final)
        actions.append(action)
        prev_final = final

    return PlayAttribution(
        months=tuple(months_list),
        actions=tuple(actions),
        contributions=tuple(contributions),
        twin_final=float(twin.final_value),
        final_value=prev_final,
    )
