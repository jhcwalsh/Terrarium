"""Write docs/data/LICENSE-REGISTRY.md: what needs a licence before commercial use.

Run from the repo root:  uv run python scripts/build_license_registry.py

Two halves, and the split matters:

* REGISTERED series, grouped by the ``license_tier`` already in
  requirements.yaml. Generated, so it cannot drift from the manifest.
* KNOWN GAPS -- quantities the platform declares it needs but has no series
  for, each with why free data does not close it. Hand-maintained here
  because a gap is an argument, not a row.

The registry is a COMMERCIAL-USE checklist, not a permission to use anything:
FREE covers redistribution too, REG means registration/attribution terms apply,
COMM means a paid licence is required and the data must not be redistributed.
``Requirement.redistributable`` is the machine-readable half (FREE only).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ah.data.manifest import load_requirements  # noqa: E402

OUT_PATH = ROOT / "docs" / "data" / "LICENSE-REGISTRY.md"

TIER_NOTES = {
    "FREE": "public domain or explicitly free to redistribute; no licence needed for commercial use",
    "REG": "free to obtain but carries registration/attribution/terms-of-use conditions -- CHECK the terms before commercial use, do not redistribute raw",
    "COMM": "paid commercial licence REQUIRED; must not be redistributed; commercial use is blocked until the licence is in place",
}

#: Quantities the platform declares it needs and has no series for. Each entry
#: says what would close it and why free data does not.
GAPS: list[dict[str, str]] = [
    {
        "need": "Commodities total return",
        "consumer": "factors.yaml `commodities` (kind: unavailable); named in "
        "pre-registration.yaml `missing_factors`, so the seal REJECTS any threshold keyed to it",
        "candidate": "Bloomberg Commodity Index (BCOM) TR, S&P GSCI TR, or equivalent",
        "tier": "COMM",
        "why_free_fails": "FRED's free commodity series are PRICE indices, not investable "
        "total-return indices: PPIACO is a producer price index (1913+), PALLFNFINDEXM an IMF "
        "spot-price index (1992+). The factor declares numeraire total_return, and a spot price "
        "index is a different quantity -- registering one as `commodities` would be exactly the "
        "plausible substitution this platform refuses. Verified 2026-08-08.",
        "unlocks": "closes a sealed missing_factor; implies a campaign retrain, not just a fetch",
    },
    {
        "need": "High-yield OAS, full history",
        "consumer": "factors.yaml `hy_spread` (currently ~97% proxy); also in "
        "pre-registration.yaml `missing_factors` for train+validation",
        "candidate": "ICE BofA US High Yield Index OAS (BAMLH0A0HYM2) with full history, "
        "direct from ICE rather than via FRED",
        "tier": "COMM",
        "why_free_fails": "FRED serves the ICE BAML family from 2023-08-08 ONLY -- verified "
        "2026-08-08, and the IG series (BAMLC0A0CM) is truncated to the same date, which "
        "confirms it is an ICE licensing policy rather than a data-availability limit. Every "
        "licensed actual therefore falls inside the holdout span. The free Baa-Aaa splice "
        "(fred.BAA - fred.AAA, 1919+) is the documented proxy and remains in use.",
        "unlocks": "retires the platform's largest single proxy; lets hy_spread join "
        "train+validation with actuals",
    },
    {
        "need": "3-month TERM SOFR",
        "consumer": "would be the tenor-matched TED successor for factors.yaml `funding_spread`",
        "candidate": "CME Term SOFR reference rates",
        "tier": "COMM",
        "why_free_fails": "CME licenses term SOFR. Overnight SOFR is free (registered as "
        "fred.SOFR) but is SECURED overnight repo, not TED's unsecured 3-month bank funding. "
        "MITIGATED, NOT BLOCKING: fred.CPF3M - fred.TB3M_SEC gives a free 3-month unsecured "
        "CP-bill spread of the same construction. MEASURED on the 300-month overlap "
        "(1997-01..2022-01, vintage 2026-08-08.2): correlation with TED +0.969 in levels and "
        "+0.918 in changes, the same crisis peak month (2008-10), and OLS CP-bill = 0.823 x TED "
        "- 0.061 -- a slightly damped but faithful tracker. It adds 55 months of coverage TED "
        "cannot have (2022-01..2026-08). Term SOFR would be a tenor-matched improvement, not a "
        "prerequisite.",
        "unlocks": "tenor-matched purity; the CP-bill spread already closes the practical gap",
    },
    {
        "need": "Private-markets cashflow lifecycle (ALB-A..E)",
        "consumer": "cashflow-tier0 historical-simulation leg (UNPARAMETERIZABLE without it); "
        "ER-6's rc_curve; the commitment lever E1",
        "candidate": "Albourne ALB-A..E -- or, per docs/data/ALBOURNE-COEFFICIENT-REQUEST.md, "
        "the pacing COEFFICIENTS instead of the raw datasets",
        "tier": "COMM",
        "why_free_fails": "no public source publishes fund-age call and distribution schedules "
        "at strategy granularity. The coefficient request is the cheaper ask and is already "
        "drafted.",
        "unlocks": "closes ER-6; unblocks the commitment lever",
    },
]


def main() -> int:
    reqs = load_requirements()
    by_tier: dict[str, list] = {}
    for r in sorted(reqs, key=lambda q: q.series_id):
        by_tier.setdefault(r.license_tier, []).append(r)

    lines = [
        "# Licence registry — what needs clearing before commercial use",
        "",
        f"*Half generated by `scripts/build_license_registry.py` from `requirements.yaml` "
        f"({datetime.now(UTC).date().isoformat()}); half hand-maintained. Regenerate after "
        "any manifest change.*",
        "",
        "**This is a checklist, not a clearance.** Tiers:",
        "",
    ]
    for tier, note in TIER_NOTES.items():
        lines.append(f"- **{tier}** — {note}")
    lines += [
        "",
        "`Requirement.redistributable` is the machine-readable half of this and is true for "
        "FREE only.",
        "",
        "## Part 1 — registered series, by tier",
        "",
    ]
    for tier in ("COMM", "REG", "FREE"):
        entries = by_tier.get(tier, [])
        lines += [f"### {tier} ({len(entries)} series)", ""]
        if not entries:
            lines += ["_none_", ""]
            continue
        if tier == "FREE":
            sources: dict[str, int] = {}
            for r in entries:
                sources[r.source] = sources.get(r.source, 0) + 1
            lines.append(
                "No licence needed. By source: "
                + ", ".join(f"`{s}` ({n})" for s, n in sorted(sources.items()))
                + "."
            )
            lines.append("")
            continue
        lines += ["| series | source | frequency | priority | notes |", "|---|---|---|---|---|"]
        for r in entries:
            note = (r.notes or "").split(".")[0][:110] if r.notes else ""
            lines.append(
                f"| `{r.series_id}` | {r.source} | {r.frequency} | {r.priority} | {note} |"
            )
        lines.append("")

    lines += [
        "## Part 2 — gaps: needed, unlicensed, no series registered",
        "",
        "Each of these is a quantity the platform declares it needs. None is a bug or a "
        "backlog item: the absence is recorded in the sealed artifacts rather than filled "
        "with a plausible substitute.",
        "",
    ]
    for g in GAPS:
        lines += [
            f"### {g['need']} — tier {g['tier']}",
            "",
            f"- **Consumer:** {g['consumer']}",
            f"- **Candidate:** {g['candidate']}",
            f"- **Why free data does not close it:** {g['why_free_fails']}",
            f"- **What a licence unlocks:** {g['unlocks']}",
            "",
        ]

    lines += [
        "## A note on how these are wired",
        "",
        "Registering and fetching a series changes `requirements.yaml` only. MAPPING one to a "
        "generator factor changes `factors.yaml`, which is hashed by BOTH pre-registration "
        "locks — so it is an amendment plus a re-seal, and for the two entries named in "
        "`missing_factors` it additionally implies a campaign retrain. Buying the data is "
        "therefore the first step of the work, not the whole of it.",
        "",
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    counts = {t: len(by_tier.get(t, [])) for t in ("FREE", "REG", "COMM")}
    print(f"wrote {OUT_PATH.relative_to(ROOT)}: {counts}, {len(GAPS)} gaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
