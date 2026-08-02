"""The Tier-2 authoring pipeline (WP4.4) — author, gate, retry, fall back.

The frozen retry rule (G4-pre): a blocked draft goes back to the author
with the violations attached, at most TWO retries, then the artifact
falls back to a Tier-1 templated substitute — boring but honest beats
fluent but wrong. The author itself is an injected callable
``(prompt) -> str``: tests use recorded or synthetic authors (no network
— pytest-socket enforces), live authoring wires the Anthropic API behind
an explicit ``--live`` flag exactly like the Step 0 compiler harness.

Every result carries what G9 will record: prompt version, model id, gate
result, retry count. Determinism note: with a deterministic author the
whole pipeline is deterministic; with a live model it is not, which is
WHY the chronicle records the artifact rather than pretending to replay
it — replay reproduces the identical artifact SEQUENCE from the
chronicle, not from re-prompting (plan DoD 3).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from ah.artifacts.gate import GateReport, run_gate
from ah.artifacts.payloads import fmt_claims_for_prompt
from ah.artifacts.prompts import PROMPT_VERSIONS, render_prompt

MAX_RETRIES = 2  # frozen: two retries, then Tier-1 fallback


class AuthorFn(Protocol):
    def __call__(self, prompt: str) -> str: ...


@dataclass
class AuthoringResult:
    text: str
    gate_result: str  # pass | fallback
    gate_report: GateReport
    retry_count: int
    prompt_version: str
    model_id: str
    author_tier: int


def tier1_fallback_text(payload: dict[str, Any]) -> str:
    """The deterministic substitute: the facts, plainly, nothing else."""
    claims = fmt_claims_for_prompt(payload["checkable_claims_table"])
    subject = payload.get("entity", {}).get("name") or payload.get("subject", "the subject")
    return (
        f"[Tier-1 substitute] Quarterly summary for {subject}, {payload['dateline']}.\n"
        f"{claims}\n"
        "A generated letter did not clear the consistency gate; the facts above "
        "are published without commentary."
    )


def author_artifact(
    kind: str,
    payload: dict[str, Any],
    *,
    author: AuthorFn,
    model_id: str,
    allowed_entities: list[str],
    generic_allowlist: list[str],
    past_artifacts: list[str] | None = None,
    fog: dict[str, Any] | None = None,
    on_retry: Callable[[int, GateReport], None] | None = None,
) -> AuthoringResult:
    """Render the prompt, author, gate; retry twice; then fall back."""
    prompt_version = PROMPT_VERSIONS[kind]
    base_prompt = render_prompt(kind, payload, allowed_entities=allowed_entities)
    prompt = base_prompt
    last_report = GateReport()
    for attempt in range(MAX_RETRIES + 1):
        draft = author(prompt)
        report = run_gate(
            draft,
            payload,
            allowed_entities=allowed_entities,
            generic_allowlist=generic_allowlist,
            is_note=(kind == "note"),
            past_artifacts=past_artifacts,
            fog=fog,
        )
        if not report.blocked:
            return AuthoringResult(
                text=draft,
                gate_result="pass",
                gate_report=report,
                retry_count=attempt,
                prompt_version=prompt_version,
                model_id=model_id,
                author_tier=2,
            )
        last_report = report
        if on_retry is not None:
            on_retry(attempt, report)
        violations = "\n".join(f"- {v['rule']}: {v['message']}" for v in report.violations)
        prompt = (
            base_prompt
            + "\n\nYOUR PREVIOUS DRAFT WAS REJECTED by the consistency gate. "
            + "Violations to fix, changing nothing else:\n"
            + violations
        )
    return AuthoringResult(
        text=tier1_fallback_text(payload),
        gate_result="fallback",
        gate_report=last_report,
        retry_count=MAX_RETRIES,
        prompt_version=prompt_version,
        model_id=model_id,
        author_tier=1,  # the substitute is Tier-1 authorship, recorded as such
    )
