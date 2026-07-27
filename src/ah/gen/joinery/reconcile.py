"""WP2.7 reconcile — Denton benchmarking to annual waypoints (DN-1.1 §II.5 step 5).

Each waypoint-bearing factor's monthly path is benchmarked to its annual waypoint
aggregates — exact low-frequency consistency, minimal high-frequency distortion
(Denton's movement-preservation objective, the sixty-year-old temporal-
disaggregation discipline DN-1.1 cites [11]) — then the platform's hard floors
are re-applied.

THE VARIANT TABLE (stated per plan: proportional Denton divides by the level, so
factors that cross zero get the additive variant):

======================  ======================  =====================================
factor                  variant                 why
======================  ======================  =====================================
``policy_rate``         additive, flow (annual  a rate CROSSES ZERO (ZLB decades sit
                        mean)                   at ~0; the floor is -1%): dividing by
                                                the level is undefined there.
``cpi``                 proportional, stock     a price index is strictly positive
                        (year-end level), via   and multiplicative: additive Denton
                        additive Denton ON THE  on log levels IS proportional Denton
                        LOG LEVEL               on levels, without the division.
``equity_mkt``          additive on monthly     returns cross zero every few months;
                        LOG returns, flow       annual aggregate = sum of monthly log
                        (annual log drift)      returns = the waypoint's log drift.
``ig_spread``           additive, stock, BAND   the waypoint is a band, not a point:
                                                a year-end inside [lo, hi] is left
                                                exactly alone; outside, benchmarked
                                                to the NEAREST band edge (minimal
                                                adjustment). Spreads sit near zero
                                                (floor 0.0), so additive.
======================  ======================  =====================================

The adjustment magnitude per factor per year is returned as a diagnostic — mean
|x - z| over the year's months, in the working space of the variant (pct for
levels, log for cpi, log-return for equity). Large means generator and structure
disagree, and disagreement is a finding (STEP2 §6): each factor carries a
``flagged`` bit against a stated threshold, and ``assemble`` aggregates the
distribution into the ensemble conditioning record. Denton can flatter a weak
generator — that is exactly why the magnitude is reported per system.

Deterministic: one linear solve per factor per decade, no RNG.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.gen.joinery.waypoints import (
    RATE_FLOOR_FACTORS,
    RATE_FLOOR_PCT,
    SPREAD_FLOOR_FACTORS,
    SPREAD_FLOOR_PCT,
    DecadeWaypoints,
    JoineryError,
    cum_log_cpi_targets,
    year_spans,
)

__all__ = [
    "VARIANT_BY_FACTOR",
    "DecadeReconciliation",
    "FactorReconciliation",
    "ReconcileConfig",
    "denton_additive",
    "reconcile_decade",
]

#: The stated per-factor variant table (see the module docstring).
VARIANT_BY_FACTOR: dict[str, str] = {
    "policy_rate": "additive",
    "cpi": "proportional_via_log",
    "equity_mkt": "additive_log_returns",
    "ig_spread": "additive_band",
}


@dataclass(frozen=True)
class ReconcileConfig:
    """Waypoint tolerances (post-reconciliation assertion) and 'large' flags.

    Tolerances are numerical-exactness checks — Denton is a linear solve, so the
    achieved aggregates sit at solver precision unless a hard floor clamped a
    reconciled cell afterwards (visible via ``floor_clamped_cells``).

    Flag thresholds define 'large, flagged reconciliation' per factor, in the
    variant's working space, on the mean |adjustment| within a year: 2.0pct for
    the two rate/spread levels (a structural disagreement of 200bp held for a
    year), 0.15 log for the price level (a 15% price-level drag), 0.05 log/month
    for equity (~0.6 log per year of drift disagreement).
    """

    tol_policy_pct: float = 1e-6
    tol_cpi_log: float = 1e-8
    tol_equity_log: float = 1e-8
    tol_spread_pct: float = 1e-6
    flag_policy_pct: float = 2.0
    flag_cpi_log: float = 0.15
    flag_equity_log: float = 0.05
    flag_spread_pct: float = 2.0


# --------------------------------------------------------------------------- #
# the Denton core
# --------------------------------------------------------------------------- #

Constraint = tuple[slice, float, str]  # (year span, target, "sum" | "last")


def denton_additive(z: np.ndarray, constraints: list[Constraint]) -> np.ndarray:
    """Additive first-difference Denton benchmarking.

    minimize   sum_t ((x_t - z_t) - (x_{t-1} - z_{t-1}))^2
    subject to sum(x[span]) = target        (kind "sum"), or
               x[span.stop - 1] = target    (kind "last")

    Movement preservation: the ADJUSTMENT is as smooth as the constraints allow,
    so the benchmarked series keeps the input's month-to-month movement. Solved
    exactly via the KKT system (T + m unknowns; T=120, m<=10 — trivial).
    """
    z = np.asarray(z, dtype=np.float64)
    t_len = z.shape[0]
    if t_len < 2:
        raise JoineryError("denton needs at least two months")
    m = len(constraints)
    if m == 0:
        return z.copy()

    a_mat = np.zeros((m, t_len))
    b_vec = np.zeros(m)
    for i, (span, target, kind) in enumerate(constraints):
        if kind == "sum":
            a_mat[i, span] = 1.0
        elif kind == "last":
            a_mat[i, span.stop - 1] = 1.0
        else:
            raise JoineryError(f"unknown constraint kind '{kind}'")
        b_vec[i] = float(target)

    # D: first-difference operator ((T-1) x T); objective (x-z)' D'D (x-z)
    d_mat = np.zeros((t_len - 1, t_len))
    idx = np.arange(t_len - 1)
    d_mat[idx, idx] = -1.0
    d_mat[idx, idx + 1] = 1.0
    dtd = d_mat.T @ d_mat

    kkt = np.zeros((t_len + m, t_len + m))
    kkt[:t_len, :t_len] = 2.0 * dtd
    kkt[:t_len, t_len:] = a_mat.T
    kkt[t_len:, :t_len] = a_mat
    rhs = np.concatenate([2.0 * dtd @ z, b_vec])
    solution = np.linalg.solve(kkt, rhs)
    return solution[:t_len]


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FactorReconciliation:
    """One factor's reconciliation diagnostic for one decade."""

    variant: str
    adjustment_by_year: np.ndarray  # mean |x - z| per year, working space
    max_abs_adjustment: float
    flagged: bool
    target: np.ndarray  # the annual aggregates asked for
    achieved: np.ndarray  # the annual aggregates delivered (post-floors)
    tolerance_ok: bool  # every year hit its target, or was floor-bound (see below)
    floor_clamped_cells: int = 0
    #: Years where the hard floor clamped reconciled cells. An annual-mean target
    #: sitting AT the floor is infeasible for any non-constant month path, and the
    #: floor wins by design (the plan re-applies floors AFTER Denton) -- so a
    #: floor-bound year is a structure-vs-floor disagreement, counted and visible,
    #: not a solver miss. tolerance_ok exempts exactly these years.
    n_floor_bound_years: int = 0


@dataclass(frozen=True)
class DecadeReconciliation:
    """All factors' diagnostics for one decade."""

    factors: dict[str, FactorReconciliation] = field(default_factory=dict)

    @property
    def any_flagged(self) -> bool:
        return any(f.flagged for f in self.factors.values())

    @property
    def tolerance_ok(self) -> bool:
        return all(f.tolerance_ok for f in self.factors.values())

    @property
    def floor_clamped_cells(self) -> int:
        return sum(f.floor_clamped_cells for f in self.factors.values())

    def summary(self) -> dict[str, Any]:
        """JSON-safe summary for the ensemble conditioning record."""
        return {
            name: {
                "variant": f.variant,
                "mean_abs_adjustment": float(f.adjustment_by_year.mean()),
                "max_abs_adjustment": float(f.max_abs_adjustment),
                "flagged": bool(f.flagged),
                "tolerance_ok": bool(f.tolerance_ok),
                "floor_clamped_cells": int(f.floor_clamped_cells),
                "n_floor_bound_years": int(f.n_floor_bound_years),
            }
            for name, f in self.factors.items()
        }


def _diagnose(
    variant: str,
    z: np.ndarray,
    x: np.ndarray,
    spans: list[slice],
    target: np.ndarray,
    achieved: np.ndarray,
    tol: float,
    flag: float,
    *,
    band: tuple[np.ndarray, np.ndarray] | None = None,
    floor_clamped: int = 0,
    floor_bound_years: np.ndarray | None = None,
) -> FactorReconciliation:
    adj = np.array([float(np.abs((x - z)[s]).mean()) for s in spans])
    if band is None:
        year_ok = np.abs(achieved - target) <= tol
    else:
        lo, hi = band
        year_ok = (achieved >= lo - tol) & (achieved <= hi + tol)
    if floor_bound_years is not None:
        year_ok = year_ok | floor_bound_years  # the floor wins by design; see the field doc
    return FactorReconciliation(
        variant=variant,
        adjustment_by_year=adj,
        max_abs_adjustment=float(np.abs(x - z).max()),
        flagged=bool(adj.max() > flag),
        target=target,
        achieved=achieved,
        tolerance_ok=bool(np.all(year_ok)),
        floor_clamped_cells=floor_clamped,
        n_floor_bound_years=0
        if floor_bound_years is None
        else int(np.count_nonzero(floor_bound_years)),
    )


# --------------------------------------------------------------------------- #
# the decade reconciliation
# --------------------------------------------------------------------------- #


def reconcile_decade(
    path: np.ndarray,
    factor_names: tuple[str, ...],
    waypoints: DecadeWaypoints,
    config: ReconcileConfig,
) -> tuple[np.ndarray, DecadeReconciliation]:
    """Benchmark one decade's paths to its annual waypoints; re-apply hard floors.

    Only the four waypoint-bearing factors are reconciled (the variant table);
    all other factors pass through untouched. Floors are re-applied to EVERY
    floored factor afterwards (cheap, and a guarantee rather than an assumption
    even though unreconciled bootstrap blocks cannot violate them).
    """
    path = np.asarray(path, dtype=np.float64)
    months = path.shape[0]
    if waypoints.months != months:
        raise JoineryError(f"waypoints cover {waypoints.months} months; path has {months}")
    names = list(factor_names)
    spans = year_spans(months)
    out = path.copy()
    diags: dict[str, FactorReconciliation] = {}

    # -- policy_rate: additive, flow (annual mean) --------------------------- #
    if "policy_rate" in names:
        col = names.index("policy_rate")
        z = path[:, col]
        target = waypoints.policy_pct
        x = denton_additive(
            z,
            [(s, float(t) * (s.stop - s.start), "sum") for s, t in zip(spans, target, strict=True)],
        )
        clamped_mask = x < RATE_FLOOR_PCT
        clamped = int(np.count_nonzero(clamped_mask))
        floor_bound = np.array([bool(clamped_mask[s].any()) for s in spans])
        x = np.maximum(x, RATE_FLOOR_PCT)
        achieved = np.array([float(x[s].mean()) for s in spans])
        out[:, col] = x
        diags["policy_rate"] = _diagnose(
            VARIANT_BY_FACTOR["policy_rate"],
            z,
            x,
            spans,
            target,
            achieved,
            config.tol_policy_pct,
            config.flag_policy_pct,
            floor_clamped=clamped,
            floor_bound_years=floor_bound,
        )

    # -- cpi: proportional via log, stock (year-end level) ------------------- #
    if "cpi" in names:
        col = names.index("cpi")
        z = path[:, col]
        if np.any(z <= 0):
            raise JoineryError("cpi path must be strictly positive to reconcile in log space")
        z_log = np.log(z)
        cum = cum_log_cpi_targets(waypoints)
        target = z_log[0] + cum
        # Month 0 is pinned to the raw level: waypoints constrain INFLATION, not the
        # price level's origin, and year 0's increment is measured from month 0.
        x_log = denton_additive(
            z_log,
            [
                (slice(0, 1), float(z_log[0]), "last"),
                *[(s, float(t), "last") for s, t in zip(spans, target, strict=True)],
            ],
        )
        achieved = np.array([float(x_log[s.stop - 1]) for s in spans])
        out[:, col] = np.exp(x_log)
        diags["cpi"] = _diagnose(
            VARIANT_BY_FACTOR["cpi"],
            z_log,
            x_log,
            spans,
            target,
            achieved,
            config.tol_cpi_log,
            config.flag_cpi_log,
        )

    # -- equity_mkt: additive on monthly log returns, flow (annual drift) ---- #
    if "equity_mkt" in names:
        col = names.index("equity_mkt")
        z = path[:, col]
        if np.any(z <= -1.0):
            raise JoineryError("equity_mkt monthly returns must exceed -100% to take logs")
        z_log = np.log1p(z)
        target = waypoints.equity_log_drift
        x_log = denton_additive(
            z_log, [(s, float(t), "sum") for s, t in zip(spans, target, strict=True)]
        )
        achieved = np.array([float(x_log[s].sum()) for s in spans])
        out[:, col] = np.expm1(x_log)
        diags["equity_mkt"] = _diagnose(
            VARIANT_BY_FACTOR["equity_mkt"],
            z_log,
            x_log,
            spans,
            target,
            achieved,
            config.tol_equity_log,
            config.flag_equity_log,
        )

    # -- ig_spread: additive, stock, band (nearest edge; inside = untouched) -- #
    if "ig_spread" in names:
        col = names.index("ig_spread")
        z = path[:, col]
        yends = np.array([s.stop - 1 for s in spans])
        target = np.clip(z[yends], waypoints.spread_lo_pct, waypoints.spread_hi_pct)
        if np.allclose(target, z[yends]):
            x = z.copy()
            clamped = 0
            floor_bound = np.zeros(len(spans), dtype=bool)
        else:
            x = denton_additive(
                z, [(s, float(t), "last") for s, t in zip(spans, target, strict=True)]
            )
            clamped_mask = x < SPREAD_FLOOR_PCT
            clamped = int(np.count_nonzero(clamped_mask))
            floor_bound = np.array([bool(clamped_mask[s].any()) for s in spans])
            x = np.maximum(x, SPREAD_FLOOR_PCT)
        achieved = x[yends]
        out[:, col] = x
        diags["ig_spread"] = _diagnose(
            VARIANT_BY_FACTOR["ig_spread"],
            z,
            x,
            spans,
            target,
            achieved,
            config.tol_spread_pct,
            config.flag_spread_pct,
            band=(waypoints.spread_lo_pct, waypoints.spread_hi_pct),
            floor_clamped=clamped,
            floor_bound_years=floor_bound,
        )

    # -- hard floors on every floored factor (re-application, not redefinition) #
    for name, floor in (
        *((f, RATE_FLOOR_PCT) for f in RATE_FLOOR_FACTORS),
        *((f, SPREAD_FLOOR_PCT) for f in SPREAD_FLOOR_FACTORS),
    ):
        if name in names and name not in ("policy_rate", "ig_spread"):
            col = names.index(name)
            out[:, col] = np.maximum(out[:, col], floor)

    return out, DecadeReconciliation(factors=diags)
