"""D-SP-12 -- the polish round's engine changes, installed around the sealed code.

Charter: ``governance/decision-register.md`` **D-SP-12** (owner ruling
2026-08-19) -- three improvements to the coupled engine, funded as one final
round of the current architecture and re-measured under the FROZEN exam.

**Change 1, join selection by inflation distance.** ``S1``'s own stop-question
named the lever: *"every seam already respects the declared 2.5 pp join bound;
what fails is that among the era-safe candidates the compiler chooses without
regard to how far inflation moves."* The polish rule ranks the candidates the
compiler already admits by ``|dYoY|`` at the seam and takes the smallest, with
the **earliest panel row** as the deterministic tie-break. **No declared
tolerance moves**: the pool, both join filters, the severity stratum, the factor
tolerance and the era-crossing licence all decide who is a candidate exactly as
before -- this rule only decides which of them is taken.

WHY A SUBSTITUTION AND NOT AN EDIT
----------------------------------
``scripts/stage2_worlds.py`` is hashed by
``docs/superpowers/specs/stage2-prereg-2.json``, which names it as the era
rule's implementation. Editing it would need an amendment entry, and an
amendment entry is an edit to a sealed file -- which D-SP-12's charter forbids
("sealed files READ-ONLY; the ENGINE may change, the bars may not"). So the
polish behaviour is installed **around** the sealed code rather than into it, by
a context manager that patches a module attribute and restores it, exactly as
``stage2_worlds.stage2_flesh`` already installs the stage-2 spine sampler under
the platform's flesh. Two consequences worth stating plainly:

* the era rule that runs is still ``stage2_worlds._era_crossing_licence`` -- the
  sealed implementation, not a copy of it that could drift;
* every hashed file keeps its sealed hash, and
  ``tests/test_stage2_rulers_seal.py`` keeps passing without an amendment.

**Change 3, the L1 across-decade dispersion recalibration.** The slow climate's
two level-carrying innovation volatilities, ``sigma_pi`` and ``sigma_r``, are
scaled by factors derived in ``scripts/stage2_polish_calibrate.py`` against a
measured historical quantity -- the panel's own decade-scale spread of the same
two states. The derivation, its estimator and its target are recorded in
``docs/superpowers/specs/stage2-fitted-params-2.json``; the frozen week-A
artifact is an INPUT here and is never written.

**Change 2, the conditional era-crossing rule ADOPTED.** A configuration
choice rather than new code: :data:`POLISH_REACH` is
``stage2_worlds.ERA_CONDITIONAL_REACH``, the design D-SP-11 sealed and audited,
promoted to the default the run entry point carries. The licence audit stays
live and stays a stop (:func:`assert_licensed_crossings`).

THE RANDOM TAPE IS NOT MOVED
----------------------------
The platform picks uniformly among the candidates that tie at the longest
matching forward path, with one ``rng.integers`` call. The polish rule computes
**the same tie set**, draws **the same uniform from the same range** and
discards it, then takes the minimum-gap member. So the block stream is consumed
at exactly the same rate and at exactly the same points as under the D-SP-11
engine, and the only difference between the two arms is which of the tied
candidates is taken.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

import stage2_fit as weeka  # noqa: E402
import stage2_worlds as worlds  # noqa: E402

import ah.gen.climate.simulate as csim  # noqa: E402
from ah.gen.climate.model import N_STATES, PARAM_NAMES  # noqa: E402
from ah.gen.climate.simulate import SimulatedClimate  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"

#: The NEW versioned parameters artifact. The frozen week-A artifact
#: (``stage2-fitted-params.json``) is an input to this round and is never
#: written by it: D-SP-12's charter says a recalibrated parameter goes into a new
#: versioned file with its derivation recorded, and this is that file.
POLISH_PARAMS_PATH = SPECS_DIR / "stage2-fitted-params-2.json"

# --------------------------------------------------------------------------- #
# 1. join selection by inflation distance
# --------------------------------------------------------------------------- #

#: The platform's own rule: uniform among the candidates that tie at the longest
#: matching forward path. Runnable inside the context so the substitution's
#: inertness is a comparison rather than an assertion.
SELECTION_PLATFORM = "platform-uniform"
#: D-SP-12's rule: **the tie is broken by inflation distance.** The forward-path
#: score still chooses the tie set -- that is the conditioning-reach mechanism
#: D-SP-10 was funded to build and it is not what ``S1`` called arbitrary -- and
#: the smallest ``|dYoY|`` at the seam wins inside it.
SELECTION_MIN_GAP = "min-inflation-gap"
#: A DISCLOSURE arm, never adopted: inflation distance decides among **all** the
#: era-safe candidates, with the forward-path score ignored entirely. It prices
#: what the reach mechanism is worth and it shows ``S1``'s lower edge biting --
#: a compiler that only ever joins near-identical rows has seams that are
#: findable by being unnaturally smooth.
SELECTION_GAP_ONLY = "min-inflation-gap-only"

SELECTION_RULES = (SELECTION_PLATFORM, SELECTION_MIN_GAP, SELECTION_GAP_ONLY)

_ORIGINAL_JOIN_FILTER = worlds._join_filter
_ORIGINAL_PREFIX_PICK = worlds._path_prefix_pick
_ORIGINAL_AGREEMENT_PICK = worlds._path_agreement_pick


@dataclass
class _JoinContext:
    """What the last call to ``_join_filter`` was asked about.

    The platform's two pick helpers take the candidate array and nothing else,
    so the inflation gap at the seam -- which needs the panel's trailing YoY and
    the row the block is standing on -- has to travel to them another way. It
    travels here, set by the patched filter immediately before the pick, and the
    pick only uses it when the array it was handed **is** the array the filter
    returned (an identity test, not an equality test). That is what keeps the
    rule off the two call sites that are not joins: month 0 and the unfiltered
    panel-edge fallback both hand over the raw pool.
    """

    candidates: np.ndarray | None = None
    yoy: np.ndarray | None = None
    previous: int = -1

    def owns(self, candidates: np.ndarray) -> bool:
        return self.candidates is not None and candidates is self.candidates


_CONTEXT = _JoinContext()
_ACTIVE_RULE: str = SELECTION_PLATFORM


def min_gap_pick(candidates: np.ndarray, yoy: np.ndarray, *, previous: int) -> int:
    """The candidate whose trailing-inflation gap at the seam is smallest.

    Ties go to the **earliest panel row**, stated as a rule and implemented as
    one (``np.lexsort`` on the row index under the gap) rather than left to the
    stability of whatever sort a library happens to use. Earliest-row is the
    tie-break because it is the only property of a candidate that is fixed
    before the world exists: it cannot encode anything about the batch, the
    seed or the bar being read.
    """
    cands = np.asarray(candidates, dtype=np.int64)
    if cands.size == 0:
        raise ValueError("min_gap_pick needs at least one candidate")
    gap = np.abs(np.asarray(yoy, dtype=np.float64)[cands] - float(yoy[int(previous)]))
    order = np.lexsort((cands, gap))
    return int(cands[order[0]])


def _patched_join_filter(
    candidates: np.ndarray,
    era_bucket: np.ndarray,
    yoy: np.ndarray,
    previous: int,
    bound: float,
    *,
    era_relaxed: bool,
    crossing_licence: tuple[int, int] | None = None,
) -> np.ndarray:
    """The sealed filter, unchanged, plus a note of what it was asked about."""
    out = _ORIGINAL_JOIN_FILTER(
        candidates,
        era_bucket,
        yoy,
        previous,
        bound,
        era_relaxed=era_relaxed,
        crossing_licence=crossing_licence,
    )
    _CONTEXT.candidates = out
    _CONTEXT.yoy = yoy
    _CONTEXT.previous = int(previous)
    return out


def _patched_prefix_pick(
    candidates: np.ndarray,
    cells: np.ndarray,
    spine_q: np.ndarray,
    m: int,
    horizon: int,
    rng: np.random.Generator,
) -> int:
    """``_path_prefix_pick`` with the uniform tie-break replaced by min-gap.

    The forward-path prefix is computed exactly as the platform computes it, the
    tie set is therefore the same set, and the uniform is drawn from the same
    range and thrown away -- so the block stream is consumed identically and the
    two arms remain comparable month by month.
    """
    if _ACTIVE_RULE == SELECTION_PLATFORM or not _CONTEXT.owns(candidates):
        return _ORIGINAL_PREFIX_PICK(candidates, cells, spine_q, m, horizon, rng)
    yoy, previous = _CONTEXT.yoy, _CONTEXT.previous
    assert yoy is not None
    if horizon <= 1 or candidates.size == 1 or _ACTIVE_RULE == SELECTION_GAP_ONLY:
        rng.integers(0, candidates.size)
        return min_gap_pick(candidates, yoy, previous=previous)
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
    rng.integers(0, best.size)
    return min_gap_pick(best, yoy, previous=previous)


def _patched_agreement_pick(
    candidates: np.ndarray,
    cells: np.ndarray,
    spine_q: np.ndarray,
    m: int,
    horizon: int,
    rng: np.random.Generator,
) -> int:
    """The anticipating move's pick, with the same tie-break substitution.

    The refusal path is untouched: when no candidate reaches the spine's
    quadrant anywhere in the look-ahead the platform returns -1 without drawing,
    and so does this.
    """
    if _ACTIVE_RULE == SELECTION_PLATFORM or not _CONTEXT.owns(candidates):
        return _ORIGINAL_AGREEMENT_PICK(candidates, cells, spine_q, m, horizon, rng)
    yoy, previous = _CONTEXT.yoy, _CONTEXT.previous
    assert yoy is not None
    n = int(cells.size)
    span = max(1, min(int(horizon), int(spine_q.size) - m))
    score = np.zeros(candidates.size, dtype=np.int64)
    for k in range(span):
        nxt = candidates + k
        inside = nxt < n
        if inside.any():
            score[inside] += (cells[nxt[inside]] == int(spine_q[m + k])).astype(np.int64)
    if int(score.max()) == 0:
        return -1
    best = candidates if _ACTIVE_RULE == SELECTION_GAP_ONLY else candidates[score == score.max()]
    rng.integers(0, best.size)
    return min_gap_pick(best, yoy, previous=previous)


@contextlib.contextmanager
def join_selection(rule: str = SELECTION_MIN_GAP) -> Iterator[None]:
    """Install the polish join-selection rule, then remove it.

    Outside this block ``stage2_worlds`` is exactly the module the D-SP-11 seal
    hashed, and every artifact that quotes it still regenerates. Inside it, the
    three helpers are wrapped; the wrappers delegate to the originals whenever
    the rule is the platform's or the candidate array did not come from a join.
    """
    if rule not in SELECTION_RULES:
        raise ValueError(f"unknown join-selection rule {rule!r}; expected one of {SELECTION_RULES}")
    global _ACTIVE_RULE
    previous_rule = _ACTIVE_RULE
    _ACTIVE_RULE = rule
    worlds._join_filter = _patched_join_filter
    worlds._path_prefix_pick = _patched_prefix_pick
    worlds._path_agreement_pick = _patched_agreement_pick
    try:
        yield
    finally:
        worlds._join_filter = _ORIGINAL_JOIN_FILTER
        worlds._path_prefix_pick = _ORIGINAL_PREFIX_PICK
        worlds._path_agreement_pick = _ORIGINAL_AGREEMENT_PICK
        _ACTIVE_RULE = previous_rule
        _CONTEXT.candidates = None
        _CONTEXT.yoy = None
        _CONTEXT.previous = -1


# --------------------------------------------------------------------------- #
# 2. the polish engine -- the conditional era-crossing rule, ADOPTED
# --------------------------------------------------------------------------- #

#: **D-SP-12 change 2: the conditional era-crossing rule is ADOPTED.** D-SP-11
#: measured it as an arm beside the D-SP-10 engine and left the adoption to the
#: owner; the ruling of 2026-08-19 takes it, with its hedge-cost accepted as part
#: of this round's measured record. Nothing about the rule itself moves -- this
#: is ``stage2_worlds.ERA_CONDITIONAL_REACH``, the sealed design, promoted from
#: "an arm the run script names" to "the default the run entry point carries".
#:
#: The licence audit stays live and stays a STOP. ``ERA_CONDITIONAL_REACH`` is
#: only trustworthy because every bucket-changing seam is re-derived from the
#: compiled row tape rather than read off the engine's counters, and D-SP-11's
#: 104-of-104 reading is a measurement that has to be retaken on every engine
#: this round produces -- a join-selection change alters WHICH candidate is
#: taken at a crossing month, so the audit is not inherited. See
#: :func:`assert_licensed_crossings`.
POLISH_REACH = worlds.ERA_CONDITIONAL_REACH


def assert_licensed_crossings(audit: dict[str, Any], *, arm: str) -> dict[str, Any]:
    """Every bucket-changing seam must sit at a licensed month. This is a STOP.

    ``audit`` is ``stage2_rulers.era_crossing_audit``'s own output -- the sealed
    tape-based re-derivation, imported by the caller and never re-implemented
    here. D-SP-11 wrote this check as a raise rather than a reported number and
    the polish round keeps it that way: an unlicensed crossing means the adopted
    rule is not the rule the engine obeyed, and no bar read on that engine means
    anything.
    """
    if not audit.get("holds"):
        raise RuntimeError(
            f"the {arm} arm has {audit.get('unlicensed_crossing_seams')} bucket-changing seam(s) "
            "at months where the spine does not cross. The era-crossing rule is a rule and this "
            "is a stop, not a diagnostic"
        )
    return audit


# --------------------------------------------------------------------------- #
# 3. the L1 across-decade dispersion recalibration
# --------------------------------------------------------------------------- #

#: The two L1 innovation volatilities the recalibration touches, and no others.
#: They are the diffusion scales of the two states the rule-implied policy rate
#: is made of (``i_rule = r* + pi* + phi_pi x + phi_c c``), which is the series
#: whose over-dispersion ``P2`` reads. Half-lives, every other volatility, both
#: Taylor loadings, ``beta_g`` and ``delta_L`` are untouched: they are not what
#: the target measures.
CALIBRATED_PARAMS = ("sigma_pi", "sigma_r")


@dataclass(frozen=True)
class L1Calibration:
    """Multiplicative factors on L1's two level-carrying innovation volatilities."""

    sigma_pi: float = 1.0
    sigma_r: float = 1.0

    @property
    def factors(self) -> dict[str, float]:
        return {"sigma_pi": float(self.sigma_pi), "sigma_r": float(self.sigma_r)}

    @property
    def is_unit(self) -> bool:
        return self.sigma_pi == 1.0 and self.sigma_r == 1.0


#: The identity. Used by the pin test and by every arm that is meant to be the
#: unrecalibrated engine.
L1_UNIT = L1Calibration()


def scaled_simulate_decades(calibration: L1Calibration) -> Any:
    """``ah.gen.climate.simulate.simulate_decades`` with the two sigmas scaled.

    A line-for-line replay of the platform's own per-decade loop -- same seed
    stride, same posterior index draw, same joint ``(theta, s0)``, same
    ``_simulate_path`` -- with the two calibrated volatilities multiplied
    **after** the draw and before the path. At unit scale the multiplication is
    skipped entirely rather than performed with a factor of one, so the arm is
    bit-identical to the platform's and every later difference is the
    calibration rather than the copy. ``tests/test_stage2_polish.py`` is where
    that is checked instead of claimed.
    """
    factors = calibration.factors

    def simulate(
        artifact: Any,
        n_decades: int,
        *,
        seed: int,
        months: int = 120,
        s0_date: Any | None = None,
        cycle: np.ndarray | None = None,
        theta_index: int | None = None,
    ) -> SimulatedClimate:
        ts = artifact.dates[-1] if s0_date is None else s0_date
        locs = artifact.dates.get_indexer([ts])
        if locs[0] < 0:
            raise ValueError(f"s0_date {ts} is not on the artifact's monthly grid")
        t0 = int(locs[0])
        cyc = csim._validate_cycle(cycle, n_decades, months)
        out = np.empty((n_decades, months, N_STATES), dtype=np.float64)
        idx = np.empty(n_decades, dtype=np.int64)
        for k in range(n_decades):
            rng = np.random.Generator(np.random.PCG64(seed + csim.SEED_STRIDE * k))
            draw = int(rng.integers(artifact.n_draws)) if theta_index is None else int(theta_index)
            idx[k] = draw
            theta = {name: float(artifact.params[name][draw]) for name in PARAM_NAMES}
            for name, factor in factors.items():
                if factor != 1.0:
                    theta[name] = theta[name] * factor
            out[k] = csim._simulate_path(theta, artifact.states[draw, t0, :], months, cyc[k], rng)
        params: dict[str, np.ndarray] = {}
        for name in PARAM_NAMES:
            drawn = artifact.params[name][idx]
            factor = factors.get(name, 1.0)
            params[name] = drawn if factor == 1.0 else drawn * factor
        return SimulatedClimate(states=out, theta_index=idx, params=params, s0_date=ts, seed=seed)

    return simulate


@contextlib.contextmanager
def l1_calibration(calibration: L1Calibration | None) -> Iterator[None]:
    """Install the recalibrated slow climate, then remove it.

    ``None`` (or the unit calibration) installs nothing at all, so an arm that
    asks for the unrecalibrated engine gets the platform's own function object
    and not a wrapper that happens to agree with it.
    """
    if calibration is None or calibration.is_unit:
        yield
        return
    previous = weeka.simulate_decades
    weeka.simulate_decades = scaled_simulate_decades(calibration)
    try:
        yield
    finally:
        weeka.simulate_decades = previous


@contextlib.contextmanager
def polish_engine(
    *, selection: str = SELECTION_MIN_GAP, calibration: L1Calibration | None = None
) -> Iterator[None]:
    """The polish engine's substitutions, installed together.

    The reach design is not installed here -- it is passed to
    ``stage2_worlds.stage2_flesh`` by the caller as :data:`POLISH_REACH` -- so
    this block is only about the behaviour that has to be patched in.
    """
    with join_selection(selection), l1_calibration(calibration):
        yield


def across_decade_spread(paths: np.ndarray) -> dict[str, float]:
    """One series' dispersion, split into across-decade and within-decade.

    ``paths`` is ``(n_decades, months)``. The same three numbers are computed on
    history by ``stage2_polish_calibrate.panel_decade_spread`` over the panel's
    own non-overlapping decades, because a calibration whose two sides are
    computed by different functions is not a calibration.
    """
    arr = np.asarray(paths, dtype=np.float64)
    means = arr.mean(axis=1)
    return {
        "total_sd": float(arr.reshape(-1).std(ddof=1)),
        "across_decade_sd": float(means.std(ddof=1)),
        "within_decade_sd": float(np.sqrt(np.mean(arr.var(axis=1, ddof=1)))),
        "n_decades": float(arr.shape[0]),
        "months_per_decade": float(arr.shape[1]),
    }
