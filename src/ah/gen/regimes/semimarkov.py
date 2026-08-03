"""WP2.6 Layer 2 -- the semi-Markov regime skeleton, sampling side (numpy only).

DN-1.1 SS II.3: a semi-Markov chain over the six Step-1 ruleset states
(:data:`ah.data.derive.REGIME_LABELS` order: EXP, SLOW, REC, CRI, STAG, REF).
Sojourns are Negative Binomial with a logit link to slow-state covariates;
transition rows are multinomial-logit linked to the same covariates. Fitting
lives in :mod:`ah.gen.regimes.fit` (numpyro); this module is the generation-time
consumer: config, the hash-verified posterior artifact, and seeded simulation.

Conventions (recorded here because DN-1.1 states the functional forms only):

- **Sojourn**: ``D = 1 + X``, ``X ~ NegBin(r_k, p_k(s))`` in the
  failures-before-r-th-success parameterization (``P(X=x) proportional to
  (1-p)^x p^r``), so durations are >= 1 month, ``E[D] = 1 + r_k(1-p_k)/p_k``,
  and a HIGHER ``p`` means a SHORTER sojourn. ``logit p_k = alpha_k +
  gamma_k' z(s)``, z evaluated at the spell's first month.
- **Transitions**: leaving state k, the destination j != k has logit
  ``eta_kj = a_kj + b_j' z(s)`` with z at the transition month. ``b_j`` is
  shared across origin rows (destination loadings -- DN-1.1's "crisis hazard
  rises with leverage and inversion" is a statement about the CRI column);
  identification pins ``b_EXP = 0`` and one intercept per row
  (``a_{k,EXP} = 0`` for k != EXP, ``a_{EXP,SLOW} = 0``).
- **Covariates** ``z(s)``, exactly DN-1.1's list, in this order:
  ``(curve_slope, credit_gap, pi_gap, drawdown_state)``.
  Historically (fitting): observed GS10-TB3MS slope (JST annual long-short
  spread before 1953), the L1 posterior-mean credit gap and ``pi* - pi_target``
  paths, and the equity-drawdown crisis indicator. At SIMULATION time every
  component must be a function of what Layer 1 hands over -- the
  ``(n_decades, months, 5)`` slow-state paths -- plus the regime path itself:

  ============== ============================== =================================
  covariate      historical (fit)               simulated
  ============== ============================== =================================
  curve_slope    GS10-TB3MS (JST spliced)       psi0 - phi_c0 * c(R_t)  [proxy]
  credit_gap     L1 posterior-mean credit_gap   simulated ``credit_gap`` state
  pi_gap         L1 posterior-mean pi* - target simulated ``pi_star`` - target
  drawdown_state 1[drawdown <= crisis thr]      1[R_t == CRI]
  ============== ============================== =================================

  ``psi0``/``phi_c0`` are the L1 posterior means of the term premium and the
  anchor's cycle loading, recorded in the artifact meta: the model-implied slope
  is ``(pi*+r*+psi) - (r*+pi*+phi_pi(pi-pi*)+phi_c c)`` which at ``pi = pi*``
  is ``psi - phi_c c``. The proxy carries the level of the historical slope but
  compresses its variance (no simulated inversions), so the inversion channel of
  the fitted hazards is attenuated at generation time -- recorded as a v1
  limitation in regime-fit-report.md, revisit if WP2.7's waypoints emit a rate
  spread. Standardization constants (train+val mean/sd per covariate; the 0/1
  drawdown dummy is left unstandardized) are stored in the artifact and applied
  identically on both sides.

The cycle term c_t (the WP2.5 contract, fulfilled here)
-------------------------------------------------------
``RegimePaths.cycle`` is ``cycle_by_regime[labels]``: a per-regime constant
mapping, values in [-1, +1], no smoothing. The mapping is EMPIRICAL, computed at
fit time as the train+val mean of L1's own fitting proxy ``1 - 2*USREC`` within
each label -- which is exactly what keeps the fitted ``phi_c``/``delta_L``
meaningful when L2's c_t replaces the proxy at simulation time. By ruleset
construction CRI months always have USREC=1 (c=-1) and EXP/SLOW/STAG/REF months
always have USREC=0 (c=+1); REC mixes NBER and non-NBER contraction months and
lands strictly between. A step function is deliberately on-scale: the proxy the
anchor was fitted against is itself a +/-1 step function.

Determinism: all randomness flows through ``numpy.random.Generator(PCG64)``;
decade/path k uses ``seed + 7919*k`` (:data:`SEED_STRIDE`). No clock reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, Field, model_validator

from ah.core.worldspec import Horizon, Regimes
from ah.data import derive
from ah.gen.bootstrap import WORLDSPEC_REGIME_TO_LABEL
from ah.gen.climate.simulate import content_sha256

__all__ = [
    "COVARIATE_NAMES",
    "N_COVARIATES",
    "N_REGIMES",
    "REGIME_LABELS",
    "SEED_STRIDE",
    "RegimePaths",
    "RegimesArtifact",
    "RegimesConfig",
    "RegimesError",
    "SensitivityThresholds",
    "config_dict",
    "load_artifact",
    "load_config",
    "regime_path_for_world",
    "simulate_regimes",
    "simulate_regimes_from_spell",
    "spell_covariates",
    "spells_from_labels",
]

#: CLAUDE.md's ensemble seed stride: decade/path k uses PCG64(base_seed + 7919*k).
SEED_STRIDE = 7919

#: The six Step-1 ruleset labels, in ah.data.derive order (EXP..REF); integer
#: codes throughout this package are indices into this tuple.
REGIME_LABELS: tuple[str, ...] = tuple(derive.REGIME_LABELS)
N_REGIMES = len(REGIME_LABELS)
_LABEL_INDEX = {label: i for i, label in enumerate(REGIME_LABELS)}
_CRI = _LABEL_INDEX["CRI"]

#: DN-1.1 SS II.3's z(s), fixed order.
COVARIATE_NAMES: tuple[str, ...] = ("curve_slope", "credit_gap", "pi_gap", "drawdown_state")
N_COVARIATES = len(COVARIATE_NAMES)

#: L1's five-state order (ah.gen.climate.model.STATE_NAMES); restated indices so
#: this module's hot loop does not need the climate import at call time.
_STATE_PI_STAR = 0
_STATE_CREDIT_GAP = 4
N_STATES = 5


class RegimesError(RuntimeError):
    """Raised for a malformed config/artifact or an unsatisfiable simulation request."""


# --------------------------------------------------------------------------- #
# config (YAML -> pydantic, hashed into the experiment record)
# --------------------------------------------------------------------------- #


class PriorSpec(BaseModel):
    loc: float
    scale: float = Field(gt=0)


class RegimesPriors(BaseModel):
    alpha: PriorSpec
    gamma: PriorSpec
    log_r: PriorSpec
    trans_a: PriorSpec
    trans_b: PriorSpec


class SeriesIds(BaseModel):
    gs10_monthly: str
    tb3ms_monthly: str
    jst_ltrate: str
    jst_stir: str
    cpi_monthly: str
    equity_mkt_rf: str
    equity_rf: str
    usrec_monthly: str
    indpro_monthly: str


class SensitivityThresholds(BaseModel):
    """The regime_ruleset_v1b variant, passed to the labeler as its ``thr`` dict."""

    version: str
    cpi_high: float
    growth_weak: float
    growth_slow: float
    drawdown_crisis: float
    hy_crisis: float

    @model_validator(mode="after")
    def _ordered(self) -> SensitivityThresholds:
        if not self.growth_slow > self.growth_weak:
            raise ValueError(
                f"growth_slow ({self.growth_slow}) must exceed growth_weak "
                f"({self.growth_weak}); the labeler's bands would invert"
            )
        if self.drawdown_crisis >= 0:
            raise ValueError("drawdown_crisis must be negative (a drawdown fraction)")
        return self


class FitSettings(BaseModel):
    chains: int = 4
    warmup: int = 1000
    samples: int = 1000
    target_accept: float = 0.9
    max_tree_depth: int = 10
    dense_mass: bool = False
    chain_method: str = "sequential"
    artifact_draws: int = 1000


class AcceptanceSettings(BaseModel):
    n_boot: int = 1000
    bootstrap_mean_block_months: int = 120
    bootstrap_seed: int = 20260727
    sim_n_decades: int = 512
    sim_months: int = 120
    sim_seed: int = 20260727
    band_lo: float = Field(default=0.025, gt=0, lt=0.5)
    band_hi: float = Field(default=0.975, gt=0.5, lt=1.0)


class RegimesConfig(BaseModel):
    priors: RegimesPriors
    pi_target: float
    series: SeriesIds
    sensitivity: SensitivityThresholds
    fit: FitSettings
    acceptance: AcceptanceSettings


_DEFAULT_CONFIG_PATH = Path(__file__).with_name("priors.yaml")


def load_config(path: str | Path | None = None) -> RegimesConfig:
    """Load the regimes config (default: the packaged ``priors.yaml``)."""
    p = _DEFAULT_CONFIG_PATH if path is None else Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return RegimesConfig.model_validate(raw)


def config_dict(config: RegimesConfig) -> dict[str, Any]:
    """A canonical plain-dict rendering for ``ah.experiment.config_hash``."""
    return config.model_dump(mode="json", exclude_none=True)


# --------------------------------------------------------------------------- #
# the artifact
# --------------------------------------------------------------------------- #

#: Posterior-draw arrays every artifact must carry, with their per-draw shapes.
_DRAW_SHAPES: dict[str, tuple[int, ...]] = {
    "alpha": (N_REGIMES,),
    "gamma": (N_REGIMES, N_COVARIATES),
    "r": (N_REGIMES,),
    "trans_a": (N_REGIMES, N_REGIMES),
    "b_dest": (N_REGIMES, N_COVARIATES),
}


@dataclass(frozen=True)
class RegimesArtifact:
    """A loaded, hash-verified L2 posterior artifact.

    Draw arrays have a leading ``n_draws`` axis; ``trans_a``/``b_dest`` are the
    FULL matrices (identification zeros already in place), so simulation never
    needs the fit-side scatter indices.
    """

    alpha: np.ndarray  # (n_draws, 6)
    gamma: np.ndarray  # (n_draws, 6, 4)
    r: np.ndarray  # (n_draws, 6)
    trans_a: np.ndarray  # (n_draws, 6, 6)
    b_dest: np.ndarray  # (n_draws, 6, 4)
    cov_mean: np.ndarray  # (4,)
    cov_sd: np.ndarray  # (4,)
    cycle_by_regime: np.ndarray  # (6,) values in [-1, +1]
    init_freqs: np.ndarray  # (6,) historical label frequencies, sum 1
    meta: dict
    path: Path

    @property
    def n_draws(self) -> int:
        return int(self.alpha.shape[0])


def load_artifact(path: str | Path) -> RegimesArtifact:
    """Load and verify a regimes posterior artifact (canonical content SHA-256).

    Same discipline as :func:`ah.gen.climate.simulate.load_artifact`: the hash
    covers every array plus the meta JSON, is stored inside the file, and is
    re-verified on every load, so a loaded artifact is bit-for-bit the one that
    was saved.
    """
    import json

    p = Path(path)
    if not p.exists():
        raise RegimesError(f"regimes artifact not found: {p}")
    with np.load(p, allow_pickle=False) as npz:
        data = {name: npz[name] for name in npz.files}

    required = (
        *(_DRAW_SHAPES),
        "cov_mean",
        "cov_sd",
        "cycle_by_regime",
        "init_freqs",
        "meta_json",
        "content_sha256",
    )
    for name in required:
        if name not in data:
            raise RegimesError(f"artifact {p} is missing entry '{name}'")

    stored_hash = str(data.pop("content_sha256")[()])
    meta_json = str(data["meta_json"][()])
    recomputed = content_sha256(data, meta_json)
    if recomputed != stored_hash:
        raise RegimesError(
            f"artifact {p} content hash mismatch: stored {stored_hash[:16]}..., "
            f"recomputed {recomputed[:16]}... (file corrupted or tampered)"
        )

    draws = {name: np.asarray(data[name], dtype=np.float64) for name in _DRAW_SHAPES}
    n_draws = draws["alpha"].shape[0]
    for name, shape in _DRAW_SHAPES.items():
        if draws[name].shape != (n_draws, *shape):
            raise RegimesError(
                f"artifact {p}: '{name}' has shape {draws[name].shape}, "
                f"expected {(n_draws, *shape)}"
            )

    fixed = {
        name: np.asarray(data[name], dtype=np.float64)
        for name in ("cov_mean", "cov_sd", "cycle_by_regime", "init_freqs")
    }
    for name, size in (
        ("cov_mean", N_COVARIATES),
        ("cov_sd", N_COVARIATES),
        ("cycle_by_regime", N_REGIMES),
        ("init_freqs", N_REGIMES),
    ):
        if fixed[name].shape != (size,):
            raise RegimesError(f"artifact {p}: '{name}' must have shape ({size},)")
    if np.any(np.abs(fixed["cycle_by_regime"]) > 1.0 + 1e-12):
        raise RegimesError("cycle_by_regime must lie in [-1, +1] (the c_t contract)")
    if not np.isclose(fixed["init_freqs"].sum(), 1.0, atol=1e-9):
        raise RegimesError("init_freqs must sum to 1")

    meta = json.loads(meta_json)
    meta["content_sha256"] = stored_hash
    return RegimesArtifact(**draws, **fixed, meta=meta, path=p)


# --------------------------------------------------------------------------- #
# simulation output
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegimePaths:
    """Simulated regime paths and their cycle term.

    ``labels``: ``(n_decades, months)`` integer codes into
    :data:`REGIME_LABELS`. ``cycle``: same shape, float64 in [-1, +1] -- the
    WP2.5 c_t contract array, feedable to
    :func:`ah.gen.climate.simulate.simulate_decades` unchanged. ``theta_index``
    is -1 where no posterior draw was consumed (sequence mode)."""

    labels: np.ndarray
    cycle: np.ndarray
    theta_index: np.ndarray
    seed: int
    mode: str
    ruleset_version: str

    @property
    def n_decades(self) -> int:
        return int(self.labels.shape[0])

    @property
    def months(self) -> int:
        return int(self.labels.shape[1])

    def label_strings(self, decade: int) -> list[str]:
        return [REGIME_LABELS[int(code)] for code in self.labels[decade]]


def spells_from_labels(labels: np.ndarray) -> list[tuple[int, int, int]]:
    """Decompose a label-code sequence into runs: ``(state, start, duration)``."""
    arr = np.asarray(labels)
    if arr.ndim != 1 or arr.size == 0:
        raise RegimesError(f"labels must be a non-empty 1-d sequence; got shape {arr.shape}")
    boundaries = np.flatnonzero(np.diff(arr)) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [arr.size]))
    return [(int(arr[s]), int(s), int(e - s)) for s, e in zip(starts, ends, strict=True)]


# --------------------------------------------------------------------------- #
# the fitted semi-Markov sampler (conditioned on slow states)
# --------------------------------------------------------------------------- #


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max()
    exp = np.exp(shifted)
    return exp / exp.sum()


def _standardize(raw: np.ndarray, artifact: RegimesArtifact) -> np.ndarray:
    return (raw - artifact.cov_mean) / artifact.cov_sd


def _sim_covariates(
    artifact: RegimesArtifact, state_row: np.ndarray, regime: int, psi0: float, phi_c0: float
) -> np.ndarray:
    """Standardized z(s) at one simulated month, given the current regime."""
    c = float(artifact.cycle_by_regime[regime])
    raw = np.array(
        [
            psi0 - phi_c0 * c,  # curve slope proxy (see module docstring)
            float(state_row[_STATE_CREDIT_GAP]),
            float(state_row[_STATE_PI_STAR]) - float(artifact.meta["pi_target"]),
            1.0 if regime == _CRI else 0.0,
        ]
    )
    return _standardize(raw, artifact)


def simulate_regimes(
    artifact: RegimesArtifact,
    states: np.ndarray,
    *,
    seed: int,
    theta_index: int | None = None,
    initial_regime: int | None = None,
) -> RegimePaths:
    """Simulate one regime path per decade of L1 slow states.

    ``states`` is the ``(n_decades, months, 5)`` array of
    :func:`ah.gen.climate.simulate.simulate_decades` (STATE_NAMES order). Decade
    k seeds ``PCG64(seed + 7919*k)`` and draws its own posterior index -- L2
    parameter uncertainty sits inside the ensemble exactly as L1's does;
    ``theta_index`` pins one draw (ablation/testing). ``initial_regime`` pins
    the first spell's state; by default it is drawn from the artifact's
    historical label frequencies.

    Seed hygiene: passing the SAME base seed used for the L1
    ``simulate_decades`` call makes decade k open an identical PCG64 stream in
    both layers, so (when the two artifacts have equal draw counts) the two
    posterior indices coincide. That pairing is statistically harmless -- the
    posteriors are independent, so any index pairing is a valid product-
    posterior draw -- but a pipeline (WP2.7) should pass distinct base seeds
    per layer so the layers' randomness is unentangled by construction.

    Per spell: z(s) at the spell's first month -> NegBin sojourn; at the spell's
    end, z(s) at the transition month (still under the outgoing regime's cycle
    and drawdown values) -> multinomial-logit destination. Self-transitions are
    structurally impossible (the sojourn owns persistence).
    """
    arr = np.asarray(states, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[2] != N_STATES:
        raise RegimesError(
            f"states must be (n_decades, months, {N_STATES}) from L1 simulate_decades; "
            f"got shape {arr.shape}"
        )
    n_decades, months = int(arr.shape[0]), int(arr.shape[1])
    if months < 1 or n_decades < 1:
        raise RegimesError("states must cover at least one decade and one month")
    if theta_index is not None and not (0 <= theta_index < artifact.n_draws):
        raise RegimesError(f"theta_index {theta_index} outside [0, {artifact.n_draws})")
    if initial_regime is not None and not (0 <= initial_regime < N_REGIMES):
        raise RegimesError(f"initial_regime {initial_regime} outside [0, {N_REGIMES})")

    psi0 = float(artifact.meta["slope_psi0"])
    phi_c0 = float(artifact.meta["slope_phi_c0"])

    labels = np.empty((n_decades, months), dtype=np.int64)
    idx = np.empty(n_decades, dtype=np.int64)
    for k in range(n_decades):
        rng = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k))
        draw = int(rng.integers(artifact.n_draws)) if theta_index is None else int(theta_index)
        idx[k] = draw
        alpha = artifact.alpha[draw]
        gamma = artifact.gamma[draw]
        r = artifact.r[draw]
        trans_a = artifact.trans_a[draw]
        b_dest = artifact.b_dest[draw]

        regime = (
            int(rng.choice(N_REGIMES, p=artifact.init_freqs))
            if initial_regime is None
            else int(initial_regime)
        )
        t = 0
        while t < months:
            z = _sim_covariates(artifact, arr[k, t], regime, psi0, phi_c0)
            logit_p = float(alpha[regime] + gamma[regime] @ z)
            p = 1.0 / (1.0 + np.exp(-logit_p))
            p = min(max(p, 1e-9), 1.0 - 1e-9)
            duration = 1 + int(rng.negative_binomial(float(r[regime]), p))
            end = min(t + duration, months)
            labels[k, t:end] = regime
            t = end
            if t >= months:
                break
            z_tr = _sim_covariates(artifact, arr[k, t], regime, psi0, phi_c0)
            logits = trans_a[regime] + b_dest @ z_tr
            logits[regime] = -np.inf
            regime = int(rng.choice(N_REGIMES, p=_softmax(logits)))

    cycle = artifact.cycle_by_regime[labels]
    return RegimePaths(
        labels=labels,
        cycle=cycle,
        theta_index=idx,
        seed=int(seed),
        mode="semimarkov",
        ruleset_version=str(artifact.meta.get("ruleset_version", "unknown")),
    )


# --------------------------------------------------------------------------- #
# WorldSpec regime modes (DN-1.1 SS II.3 binding; schemas/ field names)
# --------------------------------------------------------------------------- #


def spell_covariates(artifact: RegimesArtifact, state_row: np.ndarray, regime: int) -> np.ndarray:
    """The standardized z(s) at one month -- the public face of the private
    covariate constructor, for wp5-03 re-coning: a continuation must reproduce
    the ORIGINAL spell's sojourn covariates (z at the spell's first month, which
    sits in the observed prefix), and computing them anywhere else would fork
    the definition."""
    psi0 = float(artifact.meta["slope_psi0"])
    phi_c0 = float(artifact.meta["slope_phi_c0"])
    return _sim_covariates(
        artifact, np.asarray(state_row, dtype=np.float64), int(regime), psi0, phi_c0
    )


def _truncated_negbin_remaining(rng: np.random.Generator, r: float, p: float, elapsed: int) -> int:
    """Sample the REMAINING sojourn months, exactly, given ``elapsed`` already run.

    The spell's total is ``S = 1 + X`` with ``X ~ NegBin(r, p)``; a spell still
    running after ``elapsed`` months means ``S > elapsed``, i.e.
    ``X >= elapsed``. This inverts the conditional CDF ``X | X >= elapsed`` via
    the pmf recurrence ``pmf(k+1) = pmf(k) * (k + r) / (k + 1) * (1 - p)``
    (stable, no special functions) -- EXACT conditioning, no rejection loop to
    stall in a deep tail and no truncation cap to bias one. Returns
    ``S - elapsed >= 1``.
    """
    if elapsed < 1:
        raise RegimesError(f"elapsed must be >= 1 (a running spell); got {elapsed}")
    pmf = p**r  # pmf(0)
    cdf = pmf
    for k in range(elapsed - 1):
        pmf *= (k + r) / (k + 1.0) * (1.0 - p)
        cdf += pmf
    # cdf = P(X <= elapsed - 1); condition on the tail beyond it
    tail = 1.0 - cdf
    if tail <= 0.0:  # numerically exhausted tail: the spell ends now
        return 1
    target = cdf + float(rng.random()) * tail
    x = elapsed - 1
    acc = cdf
    while acc < target:
        x += 1
        pmf *= (x - 1 + r) / x * (1.0 - p)
        acc += pmf
        if pmf <= 0.0:
            break
    # The max-guard is the same "numerically exhausted tail" convention as the
    # early return above: float underflow deep in the tail means the remaining
    # mass is unrepresentable, and the spell ends now rather than at a made-up
    # horizon. Unreachable in any regime the fitted sojourns actually occupy.
    return max(1, 1 + x - elapsed)


def simulate_regimes_from_spell(
    artifact: RegimesArtifact,
    states: np.ndarray,
    *,
    seed: int,
    theta_index: int,
    current_regime: int,
    elapsed: int,
    spell_start_state: np.ndarray,
) -> RegimePaths:
    """Continue regime paths from MID-SPELL (wp5-03 re-coning) -- exactly.

    The conditioning state of a semi-Markov chain at month ``m`` is
    ``(current regime, elapsed months in the running spell)`` plus the
    covariates the running spell's sojourn was drawn against (z at the spell's
    FIRST month -- ``spell_start_state`` is that month's L1 state row, read from
    the observed prefix; both are derivable from an Ensemble's recorded labels
    and slow states). The remaining sojourn is drawn from the exact truncated
    NegBin (:func:`_truncated_negbin_remaining`); after the running spell ends,
    the chain proceeds under the ordinary machinery against the CONTINUATION's
    own states. ``theta_index`` is required: the continuation conditions on the
    posterior draw the original decade ran under (recorded in
    :attr:`RegimePaths.theta_index`).
    """
    arr = np.asarray(states, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[2] != N_STATES:
        raise RegimesError(f"states must be (n_decades, months, {N_STATES}); got shape {arr.shape}")
    n_decades, months = int(arr.shape[0]), int(arr.shape[1])
    if not (0 <= int(theta_index) < artifact.n_draws):
        raise RegimesError(f"theta_index {theta_index} outside [0, {artifact.n_draws})")
    if not (0 <= int(current_regime) < N_REGIMES):
        raise RegimesError(f"current_regime {current_regime} outside [0, {N_REGIMES})")

    psi0 = float(artifact.meta["slope_psi0"])
    phi_c0 = float(artifact.meta["slope_phi_c0"])
    draw = int(theta_index)
    alpha = artifact.alpha[draw]
    gamma = artifact.gamma[draw]
    r = artifact.r[draw]
    trans_a = artifact.trans_a[draw]
    b_dest = artifact.b_dest[draw]

    z0 = spell_covariates(artifact, spell_start_state, int(current_regime))
    logit_p = float(alpha[current_regime] + gamma[current_regime] @ z0)
    p0 = 1.0 / (1.0 + np.exp(-logit_p))
    p0 = min(max(p0, 1e-9), 1.0 - 1e-9)

    labels = np.empty((n_decades, months), dtype=np.int64)
    idx = np.full(n_decades, draw, dtype=np.int64)
    for k in range(n_decades):
        rng = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k))
        remaining = _truncated_negbin_remaining(rng, float(r[current_regime]), p0, int(elapsed))
        regime = int(current_regime)
        end = min(remaining, months)
        labels[k, :end] = regime
        t = end
        while t < months:
            z_tr = _sim_covariates(artifact, arr[k, t], regime, psi0, phi_c0)
            logits = trans_a[regime] + b_dest @ z_tr
            logits[regime] = -np.inf
            regime = int(rng.choice(N_REGIMES, p=_softmax(logits)))
            z = _sim_covariates(artifact, arr[k, t], regime, psi0, phi_c0)
            logit = float(alpha[regime] + gamma[regime] @ z)
            p = 1.0 / (1.0 + np.exp(-logit))
            p = min(max(p, 1e-9), 1.0 - 1e-9)
            duration = 1 + int(rng.negative_binomial(float(r[regime]), p))
            spell_end = min(t + duration, months)
            labels[k, t:spell_end] = regime
            t = spell_end

    cycle = artifact.cycle_by_regime[labels]
    return RegimePaths(
        labels=labels,
        cycle=cycle,
        theta_index=idx,
        seed=int(seed),
        mode="semimarkov",
        ruleset_version=str(artifact.meta.get("ruleset_version", "unknown")),
    )


def regime_path_for_world(
    artifact: RegimesArtifact,
    regimes: Regimes,
    horizon: Horizon,
    *,
    n_paths: int,
    seed: int,
) -> RegimePaths:
    """Regime paths for a WorldSpec's ``regimes`` block (all three modes).

    - ``sequence``: pins R_t exactly (quarter segments -> months via
      ``quarter*3``); every month of the horizon must be covered (rule V10
      guarantees tiling for validated worlds; a gap raises here too). Regime
      names map to ruleset labels via
      :data:`ah.gen.bootstrap.WORLDSPEC_REGIME_TO_LABEL` (the platform's single
      copy of that mapping; recovery and deflation_boom collapse to EXP,
      recorded there). Seed-invariant by construction.
    - ``transition_matrix``: the AUTHORED quarterly matrix is honoured verbatim
      -- schemas/ wins on field definitions (states, row-stochastic ``matrix``,
      ``initial_state``); the fitted hazards are deliberately not substituted.
      Research pipelines wanting the fitted skeleton call
      :func:`simulate_regimes` directly.
    - ``unconditional``: iid monthly draws at the artifact's historical label
      frequencies -- "bypasses L2" (no semi-Markov dynamics), matching the
      benchmark bootstrap's unconditional composition.

    Path k uses ``PCG64(seed + 7919*k)`` in the stochastic modes.
    """
    if n_paths < 1:
        raise RegimesError("n_paths must be >= 1")
    months = int(horizon.quarters) * 3
    ruleset = str(artifact.meta.get("ruleset_version", "unknown"))

    if regimes.mode == "sequence":
        labels_row = _sequence_months(regimes, months)
        labels = np.broadcast_to(labels_row, (n_paths, months)).copy()
        theta = np.full(n_paths, -1, dtype=np.int64)
    elif regimes.mode == "transition_matrix":
        labels = _matrix_paths(regimes, months, n_paths, seed)
        theta = np.full(n_paths, -1, dtype=np.int64)
    elif regimes.mode == "unconditional":
        labels = np.empty((n_paths, months), dtype=np.int64)
        for k in range(n_paths):
            rng = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k))
            labels[k] = rng.choice(N_REGIMES, size=months, p=artifact.init_freqs)
        theta = np.full(n_paths, -1, dtype=np.int64)
    else:  # pragma: no cover - Regimes.mode is schema-constrained
        raise RegimesError(f"unknown regimes.mode '{regimes.mode}'")

    return RegimePaths(
        labels=labels,
        cycle=artifact.cycle_by_regime[labels],
        theta_index=theta,
        seed=int(seed),
        mode=str(regimes.mode),
        ruleset_version=ruleset,
    )


def _sequence_months(regimes: Regimes, months: int) -> np.ndarray:
    """Expand quarter segments to one label code per month; refuse gaps."""
    if not regimes.sequence:
        raise RegimesError("sequence mode requires a non-empty regimes.sequence")
    codes = np.full(months, -1, dtype=np.int64)
    for segment in regimes.sequence:
        label = WORLDSPEC_REGIME_TO_LABEL[segment.regime]
        code = _LABEL_INDEX[label]
        for quarter in range(int(segment.from_quarter), int(segment.to_quarter) + 1):
            lo = quarter * 3
            codes[lo : min(lo + 3, months)] = code
    if np.any(codes < 0):
        first = int(np.flatnonzero(codes < 0)[0])
        raise RegimesError(
            f"regime sequence does not tile the horizon: month {first} "
            f"(quarter {first // 3}) is covered by no segment (rule V10)"
        )
    return codes


def _matrix_paths(regimes: Regimes, months: int, n_paths: int, seed: int) -> np.ndarray:
    """Quarterly Markov chain per the authored transition matrix, x3 to months."""
    tm = regimes.transition_matrix
    if tm is None:
        raise RegimesError("transition_matrix mode requires a regimes.transition_matrix block")
    matrix = np.asarray(tm.matrix, dtype=np.float64)
    n_states = len(tm.states)
    if matrix.shape != (n_states, n_states):
        raise RegimesError(
            f"transition matrix must be {n_states}x{n_states} (states order); "
            f"got shape {matrix.shape}"
        )
    row_sums = matrix.sum(axis=1)
    bad = np.flatnonzero(np.abs(row_sums - 1.0) > 1e-6)
    if bad.size:
        raise RegimesError(
            f"transition matrix row {int(bad[0])} sums to {row_sums[bad[0]]:.6f}, not 1 (rule V11)"
        )
    # exact row-stochasticity for rng.choice after float round-off
    matrix = matrix / row_sums[:, None]
    codes = np.array(
        [_LABEL_INDEX[WORLDSPEC_REGIME_TO_LABEL[name]] for name in tm.states], dtype=np.int64
    )
    if tm.initial_state not in tm.states:
        raise RegimesError(
            f"initial_state '{tm.initial_state}' is not one of the matrix states {tm.states}"
        )
    start = tm.states.index(tm.initial_state)
    quarters = (months + 2) // 3

    labels = np.empty((n_paths, months), dtype=np.int64)
    for k in range(n_paths):
        rng = np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k))
        state = start
        path = np.empty(quarters, dtype=np.int64)
        for q in range(quarters):
            path[q] = codes[state]
            state = int(rng.choice(n_states, p=matrix[state]))
        labels[k] = np.repeat(path, 3)[:months]
    return labels
