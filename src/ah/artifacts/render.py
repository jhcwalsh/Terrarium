"""Renderers per artifact type (WP4.1) — watermark in the renderer, always.

Five type-shaped skeletons (the Tier-1 template CONTENT is WP4.2's; what
lives here is the frame every artifact shares): deterministic text out of a
payload dict, with the simulated-world marking applied IN the renderer —
not the style guide — and re-applied on export, exactly as the plan's
pitfall list demands ("a fictional front page that could screenshot as
real"). Payload hashing is canonical-JSON SHA-256 via the Step 0 digest
module, so the same payload always hashes identically regardless of key
order.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ah.core.digest import canonical_json

WATERMARK_BANNER = "=== SIMULATED WORLD -- FICTIONAL -- NOT INVESTMENT ADVICE ==="
WATERMARK_FOOTER = "--- Simulated artifact. All entities fictional. Not investment advice. ---"


class RenderError(ValueError):
    """A payload the renderer refuses."""


def payload_hash(payload: dict[str, Any]) -> str:
    """Canonical-JSON SHA-256 of the payload — key order never matters."""
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _frame(world_id: str, dateline: str, title: str, body_lines: list[str]) -> str:
    """The shared frame: banner, masthead line, body, footer."""
    lines = [
        WATERMARK_BANNER,
        f"[{world_id}] {dateline}",
        "",
        title,
        "",
        *body_lines,
        "",
        WATERMARK_FOOTER,
    ]
    return "\n".join(lines)


def _require(payload: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if k not in payload]
    if missing:
        raise RenderError(f"payload missing {missing}")


def render_wire_item(payload: dict[str, Any]) -> str:
    _require(payload, "world_id", "dateline", "headline", "body")
    return _frame(payload["world_id"], payload["dateline"], payload["headline"], [payload["body"]])


def render_release_page(payload: dict[str, Any]) -> str:
    """A data-release page: rows of (series, value, prior, revision)."""
    _require(payload, "world_id", "dateline", "release_name", "rows")
    body = ["| series | value | prior | revision |", "|---|---|---|---|"]
    for row in payload["rows"]:
        body.append(
            f"| {row['series']} | {row['value']} | {row['prior']} | {row.get('revision', '')} |"
        )
    return _frame(payload["world_id"], payload["dateline"], payload["release_name"], body)


def render_statement(payload: dict[str, Any]) -> str:
    _require(payload, "world_id", "dateline", "title", "lines")
    return _frame(
        payload["world_id"], payload["dateline"], payload["title"], list(payload["lines"])
    )


def render_letterhead(payload: dict[str, Any]) -> str:
    """The frame a Tier-2 letter body is set into (the body arrives gated)."""
    _require(payload, "world_id", "dateline", "entity_name", "body")
    return _frame(
        payload["world_id"],
        payload["dateline"],
        f"{payload['entity_name']} -- Quarterly Letter",
        [payload["body"]],
    )


def render_board_pack(payload: dict[str, Any]) -> str:
    _require(payload, "world_id", "dateline", "sections")
    body: list[str] = []
    for section in payload["sections"]:
        body += [f"## {section['title']}", *section["lines"], ""]
    return _frame(payload["world_id"], payload["dateline"], "Board Pack", body)


RENDERERS = {
    "wire_item": render_wire_item,
    "release_page": render_release_page,
    "statement": render_statement,
    "letterhead": render_letterhead,
    "board_pack": render_board_pack,
}


def render(artifact_type: str, payload: dict[str, Any]) -> str:
    if artifact_type not in RENDERERS:
        raise RenderError(f"no renderer for artifact_type '{artifact_type}'")
    return RENDERERS[artifact_type](payload)


def export(text: str) -> str:
    """Re-apply the marking at the export boundary.

    Idempotent: an already-marked artifact passes through unchanged; a
    stripped one (whatever removed it) leaves marked. Export paths call
    this LAST, after any transformation.
    """
    out = text
    if WATERMARK_BANNER not in out:
        out = WATERMARK_BANNER + "\n" + out
    if WATERMARK_FOOTER not in out:
        out = out + "\n" + WATERMARK_FOOTER
    return out
