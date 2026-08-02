"""Run the WP4.9 actor validation study.

Offline:  uv run python scripts/run_actor_validation.py
Live:     uv run python scripts/run_actor_validation.py --live --asof 2026-08-02

Offline runs the ablation arms (deterministic, seeded) across N synthetic
study worlds. Live adds the Claude committee across three personas on the
SAME worlds and windows. Writes governance/evidence/ACTOR-VALIDATION.md
with the pathology measurements the plan names, the deferred human-cohort
arm stated per the owner's D-K4-5 decision, and the standing rule
restated: no client-facing actor claim precedes the full study.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ah.artifacts import committee as com
from ah.artifacts import validation as val

_REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = _REPO_ROOT / "governance" / "evidence" / "ACTOR-VALIDATION.md"
RECORDED = _REPO_ROOT / "fixtures" / "actor_validation"

N_WORLDS = 6
WORLD_SEEDS = tuple(1000 + 7919 * k for k in range(N_WORLDS))
COMMITTEE_MODEL = "claude-sonnet-5"
PERSONAS = [
    com.Persona("steady", "disciplined, contrarian only with evidence"),
    com.Persona("momentum", "trend-respecting; adds to what is working"),
    com.Persona("preserver", "capital preservation first; hates drawdowns"),
]


def _study_tape(seed: int) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(seed))
    return rng.normal(0.004, 0.035, size=(36, 3))


def main(live: bool, asof: str | None) -> None:
    records: list[val.DecisionRecord] = []
    for seed in WORLD_SEEDS:
        records.extend(val.run_ablation_arms(_study_tape(seed), world_seed=seed))

    live_note = "NOT RUN (offline invocation)"
    if live:  # pragma: no cover - live only

        def decider(prompt: str) -> str:  # the Step 0 adapter pattern, lazy import
            import anthropic

            client = anthropic.Anthropic()
            message = client.messages.create(
                model=COMMITTEE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(
                getattr(b, "text", "") for b in message.content if getattr(b, "type", "") == "text"
            )

        for seed in WORLD_SEEDS:
            records.extend(
                val.run_model_arm(
                    _study_tape(seed),
                    world_seed=seed,
                    personas=PERSONAS,
                    decider=decider,
                    model_id=COMMITTEE_MODEL,
                )
            )
        live_note = f"run asof {asof}, model {COMMITTEE_MODEL}, 3 personas"
        RECORDED.mkdir(parents=True, exist_ok=True)
        (RECORDED / "decision_records.json").write_text(
            json.dumps([r.__dict__ for r in records], indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    rates = val.action_rates(records)
    heuristic_vs_hold = val.effect_size_with_dispersion(records, "heuristic", "hold_course")
    lines = [
        "# ACTOR-VALIDATION.md — the WP4.9 study, run and deferred honestly",
        "",
        f"Worlds: {len(WORLD_SEEDS)} synthetic study decades (seeded {WORLD_SEEDS[0]}..),",
        "identical worlds/windows for every arm (the sealed comparison rule).",
        f"Ablation arms: {', '.join(val.DECIDER_ARMS)}. Model arm: {live_note}.",
        "",
        "## Action rates by arm (action-level fidelity, base measure)",
        "",
        "| arm | acted in fraction of windows |",
        "|---|---|",
        *[f"| {arm} | {rate:.2f} |" for arm, rate in rates.items()],
        "",
        "## Effect size WITH dispersion (the anti-inflation rule, mechanical)",
        "",
        f"heuristic vs hold_course action-rate difference: mean "
        f"{heuristic_vs_hold['mean_diff']:+.2f}, sd across worlds "
        f"{heuristic_vs_hold['sd_across_worlds']:.2f}, n={heuristic_vs_hold['n_worlds']:.0f}."
        " No mean travels without its dispersion and world count.",
    ]
    if live:  # pragma: no cover - live only
        fb = val.fallback_rate(records)
        ps = val.persona_sensitivity(records)
        lines += [
            "",
            "## Model-arm pathologies (measured)",
            "",
            f"- **Action-level fidelity**: fallback rate {fb:.2f} — fraction of",
            "  committee decisions rejected by the bounded contract and replaced",
            "  by the heuristic, with the rejection filed in the rationale.",
            f"- **Persona/prompt sensitivity**: {ps:.2f} of (world, window) cells",
            "  show persona disagreement (differing action counts or targets >1pt",
            "  apart). Reported as PROMPT SENSITIVITY, per the plan's pitfall list",
            "  — persona differences are measured, not sold as insight.",
        ]
    lines += [
        "",
        "## Deferred, by owner decision D-K4-5 (kickoff, 2026-08-01)",
        "",
        "- **The human-cohort arm**: the owner is the first and only test cohort",
        "  when the app exists; external cohorts later. Until it runs, the",
        "  **too-rational pathology is NOT MEASURABLE** — it is defined against",
        "  human cohorts, and no proxy number is published in its place.",
        "",
        "## Standing rule (the plan's, restated verbatim in effect)",
        "",
        "**No client-facing actor claim precedes this evidence** — and this",
        "study is INCOMPLETE until the human-cohort arm runs. What exists today",
        "supports internal engineering conclusions only.",
        "",
        "---",
        "",
        "*Not investment advice.*",
    ]
    EVIDENCE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"evidence written: {len(records)} decision records; arms {sorted(rates)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--asof", default=None)
    args = parser.parse_args()
    if args.live and not args.asof:
        raise SystemExit("--live requires --asof YYYY-MM-DD")
    main(args.live, args.asof)
