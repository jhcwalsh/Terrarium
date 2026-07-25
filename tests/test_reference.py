"""WP2.1b Task 3 acceptance: block-aware reference statistics and bootstrap bands.

``ah.eval.reference`` computes every reference statistic on train+validation only
(``ah.splits.DataAccess.train_val`` is the only sanctioned surface); the holdout must
never be reachable from it. Test 1 (leakage) and test 12 (inactive-block exclusion)
are the two that matter most per ``Instructions/WP2.1b-PRE-SEAL-PATCH.md`` Item 2 and
the WP2.1b Task 3 brief -- both are written as direct proofs against a recording
reader, not as trust in ``active_factors()``/``train_val()`` being called correctly.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ah.eval.reference import (
    CROSS_BLOCK_STATS,
    SINGLE_FACTOR_STATS,
    compute_reference,
)
from ah.factors import FactorManifest, load_manifest
from ah.splits import HOLDOUT, DataAccess, Reader

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


class _RecordingAccess(DataAccess):
    """Records every date and series id that reaches ``compute_reference`` via ``train_val``."""

    def __init__(self, reader: Reader) -> None:
        super().__init__(reader)
        self.dates_returned: list[pd.Timestamp] = []
        self.series_requested: list[str] = []

    def train_val(self, series_id: str) -> pd.DataFrame:
        self.series_requested.append(series_id)
        df = super().train_val(series_id)
        self.dates_returned.extend(df["date"].tolist())
        return df


def _small_manifest() -> FactorManifest:
    """A fast two-block, four-factor manifest for tests that don't need the real one."""
    return FactorManifest(
        blocks={"global": ("g1", "g2"), "us": ("u1", "u2")},
        active_blocks=("global", "us"),
    )


# --------------------------------------------------------------------------- #
# 1. leakage: the critical test
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

    assert ref_a.blocks == ref_b.blocks
    assert ref_a.cross_blocks == ref_b.cross_blocks


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

    estimate = SINGLE_FACTOR_STATS["acf_1"].fn(x)
    # SE(phi_hat) ~ sqrt((1-phi^2)/n) ~ 0.0057 at n=20000, phi=0.6; 0.03 is > 5x that.
    assert estimate == pytest.approx(phi, abs=0.03)


def test_excess_kurtosis_normal_near_zero_student_t_clearly_positive() -> None:
    rng = np.random.Generator(np.random.PCG64(7))
    normal_sample = rng.normal(0.0, 1.0, size=200_000)
    t_sample = rng.standard_t(5, size=200_000)  # excess kurtosis = 6/(5-4) = 6.0

    k_normal = SINGLE_FACTOR_STATS["excess_kurtosis"].fn(normal_sample)
    k_t = SINGLE_FACTOR_STATS["excess_kurtosis"].fn(t_sample)

    assert abs(k_normal) < 0.1
    assert k_t > 1.0


# --------------------------------------------------------------------------- #
# 8. band brackets its point estimate
# --------------------------------------------------------------------------- #


def test_band_brackets_point_estimate_for_every_stat() -> None:
    manifest = _small_manifest()
    seeds = {"g1": 1, "g2": 2, "u1": 3, "u2": 4}
    access = DataAccess(_make_reader(seeds, start="1950-01-01", end="2026-06-01"))

    ref = compute_reference(
        access, manifest, vintage_id="v", seed=5, n_resamples=200, block_length=24
    )

    checked = 0
    for block_ref in ref.blocks.values():
        for name, band in block_ref.stats.items():
            assert band.lo <= band.point <= band.hi, f"{name}: {band}"
            checked += 1
    for pair_ref in ref.cross_blocks.values():
        for name, band in pair_ref.stats.items():
            assert band.lo <= band.point <= band.hi, f"{name}: {band}"
            checked += 1
    assert checked == len(SINGLE_FACTOR_STATS) * 4 + len(CROSS_BLOCK_STATS) * 4


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
    assert set(sample_band) == {"point", "lo", "hi", "n_resamples", "level", "tier"}


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
    # must never appear is an actual code reference -- an import or a name use.
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
    assert not imported and not referenced, (
        "reference.py must never reference FinalEvaluationToken in code -- it never "
        f"accepts one (imports={imported}, name-refs={referenced})"
    )


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
