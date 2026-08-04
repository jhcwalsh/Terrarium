"""Tier-1 templates (WP4.2) — rule-generated from the tape, zero marginal cost.

Every builder here is a pure function of tape-shaped inputs to a renderer
payload (WP4.1's frame applies the watermark). No LLM, no RNG, no clock:
the same tape always produces the same words. Numbers are pre-formatted to
publication precision by the ``fmt_*`` helpers so any downstream author —
including Tier-2's — copies rather than computes (the G1 discipline,
inherited by construction).

Amendment A1 Delta 2 lands here: the cashflow event classes (capital call,
distribution, coverage-band crossing, forced sale, secondary discount).
Editorial rule, from the delta verbatim: cashflow events report the **cash
account**, not the reported plane — the wire already distinguishes reported
and true marks; the cash account is the third voice, and it is the honest
one. The forced-sale item is the loudest artifact in the product and reads
like the distress event it is.
"""

from __future__ import annotations

from typing import Any


class TemplateError(ValueError):
    """An input the template refuses to typeset."""


# -- publication-precision formatting (authors copy, code computes) --------- #


def fmt_pct(x: float, decimals: int = 1) -> str:
    return f"{x * 100:+.{decimals}f}%"


def fmt_level_pct(x: float, decimals: int = 1) -> str:
    return f"{x * 100:.{decimals}f}%"


def fmt_money(x: float) -> str:
    return f"{x:,.1f}"


# -- the wire: cashflow event classes (Delta 2) ----------------------------- #


def capital_call_event(
    *, world_id: str, dateline: str, sleeve: str, amount: float
) -> dict[str, Any]:
    return {
        "world_id": world_id,
        "dateline": dateline,
        "headline": f"Capital call: {sleeve} draws {fmt_money(amount)}",
        "body": (
            f"The cash account paid {fmt_money(amount)} against {sleeve}'s "
            "unfunded commitment at today's dealing."
        ),
    }


def distribution_event(
    *, world_id: str, dateline: str, sleeve: str, amount: float
) -> dict[str, Any]:
    return {
        "world_id": world_id,
        "dateline": dateline,
        "headline": f"Distribution received: {sleeve} returns {fmt_money(amount)}",
        "body": (
            f"The cash account received {fmt_money(amount)} from {sleeve}. "
            "Distributions settle in cash; reported marks are unaffected."
        ),
    }


def coverage_band_event(
    *,
    world_id: str,
    dateline: str,
    coverage: float,
    band_edge: float,
    direction: str,
) -> dict[str, Any]:
    if direction not in ("above", "below"):
        raise TemplateError("direction must be 'above' or 'below'")
    return {
        "world_id": world_id,
        "dateline": dateline,
        "headline": (
            f"Coverage crosses {direction} {fmt_level_pct(band_edge)}: "
            f"now {fmt_level_pct(coverage)}"
        ),
        "body": (
            f"Unfunded commitments stand at {fmt_level_pct(coverage)} of liquid "
            f"assets, crossing {direction} the {fmt_level_pct(band_edge)} policy "
            "band. Coverage is measured against the cash account and liquid "
            "sleeves — the ratio that determines whether the institution becomes "
            "a forced seller."
        ),
    }


def forced_sale_event(
    *,
    world_id: str,
    dateline: str,
    amount: float,
    cause: str,
    sleeves_sold: list[str],
    kind: str,
    haircut: float | None = None,
) -> dict[str, Any]:
    """The loudest artifact in the product. It reads like what it is."""
    if not sleeves_sold:
        raise TemplateError("a forced sale names the sleeves sold")
    if kind == "forced_secondary" and haircut is None:
        raise TemplateError("a forced secondary states its haircut")
    sold = ", ".join(sleeves_sold)
    if kind == "forced_secondary":
        assert haircut is not None
        detail = (
            f"Interests in {sold} were sold on the secondary market at "
            f"{fmt_level_pct(1.0 - haircut)} of carrying value — a "
            f"{fmt_level_pct(haircut)} discount taken to raise cash that was "
            "not otherwise there."
        )
    else:
        detail = f"Liquid holdings in {sold} were sold pro-rata to cover the shortfall."
    return {
        "world_id": world_id,
        "dateline": dateline,
        "headline": f"FORCED SALE: {fmt_money(amount)} raised — {cause}",
        "body": (
            f"The cash account could not meet its obligations. {detail} "
            "Forced sales are recorded events, not footnotes: cause, amount, "
            "and sleeves sold are on the chronicle."
        ),
    }


def secondary_discount_event(
    *, world_id: str, dateline: str, sleeve: str, price_pct_nav: float
) -> dict[str, Any]:
    return {
        "world_id": world_id,
        "dateline": dateline,
        "headline": (
            f"Secondary market: {sleeve} interests quoted at {fmt_level_pct(price_pct_nav)} of NAV"
        ),
        "body": (
            f"Secondary buyers are pricing {sleeve} exposure at "
            f"{fmt_level_pct(price_pct_nav)} of reported carrying value. The gap "
            "between the reported mark and the clearing price is information the "
            "reported plane does not carry."
        ),
    }


# -- the daily/monthly furniture ------------------------------------------- #


def morning_digest(*, world_id: str, dateline: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """The digest: everything that is not a push notification lands here."""
    lines = [f"- {item['headline']}" for item in items] or ["- (a quiet session)"]
    return {
        "world_id": world_id,
        "dateline": dateline,
        "title": f"Morning digest — {dateline}",
        "lines": lines,
    }


def release_page(
    *,
    world_id: str,
    dateline: str,
    release_name: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """A data release: value, prior, and revision — the revision is content."""
    for row in rows:
        missing = {"series", "value", "prior"} - set(row)
        if missing:
            raise TemplateError(f"release row missing {sorted(missing)}")
    return {
        "world_id": world_id,
        "dateline": dateline,
        "release_name": release_name,
        "rows": [
            {
                "series": r["series"],
                "value": r["value"],
                "prior": r["prior"],
                "revision": r.get("revision", ""),
            }
            for r in rows
        ],
    }


_CB_STANCE = {
    "hike": "The committee judges that upside risks to inflation warrant firmer policy.",
    "hold": "The committee judges current policy appropriately calibrated to the outlook.",
    "cut": "The committee judges that the balance of risks has shifted toward activity.",
}


def central_bank_statement(
    *,
    world_id: str,
    dateline: str,
    policy_rate: float,
    previous_rate: float,
) -> dict[str, Any]:
    """Deterministic stance language keyed on the tape — no RNG, no adjectives.

    The toy engine's policy rate is a continuous drift, not a sequence of
    meeting-quantized decisions — so the statement narrates how conditions
    MOVED over the quarter and where the rate stands, and never announces a
    discrete "raised by X" decision that no committee took (found live: a
    0.07% "hike" reads as a bug, because it is one). Moves under 5bp read as
    little changed. Discrete 25bp policy decisions are a realism requirement
    recorded for the post-G2 engine, not something to fake in narration.
    """
    move = policy_rate - previous_rate
    bp = round(abs(move) * 10000)
    if bp < 5:
        action = "hold"
        first = (
            f"The policy rate stands at {fmt_level_pct(policy_rate, 2)}, "
            "little changed over the quarter."
        )
    else:
        action = "hike" if move > 0 else "cut"
        verb = "tightened" if move > 0 else "eased"
        direction = "up" if move > 0 else "down"
        first = (
            f"Policy conditions {verb} over the quarter; the rate stands at "
            f"{fmt_level_pct(policy_rate, 2)} ({direction} {bp}bp)."
        )
    return {
        "world_id": world_id,
        "dateline": dateline,
        "title": "Statement on monetary policy",
        "lines": [first, _CB_STANCE[action]],
    }


def newspaper_front_page(
    *,
    world_id: str,
    dateline: str,
    lead: str,
    stories: list[str] | None = None,
    masthead: str = "THE MARKET RECORD",
) -> dict[str, Any]:
    """The economic backdrop, as the world's press reports it.

    Owner's ask after the second live-play round: the player needs context,
    not just instrument prices. This is the cheapest honest way to give it —
    a front page whose every line is keyed to something the tape actually
    did (a threshold crossed, a regime opening), rule-generated like every
    other Tier-1 artifact. No LLM, no RNG, no clock: same tape, same paper.

    A front page with no lead is not a front page; a quiet month simply gets
    no edition, which is itself information.
    """
    if not lead.strip():
        raise TemplateError("a front page needs a lead story")
    return {
        "world_id": world_id,
        "dateline": dateline,
        "title": f"{masthead} — {dateline}",
        "lines": [lead, *(stories or [])],
    }


# -- the institution's own paper ------------------------------------------- #


def _percentile_from_bands(value: float, band_quantiles: dict[str, float]) -> str:
    """Which ensemble band a value falls in — computed, never authored.

    ``band_quantiles`` maps quantile labels ('p5', 'p25', 'p50', 'p75',
    'p95') to values, as precomputed from the full ensemble at world build.
    """
    required = ("p5", "p25", "p50", "p75", "p95")
    if any(k not in band_quantiles for k in required):
        raise TemplateError(f"band_quantiles must carry {required}")
    edges = [band_quantiles[k] for k in required]
    if edges != sorted(edges):
        raise TemplateError("band quantiles must be monotone")
    if value < edges[0]:
        return "below the 5th percentile of peers"
    if value > edges[4]:
        return "above the 95th percentile of peers"
    labels = [
        "in the bottom quartile of peers (5th-25th percentile)",
        "below the peer median (25th-50th percentile)",
        "above the peer median (50th-75th percentile)",
        "in the top quartile of peers (75th-95th percentile)",
    ]
    for hi, label in zip(edges[1:], labels, strict=True):
        if value <= hi:
            return label
    raise AssertionError("unreachable")


def quarterly_statement(
    *,
    world_id: str,
    dateline: str,
    quarter_label: str,
    return_q: float,
    return_ytd: float,
    total_value: float,
    net_flow: float,
    peer_bands: dict[str, float],
) -> dict[str, Any]:
    return {
        "world_id": world_id,
        "dateline": dateline,
        "title": f"Quarterly statement — {quarter_label}",
        "lines": [
            f"Return for the quarter: {fmt_pct(return_q)} ({_percentile_from_bands(return_q, peer_bands)}).",
            f"Year to date: {fmt_pct(return_ytd)}.",
            f"Total value: {fmt_money(total_value)}.",
            f"Net flow for the quarter: {fmt_money(net_flow)}.",
            "Peer comparison is derived from the world ensemble at build time.",
        ],
    }


BOARD_PACK_SECTIONS = (
    "performance",
    "allocation",
    "liquidity",
    "wire_digest",
    "consultant_recommendation",
)


def board_pack(
    *,
    world_id: str,
    dateline: str,
    performance: list[str],
    allocation: list[str],
    liquidity: list[str],
    wire_digest: list[str],
    consultant_recommendation: list[str],
) -> dict[str, Any]:
    """Auto-assembled two world-weeks before each decision window (the slot
    offset lives in the calendar entry). All five sections, always — a board
    pack with a section quietly missing is how a decision gets made on
    partial information."""
    sections = {
        "performance": performance,
        "allocation": allocation,
        "liquidity": liquidity,
        "wire_digest": wire_digest,
        "consultant_recommendation": consultant_recommendation,
    }
    empty = [name for name, lines in sections.items() if not lines]
    if empty:
        raise TemplateError(f"board pack sections empty: {empty}")
    titles = {
        "performance": "Performance",
        "allocation": "Allocation vs policy ranges",
        "liquidity": "Liquidity position",
        "wire_digest": "The quarter on the wire",
        "consultant_recommendation": "Consultant recommendation",
    }
    return {
        "world_id": world_id,
        "dateline": dateline,
        "sections": [
            {"title": titles[name], "lines": sections[name]} for name in BOARD_PACK_SECTIONS
        ],
    }
