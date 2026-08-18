"""Anti-test sweeps for D-SP-11's NEW judge, ``S1`` -- run BEFORE the seal.

**The obligation.** The stage-2 exam's section 6.1, carried forward: a judge
whose pass rate does not increase in the effect its bar claims to measure does
not get sealed. D-SP-11's charter adds two of its own, in so many words: *a
seam-worsening sweep must fail it monotonically, and a seam-hiding-by-noise-
inflation attack must also fail -- think both directions.*

**Why this bar needs both directions, stated once.** ``S1`` asks whether a seam
is **distinguishable** from an ordinary historical month-transition. That is a
two-sided property. A compiler can make its seams findable by splicing across
big inflation jumps -- and it can make them findable by splicing only across
near-identical ones, which is the signature of a world that has stopped moving.
So a single "more of the effect" sweep is not enough and would in fact be
non-monotone by construction, since the bar's pass region is an interval. The
sweeps below therefore each run **toward** fidelity, from one side, and the pass
rate is required to be non-decreasing in fidelity -- exam 6.1's rule stated on the
effect the bar actually measures.

**The five constructs, and what each one is for.**

``S1_seam_inflation`` (sweep)
  Seam jumps are drawn from history's own jump distribution and multiplied by a
  factor. At 1.0 a seam **is** an ordinary historical transition, by
  construction; above it the seams are inflated. The grid runs from 3.0 down to
  1.0 and the pass rate must not fall. This is the charter's seam-worsening
  sweep, read from its good end.

``S1_seam_oversmoothing`` (sweep)
  The same construction below 1.0: seams shrunk toward zero, which is a compiler
  that only ever joins rows with near-identical inflation. The grid runs from 0.2
  up to 1.0 and the pass rate must not fall. Without this sweep the bar's lower
  edge is decoration.

``S1_texture_roughening`` (sweep)
  Block entries drawn only from the panel's most volatile stretches, so the
  months INSIDE a block stop looking like history's typical months. This is the
  half of the bar that judges texture, and it sweeps toward the whole panel.

``S1_noise_inflation_attack`` (control -- must FAIL, and fail ABOVE)
  **The attack the charter names.** Take a world whose seams are plainly visible
  and roughen its own months until the seams no longer stand out *relative to the
  world*. A bar that compared a world's seams to a world's own other months would
  be passed by this. ``S1`` is not, because its band comes from HISTORY -- and
  the roughening pushes the texture condition ABOVE its band, so the attack does
  not merely fail to help, it is itself caught. The control asserts three things:
  ``S1``'s pass rate falls to zero, the texture half fails on the **upper** side
  every time, and the self-referential bar ``S1`` refuses to be would have been
  fooled at a strictly higher rate.

``S1_history_identity`` (control -- must PASS)
  Fifty contiguous 120-month stretches of the real panel. That world **is**
  history: it has no seams and its texture is history's own. A bar that fails it
  is measuring itself, and there is no honest reading of any other result until
  this one holds.

**Everything is built on the REAL panel.** The synthetic worlds below are row
tapes over the campaign panel's own trailing-inflation series, so the anchor the
judge cuts its band from is the anchor the measurement will use. Nothing here
fits, tunes or scales a parameter of the engine, and the engine is not run: a
seam is a property of a row tape and needs no compiler to exist.

**Determinism.** One literal seed per construct, all distinct, none derived from
another by a stride. Re-running writes byte-identical output.

Invocation (from the worktree root, no network):

    uv run python scripts/stage2_rulers_antitest.py
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import stage2_rulers as rulers  # noqa: E402

from ah.gen.bootstrap import campaign_source  # noqa: E402
from ah.gen.spine import panel_yoy  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
OUT_JSON = _SPECS / "stage2-rulers-antitest-results.json"
OUT_MD = _SPECS / "stage2-rulers-antitest-results.md"

#: Batch shape: the campaign's own -- fifty decades of 120 months -- so a sweep
#: replicate is the same size object the measurement judges.
N_DECADES = 50
DECADE_MONTHS = 120
#: The world's own declared mean block length (spine_pilot.json's
#: ``mean_block_months``), so seams arrive at the rate the real compiler makes
#: them. Not a tuned number.
MEAN_BLOCK_MONTHS = 6
#: Replicates per grid point. Twelve, because each replicate costs four
#: 2000-draw block bootstraps and the sweeps' claim is about the ORDER of pass
#: rates, not about resolving one to two decimal places.
N_REPLICATES = 12

SEED_SEAM_INFLATION = 41000117
SEED_SEAM_OVERSMOOTHING = 41000253
SEED_TEXTURE = 41000397
SEED_ATTACK = 41000541
SEED_IDENTITY = 41000683
_SEEDS = {
    "S1_seam_inflation": SEED_SEAM_INFLATION,
    "S1_seam_oversmoothing": SEED_SEAM_OVERSMOOTHING,
    "S1_texture_roughening": SEED_TEXTURE,
    "S1_noise_inflation_attack": SEED_ATTACK,
    "S1_history_identity": SEED_IDENTITY,
}
if len(set(_SEEDS.values())) != len(_SEEDS):
    raise SystemExit("two anti-test constructs share a seed")


# --------------------------------------------------------------------------- #
# the synthetic worlds -- row tapes over the real panel
# --------------------------------------------------------------------------- #


def _valid_rows(yoy: np.ndarray) -> np.ndarray:
    """Panel rows the compiler could stand on: trailing inflation defined."""
    return np.flatnonzero(~np.isnan(yoy))


def _forward_roughness(yoy: np.ndarray, window: int = 12) -> np.ndarray:
    """Mean |dYoY| over the next ``window`` months, per row. NaN at the edges.

    The knob the texture sweep turns: entering a block here means the months
    inside the block move by about this much.
    """
    jumps = np.abs(np.diff(yoy))
    out = np.full(yoy.size, np.nan)
    for i in range(yoy.size - window):
        seg = jumps[i : i + window]
        if not np.isnan(seg).any():
            out[i] = float(seg.mean())
    return out


def synthetic_world(
    yoy: np.ndarray,
    *,
    seed: int,
    seam_scale: float,
    entry_roughness_percentile: float = 0.0,
    n_decades: int = N_DECADES,
    months: int = DECADE_MONTHS,
    mean_block: int = MEAN_BLOCK_MONTHS,
) -> np.ndarray:
    """A row tape with seams of a declared scale and entries of a declared texture.

    * a block ends with probability ``1 / mean_block`` each month, the platform's
      own geometric rule;
    * at a seam, a target jump is **drawn from history's own adjacent-jump
      distribution** and multiplied by ``seam_scale``, and the tape moves to the
      admissible row whose actual jump is closest to that target. At
      ``seam_scale = 1.0`` the seams are therefore draws from the anchor itself,
      which is the fidelity point both sweeps run toward;
    * ``entry_roughness_percentile`` restricts every block entry to rows above
      that percentile of forward 12-month roughness. At 0.0 the entries are the
      whole panel; at 0.9 the world lives in history's most violent stretches.

    No engine, no fit, no premise: a seam is a property of a row tape.
    """
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    anchor = rulers.panel_adjacent_jumps(yoy)
    valid = _valid_rows(yoy)
    last = int(valid.max())
    if entry_roughness_percentile > 0.0:
        rough = _forward_roughness(yoy)
        cut = float(np.nanpercentile(rough, 100.0 * entry_roughness_percentile))
        entries = np.flatnonzero(~np.isnan(rough) & (rough >= cut))
        entries = entries[np.isin(entries, valid)]
    else:
        entries = valid
    y_valid = yoy[valid]

    rows = np.empty((int(n_decades), int(months)), dtype=np.int64)
    for p in range(int(n_decades)):
        cur = int(entries[rng.integers(0, entries.size)])
        rows[p, 0] = cur
        for m in range(1, int(months)):
            seam = rng.random() < 1.0 / float(mean_block) or cur + 1 > last
            if not seam:
                cur += 1
                rows[p, m] = cur
                continue
            target = float(anchor[rng.integers(0, anchor.size)]) * float(seam_scale)
            allowed = entries if entries.size else valid
            gap = np.abs(np.abs(y_valid[np.isin(valid, allowed)] - yoy[cur]) - target)
            pool = valid[np.isin(valid, allowed)]
            order = np.argsort(gap, kind="stable")
            pick = int(pool[order[0]])
            if pick == cur + 1 or pick == cur:  # not a seam; take the runner-up
                pick = int(pool[order[1]]) if order.size > 1 else int(pool[order[0]])
            cur = pick
            rows[p, m] = cur
    return rows


def history_world(
    yoy: np.ndarray, *, seed: int, n_decades: int = N_DECADES, months: int = DECADE_MONTHS
) -> np.ndarray:
    """Fifty contiguous stretches of the real panel -- a world that IS history."""
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    valid = _valid_rows(yoy)
    starts = valid[valid <= int(valid.max()) - months + 1]
    picks = rng.choice(starts, size=int(n_decades), replace=True)
    return np.stack([np.arange(int(s), int(s) + int(months)) for s in picks])


# --------------------------------------------------------------------------- #
# sweeps and controls
# --------------------------------------------------------------------------- #


def _monotone(values: list[float]) -> bool:
    return all(b >= a - 1e-12 for a, b in itertools.pairwise(values))


def _sweep(
    name: str,
    effect: str,
    grid: list[float],
    seed: int,
    yoy: np.ndarray,
    sealed: dict[str, Any],
    *,
    roughness: float = 0.0,
    roughness_grid: list[float] | None = None,
) -> dict[str, Any]:
    rates: list[float] = []
    margins: list[float] = []
    seam_rates: list[float] = []
    texture_rates: list[float] = []
    for g, point in enumerate(grid):
        passes = seam_ok = texture_ok = 0
        vals: list[float] = []
        for r in range(N_REPLICATES):
            rows = synthetic_world(
                yoy,
                seed=seed + 1000 * g + r,
                seam_scale=(1.0 if roughness_grid is not None else float(point)),
                entry_roughness_percentile=(
                    float(roughness_grid[g]) if roughness_grid is not None else roughness
                ),
            )
            verdict = rulers.judge_s1(rows, yoy, sealed, with_disclosures=False)
            passes += int(verdict["pass"])
            seam_ok += int(verdict["seam_pass"])
            texture_ok += int(verdict["texture_pass"])
            vals.append(float(verdict["value"]))
        rates.append(passes / N_REPLICATES)
        seam_rates.append(seam_ok / N_REPLICATES)
        texture_rates.append(texture_ok / N_REPLICATES)
        margins.append(float(np.mean(vals)))
    return {
        "effect": effect,
        "statistic": "S1 binding margin: the smallest slack from a judged quantile to its band",
        "grid": grid,
        "pass_rate": rates,
        "seam_half_pass_rate": seam_rates,
        "texture_half_pass_rate": texture_rates,
        "mean_statistic": margins,
        "monotone_non_decreasing": _monotone(rates),
        "seed": seed,
        "n_replicates": N_REPLICATES,
    }


def run_sweeps(yoy: np.ndarray, sealed: dict[str, Any]) -> dict[str, Any]:
    sweeps = {
        "S1_seam_inflation": _sweep(
            "S1_seam_inflation",
            "seam jumps shrinking from 3x history's own scale down to history's own scale "
            "(the charter's seam-worsening sweep, read from its good end)",
            [3.0, 2.0, 1.5, 1.2, 1.0],
            SEED_SEAM_INFLATION,
            yoy,
            sealed,
        ),
        "S1_seam_oversmoothing": _sweep(
            "S1_seam_oversmoothing",
            "seam jumps growing from a fifth of history's own scale up to it -- the other "
            "way a seam becomes findable, by being unnaturally smooth",
            [0.2, 0.4, 0.6, 0.8, 1.0],
            SEED_SEAM_OVERSMOOTHING,
            yoy,
            sealed,
        ),
        "S1_texture_roughening": _sweep(
            "S1_texture_roughening",
            "block entries widening from the panel's most violent decile back to the whole "
            "panel, with the seams held at history's own scale throughout",
            [0.90, 0.75, 0.50, 0.25, 0.0],
            SEED_TEXTURE,
            yoy,
            sealed,
            roughness_grid=[0.90, 0.75, 0.50, 0.25, 0.0],
        ),
    }
    controls = {
        "S1_noise_inflation_attack": _attack(yoy, sealed),
        "S1_history_identity": _identity(yoy, sealed),
    }
    return {"sweeps": sweeps, "controls": controls}


#: The attack's seam scale. Seams 1.3x history's own -- **deliberately modest**.
#: A 2.5x seam is too big for any real months to camouflage, so barring it would
#: be barring a strawman; 1.3x is the regime where the camouflage genuinely works
#: against a self-anchored bar, and that is the only regime where "the attack
#: fails" says anything at all.
ATTACK_SEAM_SCALE = 1.3
#: How rough the world's own months are made, as a percentile of the panel's own
#: forward roughness. SWEPT, because the attacker chooses it and the control has
#: to survive their best choice rather than one convenient one.
ATTACK_ROUGHNESS_GRID = (0.0, 0.5, 0.8, 0.9)


def _attack(yoy: np.ndarray, sealed: dict[str, Any]) -> dict[str, Any]:
    """Camouflage the seams by roughening the world's own months. Must FAIL.

    The attacker's move in full: inflate the seams only modestly, then draw every
    block entry from history's most violent stretches so the world's own
    month-to-month moves are as large as its splices. Against a bar that compared
    a world's seams to that world's OWN other months this works -- and the grid
    below shows it working, which is the point of running it. ``S1`` cuts its
    band from history instead, so the roughening hides nothing and additionally
    pushes the texture condition above its own band: **the camouflage is itself
    the evidence.**
    """
    rungs: list[dict[str, Any]] = []
    for g, roughness in enumerate(ATTACK_ROUGHNESS_GRID):
        passes = texture_above = self_ref = 0
        margins: list[float] = []
        for r in range(N_REPLICATES):
            rows = synthetic_world(
                yoy,
                seed=SEED_ATTACK + 1000 * g + r,
                seam_scale=ATTACK_SEAM_SCALE,
                entry_roughness_percentile=float(roughness),
            )
            verdict = rulers.judge_s1(rows, yoy, sealed, with_disclosures=False)
            naive = rulers.self_referential_seam_check(rows, yoy, sealed)
            texture = [
                c for c in verdict["conditions"] if c["kind"] == "contiguous" and c["judged"]
            ]
            passes += int(verdict["pass"])
            texture_above += int(bool(texture) and any(c["value"] > c["band"][1] for c in texture))
            self_ref += int(naive["pass_if_it_were_a_bar"])
            margins.append(float(verdict["value"]))
        rungs.append(
            {
                "entry_roughness_percentile": float(roughness),
                "s1_pass_rate": passes / N_REPLICATES,
                "s1_texture_fails_above_rate": texture_above / N_REPLICATES,
                "self_referential_bar_pass_rate": self_ref / N_REPLICATES,
                "mean_s1_margin": float(np.mean(margins)),
            }
        )
    best = max(rungs, key=lambda r: r["self_referential_bar_pass_rate"])
    return {
        "attack": (
            f"seams at {ATTACK_SEAM_SCALE}x history's own scale, camouflaged by drawing every "
            "block entry from progressively more violent stretches of the panel so the world's "
            "own months move as much as its splices do"
        ),
        "requirement": (
            "three things, and all three are needed for the control to say anything. (1) S1's "
            "pass rate must be ZERO at every rung -- the attack never works. (2) The camouflage "
            "must actually fool the self-referential bar S1 refuses to be, at a strictly "
            "positive rate, or the attack is a strawman and barring it proves nothing. (3) At "
            "the rung where the camouflage works best, S1's TEXTURE half must fail on the "
            "UPPER side in every replicate: the roughening that hides the seams is exactly "
            "what S1 catches"
        ),
        "seam_scale": ATTACK_SEAM_SCALE,
        "rungs": rungs,
        "pass_rate": max(r["s1_pass_rate"] for r in rungs),
        "best_camouflage_at_roughness": best["entry_roughness_percentile"],
        "self_referential_bar_pass_rate": best["self_referential_bar_pass_rate"],
        "texture_fails_above_rate": best["s1_texture_fails_above_rate"],
        "holds": bool(
            all(r["s1_pass_rate"] == 0.0 for r in rungs)
            and best["self_referential_bar_pass_rate"] > 0.0
            and best["s1_texture_fails_above_rate"] == 1.0
        ),
        "seed": SEED_ATTACK,
    }


def _identity(yoy: np.ndarray, sealed: dict[str, Any]) -> dict[str, Any]:
    """A world that IS history must pass its own bar. Must PASS."""
    passes = 0
    vacuous = 0
    rows_out: list[dict[str, Any]] = []
    for r in range(N_REPLICATES):
        rows = history_world(yoy, seed=SEED_IDENTITY + r)
        verdict = rulers.judge_s1(rows, yoy, sealed, with_disclosures=False)
        passes += int(verdict["pass"])
        vacuous += int(verdict["seams_vacuous"])
        rows_out.append(
            {
                "replicate": r,
                "pass": bool(verdict["pass"]),
                "seams_vacuous": bool(verdict["seams_vacuous"]),
                "margin": float(verdict["value"]),
            }
        )
    rate = passes / N_REPLICATES
    return {
        "control": "fifty contiguous 120-month stretches of the real panel",
        "requirement": (
            "must PASS every replicate, with the seam half vacuous. A bar that fails a world "
            "which IS history is measuring itself and no other reading of it is honest"
        ),
        "pass_rate": rate,
        "seam_half_vacuous_rate": vacuous / N_REPLICATES,
        "replicates": rows_out,
        "holds": bool(rate == 1.0 and vacuous == N_REPLICATES),
        "seed": SEED_IDENTITY,
    }


# --------------------------------------------------------------------------- #


def _write_markdown(record: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# D-SP-11 - anti-test results for `S1` (run BEFORE the seal)")
    lines.append("")
    lines.append(
        "Produced by `scripts/stage2_rulers_antitest.py`, which imports the real judge from "
        "`scripts/stage2_rulers.py` and the real threshold block through `sealed_from_sources` "
        "- the same single assembly path the seal writes. Machine-readable values: "
        f"`{OUT_JSON.relative_to(_REPO_ROOT).as_posix()}`."
    )
    lines.append("")
    lines.append(f"**The obligation.** {record['obligation']}")
    lines.append("")
    lines.append(f"**The rule.** {record['rule']}")
    lines.append("")
    lines.append(
        f"**Size.** {record['n_replicates']} worlds per grid point, {record['n_decades']} "
        f"decades of {record['decade_months']} months each - the campaign's own batch shape. "
        "Every world is a row tape over the REAL panel, so the judge's band is cut from the "
        "same anchor the measurement will use. One literal seed per construct, all distinct."
    )
    lines.append("")
    verdict = (
        "every sweep is monotone non-decreasing and both controls hold"
        if record["all_monotone"] and record["all_controls_hold"]
        else "NOT SEALABLE"
    )
    lines.append(f"**Verdict: {verdict}.**")
    lines.append("")
    lines.append("## Sweeps")
    lines.append("")
    for name, sweep in record["sweeps"].items():
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append(sweep["effect"] + ".")
        lines.append("")
        lines.append("| grid point | S1 pass rate | seam half | texture half | mean margin |")
        lines.append("|---|---|---|---|---|")
        for point, rate, s, t, margin in zip(
            sweep["grid"],
            sweep["pass_rate"],
            sweep["seam_half_pass_rate"],
            sweep["texture_half_pass_rate"],
            sweep["mean_statistic"],
            strict=True,
        ):
            lines.append(f"| {point:g} | **{rate:.2f}** | {s:.2f} | {t:.2f} | {margin:+.3f} |")
        lines.append("")
        lines.append(
            f"Monotone non-decreasing: **{'yes' if sweep['monotone_non_decreasing'] else 'NO'}**"
        )
        lines.append("")
    lines.append("## Controls")
    lines.append("")
    for name, control in record["controls"].items():
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append(control.get("attack") or control.get("control", "") + ".")
        lines.append("")
        lines.append(f"*Requirement.* {control['requirement']}.")
        lines.append("")
        lines.append(f"- S1 pass rate: **{control['pass_rate']:.2f}**")
        for key in (
            "texture_fails_above_rate",
            "self_referential_bar_pass_rate",
            "seam_half_vacuous_rate",
        ):
            if key in control:
                lines.append(f"- {key.replace('_', ' ')}: **{control[key]:.2f}**")
        lines.append(f"- Holds: **{'yes' if control['holds'] else 'NO'}**")
        lines.append("")
    lines.append("## What is NOT swept, and why")
    lines.append("")
    lines.append(record["not_swept"])
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    sealed = rulers.sealed_from_sources()
    yoy = panel_yoy(campaign_source())
    result = run_sweeps(yoy, sealed)
    sweeps, controls = result["sweeps"], result["controls"]
    failures = [n for n, s in sweeps.items() if not s["monotone_non_decreasing"]]
    broken = [n for n, c in controls.items() if not c["holds"]]
    record = {
        "schema": "stage2-rulers-antitest-1",
        "obligation": (
            "exam section 6.1, carried into D-SP-11: before a judge is sealed, sweep the "
            "property the judge claims to measure and confirm the pass rate increases in it. "
            "D-SP-11's charter adds two: a seam-worsening sweep must fail the bar "
            "monotonically, and a seam-hiding-by-noise-inflation attack must also fail"
        ),
        "rule": (
            "S1 asks whether a seam is DISTINGUISHABLE from an ordinary historical "
            "month-transition, which is a two-sided property, so its pass region is an "
            "interval and a single sweep of 'more of the effect' would be non-monotone by "
            "construction. Each sweep therefore runs TOWARD fidelity from one side and the "
            "pass rate must not fall. The noise-inflation attack is a CONTROL: its pass rate "
            "is required to be zero and its failure required to be on the upper side of the "
            "texture half, so it is excluded from the monotonicity gate and carries its own "
            "boolean"
        ),
        "n_replicates": N_REPLICATES,
        "n_decades": N_DECADES,
        "decade_months": DECADE_MONTHS,
        "mean_block_months": MEAN_BLOCK_MONTHS,
        "seeds": _SEEDS,
        "anchor": {
            "n_jumps": int(rulers.panel_adjacent_jumps(yoy).size),
            "digest": rulers.anchor_digest(rulers.panel_adjacent_jumps(yoy)),
            "p95_pp": float(np.quantile(rulers.panel_adjacent_jumps(yoy), 0.95)),
            "note": (
                "the p95 IS spine_pilot_report.judge_b2's sealed panel_p95_adjacent_yoy_pp, "
                "0.7433911963542538 -- S1 does not open a second anchor"
            ),
        },
        "thresholds_judged_against": sealed["bars"],
        "parameters_judged_against": sealed["parameters"],
        "sweeps": sweeps,
        "controls": controls,
        "all_monotone": not failures,
        "non_monotone_sweeps": failures,
        "all_controls_hold": not broken,
        "broken_controls": broken,
        "not_swept": (
            "A1R is not swept and cannot be: it is A1's own statistic and A1's own carried "
            "containment band read on a larger batch, so there is no new judging rule to "
            "anti-test -- what changed is the batch size, and its adequacy is a power "
            "calculation rather than a sweep. The twelve sealed bars are byte-frozen and are "
            "deliberately not re-swept, the reason a carried bar exists"
        ),
        "not_blind": (
            "DISCLOSED: D-SP-10's own results document already published this engine's seam "
            "and contiguous p95 (1.9143 and 0.6956 against a panel p95 of 0.7434), so S1 was "
            "NOT designed blind to the numbers it would read. The band is nonetheless a pure "
            "function of the panel and of a sample size -- no generated quantity enters its "
            "derivation -- and both endpoints of both sweeps were fixed by the construction "
            "(fidelity at 1.0) rather than chosen to land anywhere"
        ),
    }
    OUT_JSON.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    _write_markdown(record)
    for name, sweep in sweeps.items():
        rates = ", ".join(f"{r:.2f}" for r in sweep["pass_rate"])
        flag = "OK" if sweep["monotone_non_decreasing"] else "NOT MONOTONE"
        print(f"sweep   {name:28s} [{rates}]  {flag}")
    for name, control in controls.items():
        print(
            f"control {name:28s} pass_rate={control['pass_rate']:.2f}  "
            f"{'OK' if control['holds'] else 'BROKEN'}"
        )
    print(f"all monotone: {not failures} | all controls hold: {not broken}")
    if failures or broken:
        raise SystemExit(f"NOT SEALABLE: non-monotone {failures}, broken controls {broken}")


if __name__ == "__main__":
    main()
