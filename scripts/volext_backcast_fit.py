"""The REGISTERED fit of the equity_vol backcast (WP-DATA-VOLEXT stage 2).

Operational, not a test (network + FRED_API_KEY). Refuses to run unless the
acceptance thresholds are already ratified in ``governance/amendment-log.yaml``
and match ``ah.data.vol_backcast.REGISTERED_THRESHOLDS`` exactly -- the
RFR-77 discipline (grade fixed before the fit), enforced mechanically rather
than by good intentions.

What it does, in order: fetch the French daily market factor (Mkt-RF + RF)
and the FRED implied-vol indices through the registered connectors; build the
monthly realized-vol features; run the REGISTERED fit on the 1990+ overlap;
run the full validation battery (OOS 2008+, stress decile, peaks, vol-of-vol,
coverage, walk-forward) and the 1986-89 VXO true-held-out check (VXO mapped
to VIX-equivalents through the STAGE-1 log-log fit); backcast below 1986 as
an ensemble; write the provenance JSON to ``artifacts/volext/`` (committed)
and the human report to ``docs/data/VOLEXT-STAGE2.md``. The vintage store is
untouched throughout -- nothing consumes the backcast until the owner
ratifies the separate span amendment, and a failing fit ships nothing but its
own failure report.

Run:  uv run python scripts/volext_backcast_fit.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROVENANCE = ROOT / "artifacts" / "volext" / "equity-vol-backcast-provenance.json"
REPORT = ROOT / "docs" / "data" / "VOLEXT-STAGE2.md"


def _load_env() -> None:
    if os.environ.get("FRED_API_KEY"):
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("FRED_API_KEY=") and "=" in line:
                os.environ["FRED_API_KEY"] = line.split("=", 1)[1].strip()


def _ratified_amendment_id() -> str:
    """The mechanical RFR-77 gate: no ratified thresholds, no registered fit."""
    from ah.data.vol_backcast import REGISTERED_OBJECT, REGISTERED_THRESHOLDS
    from ah.eval.prereg import load_amendments

    for am in load_amendments(ROOT / "governance" / "amendment-log.yaml"):
        payload = dict(am.payload or {})
        if payload.get("registered_object") != REGISTERED_OBJECT:
            continue
        got = {k: float(v) for k, v in dict(payload.get("thresholds", {})).items()}
        if got != REGISTERED_THRESHOLDS:
            raise SystemExit(
                f"amendment {am.amendment_id} registers {REGISTERED_OBJECT} but its "
                f"thresholds differ from REGISTERED_THRESHOLDS -- refusing:\n"
                f"  log:    {got}\n  module: {REGISTERED_THRESHOLDS}"
            )
        return am.amendment_id
    raise SystemExit(
        "no ratified thresholds for the backcast in governance/amendment-log.yaml -- "
        "the registered fit does not run before its grade is fixed (RFR-77). "
        "See governance/proposed/PROPOSED-AM-volext-thresholds.md."
    )


def main() -> int:
    _load_env()
    if not os.environ.get("FRED_API_KEY"):
        print("FRED_API_KEY not set (checked env and .env)")
        return 1
    amendment_id = _ratified_amendment_id()
    print(f"thresholds ratified: {amendment_id}")

    import pandas as pd

    from ah.data import vol_backcast as vb
    from ah.data import vol_extend as vx
    from ah.data.connectors.fred import FredConnector
    from ah.data.connectors.french import FrenchConnector
    from ah.data.manifest import load_requirements

    reqs = load_requirements()
    fred, french = FredConnector(), FrenchConnector()

    def _fetch(conn, sid: str) -> pd.DataFrame:
        req = reqs[sid]
        frame = conn.parse(conn.fetch(req), req)
        print(
            f"{sid}: {len(frame)} obs, {frame['date'].min().date()}..{frame['date'].max().date()}"
        )
        return frame

    mkt_rf = _fetch(french, "french.mkt_rf_d").set_index("date")["value"]
    rf = _fetch(french, "french.rf_d").set_index("date")["value"]
    vix_frame = _fetch(fred, "fred.VIX")
    vxo_frame = _fetch(fred, "fred.VXO")

    # total market return, cumulated to a synthetic close level
    total = (mkt_rf + rf.reindex(mkt_rf.index).fillna(0.0)).dropna()
    features = vb.realized_features(vb.close_from_returns(total))
    print(
        f"features: {len(features)} months, {features.index.min().date()}..{features.index.max().date()}"
    )

    def _month_end(frame: pd.DataFrame) -> pd.Series:
        s = frame.set_index("date")["value"].astype(float).dropna()
        s.index = s.index + pd.offsets.MonthEnd(0)
        return s

    vix = _month_end(vix_frame)
    vxo = _month_end(vxo_frame)

    # the registered fit, on the full 1990+ overlap
    f = vb.fit(features, vix)
    print(f"fit: n={f.n_obs} r2={f.r2:.3f} coef={[round(c, 3) for c in f.coef]}")

    validation = vb.validate(features, vix)
    # the 1986-89 held-out era: VXO mapped through the STAGE-1 log-log fit
    stage1 = vx.fit_loglog(vix_frame, vxo_frame)
    pre90 = vxo.loc[vxo.index < pd.Timestamp("1990-01-01")]
    equiv = pd.Series(stage1.predict_level(pre90.to_numpy()), index=pre90.index)
    heldout = vb.vxo_heldout(f, features, equiv)

    # the backcast fills below the stage-1 extension (observed+VXO reach 1986-01)
    ext = vx.extend_equity_vol(vix_frame, vxo_frame)
    observed = ext.frame.set_index("date")["value"].astype(float)
    observed.index = observed.index + pd.offsets.MonthEnd(0)
    frame, _ensemble = vb.backcast(f, features, observed, n_draws=200, seed=0)
    # every proxy row in `frame` is a model month: the VXO-spliced 1986-89
    # months entered through `observed` and are never re-flagged here
    n_bc = int(frame["is_proxy"].sum())

    fitted_at = datetime.now(UTC).isoformat(timespec="seconds")
    vb.write_provenance(
        f, validation, heldout, PROVENANCE, fitted_at=fitted_at, amendment_id=amendment_id
    )
    print(f"wrote {PROVENANCE}")

    ok = validation.ok and heldout.ok
    verdict = "PASS — all registered thresholds met" if ok else "FAIL — the backcast does not ship"
    v, h = validation, heldout

    def _peak(label: str) -> str:
        p = v.peak_errors.get(label)
        if p is None:
            return "window absent"
        return f"predicted {p['predicted_peak']:.1f} vs actual {p['actual_peak']:.1f} (ratio {p['ratio']:.2f})"

    thr = vb.REGISTERED_THRESHOLDS
    lines = [
        "# VOLEXT Stage 2 — the registered backcast fit and its verdict",
        "",
        f"*Generated by `scripts/volext_backcast_fit.py` at {fitted_at}. Thresholds",
        f"ratified as `{amendment_id}` BEFORE this fit ran; the script refuses to run",
        "without that entry. Provenance (coefficients, HAC covariance, residual pool,",
        f"full validation): `artifacts/volext/{PROVENANCE.name}`. Ensemble paths",
        "regenerate bit-identically from that artifact via `ah.data.vol_backcast.paths`",
        "(owner decision D2); the median is diagnostic/display only.*",
        "",
        f"## Verdict: {verdict}",
        "",
        "| registered check | threshold | measured | pass |",
        "|---|---|---|---|",
        f"| VXO 1986-89 held-out corr (log) | >= {thr['vxo_heldout_corr_log_min']} | {h.corr_log:.4f} | {h.passes['vxo_heldout_corr']} |",
        f"| Oct-1987 predicted/actual | [{thr['oct1987_peak_ratio_min']}, {thr['oct1987_peak_ratio_max']}] | {h.oct1987_ratio:.3f} ({h.oct1987_predicted:.1f} vs {h.oct1987_actual_vix_equiv:.1f}) | {h.passes['oct1987_peak']} |",
        f"| top-RV-decile OOS bias (log, abs) | <= {thr['stress_bias_log_abs_max']} | {v.stress_bias_log:+.4f} | {v.passes['stress_bias']} |",
        f"| ensemble vol-of-vol ratio | >= {thr['ensemble_vol_of_vol_ratio_min']} | {v.vol_of_vol_ratio_ensemble:.3f} | {v.passes['ensemble_vol_of_vol']} |",
        f"| 80% interval coverage | 0.80 +/- {thr['coverage_80_tolerance']} | {v.coverage_80:.3f} | {v.passes['interval_coverage']} |",
        "",
        "## The fit (1990+ overlap)",
        "",
        f"- n = {f.n_obs} months ({f.overlap[0]} .. {f.overlap[1]}), R^2 = {f.r2:.3f},",
        f"  residual sigma = {f.resid_sigma:.4f} log.",
        "- Coefficients (HAC t-stats, Newey-West Bartlett 12 lags): "
        + ", ".join(
            f"{n} {c:+.3f} (t={t:.1f})"
            for n, c, t in zip(("const", *vb.FEATURES), f.coef, f.tstat_hac, strict=True)
        ),
        "- The reference sketch's `downside` term is absent by specification "
        "(t = -1.28 on its real fit; unsupported regressors do not enter a "
        "registered spec).",
        "",
        "## Out-of-sample (fit <= 2007, test 2008+: the GFC and COVID)",
        "",
        f"- RMSE {v.oos_rmse_log:.4f} log, overall bias {v.oos_bias_log:+.4f},",
        f"  calm-half bias {v.calm_bias_log:+.4f}, stress-decile bias {v.stress_bias_log:+.4f},",
        f"  stress level ratio {v.stress_ratio:.3f}.",
        f"- GFC peak: {_peak('gfc_2008_09_to_2009_03')}.",
        f"- COVID peak: {_peak('covid_2020')}.",
        f"- Vol-of-vol: conditional mean retains {v.vol_of_vol_ratio_mean:.3f} of the",
        f"  truth, the ensemble {v.vol_of_vol_ratio_ensemble:.3f} — the reason the",
        "  ensemble, never the median, feeds any tail metric.",
        f"- Expanding-window walk-forward RMSE {v.walkforward_rmse_log:.4f} log.",
        "",
        "## The backcast",
        "",
        f"- {n_bc} model months below the stage-1 extension "
        f"({frame['date'].min().date()} .. 1985-12), ensemble n_draws=200, seed 0,",
        "  12-month residual blocks; every row `is_proxy=True`, rule "
        f"`{vb.RULE_ID}`; no observed or VXO-spliced month touched.",
        "",
        "## Standing caveats",
        "",
        "- Backcast months are MODEL OUTPUT. Behaviour in pre-1986 tails is",
        "  extrapolation, not evidence; the 1986-89 held-out check is the closest",
        "  audit that exists and it is 48 months long.",
        "- Nothing consumes this series. Admitting it to anything is a separate",
        "  amendment with its own evidence bar, and",
        "  `governance/proposed/PROPOSED-AM-block-draw-span-1986.md` argues AGAINST",
        "  admitting model months to the benchmark span at all.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}")
    print(f"verdict: {verdict}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
