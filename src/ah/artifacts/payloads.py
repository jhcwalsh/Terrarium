"""Tier-2 payload builders (WP4.4) — deterministic code, never an LLM.

P-LETTER and P-NOTE per the vendored authoring spec §2, verbatim in
structure: every figure pre-formatted to publication precision so the
author copies rather than computes, arc beats STRIPPED at the dateline
(nothing ahead of it ever reaches a prompt — principle 1), and the
``checkable_claims_table`` built here is the single source of truth the
G1 gate checks every number against.
"""

from __future__ import annotations

from typing import Any

from ah.artifacts.templates import fmt_level_pct, fmt_money, fmt_pct


class PayloadError(ValueError):
    """An input the payload builder refuses."""


def _beats_to_date(entity: dict[str, Any], dateline_quarter: int) -> list[str]:
    """Arc beats with from_quarter <= dateline ONLY — the strip is here,
    before any prompt exists, so a leak upstream is structurally impossible."""
    return [
        f"Q{b['from_quarter']}: {b['beat']}"
        for b in entity.get("arc", [])
        if b["from_quarter"] <= dateline_quarter
    ]


def build_p_letter(
    *,
    entity: dict[str, Any],
    dateline: str,
    dateline_quarter: int,
    quarter_label: str,
    reported_return_q: float,
    reported_return_ytd: float,
    reported_return_si: float,
    nav_index: float,
    distributions_flag: bool,
    calls_flag: bool,
    gate_status: str,
    secondary_market_context: str,
    public_equity_q: float,
    hy_spread_now_bps: float,
    policy_rate_now: float,
    cpi_now: float,
    chronicle_extracts: list[str],
) -> dict[str, Any]:
    """The manager-letter payload: facts frozen, claims table authoritative."""
    if not entity.get("held_by_institution") and not str(entity.get("kind", "")).startswith(
        ("gp_", "direct_lender")
    ):
        raise PayloadError("P-LETTER is for held or GP/lender cast entities (spec s2)")
    claims = {
        "reported_return_q": fmt_pct(reported_return_q),
        "reported_return_ytd": fmt_pct(reported_return_ytd),
        "reported_return_si": fmt_pct(reported_return_si),
        "nav_index": f"{nav_index:.1f}",
        "public_equity_q": fmt_pct(public_equity_q),
        "hy_spread_now_bps": f"{hy_spread_now_bps:.0f}bps",
        "policy_rate_now": fmt_level_pct(policy_rate_now, 2),
        "cpi_now": fmt_level_pct(cpi_now, 1),
    }
    comp_gap = abs(reported_return_q - public_equity_q)
    return {
        "artifact_type": "letterhead",
        "dateline": dateline,
        "dateline_quarter": dateline_quarter,
        "quarter_label": quarter_label,
        "entity": {
            "id": entity["id"],
            "name": entity["name"],
            "kind": entity["kind"],
            "one_liner": entity["profile"]["one_liner"],
            "signature_traits": list(entity["profile"].get("signature_traits", [])),
            "voice": entity["voice"],
            "relationships": [r["with"] for r in entity.get("relationships", [])],
        },
        "arc_beats_to_date": _beats_to_date(entity, dateline_quarter),
        "fund_facts": {
            "gate_status": gate_status,
            "distributions_flag": distributions_flag,
            "calls_flag": calls_flag,
            "secondary_market_context": secondary_market_context,
        },
        "comp_gap_exceeds_3pts": bool(comp_gap > 0.03),
        "chronicle_extracts": list(chronicle_extracts[-6:]),
        "checkable_claims_table": claims,
    }


def build_p_note(
    *,
    house: dict[str, Any],
    rival_stance_summary: str,
    subject: str,
    dateline: str,
    dateline_quarter: int,
    ytd_return: float,
    one_year_return: float,
    drawdown: float,
    hy_spread_now_bps: float,
    policy_rate_now: float,
    cpi_now: float,
    reported_vs_public_gap: float | None,
    chronicle_extracts: list[str],
) -> dict[str, Any]:
    """The research-note payload; generated as a pair, one call per house."""
    claims = {
        "ytd_return": fmt_pct(ytd_return),
        "one_year_return": fmt_pct(one_year_return),
        "drawdown": fmt_pct(drawdown),
        "hy_spread_now_bps": f"{hy_spread_now_bps:.0f}bps",
        "policy_rate_now": fmt_level_pct(policy_rate_now, 2),
        "cpi_now": fmt_level_pct(cpi_now, 1),
    }
    if reported_vs_public_gap is not None:
        claims["reported_vs_public_gap"] = fmt_pct(reported_vs_public_gap)
    return {
        "artifact_type": "wire_item",
        "dateline": dateline,
        "dateline_quarter": dateline_quarter,
        "house": {
            "id": house["id"],
            "name": house["name"],
            "prior": house["prior"],
            "voice": house["voice"],
            "coverage": list(house.get("coverage", [])),
        },
        "subject": subject,
        "rival_stance_summary": rival_stance_summary,
        "chronicle_extracts": list(chronicle_extracts[-8:]),
        "checkable_claims_table": claims,
    }


def fmt_claims_for_prompt(claims: dict[str, str]) -> str:
    """The claims table as the prompt shows it — one `key: value` per line,
    sorted, so the same facts always render identically."""
    return "\n".join(f"{k}: {v}" for k, v in sorted(claims.items()))


__all__ = [
    "PayloadError",
    "build_p_letter",
    "build_p_note",
    "fmt_claims_for_prompt",
    "fmt_money",
]
