"""Campaign-3 seal package: derive every band-recipe threshold value from the
campaign-3 reference run, for the AM-2026-08-10-001 seal event.

Run:  uv run python scripts/campaign3_seal_package.py

Prints, for every per-name threshold entry in pre-registration.yaml's
``thresholds.blocks`` / ``thresholds.cross_blocks`` (existing names updated in
place, plus the commodities family added by ruling K2), the campaign-3 band,
historical point, and the ``mid -+ 4 * half_width`` bounds after the sealed
structural clips -- the same recipe, verbatim, as campaign-2's
``campaign2_seal_package.py``. Also prints the D4 strategy bands
([historical/3, historical*3] on var_95/es_95) from the campaign-3
seal-evidence artifact, and the memorization floors.

Inputs: artifacts/campaign3/reference-run.json and
artifacts/campaign3/seal-evidence.json. Deterministic; no randomness; no
network. This script is the provenance record for the numbers pasted into the
sealed file at the campaign-3 event.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
REF_PATH = _REPO_ROOT / "artifacts" / "campaign3" / "reference-run.json"
EVID_PATH = _REPO_ROOT / "artifacts" / "campaign3" / "seal-evidence.json"

#: (block, name, structural_lo, structural_hi) for every sealed per-name entry,
#: including the commodities family (K2): the return-factor convention, i.e.
#: exactly equity_mkt's five names. Clip ranges are the sealed comments' own:
#: skew unbounded; excess_kurtosis min -2; acf_abs_sum structural range
#: [-5, 10] never binds in practice (sealed entries quote both sides); a
#: correlation lives in [-1, 1]; a Hill index is strictly positive;
#: acf_r_lag1 in [-1, 1]; acf_r_sum (sum of five autocorrelations) in [-5, 5].
_BLOCK_ENTRIES = (
    ("global", "equity_mkt.skew", None, None),
    ("global", "equity_mkt.excess_kurtosis", -2.0, None),
    ("global", "equity_mkt.acf_abs_sum", None, None),
    ("global", "equity_mkt.leverage_correlation", -1.0, 1.0),
    ("global", "equity_mkt.hill_tail_index_5pct", 0.0, None),
    ("global", "commodities.skew", None, None),
    ("global", "commodities.excess_kurtosis", -2.0, None),
    ("global", "commodities.acf_abs_sum", None, None),
    ("global", "commodities.leverage_correlation", -1.0, 1.0),
    ("global", "commodities.hill_tail_index_5pct", 0.0, None),
    ("us", "policy_rate.excess_kurtosis", -2.0, None),
    ("us", "ust_10y.acf_r_lag1", -1.0, 1.0),
    ("us", "ust_10y.acf_r_sum", -5.0, 5.0),
    ("us", "ust_10y.excess_kurtosis", -2.0, None),
    ("us", "cpi.excess_kurtosis", -2.0, None),
    ("fx", "fx_usd.acf_r_lag1", -1.0, 1.0),
    ("fx", "fx_usd.acf_r_sum", -5.0, 5.0),
    ("fx", "fx_usd.excess_kurtosis", -2.0, None),
    ("valuation", "cape_v.acf_r_lag1", -1.0, 1.0),
    ("valuation", "cape_v.acf_r_sum", -5.0, 5.0),
    ("valuation", "cape_v.excess_kurtosis", -2.0, None),
)

_CROSS_ENTRIES = (
    ("global|us", "equity_mkt~ust_10y.crisis_corr_lift"),
    ("fx|global", "fx_usd~equity_mkt.crisis_corr_lift"),
    ("fx|us", "fx_usd~ust_10y.crisis_corr_lift"),
    ("fx|valuation", "fx_usd~cape_v.crisis_corr_lift"),
    ("global|valuation", "equity_mkt~cape_v.crisis_corr_lift"),
    ("us|valuation", "ust_10y~cape_v.crisis_corr_lift"),
)
_CROSS_RANGE = (-2.0, 2.0)  # crisis_corr_lift: a difference of two correlations


def _bounds(lo: float, hi: float, s_lo, s_hi):
    mid = 0.5 * (lo + hi)
    half = 0.5 * (hi - lo)
    t_min: float | None = round(mid - 4.0 * half, 4)
    t_max: float | None = round(mid + 4.0 * half, 4)
    raw = (t_min, t_max)
    if s_lo is not None and t_min is not None and t_min <= s_lo:
        t_min = None
    if s_hi is not None and t_max is not None and t_max >= s_hi:
        t_max = None
    return t_min, t_max, raw


def main() -> None:
    ref = json.loads(REF_PATH.read_text("utf-8"))
    assert ref["vintage_id"] == "2026-08-10.1", ref["vintage_id"]
    assert ref["seed"] == 20260726
    assert ref["missing_factors"] == []
    assert ref["missing_no_data"] == []

    print("== thresholds.blocks ==")
    for block, name, s_lo, s_hi in _BLOCK_ENTRIES:
        band = ref["blocks"][block][name]
        t_min, t_max, raw = _bounds(band["lo"], band["hi"], s_lo, s_hi)
        mn = "null" if t_min is None else t_min
        mx = "null" if t_max is None else t_max
        clip = []
        if t_min is None:
            clip.append(f"min raw {raw[0]} clipped (structural {s_lo})")
        if t_max is None:
            clip.append(f"max raw {raw[1]} clipped (structural {s_hi})")
        print(
            f"{block}.{name}: band [{band['lo']:.6f}, {band['hi']:.6f}] point {band['point']:.6f}"
        )
        print(
            f'  "{name}": {{min: {mn}, max: {mx}, severity: report}}'
            + (f"   # {'; '.join(clip)}" if clip else "")
        )

    print("\n== thresholds.cross_blocks ==")
    for pair, name in _CROSS_ENTRIES:
        band = ref["cross_blocks"][pair][name]
        t_min, t_max, raw = _bounds(band["lo"], band["hi"], *_CROSS_RANGE)
        mn = "null" if t_min is None else t_min
        mx = "null" if t_max is None else t_max
        print(
            f"{pair}.{name}: band [{band['lo']:.6f}, {band['hi']:.6f}] "
            f"point {band['point']:.6f} raw [{raw[0]}, {raw[1]}]"
        )
        print(f'  "{name}": {{min: {mn}, max: {mx}, severity: report}}')

    print("\n== coverage (verbatim) ==")
    for f, c in sorted(ref["coverage"].items(), key=lambda kv: kv[1]["first_date"]):
        print(
            f'    {f}: {{first: "{c["first_date"]}", last: "{c["last_date"]}", '
            f"n_obs: {c['n_obs']}}}"
        )

    if EVID_PATH.exists():
        evid = json.loads(EVID_PATH.read_text("utf-8"))
        print("\n== seal evidence ==")
        print(json.dumps(evid, indent=2, sort_keys=True))
    else:
        print("\n(seal-evidence.json not yet written)")


if __name__ == "__main__":
    main()
