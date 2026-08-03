"""WP2.8 constraints — hard floors via transformed coordinates (DN-1.1 §II.4).

The block generators never see factor units: every factor is mapped to an
unconstrained coordinate before training, and every sampled batch is mapped back
after sampling, so a floor violation is STRUCTURALLY impossible — not filtered,
not clamped after the fact, impossible by the codomain of the inverse map.

The floors are the sealed manifest/conventions floors the joinery already
re-applies (:mod:`ah.gen.joinery.waypoints` restates them; a WP2.7 test pins
them to the ``ah.eval.metrics.economics`` originals so the statements cannot
drift): rates at -1.0 percentage points, spreads at 0.0. DN-1.1 §II.4's
illustrative "spread ≥ 100bp" is SUPERSEDED by the sealed conventions'
``SPREAD_FLOOR_PCT = 0.0`` (the WP2.2c ratification) — recorded here plainly.

Coordinate map, per sealed ``bootstrap_v1.factor_set`` factor:

- rates (``policy_rate``, ``ust_2y``, ``ust_10y``, ``hqm_curve``):
  ``z = softplus⁻¹(y - RATE_FLOOR_PCT)`` — generated in softplus space with the
  -1.0 floor; ``y = floor + softplus(z) ≥ floor`` for every real ``z`` (equality
  only at softplus underflow, which is not a violation: the sealed
  ``floor_violations`` estimator counts ``value < floor`` strictly).
- spreads (``ig_spread``, ``funding_spread``): same, floor 0.0.
- ``cpi``: ``z = log(y)`` — a positive price-index level, log space.
- ``equity_vol``: ``z = log(y)``. NOT a sealed floor — no conventions floor
  names equity_vol — but a volatility level is structurally positive, and log
  space is the standard positive-level coordinate; recorded as a structural
  choice, not a sealed requirement.
- returns (``equity_mkt``, ``smb``, ``hml``, ``mom``): ``z = log1p(r)`` —
  DN-1.1's "prices in log space" applied to simple monthly returns, giving
  ``r > -1`` by construction (a -100% month is impossible; the draw-span minimum
  is far above it). smb/hml/mom are zero-cost overlays for which ``r ≤ -1`` is
  not theoretically excluded, only structurally imposed here; recorded.

Round-trip exactness is tested bit-tight within float64 tolerance, and floor
impossibility is tested BY CONSTRUCTION (arbitrary z, including ±1e6), not by
sampling luck. numpy and torch implementations agree to float64 precision; the
torch path is differentiable (training uses it inside the loss).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ah.gen.joinery.waypoints import (
    RATE_FLOOR_FACTORS,
    RATE_FLOOR_PCT,
    SPREAD_FLOOR_FACTORS,
    SPREAD_FLOOR_PCT,
    JoineryError,
)

if TYPE_CHECKING:  # torch is imported lazily so numpy-only callers stay light
    import torch

__all__ = [
    "IDENTITY_FACTORS",
    "LOG1P_FACTORS",
    "LOG_FACTORS",
    "TRANSFORMS",
    "FactorTransform",
    "panel_to_constrained",
    "panel_to_constrained_torch",
    "panel_to_unconstrained",
    "transform_for",
]

#: Positive price-index / positive-level factors generated in log space.
#: fx_usd (campaign-2): a positive trade-weighted index level, same shape as cpi.
LOG_FACTORS: tuple[str, ...] = ("cpi", "equity_vol", "fx_usd")

#: Unbounded signed levels generated as-is (campaign-2): cape_v is ALREADY a
#: demeaned natural log (ah.data.derive.demeaned_log_cape), so its honest
#: unconstrained coordinate is itself -- re-logging a signed quantity is not a map.
IDENTITY_FACTORS: tuple[str, ...] = ("cape_v",)

#: Simple monthly returns generated in log1p space (r > -1 by construction).
LOG1P_FACTORS: tuple[str, ...] = ("equity_mkt", "smb", "hml", "mom")

_SOFTPLUS_SATURATION = 30.0  # softplus(z) == z and softplus^-1(u) == u beyond this


class FactorTransform:
    """One factor's (unconstrained <-> constrained) coordinate pair.

    ``kind`` in {"softplus_floor", "log", "log1p", "identity"}; ``floor`` used only by
    ``softplus_floor``. Both directions exist in numpy (float64) and torch
    (dtype-preserving, differentiable).
    """

    def __init__(self, name: str, kind: str, floor: float = 0.0) -> None:
        self.name = name
        self.kind = kind
        self.floor = float(floor)

    # -- numpy ------------------------------------------------------------- #

    def to_unconstrained(self, y: np.ndarray) -> np.ndarray:
        y = np.asarray(y, dtype=np.float64)
        if self.kind == "softplus_floor":
            u = y - self.floor
            if np.any(u <= 0.0):
                raise JoineryError(
                    f"factor '{self.name}': value at or below its floor {self.floor} "
                    f"cannot be mapped to softplus space (min residual {u.min()})"
                )
            # softplus^-1(u) = log(expm1(u)); == u beyond saturation (expm1 overflows).
            return np.where(u > _SOFTPLUS_SATURATION, u, np.log(np.expm1(np.minimum(u, 60.0))))
        if self.kind == "log":
            if np.any(y <= 0.0):
                raise JoineryError(f"factor '{self.name}': log space needs positive levels")
            return np.log(y)
        if self.kind == "log1p":
            if np.any(y <= -1.0):
                raise JoineryError(f"factor '{self.name}': log1p space needs returns > -1")
            return np.log1p(y)
        if self.kind == "identity":
            return y.copy()
        raise JoineryError(f"unknown transform kind '{self.kind}'")

    def to_constrained(self, z: np.ndarray) -> np.ndarray:
        z = np.asarray(z, dtype=np.float64)
        if self.kind == "softplus_floor":
            # softplus(z) = log1p(exp(z)), == z beyond saturation. >= 0 always,
            # so the result is >= floor for EVERY real z — the structural claim.
            sp = np.where(z > _SOFTPLUS_SATURATION, z, np.log1p(np.exp(np.minimum(z, 60.0))))
            return self.floor + sp
        if self.kind == "log":
            return np.exp(z)
        if self.kind == "log1p":
            return np.expm1(z)
        if self.kind == "identity":
            return z.copy()
        raise JoineryError(f"unknown transform kind '{self.kind}'")

    # -- torch (differentiable; used inside the training loss) -------------- #

    def to_constrained_torch(self, z: torch.Tensor) -> torch.Tensor:
        import torch

        if self.kind == "softplus_floor":
            return self.floor + torch.nn.functional.softplus(z)
        if self.kind == "log":
            return torch.exp(z)
        if self.kind == "log1p":
            return torch.expm1(z)
        if self.kind == "identity":
            return z
        raise JoineryError(f"unknown transform kind '{self.kind}'")


def _build_transforms() -> dict[str, FactorTransform]:
    out: dict[str, FactorTransform] = {}
    for name in RATE_FLOOR_FACTORS:
        out[name] = FactorTransform(name, "softplus_floor", RATE_FLOOR_PCT)
    for name in SPREAD_FLOOR_FACTORS:
        out[name] = FactorTransform(name, "softplus_floor", SPREAD_FLOOR_PCT)
    for name in LOG_FACTORS:
        out[name] = FactorTransform(name, "log")
    for name in LOG1P_FACTORS:
        out[name] = FactorTransform(name, "log1p")
    for name in IDENTITY_FACTORS:
        out[name] = FactorTransform(name, "identity")
    return out


#: Every factor with a declared coordinate map (covers the sealed factor set;
#: hy_spread lives here too via SPREAD_FLOOR_FACTORS, ready for a future vintage).
TRANSFORMS: dict[str, FactorTransform] = _build_transforms()


def transform_for(factor: str) -> FactorTransform:
    """The declared transform for ``factor``; raises on an unmapped factor.

    An unmapped factor is a hard error, not a pass-through: a factor generated
    in raw units would silently escape its floor, which is the exact failure
    this module exists to make impossible.
    """
    try:
        return TRANSFORMS[factor]
    except KeyError:
        raise JoineryError(
            f"factor '{factor}' has no declared coordinate transform; every generated "
            f"factor must be mapped (known: {sorted(TRANSFORMS)})"
        ) from None


def panel_to_unconstrained(values: np.ndarray, factor_names: tuple[str, ...]) -> np.ndarray:
    """Map a ``(..., n_factors)`` panel in factor units to unconstrained coords."""
    values = np.asarray(values, dtype=np.float64)
    if values.shape[-1] != len(factor_names):
        raise JoineryError(
            f"panel last dim {values.shape[-1]} != len(factor_names) {len(factor_names)}"
        )
    out = np.empty_like(values)
    for j, name in enumerate(factor_names):
        out[..., j] = transform_for(name).to_unconstrained(values[..., j])
    return out


def panel_to_constrained(z: np.ndarray, factor_names: tuple[str, ...]) -> np.ndarray:
    """Inverse of :func:`panel_to_unconstrained` — floors hold by construction."""
    z = np.asarray(z, dtype=np.float64)
    if z.shape[-1] != len(factor_names):
        raise JoineryError(f"panel last dim {z.shape[-1]} != len(factor_names)")
    out = np.empty_like(z)
    for j, name in enumerate(factor_names):
        out[..., j] = transform_for(name).to_constrained(z[..., j])
    return out


def panel_to_constrained_torch(z: torch.Tensor, factor_names: tuple[str, ...]) -> torch.Tensor:
    """Torch inverse map, differentiable, ``(..., n_factors)`` — for the aux loss."""
    import torch

    if z.shape[-1] != len(factor_names):
        raise JoineryError(f"panel last dim {z.shape[-1]} != len(factor_names)")
    cols = [
        transform_for(name).to_constrained_torch(z[..., j]) for j, name in enumerate(factor_names)
    ]
    return torch.stack(cols, dim=-1)
