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
from ah.eval import reference as reference_mod
from ah.eval.reference import (
    CROSS_BLOCK_STATS,
    SINGLE_FACTOR_STATS,
    ReferenceComputationError,
    RegisteredCrossStat,
    RegisteredStat,
    _draw_moving_block_indices,
    block_bootstrap_band,
    compute_reference,
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
    """A fast two-block, four-factor manifest for tests that don't need the real one."""
    return FactorManifest(
        blocks={"global": ("g1", "g2"), "us": ("u1", "u2")},
        active_blocks=("global", "us"),
        sources={
            name: FactorSource(kind="unavailable", reason="fixture")
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

    real_read_train_val = reference_mod._read_train_val

    def leaky_read_train_val(
        access_arg: DataAccess, factor: str, series_id_for
    ) -> pd.Series | None:
        # The exact mutation quoted in the review, applied alongside the real read.
        token = ah.splits.FinalEvaluationToken(purpose="x")
        access_arg.frame(series_id_for(factor), "holdout", token=token)
        return real_read_train_val(access_arg, factor, series_id_for)

    monkeypatch.setattr(reference_mod, "_read_train_val", leaky_read_train_val)

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
    assert ref_a == ref_b


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
    assert SINGLE_FACTOR_STATS["acf_abs_1"].fn(x) == pytest.approx(0.25, abs=1e-9)


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
