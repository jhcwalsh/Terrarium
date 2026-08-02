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

#: Pipeline v2 (AM-2026-08-02-004, owner-ratified): an optional SELF-CHECK
#: call executes inside the production of each submitted draft — the model
#: reviews its own draft against the hard rules before submission. The
#: external gate still judges each submission exactly once; the frozen
#: threshold is unchanged; "first-pass" means gate-passed on the first
#: SUBMISSION, per the ratified definition.
PIPELINE_V1 = "author-pipeline/1.0"
PIPELINE_V2 = "author-pipeline/2.0"
# 1.1: preserve-structure rules (run 13: the checker, told "body only",
# stripped a note's rating line it was never told to keep) and the check
# is now an explicit act-on-each-rule checklist.
SELF_CHECK_PROMPT_VERSION = "self-check@1.1"

SELF_CHECK_PROMPT = """\
Review the draft below against these rules. If it violates any rule, output
the corrected draft; if it is compliant, output it unchanged. Output the
draft body ONLY - no commentary, no preamble.

RULES:
- Every number must match the facts table character-for-character; no digit
  may appear that is not in the facts table.
- No promise words in any form: guarantee, assure, will deliver.
- The outlook must contain at least one cautious word (may / could / risk /
  watch / prudent).
- Name only the allowed entities; real institutions by role only ("the
  central bank"), never by name.
- No references beyond the dateline; no events the newsflow does not report.

FACTS TABLE (the only permitted numbers):
{claims}

DRAFT:
{draft}
"""


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
    pipeline_version: str = PIPELINE_V1


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
    self_check: AuthorFn | None = None,
) -> AuthoringResult:
    """Render the prompt, author, gate; retry twice; then fall back.

    ``self_check`` (pipeline v2, AM-2026-08-02-004): when supplied, every
    draft passes through one self-review call before submission — inside
    the production of the submitted draft, per the ratified definition.
    """
    prompt_version = PROMPT_VERSIONS[kind]
    pipeline_version = PIPELINE_V2 if self_check is not None else PIPELINE_V1
    base_prompt = render_prompt(kind, payload, allowed_entities=allowed_entities)
    prompt = base_prompt
    last_report = GateReport()
    for attempt in range(MAX_RETRIES + 1):
        draft = author(prompt)
        if self_check is not None:
            draft = self_check(
                SELF_CHECK_PROMPT.format(
                    claims=fmt_claims_for_prompt(payload["checkable_claims_table"]),
                    draft=draft,
                )
            )
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
                pipeline_version=pipeline_version,
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
        pipeline_version=pipeline_version,
    )
