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

from typing import Any

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
