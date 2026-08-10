"""Shared synthetic builders for the WP2.7 joinery tests (no catalog, no network).

Everything here is deterministic and hand-computable: sources whose factor values are
simple functions of the month index and regime label, climate artifacts with constant
(or near-constant) posterior draws, and regime paths constructed directly. Real
artifacts (``experiments/``) are never read by unit tests -- they are exercised only by
``scripts/run_joinery_battery.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import ah.gen.climate.fit as cf
import ah.gen.regimes.fit as rf
from ah.gen import bootstrap as bs
from ah.gen.climate import simulate as cs
from ah.gen.regimes import semimarkov as sm

# The six ruleset labels, by code.
LABELS = sm.REGIME_LABELS
CODE = {label: i for i, label in enumerate(LABELS)}

#: The WP2.6 empirical cycle mapping (EXP/SLOW/STAG/REF=+1, CRI=-1, REC=+0.04).
CYCLE_BY_REGIME = np.array([1.0, 1.0, 0.04, -1.0, 1.0, 1.0])


def theta_base() -> dict[str, float]:
    """A full parameter dict for a synthetic climate artifact (all draws identical)."""
    return {
        "hl_pi": 12.0,
        "mu_pi": 2.5,
        "sigma_pi": 0.2,
        "hl_r": 15.0,
        "mu_r": 0.75,
        "beta_g": 1.0,
        "sigma_r": 0.3,
        "hl_g": 20.0,
        "mu_g": 2.0,
        "sigma_g": 0.25,
        "hl_v": 10.0,
        "sigma_v": 0.5,
        "a_val": 6.0,
        "b_val": 6.0,
        "hl_L": 8.0,
        "delta_L": 2.0,
        "sigma_L": 2.0,
        "mu_cr": 1.0,
        "sigma_tau": 0.5,
        "lam_cr": 0.7,
        "hl_u": 2.0,
        "sigma_u": 0.8,
        "phi_pi": 0.5,
        "phi_c": 0.5,
        "psi": 1.5,
        "sigma_i": 0.5,
        "s_m_pi": 1.5,
        "s_m_cape": 0.1,
        "s_q_bis": 2.0,
        "s_a_infl": 1.0,
        "s_a_stir": 1.0,
        "s_a_lt": 1.0,
        "s_a_g": 1.5,
        "s_a_cr": 3.0,
        "s_r10": 3.0,
    }


def make_climate_artifact(
    tmp_path,
    *,
    n_draws: int = 8,
    start: str = "1988-01-01",
    t_months: int = 480,
    pi_star: float = 3.0,
    r_star: float = 1.0,
    v: float = 0.0,
    credit_gap: float = 0.0,
    theta_overrides: dict[str, float] | None = None,
    state_noise: float = 0.0,
) -> cs.ClimateArtifact:
    """A climate artifact with near-constant states and identical posterior draws."""
    base = theta_base() | (theta_overrides or {})
    params = {name: np.full(n_draws, value, dtype=np.float64) for name, value in base.items()}
    states = np.zeros((n_draws, t_months, 5), dtype=np.float64)
    states[:, :, 0] = pi_star
    states[:, :, 1] = r_star
    states[:, :, 2] = base["mu_g"]
    states[:, :, 3] = v
    states[:, :, 4] = credit_gap
    if state_noise:
        rng = np.random.Generator(np.random.PCG64(7))
        states += state_noise * rng.standard_normal(states.shape)
    dates = pd.date_range(start, periods=t_months, freq="MS")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "climate.npz"
    cf.save_artifact(
        path,
        params=params,
        states=states,
        dates=dates,
        meta={"schema_version": "climate-artifact-v1", "seed": 0},
    )
    return cs.load_artifact(path)


def make_regimes_artifact(tmp_path, *, n_draws: int = 8) -> sm.RegimesArtifact:
    """A neutral L2 artifact: flat hazards, historical-frequency start, WP2.6 cycle."""

    def tile(base: np.ndarray) -> np.ndarray:
        return np.broadcast_to(base, (n_draws, *base.shape)).astype(np.float64).copy()

    draws = {
        "alpha": tile(np.zeros(6)),
        "gamma": tile(np.zeros((6, 4))),
        "r": tile(np.full(6, 3.0)),
        "trans_a": tile(np.zeros((6, 6))),
        "b_dest": tile(np.zeros((6, 4))),
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "regimes.npz"
    rf.save_artifact(
        path,
        draws=draws,
        cov_mean=np.array([0.7, 0.0, 1.0, 0.0]),
        cov_sd=np.array([1.2, 5.0, 2.0, 1.0]),
        cycle_by_regime=CYCLE_BY_REGIME,
        init_freqs=np.array([0.5, 0.15, 0.12, 0.05, 0.1, 0.08]),
        meta={
            "schema_version": rf.ARTIFACT_SCHEMA_VERSION,
            "ruleset_version": "regime_ruleset_v1",
            "pi_target": 2.0,
            "slope_psi0": 0.7,
            "slope_phi_c0": 0.1,
            "climate_artifact_sha256": "test" * 16,
        },
    )
    return sm.load_artifact(path)


#: Per-regime deterministic monthly equity return (decimal) used by make_source.
EQUITY_BY_REGIME = {
    "EXP": 0.012,
    "SLOW": 0.004,
    "REC": -0.010,
    "CRI": -0.045,
    "STAG": -0.002,
    "REF": 0.008,
}

#: Per-regime ig_spread level (pct) used by make_source.
SPREAD_BY_REGIME = {
    "EXP": 0.8,
    "SLOW": 1.0,
    "REC": 1.6,
    "CRI": 2.4,
    "STAG": 1.3,
    "REF": 0.9,
}


def default_labels(n_rows: int) -> tuple[str, ...]:
    cycle = ("EXP", "EXP", "EXP", "SLOW", "REC", "CRI", "STAG", "REF")
    return tuple(cycle[i % len(cycle)] for i in range(n_rows))


def make_source(
    n_rows: int = 240,
    *,
    start: str = "1990-01-01",
    labels: tuple[str, ...] | None = None,
) -> bs.BootstrapSource:
    """A synthetic source over the sealed factor set, regime-structured eq/spreads.

    Factor names are exactly the sealed ``bootstrap_v1.factor_set`` so joinery code
    that looks factors up by name works unchanged against the real source.
    """
    labels = default_labels(n_rows) if labels is None else labels
    t = np.arange(n_rows, dtype=np.float64)
    eq = np.array([EQUITY_BY_REGIME[label] for label in labels])
    spread = np.array([SPREAD_BY_REGIME[label] for label in labels])
    columns = {
        # ~3.05%/yr — near the synthetic climate's pi* of 3, so the structural
        # inflation waypoints and the source's own inflation are consistent.
        "cpi": 100.0 * np.exp(0.0025 * t),
        "equity_mkt": eq + 0.001 * np.sin(t),
        "equity_vol": 18.0 + 4.0 * np.cos(t / 7.0),
        "funding_spread": 0.4 + 0.1 * np.sin(t / 5.0),
        "hml": 0.002 * np.cos(t / 3.0),
        "hqm_curve": 5.0 + 0.5 * np.sin(t / 11.0),
        "ig_spread": spread + 0.05 * np.sin(t / 4.0),
        "mom": 0.003 * np.sin(t / 2.0),
        # mean 4.5 — the synthetic climate's neutral anchor (r*+pi*+phi_c) under an
        # EXP cycle, so structural policy waypoints and the source are consistent.
        "policy_rate": 4.5 + 1.5 * np.sin(t / 13.0),
        "smb": 0.001 * np.sin(t / 6.0),
        "ust_10y": 4.0 + np.sin(t / 17.0),
        "ust_2y": 3.5 + np.sin(t / 15.0),
        # campaign-2 factors. hy tracks the regime spread at the pinned-splice
        # scale (a + b*(Baa-Aaa)-shaped); fx is a positive index level; cape_v is
        # a signed demeaned log (identity coordinate), small-amplitude.
        "hy_spread": 1.4 + 2.5 * spread + 0.1 * np.sin(t / 4.0),
        "fx_usd": 100.0 + 8.0 * np.sin(t / 19.0),
        "cape_v": 0.3 * np.sin(t / 23.0),
    }
    # The CAMPAIGN-2 set: the joinery under test assembles campaign-2-era
    # checkpoints, whose feature dimensions are a fact about that campaign.
    # Campaign-3 moved the live FACTOR_SET to sixteen (commodities joined,
    # AM-2026-08-10-001); these synthetic columns deliberately stay fifteen.
    factor_names = bs.CAMPAIGN2_FACTOR_SET
    values = np.column_stack([columns[name] for name in factor_names])
    return bs.BootstrapSource(
        factor_names=factor_names,
        dates=pd.DatetimeIndex(pd.date_range(start, periods=n_rows, freq="MS")),
        values=values,
        labels=tuple(labels),
        ruleset_version="regime_ruleset_v1",
        vintage_id="test-vintage",
        active_blocks=("global", "us", "fx", "valuation"),
    )


def make_planted_beta_pair(
    tmp_path, *, beta: float = 0.3, n_rows: int = 240
) -> tuple[cs.ClimateArtifact, bs.BootstrapSource]:
    """A (climate, source) pair with a PLANTED spread-on-credit-gap loading.

    The climate artifact's smoothed credit-gap path is sin(t/9) and the source's
    ig_spread column carries ``beta`` times that path, so
    ``source_stats(...).spread_beta_credit_gap`` must recover ``beta`` — and a
    two-pass re-run of L1 (which moves the credit gap through the cycle forcing)
    visibly moves the spread waypoints.
    """
    t_months = 480
    t = np.arange(t_months, dtype=np.float64)
    gap = np.sin(t / 9.0)
    first = make_climate_artifact(tmp_path, t_months=t_months)
    with np.load(first.path, allow_pickle=False) as npz:
        arrays = {k: npz[k].copy() for k in npz.files}
    arrays["states"][:, :, 4] = gap
    path = tmp_path / "climate-planted.npz"
    cf.save_artifact(
        path,
        params={name: arrays[f"param_{name}"] for name in cs.PARAM_NAMES},
        states=arrays["states"],
        dates=pd.DatetimeIndex(arrays["dates"].astype("datetime64[M]")),
        meta={"schema_version": "climate-artifact-v1", "seed": 0},
    )
    climate = cs.load_artifact(path)

    source = make_source(n_rows)
    idx = climate.dates.get_indexer(source.dates)
    values = source.values.copy()
    spread_col = list(source.factor_names).index("ig_spread")
    values[:, spread_col] = values[:, spread_col] + beta * gap[idx]
    source = bs.BootstrapSource(
        factor_names=source.factor_names,
        dates=source.dates,
        values=values,
        labels=source.labels,
        ruleset_version=source.ruleset_version,
        vintage_id=source.vintage_id,
        active_blocks=source.active_blocks,
    )
    return climate, source


def make_regime_paths(
    labels: np.ndarray,
    *,
    seed: int = 0,
    mode: str = "semimarkov",
) -> sm.RegimePaths:
    """A RegimePaths constructed directly from integer label codes."""
    labels = np.asarray(labels, dtype=np.int64)
    return sm.RegimePaths(
        labels=labels,
        cycle=CYCLE_BY_REGIME[labels],
        theta_index=np.zeros(labels.shape[0], dtype=np.int64),
        seed=seed,
        mode=mode,
        ruleset_version="regime_ruleset_v1",
    )
