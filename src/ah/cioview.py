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
from ah.prehistory import PreHistory, build_prehistory

PLANES: tuple[str, str] = ("reported", "true")
LINKAGE_VERSION = "public-0.1"
WATCH_FRACTION = 0.75  # DN-8 section 3: amber inside the last quarter of the band
COVERAGE_ANCHOR = 0.5  # WP3.10 section 5 steady-state anchor
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
    hold = lambda a: np.concatenate([a[:n], np.full(extra, float(a[n - 1]))])  # noqa: E731
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
) -> dict[str, Any]:
    """``prehistory`` prepends the inherited decade (cio-04) ahead of world
    month 0 — the plan chart, the long return windows and the market-path
    charts all gain a pre-run segment that terminates exactly on this
    world's own opening book. It is a display decision, not an engine one:
    ``build_prehistory`` always runs the toy engine internally regardless of
    which engine produced ``paths``, so a caller splicing it onto a
    generated (non-toy-v0) world would be stitching two engines into one
    chart. This function does not sniff ``paths`` for that — the caller
    decides and passes the flag (``ah/serve.py``)."""
    if plane not in PLANES:
        raise ValueError(f"plane must be one of {PLANES}, got {plane!r}")
    n_q = revealed_months // 3
    if n_q < 1:
        raise ValueError("no closed quarter inside the revealed window")
    hist_months = n_q * 3
    frozen = _frozen_paths(paths, hist_months, forecast_quarters)
    active = simulate_play(frozen, dict(decisions), start_targets=start_targets)
    twin = simulate_play(frozen, None, start_targets=start_targets)
    targets = dict(start_targets) if start_targets is not None else dict(START_TARGETS)
    last = active.quarters[n_q - 1]
    q_rets = _quarterly_returns(active, plane, n_q)
    twin_rets = _quarterly_returns(twin, plane, n_q)

    nav_attr = "nav_reported_months" if plane == "reported" else "nav_true_months"
    history = [round(m, 4) for q in active.quarters[:n_q] for m in getattr(q, nav_attr)]
    total = last.nav_reported if plane == "reported" else last.nav_true
    # world month 0's own opening book — untouched by prehistory (cio-04's
    # seam is stitched on NAV only); growthPct/netOfFlows read off this, not
    # off history[0], so they stay world-relative regardless of prehistory.
    opening_nav = active.opening["nav_reported" if plane == "reported" else "nav_true"]
    spend_total = sum(q.spending_paid for q in active.quarters[:n_q])

    pre: PreHistory | None = None
    if prehistory:
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
        plan["preRunLabel"] = "INHERITED DECADE"
        plan["worldStartLabel"] = "WORLD BEGINS"

    view: dict[str, Any] = {
        "meta": {
            "runId": run_id,
            "seed": str(seed),
            "worldTitle": world_title,
            "worldVersion": world_version,
            "linkageVersion": LINKAGE_VERSION,
            "decisionAlphaVersion": alpha_version,
            "asOfLabel": f"Y{(n_q - 1) // 4 + 1} Q{(n_q - 1) % 4 + 1}",
            "asOfMonth": hist_months - 1,
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
    plane: str,
    n_q: int,
    tape: Mapping[str, np.ndarray],
    pre_market_paths: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    last = active.quarters[n_q - 1]
    total = last.nav_reported if plane == "reported" else last.nav_true
    target_total = sum(targets.values()) + START_CASH
    private = last.private_reported if plane == "reported" else last.private_true

    def value_of(cid: str) -> float:
        if cid == "cash":
            return last.cash
        if cid in PRIVATE_ASSETS:
            return private[cid]
        return last.liquid_values[cid]

    ids = [*targets.keys(), "cash"]
    ordered = [cid for gid, _ in GOALS for cid in ids if GOAL_OF[cid] == gid]
    classes = []
    for cid in ordered:
        points = START_CASH if cid == "cash" else targets[cid]
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
    last = active.quarters[n_q - 1]
    total = last.nav_reported if plane == "reported" else last.nav_true
    private = last.private_reported if plane == "reported" else last.private_true
    liquid_ids = [a for a in targets if a not in PRIVATE_ASSETS]
    t1_ids = ["cash"] + [a for a in TIER1_CLASSES if a in liquid_ids]
    t2_ids = [a for a in TIER2_CLASSES if a in liquid_ids]
    t1 = last.cash + sum(last.liquid_values[a] for a in t1_ids if a != "cash")
    t2 = sum(last.liquid_values[a] for a in t2_ids)
    illiquid = sum(private.values())
    fwd = active.quarters[n_q : n_q + forecast_quarters]
    dist = sum(q.distributions_received for q in fwd)
    calls = sum(q.calls_paid for q in fwd)
    payout = sum(q.spending_paid for q in fwd)
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
        "unfundedToNav": round(last.unfunded_total / total, 4) if total > 0 else None,
        "coverageAnchor": COVERAGE_ANCHOR,
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
        }

    series = {"aggregate": [row(list(PRIVATE_ASSETS), i) for i in range(total_q)]}
    for a in PRIVATE_ASSETS:
        series[a] = [row([a], i) for i in range(total_q)]
    return {
        "histCount": n_q,
        "classes": [{"id": a, "label": CLASS_LABEL[a]} for a in PRIVATE_ASSETS],
        "aggregateLabel": "All private sleeves",
        "series": series,
        "footnote": (
            "Closed-end cohorts only; the model holds no open-end or evergreen "
            "vehicles in this book (DN-8 O-8). Forecast rows are a mechanical "
            "roll-forward at the current market state, not a projection."
        ),
    }


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
        # world's (see correlationNote below).
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
        out["correlationNote"] = (
            "current: trailing 12m; baseline: full revealed window; both computed "
            "on this world's own months only, excluding the inherited decade."
        )
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

    pcf = v.get("privateCashflows")
    if pcf:
        agg = (pcf.get("series") or {}).get("aggregate")
        if not agg:
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
