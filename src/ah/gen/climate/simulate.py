"""WP2.5 Layer 1 simulation: decades from a fitted climate artifact (numpy only).

Deliberately JAX-free: generation-time consumers (WP2.6 regimes, WP2.7 joinery,
`systems.py`) get the climate layer without dragging the fitting runtime in, and
determinism is plain ``numpy.random.Generator(PCG64(seed))`` end to end.

The artifact contract
---------------------
A single ``.npz`` written by :func:`ah.gen.climate.fit.save_artifact`: posterior
parameter draws (``param_<name>``, each ``(n_draws,)``), smoothed contract-state
draws (``states``: ``(n_draws, T, 5)`` in :data:`ah.gen.climate.model.STATE_NAMES`
order), the monthly ``dates`` grid, and a ``meta_json`` document. A canonical
SHA-256 over every array plus the meta JSON is stored inside the file and
re-verified on every load, so a loaded artifact is bit-for-bit the one that was
saved -- same file, same seed, bit-identical simulation (asserted by test).

Parameter uncertainty inside the ensemble (DN-1.1 SS II.2)
----------------------------------------------------------
:func:`simulate_decades` draws a posterior index PER DECADE: decade k gets its
own ``(theta, s0)`` from the joint posterior, so the ten thousand decades
disagree about the long-run parameters, not just the dice rolls. ``theta_index``
pins a single draw (ablation/testing); the dispersion contrast between the two
modes is asserted by test.

The cycle-term contract (what WP2.6 must supply)
------------------------------------------------
``cycle`` is an exogenous array, shape ``(months,)`` or ``(n_decades, months)``,
finite values in ``[-1, +1]``. It feeds (a) the credit-gap norm
``L_bar_t = delta_L * c_t`` inside the state dynamics and (b) the Taylor anchor
via :func:`policy_anchor`. ``None`` means neutral (zeros). Swapping in WP2.6's
regime-emitted c_t is a simulation-time input change only -- the anchor is an
observation equation and the norm an exogenous forcing, so **no refit of L1 is
needed** when Layer 2 arrives. During fitting the historical proxy was
``c_t = 1 - 2*USREC`` (see ``ah.gen.climate.fit``); WP2.6's c_t must live on the
same ``[-1, +1]`` scale for the fitted ``phi_c``/``delta_L`` to keep their meaning.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ah.gen.climate.model import DT, N_STATES, PARAM_NAMES, STATE_NAMES

__all__ = [
    "ArtifactError",
    "ClimateArtifact",
    "SimulatedClimate",
    "content_sha256",
    "load_artifact",
    "policy_anchor",
    "simulate_decades",
]

#: CLAUDE.md's ensemble seed stride: decade k uses PCG64(base_seed + 7919*k).
SEED_STRIDE = 7919

_LN2 = float(np.log(2.0))


class ArtifactError(RuntimeError):
    """Raised for a missing, malformed, or tampered climate artifact."""


def content_sha256(arrays: Mapping[str, np.ndarray], meta_json: str) -> str:
    """Canonical content hash: sorted array names, dtype, shape, raw bytes, meta.

    Computed over the *content*, not the container file: npz zip members carry
    timestamps, so file bytes are not reproducible even when the payload is.
    """
    h = hashlib.sha256()
    for name in sorted(arrays):
        arr = np.ascontiguousarray(arrays[name])
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(str(arr.dtype).encode("utf-8"))
        h.update(b"\0")
        h.update(repr(arr.shape).encode("utf-8"))
        h.update(b"\0")
        h.update(arr.tobytes())
    h.update(meta_json.encode("utf-8"))
    return h.hexdigest()


@dataclass(frozen=True)
class ClimateArtifact:
    """A loaded, hash-verified posterior artifact."""

    params: Mapping[str, np.ndarray]  # name -> (n_draws,)
    states: np.ndarray  # (n_draws, T, 5), STATE_NAMES order
    dates: pd.DatetimeIndex  # (T,) monthly grid of the fit span
    meta: dict
    path: Path

    @property
    def n_draws(self) -> int:
        return int(self.states.shape[0])


def load_artifact(path: str | Path) -> ClimateArtifact:
    """Load and verify a climate posterior artifact.

    Deterministic: the same file always yields bit-identical arrays (asserted by
    re-hashing against the stored canonical SHA-256; a mismatch raises).
    """
    p = Path(path)
    if not p.exists():
        raise ArtifactError(f"climate artifact not found: {p}")
    with np.load(p, allow_pickle=False) as npz:
        data = {name: npz[name] for name in npz.files}

    for required in ("states", "dates", "meta_json", "content_sha256"):
        if required not in data:
            raise ArtifactError(f"artifact {p} is missing entry '{required}'")

    stored_hash = str(data.pop("content_sha256")[()])
    meta_json = str(data["meta_json"][()])
    recomputed = content_sha256(data, meta_json)
    # meta_json participates in the hash both as an array and as text; that is
    # fine -- the point is that EVERYTHING in the file is covered.
    if recomputed != stored_hash:
        raise ArtifactError(
            f"artifact {p} content hash mismatch: stored {stored_hash[:16]}..., "
            f"recomputed {recomputed[:16]}... (file corrupted or tampered)"
        )

    meta = json.loads(meta_json)
    meta["content_sha256"] = stored_hash
    params: dict[str, np.ndarray] = {}
    for name in PARAM_NAMES:
        key = f"param_{name}"
        if key not in data:
            raise ArtifactError(f"artifact {p} is missing parameter draws '{key}'")
        params[name] = np.asarray(data[key], dtype=np.float64)

    states = np.asarray(data["states"], dtype=np.float64)
    if states.ndim != 3 or states.shape[2] != N_STATES:
        raise ArtifactError(f"states must be (n_draws, T, {N_STATES}); got {states.shape}")
    n_draws = states.shape[0]
    for name, arr in params.items():
        if arr.shape != (n_draws,):
            raise ArtifactError(f"param '{name}' has shape {arr.shape}, expected ({n_draws},)")

    months = np.asarray(data["dates"], dtype=np.int64)
    dates = pd.DatetimeIndex(months.astype("datetime64[M]"))
    if len(dates) != states.shape[1]:
        raise ArtifactError("dates length must match states' time dimension")

    return ClimateArtifact(params=params, states=states, dates=dates, meta=meta, path=p)


# --------------------------------------------------------------------------- #
# decade simulation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SimulatedClimate:
    """``states``: (n_decades, months, 5) in STATE_NAMES order; per-decade theta."""

    states: np.ndarray
    theta_index: np.ndarray  # (n_decades,) posterior draw index per decade
    params: Mapping[str, np.ndarray]  # name -> (n_decades,) the theta each decade used
    s0_date: pd.Timestamp
    seed: int

    @property
    def n_decades(self) -> int:
        return int(self.states.shape[0])

    @property
    def months(self) -> int:
        return int(self.states.shape[1])

    def state(self, name: str) -> np.ndarray:
        return self.states[:, :, STATE_NAMES.index(name)]


def _validate_cycle(cycle: np.ndarray | None, n_decades: int, months: int) -> np.ndarray:
    """The c_t contract: None -> neutral zeros; else (months,) or (n_decades, months),
    finite, within [-1, +1]."""
    if cycle is None:
        return np.zeros((n_decades, months), dtype=np.float64)
    arr = np.asarray(cycle, dtype=np.float64)
    if arr.shape == (months,):
        arr = np.broadcast_to(arr, (n_decades, months)).copy()
    elif arr.shape != (n_decades, months):
        raise ValueError(
            f"cycle must have shape ({months},) or ({n_decades}, {months}); got {arr.shape}"
        )
    if not np.all(np.isfinite(arr)):
        raise ValueError("cycle must be finite")
    if np.any(np.abs(arr) > 1.0 + 1e-12):
        raise ValueError("cycle values must lie in [-1, +1] (the WP2.6 c_t contract)")
    return arr


def simulate_decades(
    artifact: ClimateArtifact,
    n_decades: int,
    *,
    seed: int,
    months: int = 120,
    s0_date: str | pd.Timestamp | None = None,
    cycle: np.ndarray | None = None,
    theta_index: int | None = None,
) -> SimulatedClimate:
    """Simulate monthly five-state paths for ``n_decades`` decades.

    Each decade k: PCG64(seed + 7919*k) draws a posterior index (theta AND the
    smoothed state s0 at ``s0_date`` from the same draw -- the joint posterior),
    then Euler-steps the DN-1.1 dynamics for ``months`` months. ``theta_index``
    pins every decade to one posterior draw instead (s0 still that draw's).

    ``s0_date`` defaults to the last month of the fit span; any grid month works
    (the WP2.11 severe test starts from the 1965 climate state this way).
    """
    if n_decades < 1:
        raise ValueError("n_decades must be >= 1")
    if months < 1:
        raise ValueError("months must be >= 1")
    ts = artifact.dates[-1] if s0_date is None else pd.Timestamp(s0_date)
    locs = artifact.dates.get_indexer([ts])
    if locs[0] < 0:
        raise ValueError(
            f"s0_date {ts.date()} is not on the artifact's monthly grid "
            f"({artifact.dates[0].date()} .. {artifact.dates[-1].date()})"
        )
    t0 = int(locs[0])
    if theta_index is not None and not (0 <= theta_index < artifact.n_draws):
        raise ValueError(f"theta_index {theta_index} outside [0, {artifact.n_draws})")

    cyc = _validate_cycle(cycle, n_decades, months)

    out = np.empty((n_decades, months, N_STATES), dtype=np.float64)
    idx = np.empty(n_decades, dtype=np.int64)
    for k in range(n_decades):
        rng = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k))
        draw = int(rng.integers(artifact.n_draws)) if theta_index is None else int(theta_index)
        idx[k] = draw
        theta = {name: float(artifact.params[name][draw]) for name in PARAM_NAMES}
        s0 = artifact.states[draw, t0, :]
        out[k] = _simulate_path(theta, s0, months, cyc[k], rng)

    params = {name: artifact.params[name][idx] for name in PARAM_NAMES}
    return SimulatedClimate(states=out, theta_index=idx, params=params, s0_date=ts, seed=seed)


def simulate_decades_from_state(
    artifact: ClimateArtifact,
    n_decades: int,
    *,
    seed: int,
    s0: np.ndarray,
    theta_index: int,
    months: int = 120,
    cycle: np.ndarray | None = None,
) -> SimulatedClimate:
    """Simulate continuations from an EXPLICIT state vector (wp5-03 re-coning).

    The mid-path conditioning entry point: the five-state dynamics are Markov in
    ``s``, so continuing from a simulated path's own month-``m`` state is EXACT
    -- the same :func:`_simulate_path` the fitted-date entry uses, handed the
    observed state instead of a posterior smoothed one. ``theta_index`` is
    REQUIRED, not drawn: a continuation conditions on the parameter draw the
    original decade was simulated under (recorded in
    :attr:`SimulatedClimate.theta_index`), because re-drawing theta mid-path
    would change the world's physics halfway through a history. Each of the
    ``n_decades`` continuation paths gets its own innovation stream
    (``PCG64(seed + 7919*k)``), which is what makes the result a CONDITIONAL
    ENSEMBLE from one state rather than one replay.

    ``s0_date`` on the result is set to the artifact's last grid month purely to
    satisfy the record's type; the state is the caller's, not a grid month's --
    consumers of re-coned climates read states, never s0_date.
    """
    if n_decades < 1:
        raise ValueError("n_decades must be >= 1")
    if months < 1:
        raise ValueError("months must be >= 1")
    s0 = np.asarray(s0, dtype=np.float64).reshape(-1)
    if s0.shape != (N_STATES,):
        raise ValueError(f"s0 must have shape ({N_STATES},); got {s0.shape}")
    if not np.all(np.isfinite(s0)):
        raise ValueError("s0 must be finite")
    if not (0 <= int(theta_index) < artifact.n_draws):
        raise ValueError(f"theta_index {theta_index} outside [0, {artifact.n_draws})")

    cyc = _validate_cycle(cycle, n_decades, months)
    theta = {name: float(artifact.params[name][int(theta_index)]) for name in PARAM_NAMES}

    out = np.empty((n_decades, months, N_STATES), dtype=np.float64)
    for k in range(n_decades):
        rng = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k))
        out[k] = _simulate_path(theta, s0, months, cyc[k], rng)

    idx = np.full(n_decades, int(theta_index), dtype=np.int64)
    params = {name: artifact.params[name][idx] for name in PARAM_NAMES}
    return SimulatedClimate(
        states=out, theta_index=idx, params=params, s0_date=artifact.dates[-1], seed=seed
    )


def _simulate_path(
    theta: Mapping[str, float],
    s0: np.ndarray,
    months: int,
    cycle: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Euler-discretized DN-1.1 SS II.2 dynamics for one decade (contract states).

    Mirrors :func:`ah.gen.climate.model.transition_matrix` /
    :func:`~ah.gen.climate.model.process_noise` exactly (r* carries beta_g times
    g's innovation in addition to its own); a test pins the two implementations
    to the same one-step moments.
    """
    k_pi = _LN2 / theta["hl_pi"]
    k_r = _LN2 / theta["hl_r"]
    k_g = _LN2 / theta["hl_g"]
    k_v = _LN2 / theta["hl_v"]
    k_l = _LN2 / theta["hl_L"]
    sq = np.sqrt(DT)

    out = np.empty((months, N_STATES), dtype=np.float64)
    pi, r, g, v, credit = (float(s0[i]) for i in range(N_STATES))
    for t in range(months):
        out[t] = (pi, r, g, v, credit)
        if t == months - 1:
            break
        eps = rng.standard_normal(N_STATES)
        dg = k_g * (theta["mu_g"] - g) * DT + theta["sigma_g"] * sq * eps[2]
        pi = pi + k_pi * (theta["mu_pi"] - pi) * DT + theta["sigma_pi"] * sq * eps[0]
        r = (
            r
            + k_r * (theta["mu_r"] - r) * DT
            + theta["beta_g"] * dg
            + theta["sigma_r"] * sq * eps[1]
        )
        g = g + dg
        v = v - k_v * v * DT + theta["sigma_v"] * sq * eps[3]
        l_bar = theta["delta_L"] * cycle[t]
        credit = credit + k_l * (l_bar - credit) * DT + theta["sigma_L"] * sq * eps[4]
    return out


def policy_anchor(
    sim: SimulatedClimate,
    *,
    cycle: np.ndarray | None = None,
    pi_actual: np.ndarray | None = None,
) -> np.ndarray:
    """The Taylor-type anchor i_t = r* + pi* + phi_pi(pi_t - pi*) + phi_c c_t.

    ``pi_actual`` (actual inflation, from L3/L4 downstream) defaults to pi_star
    -- at waypoint granularity the transitory gap averages out. ``cycle`` follows
    the same contract as :func:`simulate_decades`; returns (n_decades, months).
    Noise-free by design: waypoints want the anchor's conditional mean.
    """
    cyc = _validate_cycle(cycle, sim.n_decades, sim.months)
    pi_star = sim.state("pi_star")
    r_star = sim.state("r_star")
    pi_act = pi_star if pi_actual is None else np.asarray(pi_actual, dtype=np.float64)
    if pi_act.shape != pi_star.shape:
        raise ValueError(f"pi_actual must have shape {pi_star.shape}; got {pi_act.shape}")
    phi_pi = sim.params["phi_pi"][:, None]
    phi_c = sim.params["phi_c"][:, None]
    return r_star + pi_star + phi_pi * (pi_act - pi_star) + phi_c * cyc
