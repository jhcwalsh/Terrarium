"""Campaign-2 seal package: derive new-block thresholds, verify RFR-61 band
identity, append the three amendments, and patch pre-registration.yaml.

Run:  uv run python scripts/campaign2_seal_package.py            # dry run: derive + report
      uv run python scripts/campaign2_seal_package.py --apply    # append amendments + patch YAML

Inputs: artifacts/campaign2/reference-run.json (the campaign-2 reference run on
vintage 2026-08-02.4 at the sealed seed 20260726). The threshold recipe is the
sealed one, verbatim from thresholds.blocks' header: ``band_midpoint -+ 4 *
band_half_width``, a side sealed ``null`` wherever 4 half-widths leaves the
statistic's structural range, severity report. Owner ratifications on the
record: "C3 - accept and document, proceed with the campaign seal"; "include
CAPE in this seal"; pinned-constants HY decision; "proceed with the amendments
and re-mint when the bands land".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.eval.prereg import Amendment, append_amendment, load  # noqa: E402
from ah.factors import load_manifest  # noqa: E402

REF_PATH = _REPO_ROOT / "artifacts" / "campaign2" / "reference-run.json"
LOG_PATH = _REPO_ROOT / "governance" / "amendment-log.yaml"
PREREG_PATH = _REPO_ROOT / "pre-registration.yaml"
DATE = "2026-08-02"

#: (stat, structural_lo, structural_hi) -- the clip ranges the sealed comments use.
_BLOCK_STATS = (
    ("acf_r_lag1", -1.0, 1.0),
    ("acf_r_sum", -5.0, 5.0),
    ("excess_kurtosis", -2.0, None),
)
_CROSS_RANGE = (-2.0, 2.0)  # crisis_corr_lift: a difference of two correlations

#: One representative crisis_corr_lift per new pair, mirroring the sealed
#: global|us convention (equity_mkt~ust_10y). Chosen PRE-HOC, macro-rationale in
#: the amendment rationale; key order follows verify()'s rule (factorA from the
#: pair's first block, factorB from its second, blocks sorted).
_CROSS_PAIRS = {
    ("fx", "global"): "fx_usd~equity_mkt",
    ("fx", "us"): "fx_usd~ust_10y",
    ("fx", "valuation"): "fx_usd~cape_v",
    ("global", "valuation"): "equity_mkt~cape_v",
    ("us", "valuation"): "ust_10y~cape_v",
}


def _threshold(lo: float, hi: float, structural_lo, structural_hi) -> dict:
    mid = 0.5 * (lo + hi)
    half = 0.5 * (hi - lo)
    t_min: float | None = round(mid - 4.0 * half, 4)
    t_max: float | None = round(mid + 4.0 * half, 4)
    if structural_lo is not None and t_min <= structural_lo:
        t_min = None
    if structural_hi is not None and t_max >= structural_hi:
        t_max = None
    return {"min": t_min, "max": t_max, "severity": "report", "_band": (lo, hi)}


def derive_thresholds(ref: dict) -> tuple[dict, dict]:
    block_thresholds: dict[str, dict[str, dict]] = {}
    for block, factor in (("fx", "fx_usd"), ("valuation", "cape_v")):
        entries = {}
        for stat, s_lo, s_hi in _BLOCK_STATS:
            band = ref["blocks"][block][f"{factor}.{stat}"]
            entries[f"{factor}.{stat}"] = _threshold(band["lo"], band["hi"], s_lo, s_hi)
        block_thresholds[block] = entries

    cross_thresholds: dict[str, dict[str, dict]] = {}
    for pair, factor_key in _CROSS_PAIRS.items():
        pair_key = "|".join(pair)
        band = ref["cross_blocks"][pair_key][f"{factor_key}.crisis_corr_lift"]
        cross_thresholds[pair_key] = {
            f"{factor_key}.crisis_corr_lift": _threshold(
                band["lo"], band["hi"], _CROSS_RANGE[0], _CROSS_RANGE[1]
            )
        }
    return block_thresholds, cross_thresholds


def _strip(entries: dict) -> dict:
    """Amendment payloads carry {min,max,severity} only, no band annotation."""
    return {
        name: {k: v for k, v in t.items() if not k.startswith("_")} for name, t in entries.items()
    }


def _yaml_snippet(entries: dict, indent: str) -> str:
    lines = []
    for name, t in entries.items():
        lo, hi = t["_band"]
        lines.append(f"{indent}# band [{lo:.6f}, {hi:.6f}]; campaign-2 reference run")
        lines.append(f"{indent}# (artifacts/campaign2/reference-run.json), mid -+ 4 half-widths,")
        lines.append(f"{indent}# structural clip -> null exactly as this section's header states.")
        mn = "null" if t["min"] is None else t["min"]
        mx = "null" if t["max"] is None else t["max"]
        lines.append(f'{indent}"{name}": {{min: {mn}, max: {mx}, severity: report}}')
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    ref = json.loads(REF_PATH.read_text("utf-8"))
    assert ref["vintage_id"] == "2026-08-02.4", ref["vintage_id"]
    assert ref["missing_factors"] == ["commodities"], ref["missing_factors"]
    assert ref["seed"] == 20260726

    # RFR-61: pre-existing sealed bands, quoted in pre-registration.yaml's own
    # comments, recomputed on the new vintage. Any drift is disclosed loudly.
    sealed_bands = {
        ("global", "equity_mkt.skew"): (-1.087435, 0.668305),
        ("global", "equity_mkt.excess_kurtosis"): (-0.389892, 5.443227),
        ("global", "equity_mkt.acf_abs_sum"): (-0.281798, 3.247541),
        ("global", "equity_mkt.leverage_correlation"): (-0.382038, 0.058947),
        ("global", "equity_mkt.hill_tail_index_5pct"): (1.890591, 5.874610),
        ("us", "policy_rate.excess_kurtosis"): (-1.455738, 2.169716),
        ("us", "ust_10y.acf_r_lag1"): (0.921121, 0.975344),
        ("us", "ust_10y.acf_r_sum"): (3.659931, 4.564024),
        ("us", "ust_10y.excess_kurtosis"): (-1.181082, 0.666286),
        ("us", "cpi.excess_kurtosis"): (-1.545279, 2.006997),
    }
    drifted = []
    for (block, name), (lo, hi) in sealed_bands.items():
        band = ref["blocks"][block][name]
        if abs(band["lo"] - lo) > 5e-7 or abs(band["hi"] - hi) > 5e-7:
            drifted.append((name, (lo, hi), (band["lo"], band["hi"])))
    if drifted:
        print("RFR-61: PRE-EXISTING BANDS MOVED ON THE NEW VINTAGE (disclosed):")
        for name, old, new in drifted:
            print(f"  {name}: sealed {old} -> new {new}")
    else:
        print("RFR-61: all checked pre-existing bands BIT-IDENTICAL on the new vintage.")

    block_thresholds, cross_thresholds = derive_thresholds(ref)
    for block, entries in block_thresholds.items():
        print(f"\nthresholds.blocks.{block}:")
        print(_yaml_snippet(entries, "      "))
    for pair_key, entries in cross_thresholds.items():
        print(f'\nthresholds.cross_blocks."{pair_key}":')
        print(_yaml_snippet(entries, "      "))

    cov = ref["coverage"]
    print("\ncoverage additions:")
    for f in ("hy_spread", "fx_usd", "cape_v"):
        c = cov[f]
        print(
            f'    {f}: {{first: "{c["first_date"]}", last: "{c["last_date"]}", n_obs: {c["n_obs"]}}}'
        )

    if not args.apply:
        print("\n(dry run; --apply appends the amendments)")
        return

    fx_payload = {
        "block": "fx",
        "block_thresholds": _strip(block_thresholds["fx"]),
        "cross_block_thresholds": {
            k: _strip(v) for k, v in cross_thresholds.items() if k.startswith("fx|")
        },
        "reference_run_artifact": "artifacts/campaign2/reference-run.json",
    }
    valuation_payload = {
        "block": "valuation",
        "block_thresholds": _strip(block_thresholds["valuation"]),
        "cross_block_thresholds": {
            k: _strip(v) for k, v in cross_thresholds.items() if k.endswith("|valuation")
        },
        "reference_run_artifact": "artifacts/campaign2/reference-run.json",
    }
    append_amendment(
        LOG_PATH,
        Amendment(
            amendment_id="AM-2026-08-02-007",
            type="block_addition",
            date=DATE,
            rationale=(
                "CAMPAIGN-2 FX BLOCK (owner-ratified; decision R5's recorded re-entry, "
                "S2R-FX-NEXT-CAMPAIGN; RFR-2 closes). fx_usd = trade-weighted broad "
                "dollar (fred.DTWEXBGS) extended pre-2006 by the fx_usd_pre2006 splice "
                "(donor fred.DTWEXM, overlap 2006-2019 entirely inside train+validation, "
                "fit at read time from sanctioned reads). Thresholds derived PRE-HOC "
                "from the campaign-2 reference run at the sealed recipe (mid -+ 4 "
                "half-widths, structural clips, severity report); the representative "
                "cross statistics mirror the sealed global|us convention "
                "(crisis_corr_lift on the block's macro-natural pairs: dollar~equity "
                "flight interaction, dollar~long-rate differentials). The conventions "
                "block classifies fx_usd as a level in the same edit."
            ),
            post_hoc=False,
            payload=fx_payload,
        ),
    )
    append_amendment(
        LOG_PATH,
        Amendment(
            amendment_id="AM-2026-08-02-008",
            type="block_addition",
            date=DATE,
            rationale=(
                "CAMPAIGN-2 VALUATION BLOCK (owner: 'include CAPE in this seal'; "
                "completes S2-VALUATION-FACTOR, closes RFR-18's factor gap -- RFR-81 "
                "found only the mapping was missing). cape_v = DN-1's v_t, demeaned log "
                "CAPE (derive.demeaned_log_cape over shiller.cape), a signed level; "
                "activating it turns ten_year_return_vs_valuation_{slope,r2} from "
                "STRUCTURALLY_UNAVAILABLE into computed 10yr-tier statistics (report "
                "tier; no new enforce threshold -- selecting names after seeing a run "
                "is how a threshold gets fitted, per the sealed blocks header). "
                "Thresholds derived PRE-HOC at the sealed recipe, as AM-007."
            ),
            post_hoc=False,
            payload=valuation_payload,
        ),
    )
    append_amendment(
        LOG_PATH,
        Amendment(
            amendment_id="AM-2026-08-02-009",
            type="protocol_change",
            date=DATE,
            rationale=(
                "CAMPAIGN-2 RE-SEAL (owner-ratified end to end: 'C3 - accept and "
                "document, proceed with the campaign seal'; 'proceed with the "
                "amendments and re-mint when the bands land'). One dated event, five "
                "connected changes: (1) campaign_vintage_id 2026-07-26.1 -> "
                "2026-08-02.4 (RFR-91/92 data groundwork; RFR-61 discipline applied -- "
                "every checked pre-existing band recomputed on the new vintage at the "
                "sealed seed, outcome recorded in the reference-run artifact). "
                "(2) hy_spread restored: the hy_oas_pre1996 splice is APPLIED AT THE "
                "READ SURFACE with a PINNED fit (splice.PINNED_FITS, owner decision -- "
                "the rule's only licensed fitting window lies inside the holdout span, "
                "so the two scalars a=1.4068184862787785, b=2.53288508610114 were "
                "frozen offline; the residual post-2020 information flow is exactly "
                "those two published constants). reference_run.missing_factors "
                "[commodities, hy_spread] -> [commodities]; bootstrap_v1.factor_set "
                "grows to fifteen. (3) splice.py JOINS THE SEAL (RFR-50's recorded "
                "re-entry condition fires: it is on the read path). (4) judged code "
                "changed and is re-hashed: panel.py (splice-aware derived exprs, "
                "optional-input contract), derive.py (splice application helpers), "
                "reference.py unchanged in body but re-hashed with the set, "
                "horizon.py (RFR-18 metric activation), factors.py surface untouched. "
                "(5) The campaign proceeds under decision C3: the sealed 10yr-tier "
                "defects (level-factor half-lives at the block-reassembly timescale; "
                "equity/hml lost-decade excess) are ACCEPTED as documented limits with "
                "Instructions/campaign2-regime-fix-options.md as the mechanism trace; "
                "promotion trains WITHOUT the A' residual parameterization and at "
                "guidance 1.0. This is a protocol_change: the lock is stale by design "
                "until the campaign-2 re-mint that accompanies this amendment."
            ),
            post_hoc=False,
            payload={
                "campaign_vintage_id": {"from": "2026-07-26.1", "to": "2026-08-02.4"},
                "missing_factors": {"from": ["commodities", "hy_spread"], "to": ["commodities"]},
                "factor_set_n": {"from": 12, "to": 15},
                "pinned_fit_hy_oas_pre1996": {
                    "a": 1.4068184862787785,
                    "b": 2.53288508610114,
                    "overlap_rmse": 0.2058317839495792,
                    "fit_window": "2023-08..2026-07 (36 obs; inside the holdout span)",
                },
                "c3_mechanism_trace": "Instructions/campaign2-regime-fix-options.md",
            },
        ),
    )
    print("\nthree amendments appended to governance/amendment-log.yaml")

    # sanity: the merged document must load and the manifest must agree
    prereg = load(PREREG_PATH)
    manifest = load_manifest()
    assert prereg.active_blocks == manifest.active_blocks
    print("post-apply: pre-registration.yaml loads; active_blocks agree with the manifest")


if __name__ == "__main__":
    main()
