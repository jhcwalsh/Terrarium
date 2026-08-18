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
The flesh machinery -- ``ah.gen.spine.SpineBootstrap``'s pools, percentile
strata, hazard corrections, era-safe joins and forced re-entry -- runs
**byte-verbatim**; what is substituted, at runtime and from this script, is
exactly one function: ``ah.gen.spine.sample_spine``, the spine sampler that
decides *which climate and which growth path* the flesh is conditioned on. The
substitution is installed by the :func:`stage2_flesh` context manager and
removed on exit. **Promoting the stage-2 sampler into ``src/`` is a separate
owner release event, after a pass, and is not done here.**

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
    spine_quadrant,
)
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
# the runtime substitution
# --------------------------------------------------------------------------- #


@dataclass
class FleshRun:
    """What one installed substitution saw -- for the caller's own checks."""

    premise_mode: str
    calls: list[dict[str, Any]] = field(default_factory=list)
    decades: dict[int, list[weeka.Stage2Decade]] = field(default_factory=dict)

    @property
    def last_decades(self) -> list[weeka.Stage2Decade]:
        if not self.calls:
            raise weeka.FitError("no batch has been compiled under this substitution")
        return self.decades[int(self.calls[-1]["seed"])]


class _Stage2SpineFactory(SpineBootstrap):
    """``SpineBootstrap``, fitted on the campaign panel at construction.

    Subclassed for one reason only -- the platform's factory hook takes a
    zero-argument callable and ``SpineBootstrap()`` is unfitted -- and it
    overrides no behaviour whatsoever.
    """

    _SOURCE: BootstrapSource | None = None

    def __init__(self) -> None:
        if _Stage2SpineFactory._SOURCE is None:
            _Stage2SpineFactory._SOURCE = campaign_source()
        super().__init__(_Stage2SpineFactory._SOURCE)


@contextlib.contextmanager
def stage2_flesh(frozen: FrozenSystem, *, premise_mode: str) -> Iterator[FleshRun]:
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
    record = FleshRun(premise_mode=premise_mode)
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

    previous_sampler = spine_module.sample_spine
    previous_factory = stress_module._SPINE_FACTORY
    spine_module.sample_spine = sampler
    stress_module.register_spine_factory(_Stage2SpineFactory)
    try:
        yield record
    finally:
        spine_module.sample_spine = previous_sampler
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
