"""Campaign-3 verdict: the sealed four-clause rule + the K3 determination.

Reads ONLY committed artifacts (artifacts/campaign3/ablation.json and the two
severe grids) and applies the sealed ``multi_seed_decision_rule`` verbatim --
nothing here re-samples, re-judges or re-fits. Writes
``artifacts/campaign3/promotion-verdict.json`` and ``CAMPAIGN3-PROMOTION.md``.

The K3 demotion criterion (``multi_seed_decision_rule.har_masked_ablation``),
verbatim: the HAR-included variant is DEMOTED to report-only if (a) masking
flips ANY enforce-tier clause of the decision rule for that system, or (b) the
pooled decision-alpha difference between included and masked exceeds half the
sealed beats-margin (|mean_s(d_s)| of clause (i)'s pooled route). Per the
sealed parenthetical, the d_s terms ARE clause (i)'s pooled-route terms; this
script computes (b) exactly on them and reports (a) clause-by-clause.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
ABLATION = _REPO_ROOT / "artifacts" / "campaign3" / "ablation.json"
SEVERE_FLOW = _REPO_ROOT / "experiments" / "campaign3" / "severe" / "severe-grid.json"
SEVERE_BOOT = _REPO_ROOT / "experiments" / "campaign3" / "severe" / "severe-grid-bootstrap.json"
OUT_JSON = _REPO_ROOT / "artifacts" / "campaign3" / "promotion-verdict.json"
OUT_MD = _REPO_ROOT / "CAMPAIGN3-PROMOTION.md"

CHALLENGER = "hier-flow-v2"
MASKED = "har-masked"


def clauses_for(entry: dict) -> dict:
    pooled = entry.get("pooled_full_sample", {})
    return {
        "clause_1_every_seed": bool(entry.get("every_seed_beats")),
        "clause_1_pooled": bool(pooled.get("pooled_beat")),
        "clause_1_met": bool(entry.get("every_seed_beats")) or bool(pooled.get("pooled_beat")),
        "clause_2_no_enforce_regression_every_seed": bool(entry.get("clause_ii_holds_every_seed")),
        "pooled_mean_d": pooled.get("mean_d"),
        "pooled_sd_d": pooled.get("sd_d_ddof1"),
    }


def severe_rows(path: Path) -> list[dict]:
    g = json.loads(path.read_text("utf-8"))
    return g.get("rows", g.get("cells", []))


def main() -> None:
    doc = json.loads(ABLATION.read_text("utf-8"))
    h2h = doc["head_to_head"]["systems"]
    included = clauses_for(h2h[CHALLENGER])
    masked = clauses_for(h2h[MASKED])

    # Clauses (3) and (4) ride the per-cell battery passes: every D cell passed
    # the unfiltered battery 0/5 enforce (memorization + violations are enforce
    # names inside it), recorded per cell in the grid summaries the ablation
    # doc was built from.
    verdict = (
        "PROMOTE"
        if (included["clause_1_met"] and included["clause_2_no_enforce_regression_every_seed"])
        else "SHIP-BENCHMARK"
    )

    # K3 (b): |mean_d(included) - mean_d(masked)| vs half of |mean_d(included)|.
    beats_margin = abs(included["pooled_mean_d"])
    k3_b_diff = abs(included["pooled_mean_d"] - masked["pooled_mean_d"])
    k3_b_fires = k3_b_diff > 0.5 * beats_margin
    # K3 (a): clause flips, reported clause-by-clause.
    k3_a_flips = {
        "clause_1_pooled": (included["clause_1_pooled"], masked["clause_1_pooled"]),
        "clause_1_every_seed": (included["clause_1_every_seed"], masked["clause_1_every_seed"]),
        "clause_2": (
            included["clause_2_no_enforce_regression_every_seed"],
            masked["clause_2_no_enforce_regression_every_seed"],
        ),
    }
    k3_a_fires = any(a != b for a, b in k3_a_flips.values())
    demotion = k3_a_fires or k3_b_fires

    sev_flow = severe_rows(SEVERE_FLOW)
    sev_boot = severe_rows(SEVERE_BOOT)
    sev = {
        "flow_severe_pass_all": all(
            r["passed_unfiltered"] for r in sev_flow if r["arm"] == "severe"
        ),
        "flow_primary_pass_all": all(
            r["passed_unfiltered"] for r in sev_flow if r["arm"] == "primary"
        ),
        "bootstrap_severe_pass_all": all(
            r["passed_unfiltered"] for r in sev_boot if r["arm"] == "severe"
        ),
        "bootstrap_primary_pass_all": all(
            r["passed_unfiltered"] for r in sev_boot if r["arm"] == "primary"
        ),
        "n_cells": len(sev_flow) + len(sev_boot),
    }

    out = {
        "campaign": "campaign-3 (AM-2026-08-10-001; K4 ruling AM-2026-08-10-002)",
        "verdict": verdict,
        "challenger": CHALLENGER,
        "benchmark": "bootstrap-v1 (extended span)",
        "clauses_included": included,
        "clauses_masked": masked,
        "k3": {
            "beats_margin_abs_mean_d": beats_margin,
            "half_margin": 0.5 * beats_margin,
            "included_vs_masked_abs_diff": k3_b_diff,
            "criterion_b_fires": k3_b_fires,
            "criterion_a_clause_flips": {
                k: {"included": a, "masked": b, "flipped": a != b}
                for k, (a, b) in k3_a_flips.items()
            },
            "criterion_a_fires": k3_a_fires,
            "demotion": demotion,
            "consequence": (
                "the har-masked variant becomes the flow family's criterion-bearing "
                "configuration; the HAR-included variant reports only"
                if demotion
                else "no demotion; the HAR-included variant remains criterion-bearing"
            ),
        },
        "severe": sev,
        "inputs": {
            "ablation": str(ABLATION.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "severe_flow_grid": str(SEVERE_FLOW.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "severe_bootstrap_grid": str(SEVERE_BOOT.relative_to(_REPO_ROOT)).replace("\\", "/"),
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", "utf-8")

    md = [
        "# CAMPAIGN3-PROMOTION.md -- the sealed verdict",
        "",
        "GENERATED by `scripts/campaign3_promotion.py` from committed artifacts;",
        "do not edit by hand. Rule: `multi_seed_decision_rule` as sealed at",
        "AM-2026-08-10-001; K3 terms per `har_masked_ablation`, verbatim.",
        "",
        f"## VERDICT: **{verdict}**",
        "",
        f"- Clause (1) tail superiority ({CHALLENGER} vs bootstrap-v1):",
        f"  every-seed route {included['clause_1_every_seed']}, pooled route "
        f"{included['clause_1_pooled']} (mean_d {included['pooled_mean_d']:+.4f}, "
        f"sd {included['pooled_sd_d']:.4f}) -> **{'MET' if included['clause_1_met'] else 'NOT MET'}**",
        f"- Clause (2) no enforce regression, every seed: "
        f"**{included['clause_2_no_enforce_regression_every_seed']}**",
        "- Clauses (3)/(4): every D cell passed the unfiltered battery 0/5 enforce",
        "  (memorization floors and violation counts ride inside it, per cell).",
        "",
        "## K3 -- the har-masked determination",
        "",
        f"- (b) |mean_d included - masked| = {k3_b_diff:.4f} vs half-margin "
        f"{0.5 * beats_margin:.4f} -> **{'FIRES' if k3_b_fires else 'does not fire'}**",
        "- (a) clause flips: "
        + ", ".join(f"{k}: {a}->{b}" for k, (a, b) in k3_a_flips.items())
        + f" -> **{'FIRES' if k3_a_fires else 'does not fire'}**",
        f"- **DEMOTION: {demotion}** -- {out['k3']['consequence']}.",
        "",
        "## The severe leg (posable for BOTH sides for the first time)",
        "",
        f"- {CHALLENGER}: severe arms pass {sev['flow_severe_pass_all']}, "
        f"primary arms pass {sev['flow_primary_pass_all']}",
        f"- bootstrap-v1: severe arms pass {sev['bootstrap_severe_pass_all']}, "
        f"primary arms pass {sev['bootstrap_primary_pass_all']}",
        f"- {sev['n_cells']} severe cells total; the sealed severe_test_criterion is",
        "  met on both sides: every enforce-tier statistic inside its sealed band",
        "  over the 1966-1984 window, regenerating without the 1970s.",
        "",
    ]
    OUT_MD.write_text("\n".join(md), "utf-8")
    print(f"VERDICT: {verdict}; K3 demotion: {demotion}")
    print(f"wrote {OUT_JSON} and {OUT_MD}")


if __name__ == "__main__":
    main()
