"""Generate the frozen authoring regression set (WP4.5).

Run:  uv run python scripts/gen_authoring_regression.py

The G4-pre freeze's membership rule, made concrete: ~30 payloads spanning
{bull, crash, gate_event, comp_gap, quiet} x {the two held letter
entities} for P-LETTER and x {the disagreeing house pair} x {two
subjects} for P-NOTE. Every number is a fixed constant here — the set is
deterministic, regeneration is byte-identical, and the manifest's
per-payload SHA-256 hashes ARE the freeze (tests/test_authoring_regression
fails on any drift). Any prompt or model change re-runs this set.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ah.artifacts.payloads import build_p_letter, build_p_note

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = _REPO_ROOT / "fixtures" / "authoring_regression" / "payloads"
MANIFEST = _REPO_ROOT / "fixtures" / "authoring_regression" / "manifest.yaml"
BIBLE = _REPO_ROOT / "Instructions" / "example-bible-credit-winter.json"

DATELINE = "2028-03-15"
DATELINE_QUARTER = 8
QUARTER_LABEL = "2028-Q1"

# scenario -> (rep_q, rep_ytd, rep_si, pub_q, hy_bps, rate, cpi, gate_status, extracts)
LETTER_SCENARIOS: dict[str, dict[str, Any]] = {
    "bull": dict(
        rep_q=0.032,
        rep_ytd=0.060,
        rep_si=0.45,
        pub_q=0.040,
        hy=320.0,
        rate=0.045,
        cpi=0.024,
        gate_status="open",
        extracts=["Equities extend gains", "New issuance windows reopen"],
    ),
    "crash": dict(
        rep_q=-0.085,
        rep_ytd=-0.120,
        rep_si=0.10,
        pub_q=-0.180,
        hy=780.0,
        rate=0.0525,
        cpi=0.041,
        gate_status="open",
        extracts=["Equities enter bear market territory", "Spreads gap wider on default fears"],
    ),
    "gate_event": dict(
        rep_q=-0.020,
        rep_ytd=-0.035,
        rep_si=0.18,
        pub_q=-0.030,
        hy=640.0,
        rate=0.0525,
        cpi=0.038,
        gate_status="gated",
        extracts=["Stonebeck Credit gates redemptions", "Secondary bids quoted in the low 80s"],
    ),
    "comp_gap": dict(
        rep_q=0.005,
        rep_ytd=0.010,
        rep_si=0.28,
        pub_q=0.090,
        hy=380.0,
        rate=0.0475,
        cpi=0.027,
        gate_status="open",
        extracts=["Public rally leaves private marks behind", "Listed comps rerate sharply"],
    ),
    "quiet": dict(
        rep_q=0.011,
        rep_ytd=0.011,
        rep_si=0.33,
        pub_q=0.013,
        hy=400.0,
        rate=0.05,
        cpi=0.029,
        gate_status="open",
        extracts=["A quiet session on the wire", "Data prints in line"],
    ),
}

NOTE_SUBJECTS = ("private_credit", "stonebeck")
RIVAL_STANCE = {
    "calder": "Grimshaw Partners: fragilities are compounding beneath stable marks.",
    "grimshaw": "Calder & Root: policy support resolves the stress; stay the course.",
}


def _write(payload_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    path = OUT_DIR / f"{payload_id}.json"
    text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return payload_id, hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    bible = json.loads(BIBLE.read_text("utf-8"))
    cast = {c["id"]: c for c in bible["cast"]}
    houses = {h["id"]: h for h in bible["research_houses"]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[tuple[str, str]] = []
    for scenario, s in LETTER_SCENARIOS.items():
        for entity_id in ("meridian", "stonebeck"):
            payload = build_p_letter(
                entity=cast[entity_id],
                dateline=DATELINE,
                dateline_quarter=DATELINE_QUARTER,
                quarter_label=QUARTER_LABEL,
                reported_return_q=s["rep_q"],
                reported_return_ytd=s["rep_ytd"],
                reported_return_si=s["rep_si"],
                nav_index=100.0 * (1.0 + s["rep_ytd"]),
                distributions_flag=s["rep_q"] > 0,
                calls_flag=scenario in ("crash", "gate_event"),
                gate_status=s["gate_status"],
                secondary_market_context=(
                    "secondaries quoted low-80s vs NAV"
                    if scenario in ("crash", "gate_event")
                    else "secondary market quiet"
                ),
                public_equity_q=s["pub_q"],
                hy_spread_now_bps=s["hy"],
                policy_rate_now=s["rate"],
                cpi_now=s["cpi"],
                chronicle_extracts=s["extracts"],
            )
            entries.append(_write(f"letter-{scenario}-{entity_id}", payload))
        for house_id in ("calder", "grimshaw"):
            for subject in NOTE_SUBJECTS:
                payload = build_p_note(
                    house=houses[house_id],
                    rival_stance_summary=RIVAL_STANCE[house_id],
                    subject=subject,
                    dateline=DATELINE,
                    dateline_quarter=DATELINE_QUARTER,
                    ytd_return=s["rep_ytd"],
                    one_year_return=s["rep_si"] / 3.0,
                    drawdown=min(0.0, s["pub_q"]),
                    hy_spread_now_bps=s["hy"],
                    policy_rate_now=s["rate"],
                    cpi_now=s["cpi"],
                    reported_vs_public_gap=s["rep_q"] - s["pub_q"],
                    chronicle_extracts=s["extracts"],
                )
                entries.append(_write(f"note-{scenario}-{house_id}-{subject}", payload))

    lines = [
        "# authoring_regression manifest -- the WP4.5 freeze (AM-2026-08-02-002)",
        "#",
        "# Membership rule, frozen at G4-pre: ~30 payloads spanning",
        "# {bull, crash, gate_event, comp_gap, quiet} x {entity kinds, house pair}.",
        "# Regeneration (scripts/gen_authoring_regression.py) is byte-identical;",
        "# tests/test_authoring_regression.py fails on ANY drift from these hashes.",
        "# Any prompt or model change re-runs the full set (spec s5, frozen).",
        "",
        "set_version: authoring-regression-1.0",
        f"payload_count: {len(entries)}",
        "ship_gate_first_pass: 0.95",
        "payloads:",
    ]
    for payload_id, digest in sorted(entries):
        lines.append(f"  {payload_id}: sha256:{digest}")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(entries)} payloads + manifest (set authoring-regression-1.0)")


if __name__ == "__main__":
    main()
