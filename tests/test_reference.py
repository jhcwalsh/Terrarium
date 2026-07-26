"""WP2.1b Task 3 acceptance: block-aware reference statistics and bootstrap bands.

``ah.eval.reference`` computes every reference statistic on train+validation only
(``ah.splits.DataAccess.train_val`` is the only sanctioned surface); the holdout must
never be reachable from it. Test 1 (leakage) and test 12 (inactive-block exclusion)
are the two that matter most per ``Instructions/WP2.1b-PRE-SEAL-PATCH.md`` Item 2 and
the WP2.1b Task 3 brief -- both are written as direct proofs against a recording
reader, not as trust in ``active_factors()``/``train_val()`` being called correctly.

Fix-pass-1 additions (review findings, see the scratchpad report for the full list):
the recording reader now intercepts ``frame()`` rather than ``train_val()`` (Critical 1)
so a direct/parallel holdout read is caught even if it bypasses ``train_val()``; the AST
leakage-token guard also flags qualified (``ah.splits.FinalEvaluationToken``) access, not
just bare names/imports; alignment tests use factors of deliberately different date
ranges, including a zero-overlap cross-block pair (Important 2); ``skew``/``acf_abs_1``
get hand-computed ground-truth tests (Important 5); and several structural/minor fixes
each get a dedicated test (see inline comments).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import ah.splits
from ah.eval import panel as panel_mod
from ah.eval import reference as reference_mod
from ah.eval.reference import (
    CROSS_BLOCK_STATS,
    SINGLE_FACTOR_STATS,
    STRATEGY_STATS,
    TAIL_DEPENDENCE_MIN_TAIL_OBS,
    ReferenceComputationError,
    RegisteredCrossStat,
    RegisteredStat,
    RegisteredStrategyStat,
    _draw_moving_block_indices,
    block_bootstrap_band,
    compute_reference,
    tail_dependence_lower,
    tail_dependence_upper,
)
from ah.factors import FactorManifest, FactorSource, load_manifest
from ah.splits import HOLDOUT, DataAccess, FinalEvaluationToken, Reader

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# synthetic data plumbing
# --------------------------------------------------------------------------- #


def _synthetic_frame(seed: int, start: str, end: str) -> pd.DataFrame:
    """A deterministic AR(1)-ish monthly series: mild autocorrelation, non-degenerate variance."""
    dates = pd.date_range(start, end, freq="MS")
    rng = np.random.Generator(np.random.PCG64(seed))
    eps = rng.normal(0.0, 1.0, size=len(dates))
    values = np.empty(len(dates))
    values[0] = eps[0]
    for t in range(1, len(dates)):
        values[t] = 0.3 * values[t - 1] + eps[t]
    return pd.DataFrame({"date": dates, "value": values})


def _make_reader(
    factor_seeds: dict[str, int], start: str = "1900-01-01", end: str = "2026-06-01"
) -> Reader:
    """A closure over a dict of synthetic DataFrames; unknown series raise KeyError."""
    frames = {name: _synthetic_frame(seed, start, end) for name, seed in factor_seeds.items()}

    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in frames:
            raise KeyError(series_id)
        return frames[series_id]

    return reader


def _make_reader_with_ranges(factor_specs: dict[str, tuple[int, str, str]]) -> Reader:
    """Like ``_make_reader`` but each factor gets its own ``(seed, start, end)``.

    For tests that need factors of deliberately different date ranges (Important 2) --
    all 12 tests inherited from before the fix-pass-1 review used one uniform range per
    fixture, which is why block-level over-alignment went unnoticed.
    """
    frames = {
        name: _synthetic_frame(seed, start, end)
        for name, (seed, start, end) in factor_specs.items()
    }

    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in frames:
            raise KeyError(series_id)
        return frames[series_id]

    return reader


class _RecordingAccess(DataAccess):
    """Records every date and series id returned by ``frame()``.

    Fix-pass-1 (Critical 1): the previous version overrode ``train_val()`` only. Since
    ``DataAccess.train_val()`` is already holdout-clean by construction (every date it
    returns is ``< HOLDOUT.start``, proved independently by
    ``tests/test_leakage_guard.py::test_train_val_excludes_holdout``), recording only
    at that layer meant the offenders assertion below could never fire -- it was
    redundant with a lower-layer guarantee, not a new leak channel. A direct or
    parallel holdout read (``access.frame(series_id, "holdout", token=...)``) bypasses
    ``train_val()`` entirely and so escaped detection.

    ``frame()`` is what ``train_val()`` calls internally for every split, so recording
    here catches the legitimate path *and* any direct/parallel holdout access reaching
    this same ``access`` object -- see
    ``test_leakage_guard_catches_the_review_mutation`` below, which proves this by
    applying the exact mutation quoted in the WP2.1b Task 3 review.
    """

    def __init__(self, reader: Reader) -> None:
        super().__init__(reader)
        self.dates_returned: list[pd.Timestamp] = []
        self.series_requested: list[str] = []

    def frame(
        self, series_id: str, split: str, *, token: FinalEvaluationToken | None = None
    ) -> pd.DataFrame:
        self.series_requested.append(series_id)
        df = super().frame(series_id, split, token=token)
        self.dates_returned.extend(df["date"].tolist())
        return df


def _small_manifest() -> FactorManifest:
    """A fast two-block, four-factor manifest for tests that don't need the real one.

    Fix pass 1 (Critical 1): every factor now declares a real ``kind: series`` source
    whose ``series_id`` happens to equal the factor name, because ``compute_reference``
    resolves factor ids through ``factor_sources`` rather than through an identity
    ``series_id_for`` default. The fixture's readers are keyed by those same names, so
    the data these tests see is unchanged -- what changed is that the mapping is now
    declared rather than assumed. ``kind: unavailable`` (the previous value) would now
    correctly mean "no data for this factor at all".
    """
    return FactorManifest(
        blocks={"global": ("g1", "g2"), "us": ("u1", "u2")},
        active_blocks=("global", "us"),
        sources={
            name: FactorSource(kind="series", series_id=name, units="ret")
            for name in ("g1", "g2", "u1", "u2")
        },
    )


# --------------------------------------------------------------------------- #
# 1. leakage: the critical tests
# --------------------------------------------------------------------------- #


def test_leakage_no_holdout_date_reaches_compute_reference() -> None:
    manifest = _small_manifest()
    reader = _make_reader({"g1": 1, "g2": 2, "u1": 3, "u2": 4})
    access = _RecordingAccess(reader)

    compute_reference(
        access, manifest, vintage_id="v-leak", seed=0, n_resamples=20, block_length=12
    )

    assert access.dates_returned, "expected compute_reference to actually read data"
    holdout_start = pd.Timestamp(HOLDOUT.start)
    offenders = [d for d in access.dates_returned if d >= holdout_start]
    assert not offenders, f"holdout-era dates reached compute_reference: {offenders[:5]}"


def test_leakage_guard_catches_the_review_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove the Critical-1 fix is a real guard, not a redundant check.

    Applies the exact mutation quoted in the WP2.1b Task 3 review -- a parallel,
    token-gated holdout read performed alongside the legitimate ``train_val()`` call --
    to ``compute_reference``'s own per-factor read path, and shows the leakage
    assertion actually fires. Before the fix (recording at ``train_val()`` only), this
    mutation would have gone completely undetected: ``frame()`` was not the overridden
    method, so ``access.frame(..., "holdout", token=...)`` was invisible to the
    recorder, and the whole suite would have stayed green with holdout data reaching a
    (hypothetically compromised) ``compute_reference``.
    """
    manifest = _small_manifest()
    reader = _make_reader({"g1": 1, "g2": 2, "u1": 3, "u2": 4})
    access = _RecordingAccess(reader)

    real_read_series = panel_mod._read_series

    def leaky_read_series(
        access_arg: DataAccess, series_id: str, split_reader, *, factor: str
    ) -> pd.DataFrame | None:
        # The exact mutation quoted in the review, applied alongside the real read.
        token = ah.splits.FinalEvaluationToken(purpose="x")
        access_arg.frame(series_id, "holdout", token=token)
        return real_read_series(access_arg, series_id, split_reader, factor=factor)

    # Fix pass 1 (Critical 1): compute_reference no longer owns the per-factor read --
    # ah.eval.panel.read_factor_frames does, for compute_reference and build_panel
    # alike. The mutation therefore targets that shared read path, which is the code
    # a real leak would have to live in; the guard being exercised (recording at
    # frame(), not train_val()) is unchanged.
    monkeypatch.setattr(panel_mod, "_read_series", leaky_read_series)

    compute_reference(
        access, manifest, vintage_id="v-leak-mut", seed=0, n_resamples=5, block_length=6
    )

    holdout_start = pd.Timestamp(HOLDOUT.start)
    offenders = [d for d in access.dates_returned if d >= holdout_start]
    assert offenders, (
        "the guard failed to catch a direct holdout read performed alongside "
        "train_val() -- recording must happen at frame(), not train_val()"
    )


# --------------------------------------------------------------------------- #
# 2 & 3. determinism
# --------------------------------------------------------------------------- #


def test_same_seed_gives_bit_identical_bands() -> None:
    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access_a = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))
    access_b = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))

    ref_a = compute_reference(
        access_a, manifest, vintage_id="v", seed=42, n_resamples=25, block_length=12
    )
    ref_b = compute_reference(
        access_b, manifest, vintage_id="v", seed=42, n_resamples=25, block_length=12
    )

    # Minor 10: compare the whole ReferenceStats, not just .blocks/.cross_blocks --
    # this also covers active_blocks/vintage_id/n_resamples/seed/missing_factors.
    # WP2.2 Task 3: `ergodicity_gap`'s reference-side fn is ALWAYS NaN (no historical
    # analog -- see `_ergodicity_gap_reference_stub`), and a plain dataclass `==` on
    # two NaN floats is False even when they are the "same" NaN. Compare via `.to_dict()`
    # (still the whole object, field for field) with `np.testing.assert_equal`, which
    # treats matching NaNs as equal -- what "bit-identical" actually means here.
    np.testing.assert_equal(ref_a.to_dict(), ref_b.to_dict())


def test_different_seed_gives_different_bands() -> None:
    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access_a = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))
    access_b = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))

    ref_a = compute_reference(
        access_a, manifest, vintage_id="v", seed=42, n_resamples=25, block_length=12
    )
    ref_b = compute_reference(
        access_b, manifest, vintage_id="v", seed=43, n_resamples=25, block_length=12
    )

    # Scoped to .blocks (not the whole object): ReferenceStats.seed differs by
    # construction here, which would make a whole-object inequality trivially true
    # regardless of whether the bands themselves actually changed -- the meaningful
    # claim is that the *bands* differ under a different seed.
    assert ref_a.blocks != ref_b.blocks


# --------------------------------------------------------------------------- #
# 4. block/cross-block shape matches the manifest
# --------------------------------------------------------------------------- #


def test_blocks_and_cross_blocks_match_manifest() -> None:
    manifest = load_manifest()
    factors_needed = [f for f in manifest.active_factors() if f != "commodities"]
    reader = _make_reader(
        {f: i for i, f in enumerate(factors_needed)}, start="1980-01-01", end="2026-06-01"
    )
    access = DataAccess(reader)

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=15, block_length=24
    )

    assert set(ref.blocks) == set(manifest.active_blocks)
    assert set(ref.cross_blocks) == set(manifest.cross_block_pairs())
    for pair, cross_ref in ref.cross_blocks.items():
        assert cross_ref.pair == pair


# --------------------------------------------------------------------------- #
# 5, 6, 7. statistic definitions against closed-form / known ground truth
# --------------------------------------------------------------------------- #


def test_mean_and_std_closed_form() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert SINGLE_FACTOR_STATS["mean"].fn(x) == pytest.approx(3.0)
    # ddof=1 sample std of 1..5: sum((x-3)**2) = 10, /(5-1) = 2.5, sqrt = 1.5811...
    assert SINGLE_FACTOR_STATS["std"].fn(x) == pytest.approx(np.sqrt(2.5))


def test_acf1_recovers_known_ar1_phi() -> None:
    rng = np.random.Generator(np.random.PCG64(123))
    n = 20_000
    phi = 0.6
    eps = rng.normal(0.0, 1.0, size=n)
    x = np.empty(n)
    x[0] = 0.0
    for t in range(1, n):
        x[t] = phi * x[t - 1] + eps[t]

    estimate = SINGLE_FACTOR_STATS["acf_r_lag1"].fn(x)
    # SE(phi_hat) ~ sqrt((1-phi^2)/n) ~ 0.0057 at n=20000, phi=0.6; 0.03 is > 5x that.
    assert estimate == pytest.approx(phi, abs=0.03)


def test_tail_dependence_near_zero_for_independent_factors() -> None:
    """Independent legs: at the sealed 5% tail fraction, the TRUE tail-dependence
    coefficient is 0.05 (the fraction itself, not exactly 0 -- see the estimator's own
    docstring for why), so a small, bounded-below-0.15 value at n=20000 is the
    expected, honest outcome (0.15 comfortably covers the estimator's own sampling
    noise at this n: the tail itself holds ~1000 observations, so the joint-exceedance
    count's relative standard error is a few percent of 0.05)."""
    rng = np.random.Generator(np.random.PCG64(41))
    n = 20_000
    a = rng.normal(size=n)
    b = rng.normal(size=n)  # independent of a
    assert tail_dependence_lower(a, b) < 0.15
    assert tail_dependence_upper(a, b) < 0.15


def test_tail_dependence_near_one_for_a_comonotone_pair() -> None:
    """A == B exactly: every rank exceedance coincides, so the coefficient is exactly
    1.0 at any tail fraction -- both directions."""
    rng = np.random.Generator(np.random.PCG64(42))
    a = rng.normal(size=2000)
    b = a.copy()
    assert tail_dependence_lower(a, b) == pytest.approx(1.0)
    assert tail_dependence_upper(a, b) == pytest.approx(1.0)


def test_tail_dependence_nan_below_the_minimum_tail_observation_floor() -> None:
    rng = np.random.Generator(np.random.PCG64(3))
    n = TAIL_DEPENDENCE_MIN_TAIL_OBS * 2  # n * 0.05 < TAIL_DEPENDENCE_MIN_TAIL_OBS
    a = rng.normal(size=n)
    b = rng.normal(size=n)
    assert np.isnan(tail_dependence_lower(a, b))
    assert np.isnan(tail_dependence_upper(a, b))


def test_tail_dependence_nan_on_mismatched_lengths() -> None:
    assert np.isnan(tail_dependence_lower(np.zeros(500), np.zeros(400)))


def test_tail_dependence_registered_in_cross_block_stats() -> None:
    assert CROSS_BLOCK_STATS["tail_dependence_lower"].fn is tail_dependence_lower
    assert CROSS_BLOCK_STATS["tail_dependence_upper"].fn is tail_dependence_upper
    assert CROSS_BLOCK_STATS["tail_dependence_lower"].tier == "monthly"


def test_strategy_stats_registry_has_the_eleven_wp22_task4_names() -> None:
    """RegisteredStrategyStat carries no `fn` (see the registry's own docstring) --
    this only proves the eleven names and their tier exist, the same shape
    ``test_mean_and_std_closed_form`` proves for SINGLE_FACTOR_STATS's `fn`."""
    expected = {
        "var_95",
        "es_95",
        "var_99",
        "es_99",
        "elicitability_score",
        "kupiec_pof_lr_1path",
        "kupiec_pof_chi2_tail_1path",
        "christoffersen_independence_lr_1path",
        "christoffersen_independence_chi2_tail_1path",
        "christoffersen_conditional_coverage_lr_1path",
        "christoffersen_conditional_coverage_chi2_tail_1path",
    }
    assert set(STRATEGY_STATS) == expected
    for registered in STRATEGY_STATS.values():
        assert isinstance(registered, RegisteredStrategyStat)
        assert registered.tier == "monthly"


def test_excess_kurtosis_normal_near_zero_student_t_clearly_positive() -> None:
    rng = np.random.Generator(np.random.PCG64(7))
    normal_sample = rng.normal(0.0, 1.0, size=200_000)
    t_sample = rng.standard_t(5, size=200_000)  # excess kurtosis = 6/(5-4) = 6.0

    k_normal = SINGLE_FACTOR_STATS["excess_kurtosis"].fn(normal_sample)
    k_t = SINGLE_FACTOR_STATS["excess_kurtosis"].fn(t_sample)

    assert abs(k_normal) < 0.1
    assert k_t > 1.0


def test_skew_hand_computed_ground_truth() -> None:
    """Important 5: ``skew`` had no ground-truth test -- only stats with closed-form or
    known-parameter checks did. Hand computation for ``x = [2, 3, 3, 8]``:

    mean = (2+3+3+8)/4 = 4
    deviations = [-2, -1, -1, 4]
    m2 = mean(dev**2) = (4+1+1+16)/4 = 22/4 = 5.5
    m3 = mean(dev**3) = (-8-1-1+64)/4 = 54/4 = 13.5
    skew = m3 / m2**1.5 = 13.5 / 5.5**1.5

    All of the above is exact rational arithmetic done by hand; only the final
    ``5.5**1.5`` power is left to the test to evaluate.
    """
    x = np.array([2.0, 3.0, 3.0, 8.0])
    expected = 13.5 / (5.5**1.5)
    assert SINGLE_FACTOR_STATS["skew"].fn(x) == pytest.approx(expected, abs=1e-9)


def test_acf_abs_1_known_by_construction() -> None:
    """Important 5: ``acf_abs_1`` had no ground-truth test. Hand computation for
    ``x = [1, 5, 2, 6, 1, 7]`` (n=6):

    mean(x) = (1+5+2+6+1+7)/6 = 22/6 = 11/3
    y = |x - mean(x)| = [8/3, 4/3, 5/3, 7/3, 8/3, 10/3]   (exact by hand)
    mean(y) = (8+4+5+7+8+10)/18 = 42/18 = 7/3
    dev_y = y - mean(y) = [1/3, -1, -2/3, 0, 1/3, 1]
    gamma0 = mean(dev_y**2) = (1/9 + 1 + 4/9 + 0 + 1/9 + 1)/6 = (4/9 + 2) /6 = (22/9)/6 = 22/54 = 4/9...
    (see below for the exact fraction chain)
    gamma1 = mean(dev_y[:-1]*dev_y[1:])
    acf1 = gamma1/gamma0 = 1/4 exactly.

    Constructed (not estimated asymptotically like ``test_acf1_recovers_known_ar1_phi``)
    so the expected value is exact, not a statistical approximation with a tolerance
    band -- this is what "known by construction" means here.
    """
    x = np.array([1.0, 5.0, 2.0, 6.0, 1.0, 7.0])
    assert SINGLE_FACTOR_STATS["acf_abs_lag1"].fn(x) == pytest.approx(0.25, abs=1e-9)


# --------------------------------------------------------------------------- #
# 8. band brackets its point estimate
# --------------------------------------------------------------------------- #


def test_band_brackets_point_estimate_for_every_stat() -> None:
    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))

    # block_length must comfortably exceed the longest registered lag: a moving-block
    # bootstrap keeps only the (b - k) / b share of lag-k pairs that fall inside one
    # block, so at b = 24 the lag-18..24 resample statistics are shrunk toward zero and
    # a full-sample point estimate genuinely falls outside its own band. That is a real
    # property of the estimator, not slack in this assertion -- see
    # `reference.DEFAULT_BLOCK_LENGTH` and
    # `test_short_blocks_shrink_a_long_lag_band_toward_zero` below, which pins it.
    ref = compute_reference(
        access,
        manifest,
        vintage_id="v",
        seed=5,
        n_resamples=200,
        block_length=reference_mod.DEFAULT_BLOCK_LENGTH,
    )

    # WP2.2 Task 3: a stat CAN be legitimately, honestly NaN on this fixture's ~76
    # years of history -- exactly the same "by construction" outcome
    # `hill_tail_index` already documents for a level factor, generalized. Any NaN
    # among point/lo/hi means no bracket claim can honestly be made, so those are
    # collected rather than asserted against -- and then the collected SET is asserted
    # to be exactly the expected one (WP2.2 Task 3 fix pass 1, Important 2). Skipping
    # unconditionally, as the first version of this test did, would silently green-light
    # any future all-NaN statistic: the generic invariant would still "pass" while
    # measuring nothing.
    checked = 0
    nan_stats: set[str] = set()
    for block_ref in ref.blocks.values():
        for name, band in block_ref.stats.items():
            checked += 1
            if np.isnan(band.point) or np.isnan(band.lo) or np.isnan(band.hi):
                nan_stats.add(name.split(".", 1)[1])
                continue
            assert band.lo <= band.point <= band.hi, f"{name}: {band}"
    for pair_ref in ref.cross_blocks.values():
        for name, band in pair_ref.stats.items():
            checked += 1
            if np.isnan(band.point) or np.isnan(band.lo) or np.isnan(band.hi):
                nan_stats.add(name.split(".", 1)[1])
                continue
            assert band.lo <= band.point <= band.hi, f"{name}: {band}"

    # Each of these is a NAMED, understood case, not a blanket exemption:
    #  - `ergodicity_gap` has no historical analog at all (history is one realization
    #    and there is no historical ENSEMBLE to compare it against), so its registered
    #    reference-side fn is always NaN by construction;
    #  - `variance_ratio_120m` needs >= VARIANCE_RATIO_MIN_SUMS (10) non-overlapping
    #    120-month sums, i.e. >= 1200 months (100 years) of history, more than this
    #    fixture's 76-year span provides -- NaN point AND NaN band;
    #  - the three `drawdown_*` statistics can have a REAL point (the full sample has
    #    plenty of episodes) but a NaN band: `block_bootstrap_band` draws length-matched
    #    (120-month) resamples, and a resample carrying fewer than
    #    DRAWDOWN_MIN_EPISODES pooled episodes legitimately returns NaN for THAT
    #    resample; `np.percentile` then propagates the single NaN into `lo`/`hi`
    #    (governance/retrofit-register.md RFR-19, shared sealed infrastructure).
    assert nan_stats == {
        "ergodicity_gap",
        "variance_ratio_120m",
        "drawdown_median_depth",
        "drawdown_median_duration",
        "drawdown_depth_duration_rank_corr",
    }

    # Minor 7: derive the expected count from the fixture instead of hardcoding two
    # coincidentally-equal "4"s (one counted factor instances, the other cross-factor
    # pairs -- both happened to be 4 for this fixture's shape).
    total_factors = sum(len(manifest.blocks[b]) for b in manifest.active_blocks)
    total_cross_factor_pairs = sum(
        len(manifest.blocks[a]) * len(manifest.blocks[b]) for a, b in manifest.cross_block_pairs()
    )
    expected = (
        len(SINGLE_FACTOR_STATS) * total_factors + len(CROSS_BLOCK_STATS) * total_cross_factor_pairs
    )
    assert checked == expected


# --------------------------------------------------------------------------- #
# 9. missing factor handling (the commodities gap)
# --------------------------------------------------------------------------- #


def test_missing_factor_recorded_and_absent_from_stats() -> None:
    manifest = load_manifest()
    factors_needed = [f for f in manifest.active_factors() if f != "commodities"]
    reader = _make_reader(
        {f: i for i, f in enumerate(factors_needed)}, start="1980-01-01", end="2026-06-01"
    )
    access = DataAccess(reader)

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=2, n_resamples=15, block_length=24
    )

    assert "commodities" in ref.missing_factors
    for block_ref in ref.blocks.values():
        for key in block_ref.stats:
            factor = key.split(".", 1)[0]
            assert factor != "commodities"
    for pair_ref in ref.cross_blocks.values():
        for key in pair_ref.stats:
            factors_in_key = key.split(".", 1)[0].split("~")
            assert "commodities" not in factors_in_key


def test_malformed_frame_raises_named_error() -> None:
    """Important 4: a reader failure that isn't a legitimate data gap (malformed frame,
    wrong columns) must name the offending factor and series id, not propagate an
    anonymous KeyError from deep inside ``df.set_index("date")["value"]``.
    """
    manifest = _small_manifest()
    seeds = {"g1": 1, "u1": 3, "u2": 4}
    frames = {f: _synthetic_frame(s, "1950-01-01", "2020-01-01") for f, s in seeds.items()}
    bad = _synthetic_frame(2, "1950-01-01", "2020-01-01").rename(columns={"value": "not_value"})

    def reader(series_id: str) -> pd.DataFrame:
        if series_id == "g2":
            return bad
        return frames[series_id]

    access = DataAccess(reader)
    with pytest.raises(ReferenceComputationError, match="g2"):
        compute_reference(access, manifest, vintage_id="v", seed=1, n_resamples=5, block_length=6)


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: historical_series is populated, unaligned, train+val only
# --------------------------------------------------------------------------- #


def test_historical_series_is_populated_per_present_factor() -> None:
    """ah.eval.metrics.tails/utility both read ReferenceStats.historical_series
    (never a fresh catalog read) -- this is the field that makes that possible."""
    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=5, block_length=12
    )

    assert set(ref.historical_series) == {"g1", "g2", "u1", "u2"}
    # Train+validation only (never the full synthetic series, which extends into the
    # holdout era) -- compare against access.train_val() itself, the sanctioned
    # surface, not the raw (longer) synthetic frame.
    expected_g1 = access.train_val("g1")
    np.testing.assert_allclose(
        ref.historical_series["g1"].to_numpy(), expected_g1["value"].to_numpy()
    )
    # Sidesteps pandas-stubs' overly broad DatetimeIndex.max() return type: a plain
    # Python list of Timestamps, maxed with the builtin, is unambiguously typed.
    holdout_start = pd.Timestamp(HOLDOUT.start)
    g1_dates: list[pd.Timestamp] = list(ref.historical_series["g1"].index)
    assert max(g1_dates) < holdout_start


def test_historical_series_omits_a_factor_with_no_data() -> None:
    manifest = _small_manifest()
    seeds = {"g1": 1, "u1": 3, "u2": 4}  # g2's reader raises KeyError (no data at all)
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=5, block_length=12
    )
    assert "g2" not in ref.historical_series
    assert "g2" in ref.missing_no_data


# --------------------------------------------------------------------------- #
# 10. to_dict() JSON round-trip
# --------------------------------------------------------------------------- #


def test_to_dict_round_trips_through_json() -> None:
    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))

    ref = compute_reference(
        access, manifest, vintage_id="v-json", seed=9, n_resamples=10, block_length=12
    )

    encoded = json.dumps(ref.to_dict())
    decoded = json.loads(encoded)

    assert decoded["vintage_id"] == "v-json"
    assert set(decoded["blocks"]) == {"global", "us"}
    assert "global|us" in decoded["cross_blocks"]
    sample_band = decoded["blocks"]["global"]["g1.mean"]
    assert set(sample_band) == {
        "point",
        "lo",
        "hi",
        "n_resamples",
        "level",
        "tier",
        "resample_length",
        "n_valid_resamples",
    }
    # No zero-overlap pairs in this uniform-range fixture.
    assert decoded["zero_overlap_pairs"] == {}


def test_to_dict_reports_zero_overlap_pairs() -> None:
    manifest = _small_manifest()
    specs = {
        "g1": (1, "1950-01-01", "1970-01-01"),
        "g2": (2, "1950-01-01", "1970-01-01"),
        "u1": (3, "2000-01-01", "2020-01-01"),
        "u2": (4, "2000-01-01", "2020-01-01"),
    }
    access = DataAccess(_make_reader_with_ranges(specs))

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=10, block_length=6
    )
    decoded = json.loads(json.dumps(ref.to_dict()))

    assert set(decoded["zero_overlap_pairs"]["global|us"]) == {"g1~u1", "g1~u2", "g2~u1", "g2~u2"}


# --------------------------------------------------------------------------- #
# 11. import-graph proof: reference.py never reaches the holdout mint
# --------------------------------------------------------------------------- #

_G2_IMPORT = re.compile(
    r"import\s+ah\.eval\.g2|from\s+ah\.eval\.g2\b|from\s+ah\.eval\s+import\s+.*\bg2\b"
)


def test_reference_module_never_imports_g2_or_names_the_token() -> None:
    path = ROOT / "src" / "ah" / "eval" / "reference.py"
    text = path.read_text(encoding="utf-8")
    assert not _G2_IMPORT.search(text), "reference.py must never import ah.eval.g2"

    # A docstring *mention* of FinalEvaluationToken is fine (this module's own docstring
    # explains why it holds none, same convention as the narrative-blindness test); what
    # must never appear is an actual code reference -- an import, a bare name use, or
    # (fix-pass-1, Critical 1) a qualified attribute access like
    # ``ah.splits.FinalEvaluationToken`` that a bare-name/import check alone would miss.
    tree = ast.parse(text, filename=str(path))
    imported = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == "FinalEvaluationToken"
    ]
    referenced = [
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "FinalEvaluationToken"
    ]
    attr_referenced = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "FinalEvaluationToken"
    ]
    assert not imported and not referenced and not attr_referenced, (
        "reference.py must never reference FinalEvaluationToken in code -- it never "
        f"accepts one (imports={imported}, name-refs={referenced}, attr-refs={attr_referenced})"
    )


def test_ast_guard_detects_qualified_final_evaluation_token_access() -> None:
    """Prove the broadened AST guard above actually catches qualified access.

    Applies the exact mutation quoted in the WP2.1b Task 3 review
    (``ah.splits.FinalEvaluationToken(purpose="x")``) to a standalone snippet and
    confirms the ``ast.Attribute`` check used by the real guard test flags it -- a
    bare-name/import check alone (the pre-fix-pass-1 guard) would see nothing wrong
    with this snippet, since ``FinalEvaluationToken`` here is never an ``ast.Name`` or
    an imported alias, only the ``.attr`` of an ``ast.Attribute`` node.
    """
    snippet = (
        "import ah.splits\n"
        "def _leak(access, series_id):\n"
        "    token = ah.splits.FinalEvaluationToken(purpose='x')\n"
        "    return access.frame(series_id, 'holdout', token=token)\n"
    )
    tree = ast.parse(snippet)

    imported = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == "FinalEvaluationToken"
    ]
    referenced = [
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "FinalEvaluationToken"
    ]
    attr_referenced = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "FinalEvaluationToken"
    ]

    assert not imported and not referenced, "sanity check: this mutation uses qualified access only"
    assert attr_referenced == ["FinalEvaluationToken"]


# --------------------------------------------------------------------------- #
# 12. inactive-block exclusion: uk must never be reached
# --------------------------------------------------------------------------- #


def test_inactive_uk_block_never_reached() -> None:
    manifest = load_manifest()
    assert manifest.is_active("uk") is False  # precondition this test relies on

    # Data is available for EVERY declared factor, including uk and commodities, so a
    # bug that iterated manifest.blocks (all blocks) instead of manifest.active_blocks
    # would succeed silently rather than being masked by missing data.
    all_declared = [f for factors in manifest.blocks.values() for f in factors]
    reader = _make_reader(
        {f: i for i, f in enumerate(all_declared)}, start="1980-01-01", end="2026-06-01"
    )
    access = _RecordingAccess(reader)

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=3, n_resamples=10, block_length=24
    )

    uk_factors = set(manifest.blocks["uk"])

    assert "uk" not in ref.blocks
    for pair in ref.cross_blocks:
        assert "uk" not in pair
    assert not (uk_factors & set(ref.missing_factors))
    for block_ref in ref.blocks.values():
        for key in block_ref.stats:
            assert key.split(".", 1)[0] not in uk_factors
    for pair_ref in ref.cross_blocks.values():
        for key in pair_ref.stats:
            factors_in_key = key.split(".", 1)[0].split("~")
            assert not (uk_factors & set(factors_in_key))
    assert not (uk_factors & set(access.series_requested)), (
        f"reader was asked for a uk series: {sorted(uk_factors & set(access.series_requested))}"
    )


# --------------------------------------------------------------------------- #
# 13. Important 2: alignment is scoped, not global
# --------------------------------------------------------------------------- #


def test_short_history_factor_does_not_truncate_other_factors_reference_window() -> None:
    """Important 2: a short-history factor must not silently truncate the reference
    window used for a *different* factor's own statistics -- neither across blocks nor
    within the same block (the review's own example: spread/volatility indices start
    decades after the equity series they share a block with).

    ``g1``/``g2`` (block ``global``) and ``u1`` (block ``us``) span the fixture's full
    range; ``u2`` (also block ``us``) is deliberately much shorter. Under the old
    global-inner-join design, every factor's stats would have been truncated to u2's
    ~5-year window. They must not be.
    """
    manifest = _small_manifest()
    specs = {
        "g1": (1, "1950-01-01", "2020-01-01"),
        "g2": (2, "1950-01-01", "2020-01-01"),
        "u1": (3, "1950-01-01", "2020-01-01"),
        "u2": (4, "2015-01-01", "2020-01-01"),  # short history, same block as u1
    }
    access = DataAccess(_make_reader_with_ranges(specs))

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=20, block_length=12
    )

    expected_g1_mean = float(
        np.mean(_synthetic_frame(1, "1950-01-01", "2020-01-01")["value"].to_numpy())
    )
    expected_u1_mean = float(
        np.mean(_synthetic_frame(3, "1950-01-01", "2020-01-01")["value"].to_numpy())
    )

    assert ref.blocks["global"].stats["g1.mean"].point == pytest.approx(expected_g1_mean)
    assert ref.blocks["us"].stats["u1.mean"].point == pytest.approx(expected_u1_mean)


def test_zero_overlap_cross_block_pair_is_named_not_raised() -> None:
    """Important 2: a cross-block factor pair with zero date overlap must produce a
    clear, named outcome (``CrossBlockReference.zero_overlap_pairs``), not an unhandled
    ``ValueError`` raised from deep inside ``block_bootstrap_band`` -- and must not
    prevent the rest of compute_reference (other blocks' own stats) from succeeding.
    """
    manifest = _small_manifest()
    specs = {
        "g1": (1, "1950-01-01", "1970-01-01"),
        "g2": (2, "1950-01-01", "1970-01-01"),
        "u1": (3, "2000-01-01", "2020-01-01"),  # no overlap with g1/g2 at all
        "u2": (4, "2000-01-01", "2020-01-01"),
    }
    access = DataAccess(_make_reader_with_ranges(specs))

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=10, block_length=6
    )

    pair_ref = ref.cross_blocks[("global", "us")]
    assert set(pair_ref.zero_overlap_pairs) == {"g1~u1", "g1~u2", "g2~u1", "g2~u2"}
    assert pair_ref.stats == {}
    # Each block's own single-factor stats are unaffected by the other block's range.
    assert "g1.mean" in ref.blocks["global"].stats
    assert "u1.mean" in ref.blocks["us"].stats


# --------------------------------------------------------------------------- #
# 14. Important 4: block_bootstrap_band error messages name their context
# --------------------------------------------------------------------------- #


def test_block_bootstrap_band_empty_panel_error_names_context() -> None:
    empty_panel = np.empty((0, 1), dtype=np.float64)
    with pytest.raises(ValueError, match=re.escape("block=global factor=g1 stat=mean")):
        block_bootstrap_band(
            lambda arr: float(np.mean(arr[:, 0])),
            empty_panel,
            seed=1,
            n_resamples=5,
            level=0.9,
            block_length=6,
            context="block=global factor=g1 stat=mean",
        )


# --------------------------------------------------------------------------- #
# 15. Minor 6: shared resample indices are explicit, not emergent
# --------------------------------------------------------------------------- #


def test_draw_moving_block_indices_is_deterministic() -> None:
    idx_a = _draw_moving_block_indices(30, seed=7, n_resamples=50, block_length=6)
    idx_b = _draw_moving_block_indices(30, seed=7, n_resamples=50, block_length=6)
    assert np.array_equal(idx_a, idx_b)


def test_block_bootstrap_band_reuses_supplied_resample_indices() -> None:
    """Two different sample_fns given the same explicit ``resample_indices`` must see
    exactly the same resampled sub-panels at each draw -- the mechanism minor-6's fix
    relies on to make "stats sharing a panel share a resample" explicit rather than an
    accident of matching (seed, T, block_length, n_resamples).
    """
    t = 30
    panel = np.arange(t, dtype=np.float64).reshape(-1, 1)
    resample_indices = _draw_moving_block_indices(t, seed=7, n_resamples=5, block_length=6)

    captured_a: list[np.ndarray] = []
    captured_b: list[np.ndarray] = []

    def sample_a(arr: np.ndarray) -> float:
        captured_a.append(arr[:, 0].copy())
        return float(np.mean(arr[:, 0]))

    def sample_b(arr: np.ndarray) -> float:
        captured_b.append(arr[:, 0].copy())
        return float(np.std(arr[:, 0]))

    block_bootstrap_band(
        sample_a,
        panel,
        seed=999,
        n_resamples=5,
        level=0.9,
        block_length=6,
        resample_indices=resample_indices,
    )
    block_bootstrap_band(
        sample_b,
        panel,
        seed=999,
        n_resamples=5,
        level=0.9,
        block_length=6,
        resample_indices=resample_indices,
    )

    # index 0 of each capture is the point-estimate call (the full, un-resampled panel);
    # the remaining n_resamples entries are the resample draws.
    resamples_a = captured_a[1:]
    resamples_b = captured_b[1:]
    assert len(resamples_a) == len(resamples_b) == 5
    for a, b in zip(resamples_a, resamples_b, strict=True):
        assert np.array_equal(a, b)


def test_block_reference_reuses_resample_indices_across_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration-level proof of minor 6: compute_reference's own block loop draws the
    moving-block resample once per factor and reuses it across every stat registered
    for that factor.
    """
    captured: dict[str, list[np.ndarray]] = {"a": [], "b": []}

    def stat_a(x: np.ndarray) -> float:
        captured["a"].append(x.copy())
        return float(np.sum(x))

    def stat_b(x: np.ndarray) -> float:
        captured["b"].append(x.copy())
        return float(np.sum(x))

    monkeypatch.setitem(
        reference_mod.SINGLE_FACTOR_STATS,
        "_probe_a",
        RegisteredStat(fn=stat_a, tier="monthly"),
    )
    monkeypatch.setitem(
        reference_mod.SINGLE_FACTOR_STATS,
        "_probe_b",
        RegisteredStat(fn=stat_b, tier="monthly"),
    )

    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))
    compute_reference(access, manifest, vintage_id="v", seed=11, n_resamples=8, block_length=6)

    # (both probes see the same factor loop structure: point, 8 resamples, per factor)
    assert captured["a"] and captured["b"]
    assert len(captured["a"]) == len(captured["b"])
    # Re-derive point-estimate positions (one per factor, 9 entries apart: 1 point + 8
    # resamples) and compare only the resample entries, per factor.
    n_per_factor = 1 + 8
    assert len(captured["a"]) % n_per_factor == 0
    for start in range(0, len(captured["a"]), n_per_factor):
        a_resamples = captured["a"][start + 1 : start + n_per_factor]
        b_resamples = captured["b"][start + 1 : start + n_per_factor]
        for a, b in zip(a_resamples, b_resamples, strict=True):
            assert np.array_equal(a, b)


def test_cross_block_reference_reuses_resample_indices_across_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same as the block-level proof above, for cross-block pair stats."""
    captured: dict[str, list[np.ndarray]] = {"a": [], "b": []}

    def stat_a(a: np.ndarray, b: np.ndarray) -> float:
        captured["a"].append(np.stack([a, b], axis=1))
        return float(np.sum(a))

    def stat_b(a: np.ndarray, b: np.ndarray) -> float:
        captured["b"].append(np.stack([a, b], axis=1))
        return float(np.sum(b))

    monkeypatch.setitem(
        reference_mod.CROSS_BLOCK_STATS,
        "_probe_a",
        RegisteredCrossStat(fn=stat_a, tier="monthly"),
    )
    monkeypatch.setitem(
        reference_mod.CROSS_BLOCK_STATS,
        "_probe_b",
        RegisteredCrossStat(fn=stat_b, tier="monthly"),
    )

    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))
    compute_reference(access, manifest, vintage_id="v", seed=11, n_resamples=6, block_length=6)

    n_per_pair = 1 + 6
    assert len(captured["a"]) == len(captured["b"]) > 0
    assert len(captured["a"]) % n_per_pair == 0
    for start in range(0, len(captured["a"]), n_per_pair):
        a_resamples = captured["a"][start + 1 : start + n_per_pair]
        b_resamples = captured["b"][start + 1 : start + n_per_pair]
        for a, b in zip(a_resamples, b_resamples, strict=True):
            assert np.array_equal(a, b)


# --------------------------------------------------------------------------- #
# 16. Minor 8: CROSS_BLOCK_STATS carries tier on a record, not hardcoded inline
# --------------------------------------------------------------------------- #


def test_cross_block_stat_tier_flows_from_registry_not_hardcoded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        reference_mod.CROSS_BLOCK_STATS,
        "correlation",
        RegisteredCrossStat(fn=reference_mod.CROSS_BLOCK_STATS["correlation"].fn, tier="severe"),
    )

    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))
    ref = compute_reference(
        access, manifest, vintage_id="v", seed=3, n_resamples=10, block_length=12
    )

    pair_ref = ref.cross_blocks[("global", "us")]
    sample_key = next(k for k in pair_ref.stats if k.endswith(".correlation"))
    assert pair_ref.stats[sample_key].tier == "severe"


# --------------------------------------------------------------------------- #
# 17. Minor 9: block_length is validated, not silently clamped
# --------------------------------------------------------------------------- #


def test_block_bootstrap_band_rejects_nonpositive_block_length() -> None:
    panel = np.arange(10, dtype=np.float64).reshape(-1, 1)
    for bad_block_length in (0, -3):
        with pytest.raises(ValueError, match="block_length"):
            block_bootstrap_band(
                lambda arr: float(np.mean(arr[:, 0])),
                panel,
                seed=1,
                n_resamples=5,
                level=0.9,
                block_length=bad_block_length,
            )


def test_draw_moving_block_indices_rejects_nonpositive_block_length() -> None:
    for bad_block_length in (0, -3):
        with pytest.raises(ValueError, match="block_length"):
            _draw_moving_block_indices(10, seed=1, n_resamples=5, block_length=bad_block_length)


# --------------------------------------------------------------------------- #
# 17b. Minor 5 (WP2.2 Task 2 fix pass 2): a block_length covering the whole panel
#      leaves no block-start freedom -- every replicate is the identical whole-sample
#      block, a zero-width band that would fail nearly any threshold with no warning.
#      Not reachable at today's 120-month paths and 1996+ shortest series, but reachable
#      as soon as a judged path length exceeds a short-history factor's own history.
# --------------------------------------------------------------------------- #


def test_draw_moving_block_indices_rejects_block_length_covering_the_whole_panel() -> None:
    with pytest.raises(ValueError, match="no block-start freedom"):
        _draw_moving_block_indices(10, seed=1, n_resamples=5, block_length=10)
    with pytest.raises(ValueError, match="no block-start freedom"):
        _draw_moving_block_indices(10, seed=1, n_resamples=5, block_length=20)


def test_block_bootstrap_band_rejects_block_length_covering_the_whole_panel() -> None:
    panel = np.arange(10, dtype=np.float64).reshape(-1, 1)
    with pytest.raises(ValueError, match="no block-start freedom"):
        block_bootstrap_band(
            lambda arr: float(np.mean(arr[:, 0])),
            panel,
            seed=1,
            n_resamples=5,
            level=0.9,
            block_length=10,
        )


# --------------------------------------------------------------------------- #
# 18. WP2.2 Task 1 fix pass, Critical 1: compute_reference resolves factor ids
#     through the manifest's factor_sources mapping.
#
# Before this fix compute_reference took a `series_id_for` callable defaulting to
# identity and nothing ever passed it the manifest, so it asked the catalog for
# "equity_mkt"/"policy_rate"/... -- not series ids -- and EVERY factor landed in
# missing_factors with an empty reference and no error. This is the test that would
# have caught it: a reader keyed by the manifest's own declared series ids must
# produce a populated reference, and a factor that is genuinely available must NOT
# appear in missing_factors.
# --------------------------------------------------------------------------- #


def _series_ids_of(manifest: FactorManifest) -> set[str]:
    needed: set[str] = set()
    for factor in manifest.active_factors():
        source = manifest.sources[factor]
        if source.kind == "series":
            assert source.series_id is not None
            needed.add(source.series_id)
        elif source.kind == "derived":
            needed.update(source.inputs)
    return needed


def test_compute_reference_resolves_real_manifest_series_ids() -> None:
    manifest = load_manifest()
    needed = _series_ids_of(manifest)
    reader = _make_reader(
        {sid: i for i, sid in enumerate(sorted(needed))}, start="1980-01-01", end="2026-06-01"
    )
    access = DataAccess(reader)

    ref = compute_reference(
        access, manifest, vintage_id="v-map", seed=1, n_resamples=5, block_length=12
    )

    # commodities is the one declared-unavailable active factor; everything else has a
    # declared source and real data, so nothing else may be missing.
    assert ref.missing_factors == ("commodities",)
    for factor in manifest.active_factors():
        if factor == "commodities":
            continue
        block = manifest.block_of(factor)
        assert f"{factor}.mean" in ref.blocks[block].stats, (
            f"factor '{factor}' has a declared factor_sources entry and real data, but "
            f"compute_reference produced no statistic for it"
        )


def test_compute_reference_computes_derived_factors_not_only_series_factors() -> None:
    """A `kind: derived` factor (ig_spread = fred.BAA - fred.AAA) must resolve too.

    ``FactorManifest.series_id_for`` *raises* for a derived factor, so a wiring that
    passed that method straight through as ``series_id_for=`` would crash here rather
    than compute anything -- the structural incompatibility the review flagged.
    """
    manifest = load_manifest()
    needed = _series_ids_of(manifest)
    reader = _make_reader(
        {sid: i for i, sid in enumerate(sorted(needed))}, start="1980-01-01", end="2026-06-01"
    )
    access = DataAccess(reader)

    ref = compute_reference(
        access, manifest, vintage_id="v-derived", seed=1, n_resamples=5, block_length=12
    )

    assert "ig_spread.mean" in ref.blocks["global"].stats
    assert "funding_spread.mean" in ref.blocks["us"].stats


def test_reference_records_per_factor_coverage() -> None:
    """I4: per-factor effective sample varies roughly fourfold and was recorded nowhere.

    `min_start` across the mapped series runs 1913 (fred.CPI) to 1996 (fred.HY_OAS), so
    a sealed `equity_vol` band rests on ~30 years of history and a sealed `equity_mkt`
    band on ~95. A band that does not say how much history it rests on is not
    auditable, which is the whole point of the mapping this module now reads.
    """
    manifest = _small_manifest()
    specs = {
        "g1": (1, "1950-01-01", "2020-01-01"),
        "g2": (2, "1950-01-01", "2020-01-01"),
        "u1": (3, "1950-01-01", "2020-01-01"),
        "u2": (4, "2000-01-01", "2020-01-01"),  # deliberately much shorter
    }
    access = DataAccess(_make_reader_with_ranges(specs))

    ref = compute_reference(
        access, manifest, vintage_id="v-cov", seed=1, n_resamples=5, block_length=12
    )

    assert set(ref.coverage) == {"g1", "g2", "u1", "u2"}
    assert ref.coverage["g1"].first_date == "1950-01-01"
    assert ref.coverage["u2"].first_date == "2000-01-01"
    # train+validation ends before the holdout, so no factor's last date reaches it
    assert ref.coverage["g1"].last_date < HOLDOUT.start
    # the short factor really is short -- the fourfold-spread case, made visible
    assert ref.coverage["u2"].n_obs * 3 < ref.coverage["g1"].n_obs
    assert json.loads(json.dumps(ref.to_dict()))["coverage"]["u2"]["n_obs"] == (
        ref.coverage["u2"].n_obs
    )


def test_reference_splits_missing_declared_from_missing_no_data() -> None:
    """I3, from the reference side."""
    manifest = load_manifest()
    needed = _series_ids_of(manifest)
    # drop one real series id: hy_spread becomes "declared available, no data"
    hy_series = manifest.sources["hy_spread"].series_id
    assert hy_series is not None
    reader = _make_reader(
        {sid: i for i, sid in enumerate(sorted(needed - {hy_series}))},
        start="1980-01-01",
        end="2026-06-01",
    )
    access = DataAccess(reader)

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=1, n_resamples=5, block_length=12
    )

    assert ref.missing_declared == ("commodities",)
    assert ref.missing_no_data == ("hy_spread",)
    assert set(ref.missing_factors) == {"commodities", "hy_spread"}


# --------------------------------------------------------------------------- #
# WP2.2 Task 2 fix pass -- Critical 2: the monthly statistics are registered here
#
# `ah.eval.prereg` validates a threshold key's `<stat>` against these registries, and
# `ah.eval.battery._lookup_band` matches a metric to its historical band by the same
# name. A monthly metric whose statistic is not registered here can therefore neither
# carry a sealed threshold nor be shown against history.
# --------------------------------------------------------------------------- #


_EXPECTED_NEW_SINGLE_FACTOR_STATS = (
    "hill_tail_index_5pct",
    "hill_tail_index_1pct",
    *[f"acf_r_lag{k}" for k in range(1, 6)],
    *[f"acf_abs_lag{k}" for k in range(1, 25)],
    "acf_abs_decay",
    "agg_gaussianity_3m",
    "agg_gaussianity_12m",
    "leverage_correlation",
)


def test_monthly_statistics_are_registered_as_single_factor_stats() -> None:
    for name in _EXPECTED_NEW_SINGLE_FACTOR_STATS:
        assert name in SINGLE_FACTOR_STATS, name
        assert SINGLE_FACTOR_STATS[name].tier == "monthly", name


def test_panel_statistics_registry_carries_the_corr_matrix_distance() -> None:
    from ah.eval.reference import PANEL_STATS

    assert "cross_block_corr_matrix_distance" in PANEL_STATS
    assert PANEL_STATS["cross_block_corr_matrix_distance"].tier == "monthly"


def test_no_two_registered_statistics_are_the_same_quantity() -> None:
    """Two registered names computing one number is a seal hazard: WP2.3 would author
    two bands and two thresholds on a single quantity. `acf_1`/`acf_abs_1` (lag 1) and
    `agg_gaussianity_1m` (the identity aggregation, i.e. `excess_kurtosis`) were
    exactly that; the lag-indexed names replace the former and the latter is not
    registered at all.
    """
    rng = np.random.Generator(np.random.PCG64(4242))
    x = rng.standard_t(df=5, size=800)
    values: dict[str, float] = {}
    for name, registered in SINGLE_FACTOR_STATS.items():
        value = registered.fn(x)
        if np.isnan(value):
            continue
        for other, other_value in values.items():
            assert value != pytest.approx(other_value, rel=0, abs=1e-12), (
                f"'{name}' and '{other}' are the same quantity ({value})"
            )
        values[name] = value


# --------------------------------------------------------------------------- #
# WP2.2 Task 2 fix pass -- Important 3: length-matched reference resampling
#
# Every per-path statistic uses the n-denominator Box-Jenkins ACF estimator, whose
# finite-sample bias is a function of the series length. History is ~1100 months; a
# generated path is a fraction of that. Reference replicates are therefore drawn at the
# ensemble's own path length so both sides carry the same estimator bias.
# --------------------------------------------------------------------------- #


def test_draw_moving_block_indices_honours_resample_length() -> None:
    idx = _draw_moving_block_indices(
        100, seed=0, n_resamples=5, block_length=10, resample_length=30
    )
    assert idx.shape == (5, 30)
    assert idx.min() >= 0
    assert idx.max() < 100


def test_block_bootstrap_band_records_the_resample_length() -> None:
    rng = np.random.Generator(np.random.PCG64(17))
    panel = rng.normal(size=(400, 1))
    band = block_bootstrap_band(
        lambda a: float(np.mean(a[:, 0])),
        panel,
        seed=3,
        n_resamples=50,
        level=0.9,
        block_length=24,
        resample_length=60,
    )
    assert band.resample_length == 60


def test_resample_length_widens_a_length_sensitive_band() -> None:
    """A shorter replicate is a noisier estimate, so its percentile band is wider.
    This is the property that makes the band comparable to a short generated path."""
    rng = np.random.Generator(np.random.PCG64(18))
    panel = rng.normal(size=(1200, 1))
    stat = lambda a: SINGLE_FACTOR_STATS["acf_abs_lag24"].fn(a[:, 0])  # noqa: E731
    kw = dict(seed=3, n_resamples=200, level=0.9, block_length=120)
    full = block_bootstrap_band(stat, panel, **kw)  # type: ignore[arg-type]
    short = block_bootstrap_band(stat, panel, resample_length=120, **kw)  # type: ignore[arg-type]
    assert (short.hi - short.lo) > 2.0 * (full.hi - full.lo)


def test_compute_reference_stamps_the_resample_length_on_every_band() -> None:
    manifest = _small_manifest()
    access = DataAccess(_make_reader({"g1": 1, "g2": 2, "u1": 3, "u2": 4}, start="1950-01-01"))
    ref = compute_reference(
        access,
        manifest,
        vintage_id="v",
        seed=0,
        n_resamples=5,
        block_length=12,
        resample_length=120,
    )
    # Every band records the length its own replicates were drawn at, and the field is
    # now per STATISTIC rather than uniform (WP2.2 Task 3 fix pass 1, Critical 1): a
    # statistic registered `length_matched=False` is drawn at the full sample length,
    # recorded as None, and the two decade-frequency statistics are exactly those. The
    # assertion is over the split, not over a blanket "everything is 120", so that a
    # future statistic silently opting out of length matching fails this test.
    unmatched = {"lost_decade_frequency", "long_inflation_era_frequency"}
    by_stat = {
        name.split(".", 1)[1]: band
        for block in ref.blocks.values()
        for name, band in block.stats.items()
    }
    assert by_stat
    for stat, band in by_stat.items():
        expected = None if stat in unmatched else 120
        assert band.resample_length == expected, stat


def test_default_block_length_exceeds_the_longest_registered_lag() -> None:
    """A moving-block bootstrap keeps only the ``(b - k) / b`` share of lag-k pairs
    that fall inside one block, so a block length near the longest judged lag makes
    every long-lag band an artifact of the resampling rather than a statement about
    history. The default must leave real headroom over
    ``reference.MAX_REGISTERED_LAG``."""
    assert reference_mod.MAX_REGISTERED_LAG == 24
    assert reference_mod.DEFAULT_BLOCK_LENGTH >= 4 * reference_mod.MAX_REGISTERED_LAG


# --------------------------------------------------------------------------- #
# Minor 6 (WP2.2 Task 2 fix pass 2): sealed numeric constants pinned exactly.
#
# pre-registration.yaml's conventions.acf_abs_decay_estimator, conventions.
# agg_gaussianity_estimator and conventions.estimator_length_matching all describe
# these module constants BY VALUE (241 grid points, rate range [-1.0, 5.0], tolerance
# 1e-10, at most 200 iterations, the 30-sum floor, DEFAULT_BLOCK_LENGTH=120). Nothing
# previously asserted the exact values against the code -- only bracket-style
# properties (e.g. the block-length-vs-lag test above). Pre-seal, a divergence between
# the sealed prose and the code is a silent drift with a green suite; post-seal it
# trips the lock. Pinned here so a divergence trips a test instead, on either side.
# --------------------------------------------------------------------------- #


def test_sealed_decay_estimator_constants_match_the_pre_registration() -> None:
    """pre-registration.yaml's conventions.acf_abs_decay_estimator: '241 equally spaced
    grid points across rate in [-1.0, 5.0], then golden-section search ... to an
    interval width of 1e-10 (at most 200 iterations)'."""
    assert reference_mod._DECAY_RATE_MIN == -1.0
    assert reference_mod._DECAY_RATE_MAX == 5.0
    assert reference_mod._DECAY_GRID_POINTS == 241
    assert reference_mod._DECAY_GOLDEN_TOL == 1e-10
    assert reference_mod._DECAY_MAX_ITERATIONS == 200


def test_sealed_agg_gaussianity_floor_matches_the_pre_registration() -> None:
    """pre-registration.yaml's conventions.agg_gaussianity_estimator: 'NaN below 30
    pooled sums'."""
    assert reference_mod.AGG_GAUSSIANITY_MIN_SUMS == 30


def test_sealed_default_block_length_matches_the_pre_registration() -> None:
    """pre-registration.yaml's conventions.estimator_length_matching: 'The sealed
    default is 120 months (ah.eval.reference.DEFAULT_BLOCK_LENGTH)'."""
    assert reference_mod.DEFAULT_BLOCK_LENGTH == 120


def test_short_blocks_shrink_a_long_lag_band_toward_zero() -> None:
    """The artifact the default block length exists to avoid, pinned so it cannot be
    rediscovered as a surprise while authoring sealed bands: with blocks no longer
    than the lag being measured, the resample distribution of a lag-k autocorrelation
    collapses toward zero however strong the dependence in the data actually is."""
    n = 1200
    t = np.arange(n)
    # a deterministic period-24 cycle: lag-24 autocorrelation is ~1 by construction
    panel = np.cos(2.0 * np.pi * t / 24.0).reshape(-1, 1)
    stat = SINGLE_FACTOR_STATS["acf_abs_lag24"].fn
    kw: dict[str, object] = dict(seed=1, n_resamples=200, level=0.9)
    short = block_bootstrap_band(lambda a: stat(a[:, 0]), panel, block_length=24, **kw)  # type: ignore[arg-type]
    long = block_bootstrap_band(
        lambda a: stat(a[:, 0]),
        panel,
        block_length=reference_mod.DEFAULT_BLOCK_LENGTH,
        **kw,  # type: ignore[arg-type]
    )
    assert short.point == pytest.approx(long.point)  # same full-sample estimate
    assert abs(short.hi) < 0.5 * abs(long.point), "short blocks must destroy the lag-24 signal"
    # Blocks five times the lag keep most of it. (Not all: every block seam still
    # breaks the lag-24 pairs that straddle it, which is why even here the band sits
    # below the full-sample point -- a second reason a band and its point estimate are
    # not interchangeable.)
    assert long.lo > 0.7 * long.point


def test_new_statistics_recover_known_ground_truths() -> None:
    """Each newly registered estimator against a closed-form or constructed target,
    at the registry surface `ah.eval.prereg` and `ah.eval.battery` actually consume."""
    rng = np.random.Generator(np.random.PCG64(909))

    # Hill: 1 + Lomax(alpha) is Pareto-I with shape alpha; returns are -losses.
    losses = 1.0 + rng.pareto(2.5, size=40_000)
    assert SINGLE_FACTOR_STATS["hill_tail_index_5pct"].fn(-losses) == pytest.approx(2.5, rel=0.1)

    # acf_r_lag2 of an AR(1) is phi**2.
    phi = 0.6
    eps = rng.normal(0.0, 1.0, size=40_000)
    x = np.empty(eps.size)
    x[0] = eps[0]
    for i in range(1, eps.size):
        x[i] = phi * x[i - 1] + eps[i]
    assert SINGLE_FACTOR_STATS["acf_r_lag2"].fn(x) == pytest.approx(phi**2, abs=0.03)

    # agg_gaussianity: a normal sample's aggregates stay ~mesokurtic.
    normal_sample = rng.normal(size=40_000)
    assert SINGLE_FACTOR_STATS["agg_gaussianity_3m"].fn(normal_sample) == pytest.approx(
        0.0, abs=0.2
    )

    # leverage_correlation: ~0 for a symmetric iid series.
    assert SINGLE_FACTOR_STATS["leverage_correlation"].fn(normal_sample) == pytest.approx(
        0.0, abs=0.05
    )

    # acf_abs_decay recovers -ln(phi) on a series whose |deviation| is an AR(1).
    v = np.empty(20_000)
    v[0] = 5.0
    noise = rng.normal(0.0, 0.5, size=v.size)
    for i in range(1, v.size):
        v[i] = 5.0 + 0.9 * (v[i - 1] - 5.0) + noise[i]
    signed = v * np.where(np.arange(v.size) % 2 == 0, 1.0, -1.0)
    assert SINGLE_FACTOR_STATS["acf_abs_decay"].fn(signed) == pytest.approx(
        -float(np.log(0.9)), abs=0.02
    )


def test_agg_gaussianity_is_nan_below_its_sample_floor() -> None:
    x = np.arange(60.0)
    # 60 monthly observations give 5 non-overlapping 12-month sums: far below the
    # floor at which a fourth-moment statistic carries information.
    assert np.isnan(reference_mod.agg_gaussianity(x, 12))
    assert not np.isnan(reference_mod.agg_gaussianity(x, 1))


def test_hill_tail_index_is_nan_for_an_all_positive_level_series() -> None:
    """A rate/spread/index level has no losses, so its Hill tail index is NaN by
    construction rather than a number computed from the wrong side."""
    assert np.isnan(SINGLE_FACTOR_STATS["hill_tail_index_5pct"].fn(np.linspace(1.0, 9.0, 500)))


# --------------------------------------------------------------------------- #
# 13. the decade-frequency statistics get a USABLE band (WP2.2 Task 3 fix pass 1)
# --------------------------------------------------------------------------- #


def _returns_frame(seed: int, start: str, end: str, *, drift: float, sd: float) -> pd.DataFrame:
    """Deterministic iid monthly returns: low drift, equity-like volatility.

    Low enough drift that a 10-year compounded return is genuinely a coin flip -- the
    regime in which a lost-decade frequency band is most informative, and the one that
    makes this test a statement about the estimator rather than about the fixture.
    """
    dates = pd.date_range(start, end, freq="MS")
    rng = np.random.Generator(np.random.PCG64(seed))
    return pd.DataFrame({"date": dates, "value": rng.normal(drift, sd, size=len(dates))})


def _cpi_level_frame(start: str, end: str, *, era_months: int) -> pd.DataFrame:
    """A CPI index level alternating between ~7.4%/yr and ~1.9%/yr eras.

    Deterministic (no RNG at all). Alternating eras mean some decade windows contain a
    sustained high-inflation run and some do not, so the historical frequency is a
    genuine interior fraction rather than a saturated 0 or 1.
    """
    dates = pd.date_range(start, end, freq="MS")
    hot = (np.arange(len(dates)) // era_months) % 2 == 0
    rates = np.where(hot, 0.006, 0.0016)
    level = 100.0 * np.cumprod(1.0 + rates)
    return pd.DataFrame({"date": dates, "value": level})


def _frequency_reference() -> reference_mod.ReferenceStats:
    """``compute_reference`` at PRODUCTION settings (length-matched to a 120-month
    ensemble) over a century of returns and a century of CPI levels."""
    manifest = FactorManifest(
        blocks={"global": ("g1",), "us": ("u1",)},
        active_blocks=("global", "us"),
        sources={
            "g1": FactorSource(kind="series", series_id="g1", units="ret"),
            "u1": FactorSource(kind="series", series_id="u1", units="index"),
        },
    )
    frames = {
        "g1": _returns_frame(11, "1900-01-01", "2026-06-01", drift=0.0015, sd=0.05),
        "u1": _cpi_level_frame("1900-01-01", "2026-06-01", era_months=72),
    }

    def reader(series_id: str) -> pd.DataFrame:
        return frames[series_id]

    return compute_reference(
        DataAccess(reader),
        manifest,
        vintage_id="v",
        seed=17,
        n_resamples=300,
        block_length=reference_mod.DEFAULT_BLOCK_LENGTH,
        resample_length=120,
    )


def test_decade_frequency_bands_are_non_degenerate() -> None:
    """CRITICAL 1. Both frequency statistics used to be a single 0/1 indicator over the
    whole input, so every bootstrap replicate returned 0.0 or 1.0 and the percentile
    band could only ever be [0, 1] (admits every possible ensemble value) or [0, 0] /
    [1, 1] (fails every generator with a non-zero rate). With internal decade windowing
    the point estimate is a real fraction and the band is a real interval."""
    ref = _frequency_reference()
    lost = ref.blocks["global"].stats["g1.lost_decade_frequency"]
    era = ref.blocks["us"].stats["u1.long_inflation_era_frequency"]
    for name, band in (("lost_decade_frequency", lost), ("long_inflation_era_frequency", era)):
        assert 0.0 < band.point < 1.0, f"{name} point: {band}"
        assert band.lo < band.hi, f"{name} band is degenerate: {band}"
        assert band.lo > 0.0, f"{name} lo is not strictly inside [0, 1]: {band}"
        assert band.hi < 1.0, f"{name} hi is not strictly inside [0, 1]: {band}"


def test_decade_frequency_bands_are_drawn_at_the_full_sample_length() -> None:
    """The length-matching CONSEQUENCE of the fix, made explicit rather than implied.

    A decade-frequency replicate must be long enough to contain many decade windows, so
    these two statistics are drawn at the full train+validation length while every
    length-sensitive per-path statistic stays matched to the ensemble's own 120-month
    path length. Both facts are recorded on the band itself, so the report says which
    each is."""
    ref = _frequency_reference()
    stats = ref.blocks["global"].stats
    assert stats["g1.lost_decade_frequency"].resample_length is None
    assert stats["g1.acf_r_lag1"].resample_length == 120
    assert stats["g1.variance_ratio_12m"].resample_length == 120


def test_tail_dependence_bands_are_drawn_at_the_full_sample_length() -> None:
    """IMPORTANT 3. ``TAIL_DEPENDENCE_MIN_TAIL_OBS = 10`` at a 5% tail fraction needs
    ``n >= 200``, but a length-matched replicate is drawn at the ensemble's own path
    length (120 at production settings), so EVERY replicate returned NaN and the band
    was ``(nan, nan)`` with ``n_valid_resamples = 0`` -- an empty band on a registered,
    sealable statistic whose "real historical band for free" was the stated reason for
    registering it here at all. ``RegisteredCrossStat`` now carries the same
    ``length_matched`` flag ``RegisteredStat`` does, and these two are the entries that
    set it False."""
    ref = _frequency_reference()
    stats = ref.cross_blocks[("global", "us")].stats
    for stat in ("tail_dependence_lower", "tail_dependence_upper"):
        band = stats[f"g1~u1.{stat}"]
        assert band.resample_length is None, stat
        assert band.n_valid_resamples == band.n_resamples, stat
        assert np.isfinite(band.lo) and np.isfinite(band.hi), (stat, band)
    # The length-sensitive cross-block statistics stay matched -- the assertion is over
    # the split, so a future statistic silently opting out fails this test.
    assert stats["g1~u1.correlation"].resample_length == 120
    assert stats["g1~u1.crisis_corr_lift"].resample_length == 120


def test_band_records_how_many_resamples_were_valid() -> None:
    """RFR-19 stays deferred, but its degeneracy must be VISIBLE in the artifact: a
    single NaN among the resamples destroys both bounds today, and without this field
    that is indistinguishable from a statistic that is simply undefined."""
    ref = _frequency_reference()
    band = ref.blocks["global"].stats["g1.acf_r_lag1"]
    assert band.n_valid_resamples == band.n_resamples
    nan_band = ref.blocks["global"].stats["g1.ergodicity_gap"]
    assert nan_band.n_valid_resamples == 0
