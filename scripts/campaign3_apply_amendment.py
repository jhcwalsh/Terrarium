"""Append AM-2026-08-10-001 (the campaign-3 seal event) and re-seal ALL THREE
locks in one motion.

Run AFTER every pre-registration.yaml / factors.yaml / code edit of the event
is in the working tree:  uv run python scripts/campaign3_apply_amendment.py

One amendment, three re-seals, one commit (the caller commits). The payload
carries the superseded digests of all three locks -- the AM-2026-08-09-004/-005
lesson (an edit to a file named by more than one seal_scope re-seals EVERY lock
that hashes it, in the same commit) applied prospectively rather than caught by
the gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.eval.g3seal import seal_g3  # noqa: E402
from ah.eval.g5seal import seal_g5  # noqa: E402
from ah.eval.prereg import Amendment, append_amendment, seal  # noqa: E402

LOG_PATH = _REPO_ROOT / "governance" / "amendment-log.yaml"
PREREG_PATH = _REPO_ROOT / "pre-registration.yaml"
LOCK_PATH = _REPO_ROOT / "pre-registration.lock"
DATE = "2026-08-10"

REF = json.loads((_REPO_ROOT / "artifacts" / "campaign3" / "reference-run.json").read_text("utf-8"))
assert REF["vintage_id"] == "2026-08-10.1"
assert REF["missing_factors"] == [] and REF["missing_no_data"] == []

# The commodities threshold payload, in apply_block_addition SHAPE as the audit
# record -- the machinery itself requires a newly-active BLOCK and commodities
# joins the existing `global` block, so the merge is carried by the main edit
# and this payload documents exactly what was added (edit-blocks Block 3's
# stated fallback).
COMMODITIES_THRESHOLDS = {
    "commodities.skew": {"min": -4.0662, "max": 4.6583, "severity": "report"},
    "commodities.excess_kurtosis": {"min": None, "max": 10.9203, "severity": "report"},
    "commodities.acf_abs_sum": {"min": -7.0235, "max": 9.7678, "severity": "report"},
    "commodities.leverage_correlation": {"min": None, "max": None, "severity": "report"},
    "commodities.hill_tail_index_5pct": {"min": None, "max": 11.6604, "severity": "report"},
}

RATIONALE = (
    "THE CAMPAIGN-3 SEAL EVENT: the first campaign on the extended panel "
    "(design docs/superpowers/specs/2026-08-09-campaign3-design.md; owner "
    "rulings K1-K4 2026-08-09; commodities-emission ruling 2026-08-10). "
    "post_hoc FALSE: no generator has been trained on the extended panel and "
    "no campaign-3 result exists -- everything here is sealed before the "
    "evidence it will judge. IN THIS EVENT, one commit: (1) campaign_vintage_id "
    "-> 2026-08-10.1, the first clean weekday vintage carrying the extension "
    "donors and the AQR commodities series; the campaign-2 record (2026-08-02.4) "
    "is closed and untouched. (2) reference_run re-derived at the KEPT seed "
    "20260726 (artifacts/campaign3/reference-run.json): every factor whose data "
    "is unchanged reproduces its band BIT-IDENTICALLY (verified: equity_mkt, "
    "cpi, cape_v families); every moved band belongs to an extended factor and "
    "is quoted with its superseded value in place. CAMPAIGN-2 BANDS ARE DEAD "
    "LETTERS: nothing was carried by habit; the three carried numbers "
    "(elicitability 5.0, panel absolutes, exceedance gates) are each an "
    "explicit, argued choice in the sealed comments. (3) missing_factors and "
    "uncomputable_d4_strategies are EMPTY for the first time: commodities "
    "sourced (ruling K2, REG-licensed AQR intake, factors.yaml expr add over "
    "aqr.cmdty_ew_excess + french.rf); all five D4 strategies carry sealed "
    "thresholds. Commodities also JOINS bootstrap_v1.factor_set / "
    "bootstrap.FACTOR_SET (owner ruling 2026-08-10) so the restored strategies "
    "are judgeable on generated paths. Its five per-name bounds (payload, "
    "apply_block_addition shape as audit record -- the machinery requires a "
    "newly-active block, commodities joins the existing global block, so the "
    "main edit carries the merge) mirror equity_mkt's return-factor convention. "
    "(4) The K-rulings sealed: future_accruing_holdout (K1; accrual 2026-09-01, "
    "earliest read 2029-01-01, one read ever); har_masked_ablation + ablation "
    "system F (K3, with its demotion criterion); S3-K4-HARDWARE-GATE ships "
    "OPEN (training gated on the owner's host call; the seal does not wait). "
    "(5) severe_test_protocol.benchmark_exception RETIRED (the extended span "
    "contains the excluded decade and the 1965 start state; superseded G2 text "
    "kept verbatim) and severe_test_criterion sealed WITH the procedure "
    "(RFR-77's lesson). (6) multi_seed_decision_rule.benchmark_draw_span_bias "
    "RETIRED (the disclosed mechanism is gone) and REPLACED by "
    "proxy_share_disclosure -- the extended span's own asymmetry, now a sealed "
    "reporting requirement. (7) THE THREE FX CROSS-PAIR ENTRIES SEAL VACUOUS "
    "WITH THE REASON STATED: their crisis_corr_lift bands are NaN on the "
    "extended panel (pegged-era resamples -> the AM-2026-08-09-003 degenerate-"
    "variance sentinel -> RFR-19's deliberately non-NaN-robust percentile; "
    "n_valid_resamples 882/1000, disclosed). Switching statistics after seeing "
    "the run would be name-selection; the entries stay, vacuous and honest. "
    "(8) The pinned equity-vol artifacts enter the sealed document by sha "
    "(payload). (9) ALL THREE LOCKS RE-SEALED IN THIS ONE COMMIT -- "
    "factors.yaml, derive.py, prereg.py and reference.py are hashed by main, "
    "G3 and G5 alike; the superseded digests are in the payload (the "
    "AM-2026-08-09-004/-005 lesson applied prospectively). Campaign-2 "
    "reproducibility from the live tree ended at AM-2026-08-09-003 and is "
    "unchanged by this event; the sealed campaign-2 artifacts stand."
)

PAYLOAD = {
    "campaign_vintage_id": "2026-08-10.1",
    "reference_run_artifact": "artifacts/campaign3/reference-run.json",
    "seal_evidence_artifact": "artifacts/campaign3/seal-evidence.json",
    "reference_seed_kept": 20260726,
    "commodities_activation": {
        "factor": "commodities",
        "expr": "add",
        "inputs": ["aqr.cmdty_ew_excess", "french.rf"],
        "block": "global",
        "block_thresholds": COMMODITIES_THRESHOLDS,
        "cross_block_thresholds": {},
        "joins_factor_set": True,
    },
    "pinned_artifacts": {
        "equity_vol_pinned_draw": {
            "path": "src/ah/data/equity_vol_pinned_draw.json",
            "sha256": "53a378a49bfa58f9457698473457f526298efe5454ca9187ff2c35ca3fb50178",
        },
        "equity_vol_backcast_provenance": {
            "path": "artifacts/volext/equity-vol-backcast-provenance.json",
            "sha256": "f0535582c061cc60ea8605aa9085d457b27dbc12af5e4718aed557146284fc92",
        },
    },
    "superseded_lock_digests": {
        "main": "sha256:6061fd73d9a5d25f0b105e3f1a96ddd5570bbc24c559afaf25d8b330d17636ce",
        "g3": "sha256:67384dcc6085edcdeabb3e3f1a856b581b637be5ca5220000527571424c0dccf",
        "g5": "sha256:5a7a6ca26dbe5fd17c4bcbb3d77774bb167364dc41f18afa75947d637d1adfd4",
    },
}


def main() -> None:
    append_amendment(
        LOG_PATH,
        Amendment(
            amendment_id="AM-2026-08-10-001",
            type="protocol_change",
            date=DATE,
            rationale=RATIONALE,
            post_hoc=False,
            payload=PAYLOAD,
        ),
    )
    print("amendment appended: AM-2026-08-10-001")
    d_main = seal(PREREG_PATH, out_path=LOCK_PATH, sealed_at=DATE)
    print("main lock:", d_main)
    d_g3 = seal_g3(sealed_at=DATE)
    print("g3 lock:  ", d_g3)
    d_g5 = seal_g5(sealed_at=DATE)
    print("g5 lock:  ", d_g5)


if __name__ == "__main__":
    main()
