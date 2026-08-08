"""Campaign R1 Track A — the twin over observed factor history (exhibit).

Outside both pre-registration locks by design: this module audits how the
translation layer behaves under the AM-2026-08-08-002 artifacts; nothing here
is judged, and nothing judged imports it. See
docs/superpowers/specs/2026-08-08-campaign-r1-design.md.

The prior/measured asymmetry is deliberate and IS the experiment:
``source="prior"`` reproduces the frozen pm_growth_loadings convention
(beta * factor, no alpha — the G1-replay convention), ``source="measured"``
uses the fitted row with its alpha. Their difference is exactly the change
adopting the measured loadings would make.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

CAMPAIGN_VINTAGE = "2026-08-07.5"

#: window -> (start, end). y2022 matches run_2022_replay.py's WINDOW.
WINDOWS: dict[str, tuple[str, str]] = {
    "full_span": ("1990-01-01", "2026-06-30"),
    "gfc": ("2007-07-01", "2009-12-31"),
    "covid": ("2020-01-01", "2020-12-31"),
    "y2022": ("2021-12-01", "2023-12-31"),
}

#: mapping regressor -> the observed series that realize it (I4/I6 wiring).
#: french.mkt_rf stays first: the missing-series error names its regressor.
_REGRESSOR_SOURCES: dict[str, tuple[str, ...]] = {
    "equity_mkt": ("french.mkt_rf", "french.rf"),
    "smb": ("french.smb",),
    "hml": ("french.hml",),
    "mom": ("french.mom",),
    "d_level": ("fred.DGS10",),
    "d_slope": ("fred.DGS10", "fred.DGS2"),
    "d_ig": ("fred.BAA", "fred.AAA"),
}


def _series(catalog: Any, vintage: str, sid: str) -> pd.Series:
    try:
        frame = catalog.read_observations(vintage, sid)
    except Exception as exc:  # an exhibit hard-fails; it never backfills silence
        needed_for = [k for k, v in _REGRESSOR_SOURCES.items() if sid in v]
        raise SystemExit(
            f"campaign R1: series '{sid}' unreadable on vintage {vintage} "
            f"(needed for regressor(s) {needed_for}): {exc}"
        ) from exc
    return pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float),
        index=pd.to_datetime(frame["date"]),
    )


def load_regressors(catalog: Any, vintage: str) -> pd.DataFrame:
    """Monthly regressor frame on the campaign vintage, common span, no NaNs."""
    s: dict[str, pd.Series] = {}
    for sources in _REGRESSOR_SOURCES.values():
        for sid in sources:
            if sid not in s:
                s[sid] = _series(catalog, vintage, sid)
    cols = {
        "equity_mkt": s["french.mkt_rf"] + s["french.rf"],
        "smb": s["french.smb"],
        "hml": s["french.hml"],
        "mom": s["french.mom"],
        "d_level": s["fred.DGS10"].diff(),
        "d_slope": (s["fred.DGS10"] - s["fred.DGS2"]).diff(),
        "d_ig": (s["fred.BAA"] - s["fred.AAA"]).diff(),
    }
    frame = pd.DataFrame(cols).dropna()
    if frame.empty:
        raise SystemExit(f"campaign R1: empty regressor frame on vintage {vintage}")
    return frame


def hf_sleeve_returns(reg: pd.DataFrame, mapping: dict) -> dict[str, pd.Series]:
    """Monthly HF sleeve returns from the mapping's ``sleeves:`` block."""
    out: dict[str, pd.Series] = {}
    for sleeve, spec in mapping["sleeves"].items():
        r = pd.Series(float(spec["alpha_monthly"]), index=reg.index)
        for name, beta in spec["loadings"].items():
            if float(beta) != 0.0:
                r = r + float(beta) * reg[name]
        out[sleeve] = r
    return out


def pm_sleeve_returns(reg_q: pd.DataFrame, mapping: dict, *, source: str) -> dict[str, pd.Series]:
    """Quarterly PM sleeve returns under the prior or the measured loadings.

    ``source="prior"`` reproduces the frozen pm_growth_loadings convention
    (beta * factor, no alpha); ``"measured"`` uses the fitted row with its
    alpha. The asymmetry is the experiment — see the module docstring.
    """
    if source not in ("prior", "measured"):
        raise ValueError(f"source must be 'prior' or 'measured', got {source!r}")
    out: dict[str, pd.Series] = {}
    for sleeve, spec in mapping["pm_sleeves"].items():
        if source == "prior":
            r = pd.Series(0.0, index=reg_q.index)
            for name, beta in spec["prior_superseded"].items():
                if name != "source" and float(beta) != 0.0:
                    r = r + float(beta) * reg_q[name]
        else:
            r = pd.Series(float(spec["alpha_quarterly"]), index=reg_q.index)
            for name, beta in spec["loadings"].items():
                if float(beta) != 0.0:
                    r = r + float(beta) * reg_q[name]
        out[sleeve] = r
    return out


def geltner_report(true: np.ndarray, *, a: float, phi: float) -> np.ndarray:
    """Forward AR(1) partial adjustment: reported[t] = phi*reported[t-1] + a*true[t]."""
    x = np.asarray(true, dtype=float)
    rep = np.empty_like(x)
    prev = 0.0
    for t, value in enumerate(x):
        prev = phi * prev + a * float(value)
        rep[t] = prev
    return rep


def reported_plane(sleeve_id: str, true: pd.Series) -> pd.Series:
    """The sleeve's reported returns under its OWN smoothing family.

    Family resolution is read-only through the sealed taxonomy
    (``ah.eval.sleevetails.smoothing_family``) so the exhibit cannot drift
    from the judged classification; HF sleeves are always GLM.
    """
    from ah.eval.sleevetails import smoothing_family
    from ah.port import smoothing as sk

    family = "glm" if sleeve_id.startswith("hf_") else smoothing_family(sleeve_id)
    values = true.to_numpy(dtype=float)
    if family == "geltner":
        a, phi = sk.geltner_for(sleeve_id)
        reported = geltner_report(values, a=a, phi=phi)
    else:
        reported = sk.smooth(values, sk.theta_for(sleeve_id))
    return pd.Series(reported, index=true.index)
