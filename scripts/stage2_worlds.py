"""Stage 2, week C: the stage-2 world builder -- the coupled spine, FLESHED.

Spec: ``docs/superpowers/specs/2026-08-17-stage2-coupled-system-design.md``,
judged by ``docs/superpowers/specs/2026-08-18-stage2-exam-delta.md`` and the ten
bars it carries byte-frozen from
``docs/superpowers/specs/2026-08-17-spine-v2-exam.md``.

**What this module is.** Week A fitted the coupled macro system and read the
eight bars a bare spine can be judged on. Four bars need something week A does
not produce: ``A1`` and ``A2`` need the **flesh** -- verbatim real months of
asset returns compiled onto the spine -- ``R2`` needs the compiled ensemble and
the panel source, and ``R1`` needs the institutional twin driven off a compiled
world. This module composes the object all four need: **the coupled climate +
season path of week A, driving the platform's own quadrant-conditioned block
sampler.**

**Composition, not promotion.** Nothing in ``src/`` is edited by this campaign.
Week C substituted exactly one function at runtime -- ``ah.gen.spine.sample_spine``,
the spine sampler that decides *which climate and which growth path* the flesh is
conditioned on -- and let the platform's block sampler run byte-verbatim
underneath it. **D-SP-10 (owner ruling 2026-08-18) changes that**: the funded fix
is to the block sampler itself, so this module now also carries a composed
``_draw`` (:func:`_reach_draw`) that the stage-2 spine factory uses in place of
``ah.gen.spine.SpineBootstrap._draw``. Everything else the platform supplies --
pools, percentile strata, the severity table, the hazard corrections, the join
tolerances, the era filter, the forced-re-entry rule -- is imported and called,
never re-implemented. The substitutions are installed by the :func:`stage2_flesh`
context manager and removed on exit. **Promoting any of it into ``src/`` is a
separate owner release event, after a pass, and is not done here.**

**Why a composed ``_draw`` is not a fork, and the guard that keeps it honest.**
A copy of sealed-adjacent machinery drifts, and week C refused one for exactly
that reason. The copy is only admissible because it is pinned:
``REACH_BASELINE`` runs the platform's own rule and
``tests/test_stage2_weekc_composition.py::test_the_baseline_reach_draw_is_the_platforms_own``
compiles a batch both ways and demands **bit-identical row indices**. If the
platform's ``_draw`` ever changes, that test fails rather than this module
quietly diverging from it.

**The one interface that forces a choice, and the minimal-change option taken.**
``SpineBootstrap._draw`` derives each month's quadrant itself, through
``ah.gen.spine.spine_quadrant``, from an L1 state row and a six-label regime
code: hot is ``pi_star - mu_pi > BACKDROP_MARGIN_PP`` and expanding is "the
label is outside ``{REC, CRI}``". Stage 2's own season -- the one the sealed
``grader_v2`` judges, and the one every week-A bar was read on -- is
``(expanding << 1) | (yoy > era_threshold_pp)`` where ``yoy = pi* + x`` is the
coupled system's inflation, ``era_threshold_pp`` is grader_v2's era line
(3.3513 pp) and the contracting axis is grader_v2's ``{REC, CRI, STAG}``. The
two disagree, so handing ``_draw`` the stage-2 decade raw would condition the
flesh on a **different classification from the one the exam judges**.

Three options were available: re-implement ``_draw``'s loop in this script with
the stage-2 quadrant inlined (a copy of sealed-adjacent machinery, which drifts);
edit ``src/`` (out of scope for the campaign, and a release event); or **project
the stage-2 decade into the ``SpinePaths`` contract so that the machinery's own
formulas evaluate to the stage-2 season**. The third is taken, because it is the
only one under which not one line of the flesh changes. The projection is:

* ``states[:, :, 0]``  <- ``yoy - era_threshold_pp + BACKDROP_MARGIN_PP`` with
  ``mu_pi = 0``, so ``spine_quadrant``'s hot test ``col0 - mu_pi > 0.5`` is
  ``yoy > era_threshold_pp`` **exactly** -- same strict inequality, no epsilon.
  The same substitution carries the severity table's ``infl`` condition, which
  the pilot world already documents as a duplicate of the quadrant's hot bit.
* ``labels`` <- ``EXP`` where the coupled chain's growth axis is expanding and
  ``REC`` where it is contracting, so ``label not in {REC, CRI}`` is that axis.
  The projection is used **only** for the quadrant: the compiled ensemble's own
  regime record is the panel's labels at the selected rows, never these.
* every other column of ``states`` is the coupled decade's real L1 state, so the
  severity table's ``credit`` condition still reads the true credit gap.

The projection is **verified in code, not argued**:
:func:`spine_paths_from_decades` asserts month by month that
``spine_quadrant(projected) == stage-2 season`` for every decade before the
flesh is allowed to see it. If the projection ever stopped being exact, the run
stops rather than producing a quietly mis-conditioned world.

**The frozen input.** ``docs/superpowers/specs/stage2-fitted-params.json`` is
week A's artifact and is read-only here. :func:`build_frozen_system` rebuilds
the coupled system by running week A's own deterministic estimator and then
**asserts every fitted coefficient against that artifact** at week A's own
tolerance (``stage2_fit.ANCHOR_TOLERANCE``, 1e-11, the artifact's twelve-decimal
rounding). Week C therefore cannot refit anything: a system that does not
reproduce the frozen numbers raises.

Import-safe: importing this module reads no data, draws no random number and
writes no file.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

import stage2_fit as weeka  # noqa: E402
from spine_v2_fit import Panel, build_panel, fit_arm, select_curve_lag  # noqa: E402
from spine_v2_grader import season_cells  # noqa: E402
from stage2_anchors import rule_implied_states  # noqa: E402

import ah.gen.spine as spine_module  # noqa: E402
from ah.core.numericworld import NumericWorld, project_numeric  # noqa: E402
from ah.core.worldspec import WorldSpec  # noqa: E402
from ah.data.derive import REGIME_LABELS  # noqa: E402
from ah.gen import stress as stress_module  # noqa: E402
from ah.gen.base import Ensemble  # noqa: E402
from ah.gen.bootstrap import BootstrapSource, campaign_source  # noqa: E402
from ah.gen.spine import (  # noqa: E402
    BACKDROP_MARGIN_PP,
    LAYER_OFFSETS,
    SpineBootstrap,
    SpinePaths,
    SpineRefusal,
    _build_pools,
    _correction_expire,
    _correction_onset,
    percentile_for,
    spine_quadrant,
)
from ah.gen.stress import _segment_for, join_candidates  # noqa: E402
from ah.gen.systems import _pinned_layers  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
PARAMS_PATH = SPECS_DIR / "stage2-fitted-params.json"

#: The one world in the tree that declares both ``x_stress`` and ``x_spine`` --
#: world ...802, "The Hard Landing". It supplies the flesh SPEC (segments, entry
#: percentiles, block length, join tolerances, severity table) for every batch
#: here, and its premise for the batches that are premise-conditioned. R1 and R2
#: are carried byte-frozen on this world, so using any other one would break the
#: only property a carried bar has.
WORLD_PATH = _REPO_ROOT / "src" / "ah" / "presets" / "spine_pilot.json"

#: Premise modes. ``declared`` runs world 802's own premise clause (the arm R1's
#: byte-frozen harness is defined on); ``unconditional`` accepts every attempt,
#: which is week A's own verification arm and the batch the eight pre-flesh bars
#: were read on.
PREMISE_DECLARED = "declared"
PREMISE_UNCONDITIONAL = "unconditional"
PREMISE_MODES = (PREMISE_DECLARED, PREMISE_UNCONDITIONAL)

_EXP_CODE = REGIME_LABELS.index("EXP")
_REC_CODE = REGIME_LABELS.index("REC")


def load_world() -> NumericWorld:
    """World ...802, projected. Read-only; the preset is never rewritten."""
    doc = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    return project_numeric(WorldSpec.model_validate(doc))


# --------------------------------------------------------------------------- #
# the frozen system -- week A's estimator, re-run and checked, never refitted
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FrozenSystem:
    """Week A's coupled system, reproduced and checked against its artifact."""

    system: weeka.CoupledSystem
    panel: Panel
    climate: Any
    hazard: dict[str, Any]
    agreement: dict[str, Any]

    @property
    def era_threshold_pp(self) -> float:
        return float(self.system.engine.era_threshold_pp)


def _drift(name: str, got: float, want: Any, out: dict[str, float]) -> None:
    out[name] = abs(float(got) - float(want))


def _check_frozen(system: weeka.CoupledSystem, hazard: dict[str, Any]) -> dict[str, Any]:
    """Every fitted number, against ``stage2-fitted-params.json``.

    Week A's own ``anchor_agreement`` discipline, turned on week A itself: the
    artifact is the frozen input for week C, so a rebuild that does not
    reproduce it is a stop, not a warning.
    """
    frozen = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))["fit"]
    drifts: dict[str, float] = {}

    infl, want_i = system.inflation, frozen["inflation"]
    _drift("inflation.lam_x", infl.lam_x, want_i["lam_x"], drifts)
    _drift("inflation.persistence", infl.persistence, want_i["persistence_a"], drifts)
    _drift("inflation.intercept", infl.intercept, want_i["intercept"], drifts)
    _drift("inflation.innovation_sd", infl.innovation_sd, want_i["innovation_sd_pp"], drifts)
    _drift("inflation.cbar", infl.cbar, want_i["cbar"], drifts)
    if int(infl.lag_months) != int(want_i["selected_lag_months"]):
        raise weeka.FitError(
            f"the sealed lag rule now selects {infl.lag_months} months against the frozen "
            f"artifact's {want_i['selected_lag_months']}"
        )

    pol, want_p = system.policy, frozen["policy"]
    _drift("policy.intercept", pol.intercept, want_p["intercept"], drifts)
    _drift("policy.persistence", pol.persistence, want_p["persistence_phi_u"], drifts)
    _drift("policy.lam_u", pol.lam_u, want_p["lam_u"], drifts)
    _drift("policy.lam_c", pol.lam_c, want_p["lam_c"], drifts)
    _drift("policy.innovation_sd", pol.innovation_sd, want_p["innovation_sd"], drifts)

    curve, want_c = system.curve, frozen["curve"]
    for name, value in curve.coefficients.items():
        _drift(f"curve.{name}", value, want_c["coefficients"][name], drifts)
    _drift("curve.rho", curve.rho, want_c["rho"], drifts)
    _drift("curve.innovation_sd", curve.innovation_sd, want_c["innovation_sd_pp"], drifts)
    _drift(
        "curve.residual_stationary_sd",
        curve.residual_stationary_sd,
        want_c["residual_stationary_sd_pp"],
        drifts,
    )
    for i, center in enumerate(want_c["centers"]):
        _drift(f"curve.center[{i}]", curve.centers[i], center, drifts)

    for name, value in hazard["coefficients"].items():
        _drift(f"hazard.{name}", float(value), frozen["hazard"]["coefficients"][name], drifts)

    _drift(
        "axis_cycle.expanding",
        system.axis_cycle[1],
        frozen["axis_calibrated_cycle"]["expanding"],
        drifts,
    )
    _drift(
        "axis_cycle.contracting",
        system.axis_cycle[0],
        frozen["axis_calibrated_cycle"]["contracting"],
        drifts,
    )

    worst_name = max(drifts, key=lambda k: drifts[k])
    worst = drifts[worst_name]
    if worst > weeka.ANCHOR_TOLERANCE:
        raise weeka.FitError(
            f"the rebuilt stage-2 system does not reproduce the frozen artifact: "
            f"'{worst_name}' drifts by {worst:.3e} against a tolerance of "
            f"{weeka.ANCHOR_TOLERANCE:.0e}. Week C may not refit anything, so this is a stop"
        )
    return {
        "artifact": str(PARAMS_PATH.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "n_numbers_checked": len(drifts),
        "max_abs_drift": worst,
        "max_abs_drift_at": worst_name,
        "tolerance": weeka.ANCHOR_TOLERANCE,
        "holds": True,
        "note": (
            "week A's parameters are FROZEN INPUT. This rebuild runs week A's own "
            "deterministic estimator and checks every coefficient against the committed "
            "artifact; nothing in week C fits, tunes or scales a parameter"
        ),
    }


def build_frozen_system() -> FrozenSystem:
    """Week A's coupled system, rebuilt and checked. The only entry point."""
    panel = build_panel()
    cells = season_cells(panel.labels, panel.yoy, panel.era_threshold_pp)
    lag = int(select_curve_lag(panel, cells)["selected_lag_months"])
    hazard = fit_arm(cells, panel.z_lagged(lag))
    states = rule_implied_states(panel)
    cycle = weeka._usrec_cycle(panel)
    observed = ~np.isnan(panel.yoy)
    inflation = weeka.fit_inflation_block(states["x_gap"], cycle, observed, "usrec")
    policy = weeka.fit_policy_block(panel.u_hat, states["x_gap"], cycle)
    curve = weeka.fit_stage2_curve(panel, states)
    system = weeka.build_system(panel, hazard, cells, lag, inflation, policy, curve, states, cycle)
    agreement = _check_frozen(system, hazard)
    climate, _regimes = _pinned_layers()
    return FrozenSystem(
        system=system, panel=panel, climate=climate, hazard=hazard, agreement=agreement
    )


# --------------------------------------------------------------------------- #
# the projection: a stage-2 decade, in the SpinePaths contract
# --------------------------------------------------------------------------- #


def spine_paths_from_decades(
    decades: list[weeka.Stage2Decade], era_threshold_pp: float, *, seed: int, attempts: int
) -> SpinePaths:
    """The coupled batch, projected so the flesh's own quadrant IS stage 2's.

    See the module docstring for why the projection exists and what it changes.
    The assertion below is the whole safety of it: for every month of every
    decade the machinery's own ``spine_quadrant`` must return the season the
    coupled chain produced and the sealed grader judges. It is checked before
    the flesh sees the batch, never after.
    """
    if not decades:
        raise weeka.FitError("the flesh needs at least one decade")
    months = int(decades[0].season.size)
    states = np.stack([np.asarray(d.states, dtype=np.float64) for d in decades])
    yoy = np.stack([np.asarray(d.yoy, dtype=np.float64) for d in decades])
    expanding = np.stack([np.asarray(d.expanding, dtype=bool) for d in decades])
    states[:, :, 0] = yoy - float(era_threshold_pp) + BACKDROP_MARGIN_PP
    labels = np.where(expanding, _EXP_CODE, _REC_CODE).astype(np.int64)

    for p, decade in enumerate(decades):
        season = np.asarray(decade.season, dtype=np.int64)
        for m in range(months):
            got = spine_quadrant(states[p, m], int(labels[p, m]), mu_pi=0.0)
            if got != int(season[m]):
                raise weeka.FitError(
                    f"the SpinePaths projection is not exact at decade {p}, month {m}: the "
                    f"flesh would read quadrant {got} where stage 2's season is "
                    f"{int(season[m])}. The flesh must be conditioned on the classification "
                    "the exam judges, so this is a stop"
                )
    return SpinePaths(
        states=states,
        labels=labels,
        cycle=np.zeros((len(decades), months), dtype=np.float64),
        policy=np.zeros((len(decades), months), dtype=np.float64),
        mu_pi=np.zeros(len(decades), dtype=np.float64),
        pi_actual=yoy,
        attempts=int(attempts),
        seed=int(seed),
    )


# --------------------------------------------------------------------------- #
# D-SP-10 -- the conditioning-reach engine
# --------------------------------------------------------------------------- #
#
# THE DEFECT, stated as the mechanism rather than as the number. The platform's
# block sampler consults the spine's quadrant when it OPENS a block and at no
# other time: month 0, a join, a forced re-entry. Every other month is
# ``previous + 1`` -- the panel's own next row, taken for no reason but
# contiguity. Week C measured what that costs: 494 of 6,000 months selected for
# their quadrant (8.2%), and the decade's declared inflation story agreeing with
# the months actually drawn on 60.6% of judged months against 59.2% expected of
# two independent dials.
#
# THE STRUCTURAL FACT that decides between the candidate fixes, and it is not in
# the week-C record. The panel's "hot" bit and the era-safe join's era bucket are
# THE SAME PREDICATE -- both are ``panel YoY > era_threshold_pp`` (see
# ``ah.gen.spine.panel_quadrant`` and ``sample_months``'s ``era_bucket``). So an
# era-safe join can never cross the era line: a join into a hot quadrant from a
# cool row has every candidate filtered out, and the block simply continues.
# **The compiler is structurally unable to FOLLOW the spine's inflation dial by
# joining.** Adding joins -- shorter blocks, or breaking on divergence -- cannot
# repair that, because the repair is forbidden at exactly the months that matter.
# What CAN cross the era line is real history's own contiguity: a stretch of
# months that crosses the line by itself, on the panel, in the same month the
# spine does. That is not a teleport and the era filter never sees it.
#
# Hence the three designs below, and the fourth that is their composition.


#: The sealed week-C rule: condition at block starts only. Kept runnable, and
#: pinned bit-for-bit against the platform's own ``_draw`` by the composition
#: suite -- this is the anti-drift device for the whole composed loop.
REACH_BASELINE = "baseline"
#: (a) Shorter blocks: more block starts, hence more conditioning points. The
#: knob is the world's declared ``mean_block_months``, so this arm is measured
#: through an override rather than adopted -- block length is an owner
#: declaration (ruling 2026-08-15, on the generator-only coherence study), and
#: R1/R2 are carried byte-frozen on the world that declares it.
REACH_SHORT_BLOCKS = "short-blocks"
#: (c) Mid-block divergence break: when the block's next month would land on a
#: panel row whose quadrant is NOT the spine's, end the block and re-select
#: through the ordinary era-safe join. Nothing is teleported: with no candidate
#: reachable the block continues, and that month is counted as an unresolved
#: divergence rather than papered over.
REACH_DIVERGENCE_BREAK = "divergence-break"
#: (b) Whole-block path matching: choose the ENTRY by how far the panel's own
#: forward quadrant path tracks the spine's coming months, not by its first
#: month alone.
REACH_PATH_MATCH = "path-match"
#: (b) + (c).
REACH_PATH_MATCH_BREAK = "path-match+divergence-break"
#: (d) (b) + (c) + ANTICIPATION: when the era filter leaves a divergence
#: unjoinable -- which is most of them, because the era bucket and the
#: quadrant's hot bit are the same predicate -- move instead to a month from
#: which real history WALKS INTO the spine's quadrant, chosen by forward
#: agreement over the look-ahead. The month itself stays mis-conditioned and is
#: still counted as unreached; what changes is the months after it.
REACH_ANTICIPATE = "path-match+break+anticipate"
#: (e) (d) with the era bucket dropped from the join filter, keeping only the
#: declared level bound (|dYoY| <= join_yoy_max_pp). **A DISCLOSURE ARM, never
#: adopted**: it prices the constraint D-SP-10 preserved, and relaxing an
#: era-safe join is an owner ruling, not a campaign's choice.
REACH_ERA_RELAXED = "era-relaxed(disclosure)"

#: The look-ahead used by the path-matching arms, in months. Six is the world's
#: own declared mean block length -- the horizon over which an entry is expected
#: to be used -- not a tuned number.
DEFAULT_MATCH_HORIZON = 6


@dataclass(frozen=True)
class ReachDesign:
    """One conditioning-reach design, as the composed ``_draw`` reads it.

    ``match_horizon`` = 0 turns path matching off; ``break_on_divergence`` =
    False turns the mid-block break off; both off with no block override IS the
    platform's sealed rule.
    """

    name: str
    match_horizon: int = 0
    break_on_divergence: bool = False
    block_months_override: float | None = None
    anticipate: bool = False
    era_relaxed_joins: bool = False

    @property
    def is_baseline(self) -> bool:
        return (
            self.match_horizon <= 0
            and not self.break_on_divergence
            and self.block_months_override is None
            and not self.anticipate
            and not self.era_relaxed_joins
        )


def reach_design(name: str, *, match_horizon: int | None = None, block_months: float | None = None):
    """The named design. The only constructor callers should use."""
    horizon = DEFAULT_MATCH_HORIZON if match_horizon is None else int(match_horizon)
    if name == REACH_BASELINE:
        return ReachDesign(name)
    if name == REACH_SHORT_BLOCKS:
        if block_months is None:
            raise ValueError("the short-blocks arm needs an explicit block_months")
        return ReachDesign(f"{name}({block_months:g})", block_months_override=float(block_months))
    if name == REACH_DIVERGENCE_BREAK:
        return ReachDesign(name, break_on_divergence=True, block_months_override=block_months)
    if name == REACH_PATH_MATCH:
        return ReachDesign(name, match_horizon=horizon, block_months_override=block_months)
    if name == REACH_PATH_MATCH_BREAK:
        return ReachDesign(
            name,
            match_horizon=horizon,
            break_on_divergence=True,
            block_months_override=block_months,
        )
    if name == REACH_ANTICIPATE:
        return ReachDesign(
            name,
            match_horizon=horizon,
            break_on_divergence=True,
            block_months_override=block_months,
            anticipate=True,
        )
    if name == REACH_ERA_RELAXED:
        return ReachDesign(
            name,
            match_horizon=horizon,
            break_on_divergence=True,
            block_months_override=block_months,
            anticipate=True,
            era_relaxed_joins=True,
        )
    raise ValueError(f"unknown reach design {name!r}")


#: The design D-SP-10 adopts. See ``docs/superpowers/specs/2026-08-18-stage2-reach-results.md``
#: for the frontier the four arms trace and why this is the point on it.
ADOPTED_REACH = reach_design(REACH_ANTICIPATE)


def _path_prefix_pick(
    candidates: np.ndarray,
    cells: np.ndarray,
    spine_q: np.ndarray,
    m: int,
    horizon: int,
    rng: np.random.Generator,
) -> int:
    """One entry, chosen for how far its panel path tracks the spine's.

    Every candidate already matches the spine's quadrant AT ``m`` -- pool
    membership is exactly that (``_build_pools``) -- so the prefix length is at
    least 1 and the maximum is always attained: **this can never empty a pool,
    and it is therefore never a refusal in disguise.** Among the candidates that
    tie at the longest matching prefix the draw is uniform, on the block stream,
    one ``rng.integers`` call -- the same single call the platform makes, so the
    two arms consume the block tape at the same rate.

    A candidate whose forward months run off the panel's end stops matching
    there. That is not a special case bolted on for ``R2``: a block entered
    within a few rows of the panel edge genuinely cannot track a ten-year spine,
    and the forced-re-entry rule is what the platform does when it happens.
    """
    if horizon <= 1 or candidates.size == 1:
        return int(candidates[rng.integers(0, candidates.size)])
    n = int(cells.size)
    span = min(int(horizon), int(spine_q.size) - m)
    prefix = np.ones(candidates.size, dtype=np.int64)
    alive = np.ones(candidates.size, dtype=bool)
    for k in range(1, span):
        nxt = candidates + k
        step = alive & (nxt < n)
        if step.any():
            step[step] &= cells[nxt[step]] == int(spine_q[m + k])
        prefix[step] += 1
        alive = step
        if not alive.any():
            break
    best = candidates[prefix == prefix.max()]
    return int(best[rng.integers(0, best.size)])


def _path_agreement_pick(
    candidates: np.ndarray,
    cells: np.ndarray,
    spine_q: np.ndarray,
    m: int,
    horizon: int,
    rng: np.random.Generator,
) -> int:
    """One entry, chosen for TOTAL forward agreement rather than leading prefix.

    Used only by the anticipation arm, where by construction no candidate
    matches at ``m`` -- the whole point is to find a month from which history
    walks into the spine's quadrant a few months later, so a leading-prefix rule
    would score every candidate zero and pick at random. Uniform among ties, one
    ``rng.integers`` call, same as everywhere else.
    """
    n = int(cells.size)
    span = max(1, min(int(horizon), int(spine_q.size) - m))
    score = np.zeros(candidates.size, dtype=np.int64)
    for k in range(span):
        nxt = candidates + k
        inside = nxt < n
        if inside.any():
            score[inside] += (cells[nxt[inside]] == int(spine_q[m + k])).astype(np.int64)
    if int(score.max()) == 0:
        # nothing to walk into: no candidate reaches the spine's quadrant
        # anywhere in the look-ahead, so a move here would buy nothing and
        # would still splice in a month the world's story contradicts. Park
        # only when parking pays.
        return -1
    best = candidates[score == score.max()]
    return int(best[rng.integers(0, best.size)])


def _join_filter(
    candidates: np.ndarray,
    era_bucket: np.ndarray,
    yoy: np.ndarray,
    previous: int,
    bound: float,
    *,
    era_relaxed: bool,
) -> np.ndarray:
    """The spine's two join filters, as the platform applies them.

    ``era_relaxed`` drops the era-bucket half and keeps the declared level bound.
    It exists to PRICE the constraint (the disclosure arm) and is never adopted:
    the era bucket is the sealed compiler's own rule and D-SP-10 preserved it.
    """
    if candidates.size == 0:
        return candidates
    ok = np.abs(yoy[candidates] - yoy[previous]) <= float(bound)
    if not era_relaxed:
        ok &= era_bucket[candidates] == era_bucket[previous]
    return candidates[ok]


def _anticipating_entry(
    args: Any,
    design: ReachDesign,
    pools: dict[tuple[int, int, float], np.ndarray],
    previous: int,
    m: int,
    spine_q_row: np.ndarray,
    seg: Any,
    pct: float,
    rng: np.random.Generator,
) -> int | None:
    """A month to move to when the spine's quadrant is unreachable this month.

    Called only on a divergence the join filters left with no candidate -- and
    ~88% of those are unreachable *by construction*, because crossing the era
    line is exactly what an era-safe join forbids (this section's header). The
    move is drawn from the pool of the row the block is standing on -- its OWN
    quadrant, the one the panel says it is in -- and is filtered by the same two
    join filters, so nothing teleports and no severity stratum is bypassed. What
    the choice optimises is forward agreement with the spine's coming months:
    **if the compiler cannot be in the right quadrant now, it moves to a month
    from which real history walks into it.**

    Returns ``None`` when there is nothing to move to, in which case the caller
    continues the block exactly as the platform does. An empty own-quadrant pool
    is one such case: ``_build_pools`` treats an empty CONDITIONING pool as a
    refusal, and borrowing that refusal for an anticipation lookup would turn a
    diagnostic into a stop, so it is caught here and only here.
    """
    cells, era_bucket, yoy = args.cells, args.era_bucket, args.yoy
    own = int(cells[previous])
    if own < 0:
        return None
    try:
        own_pool = _build_pools(pools, args.scores, cells, seg.from_quarter, own, pct)
    except SpineRefusal:
        return None
    candidates = _join_filter(
        join_candidates(
            args.source.values,
            args.source.factor_names,
            previous,
            args.stress.join_tolerance,
            own_pool[own_pool != previous],
        ),
        era_bucket,
        yoy,
        previous,
        args.spine.join_yoy_max_pp,
        era_relaxed=design.era_relaxed_joins,
    )
    if candidates.size == 0:
        return None
    picked = _path_agreement_pick(
        candidates, cells, spine_q_row, m, max(int(design.match_horizon), 1), rng
    )
    return None if picked < 0 else picked


def _reach_draw(args: Any, design: ReachDesign) -> tuple[np.ndarray, dict[str, Any]]:
    """``SpineBootstrap._draw``, composed so conditioning can reach every month.

    Structure, stream discipline and every helper are the platform's. The two
    differences from ``ah.gen.spine.SpineBootstrap._draw``, both gated on
    ``design`` and both inert at ``REACH_BASELINE``:

    1. **the entry choice** -- ``_path_prefix_pick`` instead of a uniform draw
       over the pool, at all three places an entry is drawn (month 0, a join, a
       forced re-entry);
    2. **the continuation choice** -- a block whose next month would land on a
       row of the wrong quadrant is ended, and the ordinary era-safe join is
       attempted instead. The block-break uniform is drawn either way and in the
       same place, so the two arms stay comparable month by month.

    Severity remains selection-only (rule 1): nothing here reads a portfolio
    outcome, a return or a drawdown -- only the panel's quadrant, which is the
    same object the pools are already built on. Joins keep both filters (era
    bucket AND the declared YoY bound) and the forced-re-entry rule is
    byte-unchanged, including its unfiltered fallback.
    """
    source, sp, hazard = args.source, args.sp, args.hazard
    scores, cells, yoy, era_bucket = args.scores, args.cells, args.yoy, args.era_bucket
    months, n_paths, seed = args.months, args.n_paths, args.seed
    stress, spine, pools = args.stress, args.spine, args.pools
    n = source.n_rows
    index = np.empty((n_paths, months), dtype=np.int64)
    per_path_onsets = [0] * n_paths
    per_quadrant_onsets = [0, 0, 0, 0]
    per_quadrant_months = [0, 0, 0, 0]
    forced_reentries = 0
    unfiltered_reentries = 0
    divergence_breaks = 0
    unresolved_divergences = 0
    breaks_blocked_by_the_era_filter = 0
    anticipating_moves = 0

    horizon = int(design.match_horizon)
    # the spine's quadrant for every month of every decade, precomputed: the
    # look-ahead needs months the platform's month-at-a-time loop never has in
    # hand. Same function, same inputs, same values.
    spine_q = np.empty((n_paths, months), dtype=np.int64)
    for p in range(n_paths):
        for m in range(months):
            spine_q[p, m] = spine_quadrant(
                sp.states[p, m], int(sp.labels[p, m]), mu_pi=float(sp.mu_pi[p])
            )

    for p in range(n_paths):
        rng = np.random.Generator(np.random.PCG64(int(seed) + LAYER_OFFSETS["blocks"]).jumped(p))
        rng_h = np.random.Generator(np.random.PCG64(int(seed) + LAYER_OFFSETS["hazard"]).jumped(p))
        in_correction = False
        dwell_left = 0
        shift = 0

        for m in range(months):
            seg = _segment_for(stress, m // 3)
            q = int(spine_q[p, m])

            if not in_correction:
                per_quadrant_months[q] += 1
                fires = rng_h.random() < float(hazard.rates[q])
            else:
                fires = False

            infl = credit = False
            if fires:
                infl = float(sp.states[p, m, 0]) - float(sp.mu_pi[p]) > BACKDROP_MARGIN_PP
                credit = float(sp.states[p, m, 4]) > 0.0
                per_path_onsets[p] += 1
                per_quadrant_onsets[q] += 1

            in_correction, dwell_left, shift = _correction_onset(
                spine, in_correction, dwell_left, shift, fires=fires, infl=infl, credit=credit
            )
            pct = (
                percentile_for(seg.entry_percentile, shift)
                if in_correction
                else seg.entry_percentile
            )
            pool = _build_pools(pools, scores, cells, seg.from_quarter, q, pct)
            in_correction, dwell_left, shift = _correction_expire(in_correction, dwell_left, shift)

            if m == 0:
                index[p, 0] = _path_prefix_pick(pool, cells, spine_q[p], m, horizon, rng)
                continue

            previous = int(index[p, m - 1])

            if previous + 1 >= n:
                # the panel-edge rule, byte-unchanged (owner ruling 2026-08-16)
                forced_reentries += 1
                pool_wo_prev = pool[pool != previous]
                filtered = _join_filter(
                    pool_wo_prev,
                    era_bucket,
                    yoy,
                    previous,
                    spine.join_yoy_max_pp,
                    era_relaxed=design.era_relaxed_joins,
                )
                if filtered.size:
                    index[p, m] = _path_prefix_pick(filtered, cells, spine_q[p], m, horizon, rng)
                else:
                    unfiltered_reentries += 1
                    index[p, m] = _path_prefix_pick(pool, cells, spine_q[p], m, horizon, rng)
                continue

            advanced = previous + 1
            # drawn unconditionally and here, exactly as the platform draws it,
            # so a divergence break cannot be confused with a longer block
            u = rng.random()
            diverged = design.break_on_divergence and int(cells[advanced]) != q
            mean_block = float(
                design.block_months_override
                if design.block_months_override is not None
                else seg.mean_block_months
            )
            if not diverged and u >= 1.0 / mean_block:
                index[p, m] = advanced
                continue
            if diverged:
                divergence_breaks += 1

            candidates = _join_filter(
                join_candidates(
                    source.values,
                    source.factor_names,
                    previous,
                    stress.join_tolerance,
                    pool[pool != previous],
                ),
                era_bucket,
                yoy,
                previous,
                spine.join_yoy_max_pp,
                era_relaxed=design.era_relaxed_joins,
            )
            if candidates.size:
                index[p, m] = _path_prefix_pick(candidates, cells, spine_q[p], m, horizon, rng)
                continue

            if diverged:
                unresolved_divergences += 1
                if int(era_bucket[previous]) != (q & 1):
                    # the era filter and the quadrant's hot bit are the same
                    # predicate, so this divergence was unjoinable by
                    # construction -- see this section's header
                    breaks_blocked_by_the_era_filter += 1
            if diverged and design.anticipate:
                moved = _anticipating_entry(
                    args, design, pools, previous, m, spine_q[p], seg, pct, rng
                )
                if moved is not None:
                    anticipating_moves += 1
                    index[p, m] = moved
                    continue
            index[p, m] = advanced

    corrections: dict[str, Any] = {
        "per_path_onsets": per_path_onsets,
        "per_quadrant_onsets": per_quadrant_onsets,
        "per_quadrant_months": per_quadrant_months,
        "forced_reentries": forced_reentries,
        "unfiltered_reentries": unfiltered_reentries,
        # D-SP-10 counters. The platform's stamp ignores unknown keys, so these
        # are surfaced through the FleshRun record instead (reach_stamp).
        "divergence_breaks": divergence_breaks,
        "unresolved_divergences": unresolved_divergences,
        "unresolved_divergences_blocked_by_the_era_filter": breaks_blocked_by_the_era_filter,
        "anticipating_moves": anticipating_moves,
    }
    return index, corrections


def reach_metrics(rows: np.ndarray, spine_seasons: np.ndarray, cells: np.ndarray) -> dict[str, Any]:
    """The two reach numbers, on one compiled batch.

    * ``share_of_months_selected_for_their_quadrant`` -- week C's own formula,
      recomputed unchanged so the 8.2% is comparable: a month is *selected* when
      it opens a block (month 0, a join, a forced re-entry).
    * ``conditioning_reach`` -- the quantity the ruling actually asks about: the
      share of months whose drawn panel row carries the quadrant the spine
      declares for that month, however it got there. A month that continues a
      block INTO the right quadrant is conditioned in every sense that matters
      to ``A1``/``A2``; a month selected at a block start is trivially matched.
      The first number can only ever be a lower bound on this one.
    """
    rows = np.asarray(rows, dtype=np.int64)
    seasons = np.asarray(spine_seasons, dtype=np.int64)
    matched = cells[rows] == seasons
    starts = int(rows.shape[0] + int(np.sum(rows[:, 1:] != rows[:, :-1] + 1)))
    total = int(rows.size)
    return {
        "months_in_the_batch": total,
        "months_selected_for_their_quadrant": starts,
        "share_of_months_selected_for_their_quadrant": starts / total,
        "months_whose_drawn_row_carries_the_spine_s_quadrant": int(matched.sum()),
        "conditioning_reach": float(matched.mean()),
        "distinct_panel_rows_visited": int(np.unique(rows).size),
    }


# --------------------------------------------------------------------------- #
# the runtime substitution
# --------------------------------------------------------------------------- #


@dataclass
class FleshRun:
    """What one installed substitution saw -- for the caller's own checks."""

    premise_mode: str
    design: ReachDesign = ADOPTED_REACH
    calls: list[dict[str, Any]] = field(default_factory=list)
    decades: dict[int, list[weeka.Stage2Decade]] = field(default_factory=dict)
    #: the D-SP-10 counters, per compiled batch, keyed by seed. The platform's
    #: conditioning stamp has a fixed key set and drops unknown ones, so the
    #: composed draw reports through here instead of through the ensemble.
    reach: dict[int, dict[str, Any]] = field(default_factory=dict)

    @property
    def last_decades(self) -> list[weeka.Stage2Decade]:
        if not self.calls:
            raise weeka.FitError("no batch has been compiled under this substitution")
        return self.decades[int(self.calls[-1]["seed"])]


#: The design the installed factory draws under, and the run it reports to.
#: Module state because the platform's factory hook takes a zero-argument
#: callable; both are set and restored by :func:`stage2_flesh`.
_ACTIVE_DESIGN: ReachDesign = ADOPTED_REACH
_ACTIVE_RUN: FleshRun | None = None


class _Stage2SpineFactory(SpineBootstrap):
    """``SpineBootstrap``, fitted on the campaign panel, drawing under D-SP-10.

    Two reasons to subclass, and no third: the platform's factory hook takes a
    zero-argument callable and ``SpineBootstrap()`` is unfitted; and D-SP-10
    funds a change to the block sampler, which is ``_draw``. Every other method
    -- ``sample``, ``sample_months``, the conditioning stamp, the ensemble
    assembly -- is the platform's and is not touched.
    """

    _SOURCE: BootstrapSource | None = None

    def __init__(self) -> None:
        if _Stage2SpineFactory._SOURCE is None:
            _Stage2SpineFactory._SOURCE = campaign_source()
        super().__init__(_Stage2SpineFactory._SOURCE)

    def _draw(self, args: Any) -> tuple[np.ndarray, dict[str, Any]]:
        design = _ACTIVE_DESIGN
        if design.is_baseline:
            # the platform's own rule, run by the platform's own code: the
            # baseline arm is never a re-implementation of anything
            return super()._draw(args)
        index, corrections = _reach_draw(args, design)
        if _ACTIVE_RUN is not None:
            _ACTIVE_RUN.reach[int(args.seed)] = {
                "design": design.name,
                "match_horizon": int(design.match_horizon),
                "break_on_divergence": bool(design.break_on_divergence),
                "block_months_override": design.block_months_override,
                "divergence_breaks": int(corrections["divergence_breaks"]),
                "unresolved_divergences": int(corrections["unresolved_divergences"]),
                "unresolved_divergences_blocked_by_the_era_filter": int(
                    corrections["unresolved_divergences_blocked_by_the_era_filter"]
                ),
                "anticipating_moves": int(corrections["anticipating_moves"]),
            }
        return index, corrections


@contextlib.contextmanager
def stage2_flesh(
    frozen: FrozenSystem, *, premise_mode: str, design: ReachDesign | None = None
) -> Iterator[FleshRun]:
    """Install the stage-2 spine sampler under the platform's flesh, then remove it.

    Inside the block, ``ah.gen.spine.sample_spine`` is the coupled system's own
    batch generator and everything below it -- ``SpineBootstrap.sample_months``,
    the pools, the hazard corrections, the joins, ``ah.port.adapter.run_gen_path``
    and the institutional twin -- runs unchanged. Outside it, the platform is
    exactly as it was: the previous sampler and the previous spine factory are
    both restored, including on an exception.

    Three properties of the replacement, each a deliberate choice:

    * the ``regimes_artifact`` argument is **ignored**. Stage 2's growth chain
      replaces L2's semi-Markov regime layer -- that is what the coupled system
      is -- while the L1 ``climate`` argument is the same pinned posterior the
      platform passes, so the climate the flesh is conditioned on is unchanged.
    * ``max_attempts_per_decade`` is stage 2's own
      (``spine_v2_fit.MAX_ATTEMPTS_PER_DECADE``, 200 -- the same number the
      platform uses), and an unfillable premise raises
      ``ah.gen.spine.SpineRefusal`` rather than week A's ``FitError``, so the
      byte-frozen b3 harness's refusal accounting keeps working unmodified.
    * ``premise_mode='unconditional'`` drops the premise clause and accepts every
      attempt. That is week A's own verification arm, not a new construct: the
      world still supplies the flesh spec, and only the acceptance filter is off.
    """
    if premise_mode not in PREMISE_MODES:
        raise ValueError(f"premise_mode must be one of {PREMISE_MODES}; got {premise_mode!r}")
    record = FleshRun(premise_mode=premise_mode, design=design or ADOPTED_REACH)
    era = frozen.era_threshold_pp

    def sampler(
        climate: Any,
        regimes_artifact: Any,
        premise: Any,
        *,
        n_decades: int,
        seed: int,
        months: int = 120,
        max_attempts_per_decade: int = weeka.MAX_ATTEMPTS_PER_DECADE,
    ) -> SpinePaths:
        del regimes_artifact, climate, max_attempts_per_decade
        try:
            decades, tally = weeka.simulate_batch_coupled(
                frozen.system,
                frozen.climate,
                n_decades=int(n_decades),
                seed=int(seed),
                months=int(months),
                premise=None if premise_mode == PREMISE_UNCONDITIONAL else premise,
            )
        except weeka.FitError as exc:  # the harnesses below expect the platform's own
            raise SpineRefusal(str(exc)) from exc
        record.calls.append(
            {"seed": int(seed), "n_decades": int(n_decades), "attempts": int(tally["attempts"])}
        )
        record.decades[int(seed)] = decades
        return spine_paths_from_decades(
            decades, era, seed=int(seed), attempts=int(tally["attempts"])
        )

    global _ACTIVE_DESIGN, _ACTIVE_RUN
    previous_sampler = spine_module.sample_spine
    previous_factory = stress_module._SPINE_FACTORY
    previous_design, previous_run = _ACTIVE_DESIGN, _ACTIVE_RUN
    spine_module.sample_spine = sampler
    stress_module.register_spine_factory(_Stage2SpineFactory)
    _ACTIVE_DESIGN, _ACTIVE_RUN = record.design, record
    try:
        yield record
    finally:
        spine_module.sample_spine = previous_sampler
        _ACTIVE_DESIGN, _ACTIVE_RUN = previous_design, previous_run
        if previous_factory is not None:
            stress_module.register_spine_factory(previous_factory)


def compile_world(
    world: NumericWorld, n_decades: int, seed: int, *, generator: SpineBootstrap | None = None
) -> Ensemble:
    """One compiled batch: ``n_decades`` fleshed decades of ``world``.

    Must be called inside :func:`stage2_flesh`; outside it this is the
    platform's own spine and not stage 2's.
    """
    gen = generator or _Stage2SpineFactory()
    return gen.sample(world, int(n_decades), int(seed))


def campaign_panel_source() -> BootstrapSource:
    """The campaign panel the flesh draws from. One instance, memoised upstream."""
    return campaign_source()


# --------------------------------------------------------------------------- #
# stream hygiene for the streams week C adds
# --------------------------------------------------------------------------- #


def assert_flesh_streams_distinct(base_seeds: list[int], n_paths: int = 64) -> dict[str, Any]:
    """The flesh's per-path streams collide with no stage-2 per-decade stream.

    Week A proved its five per-decade streams disjoint from each other and from
    ``ah.gen.spine.LAYER_OFFSETS``. Week C turns on two more consumers at the
    same base seeds -- the block stream and the hazard stream inside
    ``SpineBootstrap._draw`` -- and they are opened a **different way**:
    ``PCG64(seed + offset).jumped(p)``, one fixed jump per path, against week A's
    ``PCG64(seed + offset + ATTEMPT_STRIDE * attempt)``. Two different
    constructions cannot be compared by looking at integers, so whole tapes are
    drawn and compared, as week A's own check does.
    """
    from math import gcd

    def tape(seed: int, jump: int = 0) -> tuple[float, ...]:
        rng = np.random.Generator(np.random.PCG64(int(seed)).jumped(int(jump)))
        return tuple(float(x) for x in rng.random(8))

    flesh: dict[tuple[int, str, int], tuple[float, ...]] = {}
    for base in base_seeds:
        for name in ("blocks", "hazard"):
            for p in range(n_paths):
                flesh[(base, name, p)] = tape(base + LAYER_OFFSETS[name], p)
    if len(set(flesh.values())) != len(flesh):
        raise weeka.FitError("two flesh per-path streams share a tape")

    stage2: set[tuple[float, ...]] = set()
    for base in base_seeds:
        for offset in weeka.STAGE2_LAYER_OFFSETS.values():
            for attempt in range(weeka.MAX_ATTEMPTS_PER_DECADE):
                stage2.add(tape(base + offset + weeka.SPINE2_ATTEMPT_STRIDE * attempt))
    collisions = stage2 & set(flesh.values())
    if collisions:
        raise weeka.FitError(
            f"{len(collisions)} flesh stream(s) collide with a stage-2 per-decade stream"
        )

    ladder = {tape(base) for base in base_seeds}
    if ladder & set(flesh.values()):
        raise weeka.FitError("a flesh stream collides with a bare ladder seed")
    if gcd(weeka.PLATFORM_SEED_STRIDE, weeka.SPINE2_ATTEMPT_STRIDE) != 1:
        raise weeka.FitError("the platform ladder stride and the attempt stride are not coprime")
    return {
        "base_seeds": [int(s) for s in base_seeds],
        "flesh_streams_checked": len(flesh),
        "stage2_streams_checked": len(stage2),
        "flesh_per_path_streams_distinct": True,
        "disjoint_from_every_stage2_attempt_stream": True,
        "disjoint_from_the_bare_ladder": True,
        "flesh_offsets": {k: int(LAYER_OFFSETS[k]) for k in ("blocks", "hazard")},
        "construction_note": (
            "the flesh opens PCG64(seed + offset).jumped(p); stage 2 opens "
            "PCG64(seed + offset + ATTEMPT_STRIDE * attempt). Whole tapes are drawn and "
            "compared because two integers being different says nothing about two "
            "differently-constructed streams"
        ),
    }
