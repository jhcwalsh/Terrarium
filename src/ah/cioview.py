"""The CIO view builder (cio-01) — DN-8's engine side.

``build_cio_view`` is a pure function from replayed play state to the
``CioView`` payload the dashboard renders. The renderer computes nothing
(DN-8 section 1); everything on screen originates here, server-side, because
the server is the authority for value (DN-3 W5).

``validate_cio_view`` is the Python port of ``validateCioView`` from
``docs/cio-dashboard/cioView.ts`` and is the CI authority for the contract;
the TS validator runs dev-side only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

import numpy as np

from ah.core.engine import EnginePaths
from ah.play import PRIVATE_ASSETS, START_CASH, START_TARGETS, PlayResult, simulate_play
from ah.port.book import OpeningBook
from ah.prehistory import PreHistory, build_prehistory

PLANES: tuple[str, str] = ("reported", "true")
LINKAGE_VERSION = "public-0.1"
WATCH_FRACTION = 0.75  # DN-8 section 3: amber inside the last quarter of the band
COVERAGE_ANCHOR = 0.5  # WP3.10 section 5 steady-state anchor
# decision_metrics.py's liquidity_shortfall_probability docstring: "Coverage
# here is unfunded/liquid (P-B's binding ratio): breaching 1.0 means
# unfunded commitments exceed everything sellable." The E1 measurement
# (docs/superpowers/specs/2026-08-15-e1-overcommitment-measurement.md) found
# worst coverage monotone in the player's allocation (0.10 -> 1.57 across the
# policy range) while forced secondaries stayed unreachable -- this ratio,
# not unfundedToNav, is the owner-designated teaching surface (cov-01).
COVERAGE_BREACH_LINE = 1.0
UNIT_LABEL, UNIT_SUFFIX, CURRENCY = "$m", "m", "USD"  # 1 point = $1m, declared
WATERMARK = "TERRARIUM - SIMULATED WORLD"
DISCLAIMER = (
    "Simulated world; generic parameters. Not investment advice and not "
    "representative of any institution's policy portfolio."
)
TRUE_PLANE_LABEL = "engine true state"  # O-2: never "true value"

#: O-5: the fixed goal taxonomy. Display order is the declaration order.
GOALS: tuple[tuple[str, str], ...] = (
    ("growth", "Growth"),
    ("real", "Real return"),
    ("income", "Income"),
    ("diversifier", "Diversifiers"),
)
GOAL_OF: dict[str, str] = {
    "equity": "growth",
    "pe": "growth",
    "commodities": "real",
    "reits": "real",
    "re": "real",
    "bonds": "income",
    "hy": "income",
    "pc": "income",
    "cash": "diversifier",
}
CLASS_LABEL: dict[str, str] = {
    "equity": "Public equity",
    "bonds": "Core bonds",
    "hy": "High yield",
    "commodities": "Commodities",
    "reits": "REITs",
    "pe": "Private equity",
    "pc": "Private credit",
    "re": "Real estate",
    "cash": "Cash",
}
#: Band half-widths in points, a declared display-policy input (O-5 kin).
BAND_PCT: dict[str, float] = {
    "equity": 5.0,
    "bonds": 3.0,
    "hy": 2.0,
    "commodities": 2.0,
    "reits": 2.0,
    "pe": 4.0,
    "pc": 2.0,
    "re": 2.0,
    "cash": 2.0,
}
GOAL_TOLERANCE_PCT = 5.0

#: O-4: static class->tier mapping, footnoted on the surface.
TIER1_CLASSES: tuple[str, ...] = ("cash", "bonds")
TIER2_CLASSES: tuple[str, ...] = ("equity", "hy", "commodities", "reits")
# everything in PRIVATE_ASSETS is the illiquid remainder (liquid: False)


def _frozen_paths(paths: EnginePaths, hist_months: int, extra_quarters: int) -> EnginePaths:
    """The revealed tape verbatim plus flat forecast months."""
    n, extra = hist_months, extra_quarters * 3
    # n=0 (app-open-01, cio-05: a month-0 CIO payload has no revealed month at
    # all) has no "last revealed month" to hold — `a[n - 1]` would silently
    # wrap to `a[-1]`, the world's FINAL month, and feed the mechanical
    # forecast the wrong rate/spread/inflation regime. Hold at month 0's own
    # reading instead, the only defensible baseline before anything has run.
    base_month = n - 1 if n > 0 else 0
    hold = lambda a: np.concatenate([a[:n], np.full(extra, float(a[base_month]))])  # noqa: E731
    flat = lambda d: {k: np.concatenate([v[:n], np.zeros(extra)]) for k, v in d.items()}  # noqa: E731
    return replace(
        paths,
        months=n + extra,
        rate=hold(paths.rate),
        spread=hold(paths.spread),
        inflation=hold(paths.inflation),
        crisis=np.concatenate([paths.crisis[:n], np.zeros(extra)]),
        returns=flat(paths.returns),
        reported=flat(paths.reported),
    )


PERIODS = ("1Q", "YTD", "1Y", "3Y", "5Y", "10Y")
ANNUALISED_FROM = 3  # 3Y onward annualised
_WINDOW_QUARTERS = {"1Q": 1, "1Y": 4, "3Y": 12, "5Y": 20, "10Y": 40}


def _quarterly_returns(result: PlayResult, plane: str, n_quarters: int) -> list[float]:
    key = "nav_reported" if plane == "reported" else "nav_true"
    navs = [result.opening[key]] + [getattr(q, key) for q in result.quarters[:n_quarters]]
    return [
        (navs[i + 1] + result.quarters[i].spending_paid) / navs[i] - 1.0 for i in range(n_quarters)
    ]


def _window_return(q_rets: list[float], n: int, annualise: bool) -> float | None:
    if n > len(q_rets):
        return None
    growth = float(np.prod([1.0 + r for r in q_rets[-n:]]))
    if annualise:
        return round((growth ** (4.0 / n) - 1.0) * 100.0, 4)
    return round((growth - 1.0) * 100.0, 4)


def _period_row(q_rets: list[float], last_q: int) -> list[float | None]:
    out: list[float | None] = []
    for i, p in enumerate(PERIODS):
        # last_q < 0 (app-open-01, cio-05: no world quarter has closed —
        # month-0) has no "this calendar year" to speak of; Python's modulo
        # would otherwise silently produce a positive-looking YTD window out
        # of a negative last_q. Every other period is a plain trailing
        # window and stays well-defined off q_rets alone (empty at month 0,
        # so _window_return already nulls it).
        if p == "YTD" and last_q < 0:
            out.append(None)
            continue
        n = (last_q % 4) + 1 if p == "YTD" else _WINDOW_QUARTERS[p]
        out.append(_window_return(q_rets, n, i >= ANNUALISED_FROM))
    return out


def build_cio_view(
    paths: EnginePaths,
    decisions: Mapping[int, Any],
    *,
    run_id: str,
    seed: int,
    world_title: str,
    world_version: str,
    alpha_version: str,
    start_targets: Mapping[str, float] | None,
    plane: str,
    revealed_months: int,
    forecast_quarters: int = 4,
    prehistory: bool = True,
    opening_book: OpeningBook | None = None,
) -> dict[str, Any]:
    """``prehistory`` prepends the inherited decade (cio-04) ahead of world
    month 0 — the plan chart, the long return windows and the market-path
    charts all gain a pre-run segment that terminates exactly on this
    world's own opening book. It is a display decision, not an engine one:
    ``build_prehistory`` always runs the toy engine internally regardless of
    which engine produced ``paths``, so a caller splicing it onto a
    generated (non-toy-v0) world would be stitching two engines into one
    chart. This function does not sniff ``paths`` for that — the caller
    decides and passes the flag (``ah/serve.py``).

    ``opening_book`` (su-app-06) rides along on both the active replay and
    its twin — this is a LIVE surface (mid-decade, not just at outcome), so
    a player who entered a custom book must see a dashboard for that book
    the whole way through, not just at the end.
    """
    if plane not in PLANES:
        raise ValueError(f"plane must be one of {PLANES}, got {plane!r}")
    n_q = revealed_months // 3
    # app-open-01 (cio-05): revealed_months == 0 is the CIO's new front door —
    # the state right after the opening book is confirmed, before the player
    # has advanced at all. It is handled below (n_q == 0 throughout this
    # function reads active.opening instead of active.quarters[n_q - 1]).
    # revealed_months in (1, 2) is still mid-quarter with nothing closed —
    # that 409 is unchanged.
    if revealed_months > 0 and n_q < 1:
        raise ValueError("no closed quarter inside the revealed window")
    hist_months = n_q * 3
    frozen = _frozen_paths(paths, hist_months, forecast_quarters)
    active = simulate_play(
        frozen, dict(decisions), start_targets=start_targets, opening_book=opening_book
    )
    twin = simulate_play(frozen, None, start_targets=start_targets, opening_book=opening_book)
    targets = dict(start_targets) if start_targets is not None else dict(START_TARGETS)
    cash_target = START_CASH
    if opening_book is not None:
        # su-app-07 Ruling G. Since task 2 the engine PACES AND CAPS off the
        # book's `effective_targets()`, so a dashboard whose `targetPct` still
        # read the world default would state a policy the institution is not
        # running — su-app-06's worst defect class (displayed one thing,
        # applied another) reappearing on the CIO surface.
        #
        # `effective_targets()` is the single resolver (it already carries the
        # "entered targets, else the book's own opening values" fallback), so
        # nothing is re-derived here. `ah/serve.py::_policy_basis` wraps the
        # same answer for the four SERVICE sites, but `serve` imports this
        # module, so importing it back would be circular; the book's own
        # method is the shared thing, not the wrapper.
        #
        # The world's key ORDER is kept and the book's NUMBERS taken, because
        # `_allocation` derives its display order from this dict; a sleeve
        # only the book names is appended rather than dropped.
        #
        # The lookup is `effective[k]`, NOT `effective.get(k, v)`. A per-key
        # fallback to the world default would be a SECOND, divergent answer to
        # "the book omits a sleeve": `simulate_play` (play.py) replaces
        # `targets` wholesale, so the engine would pace on nothing there while
        # this surface displayed the world's number — the exact latent
        # display-vs-applied drift Ruling G exists to kill. `validate_book`
        # forces `set(book.targets) == full_sleeves` and both branches of
        # `effective_targets()` cover that set, so the key is always present;
        # if that ever stops being true this raises loudly instead of
        # printing a policy nobody is running.
        effective = opening_book.effective_targets()
        targets = {
            **{k: float(effective[k]) for k in targets},
            **{k: float(v) for k, v in effective.items() if k not in targets},
        }
        cash_target = float(opening_book.cash)
    q_rets = _quarterly_returns(active, plane, n_q)
    twin_rets = _quarterly_returns(twin, plane, n_q)

    nav_attr = "nav_reported_months" if plane == "reported" else "nav_true_months"
    history = [round(m, 4) for q in active.quarters[:n_q] for m in getattr(q, nav_attr)]
    # world month 0's own opening book — untouched by prehistory (cio-04's
    # seam is stitched on NAV only); growthPct/netOfFlows read off this, not
    # off history[0], so they stay world-relative regardless of prehistory.
    opening_nav = active.opening["nav_reported" if plane == "reported" else "nav_true"]
    if n_q > 0:
        last = active.quarters[n_q - 1]
        total = last.nav_reported if plane == "reported" else last.nav_true
    else:
        # nothing has closed yet: "now" IS the opening state, by definition.
        total = opening_nav
    spend_total = sum(q.spending_paid for q in active.quarters[:n_q])

    pre: PreHistory | None = None
    if prehistory:
        # KNOWN HOLDOUT (su-app-07 Ruling G, final review). `start_targets`
        # here is the WORLD default, deliberately — NOT the book's
        # `effective_targets()` that `targets`/`cash_target` above now
        # resolve to. So on a book-carrying session the inherited decade is
        # still simulated against the world's policy while everything from
        # world month 0 onward runs the book's. It is the last target-basis
        # holdout on this surface, and it is left alone on purpose: re-basing
        # it changes the ER-13 inherited decade's numbers for every
        # book-carrying session, which is a release event and the owner's
        # call, not an incidental cleanup. Recorded in `CHANGELOG.md`'s
        # su-app-07 deferral list.
        pre = build_prehistory(
            seed,
            active.opening["nav_true"],
            active.opening["nav_reported"],
            start_targets=start_targets,
        )
    pre_nav_months = (
        (pre.nav_reported_months if plane == "reported" else pre.nav_true_months)
        if pre is not None
        else ()
    )
    world_start_index = len(pre_nav_months)
    history_values = [round(m, 4) for m in pre_nav_months] + history
    if n_q == 0:
        # No world month has been revealed at all — `history` is empty, so
        # without this the chart would have nothing to draw at "now" (or, with
        # no prehistory either, literally zero points). The opening NAV is
        # exactly one real, known point: append it, and worldStartIndex (set
        # below) then points AT it — the hatched pre-history right up to a
        # single dot at "now", nothing of the world's own drawn yet.
        history_values = [*history_values, round(total, 4)]
    pre_q_rets = (
        list(pre.quarterly_returns_reported if plane == "reported" else pre.quarterly_returns_true)
        if pre is not None
        else []
    )
    performance_footnote = "Payout added back; time-weighted. Twin holds the t0 plan."
    if pre is not None:
        performance_footnote += (
            " 3Y/5Y/10Y include the inherited decade (simulated, scaled to the "
            "opening book - not this world's own history); 1Y crosses that "
            "seam whenever fewer than four world quarters have been played; "
            "Excess is near zero in every long column by construction, "
            "because the twin shares the identical inherited prefix, not "
            "because the plan tracked the benchmark for a decade; private "
            "classes show an em dash in the long columns because a per-class "
            "inherited tape is not exported - not because the inherited "
            "decade has no private history (it ran the full book, privates "
            "included, which is why the true and reported series differ at "
            "all)."
        )

    plan: dict[str, Any] = {
        "totalValue": round(total, 4),
        "growthPct": (round((total / opening_nav - 1.0) * 100.0, 4) if opening_nav > 0 else None),
        "netOfFlows": (round(total - opening_nav + spend_total, 4) if opening_nav > 0 else None),
        # growthPct/netOfFlows above are since-inception (world month 0) only
        # — windowLabel describes THEM, not the chart's hatched band, so it
        # stays "Since inception" regardless of prehistory (review finding,
        # Critical 1: the brief's original instruction to change this was
        # wrong — a decade label beside a one-year figure is the defect).
        "windowLabel": "Since inception",
        "history": {"values": history_values, "worldStartIndex": world_start_index},
    }
    if pre is not None:
        # Tag-length, not sentence-length: these render as un-wrapping SVG
        # <text> in a fixed-width band on the plan chart (app/src/components/
        # CioDashboard.tsx renders the renderer's own hatch/boundary
        # annotations unchanged — DN-8's "dashboard unchanged" promise, so
        # the copy has to fit the existing slot rather than the slot
        # growing to fit the copy). The full sentence lives in
        # performance.footnote instead.
        # I1 (whole-branch review): "simulated" previously appeared only in
        # performance.footnote, under a different panel; nothing on the
        # chart itself said the hatched band was simulated. preRunLabel is
        # centred inside the hatched band (not left-anchored like
        # worldStartLabel), so it has room: ~190px at ~6.8px/char inside a
        # band 758px wide at revealed=12 and 416px at revealed=120.
        plan["preRunLabel"] = "INHERITED DECADE (SIMULATED)"
        plan["worldStartLabel"] = "WORLD BEGINS"

    view: dict[str, Any] = {
        "meta": {
            "runId": run_id,
            "seed": str(seed),
            "worldTitle": world_title,
            "worldVersion": world_version,
            "linkageVersion": LINKAGE_VERSION,
            "decisionAlphaVersion": alpha_version,
            # n_q == 0: no world quarter has closed, so there is no "Y_ Q_" to
            # name — "T0" matches the label Play.tsx's own clock already uses
            # for revealed_months == 0 (dateNow), rather than inventing a
            # second wording for the same moment.
            "asOfLabel": (f"Y{(n_q - 1) // 4 + 1} Q{(n_q - 1) % 4 + 1}" if n_q > 0 else "T0"),
            "asOfMonth": (hist_months - 1 if n_q > 0 else 0),
            "plane": plane,
            "planesAvailable": list(PLANES),
            "unitLabel": UNIT_LABEL,
            "unitSuffix": UNIT_SUFFIX,
            "currency": CURRENCY,
            "watermark": WATERMARK,
            "disclaimer": DISCLAIMER,
        },
        "plan": plan,
        "allocation": _allocation(
            active,
            targets,
            cash_target,
            plane,
            n_q,
            # liquid sleeves have no reporting plane (port/portfolio.py:73 -
            # "liquid marks are true"); on the reported plane, private marks
            # come from the reported tape, listed marks from the true tape.
            {**frozen.returns, **frozen.reported} if plane == "reported" else frozen.returns,
            pre.market_paths if pre is not None else None,
        ),
        "performance": {
            "periods": list(PERIODS),
            "annualisedFromIndex": ANNUALISED_FROM,
            # last_q stays world-relative (YTD is a world-year concept) even
            # though the q_rets fed in are prepended with the inherited
            # decade's quarters.
            "total": _period_row(pre_q_rets + q_rets, n_q - 1),
            "benchmark": _period_row(pre_q_rets + twin_rets, n_q - 1),
            "benchmarkLabel": "Policy twin (hold course)",
            "footnote": performance_footnote,
        },
        "liquidity": _liquidity(active, targets, plane, n_q, forecast_quarters),
        "privateCashflows": _private_cashflows(active, n_q, forecast_quarters, plane),
    }
    markets = _markets(paths, hist_months, plane, pre)
    if markets is not None:
        view["markets"] = markets
    return view


def _allocation(
    active: PlayResult,
    targets: Mapping[str, float],
    cash_target: float,
    plane: str,
    n_q: int,
    tape: Mapping[str, np.ndarray],
    pre_market_paths: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """``cash_target`` is the policy cash the targets are normalised against —
    the entered book's own ``cash`` when there is one, else ``START_CASH``
    (su-app-07 Ruling G). It has to travel WITH ``targets``: the denominator
    is ``sum(targets) + cash``, so taking one from the book and the other
    from the world default would print a percentage neither of them means.

    ``n_q == 0`` (app-open-01, cio-05: the month-0 CIO view) has no closed
    quarter to read — ``active.quarters[-1]`` would silently be the FURTHEST
    forecast quarter, not "now". Reads ``active.opening`` instead, which is
    exactly what "now" means before anything has run."""
    target_total = sum(targets.values()) + cash_target
    if n_q > 0:
        last = active.quarters[n_q - 1]
        total = last.nav_reported if plane == "reported" else last.nav_true
        private = last.private_reported if plane == "reported" else last.private_true
        cash_now = last.cash
        liquid_now = last.liquid_values
    else:
        total = active.opening["nav_reported" if plane == "reported" else "nav_true"]
        private = active.opening["private_reported" if plane == "reported" else "private_true"]
        cash_now = active.opening["cash"]
        liquid_now = active.opening["liquid_values"]

    def value_of(cid: str) -> float:
        if cid == "cash":
            return cash_now
        if cid in PRIVATE_ASSETS:
            return private[cid]
        return liquid_now[cid]

    ids = [*targets.keys(), "cash"]
    ordered = [cid for gid, _ in GOALS for cid in ids if GOAL_OF[cid] == gid]
    classes = []
    for cid in ordered:
        points = cash_target if cid == "cash" else targets[cid]
        classes.append(
            {
                "id": cid,
                "label": CLASS_LABEL[cid],
                "goalId": GOAL_OF[cid],
                "targetPct": round(points / target_total * 100.0, 4),
                "bandPct": BAND_PCT[cid],
                "currentPct": (round(value_of(cid) / total * 100.0, 4) if total > 0 else None),
                "value": round(value_of(cid), 4),
                "returns": _class_returns(tape, cid, n_q, pre_market_paths),
                **({"isPrivate": True} if cid in PRIVATE_ASSETS else {}),
            }
        )
    goal_ids = {c["goalId"] for c in classes}
    return {
        "goals": [
            {"id": gid, "label": label, "tolerancePct": GOAL_TOLERANCE_PCT}
            for gid, label in GOALS
            if gid in goal_ids
        ],
        "classes": classes,
        "alertPolicy": {
            "watchFraction": WATCH_FRACTION,
            "label": "amber inside the last quarter of the band",
        },
    }


def _class_returns(
    tape: Mapping[str, np.ndarray],
    cid: str,
    n_q: int,
    pre_market_paths: Mapping[str, Sequence[float]] | None = None,
) -> list[float | None]:
    """Per-class period returns from the sleeve tape (cash has none -> nulls).

    ``pre_market_paths`` is the inherited decade's per-LIQUID-asset monthly
    tape (``PreHistory.market_paths`` — cio-04 does not export a per-asset
    tape for the private sleeves, so their 3Y/5Y/10Y columns stay governed
    by the world's own revealed window, same as before this WP)."""
    if cid not in tape:  # cash has no tape
        return [None] * len(PERIODS)
    monthly = tape[cid][: n_q * 3]
    q_rets = [float(np.prod(1.0 + monthly[i * 3 : i * 3 + 3] / 100.0)) - 1.0 for i in range(n_q)]
    pre_series = (pre_market_paths or {}).get(cid)
    if pre_series:
        pre_monthly = np.asarray(pre_series, dtype=float)
        n_pre_q = len(pre_monthly) // 3
        pre_q_rets = [
            float(np.prod(1.0 + pre_monthly[i * 3 : i * 3 + 3] / 100.0)) - 1.0
            for i in range(n_pre_q)
        ]
        q_rets = pre_q_rets + q_rets
    return _period_row(q_rets, n_q - 1)


def _liquidity(
    active: PlayResult,
    targets: Mapping[str, float],
    plane: str,
    n_q: int,
    forecast_quarters: int,
) -> dict[str, Any]:
    # n_q == 0 (app-open-01, cio-05): no closed quarter — read the opening
    # state directly rather than `active.quarters[-1]`, which would silently
    # be the FURTHEST forecast quarter, not "now" (same reasoning as
    # `_allocation`).
    if n_q > 0:
        last = active.quarters[n_q - 1]
        total = last.nav_reported if plane == "reported" else last.nav_true
        private = last.private_reported if plane == "reported" else last.private_true
        cash_now = last.cash
        liquid_now = last.liquid_values
        unfunded_now = last.unfunded_total
    else:
        total = active.opening["nav_reported" if plane == "reported" else "nav_true"]
        private = active.opening["private_reported" if plane == "reported" else "private_true"]
        cash_now = active.opening["cash"]
        liquid_now = active.opening["liquid_values"]
        unfunded_now = sum(active.opening["private_unfunded"].values())
    liquid_ids = [a for a in targets if a not in PRIVATE_ASSETS]
    t1_ids = ["cash"] + [a for a in TIER1_CLASSES if a in liquid_ids]
    t2_ids = [a for a in TIER2_CLASSES if a in liquid_ids]
    t1 = cash_now + sum(liquid_now[a] for a in t1_ids if a != "cash")
    t2 = sum(liquid_now[a] for a in t2_ids)
    illiquid = sum(private.values())
    fwd = active.quarters[n_q : n_q + forecast_quarters]
    dist = sum(q.distributions_received for q in fwd)
    calls = sum(q.calls_paid for q in fwd)
    payout = sum(q.spending_paid for q in fwd)

    # unfundedToLiquid: the same liquid base as tiers t1+t2 (cash plus every
    # non-private sleeve), not the t1/t2 SUBSET filtered to `targets` above --
    # liquid_now already only carries non-private ids (play.py's
    # _liquid_snapshot), so summing it whole is the full liquid base.
    liquid_base = cash_now + sum(liquid_now.values())
    unfunded_to_liquid = round(unfunded_now / liquid_base, 4) if liquid_base > 0 else None

    # worstUnfundedToLiquid: the E1 ladder's statistic, live -- the running
    # maximum of unfunded/liquid over every CLOSED quarter so far, not just
    # the as-of quarter.
    worst: float | None = None
    for q in active.quarters[:n_q]:
        base = q.cash + sum(q.liquid_values.values())
        if base <= 0:
            continue
        ratio = q.unfunded_total / base
        if worst is None or ratio > worst:
            worst = ratio
    worst_unfunded_to_liquid = round(worst, 4) if worst is not None else None

    return {
        "tiers": [
            {
                "id": "t1",
                "tier": 1,
                "label": "Tier 1",
                "note": "cash + core bonds",
                "value": round(t1, 4),
                "classIds": t1_ids,
            },
            {
                "id": "t2",
                "tier": 2,
                "label": "Tier 2",
                "note": "listed markets",
                "value": round(t2, 4),
                "classIds": t2_ids,
            },
            {
                "id": "illiquid",
                "label": "Illiquid",
                "note": "closed-end private sleeves",
                "value": round(illiquid, 4),
                "liquid": False,
                "classIds": list(PRIVATE_ASSETS),
            },
        ],
        "forecast12m": {
            "distributions": round(dist, 4),
            "income": 0.0,
            "calls": round(calls, 4),
            "payout": round(payout, 4),
            "net": round(dist + 0.0 - calls - payout, 4),
        },
        "payoutLabel": "spending",
        "unfundedToNav": round(unfunded_now / total, 4) if total > 0 else None,
        "coverageAnchor": COVERAGE_ANCHOR,
        "unfundedToLiquid": unfunded_to_liquid,
        "breachLine": COVERAGE_BREACH_LINE,
        "worstUnfundedToLiquid": worst_unfunded_to_liquid,
        "tierFootnote": "Static class-to-tier mapping (DN-8 O-4); behavioural re-tiering deferred.",
        "flowFootnote": (
            "Roll-forward at the current market state; the model has no income "
            "line, so income is a true zero, not a gap."
        ),
    }


def _private_cashflows(
    active: PlayResult, n_q: int, forecast_quarters: int, plane: str
) -> dict[str, Any]:
    total_q = n_q + forecast_quarters
    nav_key = "private_reported" if plane == "reported" else "private_true"

    def row(asset_ids: list[str], i: int) -> dict[str, Any]:
        q = active.quarters[i]
        prev_nav = (
            {a: active.opening[nav_key][a] for a in asset_ids}
            if i == 0
            else {a: getattr(active.quarters[i - 1], nav_key)[a] for a in asset_ids}
        )
        prev_unf = (
            {a: active.opening["private_unfunded"][a] for a in asset_ids}
            if i == 0
            else {a: active.quarters[i - 1].private_unfunded[a] for a in asset_ids}
        )
        calls = sum(q.private_calls[a] for a in asset_ids)
        dists = sum(q.private_distributions[a] for a in asset_ids)
        expired = sum(q.private_expired[a] for a in asset_ids)
        nav_open, nav_close = sum(prev_nav.values()), sum(getattr(q, nav_key)[a] for a in asset_ids)
        unf_open, unf_close = sum(prev_unf.values()), sum(q.private_unfunded[a] for a in asset_ids)
        return {
            "label": f"Y{i // 4 + 1}Q{i % 4 + 1}",
            "forecast": i >= n_q,
            "calls": round(calls, 4),
            "distributions": round(dists, 4),
            "net": round(dists - calls, 4),
            "navOpen": round(nav_open, 4),
            "navClose": round(nav_close, 4),
            "unfundedOpen": round(unf_open, 4),
            "unfundedClose": round(unf_close, 4),
            "callRateUnfunded": round(calls / unf_open, 4) if unf_open > 0 else None,
            "callRateNav": round(calls / nav_open, 4) if nav_open > 0 else None,
            "coverage": round(unf_close / nav_close, 4) if nav_close > 0 else None,
            "expiredUndrawn": round(expired, 4),
        }

    series = {"aggregate": [row(list(PRIVATE_ASSETS), i) for i in range(total_q)]}
    for a in PRIVATE_ASSETS:
        series[a] = [row([a], i) for i in range(total_q)]
    return {
        "histCount": n_q,
        "classes": [{"id": a, "label": CLASS_LABEL[a]} for a in PRIVATE_ASSETS],
        "aggregateLabel": "All private sleeves",
        "series": series,
        # n_q == 0 (app-open-01, cio-05): no closed quarter carries a
        # `vintage_nav` snapshot yet, and the opening book only tracks
        # per-SLEEVE NAV, not per-cohort — `vintages` is optional on the
        # contract precisely for this, so it is omitted rather than
        # approximated from the first forecast quarter's (already-projected)
        # cohort state.
        "vintages": _vintage_ladder(active.quarters[n_q - 1]) if n_q > 0 else [],
        "footnote": (
            "Closed-end cohorts only; the model holds no open-end or evergreen "
            "vehicles in this book (DN-8 O-8). Forecast rows are a mechanical "
            "roll-forward at the current market state, not a projection. "
            "expiredUndrawn is undrawn commitment CANCELLED at the end of a "
            "cohort's contractual life (ER-6) — it leaves the unfunded balance "
            "without ever being called, so it is never a call the player pays. "
            "The vintage ladder is snapshotted at the as-of quarter and carries "
            "true NAV only: a reported (appraisal-smoothed) NAV per cohort is "
            "not tracked by the engine, so it is omitted rather than invented."
        ),
    }


def _vintage_sort_key(cohort_id: str) -> tuple[int, str]:
    """Oldest-first ordering for a cohort id, without inventing a calendar year.

    ``{asset}-s{K}`` is a seeded opening-book rung: K=0 is its NEWEST vintage
    and larger K is older (:func:`_seed_ladder`). ``{asset}-v{Y}`` is a
    commitment made during play: larger Y is newer
    (:func:`_commit_new_vintage`). Both offsets are measured from the SAME
    base vintage year, so ``-K`` and ``+Y`` sit on one comparable scale
    without reading the base year itself. Ties (same offset, different
    asset) break on the id string for a fully deterministic order.
    """
    _, tag = cohort_id.rsplit("-", 1)
    n = int(tag[1:])
    key = -n if tag[0] == "s" else n
    return (key, cohort_id)


def _vintage_ladder(as_of: Any) -> list[dict[str, Any]]:
    """The as-of quarter's cohort NAV stack, oldest vintage first.

    True NAV only (``PlayQuarter.vintage_nav``) — a per-cohort REPORTED mark
    is not tracked anywhere in the engine, so this deliberately does not
    invent one alongside it (task cio-03b's whole reason for existing: a
    prior retirement claimed coverage of this ladder that did not exist).
    """
    ids = sorted(as_of.vintage_nav, key=_vintage_sort_key)
    out = []
    for cid in ids:
        asset, tag = cid.rsplit("-", 1)
        out.append(
            {
                "id": cid,
                "label": f"{CLASS_LABEL[asset]} · {tag}",
                "navTrue": round(float(as_of.vintage_nav[cid]), 4),
            }
        )
    return out


_MARKET_COLOURS = {
    "equity": "#F0C46A",
    "bonds": "#6E9BD1",
    "hy": "#D9705A",
    "commodities": "#58B49E",
    "reits": "#A88BC4",
}


def _markets(
    paths: EnginePaths, hist_months: int, plane: str, pre: PreHistory | None = None
) -> dict[str, Any] | None:
    if hist_months < 2:
        return None
    liquid = [a for a in paths.asset_order if a not in PRIVATE_ASSETS]
    footnote = (
        "Indexed to 100 at world start, not the inherited decade's start; the "
        "leading segment is the simulated pre-history (cio-04), rescaled to "
        "land on the opening book."
        if pre is not None
        else "Indexed to 100 at world start; revealed tape only."
    )
    out: dict[str, Any] = {
        "tiles": [
            {"label": "Policy rate", "value": f"{float(paths.rate[hist_months - 1]):.2f}%"},
            {"label": "HY spread", "value": f"{float(paths.spread[hist_months - 1]):.0f}bps"},
            {"label": "Inflation", "value": f"{float(paths.inflation[hist_months - 1]):.1f}%"},
        ],
        "returns": [],
        "returnsFootnote": footnote,
    }
    for a in liquid:
        world_monthly = paths.returns[a][:hist_months]
        if pre is not None:
            # Index to 100 at the world-start boundary: cumprod the whole
            # combined tape from an arbitrary base, then rescale so the
            # level right at the boundary (the last pre-history month,
            # index pre.months - 1) lands on 100. World-segment values then
            # fall out identical to the no-prehistory formula below (a
            # constant rescale cancels inside every ratio).
            pre_monthly = np.asarray(pre.market_paths[a], dtype=float)
            combined = np.concatenate([pre_monthly, world_monthly])
            raw = np.cumprod(1.0 + combined / 100.0)
            path = raw * (100.0 / raw[pre.months - 1])
        else:
            path = 100.0 * np.cumprod(1.0 + world_monthly / 100.0)
        out["returns"].append(
            {
                "id": a,
                "label": CLASS_LABEL[a],
                "colour": _MARKET_COLOURS.get(a, "#8FA2BE"),
                "path": [round(float(x), 2) for x in path],
            }
        )
    if hist_months >= 24:
        # This world's own revealed months only — the inherited decade is
        # never mixed into a correlation the player would read as this
        # world's (correlationNote states the window either way, below).
        eq = paths.returns["equity"][:hist_months]
        corrs = []
        for a in liquid:
            if a == "equity":
                continue
            s = paths.returns[a][:hist_months]
            corrs.append(
                {
                    "id": a,
                    "label": CLASS_LABEL[a],
                    "current": round(float(np.corrcoef(eq[-12:], s[-12:])[0, 1]), 2),
                    "baseline": round(float(np.corrcoef(eq, s)[0, 1]), 2),
                }
            )
        out["correlations"] = corrs
        # Minor 2 (whole-branch review), then re-reviewed: on main this note
        # was unconditionally the base sentence below — correct and
        # prehistory-neutral. The original finding was about the
        # inherited-decade clause this WP appended, not about the note's
        # existence; guarding the whole assignment on `pre is not None`
        # over-corrected and left opted-out worlds with NO correlationNote,
        # so the renderer fell back to its own generic copy and the window
        # definition was lost. Restored as an if/else: base sentence always,
        # clause appended only when there is an inherited decade to exclude.
        note = "current: trailing 12m; baseline: full revealed window"
        if pre is not None:
            note += (
                "; both computed on this world's own months only, excluding the inherited decade."
            )
        out["correlationNote"] = note
    return out


def validate_cio_view(v: dict[str, Any]) -> list[str]:
    """Port of ``validateCioView`` — empty list means the payload is valid."""
    e: list[str] = []

    def near(a: float, b: float, tol: float = 0.1) -> bool:
        return abs(a - b) <= tol

    meta = v.get("meta") or {}
    if not meta.get("runId"):
        e.append("meta.runId is required")
    if not meta.get("linkageVersion"):
        e.append("meta.linkageVersion is required and is disclosed on screen")
    if meta.get("plane") not in (meta.get("planesAvailable") or []):
        e.append("meta.plane is not in meta.planesAvailable")

    alloc = v.get("allocation") or {}
    classes = alloc.get("classes") or []
    goals = alloc.get("goals") or []
    cur = sum(c.get("currentPct") or 0.0 for c in classes)
    tgt = sum(c["targetPct"] for c in classes)
    if not near(cur, 100.0):
        e.append(f"allocation.classes currentPct sums to {cur:.2f}, expected 100")
    if not near(tgt, 100.0):
        e.append(f"allocation.classes targetPct sums to {tgt:.2f}, expected 100")

    goal_ids = {g["id"] for g in goals}
    periods = (v.get("performance") or {}).get("periods") or []
    for c in classes:
        if c["goalId"] not in goal_ids:
            e.append(f"class {c['id']} references unknown goal {c['goalId']}")
        if c.get("returns") is not None and len(c["returns"]) != len(periods):
            e.append(f"class {c['id']} has {len(c['returns'])} returns, expected {len(periods)}")
        if c["bandPct"] < 0:
            e.append(f"class {c['id']} has a negative band")

    ap = alloc.get("alertPolicy")
    wf = ap.get("watchFraction") if ap else None
    if ap and wf is not None and not (0.0 < wf < 1.0):
        e.append(
            f"allocation.alertPolicy.watchFraction is {wf}, expected between 0 and 1 exclusive"
        )
    if wf is None and not any(c.get("alert") for c in classes):
        e.append("no alertPolicy.watchFraction and no explicit class.alert - amber will never fire")
    explicit = sum(1 for c in classes if c.get("alert"))
    if 0 < explicit < len(classes):
        e.append(f"{explicit} of {len(classes)} classes carry an explicit alert - all or none")
    for g in goals:
        tol = g.get("tolerancePct")
        if tol is not None and tol <= 0:
            e.append(f"goal {g['id']} has a non-positive tolerancePct")
        if tol is None and not g.get("alert"):
            e.append(f"goal {g['id']} has neither tolerancePct nor alert - it will never flag")

    order = [next((i for i, g in enumerate(goals) if g["id"] == c["goalId"]), -1) for c in classes]
    if any(order[i] < order[i - 1] for i in range(1, len(order))):
        e.append("allocation.classes are not grouped in goal order")

    perf = v.get("performance") or {}
    if len(perf.get("total") or []) != len(periods):
        e.append("performance.total length != periods length")
    if perf.get("benchmark") is not None and len(perf["benchmark"]) != len(periods):
        e.append("performance.benchmark length != periods length")

    liq = v.get("liquidity") or {}
    plan_total = (v.get("plan") or {}).get("totalValue") or 0.0
    tier_sum = sum(t["value"] for t in liq.get("tiers") or [])
    if not near(tier_sum, plan_total, max(0.1, plan_total * 0.005)):
        e.append(f"liquidity tiers sum to {tier_sum:.1f}, plan total is {plan_total:.1f}")
    f = liq.get("forecast12m")
    if f:
        for k in ("distributions", "income", "calls", "payout"):
            if isinstance(f.get(k), (int, float)) and f[k] < 0:
                e.append(f"liquidity.forecast12m.{k} must be a positive magnitude")
        net = f["distributions"] + f["income"] - f["calls"] - f["payout"]
        if not near(net, f["net"], 1.0):
            e.append(f"liquidity.forecast12m.net is {f['net']}, components imply {net:.1f}")
    for key in ("unfundedToLiquid", "worstUnfundedToLiquid"):
        val = liq.get(key)
        if isinstance(val, (int, float)) and val < 0:
            e.append(f"liquidity.{key} must be a non-negative ratio")
    breach = liq.get("breachLine")
    if breach is not None and breach != COVERAGE_BREACH_LINE:
        e.append(f"liquidity.breachLine is {breach}, expected exactly {COVERAGE_BREACH_LINE}")

    pcf = v.get("privateCashflows")
    if pcf:
        agg = (pcf.get("series") or {}).get("aggregate")
        # `agg is None`, not `not agg`: an EMPTY (but present) aggregate is a
        # legitimate month-0 payload (app-open-01, cio-05 — histCount=0 and
        # forecast_quarters=0 together leave every series at length 0). The
        # TS twin's `!agg` already treats `[]` as present (arrays are
        # truthy in JS); `not agg` was a silent parity gap only reachable
        # once this shape became real.
        if agg is None:
            e.append("privateCashflows.series.aggregate is required")
        n = len(agg or [])
        if pcf["histCount"] > n:
            e.append("privateCashflows.histCount exceeds series length")
        for key, rows in (pcf.get("series") or {}).items():
            if len(rows) != n:
                e.append(f"private series {key} has length {len(rows)}, aggregate has {n}")
            for i, r in enumerate(rows):
                if r["calls"] < 0 or r["distributions"] < 0:
                    e.append(
                        f"{key} {r['label']}: calls and distributions must be positive magnitudes"
                    )
                if not near(r["net"], r["distributions"] - r["calls"], 0.5):
                    e.append(f"{key} {r['label']}: net != distributions - calls")
                if agg and i < n and rows[i]["label"] != agg[i]["label"]:
                    e.append(f"{key} quarter {i} label does not match aggregate")
                if (i >= pcf["histCount"]) != r["forecast"]:
                    e.append(f"{key} {r['label']}: forecast flag disagrees with histCount")
        if agg:
            class_ids = [c["id"] for c in pcf.get("classes") or []]
            for i, r in enumerate(agg):
                s = sum(
                    (pcf["series"].get(cid) or [{}] * n)[i].get("calls", 0.0) for cid in class_ids
                )
                if not near(s, r["calls"], max(0.5, r["calls"] * 0.001)):
                    e.append(f"aggregate calls at {r['label']} != sum of classes")
                s_exp = sum(
                    (pcf["series"].get(cid) or [{}] * n)[i].get("expiredUndrawn", 0.0)
                    for cid in class_ids
                )
                r_exp = r.get("expiredUndrawn", 0.0)
                if not near(s_exp, r_exp, max(0.5, r_exp * 0.001)):
                    e.append(f"aggregate expiredUndrawn at {r['label']} != sum of classes")

    h_len = len(((v.get("plan") or {}).get("history") or {}).get("values") or [])
    mk = v.get("markets") or {}
    for s in (mk.get("returns") or []) + (mk.get("conditions") or []):
        if len(s["path"]) != h_len:
            e.append(
                f"market series {s['id']} has {len(s['path'])} points, plan history has {h_len}"
            )

    for where in ("total", "benchmark"):
        arr = perf.get(where)
        if arr:
            for i, x in enumerate(arr):
                if x == 0:
                    e.append(
                        f"performance.{where}[{i}] is exactly 0 - confirm real zero vs unreached"
                    )

    return e
