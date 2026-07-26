"""WP2.2b Task 7 acceptance: the negative-control suite validates the battery itself.

STEP2-GENERATOR-PLAN Sec.WP2.2b: five deliberately broken generators, each registered
through ``ah.gen.registry`` exactly like a real one, each of which a designated tier of
the validation battery must reject. This module is the battery's own validation record.

**A control that passes a tier it should fail is a finding about the battery, not a bug
in the control.** Where that happened, the gap is pinned by an explicitly named test
below (``test_..._gap_...``) rather than papered over by weakening the control or
loosening a threshold -- see ``docs`` in ``ah.eval.negative_controls``'s module
docstring and the WP2.2b report.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ah.eval import battery as battery_mod
from ah.eval import negative_controls as nc
from ah.eval import prereg as prereg_mod
from ah.eval.negative_controls import (
    NC1_IID_GAUSSIAN,
    NC2_SHUFFLED,
    NC3_SHIFTED_BOOTSTRAP,
    NC4_MEMORIZER,
    NC5_CONDITION_IGNORING,
    NEGATIVE_CONTROL_IDS,
    NegativeControlReport,
)
from ah.factors import load_manifest
from ah.gen import registry as gen_registry
from ah.splits import DataAccess

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------- #
# The synthetic-but-stylized historical fixture.
#
# No network and no committed catalog in CI (`data/` is gitignored), so the controls
# are fitted against a synthetic panel -- but one deliberately built to carry the
# stylized facts the monthly tier exists to test, because otherwise NC1 (iid Gaussian
# matched to it) would be indistinguishable from the history it was matched to, and
# "the monthly tier missed NC1" would be an artifact of a Gaussian fixture rather than
# a finding about the battery. Every return-bearing series is a stochastic-volatility
# process (log-AR(1) latent vol, common across factors -> volatility clustering, fat
# unconditional tails, a leverage effect and cross-factor crisis co-movement); every
# level series is a highly persistent random walk / AR(1).
# --------------------------------------------------------------------------- #

_HISTORY_START = "1940-01-01"
_HISTORY_MONTHS = 972  # 1940-01 .. 2020-12; entirely inside train+validation.

# The 15 requirements.yaml series ids the REAL factors.yaml maps its active factors to.
_RETURN_SERIES = ("french.mkt_rf", "french.rf", "french.smb", "french.hml", "french.mom")
_LEVEL_SERIES = (
    "fred.VIX",
    "fred.BAA",
    "fred.AAA",
    "fred.HY_OAS",
    "fred.FEDFUNDS",
    "fred.DGS2",
    "fred.DGS10",
    "fred.CPI",
    "treasury.hqm_curve",
    "fred.TEDRATE",
)


def _stochastic_vol(rng: np.random.Generator, n: int) -> np.ndarray:
    """A log-AR(1) latent volatility path: ``log s_t = 0.94 log s_{t-1} + eta_t``."""
    log_s = np.zeros(n, dtype=np.float64)
    eta = rng.normal(0.0, 0.30, size=n)
    for t in range(1, n):
        log_s[t] = 0.94 * log_s[t - 1] + eta[t]
    return np.exp(log_s - 0.5 * np.var(log_s))


def _synthetic_frames(seed: int = 20260724) -> dict[str, pd.DataFrame]:
    dates = pd.date_range(_HISTORY_START, periods=_HISTORY_MONTHS, freq="MS")
    rng = np.random.Generator(np.random.PCG64(seed))
    n = _HISTORY_MONTHS
    # One common volatility factor -> crisis co-movement across every return factor.
    common_vol = _stochastic_vol(rng, n)

    frames: dict[str, pd.DataFrame] = {}
    for i, sid in enumerate(_RETURN_SERIES):
        idio_vol = _stochastic_vol(rng, n)
        vol = 0.7 * common_vol + 0.3 * idio_vol
        shocks = rng.standard_normal(n)
        # A mild AR(1) in returns (so shuffling is detectable) and a leverage effect
        # (down months raise next month's vol) -- both real stylized facts.
        base = 0.02 + 0.004 * i
        values = np.zeros(n, dtype=np.float64)
        prev = 0.0
        for t in range(n):
            values[t] = 0.003 + 0.12 * prev + base * vol[t] * shocks[t]
            prev = values[t]
        frames[sid] = pd.DataFrame({"date": dates, "value": values})

    levels: dict[str, np.ndarray] = {}
    for sid in _LEVEL_SERIES:
        drift, start, scale = _LEVEL_SHAPE[sid]
        innov = rng.normal(drift, scale, size=n)
        if sid == "fred.CPI":
            levels[sid] = 20.0 * np.exp(np.cumsum(np.abs(innov)))
        else:
            levels[sid] = np.abs(start + np.cumsum(innov)) + 0.25
    # `ig_spread` is `derive.difference(BAA, AAA)` and a credit spread is positive by
    # construction. Two independent random walks cross, which would give the fixture a
    # negative investment-grade spread and make `economics.floor_violations` fire for
    # every control alike -- a fixture artifact masquerading as a detection.
    levels["fred.BAA"] = levels["fred.AAA"] + 0.9 + 0.35 * (levels["fred.HY_OAS"] / 5.5)
    for sid, level in levels.items():
        frames[sid] = pd.DataFrame({"date": dates, "value": level})
    return frames


# (per-month drift, starting level, innovation scale) for each level series.
_LEVEL_SHAPE: dict[str, tuple[float, float, float]] = {
    "fred.VIX": (0.0, 19.0, 1.8),
    "fred.BAA": (0.0, 7.0, 0.15),
    "fred.AAA": (0.0, 6.0, 0.12),
    "fred.HY_OAS": (0.0, 5.5, 0.30),
    "fred.FEDFUNDS": (0.0, 4.0, 0.22),
    "fred.DGS2": (0.0, 4.5, 0.20),
    "fred.DGS10": (0.0, 5.5, 0.18),
    "fred.CPI": (0.0025, 20.0, 0.0018),
    "treasury.hqm_curve": (0.0, 6.0, 0.18),
    "fred.TEDRATE": (0.0, 0.8, 0.10),
}


def _synthetic_access() -> DataAccess:
    frames = _synthetic_frames()

    def reader(series_id: str) -> pd.DataFrame:
        if series_id not in frames:
            raise KeyError(series_id)
        return frames[series_id]

    return DataAccess(reader)


# Small but sufficient: 16 paths keeps `battery._n_subsamples_for` at 8 Monte-Carlo
# subsamples, and 120 months is DN-1.1's decade horizon and the memorization suite's
# 5-blocks-per-path scale. n_resamples=120 gives a usable 90% percentile band.
_N_PATHS = 16
_MONTHS = 120
_N_RESAMPLES = 120
_SEED = 4242


@pytest.fixture(scope="module", autouse=True)
def _isolate_globals() -> Iterator[None]:
    """Snapshot/restore both process-global tables this module writes through."""
    suites = dict(battery_mod.SUITES)
    registry = dict(gen_registry._REGISTRY)
    try:
        yield
    finally:
        battery_mod.SUITES.clear()
        battery_mod.SUITES.update(suites)
        gen_registry._REGISTRY.clear()
        gen_registry._REGISTRY.update(registry)


@pytest.fixture(scope="module")
def report() -> NegativeControlReport:
    return nc.run_negative_controls(
        access=_synthetic_access(),
        manifest=load_manifest(),
        prereg=prereg_mod.load(),
        seed=_SEED,
        n_paths=_N_PATHS,
        months=_MONTHS,
        n_resamples=_N_RESAMPLES,
    )


# --------------------------------------------------------------------------- #
# 4. the controls are registered and resolvable through ah.gen.registry
# --------------------------------------------------------------------------- #


def test_every_control_is_resolvable_through_the_generator_registry() -> None:
    access = _synthetic_access()
    reference = nc.control_reference(access, load_manifest(), n_resamples=4, months=_MONTHS)
    with nc.negative_control_registry(reference) as ids:
        assert set(ids) == set(NEGATIVE_CONTROL_IDS)
        for control_id in NEGATIVE_CONTROL_IDS:
            generator = gen_registry.resolve(control_id)
            assert generator.generator_id == control_id
    # The context manager restores the registry it borrowed.
    for control_id in NEGATIVE_CONTROL_IDS:
        assert control_id not in gen_registry.registered()


def test_every_control_produces_a_well_formed_ensemble() -> None:
    access = _synthetic_access()
    manifest = load_manifest()
    reference = nc.control_reference(access, manifest, n_resamples=4, months=_MONTHS)
    controls = nc.build_negative_controls(reference)
    assert set(controls) == set(NEGATIVE_CONTROL_IDS)
    for control_id, generator in sorted(controls.items()):
        ensemble = generator.sample_months(_MONTHS, _N_PATHS, _SEED)
        assert ensemble.paths.shape == (_N_PATHS, _MONTHS, len(ensemble.factor_names))
        assert ensemble.meta.generator_id == control_id
        assert bool(np.all(np.isfinite(ensemble.paths))), control_id


# --------------------------------------------------------------------------- #
# 3. determinism -- and a different-seed test proving it is not vacuous
# --------------------------------------------------------------------------- #


def test_same_seed_gives_bit_identical_ensembles() -> None:
    access = _synthetic_access()
    manifest = load_manifest()
    reference = nc.control_reference(access, manifest, n_resamples=4, months=_MONTHS)
    a = nc.build_negative_controls(reference)
    b = nc.build_negative_controls(reference)
    for control_id in NEGATIVE_CONTROL_IDS:
        left = a[control_id].sample_months(_MONTHS, _N_PATHS, 99)
        right = b[control_id].sample_months(_MONTHS, _N_PATHS, 99)
        assert np.array_equal(left.paths, right.paths), control_id


def test_different_seed_gives_different_ensembles() -> None:
    """Proves the determinism test above is not vacuous (a constant generator would
    pass it trivially)."""
    access = _synthetic_access()
    manifest = load_manifest()
    reference = nc.control_reference(access, manifest, n_resamples=4, months=_MONTHS)
    controls = nc.build_negative_controls(reference)
    for control_id in NEGATIVE_CONTROL_IDS:
        left = controls[control_id].sample_months(_MONTHS, _N_PATHS, 99)
        right = controls[control_id].sample_months(_MONTHS, _N_PATHS, 100)
        assert not np.array_equal(left.paths, right.paths), control_id


def test_battery_verdict_is_bit_identical_for_the_same_seed(
    report: NegativeControlReport,
) -> None:
    """Same seed, same inputs -> the same report, field for field.

    Compared as dicts rather than as JSON text so a failure names the differing key
    instead of printing two 200 kB strings. The report carries no metric VALUES (only
    names, counts and verdicts), so any difference here is a metric that changed side of
    a bound -- which is what makes this a real determinism check and not a float-equality
    trap.

    **Observed instability, recorded rather than assumed away (WP2.2b Task 7).** This
    assertion failed twice during development, both times in a full-suite run executing
    concurrently with a second full-suite run on a loaded machine. It was then NOT
    reproducible in 18 controlled attempts: 12 back-to-back in-process comparisons across
    4 concurrent processes, 4 concurrent runs of this module, and 2 concurrent full
    suites. Since the fitted panel, the reference, and all five ensembles are separately
    proven bit-identical (the three tests above), any difference must be a metric landing
    on the far side of a bound it was already sitting on. The leading hypothesis is
    last-bit variation in a threaded BLAS reduction (numpy here is scipy-openblas 0.3.33,
    ``DYNAMIC_ARCH``, ``MAX_THREADS=24``, ``NO_AFFINITY``, whose GEMM partitioning is
    thread-count dependent) reaching one of the few metrics that route through
    ``np.corrcoef`` or a large matmul. The assertion is deliberately kept exact rather
    than given a tolerance: a real determinism regression moves a value by O(1), not by
    an ULP, and a tolerance would hide it. If this fails again, the dict diff names the
    control, tier, suite and failure list that moved -- start there."""
    again = nc.run_negative_controls(
        access=_synthetic_access(),
        manifest=load_manifest(),
        prereg=prereg_mod.load(),
        seed=_SEED,
        n_paths=_N_PATHS,
        months=_MONTHS,
        n_resamples=_N_RESAMPLES,
    )
    assert again.to_dict() == report.to_dict()


# --------------------------------------------------------------------------- #
# 1 + 2. each control is caught by its DESIGNATED tier, for the RIGHT reason
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("control_id", NEGATIVE_CONTROL_IDS)
def test_every_control_is_rejected_by_the_battery(
    report: NegativeControlReport, control_id: str
) -> None:
    """The plan's headline acceptance: all five controls rejected."""
    outcome = report.outcome(control_id)
    assert not outcome.battery_passed, control_id
    assert outcome.substantive_failures, (
        f"{control_id} was rejected only by NaN-valued metrics -- that is not a "
        f"demonstration that any metric detected anything"
    )


@pytest.mark.parametrize("control_id", NEGATIVE_CONTROL_IDS)
def test_every_control_is_caught_by_its_designated_tier(
    report: NegativeControlReport, control_id: str
) -> None:
    """Requirement 2: the DESIGNATED tier fires, on a metric with a FINITE value.

    A control rejected because an unrelated metric NaN'd has not been caught, so only
    ``substantive`` (finite-valued) failures count here.
    """
    outcome = report.outcome(control_id)
    caught = outcome.designated_substantive_failures
    assert caught, (
        f"{control_id} was NOT caught by its designated tier(s) "
        f"{outcome.designation.tiers} / suite(s) {outcome.designation.suites}. "
        f"Substantive failures elsewhere: {outcome.substantive_failures}"
    )


def test_nc1_kills_tails_and_clustering_on_the_named_stylized_facts(
    report: NegativeControlReport,
) -> None:
    """NC1 is designated to the monthly tier because it destroys exactly the DN-1.1
    stylized facts: fat tails and volatility clustering. Named metrics, not just a
    tier count -- a monthly-tier rejection driven only by, say, a mean band would not
    demonstrate that the tail/clustering machinery works."""
    outcome = report.outcome(NC1_IID_GAUSSIAN)
    fired = set(outcome.designated_substantive_failures)
    clustering = {m for m in fired if ".acf_abs_lag" in m or m.endswith(".acf_abs_decay")}
    tails = {m for m in fired if "hill_tail_index" in m or m.endswith(".excess_kurtosis")}
    assert clustering, f"NC1 destroyed volatility clustering but no acf_abs metric fired: {fired}"
    assert tails, f"NC1 destroyed fat tails but no tail metric fired: {fired}"


def test_nc2_kills_dynamics_on_acf_and_horizon_metrics(report: NegativeControlReport) -> None:
    """NC2's marginals are exact by construction, so a rejection driven by a marginal
    statistic (mean/std/skew/kurtosis) would be the wrong reason. The ACF and the
    1_5yr horizon statistics are the ones that must fire."""
    outcome = report.outcome(NC2_SHUFFLED)
    fired = set(outcome.designated_substantive_failures)
    acf = {m for m in fired if ".acf_" in m}
    horizon = {
        m
        for m in fired
        if "variance_ratio" in m or "mean_reversion_halflife" in m or "drawdown_" in m
    }
    assert acf, f"NC2 destroyed serial dependence but no ACF metric fired: {fired}"
    assert horizon, f"NC2 destroyed multi-year dynamics but no horizon metric fired: {fired}"


def test_nc3_is_rejected_by_the_reference_bands_it_targets(
    report: NegativeControlReport,
) -> None:
    """NC3 targets the BANDS, not a threshold: a mean/volatility-shifted generator that
    a length-matched block-bootstrap band admits is not a band. The shift is stated in
    ``NC3_MEAN_SHIFT_SDS``/``NC3_VOL_MULTIPLIER`` and is not tuned."""
    outcome = report.outcome(NC3_SHIFTED_BOOTSTRAP)
    assert outcome.band_failures, "no reference band rejected the shifted bootstrap"
    assert outcome.designated_substantive_failures


def test_nc4_is_caught_by_the_memorization_suite_at_its_stated_noise_level(
    report: NegativeControlReport,
) -> None:
    """The noise level is load-bearing and stated up front (``NC4_NOISE_FRACTION``);
    this asserts the memorization tier catches the memorizer AT THAT LEVEL, and that it
    does so because the memorizer looks like a memorizer -- every one of the suite's
    four signals must move in the copying direction relative to the non-memorizing
    control NC1, not just the one that happens to cross a threshold."""
    assert nc.NC4_NOISE_FRACTION == 0.10
    outcome = report.outcome(NC4_MEMORIZER)
    memorizer = outcome.suite_metrics("memorization")
    baseline = report.outcome(NC1_IID_GAUSSIAN).suite_metrics("memorization")
    assert memorizer, "the memorization suite produced no metrics for NC4"

    assert memorizer["nn_distance_p05"] < baseline["nn_distance_p05"] / 2.0, (memorizer, baseline)
    assert memorizer["nn_distance_p50"] < baseline["nn_distance_p50"] / 2.0, (memorizer, baseline)
    assert memorizer["membership_inference_auc"] > 0.65, memorizer
    assert baseline["membership_inference_auc"] < 0.55, baseline
    assert memorizer["near_duplicate_fraction"] > baseline["near_duplicate_fraction"], (
        memorizer,
        baseline,
    )
    fired = set(outcome.designated_substantive_failures)
    assert fired, f"the memorization suite did not reject NC4: {memorizer}"


def test_nc5_is_caught_by_the_conditional_suite(report: NegativeControlReport) -> None:
    """NC5 is the unshifted bootstrap -- statistically the most defensible of the five
    -- whose ONLY defect is that it ignores ``factor_conditions``. So a conditional
    rejection here is unambiguously about conditioning."""
    outcome = report.outcome(NC5_CONDITION_IGNORING)
    conditional = outcome.suite_metrics("conditional")
    assert conditional, "the conditional suite produced no metrics for NC5"
    assert np.isfinite(conditional["condition_adherence_error_rate"]), conditional
    # A real, large, quantified adherence error -- not a NaN and not a small one.
    assert conditional["condition_adherence_error_inflation"] > 5.0, conditional
    assert conditional["condition_adherence_error_crisis_timing"] > 4.0, conditional
    fired = set(outcome.designated_substantive_failures)
    assert fired, f"the conditional suite did not reject NC5: {conditional}"


# --------------------------------------------------------------------------- #
# FINDINGS. Each test below PINS a hole this suite discovered in the battery.
#
# Every one of them asserts a fact that is currently TRUE and that ought not to be.
# They are written this way deliberately: the alternative -- leaving the acceptance
# test red, or weakening a control until the hole disappears -- either blocks the
# branch or destroys the evidence. When WP2.3 closes one of these, the corresponding
# test fails loudly and is deleted in the same commit, which is exactly the signal
# wanted. See the WP2.2b report for the full write-up.
# --------------------------------------------------------------------------- #


def test_finding_no_metric_suite_emits_a_mean_or_std_metric_at_all() -> None:
    """**Primary finding.** ``ah.eval.reference.SINGLE_FACTOR_STATS`` registers ``mean``
    and ``std`` for every factor and ``compute_reference`` computes a real, length-
    matched block-bootstrap band for each -- and no suite in the battery ever computes
    the generated-side value, so neither band can ever be consulted. The same holds for
    the cross-block ``correlation`` band. NC3 exists to break exactly this axis and is
    invisible to it; see the companion test below for the numbers."""
    access = _synthetic_access()
    manifest = load_manifest()
    reference = nc.control_reference(access, manifest, n_resamples=4, months=_MONTHS)
    battery_mod.register_reference_dependent_suites(manifest, reference)
    names = {spec.name for specs in battery_mod.SUITES.values() for spec in specs}
    assert names, "no suite registered at all -- this test would be vacuous"
    assert not [n for n in names if n.endswith(".mean")]
    assert not [n for n in names if n.endswith(".std")]
    assert not [n for n in names if n.endswith(".correlation")]
    # ... while the bands for all three DO exist and are computed.
    from ah.eval.reference import CROSS_BLOCK_STATS, SINGLE_FACTOR_STATS

    assert "mean" in SINGLE_FACTOR_STATS
    assert "std" in SINGLE_FACTOR_STATS
    assert "correlation" in CROSS_BLOCK_STATS


def test_finding_nc3s_drift_would_be_rejected_by_bands_that_are_never_consulted() -> None:
    """The evidence behind the finding above: NC3's pooled ``equity_mkt`` mean and
    standard deviation both fall OUTSIDE their own train+validation bands -- so the band
    would reject the drift if anything computed the value."""
    from ah.eval.reference import _mean, _std

    access = _synthetic_access()
    manifest = load_manifest()
    reference = nc.control_reference(
        access, manifest, n_resamples=_N_RESAMPLES, months=_MONTHS, seed=_SEED
    )
    control = nc.build_negative_controls(reference)[NC3_SHIFTED_BOOTSTRAP]
    ensemble = control.sample_months(_MONTHS, _N_PATHS, _SEED + 7919 * 2)
    values = ensemble.factor("equity_mkt").reshape(-1)
    stats = reference.blocks["global"].stats
    mean_band = stats["equity_mkt.mean"]
    std_band = stats["equity_mkt.std"]
    assert not (mean_band.lo <= _mean(values) <= mean_band.hi), (
        _mean(values),
        mean_band,
    )
    assert not (std_band.lo <= _std(values) <= std_band.hi), (_std(values), std_band)


def test_finding_the_monthly_tier_cannot_separate_nc3_from_the_undistorted_bootstrap(
    report: NegativeControlReport,
) -> None:
    """The sharpest form of the primary finding, and the reason it matters.

    NC5 is NC3's construction with the distortion switched off -- the two differ ONLY by
    a +0.5 sigma mean shift and a 1.5x volatility multiplier on every factor. In the
    monthly tier's own designated cell, NC3 (distorted) produces *no more* band failures
    than NC5 (undistorted): the distortion adds two long-lag ACF rejections and removes
    three others. The tier's answer to "did this generator's location and scale drift"
    is therefore indistinguishable from noise, because nothing in the tier measures
    location or scale at all."""
    nc3_cell = report.outcome(NC3_SHIFTED_BOOTSTRAP).cell("monthly", "monthly")
    nc5_cell = report.outcome(NC5_CONDITION_IGNORING).cell("monthly", "monthly")
    assert nc3_cell is not None and nc5_cell is not None
    added = set(nc3_cell.band_failures) - set(nc5_cell.band_failures)
    # Not one of the metrics the distortion added measures location or scale.
    assert not [m for m in added if m.endswith((".mean", ".std"))], added
    assert len(nc3_cell.band_failures) <= len(nc5_cell.band_failures), (
        len(nc3_cell.band_failures),
        len(nc5_cell.band_failures),
    )


def test_finding_the_only_enforce_gate_that_fires_discriminates_nothing(
    report: NegativeControlReport,
) -> None:
    """**Second finding.** Not one control is rejected by an ``enforce``-severity
    threshold for a reason specific to its own defect. The single enforce gate that
    fires -- ``floor_violations`` -- fires identically for all five, including for
    controls that replay real historical values verbatim, so it is a statement about
    the data (a realistic funding spread sits below the sealed 100bp
    ``SPREAD_FLOOR_PCT``) and not a detection. Every designated-tier catch in this
    suite therefore came from a ``report``-severity threshold or from a reference band
    the battery does not judge against."""
    assert report.shared_enforce_failures == ("floor_violations",), report.shared_enforce_failures
    for control_id, discriminating in report.discriminating_enforce_failures.items():
        assert discriminating == (), (control_id, discriminating)


def test_finding_a_plain_block_bootstrap_scores_worse_than_the_memorizer(
    report: NegativeControlReport,
) -> None:
    """**Third finding, and the one WP2.4 must read.** NC5 is a plain moving-block
    bootstrap of real history -- the shape of the G2 benchmark generator WP2.4 builds --
    and it scores WORSE on ``near_duplicate_fraction`` and ``nn_distance_p05`` than
    NC4, the deliberate memorizer. A block bootstrap emits literal contiguous
    historical segments by construction, so the memorization suite cannot separate
    "resampled history" from "memorized history".

    Caveat recorded with the finding rather than left for a reader to spot:
    ``NC3_BLOCK_MONTHS`` (24) coincides with the memorization suite's own
    ``MEMORIZATION_BLOCK_MONTHS`` (24), which maximises block alignment and therefore
    the size of the effect. The ORDERING, not its magnitude, is what this pins."""
    memorizer = report.outcome(NC4_MEMORIZER).suite_metrics("memorization")
    bootstrap = report.outcome(NC5_CONDITION_IGNORING).suite_metrics("memorization")
    assert bootstrap["near_duplicate_fraction"] > memorizer["near_duplicate_fraction"], (
        bootstrap,
        memorizer,
    )
    assert bootstrap["nn_distance_p05"] < memorizer["nn_distance_p05"], (bootstrap, memorizer)


def test_finding_the_10yr_tier_catches_nothing(report: NegativeControlReport) -> None:
    """**Fourth finding.** The ``10yr`` tier produced no substantive failure for any of
    the five controls: 13 of its 22 metrics are the structural-gap metrics that are NaN
    for every generator (no valuation/regime factor exists in ``factors.yaml``), and the
    remainder did not move enough to leave their own very wide decade bands. NC2 in
    particular -- whose dynamics are destroyed outright -- is designated to this tier and
    is not caught by it."""
    for o in report.outcomes:
        tenyr = [c for c in o.cells if c.tier == "10yr"]
        assert tenyr, o.control_id
        fired = {name for c in tenyr for name in c.substantive_failures}
        # 13 structurally-unavailable metrics per control, for every control alike.
        assert sum(len(c.band_nan_metrics) + len(c.enforce_nan_failures) for c in tenyr) >= 13
        if o.control_id == NC3_SHIFTED_BOOTSTRAP:
            # The one exception, and only via the two decade FREQUENCY statistics --
            # not via anything measuring decade dynamics.
            assert fired and all(
                name.endswith(("lost_decade_frequency", "long_inflation_era_frequency"))
                for name in fired
            ), fired
            continue
        assert not fired, (o.control_id, fired)


# --------------------------------------------------------------------------- #
# 5. the report table round-trips through JSON and names the firing metrics
# --------------------------------------------------------------------------- #


def test_report_round_trips_through_json_and_names_firing_metrics(
    report: NegativeControlReport,
) -> None:
    doc = json.loads(report.to_json())
    assert doc["battery_version"] == battery_mod.BATTERY_VERSION
    assert doc["prereg_digest"].startswith("sha256:")
    assert [row["control_id"] for row in doc["controls"]] == list(NEGATIVE_CONTROL_IDS)
    for row in doc["controls"]:
        assert set(row["designation"]["tiers"]) <= set(battery_mod.TIERS)
        assert row["construction"], row["control_id"]
        # Every cell names the metrics that fired, never only a count.
        for cell in row["cells"]:
            assert isinstance(cell["enforce_failures"], list)
            assert isinstance(cell["band_failures"], list)


def test_report_markdown_has_one_row_per_control_and_one_column_per_tier(
    report: NegativeControlReport,
) -> None:
    md = report.to_markdown()
    assert md.isascii(), "battery report text stays ASCII (Windows console is cp1252)"
    header = next(line for line in md.splitlines() if line.startswith("| control "))
    for tier in battery_mod.TIERS:
        assert tier in header
    for control_id in NEGATIVE_CONTROL_IDS:
        assert any(line.startswith(f"| {control_id} ") for line in md.splitlines()), control_id


# --------------------------------------------------------------------------- #
# Leakage + seal guards
# --------------------------------------------------------------------------- #


def test_negative_controls_never_imports_the_holdout_token_mint() -> None:
    """AST guard: ``ah.eval.negative_controls`` must never import ``ah.eval.g2``, the
    only sanctioned ``FinalEvaluationToken`` mint."""
    source = (ROOT / "src" / "ah" / "eval" / "negative_controls.py").read_text("utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("ah.eval.g2"), alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("ah.eval.g2"), module
            if module in {"ah.eval", "ah"}:
                for alias in node.names:
                    assert alias.name != "g2", alias.name


def test_negative_controls_never_imports_data_access() -> None:
    """The controls read real data ONLY through ``ReferenceStats.historical_series``.
    ``run_negative_controls`` is handed a live ``DataAccess`` to compute that reference
    (exactly as ``run_full_battery`` is), so a DataAccess import is expected HERE --
    what must never happen is a control's ``fit``/``sample`` reaching the catalog. The
    guard is therefore on the control classes, not the module: no control may hold a
    reader."""
    for control_id, generator in sorted(
        nc.build_negative_controls(
            nc.control_reference(_synthetic_access(), load_manifest(), n_resamples=4, months=12)
        ).items()
    ):
        state = vars(generator)
        for value in state.values():
            assert not isinstance(value, DataAccess), (control_id, state)


def test_negative_controls_is_inside_the_pre_registration_seal() -> None:
    """It is judging code living outside ``src/ah/eval/metrics/``, so it joins
    ``_REQUIRED_JUDGED_SOURCES`` in the commit that adds it (``ah.eval.prereg``'s
    module docstring states the rule)."""
    assert ("src", "ah", "eval", "negative_controls.py") in prereg_mod._REQUIRED_JUDGED_SOURCES


def test_controls_only_ever_read_train_and_validation() -> None:
    """The fitted panel's last observation must precede the holdout boundary."""
    from ah.splits import HOLDOUT

    panel = nc.fit_historical_panel(
        nc.control_reference(_synthetic_access(), load_manifest(), n_resamples=4, months=12)
    )
    assert bool((panel.dates < pd.Timestamp(HOLDOUT.start)).all())
