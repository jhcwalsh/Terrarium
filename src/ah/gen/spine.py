"""The spine-conditioned compiler (pilot), Layer S + H + F.

Spec: docs/superpowers/specs/2026-08-15-spine-conditioned-compiler-design.md.
Layers S, H and F all live in this module.

Seed hygiene: four consumers, four disjoint streams per decade/path --
climate (offset 0), regimes (offset 104729), hazard (offset 224737), blocks
(offset 350377). The block stream is NOT the bare seed StressBootstrap uses:
climate sits at offset 0, so a bare-seed block stream would be bit-identical
to spine attempt 0's climate stream (AMENDED after the Task-4 review, F3).
An attempt counter, not the accepted-decade index, advances the S streams,
so acceptance filtering never re-uses an attempt's randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ah.core.numericworld import NumericWorld
from ah.core.worldspec import SpinePremise, SpineSpec, StressSpec
from ah.data.derive import REGIME_LABELS
from ah.gen.base import Ensemble, EnsembleMeta, RegimeRecord, SlowStateRecord
from ah.gen.bootstrap import BootstrapSource
from ah.gen.climate.model import STATE_NAMES
from ah.gen.climate.simulate import (
    ClimateArtifact,
    policy_anchor,
    simulate_decades,
)
from ah.gen.regimes.semimarkov import RegimesArtifact, simulate_regimes
from ah.gen.stress import (
    StressError,
    _segment_for,
    eligible_rows,
    join_candidates,
    severity_score,
)
from ah.gen.systems import _pinned_layers

SEED_STRIDE = 7919
LAYER_OFFSETS = {"climate": 0, "regimes": 104729, "hazard": 224737, "blocks": 350377}
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


# --------------------------------------------------------------------------- #
# Layer F -- SpineBootstrap: quadrant-conditioned pools, hazard corrections,
# era-safe joins. PATTERN copied from StressBootstrap._draw (ah/gen/stress.py),
# not subclassed: the two samplers stay independently readable.
# --------------------------------------------------------------------------- #

BASE_DWELL_QUARTERS = 2
STRATUM_FLOOR_PCT = 5.0


def percentile_for(base: float, shift: int) -> float:
    """The stratified entry percentile ``shift`` strata deeper than ``base``.

    Halves per stratum, floored at ``STRATUM_FLOOR_PCT`` so a correction can
    never demand an empty pool purely from repeated halving.
    """
    return max(STRATUM_FLOOR_PCT, base * 0.5**shift)


def _severity_row_for(spine: SpineSpec, infl: bool, credit: bool):
    """The state-severity row for the firing month's conditions (spec 3.4):
    both flags -> "both", exactly one -> "either", neither -> "baseline"."""
    condition = "both" if infl and credit else "either" if infl or credit else "baseline"
    for row in spine.severity_table:
        if row.condition == condition:
            return row
    raise StressError(
        f"severity_table has no row for condition '{condition}'"
    )  # unreachable: SpineSpec validates coverage


def _build_pools(
    pools: dict[tuple[int, int, float], np.ndarray],
    scores: np.ndarray,
    cells: np.ndarray,
    from_quarter: int,
    quadrant: int,
    pct: float,
) -> np.ndarray:
    """The pool for (segment, quadrant, percentile), built on first demand and
    cached. Membership = eligible_rows(scores, pct) INTERSECT the panel rows
    whose own quadrant matches (NaN-yoy rows are never cell members -- see
    panel_quadrant). An empty pool is refusal, never substitution."""
    key = (int(from_quarter), int(quadrant), round(float(pct), 6))
    pool = pools.get(key)
    if pool is not None:
        return pool
    elig = eligible_rows(scores, pct)
    pool = elig[cells[elig] == quadrant]
    if pool.size == 0:
        raise SpineRefusal(
            f"empty pool at segment {from_quarter}, quadrant {QUADRANTS[quadrant]}, percentile {pct}"
        )
    pools[key] = pool
    return pool


def _pool_occupancy_stamp(pools: dict[tuple[int, int, float], np.ndarray]) -> dict[str, int]:
    """``{"<from_quarter>/<quadrant>@<pct>": size}`` for every pool actually
    built. The percentile is part of the key (g-style, e.g. ``35`` or
    ``17.5``) so a segment/quadrant pair opened at more than one percentile
    by a firing correction is unambiguous -- never disambiguated by an
    incidental build-order suffix (AMENDED after the Task-4 review, F4a)."""
    stamp: dict[str, int] = {}
    for from_quarter, quadrant, pct in sorted(pools):
        label = f"{from_quarter}/{QUADRANTS[quadrant]}@{pct:g}"
        stamp[label] = int(pools[(from_quarter, quadrant, pct)].size)
    return stamp


def _correction_onset(
    spine: SpineSpec,
    in_correction: bool,
    dwell_left: int,
    shift: int,
    *,
    fires: bool,
    infl: bool,
    credit: bool,
) -> tuple[bool, int, int]:
    """One correction's START (spec 3.4): if not already in a correction and
    the hazard fired this month, the dwell (including the firing month) and
    stratum shift come from the firing month's severity row; otherwise the
    state is unchanged. Pure and RNG-free -- ``fires``/``infl``/``credit`` are
    already-decided outcomes, so this is drivable directly by
    ``test_correction_dwell_and_refire`` without touching any RNG stream."""
    if not in_correction and fires:
        row = _severity_row_for(spine, infl, credit)
        return True, (BASE_DWELL_QUARTERS + row.dwell_shift_quarters) * 3, row.stratum_shift
    return in_correction, dwell_left, shift


def _correction_expire(in_correction: bool, dwell_left: int, shift: int) -> tuple[bool, int, int]:
    """One correction's EXPIRY: consume a dwell month, clearing the
    correction (and its shift) once the dwell reaches zero. Called AFTER the
    month's pool has been built, so the firing month and every dwell month up
    to and including expiry still see the shifted pool -- only the month
    AFTER expiry sees the baseline pool again."""
    if not in_correction:
        return in_correction, dwell_left, shift
    dwell_left -= 1
    if dwell_left <= 0:
        return False, dwell_left, 0
    return True, dwell_left, shift


@dataclass(frozen=True)
class _DrawInputs:
    """Bundles ``SpineBootstrap._draw``'s per-sample inputs (FIX7, Task-4
    review: 13 bare positional parameters were error-prone to call and to
    test directly)."""

    source: BootstrapSource
    sp: SpinePaths
    hazard: HazardTable
    scores: np.ndarray
    cells: np.ndarray
    yoy: np.ndarray
    era_bucket: np.ndarray
    months: int
    n_paths: int
    seed: int
    stress: StressSpec
    spine: SpineSpec
    pools: dict[tuple[int, int, float], np.ndarray]


class SpineBootstrap:
    """The spine-conditioned compiler. Implements ah.gen.base.Generator."""

    generator_id = "bootstrap-stratified"

    def __init__(self, source: BootstrapSource | None = None) -> None:
        self._source = source
        self._climate, self._regimes = _pinned_layers()

    @property
    def source(self) -> BootstrapSource:
        if self._source is None:
            raise StressError(
                "bootstrap-stratified (spine) is not fitted; call fit(campaign_source())"
            )
        return self._source

    def fit(self, data: Any) -> None:
        if not isinstance(data, BootstrapSource):
            raise StressError(
                f"fit expects a BootstrapSource (see ah.gen.bootstrap.campaign_source); "
                f"got {type(data).__name__}"
            )
        self._source = data

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        if world.stress is None:
            raise StressError(
                f"world '{world.world_id}' selects bootstrap-stratified but declares no "
                "extensions.x_stress; a spine-conditioned world must declare both x_stress and x_spine"
            )
        if world.spine is None:
            raise StressError(
                f"world '{world.world_id}' declares extensions.x_stress but no extensions.x_spine; "
                "a spine-conditioned world must declare both"
            )
        months = int(world.horizon.quarters) * 3
        return self.sample_months(
            months, n_paths, seed, world=world, stress=world.stress, spine=world.spine
        )

    def sample_months(
        self,
        months: int,
        n_paths: int,
        seed: int,
        *,
        world: NumericWorld | None = None,
        stress: StressSpec | None = None,
        spine: SpineSpec | None = None,
    ) -> Ensemble:
        source = self.source
        if stress is None or spine is None:
            raise StressError(
                "spine-conditioned sampling requires both a StressSpec and a SpineSpec"
            )
        months, n_paths = int(months), int(n_paths)
        if months < 1 or n_paths < 1:
            raise StressError(f"months and n_paths must be >= 1; got {months}, {n_paths}")

        sp = sample_spine(
            self._climate, self._regimes, spine.premise, n_decades=n_paths, seed=seed, months=months
        )
        hazard = fit_hazard(source)
        scores = severity_score(source.values, source.factor_names, stress.functional)
        yoy = panel_yoy(source)
        cells = panel_quadrant(source, yoy, hazard.era_threshold_pp)
        # -1 where yoy is NaN: a previous row with an undefined era bucket can
        # never era-match a join candidate, so a join can never land on (or
        # leave from) a row the panel cannot date an inflation era for.
        era_bucket = np.where(np.isnan(yoy), -1, (yoy > hazard.era_threshold_pp).astype(np.int64))

        pools: dict[tuple[int, int, float], np.ndarray] = {}
        index, corrections = self._draw(
            _DrawInputs(
                source=source,
                sp=sp,
                hazard=hazard,
                scores=scores,
                cells=cells,
                yoy=yoy,
                era_bucket=era_bucket,
                months=months,
                n_paths=n_paths,
                seed=seed,
                stress=stress,
                spine=spine,
                pools=pools,
            )
        )
        paths = source.values[index]

        label_codes = {label: i for i, label in enumerate(REGIME_LABELS)}
        source_codes = np.array([label_codes[label] for label in source.labels], dtype=np.int64)

        conditioning: dict[str, Any] = {
            "mode": "spine-conditioned-stress",
            "functional": stress.functional,
            "premise": spine.premise.model_dump(),
            "severity_table": [row.model_dump() for row in spine.severity_table],
            "spine_precedent": list(spine.precedent),
            "quadrant_legend": list(QUADRANTS),
            "hazard": {
                "rates": [float(x) for x in hazard.rates],
                "cell_months": [int(x) for x in hazard.cell_months],
                "era_threshold_pp": float(hazard.era_threshold_pp),
                "fallback_rate": float(hazard.fallback_rate),
            },
            "corrections": {
                "per_path_onsets": corrections["per_path_onsets"],
                "per_quadrant_onsets": corrections["per_quadrant_onsets"],
                "per_quadrant_months": corrections["per_quadrant_months"],
            },
            "forced_reentries": int(corrections["forced_reentries"]),
            "unfiltered_reentries": int(corrections["unfiltered_reentries"]),
            "spine_attempts": int(sp.attempts),
            "pool_occupancy": _pool_occupancy_stamp(pools),
            "segments": [
                {
                    "from_quarter": s.from_quarter,
                    "to_quarter": s.to_quarter,
                    "entry_percentile": s.entry_percentile,
                    "mean_block_months": s.mean_block_months,
                }
                for s in stress.segments
            ],
            "join_tolerance": dict(stress.join_tolerance),
            "join_yoy_max_pp": float(spine.join_yoy_max_pp),
            "precedent": list(stress.precedent),
            "ruleset_version": source.ruleset_version,
            "block_draw_span": {
                "start": str(source.dates[0].date()),
                "end": str(source.dates[-1].date()),
                "months": source.n_rows,
            },
            # This generator honours no factor_conditions either: severity is
            # declared through x_stress/x_spine, not through an inflation
            # average (mirrors the stress stamp's own field, FIX4b).
            "factor_conditions_honoured": False,
            "provenance": "declared",
        }
        if world is not None:
            conditioning["world_id"] = world.world_id

        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id=source.vintage_id,
            seed=int(seed),
            n_paths=n_paths,
            months=months,
            conditioning=conditioning,
            active_blocks=tuple(source.active_blocks),
        )
        return Ensemble(
            paths=paths,
            factor_names=list(source.factor_names),
            meta=meta,
            row_indices=index,
            regimes=RegimeRecord(
                labels=source_codes[index],
                legend=tuple(REGIME_LABELS),
                mode="realized-spine-conditioned",
                ruleset_version=source.ruleset_version,
            ),
            slow_states=SlowStateRecord(states=sp.states, names=STATE_NAMES, layer="simulated"),
        )

    def _draw(self, args: _DrawInputs) -> tuple[np.ndarray, dict[str, Any]]:
        source, sp, hazard = args.source, args.sp, args.hazard
        scores, cells, yoy, era_bucket = args.scores, args.cells, args.yoy, args.era_bucket
        months, n_paths, seed = args.months, args.n_paths, args.seed
        stress, spine, pools = args.stress, args.spine, args.pools
        n = source.n_rows
        index = np.empty((n_paths, months), dtype=np.int64)
        per_path_onsets = [0] * n_paths
        per_quadrant_onsets = [0, 0, 0, 0]
        per_quadrant_months = [0, 0, 0, 0]
        forced_reentries = 0
        unfiltered_reentries = 0

        for p in range(n_paths):
            # Two DIFFERENT generators: the hazard stream and the block stream
            # must never share state, so a premise's firing pattern (which
            # consumes rng_h at a variable rate -- skipped entirely while
            # already inside a correction) cannot perturb the block tape. The
            # block stream is offset (FIX3): the bare seed would be
            # bit-identical to spine attempt 0's climate stream (offset 0).
            rng = np.random.Generator(
                np.random.PCG64(int(seed) + LAYER_OFFSETS["blocks"]).jumped(p)
            )
            rng_h = np.random.Generator(
                np.random.PCG64(int(seed) + LAYER_OFFSETS["hazard"]).jumped(p)
            )
            in_correction = False
            dwell_left = 0
            shift = 0

            for m in range(months):
                seg = _segment_for(stress, m // 3)
                q = spine_quadrant(sp.states[p, m], int(sp.labels[p, m]), mu_pi=float(sp.mu_pi[p]))

                # The hazard is checked ONLY when not already in a correction --
                # and B5's realized rate is onsets/AT-RISK months (mirroring
                # fit_hazard's own denominator), so every such check counts,
                # regardless of whether it goes on to fire (FIX1).
                if not in_correction:
                    per_quadrant_months[q] += 1
                    fires = rng_h.random() < float(hazard.rates[q])
                else:
                    fires = False

                infl = credit = False
                if fires:
                    infl = float(sp.states[p, m, 0]) - float(sp.mu_pi[p]) > BACKDROP_MARGIN_PP
                    credit = float(sp.states[p, m, 4]) > 0.0
                    per_path_onsets[p] += 1
                    per_quadrant_onsets[q] += 1

                in_correction, dwell_left, shift = _correction_onset(
                    spine, in_correction, dwell_left, shift, fires=fires, infl=infl, credit=credit
                )

                pct = (
                    percentile_for(seg.entry_percentile, shift)
                    if in_correction
                    else seg.entry_percentile
                )
                pool = _build_pools(pools, scores, cells, seg.from_quarter, q, pct)

                in_correction, dwell_left, shift = _correction_expire(
                    in_correction, dwell_left, shift
                )

                if m == 0:
                    index[p, 0] = int(pool[rng.integers(0, pool.size)])
                    continue

                previous = int(index[p, m - 1])

                if previous + 1 >= n:
                    # Owner ruling 2026-08-16 (FIX2): the block ENDS at the
                    # panel's last row rather than wrapping to row 0 -- a
                    # silent 67-year era teleport that would bypass the join
                    # safety entirely. A fresh entry is drawn from THIS
                    # month's pool: era-filtered against the previous row
                    # when any candidate matches, unfiltered when none does.
                    # Both draws come from the block stream (rng), not the
                    # hazard stream -- it is a block event, not a correction.
                    forced_reentries += 1
                    pool_wo_prev = pool[pool != previous]
                    if pool_wo_prev.size:
                        ok = (era_bucket[pool_wo_prev] == era_bucket[previous]) & (
                            np.abs(yoy[pool_wo_prev] - yoy[previous]) <= spine.join_yoy_max_pp
                        )
                        filtered = pool_wo_prev[ok]
                    else:
                        filtered = pool_wo_prev
                    if filtered.size:
                        index[p, m] = int(filtered[rng.integers(0, filtered.size)])
                    else:
                        unfiltered_reentries += 1
                        index[p, m] = int(pool[rng.integers(0, pool.size)])
                    continue

                advanced = previous + 1
                if rng.random() >= 1.0 / float(seg.mean_block_months):
                    index[p, m] = advanced
                    continue

                # Exclude the current row itself (as stress does), then apply
                # the two spine-only join filters: the era bucket must match
                # (no CPI-YoY-era teleport) and the YoY level itself must sit
                # within the declared join bound. Severity is a preference
                # over entries, never a licence to teleport: with nothing
                # reachable the block simply continues.
                candidates = join_candidates(
                    source.values,
                    source.factor_names,
                    previous,
                    stress.join_tolerance,
                    pool[pool != previous],
                )
                if candidates.size:
                    ok = (era_bucket[candidates] == era_bucket[previous]) & (
                        np.abs(yoy[candidates] - yoy[previous]) <= spine.join_yoy_max_pp
                    )
                    candidates = candidates[ok]
                index[p, m] = (
                    advanced
                    if candidates.size == 0
                    else int(candidates[rng.integers(0, candidates.size)])
                )
        corrections: dict[str, Any] = {
            "per_path_onsets": per_path_onsets,
            "per_quadrant_onsets": per_quadrant_onsets,
            "per_quadrant_months": per_quadrant_months,
            "forced_reentries": forced_reentries,
            "unfiltered_reentries": unfiltered_reentries,
        }
        return index, corrections
