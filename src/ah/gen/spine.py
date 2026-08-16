"""The spine-conditioned compiler (pilot), Layer S + H + F.

Spec: docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md.
Layer S here; Layers H and F arrive in the same module (Tasks 3-4).

Seed hygiene: three consumers, three disjoint streams per decade/path --
climate (offset 0), regimes (offset 104729), hazard (offset 224737); the
block-draw stream stays PCG64(seed).jumped(p) exactly as StressBootstrap.
An attempt counter, not the accepted-decade index, advances the S streams,
so acceptance filtering never re-uses an attempt's randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ah.core.worldspec import SpinePremise
from ah.data.derive import REGIME_LABELS
from ah.gen.climate.simulate import (
    ClimateArtifact,
    policy_anchor,
    simulate_decades,
)
from ah.gen.regimes.semimarkov import RegimesArtifact, simulate_regimes

SEED_STRIDE = 7919
LAYER_OFFSETS = {"climate": 0, "regimes": 104729, "hazard": 224737}
CONTRACTION_CODES = frozenset({REGIME_LABELS.index("REC"), REGIME_LABELS.index("CRI")})
BACKDROP_MARGIN_PP = 0.5
ARRIVAL_LATE_SLACK_MONTHS = 6
SLOW_RECOVERY_MIN_MONTHS = 24
MAX_ATTEMPTS_PER_DECADE = 200


class SpineRefusal(RuntimeError):
    """A premise the pinned posterior would not realize at the attempt budget."""


@dataclass(frozen=True)
class SpinePaths:
    states: np.ndarray  # (n, months, 5) STATE_NAMES order
    labels: np.ndarray  # (n, months) int codes into REGIME_LABELS
    cycle: np.ndarray  # (n, months)
    policy: np.ndarray  # (n, months) Taylor anchor, noise-free
    mu_pi: np.ndarray  # (n,) each decade's own posterior-draw mu_pi
    attempts: int
    seed: int


def _reject_reason(
    premise: SpinePremise, states: np.ndarray, labels: np.ndarray, mu_pi: float
) -> str | None:
    """None if the decade realizes the premise, else the failed clause's name."""
    arrive = 3 * premise.arrives_quarter
    pi_pre = float(states[:arrive, 0].mean())  # pi_star is STATE_NAMES[0]
    if premise.backdrop == "inflation_above_trend":
        if not pi_pre > mu_pi + BACKDROP_MARGIN_PP:
            return "backdrop:inflation_above_trend"
    else:
        if pi_pre > mu_pi + BACKDROP_MARGIN_PP:
            return "backdrop:benign"
    in_c = np.isin(labels, list(CONTRACTION_CODES))
    starts = np.flatnonzero(in_c & ~np.roll(in_c, 1))
    if in_c[0]:
        starts = np.unique(np.concatenate([[0], starts]))
    lo, hi = arrive - 3, arrive + ARRIVAL_LATE_SLACK_MONTHS
    if not ((starts >= lo) & (starts <= hi)).any():
        return "arrival"
    months_c = int(in_c.sum())
    if premise.recovery == "slow" and months_c < SLOW_RECOVERY_MIN_MONTHS:
        return "recovery:slow"
    if premise.recovery == "normal" and months_c >= SLOW_RECOVERY_MIN_MONTHS:
        return "recovery:normal"
    return None


def sample_spine(
    climate: ClimateArtifact,
    regimes_artifact: RegimesArtifact,
    premise: SpinePremise,
    *,
    n_decades: int,
    seed: int,
    months: int = 120,
    max_attempts_per_decade: int = MAX_ATTEMPTS_PER_DECADE,
) -> SpinePaths:
    """Premise-accepted spines, one-pass L2 on one-pass L1, then the two-pass
    L1 re-run under the regime cycle (the joinery/assemble composition)."""
    if n_decades < 1:
        raise ValueError("n_decades must be >= 1")
    budget = max_attempts_per_decade * n_decades
    kept_s: list[np.ndarray] = []
    kept_l: list[np.ndarray] = []
    kept_c: list[np.ndarray] = []
    kept_p: list[np.ndarray] = []
    kept_mu: list[float] = []
    tally: dict[str, int] = {}
    attempt = 0
    while len(kept_s) < n_decades and attempt < budget:
        l1_seed = seed + LAYER_OFFSETS["climate"] + SEED_STRIDE * attempt
        l2_seed = seed + LAYER_OFFSETS["regimes"] + SEED_STRIDE * attempt
        sim1 = simulate_decades(climate, 1, seed=l1_seed, months=months)
        reg = simulate_regimes(regimes_artifact, sim1.states, seed=l2_seed)
        # two-pass: same seed -> same theta/s0/innovations; only the credit
        # norm's cycle forcing changes (assemble.py's documented pattern).
        sim2 = simulate_decades(climate, 1, seed=l1_seed, months=months, cycle=reg.cycle)
        pol = policy_anchor(sim2, cycle=reg.cycle)
        mu_pi = float(sim2.params["mu_pi"][0])
        reason = _reject_reason(premise, sim2.states[0], reg.labels[0], mu_pi)
        attempt += 1
        if reason is None:
            kept_s.append(sim2.states[0])
            kept_l.append(reg.labels[0])
            kept_c.append(reg.cycle[0])
            kept_p.append(pol[0])
            kept_mu.append(mu_pi)
        else:
            tally[reason] = tally.get(reason, 0) + 1
    if len(kept_s) < n_decades:
        raise SpineRefusal(
            f"premise unfillable at budget {budget}: accepted {len(kept_s)}/{n_decades}; "
            f"rejections {dict(sorted(tally.items()))}"
        )
    return SpinePaths(
        states=np.stack(kept_s),
        labels=np.stack(kept_l),
        cycle=np.stack(kept_c),
        policy=np.stack(kept_p),
        mu_pi=np.asarray(kept_mu, dtype=np.float64),
        attempts=attempt,
        seed=int(seed),
    )


MIN_CELL_MONTHS = 24

#: R3: the investment clock. Index = (expanding << 1) | hot.
QUADRANTS = ("recession", "stagflation", "recovery", "expansion")
#: recovery -> expansion -> stagflation -> recession -> recovery
CLOCKWISE = frozenset({(2, 3), (3, 1), (1, 0), (0, 2)})


def panel_yoy(source) -> np.ndarray:
    """Trailing CPI YoY per panel row, %; NaN where the 12-month lookback is
    unavailable. The panel's cpi factor is a LEVEL (the 2026-08-15 finding):
    YoY is only computed against the row 12 places earlier IN THE PANEL, which
    is contiguous by construction within the panel's own ordering."""
    ci = list(source.factor_names).index("cpi")
    level = np.asarray(source.values)[:, ci].astype(np.float64)
    out = np.full(source.n_rows, np.nan)
    out[12:] = (level[12:] / level[:-12] - 1.0) * 100.0
    return out


def panel_quadrant(source, yoy: np.ndarray, era_threshold_pp: float) -> np.ndarray:
    """Quadrant per panel row; -1 where yoy is NaN. Panel-space proxies (spec
    3.3 disclosure): expanding = the row's regime label outside {REC, CRI};
    hot = trailing YoY above the era threshold. CRI rows keep their quadrant --
    crisis is the overlay, not a quadrant (R3)."""
    contracting = np.isin(np.asarray(source.labels), ["REC", "CRI"])
    cells = np.full(source.n_rows, -1, dtype=np.int8)
    ok = ~np.isnan(yoy)
    hot = (yoy > era_threshold_pp).astype(np.int8)
    expanding = (~contracting).astype(np.int8)
    cells[ok] = (expanding[ok] << 1) | hot[ok]
    return cells


def spine_quadrant(states_m: np.ndarray, label_m: int, *, mu_pi: float) -> int:
    """Spine-space quadrant for one month. states_m is one row in STATE_NAMES
    order; expanding = the six-label engine's month is outside REC/CRI."""
    hot = int(states_m[0] - mu_pi > BACKDROP_MARGIN_PP)
    expanding = int(int(label_m) not in CONTRACTION_CODES)
    return (expanding << 1) | hot


@dataclass(frozen=True)
class HazardTable:
    rates: np.ndarray  # (4,) monthly correction-onset probability per quadrant
    era_threshold_pp: float
    cell_months: np.ndarray  # (4,) panel months per quadrant
    fallback_rate: float


def fit_hazard(source) -> HazardTable:
    """P(a crisis BEGINS next month | this month's quadrant) -- the discrete hazard
    rate per panel quadrant (spec 3.2, R3). Over one categorical covariate the
    saturated fit IS the frequency table -- portfolio outcomes never enter (rule 1).
    Starved quadrants (< MIN_CELL_MONTHS) take the marginal onset rate.

    Conditioning is on the month BEFORE the onset (the onset month itself is labelled
    CRI and always classifies as contracting; conditioning on it would silence expanding
    quadrants structurally). AMENDED 2026-08-15 during Task 3: the original formula
    conditioned on the onset month's own quadrant."""
    yoy = panel_yoy(source)
    era_thr = float(np.nanmedian(yoy) + BACKDROP_MARGIN_PP)
    cells = panel_quadrant(source, yoy, era_thr)
    labels = np.asarray(source.labels)
    is_cri = labels == "CRI"
    # At-risk months: valid quadrant, not already in a crisis
    at_risk = (cells >= 0) & ~is_cri
    at_risk[-1] = False  # a month already inside a crisis cannot 'onset'; the last month has no t+1
    # Events credited to the month BEFORE the onset
    event = np.zeros(source.n_rows, dtype=bool)
    event[:-1] = is_cri[1:] & ~is_cri[:-1]
    fallback = float(event[at_risk].sum() / max(int(at_risk.sum()), 1))
    rates = np.full(4, fallback)
    months = np.zeros(4, dtype=np.int64)
    for c in range(4):
        mask = at_risk & (cells == c)
        months[c] = int(mask.sum())
        if months[c] >= MIN_CELL_MONTHS:
            rates[c] = float(event[mask].sum() / months[c])
    return HazardTable(
        rates=rates, era_threshold_pp=era_thr, cell_months=months, fallback_rate=fallback
    )
