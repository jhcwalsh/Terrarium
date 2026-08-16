"""Task 13: THE MEASUREMENT RE-RUN (spine-02, round two).

Spec: spine-02 Task 13 brief. Bars are SEALED at
``docs/superpowers/specs/spine02-prereg.json`` (commit ``d8d506c``) -- this
script may build wiring and read thresholds from that file, but it may never
write one back into the thresholds themselves, and it may never touch any
file the seal hashes (``src/ah/gen/spine.py``, ``src/ah/gen/stress.py``,
``src/ah/gen/bootstrap.py``, ``src/ah/gen/regimes/semimarkov.py``,
``src/ah/gen/climate/{model,simulate}.py``, ``scripts/spine_pilot_report.py``,
``scripts/spine_pilot_b3.py``, ``src/ah/presets/spine_pilot.json``,
``scripts/spine02_seal.py``).

Precedent: ``scripts/spine_pilot_b3.py`` postdated round one's own seal the
same way -- a thin harness written AFTER the pre-registration, reading
sealed thresholds, never writing them. This script does the analogous thing
for round two: it contains NO judging logic of its own. Every judge it calls
(``judge_b1_v2``, ``judge_b2``, ``judge_b4``, ``judge_b5_v2``,
``judge_b6_v2``) is loaded, by file path, from ``scripts/spine_pilot_report.py``
-- the sealed module -- so every number this script prints is judged by code
the seal's hash already covers, never by a fresh re-implementation that could
silently drift from it. The sampling call shapes (``SpineBootstrap`` +
``sample_spine`` over the same world/source/seed) are copied verbatim from
that module's own ``_run_seed``.

Also re-runs B3 (``scripts/spine_pilot_b3.py``, UNCHANGED, invoked as a
subprocess) -- as a side effect of running, it reads world 802 and the
sealed b3 thresholds and appends its own section to round one's results file
(``docs/superpowers/specs/2026-08-15-spine-pilot-results.md``, its own
hardcoded ``RESULTS_PATH``). Round one's record is frozen and must not carry
that mutation: this script snapshots that file's bytes before invoking the
subprocess and restores them immediately after, so the round-one record is
byte-identical before and after this script runs. The section the subprocess
appended is captured only from the before/after diff -- never left in
place -- and copied verbatim into round two's own results doc, alongside a
distinct-spine count this script computes independently for the b3 seed
ladder (``199002 + 7919*k``, k=0..19).

Import-safe: importing this module draws no data, samples no ensemble, and
writes no file. All of that happens only under ``if __name__ == "__main__"``.

Run:

    uv run python scripts/spine02_report.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
SEALED_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine02-prereg.json"
WORLD_PATH = _REPO_ROOT / "src" / "ah" / "presets" / "spine_pilot.json"
RESULTS_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-08-16-spine02-results.md"
ROUND_ONE_RESULTS_PATH = (
    _REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-08-15-spine-pilot-results.md"
)
ROUND_ONE_SEAL_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-pilot-prereg.json"
B3_SCRIPT_PATH = _REPO_ROOT / "scripts" / "spine_pilot_b3.py"

N_PATHS = 20

#: scripts/spine_pilot_b3.py's own seed ladder (world 802's base_seed, the
#: platform's SEED_STRIDE=7919) -- reproduced here as literals so this
#: script's own distinct-spine count can be computed WITHOUT running the
#: sealed b3 harness's full institution simulation; the harness itself is
#: still run separately, unchanged, below.
B3_BASE_SEED = 199002
B3_SEED_STRIDE = 7919
B3_N_SEEDS = 20

#: Round one's ALL-seed conjunction verdicts, cited verbatim from
#: docs/superpowers/specs/2026-08-15-spine-pilot-results.md's own summary
#: table (the "**ALL**" row). B1/B5/B6 there are the v1 bars (different
#: construct from this round's v1_v2 bars); B2/B4 are the SAME bars, judged
#: by the SAME frozen code (test_v1_judges_are_frozen).
ROUND_ONE_ALL_VERDICTS: dict[str, str] = {
    "b1": "FAIL",
    "b2": "FAIL",
    "b4": "FAIL",
    "b5": "FAIL",
    "b6": "INCONCLUSIVE (construct mismatch)",
}


# --------------------------------------------------------------------------- #
# small pure wiring helpers (formatting only -- no judging)
# --------------------------------------------------------------------------- #


def _load_sealed_judges() -> Any:
    """Loads scripts/spine_pilot_report.py by file path (the sealed module),
    same pattern as tests/test_gen_spine.py's ``report`` fixture, so every
    judge this script calls is the one the seal's hash covers."""
    spec = importlib.util.spec_from_file_location(
        "_spine_pilot_report", _REPO_ROOT / "scripts" / "spine_pilot_report.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_sealed() -> dict[str, Any]:
    return json.loads(SEALED_PATH.read_text(encoding="utf-8"))


def _load_world() -> Any:
    from ah.core.numericworld import project_numeric
    from ah.core.worldspec import WorldSpec

    doc = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


def _distinct_state_hashes(states: np.ndarray) -> set[str]:
    """SHA-256 of each leading-axis slice's bytes -- the stride-fix
    verification the Task-13 brief asks for: hash each decade's/spine's
    states bytes, count uniques."""
    return {
        hashlib.sha256(np.ascontiguousarray(states[k]).tobytes()).hexdigest()
        for k in range(states.shape[0])
    }


def _fmt_bool(p: bool) -> str:
    return "PASS" if p else "FAIL"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# the measurement run itself -- only under __main__ (import-safe module)
# --------------------------------------------------------------------------- #


def _run_seed(
    seed: int, world: Any, source: Any, sealed: dict[str, Any], report: Any
) -> dict[str, Any]:
    """Wiring only: sample_spine + SpineBootstrap over the same world/
    source/seed (call shapes copied verbatim from spine_pilot_report.py's
    own ``_run_seed``), judged by the sealed module's v2 judges (B1/B5/B6)
    and its carried-verbatim v1 judges (B2/B4)."""
    from ah.gen.spine import SpineBootstrap, sample_spine
    from ah.gen.systems import _pinned_layers

    climate, regimes_artifact = _pinned_layers()
    months = int(world.horizon.quarters) * 3
    premise = world.spine.premise

    sp = sample_spine(
        climate, regimes_artifact, premise, n_decades=N_PATHS, seed=seed, months=months
    )
    gen = SpineBootstrap()
    gen.fit(source)
    ens = gen.sample(world, N_PATHS, seed)
    cond = ens.meta.conditioning

    b1 = report.judge_b1_v2(sp, sealed["b1_v2"])
    b2 = report.judge_b2(ens, source, sealed["b2"])
    b4 = report.judge_b4(sp, sealed["b4"])
    b5 = report.judge_b5_v2(cond, sealed["b5_v2"])
    b6 = report.judge_b6_v2(sp, sealed["b6_v2"])

    return {
        "seed": seed,
        "spine_attempts": int(sp.attempts),
        "distinct_spines": len(_distinct_state_hashes(sp.states)),
        "n_decades": int(sp.states.shape[0]),
        "conditioning": cond,
        "b1": b1,
        "b2": b2,
        "b4": b4,
        "b5": b5,
        "b6": b6,
    }


def _b3_ladder_distinct_count(world: Any) -> dict[str, Any]:
    """The round-one collision reproduction, re-measured: 20 INDEPENDENT
    ``sample_spine`` calls (n_decades=1 each), one per B3 ladder seed
    (``199002 + 7919*k``, k=0..19 -- world 802's own base seed and the
    platform's own per-path stride, scripts/spine_pilot_b3.py's ladder
    verbatim). Round one found only 2 distinct spines across these 20 calls
    (final-review finding F3: the spine attempt stride reused the platform's
    7919 stride, so consecutive ladder seeds realigned onto the SAME
    climate/regimes/inflnoise tape). The Task-10 fix decouples
    ``ATTEMPT_STRIDE`` from ``SEED_STRIDE``; this recomputes the same
    26-call diversity check the round-one B3 section disclosed, against the
    fixed tree, WITHOUT running the sealed b3 harness's institution
    simulation (that runs separately below, unchanged)."""
    from ah.gen.spine import sample_spine
    from ah.gen.systems import _pinned_layers

    climate, regimes_artifact = _pinned_layers()
    months = int(world.horizon.quarters) * 3
    premise = world.spine.premise
    base_seed = int(world.engine_defaults.base_seed)
    assert base_seed == B3_BASE_SEED, f"world 802's base_seed changed: {base_seed}"

    per_seed_hash: dict[int, str] = {}
    for k in range(B3_N_SEEDS):
        seed = base_seed + B3_SEED_STRIDE * k
        sp = sample_spine(climate, regimes_artifact, premise, n_decades=1, seed=seed, months=months)
        per_seed_hash[seed] = hashlib.sha256(
            np.ascontiguousarray(sp.states[0]).tobytes()
        ).hexdigest()
    distinct = len(set(per_seed_hash.values()))
    return {
        "seeds": list(per_seed_hash.keys()),
        "hashes": per_seed_hash,
        "distinct": distinct,
        "n": B3_N_SEEDS,
    }


def _print_seed(row: dict[str, Any]) -> None:
    cond = row["conditioning"]
    corr = cond["corrections"]
    print(f"=== seed {row['seed']} ===")
    print(f"spine attempts: {row['spine_attempts']}")
    print(f"distinct spines (within-call, /{row['n_decades']}): {row['distinct_spines']}")
    print(f"pool_occupancy: {cond['pool_occupancy']}")
    print(f"per_path_onsets: {corr['per_path_onsets']}")
    print(f"per_quadrant_onsets: {corr['per_quadrant_onsets']}")
    print(f"per_quadrant_months: {corr['per_quadrant_months']}")
    print(
        f"forced_reentries: {cond['forced_reentries']}  unfiltered_reentries: {cond['unfiltered_reentries']}"
    )
    b1, b2, b4, b5, b6 = row["b1"], row["b2"], row["b4"], row["b5"], row["b6"]
    print(f"B1v2 {_fmt_bool(b1['pass'])}  value={b1['value']:.4f} (>= {b1['threshold']:.2f})")
    print(
        f"B2 {_fmt_bool(b2['pass'])}  max_join_jump={b2['value']['max_join_jump_pp']:.4f}pp "
        f"p95_adjacent={b2['value']['p95_adjacent_yoy_pp']:.4f}pp  n_joins={b2['n_joins']}"
    )
    print(
        f"B4 {_fmt_bool(b4['pass'])}  clockwise={b4['clockwise']['value']:.4f} "
        f"(panel {b4['clockwise']['panel']:.4f})"
    )
    print(
        f"B5v2 {_fmt_bool(b5['pass'])}  observed={b5['observed']}  expected={b5['expected']:.4f} "
        f"margin={b5['margin']:.4f}  zero_rate_ok={b5['zero_rate_ok']}"
    )
    print(
        f"B6v2 {b6['verdict']}  value={b6['value']:.4f} (panel {b6['threshold']:.4f})  "
        f"spine_base={b6['spine_base_rate']:.4f}  panel_base={b6['panel_base_rate']:.4f}"
    )
    print()


def _print_summary(
    rows: list[dict[str, Any]],
    all_b1: bool,
    all_b2: bool,
    all_b4: bool,
    all_b5: bool,
    all_b6: str,
) -> None:
    print("=== SUMMARY (per-seed verdicts, ALL-seed conjunction) ===")
    header = f"{'seed':>10} | {'B1v2':6} | {'B2':6} | {'B4':6} | {'B5v2':6} | {'B6v2':30}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['seed']:>10} | {_fmt_bool(row['b1']['pass']):6} | "
            f"{_fmt_bool(row['b2']['pass']):6} | {_fmt_bool(row['b4']['pass']):6} | "
            f"{_fmt_bool(row['b5']['pass']):6} | {row['b6']['verdict']:30}"
        )
    print("-" * len(header))
    print(
        f"{'ALL':>10} | {_fmt_bool(all_b1):6} | {_fmt_bool(all_b2):6} | "
        f"{_fmt_bool(all_b4):6} | {_fmt_bool(all_b5):6} | {all_b6:30}"
    )


def _write_report(
    sealed: dict[str, Any],
    rows: list[dict[str, Any]],
    all_b1: bool,
    all_b2: bool,
    all_b4: bool,
    all_b5: bool,
    all_b6: str,
    b3_ladder: dict[str, Any],
) -> None:
    lines: list[str] = []
    lines.append("# Spine-02 -- measurement re-run (Task 13)")
    lines.append("")
    lines.append(
        "Sealed thresholds: `docs/superpowers/specs/spine02-prereg.json` (commit `d8d506c`). "
        "World: `src/ah/presets/spine_pilot.json` (`00000000-0000-4000-9000-000000000802`, "
        '"The Hard Landing"). '
        f"Sensitivity seeds: {sealed['sensitivity_seeds']}. `n_paths=20` per seed. "
        "B1/B5/B6 are the v2 (Task-11-respecified) bars; B2/B4 are round one's bars, judged by "
        "the SAME frozen code (`test_v1_judges_are_frozen`)."
    )
    lines.append("")
    lines.append("## Verdict summary (round two)")
    lines.append("")
    lines.append(
        _md_table(
            ["seed", "B1 v2", "B2", "B4", "B5 v2", "B6 v2"],
            [
                [
                    str(row["seed"]),
                    _fmt_bool(row["b1"]["pass"]),
                    _fmt_bool(row["b2"]["pass"]),
                    _fmt_bool(row["b4"]["pass"]),
                    _fmt_bool(row["b5"]["pass"]),
                    row["b6"]["verdict"],
                ]
                for row in rows
            ]
            + [
                [
                    "**ALL**",
                    _fmt_bool(all_b1),
                    _fmt_bool(all_b2),
                    _fmt_bool(all_b4),
                    _fmt_bool(all_b5),
                    all_b6,
                ]
            ],
        )
    )
    lines.append("")
    lines.append(
        "ALL-seed conjunction rule (unchanged from round one): B1/B2/B4/B5 are AND across "
        "seeds. B6's three-way conjunction: any seed FAIL dominates (a real construct-matched "
        "failure); else any seed INCONCLUSIVE dominates; else PASS."
    )

    lines.append("")
    lines.append("## Round one vs round two, side by side")
    lines.append("")
    lines.append(
        _md_table(
            ["bar", "round one ALL", "round two ALL", "same bar?"],
            [
                ["B1", ROUND_ONE_ALL_VERDICTS["b1"], _fmt_bool(all_b1), "no -- v2 respecified"],
                ["B2", ROUND_ONE_ALL_VERDICTS["b2"], _fmt_bool(all_b2), "yes -- frozen v1 code"],
                ["B4", ROUND_ONE_ALL_VERDICTS["b4"], _fmt_bool(all_b4), "yes -- frozen v1 code"],
                ["B5", ROUND_ONE_ALL_VERDICTS["b5"], _fmt_bool(all_b5), "no -- v2 respecified"],
                ["B6", ROUND_ONE_ALL_VERDICTS["b6"], all_b6, "no -- v2 respecified"],
            ],
        )
    )
    lines.append("")
    lines.append(
        "Round-one verdicts cited verbatim from "
        "`docs/superpowers/specs/2026-08-15-spine-pilot-results.md`'s own summary table "
        "(the **ALL** row). B1/B5/B6 test a DIFFERENT construct in round two (see judge "
        "docstrings in `scripts/spine_pilot_report.py`), so a verdict flip there is not "
        "necessarily 'the same defect, fixed' -- B2/B4 are the one apples-to-apples comparison "
        "in this table, run through byte-identical judging code both rounds."
    )

    lines.append("")
    lines.append("## Distinct-spine counts (stride-fix verification)")
    lines.append("")
    lines.append(
        "**Within-call** (per sensitivity seed, across its own 20 decades -- each decade "
        "within one `sample_spine` call already advances on its own attempt index, so this "
        "checks nothing was aliasing WITHIN a call):"
    )
    lines.append("")
    lines.append(
        _md_table(
            ["seed", "distinct spines", "n decades", "spine attempts used"],
            [
                [
                    str(row["seed"]),
                    str(row["distinct_spines"]),
                    str(row["n_decades"]),
                    str(row["spine_attempts"]),
                ]
                for row in rows
            ],
        )
    )
    lines.append("")
    lines.append(
        "**Cross-call, the round-one collision itself** (the B3 ladder, `199002 + 7919*k`, "
        f"k=0..19 -- one INDEPENDENT `sample_spine(n_decades=1, ...)` call per seed): "
        f"**{b3_ladder['distinct']}/{b3_ladder['n']}** distinct spines. Round one measured "
        "**2/20** on this exact ladder (`k=0..18` collapsed onto one shared attempt tape; only "
        "`k=19` differed -- see round one's 'Spine multiplicity disclosure', final-review "
        "finding F3). The Task-10 fix (`ATTEMPT_STRIDE` decoupled from `SEED_STRIDE`) is what "
        "this number verifies."
    )

    lines.append("")
    lines.append("## B1 v2 -- reaction function (contemporaneous lag, 0..2 months)")
    lines.append("")
    lines.append(
        _md_table(
            ["seed", "fraction of decades passing", "threshold", "verdict"],
            [
                [
                    str(row["seed"]),
                    f"{row['b1']['value']:.4f}",
                    f">= {row['b1']['threshold']:.2f}",
                    _fmt_bool(row["b1"]["pass"]),
                ]
                for row in rows
            ],
        )
    )

    lines.append("")
    lines.append("## B2 -- era coherence (round-one bar and judge, unchanged)")
    lines.append("")
    lines.append(
        _md_table(
            [
                "seed",
                "n_joins",
                "max join YoY jump (pp)",
                "bound (pp)",
                "p95 adjacent YoY (pp)",
                "bound (pp)",
                "verdict",
            ],
            [
                [
                    str(row["seed"]),
                    str(row["b2"]["n_joins"]),
                    f"{row['b2']['value']['max_join_jump_pp']:.4f}",
                    f"{row['b2']['threshold']['join_yoy_max_pp']:.4f}",
                    f"{row['b2']['value']['p95_adjacent_yoy_pp']:.4f}",
                    f"{row['b2']['threshold']['p95_bound_pp']:.4f}",
                    _fmt_bool(row["b2"]["pass"]),
                ]
                for row in rows
            ],
        )
    )

    lines.append("")
    lines.append("## B4 -- persistence and the clock's order (round-one bar and judge, unchanged)")
    lines.append("")
    for row in rows:
        lines.append(f"### seed {row['seed']}")
        lines.append("")
        lines.append(
            _md_table(
                [
                    "quadrant",
                    "visits (spells)",
                    "median (months)",
                    "panel median",
                    "ratio",
                    "band",
                    "pass",
                ],
                [
                    [
                        d["quadrant"],
                        str(d["visits"]),
                        "n/a" if d["median"] is None else f"{d['median']:.1f}",
                        f"{d['panel_median']:.1f}",
                        "n/a" if d["ratio"] is None else f"{d['ratio']:.3f}",
                        f"[{sealed['b4']['dwell_median_ratio_band'][0]}, {sealed['b4']['dwell_median_ratio_band'][1]}]",
                        _fmt_bool(d["pass"]),
                    ]
                    for d in row["b4"]["dwell"]
                ],
            )
        )
        cw = row["b4"]["clockwise"]
        lines.append("")
        lines.append(
            f"Clockwise fraction: {cw['value']:.4f} ({cw['clockwise_changes']}/{cw['total_changes']} "
            f"transitions) vs panel {cw['panel']:.4f} +/- {cw['tolerance']} -> {_fmt_bool(cw['pass'])}"
        )
        lines.append(f"B4 overall: {_fmt_bool(row['b4']['pass'])}")
        lines.append("")

    lines.append("## B5 v2 -- hazard realism (aggregate, normal approximation)")
    lines.append("")
    lines.append(
        _md_table(
            ["seed", "observed", "expected", "sd", "margin", "diff", "zero_rate_ok", "verdict"],
            [
                [
                    str(row["seed"]),
                    str(row["b5"]["observed"]),
                    f"{row['b5']['expected']:.4f}",
                    f"{row['b5']['sd']:.4f}",
                    f"{row['b5']['margin']:.4f}",
                    f"{row['b5']['diff']:.4f}",
                    str(row["b5"]["zero_rate_ok"]),
                    _fmt_bool(row["b5"]["pass"]),
                ]
                for row in rows
            ],
        )
    )

    lines.append("")
    lines.append("## B6 v2 -- transmission (quantile-matched, three-way outcome)")
    lines.append("")
    lines.append(
        _md_table(
            [
                "seed",
                "value (spine conditional)",
                "panel conditional",
                "panel unconditional",
                "rel error",
                "sign ok",
                "spine base rate",
                "panel base rate",
                "base rate ratio",
                "verdict",
            ],
            [
                [
                    str(row["seed"]),
                    f"{row['b6']['value']:.4f}",
                    f"{row['b6']['threshold']:.4f}",
                    f"{row['b6']['panel_unconditional_onset_rate']:.4f}",
                    f"{row['b6']['rel_error']:.4f}",
                    _fmt_bool(row["b6"]["sign_ok"]),
                    f"{row['b6']['spine_base_rate']:.4f} ({row['b6']['tight_months']}/{row['b6']['eligible_months']})",
                    f"{row['b6']['panel_base_rate']:.4f}",
                    f"{row['b6']['base_rate_ratio']:.3f}",
                    row["b6"]["verdict"],
                ]
                for row in rows
            ],
        )
    )

    lines.append("")
    lines.append("## Occupancy and corrections (no silent caps)")
    lines.append("")
    for row in rows:
        cond = row["conditioning"]
        corr = cond["corrections"]
        lines.append(f"### seed {row['seed']}")
        lines.append("")
        lines.append(f"- spine attempts: {row['spine_attempts']}")
        lines.append(
            f"- distinct spines (within-call): {row['distinct_spines']}/{row['n_decades']}"
        )
        lines.append(f"- pool_occupancy: `{cond['pool_occupancy']}`")
        lines.append(f"- per_path_onsets: `{corr['per_path_onsets']}`")
        lines.append(f"- per_quadrant_onsets: `{corr['per_quadrant_onsets']}`")
        lines.append(f"- per_quadrant_months: `{corr['per_quadrant_months']}`")
        lines.append(f"- forced_reentries: {cond['forced_reentries']}")
        lines.append(f"- unfiltered_reentries: {cond['unfiltered_reentries']}")
        lines.append("")

    lines.append("## Sealed disclosures (quoted verbatim)")
    lines.append("")
    lines.append(f"- B4 power disclosure: {sealed['b4']['power_disclosure']}")
    lines.append(f"- B5 v2 zero-rate convention: {sealed['b5_v2']['zero_rate_convention']}")
    lines.append("")

    lines.append("## What changed and why")
    lines.append("")
    lines.append(
        "Two wiring fixes separate this round's numbers from round one's, both landed under "
        "spine-02's own authority before this seal (Task 10, commit `75e8b07`), and both "
        "verified directly above rather than merely asserted:"
    )
    lines.append("")
    lines.append(
        "1. **The attempt stride was decoupled from the platform's per-path stride.** Round "
        "one's `sample_spine` advanced its climate/regimes/inflnoise attempt streams by "
        "`SEED_STRIDE` (7919) -- the SAME constant the platform uses for its own per-path "
        "ensemble seeding (`base_seed + 7919*k`, CLAUDE.md). Whenever one call's accepted "
        "attempt index landed exactly `7919*k` away from another call's base seed, the two "
        "calls' climate/regimes/inflnoise draws collided and produced BIT-IDENTICAL spines "
        "from that attempt onward (final-review finding F3). This silently collapsed the "
        "macro-storyline diversity behind an entire seed ladder to a handful of distinct "
        "spines -- round one's own B3 section measured 2/20 on the `199002 + 7919*k` ladder. "
        "`ATTEMPT_STRIDE` (a large prime, coprime to 7919) replaces `SEED_STRIDE` for the "
        "attempt loop, so no attempt index in the budget can realign two calls' streams. "
        "Re-measured above: the same ladder now reads "
        "**{B3_DISTINCT_PLACEHOLDER}**."
    )
    lines.append(
        "2. **`pi_actual` (fitted CPI observation noise) now feeds the policy anchor.** Round "
        "one's Taylor anchor responded only to `pi_star`, the slow-moving trend component -- "
        "the transitory inflation surprise a real policy reaction function actually chases "
        "structurally never reached it. B1 v1 therefore tested the anchor's response to "
        "`pi_star - mu_pi` at a 3..12-month lag and failed on every seed (0.10-0.15 of decades "
        "passing against a 0.90 bar). spine-02 wires `pi_actual = pi_star + eps` into "
        "`policy_anchor`, so the anchor CAN respond same-month; B1 v2 tests the response to "
        "`pi_actual - pi_star` at the model's own 0..2-month contemporaneous lag -- the window "
        "the round-one construct structurally excluded. B6 v2's quantile-matched tightness "
        "threshold (Task 11) is a separate, independently-motivated respec (matching the "
        "panel's own curve-inversion base rate per decade rather than a fixed `policy_gap > 0` "
        "cut) and does not depend on either wiring fix above."
    )
    lines.append("")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    text = text.replace("{B3_DISTINCT_PLACEHOLDER}", f"{b3_ladder['distinct']}/{b3_ladder['n']}")
    RESULTS_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {RESULTS_PATH}")


def _run_b3_and_append(b3_ladder: dict[str, Any]) -> None:
    """Re-runs scripts/spine_pilot_b3.py UNCHANGED (it is sealed -- this
    script never edits it, only invokes it). scripts/spine_pilot_b3.py reads
    world 802 and the sealed b3 thresholds itself and appends its own section
    to round one's results file (its own hardcoded RESULTS_PATH) as a side
    effect of running -- round one's record must not carry that mutation, so
    this function snapshots that file's bytes before invoking the subprocess
    and restores them immediately after, regardless of what the subprocess
    wrote. The appended section is captured only from the before/after diff
    (never left in place) and copied VERBATIM into this round's own results
    doc, alongside the distinct-spine count computed independently above."""
    before = ROUND_ONE_RESULTS_PATH.read_bytes()
    try:
        proc = subprocess.run(
            [sys.executable, str(B3_SCRIPT_PATH)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        print(proc.stdout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"scripts/spine_pilot_b3.py exited {proc.returncode}:\n{proc.stderr}"
            )
        after = ROUND_ONE_RESULTS_PATH.read_text(encoding="utf-8")
        before_text = before.decode("utf-8")
        before_stripped = before_text.rstrip("\n")
        if not after.startswith(before_stripped):
            raise RuntimeError(
                "scripts/spine_pilot_b3.py's append did not extend round one's results file as "
                "expected -- cannot isolate the newly-appended B3 section"
            )
        appended_section = after[len(before_stripped) :]
    finally:
        ROUND_ONE_RESULTS_PATH.write_bytes(before)

    header = (
        "\n## B3 -- the over-commitment grid under spine worlds, re-run (Task 13)\n\n"
        "`scripts/spine_pilot_b3.py` re-run UNCHANGED against this round's (stride-fixed) "
        "tree -- the script itself is sealed and untouched; its tapes differ from round one's "
        "legitimately, because the upstream stride fix changes what `sample_spine` returns for "
        "the same seeds. Section below is copied VERBATIM from what the script itself appended "
        "to `docs/superpowers/specs/2026-08-15-spine-pilot-results.md` (its own hardcoded "
        "output path) in this run.\n\n"
        "Distinct-spine count across this same 20-seed ladder (`199002 + 7919*k`, k=0..19), "
        f"computed independently above via `sample_spine` directly: "
        f"**{b3_ladder['distinct']}/{b3_ladder['n']}**.\n"
    )
    with RESULTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(header)
        fh.write(appended_section)
    print(f"appended re-run B3 section to {RESULTS_PATH}")


def main() -> None:
    from ah.gen.bootstrap import campaign_source

    report = _load_sealed_judges()
    sealed = _load_sealed()
    world = _load_world()
    source = campaign_source()

    rows: list[dict[str, Any]] = []
    for seed in sealed["sensitivity_seeds"]:
        row = _run_seed(int(seed), world, source, sealed, report)
        _print_seed(row)
        rows.append(row)

    all_b1 = report._conjoin_bool([row["b1"]["pass"] for row in rows])
    all_b2 = report._conjoin_bool([row["b2"]["pass"] for row in rows])
    all_b4 = report._conjoin_bool([row["b4"]["pass"] for row in rows])
    all_b5 = report._conjoin_bool([row["b5"]["pass"] for row in rows])
    all_b6 = report._conjoin_b6([row["b6"]["verdict"] for row in rows])

    _print_summary(rows, all_b1, all_b2, all_b4, all_b5, all_b6)

    b3_ladder = _b3_ladder_distinct_count(world)
    print(f"B3 ladder distinct-spine count: {b3_ladder['distinct']}/{b3_ladder['n']}")

    _write_report(sealed, rows, all_b1, all_b2, all_b4, all_b5, all_b6, b3_ladder)
    _run_b3_and_append(b3_ladder)


if __name__ == "__main__":
    main()
