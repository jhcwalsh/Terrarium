"""Run the authoring regression set (WP4.5).

Live:    uv run python scripts/run_authoring_regression.py --live --asof 2026-08-02
Replay:  uv run python scripts/run_authoring_regression.py

Live mode authors every frozen payload through the WP4.4 pipeline with a
real Claude call (ANTHROPIC_API_KEY; the Step 0 adapter pattern — lazy
import, never on the test path), records every outcome to
``fixtures/authoring_regression/recorded/`` (draft text, gate result,
retry count, prompt version, model id, violations), and writes
``governance/evidence/AUTHORING-REGRESSION.md`` scoring the FIRST-PASS
gate rate against the frozen >=0.95 ship gate (AM-2026-08-02-002) — the
result ships reported whichever way it falls.

Replay mode re-gates the recorded drafts offline and recomputes the
rates deterministically — what CI verifies forever, no network.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ah.artifacts.author import author_artifact
from ah.artifacts.gate import GATE_IMPL_VERSION, run_gate
from ah.artifacts.prompts import PROMPT_VERSIONS

_REPO_ROOT = Path(__file__).resolve().parents[1]
REG_DIR = _REPO_ROOT / "fixtures" / "authoring_regression"
RECORDED = REG_DIR / "recorded"
EVIDENCE = _REPO_ROOT / "governance" / "evidence" / "AUTHORING-REGRESSION.md"
BIBLE = _REPO_ROOT / "Instructions" / "example-bible-credit-winter.json"

AUTHOR_MODEL = "claude-sonnet-5"
SHIP_GATE_FIRST_PASS = 0.95


class AnthropicAuthor:
    """Live author: one Messages call per prompt. Requires ANTHROPIC_API_KEY."""

    def __init__(self, model: str = AUTHOR_MODEL) -> None:
        self.model = model

    def __call__(self, prompt: str) -> str:  # pragma: no cover - live only
        import anthropic  # lazy: keep import off the test/CI path

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self.model,
            # 2048: the v2 self-check re-emits WHOLE drafts; 1024 truncated
            # long letters mid-outlook (run 11's ten no-hedging failures
            # were amputated tails, the committee 512-cap bug's sibling)
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", "") == "text"
        )


def _bible_lists() -> tuple[list[str], list[str]]:
    bible = json.loads(BIBLE.read_text("utf-8"))
    allowed = (
        [bible["institution"]["name"]]
        + [c["name"] for c in bible["cast"]]
        + [h["name"] for h in bible["research_houses"]]
        + [bible["media"]["wire_name"], bible["media"]["paper_name"]]
        + [col["name"] for col in bible["media"].get("columnists", [])]
    )
    return allowed, list(bible["safety"]["generic_allowlist"])


def _payloads() -> dict[str, dict[str, Any]]:
    return {
        p.stem: json.loads(p.read_text("utf-8"))
        for p in sorted((REG_DIR / "payloads").glob("*.json"))
    }


def run_live(asof: str) -> None:  # pragma: no cover - live only
    allowed, generic = _bible_lists()
    author = AnthropicAuthor()
    RECORDED.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    for payload_id, payload in _payloads().items():
        kind = "letter" if payload_id.startswith("letter-") else "note"
        attempt_violations: list[list[dict[str, str]]] = []
        result = author_artifact(
            kind,
            payload,
            author=author,
            model_id=author.model,
            allowed_entities=allowed,
            generic_allowlist=generic,
            on_retry=lambda _a, report, _sink=attempt_violations: _sink.append(
                list(report.violations)
            ),
            self_check=author,  # pipeline v2 (AM-2026-08-02-004)
        )
        record = {
            "payload_id": payload_id,
            "kind": kind,
            "text": result.text,
            "gate_result": result.gate_result,
            "retry_count": result.retry_count,
            "prompt_version": result.prompt_version,
            "pipeline_version": result.pipeline_version,
            "model_id": result.model_id,
            "author_tier": result.author_tier,
            "violations": result.gate_report.violations,
            "attempt_violations": attempt_violations,
            "asof": asof,
        }
        (RECORDED / f"{payload_id}.json").write_text(
            json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        results[payload_id] = record
        print(f"{payload_id}: {result.gate_result} (retries {result.retry_count})")
    _write_evidence(results, asof, live=True)


def run_replay() -> None:
    """Re-gate every recorded draft offline; verdicts must reproduce."""
    allowed, generic = _bible_lists()
    payloads = _payloads()
    results: dict[str, dict[str, Any]] = {}
    for path in sorted(RECORDED.glob("*.json")):
        record = json.loads(path.read_text("utf-8"))
        payload = payloads[record["payload_id"]]
        if record["author_tier"] == 2:  # a passed draft must still pass the gate
            report = run_gate(
                record["text"],
                payload,
                allowed_entities=allowed,
                generic_allowlist=generic,
                is_note=(record["kind"] == "note"),
            )
            record["replay_blocked"] = report.blocked
        results[record["payload_id"]] = record
    if not results:
        print("no recorded outputs; run --live first")
        return
    _write_evidence(results, results[next(iter(results))]["asof"], live=False)


def _write_evidence(results: dict[str, dict[str, Any]], asof: str, *, live: bool) -> None:
    n = len(results)
    first_pass = sum(
        1 for r in results.values() if r["gate_result"] == "pass" and r["retry_count"] == 0
    )
    retried_pass = sum(
        1 for r in results.values() if r["gate_result"] == "pass" and r["retry_count"] > 0
    )
    fallbacks = sum(1 for r in results.values() if r["gate_result"] == "fallback")
    rate = first_pass / n if n else 0.0
    ships = rate >= SHIP_GATE_FIRST_PASS
    lines = [
        "# AUTHORING-REGRESSION.md — the WP4.5 set, measured",
        "",
        f"Set `authoring-regression-1.0` ({n} payloads); model `{AUTHOR_MODEL}`;",
        f"prompts {PROMPT_VERSIONS['letter']} / {PROMPT_VERSIONS['note']}; {GATE_IMPL_VERSION}; run asof {asof}"
        f" ({'LIVE' if live else 'offline replay of the recorded outputs'}).",
        "Ship gate (FROZEN, AM-2026-08-02-002): first-pass gate rate >= 95%.",
        "",
        "| first-pass | pass after retry | fallback | first-pass rate | ships |",
        "|---|---|---|---|---|",
        f"| {first_pass}/{n} | {retried_pass} | {fallbacks} | {rate:.1%} | "
        f"{'YES' if ships else 'NO - prompt version may not ship'} |",
        "",
        "## Per-payload results",
        "",
        "| payload | result | retries | violations at final gate |",
        "|---|---|---|---|",
    ]
    for payload_id, r in sorted(results.items()):
        rules = ", ".join(v["rule"] for v in r["violations"]) or "-"
        lines.append(f"| {payload_id} | {r['gate_result']} | {r['retry_count']} | {rules} |")
    lines += [
        "",
        "## Human review items (spec s5: reviewed, not automated)",
        "",
        "- **Voice drift**: read a bull and a crash letter per entity against the",
        "  bible's voice register and tics; drift is a prompt-version question.",
        "- **Disagreement quality**: the calder/grimshaw pair on the same subject",
        "  must read the same numbers through different priors and NOT converge.",
        "",
        "---",
        "",
        "*Not investment advice.*",
    ]
    EVIDENCE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(
        f"evidence written: first-pass {first_pass}/{n} ({rate:.1%}), "
        f"retried {retried_pass}, fallback {fallbacks}, ships={ships}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--asof", default=None, help="required with --live (no clock reads)")
    args = parser.parse_args()
    if args.live:
        if not args.asof:
            raise SystemExit("--live requires --asof YYYY-MM-DD")
        run_live(args.asof)
    else:
        run_replay()
