"""The policy anchor, decomposed — DN-1 II.2 through DN-9 §C.5/§C.6.

``i_t = r*_t + pi*_t + phi_pi*(pi_t - pi*_t) + phi_c*c_t + eps_t``

The realised policy rate is already in the path; this module reconstructs what
the *rule* implied, so the residual can be named as the surprise. Three things
about that reconstruction are worth stating because they are easy to lose:

* **The generator does not emit ``phi_pi``, ``phi_c`` or ``c_t``.** The anchor is
  narration's own reconstruction of a reaction function, and every coefficient
  in it is an open parameter (``voices.fomc.anchor.*``). A wrong coefficient does
  not produce an error — it produces strain, which is the point of §D.6.
* **The narration anchor is smoothed** (``i~_t = rho*i_{t-1} + (1-rho)*anchor_t``)
  because §C.6 measured the raw residual reaching +1.47 on a cut, which is
  unusable as a surprise measure. ``rho`` is unratified.
* **Quantisation is a display transform** under §3.4 — deterministic, registered.
  It is *not* a fix for an un-inertial generated path; that is referral N-q, and
  the diagnostics report reversal frequency precisely so it stays visible.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ah.narration.constants import BPS_PER_PP, RECORD_PRECISION
from ah.narration.errors import NarrationError

__all__ = ["AnchorParams", "AnchorTerms", "decompose"]


@dataclass(frozen=True)
class AnchorParams:
    """Resolved anchor parameters. Every field is an open decision upstream."""

    rho: float
    quantise_bp: float
    phi_pi: float
    phi_c: float
    cycle_source: str


@dataclass(frozen=True)
class AnchorTerms:
    """One month's decomposition, in percentage points."""

    month: int
    neutral: float
    gap_term: float
    cycle_term: float
    anchor: float
    smoothed: float
    realised: float
    epsilon: float
    cycle_value: float
    pi: float
    pi_star: float
    r_star: float

    def as_record(self) -> dict[str, float]:
        return {
            "r_star": round(self.r_star, RECORD_PRECISION),
            "pi_star": round(self.pi_star, RECORD_PRECISION),
            "pi": round(self.pi, RECORD_PRECISION),
            "neutral": round(self.neutral, RECORD_PRECISION),
            "gap_term": round(self.gap_term, RECORD_PRECISION),
            "cycle_term": round(self.cycle_term, RECORD_PRECISION),
            "cycle_value": round(self.cycle_value, RECORD_PRECISION),
            "anchor": round(self.anchor, RECORD_PRECISION),
            "smoothed_anchor": round(self.smoothed, RECORD_PRECISION),
            "realised": round(self.realised, RECORD_PRECISION),
            "epsilon": round(self.epsilon, RECORD_PRECISION),
        }


def _quantise(values: np.ndarray, step_bp: float) -> np.ndarray:
    """Round to the nearest ``step_bp`` basis points. ``0`` means no quantisation."""
    if step_bp <= 0.0:
        return values
    step = step_bp / BPS_PER_PP
    return np.round(values / step) * step


def _cycle(l1_state: dict[str, np.ndarray], source: str, window: int) -> np.ndarray:
    if source == "credit_gap":
        return l1_state["credit_gap"]
    if source == "v":
        return l1_state["v"]
    if source == "g_minus_trailing_mean":
        growth = l1_state["g"]
        out = np.zeros_like(growth)
        for month in range(len(growth)):
            lo = max(0, month - window)
            past = growth[lo:month]
            out[month] = growth[month] - (float(np.mean(past)) if len(past) else growth[month])
        return out
    raise NarrationError(
        f"voices.fomc.anchor.cycle_source: unknown source '{source}'. The cycle term is not "
        "defaulted — DN-1 II.2 says c_t is inherited from L2, and this world's L2 layer is a "
        "label sequence with no scalar in it, so the substitute must be chosen and stated."
    )


def decompose(
    *,
    policy_rate: np.ndarray,
    cpi_yoy: np.ndarray,
    l1_state: dict[str, np.ndarray],
    params: AnchorParams,
    z_window_months: int,
) -> list[AnchorTerms | None]:
    """The decomposition for every month; ``None`` where the inflation gap has no value.

    A month without a year-on-year inflation figure (the adapter's warmup) has no
    inflation gap, so it has no anchor and no policy surprise — a consequence of
    ``adapter.cpi_yoy_warmup``, not a silent gap.
    """
    cycle = _cycle(l1_state, params.cycle_source, z_window_months)
    r_star = l1_state["r_star"]
    pi_star = l1_state["pi_star"]

    neutral = r_star + pi_star
    gap_term = params.phi_pi * (cpi_yoy - pi_star)
    cycle_term = params.phi_c * cycle
    anchor = neutral + gap_term + cycle_term

    smoothed = np.full_like(anchor, np.nan)
    for month in range(len(anchor)):
        previous = policy_rate[month - 1] if month else policy_rate[month]
        smoothed[month] = params.rho * previous + (1.0 - params.rho) * anchor[month]

    smoothed_q = _quantise(smoothed, params.quantise_bp)
    realised_q = _quantise(policy_rate, params.quantise_bp)

    out: list[AnchorTerms | None] = []
    for month in range(len(anchor)):
        if not np.isfinite(anchor[month]):
            out.append(None)
            continue
        out.append(
            AnchorTerms(
                month=month + 1,
                neutral=float(neutral[month]),
                gap_term=float(gap_term[month]),
                cycle_term=float(cycle_term[month]),
                anchor=float(anchor[month]),
                smoothed=float(smoothed_q[month]),
                realised=float(realised_q[month]),
                epsilon=float(realised_q[month] - smoothed_q[month]),
                cycle_value=float(cycle[month]),
                pi=float(cpi_yoy[month]),
                pi_star=float(pi_star[month]),
                r_star=float(r_star[month]),
            )
        )
    return out
