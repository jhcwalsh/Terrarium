"""Inspection points I4 and I6 (MPP-A1 / liquidity-spine v0.2 s12) — Step 4 pre-work.

Run:  uv run python scripts/run_inspection_i4_i6.py

Renders the two exhibits the owner inspects before wp4-01 branches:

I4 — the reported-vs-true toggle across 2021-2023 (the reference case).
     Three things must be visible: (1) reported drawdown materially shallower
     than true; (2) the gap widening INTO the trough (SM-11 stickiness);
     (3) the denominator effect in the private weight, on both planes.

I6 — one liquidity timeline across the same episode: cash, calls,
     distributions, spending, net cashflow, coverage on both bases, forced
     sales marked, and the vintage stack so the age profile is visible.

Diagnostic with teeth, not a gate: red flags become work items recorded in
the exhibit, against register rows, before G4 closes. Deterministic —
observed inputs, frozen artifacts, no RNG.

Conventions (stated, not hidden): the PM reported plane uses the hf_event
theta as stand-in (the Geltner family is UNPARAMETERIZED by the sealed PM
unavailability — same convention as the G1 replay); vintage-stack warm-up
runs at a constant 3%/quarter calm return with f_call = f_dist = 1.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.port import smoothing as sk
from ah.port.cashflow_tier1 import f_call, f_dist
from ah.port.cohort import ClosedEndCohort
from ah.port.engine import Policy, PortfolioEngine
from ah.port.mapping import load_artifact as load_mapping
from ah.port.portfolio import Portfolio
from ah.port.sleeves import LiquidSleeve

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = _REPO_ROOT / "governance" / "evidence" / "I4-I6-INSPECTION.md"
WINDOW = ("2021-12-01", "2023-12-31")
VINTAGES = tuple(range(2015, 2022))
CALM_QUARTERLY_RETURN = 0.03
PM_LOADINGS = {"equity_mkt": 1.2, "smb": 0.2, "hml": 0.2}  # frozen pm_buyout row
START_PRIVATE_WEIGHT = 0.38
CASH_FRACTION = 0.04


def _series(catalog: Catalog, vintage: str, sid: str) -> pd.Series:
    frame = catalog.read_observations(vintage, sid)
    s = pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(frame["date"]),
    )
    return s.loc[WINDOW[0] : WINDOW[1]]


def _drawdown(cum: pd.Series) -> pd.Series:
    return cum / cum.cummax() - 1.0


def _bar(value: float, scale: float, width: int = 24) -> str:
    n = 0 if scale <= 0 else max(0, min(width, round(abs(value) / scale * width)))
    return "#" * n


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")

    mkt = _series(catalog, vintage, "french.mkt_rf") + _series(catalog, vintage, "french.rf")
    cum_public = (1.0 + mkt).cumprod()
    public_trough = _drawdown(cum_public).idxmin()
    ig = _series(catalog, vintage, "fred.BAA") - _series(catalog, vintage, "fred.AAA")
    baa = pd.Series(
        pd.to_numeric(catalog.read_observations(vintage, "fred.BAA")["value"]).to_numpy(float),
        index=pd.to_datetime(catalog.read_observations(vintage, "fred.BAA")["date"]),
    )
    aaa = pd.Series(
        pd.to_numeric(catalog.read_observations(vintage, "fred.AAA")["value"]).to_numpy(float),
        index=pd.to_datetime(catalog.read_observations(vintage, "fred.AAA")["date"]),
    )
    spread_anchor = float((baa - aaa).loc["2019-01-01":"2021-12-31"].mean())
    dd_monthly = (-_drawdown(cum_public)).clip(lower=0.0)
    ratio_monthly = (ig / spread_anchor).clip(lower=0.5)

    # ================= I4 — the toggle ================================== #
    mapping = load_mapping()
    regressors = {
        "equity_mkt": mkt,
        "smb": _series(catalog, vintage, "french.smb"),
        "hml": _series(catalog, vintage, "french.hml"),
        "mom": _series(catalog, vintage, "french.mom"),
        "d_level": _series(catalog, vintage, "fred.DGS10").diff().fillna(0.0),
        "d_slope": (
            _series(catalog, vintage, "fred.DGS10") - _series(catalog, vintage, "fred.DGS2")
        )
        .diff()
        .fillna(0.0),
        "d_ig": ig.diff().fillna(0.0),
    }
    hf_true_sleeves, hf_rep_sleeves = [], []
    for sleeve, spec in mapping["sleeves"].items():
        true = pd.Series(float(spec["alpha_monthly"]), index=mkt.index)
        for reg, beta in spec["loadings"].items():
            true = true + float(beta) * regressors[reg]
        hf_true_sleeves.append(true)
        hf_rep_sleeves.append(
            pd.Series(sk.smooth(true.to_numpy(), sk.theta_for(sleeve)), index=mkt.index)
        )
    hf_true = sum(hf_true_sleeves) / len(hf_true_sleeves)
    hf_rep = sum(hf_rep_sleeves) / len(hf_rep_sleeves)
    dd_hf_true = _drawdown((1.0 + hf_true).cumprod())
    dd_hf_rep = _drawdown((1.0 + hf_rep).cumprod())
    gap = dd_hf_rep - dd_hf_true  # positive = reported shallower

    # PM: quarterly true vs reported (hf_event stand-in theta, stated above)
    factors_q = {
        f: regressors[f].resample("QE").sum().to_numpy() for f in ("equity_mkt", "smb", "hml")
    }
    pm_true_q = sum(w * factors_q[f] for f, w in PM_LOADINGS.items())
    qidx = pd.date_range(WINDOW[0], periods=len(pm_true_q), freq="QE")
    theta_pm = sk.theta_for("hf_event")
    pm_rep_q = sk.smooth(np.asarray(pm_true_q), theta_pm)
    dd_pm_true = _drawdown(pd.Series((1.0 + pm_true_q).cumprod(), index=qidx))
    dd_pm_rep = _drawdown(pd.Series((1.0 + pm_rep_q).cumprod(), index=qidx))

    # the denominator effect: the 62/38 book's private weight on both planes
    liquid_ix = (1.0 - START_PRIVATE_WEIGHT) * cum_public / cum_public.iloc[0]
    pm_m_true = (
        ((1.0 + pd.Series(pm_true_q, index=qidx)) ** (1 / 3))
        .reindex(mkt.index, method="bfill")
        .fillna(1.0)
        .cumprod()
    )
    pm_m_rep = (
        ((1.0 + pd.Series(pm_rep_q, index=qidx)) ** (1 / 3))
        .reindex(mkt.index, method="bfill")
        .fillna(1.0)
        .cumprod()
    )
    w_true = START_PRIVATE_WEIGHT * pm_m_true / (START_PRIVATE_WEIGHT * pm_m_true + liquid_ix)
    w_rep = START_PRIVATE_WEIGHT * pm_m_rep / (START_PRIVATE_WEIGHT * pm_m_rep + liquid_ix)

    trough_hf = dd_hf_true.idxmin()
    m3 = trough_hf - pd.DateOffset(months=3)
    i4_checks = {
        "shallower_hf": float(dd_hf_rep.min()) > float(dd_hf_true.min()),
        "shallower_pm": float(dd_pm_rep.min()) > float(dd_pm_true.min()),
        "gap_widens": float(gap.loc[:trough_hf].iloc[-1]) > float(gap.loc[:m3].iloc[-1]),
        "denominator": float(w_rep.loc[public_trough]) > float(w_true.iloc[0])
        and float(w_rep.loc[public_trough]) > float(w_true.loc[public_trough]),
    }

    # ================= I6 — the liquidity timeline ====================== #
    base = json.loads(
        (_REPO_ROOT / "fixtures" / "state" / "closed-end-cohort.example.json").read_text("utf-8")
    )
    liquid_doc = json.loads(
        (_REPO_ROOT / "fixtures" / "state" / "liquid-sleeve.example.json").read_text("utf-8")
    )
    dd_q = dd_monthly.resample("QE").last().to_numpy()
    ratio_q = ratio_monthly.resample("QE").last().to_numpy()
    public_q = (1.0 + mkt).resample("QE").prod().to_numpy() - 1.0
    n_q = len(dd_q)

    cohorts: dict[str, ClosedEndCohort] = {}
    rep_paths: dict[str, np.ndarray] = {}
    for v in VINTAGES:
        c = ClosedEndCohort.new_commitment(base, committed=100.0, vintage_year=v, cohort_id=f"v{v}")
        warmup = (2022 - v) * 4
        for _ in range(warmup):
            c.step(CALM_QUARTERLY_RETURN, f_call=1.0, f_dist=1.0)
        full = np.concatenate([np.full(warmup, CALM_QUARTERLY_RETURN), pm_true_q])
        rep_full = sk.smooth(full, theta_pm)
        c.report(c.nav_true)  # reported meets true at the window door
        cohorts[f"v{v}"] = c
        rep_paths[f"v{v}"] = rep_full[warmup:]

    private_start = sum(c.nav_true for c in cohorts.values())
    liquid_value = private_start * (1.0 - START_PRIVATE_WEIGHT) / START_PRIVATE_WEIGHT
    book = private_start + liquid_value
    liquid_doc["value"] = liquid_value
    liquid_doc["weight"] = 1.0 - START_PRIVATE_WEIGHT
    sleeve = LiquidSleeve.from_document(liquid_doc)

    portfolio = Portfolio(cash=CASH_FRACTION * book)
    for key, c in cohorts.items():
        portfolio.add(key, c)
    portfolio.add("public_equity", sleeve)
    engine = PortfolioEngine(portfolio, Policy())

    rows = []
    stack_rows = []
    for t in range(n_q):
        sleeve.apply_return(float(public_q[t]))
        fc = f_call(float(dd_q[t]))
        fd = f_dist(float(dd_q[t]), float(ratio_q[t]))
        calls = dists = 0.0
        for key, c in cohorts.items():
            step = c.step(float(pm_true_q[t]), f_call=fc, f_dist=fd)
            calls += step.call
            dists += step.distribution_total
            c.report(c.nav_reported * (1.0 + float(rep_paths[key][t])))
        report = engine.run_quarter(distributions=dists, calls=calls)
        rows.append(report)
        stack_rows.append({key: c.nav_true for key, c in cohorts.items()})

    terminal_dist_rate = float(base["parameters"]["yield_rate"])  # register Y, %/yr at age L
    i6_checks = {
        "calls_vary": (max(r.calls_paid for r in rows) - min(r.calls_paid for r in rows))
        > 0.05 * max(r.calls_paid for r in rows),
        "drought_visible": min(r.distributions_received for r in rows[2:6])
        < 0.75 * rows[0].distributions_received,
        "age_profile": cohorts["v2015"].unfunded
        < cohorts["v2018"].unfunded
        < cohorts["v2021"].unfunded,
        "dist_level_credible": terminal_dist_rate >= 0.05,
        "forced_sales_bounded": 0 <= len(portfolio.forced_sales) < n_q,
    }
    forced_kinds = sorted({e["kind"] for e in portfolio.forced_sales})

    # ================= render ========================================== #
    q_labels = [
        d.strftime("%YQ%q") if False else f"{d.year}Q{(d.month - 1) // 3 + 1}" for d in qidx
    ]
    lines = [
        "# I4 + I6 inspection — the 2021-2023 reference episode",
        "",
        f"Vintage `{vintage}`; window {WINDOW[0]}..{WINDOW[1]}; public trough"
        f" {public_trough.date()}. Produced by `scripts/run_inspection_i4_i6.py`"
        " (deterministic: observed inputs, frozen artifacts, no RNG). Inspection"
        " points are diagnostic with teeth (MPP-A1 standing rule): they cannot"
        " pass what a battery failed, and red flags below are recorded as work"
        " items before G4 closes.",
        "",
        "## I4 — the reported-vs-true toggle (MPP-A1)",
        "",
        "HF composite, monthly (equal-weight frozen sleeves; per-sleeve theta):",
        "",
        "| month | dd true | dd reported | gap (rep-true) |",
        "|---|---|---|---|",
    ]
    for d in dd_hf_true.index:
        lines.append(f"| {d.date()} | {dd_hf_true[d]:+.4f} | {dd_hf_rep[d]:+.4f} | {gap[d]:+.4f} |")
    lines += [
        "",
        "PM cohort plane, quarterly (hf_event theta stand-in — Geltner family is",
        "UNPARAMETERIZED by the sealed PM unavailability, convention stated):",
        "",
        "| quarter | dd true | dd reported | w_true | w_reported |",
        "|---|---|---|---|---|",
    ]
    w_true_q = w_true.resample("QE").last()
    w_rep_q = w_rep.resample("QE").last()
    for i, d in enumerate(qidx):
        lines.append(
            f"| {q_labels[i]} | {dd_pm_true[d]:+.4f} | {dd_pm_rep[d]:+.4f} "
            f"| {w_true_q[d]:.4f} | {w_rep_q[d]:.4f} |"
        )
    lines += [
        "",
        "### The three things the protocol says must be visible",
        "",
        f"1. **Reported materially shallower than true** — "
        f"{'VISIBLE' if i4_checks['shallower_hf'] and i4_checks['shallower_pm'] else 'NOT VISIBLE'}."
        f" HF: true {dd_hf_true.min():+.4f} vs reported {dd_hf_rep.min():+.4f};"
        f" PM: true {dd_pm_true.min():+.4f} vs reported {dd_pm_rep.min():+.4f}.",
        f"2. **Gap widening into the trough** — "
        f"{'VISIBLE' if i4_checks['gap_widens'] else 'NOT VISIBLE'}"
        f" (gap {float(gap.loc[:m3].iloc[-1]):+.4f} three months before the true"
        f" trough -> {float(gap.loc[:trough_hf].iloc[-1]):+.4f} at it). **Caveat,"
        " and it is the point:** this widening comes from the MA kernel alone."
        " SM-11 state-dependent stickiness is MEASURED ZERO on the frozen panel"
        " (kernel artifact, stickiness_evidence), so the parameter contributes"
        " nothing here; the G1 replay's mark_lag FAIL already recorded that 2022's"
        " lag does not fully emerge from MA structure. Standing work item (next"
        " generator campaign, with the HY splice): re-estimate stickiness with"
        " post-2021 data in view. Recorded against SM-11; not tunable now.",
        f"3. **The denominator effect on the private weight** — "
        f"{'VISIBLE' if i4_checks['denominator'] else 'NOT VISIBLE'}."
        f" On the reported plane the weight rises from {float(w_rep.iloc[0]):.4f}"
        f" to {float(w_rep.loc[public_trough]):.4f} at the public trough; the true"
        f" plane reads {float(w_true.loc[public_trough]):.4f} there. With the"
        " levered PM beta (1.2) the true weight also drifts up before its deeper"
        " marks catch down - the planes DIVERGE (reported above true through the"
        " trough), which is the mechanic the toggle exists to show.",
        "",
        "## I6 — the liquidity timeline (liquidity-spine v0.2 s12)",
        "",
        f"Vintage stack {VINTAGES[0]}-{VINTAGES[-1]}, 100 committed each; warm-up"
        f" at {CALM_QUARTERLY_RETURN:.0%}/q calm; observed window states; frozen"
        " tier-1 linkage; engine waterfall with spending off trailing REPORTED"
        f" value (Policy defaults). Book at the door: {book:,.0f}"
        f" ({1 - START_PRIVATE_WEIGHT:.0%} public / {START_PRIVATE_WEIGHT:.0%}"
        f" private), cash {CASH_FRACTION:.0%}.",
        "",
        "| quarter | calls | dists | spending | net cf | cash end | cov true | cov liquid | forced |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows):
        net = r.distributions_received - r.calls_paid - r.spending_paid
        lines.append(
            f"| {q_labels[i]} | {r.calls_paid:.2f} | {r.distributions_received:.2f} "
            f"| {r.spending_paid:.2f} | {net:+.2f} | {r.cash_end:.2f} "
            f"| {r.coverage_true:.3f} | {r.coverage_liquid:.3f} "
            f"| {'FORCED' if r.forced_sale_total > 0 else ''} |"
        )
    nav_scale = max(sum(s.values()) for s in stack_rows)
    lines += [
        "",
        "Vintage stack (true NAV; `#` = stacked area, oldest at left):",
        "",
        "```",
    ]
    for i, snap in enumerate(stack_rows):
        segs = "|".join(_bar(snap[f"v{v}"], nav_scale, width=8) for v in VINTAGES)
        lines.append(f"{q_labels[i]}  {segs}  total {sum(snap.values()):7.1f}")
    lines += [
        "```",
        "",
        "### What the protocol says this catches, checked",
        "",
        f"- Calls too smooth: calls range "
        f"{min(r.calls_paid for r in rows):.2f}..{max(r.calls_paid for r in rows):.2f}"
        f" per quarter — {'VARY (not flat)' if i6_checks['calls_vary'] else 'FLAT - red flag'}."
        " f_call is near-flat by Delta 3 (measured), so most variation is the"
        " age profile, which is the honest shape.",
        f"- Drought too shallow/deep: distributions fall from"
        f" {rows[0].distributions_received:.2f} to"
        f" {min(r.distributions_received for r in rows):.2f} at the trough —"
        f" {'shape VISIBLE' if i6_checks['drought_visible'] else 'NOT VISIBLE - red flag'}"
        " as a RATIO (the G1 replay scored depth 0.544 inside the sealed"
        " [0.45, 0.55]) — but see the LEVEL red flag below.",
        f"- **Distribution LEVEL implausible — RED FLAG.** The fixture's"
        f" `yield_rate` (the register's Y, the terminal annual distribution rate)"
        f" is {terminal_dist_rate:.2%}/yr. Real mature buyout distributes roughly"
        " 20-30%/yr of NAV; the fixture's own flows snapshot (2.0/q on NAV 71.8,"
        " ~11%/yr at age 5.25) contradicts its own parameter by ~40x. The CODE is"
        " faithful to the register (`RD(t) = Y*(t/L)^B`, register s1 line-for-"
        " line); the fixture VALUE is mis-scaled against the register's Y"
        " definition. Consequence in this exhibit: distributions are starved,"
        " so spending forces liquid sales nearly every quarter.",
        f"- Cohorts never mature: unfunded ordering v2015 {cohorts['v2015'].unfunded:.1f}"
        f" < v2018 {cohorts['v2018'].unfunded:.1f} < v2021 {cohorts['v2021'].unfunded:.1f}"
        f" — {'age profile present' if i6_checks['age_profile'] else 'red flag'}."
        " Absolute pace is slow (34% uncalled at age 7 vs ~10% real-world):"
        " the rc_curve is the register's kind-C stand-in pending ALB-A; noted,"
        " not tuned.",
        f"- Forced sales never/constantly: {len(portfolio.forced_sales)} event(s)"
        f" in {n_q} quarters, kinds {forced_kinds} — 'constantly', which on this"
        " exhibit is the DOWNSTREAM of the distribution-level flag (spending is"
        " ~4.5%/yr of reported book while distributions run ~0.2%/yr; the gap"
        " must come from somewhere, and the engine honestly logs where). No"
        " forced secondaries trigger: liquid cover is ample (cov_liquid ~0.4)."
        " Re-inspect after the Y fix before treating cadence as a model finding.",
        "",
        "## Work items raised (recorded before G4 closes; the standing rule)",
        "",
        "1. **WI-I6-1 - fixture `yield_rate` mis-scaled** (register s1, parameter Y;",
        "   D7 row). Re-parameterize the fixture cohort's Y from industry aggregates",
        "   (the register's stated ALB-A fallback), reconcile the fixture's",
        "   performance/flows block to its own parameters, and SENSITIVITY-CHECK the",
        "   G1 drought ratio under corrected Y - as a robustness note on the sealed",
        "   result, not a reseal. Owner sign-off required (fixtures are contract",
        "   surface).",
        "2. **WI-I4-1 - SM-11 stickiness**: the state-dependent parameter is",
        "   measured zero and contributes nothing; 2022's mark lag does not fully",
        "   emerge from MA structure (G1 replay FAIL). Already queued for the next",
        "   generator campaign alongside the HY splice; recorded here so G4 cannot",
        "   close without the register knowing.",
        "3. **WI-I4-2 - PM kernel stand-in**: reported PM planes use hf_event theta",
        "   because Geltner is UNPARAMETERIZED (sealed PM unavailability). First PM",
        "   delivery parameterizes it by amendment before any RE/infra reported",
        "   path is generated - restated so the Step 4 artifact layer (which",
        "   renders reported marks) inherits the caveat.",
        "",
        "---",
        "",
        "*Not investment advice.*",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(_REPO_ROOT)} written")
    print(f"I4 checks: {i4_checks}")
    print(f"I6 checks: {i6_checks}; forced sales: {len(portfolio.forced_sales)}")


if __name__ == "__main__":
    main()
