"""Freeze tier 1's market linkage (WP3.4) — linkage_version public-0.1.

Run:  uv run python scripts/freeze_tier1_linkage.py

The market-sensitive extension's parameters, calibrated on the PUBLIC route
(Amendment A1 Delta 1: the Albourne panel is a later institutional
recalibration, panel-1.0) and frozen before any episode replay exists.

**f_dist** — the load-bearing function (liquidity-spine §4.1). Form:
``f_dist = clip(exp(-a·dd - b·ln(spread_ratio)), floor, ceiling)`` over two
CONTINUOUS market states: equity drawdown depth ``dd`` and the IG spread level
ratio to its trailing anchor. Substitutions from the P-A original (log P/D ->
drawdown depth as the valuation proxy; HY -> IG spread, HY being a sealed
missing factor) are DOCUMENTED, and the coefficients are re-solved so that the
P-A public target holds: at the MEASURED 2022 state (dd and spread ratio read
from the store, train-val-adjacent episode anchors), ``f_dist = 0.50`` — the
center of P-A's drought depth 0.45-0.55 — with the two coefficients sharing
influence in P-A's own elasticity ratio (0.37 : 0.30). Reproducing the trough
is P-A's stated ACCEPTANCE TEST; the sealed episode criterion judges the full
replay chain, not this point function.

**f_call** — near-flat (Delta 3's binding finding: the self-funding breakdown
is a distribution-side phenomenon; buyout calls barely move in stress).
``f_call = 1 - c·dd`` with a small frozen c.

**NO CRISIS/REGIME TERM** (Delta 3): both functions consume continuous market
states only — no regime label, no recession dummy, structurally. The full
adds-nothing regression test becomes meaningful at the WP3.11 replay and is
recorded there.

**PM growth loadings**: no PM return series exists (sealed unavailability), so
the DN-5 §3.3 tabled priors are adopted AS CHOSEN (kind C) loadings, stated
with sensitivity flags — never presented as estimates. λ_G = 0: the smoothing
kernel owns the lag (the register's must-not-double-count rule).

Output: ``mappings/cashflow-tier1-v1.0.yaml``. Deterministic, no RNG.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog

_REPO_ROOT = Path(__file__).resolve().parents[1]
TIER1_VERSION = "tier1-public-0.1"

P_A_TARGET = 0.50  # center of the P-A drought depth 0.45-0.55
ELASTICITY_RATIO = 0.37 / 0.30  # P-A's own log-P/D : log-spread influence ratio
F_DIST_FLOOR = 0.30
F_DIST_CEILING = 1.50
F_CALL_SLOPE = 0.10  # near-flat (Delta 3); venture-style uplift is a later, named knob

#: DN-5 §3.3 tabled priors adopted as CHOSEN loadings (kind C) — no PM data
#: exists to estimate against. Regressor order matches the mapping artifact.
PM_GROWTH_LOADINGS: dict[str, dict[str, float]] = {
    "pm_buyout": {"equity_mkt": 1.2, "smb": 0.2, "hml": 0.2, "d_ig": -0.05},
    "pm_growth": {"equity_mkt": 1.3, "hml": -0.2},
    "pm_vc": {"equity_mkt": 1.2, "hml": -0.3},
    "pm_secondaries": {"equity_mkt": 1.1, "d_ig": -0.05},
    "pm_direct_lending": {"d_ig": -0.35},
    "pm_mezzanine": {"equity_mkt": 0.3, "d_ig": -0.20},
    "pm_distressed": {"equity_mkt": 0.35, "d_ig": -0.25},
    "pm_re_value_add": {"equity_mkt": 0.5},
    "pm_infra": {"equity_mkt": 0.3},
}


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")

    # The 2022 state, MEASURED (episode-anchor months; deterministic reads).
    def series(sid: str) -> pd.Series:
        frame = catalog.read_observations(vintage, sid)
        return pd.Series(
            pd.to_numeric(frame["value"]).to_numpy(dtype=float),
            index=pd.to_datetime(frame["date"]),
        )

    mkt = series("french.mkt_rf") + series("french.rf")
    cum = (1.0 + mkt.loc["2021-12-01":"2022-12-31"]).cumprod()
    dd_2022 = float(1.0 - cum.min() / cum.cummax().max())  # trough depth, positive

    ig = series("fred.BAA") - series("fred.AAA")  # the ig_spread identity's inputs
    anchor = float(ig.loc["2019-01-01":"2021-12-31"].mean())
    peak_2022 = float(ig.loc["2022-01-01":"2022-12-31"].max())
    spread_ratio_2022 = peak_2022 / anchor

    # Solve a, b sharing influence in the P-A elasticity ratio:
    #   a*dd + b*ln(ratio) = -ln(target);  a*dd / (b*ln(ratio)) = 0.37/0.30
    total = -np.log(P_A_TARGET)
    b = total / (ELASTICITY_RATIO + 1.0) / np.log(spread_ratio_2022)
    a = total * ELASTICITY_RATIO / (ELASTICITY_RATIO + 1.0) / dd_2022

    lines = [
        "# mappings/cashflow-tier1-v1.0.yaml — scripts/freeze_tier1_linkage.py",
        f"# vintage {vintage}. Frozen BEFORE any episode replay exists.",
        f"linkage_version: {TIER1_VERSION}",
        f'campaign_vintage_id: "{vintage}"',
        "f_dist:",
        "  form: clip(exp(-a*dd - b*ln(spread_ratio)), floor, ceiling)",
        f"  a_drawdown: {a:.6f}",
        f"  b_log_spread: {b:.6f}",
        f"  floor: {F_DIST_FLOOR}",
        f"  ceiling: {F_DIST_CEILING}",
        f"  calibration: {{target: {P_A_TARGET}, dd_2022_measured: {dd_2022:.4f}, "
        f"spread_ratio_2022_measured: {spread_ratio_2022:.4f}, "
        f"elasticity_ratio: '0.37:0.30 (P-A verbatim)'}}",
        "  substitutions: >-",
        "    log P/D -> equity drawdown depth (valuation proxy); HY spread -> IG",
        "    (Baa-Aaa) spread ratio, HY being a sealed missing factor. Coefficients",
        "    re-solved so the P-A public target (drought depth 0.50 at the measured",
        "    2022 state) holds under the substituted drivers.",
        "f_call:",
        "  form: clip(1 - c*dd, 0.5, 1.2)",
        f"  c: {F_CALL_SLOPE}",
        "  source: Delta 3 / linkage-estimation s4 - near-flat for buyout in stress;",
        "    the self-funding breakdown is distribution-side. Venture-style call",
        "    ACCELERATION is a later, named knob, not silently folded in.",
        "no_crisis_term: >-",
        "  STRUCTURAL (Delta 3): both functions consume continuous market states",
        "  only - no regime label, no recession dummy, by signature. The",
        "  adds-nothing regression test runs at the WP3.11 replay.",
        "lambda_g: 0  # the smoothing kernel owns the lag; never double-counted",
        "pm_growth_loadings:  # DN-5 s3.3 priors ADOPTED AS CHOSEN (kind C) - no PM",
        "                     # data exists; sensitivity-flagged, never called estimates",
    ]
    for sleeve, loadings in PM_GROWTH_LOADINGS.items():
        inner = ", ".join(f"{k}: {v}" for k, v in loadings.items())
        lines.append(f"  {sleeve}: {{{inner}}}")

    out = _REPO_ROOT / "mappings" / "cashflow-tier1-v1.0.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {out.name}: a={a:.3f}, b={b:.3f} "
        f"(dd_2022={dd_2022:.3f}, spread_ratio={spread_ratio_2022:.3f})"
    )


if __name__ == "__main__":
    main()
