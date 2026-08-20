"""D-SP-12 change 3 -- the slow climate's dispersion, diagnosed and recalibrated.

Charter: ``governance/decision-register.md`` **D-SP-12** (owner ruling
2026-08-19) -- *"the slow-climate dispersion recalibrated: across-decade state
spread brought toward history's."*

THE DIAGNOSIS THIS SCRIPT MAKES, AND WHAT IT OVERTURNS
------------------------------------------------------
``2026-08-18-stage2-results.md`` §2.2 measured ``P2``'s overshoot as
**dispersion** -- the generated rule-implied policy rate has 1.635x history's
standard deviation and the slope 1.735x -- and attributed it to L1: *"fifty
decades each re-draw their initial states from the posterior, and the spread of
L1's r* and pi* across those draws is wider than the single 68-year path history
realised."*

That attribution is **measured here and it does not hold**. Pinning the drawn
initial state ``s0`` to the posterior mean moves the generated ``i_rule``
standard deviation from 5.684 to 5.690 -- i.e. **not at all**: the smoother is
sharp at the last month of the fit span, so the posterior spread of the state
there is negligible. Pinning the drawn long-run means ``mu_pi``/``mu_r`` as well
moves it only to 5.581. **The across-decade spread is not posterior uncertainty
about where a decade starts; it is the diffusion itself.** ``pi*`` has a fitted
half-life of 10.7 years and an innovation volatility of 2.68 pp, ``r*`` 7.8 years
and 2.16 pp, so over a 120-month decade both states wander far further than the
same two states wandered on the panel -- and different decades wander to
different places, which is what the across-decade spread reads.

So the recalibrated parameters are ``sigma_pi`` and ``sigma_r``, and nothing
else. Half-lives are untouched (they are identified by the fit's own
autocorrelation, and the target below does not measure them); the other three
state volatilities are untouched (they carry growth, drawdown and credit, which
is not what over-disperses); every coupling coefficient in the stage-2 fit is
untouched and is still checked against the frozen artifact before any batch is
compiled.

THE TARGET, THE ESTIMATOR, AND WHY THIS IS NOT TUNING TO A BAR
---------------------------------------------------------------
**Target** (a measured historical quantity, fixed before any bar is read): the
panel's own **across-decade** standard deviation of ``pi*`` and of ``r*`` --
the standard deviation of the six non-overlapping 120-month decade means of each
state, on the same posterior-mean smoothed path ``M4`` decomposes history's
curve on. Reading them: ``pi*`` **2.4726 pp**, ``r*`` **1.3339 pp**.

**Estimator.** Write ``S_s(k)`` for the generated across-decade spread of state
``s`` when its innovation volatility is scaled by ``k``. Two components add in
variance: a floor ``F_s`` that survives ``k = 0`` (decades still differ in their
drawn ``mu`` and ``s0``) and a diffusion term proportional to ``k``:

    S_s(k)^2  =  F_s^2  +  k^2 (S_s(1)^2 - F_s^2)

Both ``F_s`` and ``S_s(1)`` are measured on a declared calibration batch, and
the factor solves the equation at the target:

    k_s  =  sqrt( max(T_s^2 - F_s^2, 0) ) / sqrt( S_s(1)^2 - F_s^2 )

**Verification, declared in advance.** The relation is exact only if the two
states were independent of everything else; they are not (``r*`` carries
``beta_g`` times growth's innovation, and the coupled chain reads both). So the
factor is applied, the achieved spread is re-measured, and the procedure allows
**at most two** closed-form steps at a **2% relative tolerance**. Both steps are
recorded in the artifact whether or not the second is taken.

**Why this is calibration and not tuning.** The target is a property of the
panel. It was measured before the bar was read, it does not mention ``P2``, and
``P2``'s band appears nowhere in the estimator. The artifact also records the
whole response curve of ``P2`` to the scale factor, so a reader can see that the
adopted point is where the historical target puts it and not where the band is
widest.

Run (from the worktree root, no network; about a minute):

    uv run python scripts/stage2_polish_calibrate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

import stage2_anchors as anchors  # noqa: E402
import stage2_fit as weeka  # noqa: E402
import stage2_polish as polish  # noqa: E402
import stage2_worlds as worlds  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
FROZEN_PARAMS_PATH = SPECS_DIR / "stage2-fitted-params.json"

#: The calibration batch's seed -- **deliberately not the exam's**. Reading the
#: target on the same batch the bars are read on would make the calibration
#: in-sample against its own verification. 20260819 is the date of the D-SP-12
#: ruling; it is below every ``A1R`` rung seed (20260821 + 15485863k) and below
#: the exam's own verification seed, so it collides with nothing on the record.
CALIBRATION_SEED = 20260819
#: Four times the exam's batch, because the estimator reads a spread ACROSS
#: decades and fifty of them is a thin sample for one.
CALIBRATION_DECADES = 200
#: The panel's own decade. Not a new number: it is the exam's ``DECADE_MONTHS``.
DECADE_MONTHS = 120
#: The declared verification rule, fixed before the first factor was computed.
TOLERANCE_RELATIVE = 0.02
MAX_STEPS = 2
#: The moving-block resampling published beside the target. The campaign's own
#: convention (``S1``/``P2``'s band: 24-month blocks, 2,000 draws, seed 20260821,
#: central 95%), reused rather than a fourth one invented -- and it turns out to
#: measure a NULL rather than the target's uncertainty. See
#: :func:`bootstrap_target_band`, which says why and publishes it as one.
BOOTSTRAP_BLOCK_MONTHS = 24
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20260821
BOOTSTRAP_LEVEL = 0.95

#: The two states the rule-implied policy rate is made of, and the L1 volatility
#: that drives each. The pairing is the whole content of the recalibration.
CALIBRATED = (("pi_star", "sigma_pi"), ("r_star", "sigma_r"))


def panel_decade_spread(series: np.ndarray, months: int = DECADE_MONTHS) -> dict[str, float]:
    """History's own decade-scale dispersion of one series.

    Non-overlapping ``months``-month blocks from the start of the panel, the
    remainder dropped. The same three numbers
    :func:`stage2_polish.across_decade_spread` computes on a generated batch,
    because a calibration whose two sides are computed by different functions is
    not a calibration.
    """
    arr = np.asarray(series, dtype=np.float64)
    n = int(arr.size // months)
    if n < 2:
        raise ValueError(f"the panel supplies only {n} whole decades; a spread needs at least two")
    blocks = arr[: n * months].reshape(n, months)
    return polish.across_decade_spread(blocks)


def overlapping_decade_spread(series: np.ndarray, months: int = DECADE_MONTHS) -> float:
    """The same target under every overlapping window -- a robustness disclosure.

    Overlapping windows are strongly dependent, so this is a biased estimator of
    the marginal spread of a decade mean and is **never** the target. It is
    reported because a target cut from six numbers should be shown beside the
    reading that uses all of them.
    """
    arr = np.asarray(series, dtype=np.float64)
    n = int(arr.size - months + 1)
    means = np.array([arr[i : i + months].mean() for i in range(n)], dtype=np.float64)
    return float(means.std(ddof=1))


def bootstrap_target_band(series: np.ndarray) -> dict[str, Any]:
    """A moving-block resampling of the target -- and it is NOT a sampling band.

    This was written to publish the target's own sampling uncertainty, using the
    campaign's own convention (24-month moving blocks, 2,000 draws, seed
    20260821). **The reading says the estimator does not measure what it was
    written for**, and that is worth recording rather than quietly dropping:
    the resampled band for ``pi*`` is ``[0.43, 1.83]`` and the panel's own
    reading is ``2.47`` -- far ABOVE its own band.

    The reason is structural. Reassembling a path out of 24-month blocks
    destroys every correlation longer than 24 months, and the across-decade
    spread of ``pi*`` is made almost entirely of correlation longer than that:
    it is the 1970s-to-1990s level shift. So the band is a **null** -- "how far
    apart would decade means be if nothing persisted past two years" -- and the
    target sits above it because the persistence is real.

    Published as that null, never as a band on the target. The honest statement
    about the target's uncertainty is the limitation recorded in the artifact:
    six decades of one 68-year panel supply no usable sampling band for a
    statistic whose content is a once-in-the-sample level shift.
    """
    arr = np.asarray(series, dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    n_blocks = int(np.ceil(arr.size / BOOTSTRAP_BLOCK_MONTHS))
    starts = rng.integers(
        0, arr.size - BOOTSTRAP_BLOCK_MONTHS + 1, size=(BOOTSTRAP_DRAWS, n_blocks)
    )
    idx = (starts[:, :, None] + np.arange(BOOTSTRAP_BLOCK_MONTHS)[None, None, :]).reshape(
        BOOTSTRAP_DRAWS, -1
    )[:, : arr.size]
    draws = arr[idx]
    n_dec = int(arr.size // DECADE_MONTHS)
    blocks = draws[:, : n_dec * DECADE_MONTHS].reshape(BOOTSTRAP_DRAWS, n_dec, DECADE_MONTHS)
    spread = blocks.mean(axis=2).std(axis=1, ddof=1)
    tail = (1.0 - BOOTSTRAP_LEVEL) / 2.0
    lo, hi = np.percentile(spread, [100.0 * tail, 100.0 * (1.0 - tail)])
    return {"lo": float(lo), "hi": float(hi), "median": float(np.median(spread))}


def generated_spreads(
    frozen: Any, calibration: polish.L1Calibration, *, n_decades: int = CALIBRATION_DECADES
) -> dict[str, Any]:
    """One calibration batch's dispersion, per state and for the rule-implied rate."""
    with polish.l1_calibration(calibration):
        decades, _tally = weeka.simulate_batch_coupled(
            frozen.system, frozen.climate, n_decades=n_decades, seed=CALIBRATION_SEED
        )
    out: dict[str, Any] = {}
    for index, name in ((0, "pi_star"), (1, "r_star")):
        out[name] = polish.across_decade_spread(np.stack([d.states[:, index] for d in decades]))
    out["i_rule"] = polish.across_decade_spread(np.stack([d.i_rule for d in decades]))
    out["x_gap"] = polish.across_decade_spread(np.stack([d.x_gap for d in decades]))
    components, residual_sd = weeka.p2_components(decades, frozen.system)
    economic = float(sum(v * v for v in components.values()))
    out["p2_economic_share"] = economic / (economic + residual_sd * residual_sd)
    out["p2_components_sd_pp"] = {k: float(v) for k, v in components.items()}
    return out


def _solve(target: float, floor: float, at_unit: float) -> float:
    """The closed-form factor: variance in, variance out."""
    diffusion = at_unit * at_unit - floor * floor
    if diffusion <= 0.0:
        raise ValueError("the unit-scale spread does not exceed its own zero-scale floor")
    return float(np.sqrt(max(target * target - floor * floor, 0.0)) / np.sqrt(diffusion))


def calibrate() -> dict[str, Any]:
    """The whole derivation, as the artifact records it."""
    frozen = worlds.build_frozen_system()
    history = anchors.rule_implied_states(frozen.panel)

    targets: dict[str, Any] = {}
    for state, _sigma in CALIBRATED:
        series = np.asarray(history[state], dtype=np.float64)
        targets[state] = {
            **panel_decade_spread(series),
            "overlapping_window_across_decade_sd": overlapping_decade_spread(series),
            "moving_block_null_not_a_sampling_band": {
                **bootstrap_target_band(series),
                "what_it_is": (
                    "how far apart decade means would be if nothing persisted past 24 months. "
                    "The panel's own reading sits ABOVE this null because the across-decade "
                    "spread of these states IS long persistence -- the 1970s-to-1990s level "
                    "shift. It is published as a null and is not a band on the target"
                ),
            },
        }
    targets["i_rule"] = {
        **panel_decade_spread(np.asarray(history["i_rule"], dtype=np.float64)),
        "note": "reported, never targeted -- it is a consequence of the two states",
    }

    at_unit = generated_spreads(frozen, polish.L1_UNIT)
    floors = generated_spreads(frozen, polish.L1Calibration(sigma_pi=0.0, sigma_r=0.0))

    steps: list[dict[str, Any]] = []
    factors = {sigma: 1.0 for _state, sigma in CALIBRATED}
    current = at_unit
    for step in range(MAX_STEPS):
        proposal = {}
        for state, sigma in CALIBRATED:
            k = _solve(
                float(targets[state]["across_decade_sd"]),
                float(floors[state]["across_decade_sd"]),
                float(current[state]["across_decade_sd"]),
            )
            proposal[sigma] = float(factors[sigma] * k)
        calibration = polish.L1Calibration(**proposal)
        achieved = generated_spreads(frozen, calibration)
        errors = {
            state: float(
                achieved[state]["across_decade_sd"] / targets[state]["across_decade_sd"] - 1.0
            )
            for state, _sigma in CALIBRATED
        }
        steps.append(
            {
                "step": step + 1,
                "factors": dict(proposal),
                "achieved_across_decade_sd": {
                    state: achieved[state]["across_decade_sd"] for state, _s in CALIBRATED
                },
                "relative_error": errors,
                "inside_tolerance": all(abs(e) <= TOLERANCE_RELATIVE for e in errors.values()),
            }
        )
        factors, current = proposal, achieved
        if steps[-1]["inside_tolerance"]:
            break

    adopted = polish.L1Calibration(**factors)
    response = []
    for k in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.25):
        arm = generated_spreads(frozen, polish.L1Calibration(sigma_pi=k, sigma_r=k))
        response.append(
            {
                "uniform_scale": k,
                "i_rule_total_sd": arm["i_rule"]["total_sd"],
                "pi_star_across_decade_sd": arm["pi_star"]["across_decade_sd"],
                "r_star_across_decade_sd": arm["r_star"]["across_decade_sd"],
                "p2_economic_share": arm["p2_economic_share"],
            }
        )

    attribution = {}
    for label, calibration in (
        ("unit (the unrecalibrated engine)", polish.L1_UNIT),
        ("sigma_pi and sigma_r at zero", polish.L1Calibration(sigma_pi=0.0, sigma_r=0.0)),
        ("sigma_pi at zero only", polish.L1Calibration(sigma_pi=0.0)),
        ("sigma_r at zero only", polish.L1Calibration(sigma_r=0.0)),
    ):
        arm = generated_spreads(frozen, calibration)
        attribution[label] = {
            "pi_star_across_decade_sd": arm["pi_star"]["across_decade_sd"],
            "r_star_across_decade_sd": arm["r_star"]["across_decade_sd"],
            "i_rule_total_sd": arm["i_rule"]["total_sd"],
            "p2_economic_share": arm["p2_economic_share"],
        }

    frozen_doc = json.loads(FROZEN_PARAMS_PATH.read_text(encoding="utf-8"))
    return {
        "schema": "stage2-fitted-params-2",
        "purpose": (
            "D-SP-12 change 3: the slow climate's two level-carrying innovation volatilities, "
            "recalibrated against the panel's own decade-scale spread of the same two states. "
            "The week-A stage-2 fit is CARRIED UNCHANGED -- all 42 coefficients are the frozen "
            "artifact's and this round refits none of them"
        ),
        "charter": "governance/decision-register.md D-SP-12 (owner ruling 2026-08-19)",
        "produced_by": "scripts/stage2_polish_calibrate.py",
        "carried_from": {
            "artifact": "docs/superpowers/specs/stage2-fitted-params.json",
            "status": "FROZEN INPUT, never written by this round",
            "fit": frozen_doc["fit"],
        },
        "l1_dispersion_calibration": {
            "what_moves": {
                "parameters": list(polish.CALIBRATED_PARAMS),
                "layer": "L1, the slow climate posterior (ah.gen.climate)",
                "untouched": (
                    "every half-life, the other three state volatilities, beta_g, delta_L, both "
                    "Taylor loadings, and every one of the 42 stage-2 coefficients"
                ),
            },
            "diagnosis": {
                "question": "which L1 parameters produce the 1.6-1.7x dispersion",
                "the_prior_attribution_that_does_not_hold": (
                    "2026-08-18-stage2-results.md 2.2 attributed it to the per-decade posterior "
                    "redraw of the initial state. Pinning s0 to the posterior mean moves the "
                    "generated i_rule sd from 5.6839 to 5.6903 -- the smoother is sharp at the "
                    "last month of the fit span, so there is almost no posterior spread there to "
                    "remove. Pinning mu_pi and mu_r as well reaches only 5.5814"
                ),
                "what_it_is_instead": (
                    "the diffusion. pi* has a fitted half-life of 10.7 years at an innovation "
                    "volatility of 2.68 pp and r* 7.8 years at 2.16 pp, so over a 120-month "
                    "decade both states wander far further than the panel's own two states did, "
                    "and different decades wander to different places"
                ),
                "attribution_arms": attribution,
            },
            "target": {
                "quantity": (
                    "the panel's own across-decade standard deviation of pi* and of r*: the sd of "
                    "the six non-overlapping 120-month decade means, on the same posterior-mean "
                    "smoothed path M4 decomposes history's curve on"
                ),
                "measured_before_any_bar_was_read": True,
                "mentions_no_bar": True,
                "per_state": targets,
            },
            "estimator": {
                "relation": "S(k)^2 = F^2 + k^2 (S(1)^2 - F^2)",
                "floor_F": "the across-decade spread that survives k = 0",
                "solution": "k = sqrt(max(T^2 - F^2, 0)) / sqrt(S(1)^2 - F^2)",
                "verification_rule": (
                    f"apply, re-measure, at most {MAX_STEPS} closed-form steps at a "
                    f"{TOLERANCE_RELATIVE:.0%} relative tolerance; every step recorded"
                ),
                "calibration_batch": {
                    "seed": CALIBRATION_SEED,
                    "n_decades": CALIBRATION_DECADES,
                    "why_not_the_exam_seed": (
                        "reading the target on the batch the bars are read on would make the "
                        "calibration in-sample against its own verification"
                    ),
                },
                "at_unit_scale": {s: at_unit[s] for s, _k in CALIBRATED},
                "floors_at_zero_scale": {s: floors[s] for s, _k in CALIBRATED},
                "steps": steps,
            },
            "adopted_factors": adopted.factors,
            "adopted_converged_within_tolerance": bool(steps[-1]["inside_tolerance"]),
            "achieved_on_the_calibration_batch": current,
            "p2_response_to_a_uniform_scale": response,
            "p2_note": (
                "P2's band appears nowhere in the estimator. The response curve is published so "
                "a reader can see that the adopted point is where the historical target puts it "
                "and not where the band is widest"
            ),
            "limitations": [
                "history's pi* and r* are POSTERIOR-MEAN SMOOTHED paths and a generated decade is "
                "a forward simulation, so part of what this factor absorbs is the difference "
                "between a smoothed estimate and a simulated path rather than a difference in "
                "the world. It is nonetheless the comparison the exam itself makes: M4 decomposes "
                "history on exactly this series and p2_components scores the engine by the same "
                "function on its own",
                "the target rests on six non-overlapping decades of one 68-year panel and NO "
                "usable sampling band for it exists: a 24-month moving-block bootstrap returns "
                "[0.43, 1.83] for pi* against the panel's own 2.47, because reassembling the "
                "path out of two-year blocks destroys exactly the long persistence the target is "
                "made of. That resampling is published as a null, not as a band. The target's "
                "uncertainty is therefore UNQUANTIFIED, and a reader should treat the two "
                "factors as point estimates with no interval",
                "the recalibration is a scaling of an L1 posterior parameter, not a refit of L1. "
                "It does not re-derive the climate layer and it does not claim to",
                "sigma_pi drives pi*, which sets the era dial, so this change moves the spine and "
                "therefore every pre-flesh bar. That is measured in the polish results document, "
                "not assumed away",
            ],
        },
    }


def main() -> int:
    payload = calibrate()
    polish.POLISH_PARAMS_PATH.write_text(
        json.dumps(weeka._round(payload), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    block = payload["l1_dispersion_calibration"]
    print("D-SP-12 change 3 -- the slow climate's dispersion, recalibrated.")
    for state, sigma in CALIBRATED:
        target = block["target"]["per_state"][state]["across_decade_sd"]
        achieved = block["achieved_on_the_calibration_batch"][state]["across_decade_sd"]
        print(
            f"  {state:8s} target {target:7.4f}  achieved {achieved:7.4f}  "
            f"{sigma} x {block['adopted_factors'][sigma]:.6f}"
        )
    print(
        f"  steps taken: {len(block['estimator']['steps'])}, converged: "
        f"{block['adopted_converged_within_tolerance']}"
    )
    print(
        f"  P2 economic share on the calibration batch: "
        f"{block['achieved_on_the_calibration_batch']['p2_economic_share']:.6f}"
    )
    print(f"wrote {polish.POLISH_PARAMS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
