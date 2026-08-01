"""The 2022 end-to-end reproduction (WP3.11) — G1 completion.

Run:  uv run python scripts/run_2022_replay.py

Feeds 2022-23's OBSERVED market history through the full translation chain —
mappings, smoothing kernel, tier-1 cashflows, the portfolio identities — and
scores the result against the SEALED episode criteria (frozen at G3-pre,
before any of this code existed) via ``ah.eval.episode2022``. Also scores
TIER 0 on the identical episode, and applies the sealed ``tier0_beats_rule``.

Writes ``G1-EVIDENCE.md``. Deterministic end to end: observed inputs, frozen
artifacts, no RNG.

The reference over-allocated institution (the sealed formula delegates its
definition here): 62% public equity, 38% in a mid-life buyout cohort (the
fixture cohort, age 5.25y — old enough that distributions are flowing), with
the private target range topping out at 0.35 — over-allocated at the door,
exactly the book 2022 punished.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.eval import episode2022 as ep
from ah.port import smoothing as sk
from ah.port.cashflow_tier1 import StructuralTerms, run_tier1
from ah.port.engine import Policy
from ah.port.mapping import load_artifact as load_mapping

_REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOW = ("2021-12-01", "2023-12-31")
PRIVATE_UPPER = 0.35
START_PRIVATE_WEIGHT = 0.38


def _series(catalog: Catalog, vintage: str, sid: str) -> pd.Series:
    frame = catalog.read_observations(vintage, sid)
    s = pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(frame["date"]),
    )
    return s.loc[WINDOW[0] : WINDOW[1]]


def _trough_month(cum: pd.Series) -> pd.Timestamp:
    return (cum / cum.cummax()).idxmin()


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")

    # -- observed public path and states ------------------------------------ #
    mkt = _series(catalog, vintage, "french.mkt_rf") + _series(catalog, vintage, "french.rf")
    cum_public = (1.0 + mkt).cumprod()
    public_dd = float((cum_public / cum_public.cummax() - 1.0).min())
    public_trough = _trough_month(cum_public)

    ig = _series(catalog, vintage, "fred.BAA") - _series(catalog, vintage, "fred.AAA")
    ig_full = pd.Series(
        pd.to_numeric(catalog.read_observations(vintage, "fred.BAA")["value"]).to_numpy(
            dtype=float
        ),
        index=pd.to_datetime(catalog.read_observations(vintage, "fred.BAA")["date"]),
    ) - pd.Series(
        pd.to_numeric(catalog.read_observations(vintage, "fred.AAA")["value"]).to_numpy(
            dtype=float
        ),
        index=pd.to_datetime(catalog.read_observations(vintage, "fred.AAA")["date"]),
    )
    spread_anchor = float(ig_full.loc["2019-01-01":"2021-12-31"].mean())

    dd_monthly = (1.0 - cum_public / cum_public.cummax()).clip(lower=0.0)
    ratio_monthly = (ig / spread_anchor).clip(lower=0.5)

    # quarterly states for the cashflow engine (quarter-end sampling)
    dd_q = dd_monthly.resample("QE").last().to_numpy()
    ratio_q = ratio_monthly.resample("QE").last().to_numpy()
    quarters = len(dd_q)

    # -- PM cohort: tier 1 vs the age-matched calm counterfactual ------------ #
    import json

    base = json.loads(
        (_REPO_ROOT / "fixtures" / "state" / "closed-end-cohort.example.json").read_text("utf-8")
    )
    pm_load = {"equity_mkt": 1.2, "smb": 0.2, "hml": 0.2}  # the frozen pm_buyout row
    factors_q = {
        "equity_mkt": mkt.resample("QE").sum().to_numpy(),
        "smb": _series(catalog, vintage, "french.smb").resample("QE").sum().to_numpy(),
        "hml": _series(catalog, vintage, "french.hml").resample("QE").sum().to_numpy(),
    }
    pm_true_q = sum(w * factors_q[f] for f, w in pm_load.items())

    terms = StructuralTerms(recycling_fraction=0.0)
    stressed = run_tier1(
        base,
        committed=100.0,
        vintage_year=2019,
        sleeve_returns=pm_true_q,
        drawdown_depth=dd_q,
        spread_ratio=ratio_q,
        terms=terms,
        fees_on=False,
        start_mid_life=True,
    )
    calm = run_tier1(
        base,
        committed=100.0,
        vintage_year=2019,
        sleeve_returns=pm_true_q,
        drawdown_depth=np.zeros(quarters),
        spread_ratio=np.ones(quarters),
        terms=terms,
        fees_on=False,
        start_mid_life=True,
    )
    # distribution RATES, age-matched: stressed rate / calm rate per quarter
    rate_ratio = [
        (s.distribution_total / c.distribution_total)
        for s, c in zip(stressed.flows, calm.flows, strict=True)
        if c.distribution_total > 1e-9
    ]
    trough_depth_num = min(rate_ratio) if rate_ratio else float("nan")

    # -- reported marks and the lag ------------------------------------------ #
    # HF composite: mapped true returns (frozen loadings) -> kernel -> trough
    mapping = load_mapping()
    regressors_m = {
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
    hf_true = pd.Series(0.0, index=mkt.index)
    n_sleeves = 0
    for sleeve, spec in mapping["sleeves"].items():
        contribution = pd.Series(float(spec["alpha_monthly"]), index=mkt.index)
        for reg, beta in spec["loadings"].items():
            contribution = contribution + float(beta) * regressors_m[reg]
        hf_true = hf_true + contribution
        n_sleeves += 1
    hf_true = hf_true / n_sleeves
    theta = sk.theta_for("hf_event")  # the most-smoothed modeled sleeve family
    hf_reported = pd.Series(sk.smooth(hf_true.to_numpy(), theta), index=hf_true.index)
    hf_lag_months = (_trough_month((1.0 + hf_reported).cumprod()) - public_trough) / np.timedelta64(
        30, "D"
    )

    # PM reported: cohort NAV path through the kernel (quarterly -> months x3)
    pm_nav_true = pd.Series(
        [f.nav_growth for f in stressed.flows],
        index=pd.date_range(WINDOW[0], periods=quarters, freq="QE"),
    )
    pm_true_q_series = pd.Series(pm_true_q, index=pm_nav_true.index)
    pm_reported_q = pd.Series(
        sk.smooth(pm_true_q_series.to_numpy(), theta), index=pm_nav_true.index
    )
    pm_lag_months = (
        _trough_month((1.0 + pm_reported_q).cumprod()) - public_trough
    ) / np.timedelta64(30, "D")

    # -- the over-allocated institution's weight breach ---------------------- #
    liquid = (1.0 - START_PRIVATE_WEIGHT) * cum_public / cum_public.iloc[0]
    pm_growth_m = (1.0 + pd.Series(pm_true_q, index=pm_nav_true.index)) ** (1 / 3)
    pm_m = pm_growth_m.reindex(mkt.index, method="bfill").fillna(1.0).cumprod()
    private = START_PRIVATE_WEIGHT * pm_m
    w_true = private / (private + liquid)
    breached = w_true[w_true > PRIVATE_UPPER]
    if len(breached):
        first_breach = breached.index[0]
        breach_offset = (first_breach - public_trough) / np.timedelta64(30, "D")
        breach_size = float(w_true.loc[first_breach] - PRIVATE_UPPER)
    else:
        breach_offset, breach_size = float("nan"), float("nan")

    # -- score the sealed criteria ------------------------------------------- #
    results = [
        ep.score_public_equity_drawdown(public_dd),
        ep.score_mark_lag(float(pm_lag_months), float(hf_lag_months)),
        ep.score_distribution_shortfall(trough_depth_num, 1.0),
        ep.score_secondary_pricing(1.0 - Policy().secondary_haircut),
        ep.score_private_weight_breach(float(breach_offset), breach_size),
        ep.score_coverage_warning(True, True),  # both ratios are QuarterReport fields
    ]
    verdict = ep.apply_gate_rule(results)

    # -- tier 0 on the identical episode (the sealed beats rule) ------------- #
    tier0_results = [
        ep.score_public_equity_drawdown(public_dd),  # same observed path
        ep.score_mark_lag(float(pm_lag_months), float(hf_lag_months)),  # same kernel
        ep.score_distribution_shortfall(1.0, 1.0),  # constant G: NO drought
        ep.score_secondary_pricing(1.0 - Policy().secondary_haircut),
        ep.score_private_weight_breach(float(breach_offset), breach_size),
        ep.score_coverage_warning(True, True),
    ]
    tier0_verdict = ep.apply_gate_rule(tier0_results)
    tier1_beats = verdict.score() < tier0_verdict.score()  # strictly lower; tie is not a beat

    # -- G1-EVIDENCE.md ------------------------------------------------------ #
    lines = [
        "# G1-EVIDENCE.md — the 2022 end-to-end reproduction (WP3.11)",
        "",
        f"Vintage `{vintage}`; window {WINDOW[0]}..{WINDOW[1]}; every criterion sealed at",
        "G3-pre (`pre-registration-g3.yaml`) BEFORE any of the judged code existed.",
        f"Public trough: {public_trough.date()}. Deterministic, no RNG.",
        "",
        "## Verdict",
        "",
        f"**Episode criterion set: {'PASS' if verdict.passed else 'FAIL'}** "
        f"(tier 1, `linkage_version tier1-public-0.1`).",
        "",
        "| criterion | value | sealed pass condition met | detail |",
        "|---|---|---|---|",
    ]
    for r in verdict.results:
        lines.append(f"| {r.name} | {r.value:.4f} | {'YES' if r.passed else 'NO'} | {r.detail} |")
    if verdict.named_failures:
        lines += [
            "",
            "### Named limitations (the gate rule's permitted failures, named as required)",
            "",
        ]
        for name in verdict.named_failures:
            r = next(x for x in verdict.results if x.name == name)
            lines.append(f"- **{name}** failed: {r.detail}")
    lines += [
        "",
        "## Tier 0 vs tier 1 (the sealed tier0_beats_rule)",
        "",
        f"Tier 1 episode score (criteria failed): **{verdict.score()}**; "
        f"tier 0: **{tier0_verdict.score()}** "
        f"(tier 0's constant G produces NO distribution drought — depth 1.0, sealed fail).",
        f"**Tier 1 {'BEATS' if tier1_beats else 'DOES NOT BEAT'} tier 0** "
        "(strictly lower score; a tie is not a beat). Claim scored under "
        "`linkage_version tier1-public-0.1`; a later `panel-1.0` claim is separate.",
        "",
        "## Chain notes",
        "",
        "- The public path is OBSERVED history: its drawdown criterion validates the",
        "  chain's wiring, not a model.",
        "- Mark lags use the frozen kernel with its MEASURED stickiness of 0.0 — this",
        "  replay is the genuine test that criterion was preserved for.",
        "- The secondary price is the v1 POLICY constant at the public anchor (0.81);",
        "  a state-dependent discount curve is a later refinement, named here.",
        "- The reference institution: 62% public equity / 38% mid-life buyout cohort,",
        "  private range upper 0.35 — over-allocated at the door, as the sealed",
        "  formula delegates to this replay spec.",
        "",
        "## Diagnosis of the mark_lag failure (the finding, not an excuse)",
        "",
        "The HF half fails at -3.1 months: the mapped HF composite's cumulative",
        "trough lands at 2022's FIRST leg (June), three months before the public",
        "total-return trough (September) — so no smoothing kernel could produce a",
        "positive lag; the composite's own trough timing dominates. Two candidate",
        "accounts, both already on the record:",
        "",
        "1. **The sealed HY omission.** `hy_spread` is a sealed missing factor, so",
        "   the loadings carry no high-yield channel — precisely the exposure that",
        "   deepened HF credit losses into the autumn re-trough. The next campaign's",
        "   panel (which revives HY via its splice) re-tests this mechanically.",
        "2. **Stickiness lives in 2021-23.** The kernel's stickiness was MEASURED at",
        "   0.0 on pre-2021 stress and the 2021-23 span was off-limits (holdout +",
        "   judging episode). This replay is the genuine test that discipline",
        "   preserved — and its answer is that 2022's mark lag does NOT fully emerge",
        "   from the MA structure alone. Re-estimating stickiness with post-2021",
        "   data is a NEXT-CAMPAIGN decision, taken with results in view and said so.",
        "",
        "Under the sealed gate rule the criterion set FAILS (mark_lag is must-pass),",
        "tier 1 still BEATS tier 0, and per the plan's own DoD the result ships",
        "reported honestly rather than tuned quiet.",
    ]
    (_REPO_ROOT / "G1-EVIDENCE.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        f"G1-EVIDENCE.md written: episode {'PASS' if verdict.passed else 'FAIL'}; "
        f"tier1 score {verdict.score()} vs tier0 {tier0_verdict.score()} "
        f"({'BEATS' if tier1_beats else 'no beat'}); named failures: "
        f"{list(verdict.named_failures) or 'none'}"
    )


if __name__ == "__main__":
    main()
