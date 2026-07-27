"""WP2.7 support — the conditioning-support monitor (STEP2 §WP2.7, new in v1.1).

Conditional generators fail QUIETLY off-support, so the conditioning interface is
instrumented, not trusted: for every assembled decade this module measures how
far its block-conditioning vectors sit from the train+validation conditioning
distribution, and logs a per-decade **extrapolation share** into the ensemble
metadata.

The reference distribution
--------------------------
Historical analogues of c_b are built from the bootstrap source's own panel (read
through the sanctioned ``DataAccess.train_val`` surface when the source was
built) plus the L1 posterior-MEAN smoothed states at the matching dates: for
every historical block start (stride 3, starting at month 12 so a full trailing
year exists), the 12 CONTINUOUS c_b components — s_t snapshot (5), h_t trailing
summary (3), realized Δw increments (4). The one-hot regime part is excluded
(it would make the covariance singular); the regime dimension is monitored by a
separate frequency check.

The distances
-------------
Mahalanobis distance to the historical mean/covariance (ridge-regularized by
1e-9·tr(Σ)/12 for numerical rank safety). The **stated extrapolation quantile is
p99**: the threshold is the 99th percentile of the HISTORICAL blocks' own
self-distances, so a decade whose blocks are exchangeable with history shows an
extrapolation share near 0.01 by construction. A decade is flagged off-support
when more than :data:`OFF_SUPPORT_FLAG_SHARE` (25%) of its blocks sit beyond
that threshold — 25x the nominal rate, chosen so the flag marks structural
extrapolation rather than sampling noise.

The regime-frequency check reports the total-variation distance between the
decade's regime mix and the historical label frequencies; STAG's thinness (9
historical spells; zero months on the 1990-2020 draw span) surfaces here as a
large TV distance for STAG-leaning decades rather than being papered over.

The plan says the diagnostic is "surfaced as a battery report line". The sealed
``ah.eval.battery`` is untouchable and carries no ensemble-conditioning line, so
the diagnostic lands in ``EnsembleMeta.conditioning`` and the assembly report;
the presentation gap is recorded (progress.md) as a WP2.11 item, not a code
change here.

Deterministic: no RNG anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ah.gen.bootstrap import BootstrapSource
from ah.gen.climate.simulate import ClimateArtifact
from ah.gen.joinery.bridge import BLOCK_MONTHS, BLOCK_STRIDE, BlockConditioning
from ah.gen.joinery.waypoints import JoineryError, _column  # shared factor lookup
from ah.gen.regimes.semimarkov import N_REGIMES, REGIME_LABELS

__all__ = [
    "EXTRAPOLATION_QUANTILE",
    "OFF_SUPPORT_FLAG_SHARE",
    "SupportReference",
    "build_support_reference",
    "decade_support",
    "historical_conditioning",
    "mahalanobis",
]

#: The stated distance quantile defining "beyond historical support" (p99 of the
#: historical blocks' own self-distances).
EXTRAPOLATION_QUANTILE = 0.99

#: A decade is flagged off-support when its extrapolation share exceeds this —
#: 25x the nominal 1% rate an on-support decade shows by construction.
OFF_SUPPORT_FLAG_SHARE = 0.25

_LABEL_INDEX = {label: i for i, label in enumerate(REGIME_LABELS)}


def historical_conditioning(
    source: BootstrapSource,
    climate: ClimateArtifact,
    *,
    block_months: int = BLOCK_MONTHS,
    stride: int = BLOCK_STRIDE,
) -> tuple[np.ndarray, np.ndarray]:
    """Historical c_b analogues: ``(n_blocks, 12)`` continuous components + labels.

    Block starts run from month 12 (first month with a full trailing year)
    through the last start whose block fits inside the span. Δw components are
    the REALIZED increments over the block window — history's blocks were, by
    definition, consistent with history's waypoints.
    """
    policy = _column(source, "policy_rate")
    cpi = _column(source, "cpi")
    equity = _column(source, "equity_mkt")
    spread = _column(source, "ig_spread")
    eq_log = np.log1p(equity)
    if np.any(cpi <= 0):
        raise JoineryError("cpi levels must be positive to build conditioning increments")
    log_cpi = np.log(cpi)
    cum_eq = np.concatenate(([0.0], np.cumsum(eq_log)))  # cum_eq[t] = sum of first t

    idx = climate.dates.get_indexer(source.dates)
    if np.any(idx < 0):
        first = source.dates[int(np.flatnonzero(idx < 0)[0])]
        raise JoineryError(
            f"climate artifact grid ({climate.dates[0].date()}..{climate.dates[-1].date()}) "
            f"does not cover source month {first.date()}"
        )
    states = climate.states.mean(axis=0)[idx, :]  # (T, 5) posterior-mean path
    codes = np.array([_LABEL_INDEX[label] for label in source.labels], dtype=np.int64)

    rows: list[np.ndarray] = []
    labels: list[int] = []
    t_len = source.n_rows
    for start in range(12, t_len - block_months + 1, stride):
        hi = start + block_months - 1
        lo = start - 1
        window = eq_log[start - 12 : start]
        row = np.concatenate(
            [
                states[start],
                [float(window.sum()), float(np.std(window, ddof=1)), float(spread[start - 1])],
                [
                    float(policy[hi] - policy[lo]),
                    float(log_cpi[hi] - log_cpi[lo]),
                    float(cum_eq[hi + 1] - cum_eq[lo + 1]),
                    float(spread[hi] - spread[lo]),
                ],
            ]
        )
        rows.append(row)
        labels.append(int(codes[start]))
    if not rows:
        raise JoineryError("draw span too short to build any historical conditioning block")
    return np.vstack(rows), np.array(labels, dtype=np.int64)


@dataclass(frozen=True)
class SupportReference:
    """The train+validation conditioning distribution, frozen for a campaign."""

    mean: np.ndarray  # (12,)
    cov: np.ndarray  # (12, 12), ridge-regularized
    cov_inv: np.ndarray  # (12, 12)
    threshold: float  # the p-`quantile` historical self-distance
    quantile: float
    label_frequencies: np.ndarray  # (6,) historical label frequency at block starts


def build_support_reference(
    source: BootstrapSource,
    climate: ClimateArtifact,
    *,
    quantile: float = EXTRAPOLATION_QUANTILE,
) -> SupportReference:
    """Mean/cov of the historical conditioning vectors + the self-distance threshold."""
    x, labels = historical_conditioning(source, climate)
    mean = x.mean(axis=0)
    cov = np.cov(x, rowvar=False)
    ridge = 1e-9 * float(np.trace(cov)) / cov.shape[0]
    cov = cov + ridge * np.eye(cov.shape[0])
    cov_inv = np.linalg.inv(cov)
    centered = x - mean
    d = np.sqrt(np.einsum("ij,jk,ik->i", centered, cov_inv, centered))
    freqs = np.bincount(labels, minlength=N_REGIMES).astype(np.float64)
    freqs /= freqs.sum()
    return SupportReference(
        mean=mean,
        cov=cov,
        cov_inv=cov_inv,
        threshold=float(np.quantile(d, quantile)),
        quantile=float(quantile),
        label_frequencies=freqs,
    )


def mahalanobis(x: np.ndarray, ref: SupportReference) -> np.ndarray:
    """Mahalanobis distances of rows of ``x`` (n, 12) to the reference distribution."""
    centered = np.atleast_2d(np.asarray(x, dtype=np.float64)) - ref.mean
    return np.sqrt(np.einsum("ij,jk,ik->i", centered, ref.cov_inv, centered))


def decade_support(
    conds: list[BlockConditioning],
    month_labels: np.ndarray,
    ref: SupportReference,
) -> dict[str, Any]:
    """One decade's support diagnostic (JSON-safe; logged into EnsembleMeta).

    ``conds`` are the decade's block conditioning vectors (bridge order);
    ``month_labels`` the decade's monthly regime codes (the waypoint labels, so
    crisis-window overlays are counted).
    """
    if not conds:
        raise JoineryError("decade_support needs at least one conditioning vector")
    x = np.vstack([cond.continuous_vector() for cond in conds])
    d = mahalanobis(x, ref)
    share = float(np.mean(d > ref.threshold))

    codes = np.asarray(month_labels, dtype=np.int64)
    freqs = np.bincount(codes, minlength=N_REGIMES).astype(np.float64)
    freqs /= freqs.sum()
    tv = 0.5 * float(np.abs(freqs - ref.label_frequencies).sum())

    return {
        "n_blocks": len(conds),
        "mahalanobis_mean": float(d.mean()),
        "mahalanobis_p95": float(np.quantile(d, 0.95)),
        "mahalanobis_max": float(d.max()),
        "extrapolation_share": share,
        "extrapolation_quantile": float(ref.quantile),
        "flag_off_support": bool(share > OFF_SUPPORT_FLAG_SHARE),
        "regime_freq_tv": tv,
        "regime_frequencies": {REGIME_LABELS[i]: float(freqs[i]) for i in range(N_REGIMES)},
    }
