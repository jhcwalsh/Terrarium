"""WP2.4 acceptance: `bootstrap-v1`, the sealed benchmark generator.

Every test here checks the implementation against ``pre-registration.yaml``'s sealed
``bootstrap_v1`` block, never against a number restated in the test. The sealed document
is the specification; this file is the machine check that the code implements it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.data.derive import regime_thresholds
from ah.factors import load_manifest
from ah.gen import bootstrap as bs
from ah.gen import registry
from ah.gen.base import Generator
from ah.splits import DataAccess

ROOT = Path(__file__).resolve().parents[1]
GEN_DIR = ROOT / "src" / "ah" / "gen"

_SEALED: dict[str, Any] = yaml.safe_load((ROOT / "pre-registration.yaml").read_text("utf-8"))
_BOOTSTRAP: dict[str, Any] = _SEALED["bootstrap_v1"]


# --------------------------------------------------------------------------- #
# a synthetic source -- no catalog, no network
# --------------------------------------------------------------------------- #


def _synthetic_source(
    n_rows: int = 60,
    factor_names: tuple[str, ...] = ("a", "b", "c"),
    labels: tuple[str, ...] | None = None,
) -> bs.BootstrapSource:
    """A source whose every column is an injective function of the row index.

    ``values[i, j] = i + 1000*j`` -- so a single emitted cell identifies the source row
    it came from unambiguously, which is what makes the multivariate-block test exact
    rather than statistical.
    """
    dates = pd.DatetimeIndex(pd.date_range("1990-01-01", periods=n_rows, freq="MS"))
    values = np.arange(n_rows, dtype=np.float64)[:, None] + 1000.0 * np.arange(
        len(factor_names), dtype=np.float64
    )
    if labels is None:
        # a deterministic, uneven spread over the six ruleset labels
        cycle = ("EXP", "EXP", "EXP", "SLOW", "REC", "CRI", "STAG", "REF")
        labels = tuple(cycle[i % len(cycle)] for i in range(n_rows))
    return bs.BootstrapSource(
        factor_names=factor_names,
        dates=dates,
        values=values,
        labels=tuple(labels),
        ruleset_version="regime_ruleset_v1",
        vintage_id="test-vintage",
        active_blocks=("global", "us"),
    )


def _row_indices(paths: np.ndarray) -> np.ndarray:
    """Recover the source row index behind every emitted cell of a synthetic ensemble."""
    return paths[:, :, 0].astype(np.int64)


# --------------------------------------------------------------------------- #
# 1. the sealed spec is implemented verbatim
# --------------------------------------------------------------------------- #


def test_module_constants_equal_the_sealed_bootstrap_v1_block() -> None:
    assert _BOOTSTRAP["generator_id"] == bs.GENERATOR_ID
    assert _BOOTSTRAP["form"] == bs.FORM
    assert _BOOTSTRAP["block_length_distribution"] == bs.BLOCK_LENGTH_DISTRIBUTION
    assert _BOOTSTRAP["mean_block_months"] == bs.MEAN_BLOCK_MONTHS
    assert tuple(_BOOTSTRAP["factor_set"]) == bs.FACTOR_SET
    assert _BOOTSTRAP["stratification"] == bs.STRATIFICATION
    span = _BOOTSTRAP["block_draw_span"]
    assert str(span["start"]) == bs.BLOCK_DRAW_SPAN_START
    assert str(span["end"]) == bs.BLOCK_DRAW_SPAN_END
    assert int(span["months"]) == bs.BLOCK_DRAW_SPAN_MONTHS
    assert _BOOTSTRAP["block_draw_span_binding_factor"] == bs.BLOCK_DRAW_SPAN_BINDING_FACTOR
    assert _SEALED["campaign_vintage_id"] == bs.CAMPAIGN_VINTAGE_ID


def test_stratification_thresholds_match_the_sealed_restatement() -> None:
    """The sealed statement restates the ruleset thresholds; derive.py must agree."""
    thresholds = regime_thresholds()
    assert thresholds["version"] == _BOOTSTRAP["stratification"]
    statement = _BOOTSTRAP["stratification_statement"]
    for key, value in (
        ("cpi_high", 4.0),
        ("growth_weak", 0.0),
        ("growth_slow", 1.5),
        ("drawdown_crisis", -0.2),
        ("hy_crisis", 8.0),
    ):
        assert f"{key}={value}" in statement, f"sealed statement no longer restates {key}"
        assert float(thresholds[key]) == value


def test_sealed_ensemble_size_is_what_the_benchmark_must_run_at() -> None:
    assert _SEALED["ensemble_size"]["n_paths"] == bs.CRITERION_N_PATHS
    assert _SEALED["ensemble_size"]["months"] == bs.CRITERION_MONTHS


# --------------------------------------------------------------------------- #
# 2. registration
# --------------------------------------------------------------------------- #


def test_registered_as_bootstrap_v1() -> None:
    """Importing ``ah.gen`` is enough -- ``ah.eval.metrics.conditional`` resolves by id.

    Deliberately does NOT call :func:`ah.gen.registry.resolve`: the registered factory
    reads the campaign catalog, ``data/`` is gitignored, and a test that needs it would
    be red in CI and on any fresh clone. The factory's own behaviour is exercised by the
    equality below and by the directly-constructed generator every other test uses.
    """
    assert bs.GENERATOR_ID in registry.registered()
    assert registry.snapshot()[bs.GENERATOR_ID] is bs.bootstrap_v1_factory


def test_bootstrap_v1_satisfies_the_generator_protocol() -> None:
    generator = bs.BootstrapV1(_synthetic_source())
    assert isinstance(generator, Generator)
    assert generator.generator_id == bs.GENERATOR_ID


# --------------------------------------------------------------------------- #
# 3. THE structural property: multivariate blocks, never per-factor resampling
# --------------------------------------------------------------------------- #


def test_blocks_are_multivariate_one_shared_row_index_across_all_factors() -> None:
    source = _synthetic_source()
    ensemble = bs.BootstrapV1(source).sample_months(months=48, n_paths=32, seed=11)
    paths = ensemble.paths
    rows = _row_indices(paths)
    for j in range(1, len(source.factor_names)):
        expected = rows.astype(np.float64) + 1000.0 * j
        assert np.array_equal(paths[:, :, j], expected), (
            f"factor {source.factor_names[j]} was resampled independently of factor 0; "
            f"a block must be one contiguous window across ALL factors at once"
        )


def test_emitted_rows_are_always_real_source_rows() -> None:
    source = _synthetic_source()
    rows = _row_indices(bs.BootstrapV1(source).sample_months(60, 32, 3).paths)
    assert rows.min() >= 0
    assert rows.max() < source.n_rows


# --------------------------------------------------------------------------- #
# 4. the Politis-Romano draw rule, as the sealed form_statement defines it
# --------------------------------------------------------------------------- #


def test_within_a_block_the_index_advances_by_one_and_wraps_circularly() -> None:
    source = _synthetic_source(n_rows=24)
    rows = _row_indices(bs.BootstrapV1(source).sample_months(400, 64, 5).paths)
    step = rows[:, 1:] - rows[:, :-1]
    advanced = (rows[:, :-1] + 1) % source.n_rows == rows[:, 1:]
    # every transition is either an advance (possibly a circular wrap) or a fresh start
    wrapped = advanced & (step < 0)
    assert wrapped.any(), "the circular wrap is part of the sealed definition, not optional"


def test_block_lengths_are_geometric_with_the_sealed_mean() -> None:
    source = _synthetic_source(n_rows=200)
    rows = _row_indices(bs.BootstrapV1(source).sample_months(120, 2048, 7).paths)
    restarts = (rows[:, :-1] + 1) % source.n_rows != rows[:, 1:]
    # p = 1/mean_block_months, so the restart rate is the geometric's own parameter
    observed_p = float(restarts.mean())
    expected_p = 1.0 / bs.MEAN_BLOCK_MONTHS
    assert abs(observed_p - expected_p) < 0.01, (
        f"restart rate {observed_p:.4f} is not the sealed p=1/{bs.MEAN_BLOCK_MONTHS}"
    )


# --------------------------------------------------------------------------- #
# 5. determinism
# --------------------------------------------------------------------------- #


def test_same_seed_gives_a_bit_identical_ensemble() -> None:
    source = _synthetic_source()
    a = bs.BootstrapV1(source).sample_months(120, 64, 20260726)
    b = bs.BootstrapV1(source).sample_months(120, 64, 20260726)
    assert np.array_equal(a.paths, b.paths)
    assert a.meta == b.meta


def test_a_different_seed_gives_a_different_ensemble() -> None:
    source = _synthetic_source()
    a = bs.BootstrapV1(source).sample_months(120, 64, 1)
    b = bs.BootstrapV1(source).sample_months(120, 64, 2)
    assert not np.array_equal(a.paths, b.paths)


def test_ensemble_seed_rule_is_the_platform_stride() -> None:
    assert bs.SEED_STRIDE == 7919
    source = _synthetic_source()
    generator = bs.BootstrapV1(source)
    base = 1000
    direct = generator.sample_months(24, 8, base + bs.SEED_STRIDE * 3)
    via_rule = generator.ensemble_seed(base, 3)
    assert via_rule == base + 7919 * 3
    assert np.array_equal(generator.sample_months(24, 8, via_rule).paths, direct.paths)


def test_no_global_rng_is_touched() -> None:
    source = _synthetic_source()
    np.random.seed(0)
    before = np.random.get_state()[1][0]  # type: ignore[index]
    bs.BootstrapV1(source).sample_months(60, 32, 99)
    after = np.random.get_state()[1][0]  # type: ignore[index]
    assert before == after


# --------------------------------------------------------------------------- #
# 6. metadata -- RFR-4's active_blocks producer
# --------------------------------------------------------------------------- #


def test_meta_pins_generator_vintage_seed_and_active_blocks() -> None:
    source = _synthetic_source()
    ensemble = bs.BootstrapV1(source).sample_months(120, 16, 42)
    meta = ensemble.meta
    assert meta.generator_id == bs.GENERATOR_ID
    assert meta.vintage_id == "test-vintage"
    assert meta.seed == 42
    assert meta.n_paths == 16
    assert meta.months == 120
    assert meta.active_blocks == ("global", "us")
    assert meta.conditioning["stratification"] == bs.STRATIFICATION
    assert meta.conditioning["ruleset_version"] == "regime_ruleset_v1"
    assert meta.conditioning["mean_block_months"] == bs.MEAN_BLOCK_MONTHS
    assert meta.conditioning["factor_conditions_honoured"] is False


def test_active_blocks_is_validated_against_the_live_manifest() -> None:
    """RFR-4: be the producer, and check the field rather than trusting it."""
    manifest = load_manifest()
    assert bs.validated_active_blocks(manifest) == manifest.active_blocks
    with pytest.raises(bs.BootstrapError, match="active_blocks"):
        bs.validated_active_blocks(manifest, declared=("global",))


def test_source_rejects_an_active_blocks_that_the_manifest_does_not_declare() -> None:
    with pytest.raises(bs.BootstrapError):
        bs.BootstrapSource(
            factor_names=("a",),
            dates=pd.DatetimeIndex(pd.date_range("1990-01-01", periods=3, freq="MS")),
            values=np.zeros((3, 1)),
            labels=("EXP", "EXP", "EXP"),
            ruleset_version="regime_ruleset_v1",
            vintage_id="v",
            active_blocks=("global", "us"),
        ).check_active_blocks(("global",))


# --------------------------------------------------------------------------- #
# 7. stratification -- unconditional draws at historical frequency
# --------------------------------------------------------------------------- #


def test_unconditional_block_starts_follow_the_historical_regime_frequency() -> None:
    source = _synthetic_source(n_rows=240)
    rows = _row_indices(bs.BootstrapV1(source).sample_months(120, 1024, 13).paths)
    restart = np.ones_like(rows, dtype=bool)
    restart[:, 1:] = (rows[:, :-1] + 1) % source.n_rows != rows[:, 1:]
    start_labels = np.asarray(source.labels)[rows[restart]]
    for label, expected in source.label_frequencies.items():
        observed = float((start_labels == label).mean())
        assert abs(observed - expected) < 0.02, (
            f"regime {label} started {observed:.3f} of blocks, history has {expected:.3f}"
        )


def test_every_source_label_is_a_ruleset_label() -> None:
    source = _synthetic_source()
    assert set(source.label_frequencies) <= set(bs.REGIME_LABELS)


# --------------------------------------------------------------------------- #
# 8. stratification -- a WorldSpec sequence pins the path
# --------------------------------------------------------------------------- #


_WORLD_BASE: dict[str, Any] = {
    "spec_version": "1.0.0",
    "world_id": "wp24-sequence-probe",
    "status": "validated",
    "provenance": {
        "created_at": "2026-07-26T00:00:00Z",
        "author": "sso:wp24",
        "source": {"kind": "manual"},
    },
    "narrative": {
        "language": "en",
        "title": "A sequence-conditioned probe",
        "tagline": "Pins the stratification path",
        "summary": "A WP2.4 test world used only to pin a regime sequence for the benchmark.",
        "lesson": "A test fixture, not a scenario.",
        "dispatches": [
            {"date": "2027", "headline": "It begins", "detail": "n/a"},
            {"date": "2030", "headline": "It continues", "detail": "n/a"},
            {"date": "2033", "headline": "It closes", "detail": "n/a"},
        ],
    },
    "horizon": {"start": "2027-Q1", "quarters": 40},
    "regimes": {"mode": "unconditional"},
    "factor_conditions": {},
    "structural": {"parameter_vintage": "historical_average"},
    "engine_defaults": {"generator_id": "bootstrap-stratified", "n_paths": 1000},
}


def _sequence_world(segments: list[dict[str, Any]]) -> Any:
    doc = dict(_WORLD_BASE)
    doc["regimes"] = {"mode": "sequence", "sequence": segments}
    return project_numeric(load_worldspec(doc))


def test_a_worldspec_sequence_pins_the_start_regime_of_every_block() -> None:
    source = _synthetic_source(n_rows=240)
    world = _sequence_world(
        [
            {"regime": "expansion", "from_quarter": 0, "to_quarter": 19},
            {"regime": "crisis", "from_quarter": 20, "to_quarter": 39},
        ]
    )
    ensemble = bs.BootstrapV1(source).sample(world, n_paths=128, seed=17)
    rows = _row_indices(ensemble.paths)
    restart = np.ones_like(rows, dtype=bool)
    restart[:, 1:] = (rows[:, :-1] + 1) % source.n_rows != rows[:, 1:]
    labels = np.asarray(source.labels)[rows]
    months = rows.shape[1]
    for t in range(months):
        wanted = "EXP" if (t // 3) < 20 else "CRI"
        starts = labels[restart[:, t], t]
        assert starts.size > 0
        assert set(np.unique(starts)) == {wanted}, (
            f"month {t}: block starts drew {set(np.unique(starts))}, sequence asked {wanted}"
        )
    assert ensemble.meta.conditioning["regime_path_source"] == "worldspec_sequence"


def test_unconditional_mode_records_that_it_sampled_historical_frequencies() -> None:
    source = _synthetic_source()
    world = project_numeric(load_worldspec(dict(_WORLD_BASE)))
    ensemble = bs.BootstrapV1(source).sample(world, n_paths=8, seed=1)
    assert ensemble.meta.conditioning["regime_path_source"] == "historical_frequency"
    assert ensemble.months == world.horizon.quarters * 3


def test_an_unreachable_requested_regime_falls_back_and_is_recorded() -> None:
    """A regime with no month in the draw span cannot be drawn; that must be visible."""
    source = _synthetic_source(n_rows=60, labels=tuple(["EXP"] * 60))
    world = _sequence_world([{"regime": "crisis", "from_quarter": 0, "to_quarter": 39}])
    ensemble = bs.BootstrapV1(source).sample(world, n_paths=8, seed=2)
    assert ensemble.meta.conditioning["unsatisfiable_regimes"] == ["CRI"]


def test_worldspec_regime_names_map_onto_the_six_ruleset_labels() -> None:
    for name, label in bs.WORLDSPEC_REGIME_TO_LABEL.items():
        assert label in bs.REGIME_LABELS, f"{name} maps to non-ruleset label {label}"
    # every schema regime name is mapped -- an unmapped one would silently fall back
    import typing

    from ah.core.worldspec import RegimeName

    assert set(typing.get_args(RegimeName)) == set(bs.WORLDSPEC_REGIME_TO_LABEL)


# --------------------------------------------------------------------------- #
# 9. the severe test is structurally not posable for this benchmark
# --------------------------------------------------------------------------- #


def test_no_pre_1990_month_is_reachable() -> None:
    """The sealed span starts 1990-01, so WP2.11's 'regenerate from 1965' cannot be posed."""
    assert bs.BLOCK_DRAW_SPAN_START == "1990-01-01"
    source = _synthetic_source(n_rows=372)
    rows = _row_indices(bs.BootstrapV1(source).sample_months(120, 64, 4).paths)
    reachable = source.dates.to_numpy()[np.unique(rows)]
    assert reachable.min() >= np.datetime64(bs.BLOCK_DRAW_SPAN_START)
    assert bs.SEVERE_TEST_POSABLE is False


# --------------------------------------------------------------------------- #
# 10. guards
# --------------------------------------------------------------------------- #


def test_sample_rejects_a_non_positive_shape() -> None:
    generator = bs.BootstrapV1(_synthetic_source())
    with pytest.raises(bs.BootstrapError):
        generator.sample_months(0, 4, 1)
    with pytest.raises(bs.BootstrapError):
        generator.sample_months(12, 0, 1)


def test_sampling_before_fit_raises() -> None:
    with pytest.raises(bs.BootstrapError, match="not fitted"):
        bs.BootstrapV1().sample_months(12, 4, 1)


def test_fit_accepts_a_source_and_rejects_anything_else() -> None:
    generator = bs.BootstrapV1()
    generator.fit(_synthetic_source())
    assert generator.sample_months(12, 4, 1).n_paths == 4
    with pytest.raises(bs.BootstrapError):
        generator.fit({"not": "a source"})


# --------------------------------------------------------------------------- #
# 11. the local factor resolver must not drift from ah.eval.panel's
# --------------------------------------------------------------------------- #


def _fake_access() -> DataAccess:
    dates = pd.date_range("1990-01-01", "2020-12-01", freq="MS")
    n = len(dates)

    def reader(series_id: str) -> pd.DataFrame:
        if series_id in {"fred.HY_OAS"}:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})
        # A stable per-series offset: `hash(str)` is salted per process, and a fixture
        # that differs between runs is not a fixture.
        offset = float(sum(map(ord, series_id)) % 97)
        values = offset + np.arange(n, dtype=np.float64) / 100.0
        return pd.DataFrame({"date": dates, "value": values})

    return DataAccess(reader)


def test_local_factor_resolution_matches_ah_eval_panel() -> None:
    """Two resolvers of one mapping is the defect class this repo keeps finding.

    ``ah.gen`` may not import ``ah.eval``, so the factor-source resolution has to be
    written twice; this test is what stops the two copies diverging.
    """
    from ah.eval.panel import read_factor_frames  # test-only: tests may import both layers

    manifest = load_manifest()
    access = _fake_access()
    theirs = read_factor_frames(access, manifest)
    mine = bs.read_factor_frames(access, manifest)
    assert set(mine) == set(theirs.frames)
    for factor, frame in mine.items():
        pd.testing.assert_frame_equal(
            frame.reset_index(drop=True), theirs.frames[factor].reset_index(drop=True)
        )


# --------------------------------------------------------------------------- #
# 12. build_source -- the sealed span is DERIVED, then checked against the seal
# --------------------------------------------------------------------------- #


def _plausible_access(vix_start: str = "1990-01-01") -> DataAccess:
    """A catalog-free stand-in with the real vintage's *shape*.

    Every registered series runs 1970-01..2020-12 except ``fred.VIX``, which starts at
    ``vix_start`` and is therefore the binding factor exactly as the sealed
    ``block_draw_span_binding_factor`` records; ``fred.HY_OAS`` is empty, as it is on the
    sealed campaign vintage (its whole licensed history is inside the holdout).
    Magnitudes are plausible rather than realistic -- enough that a cumulative equity
    index, a CPI year-on-year and an NBER indicator all compute.
    """
    long_dates = pd.date_range("1970-01-01", "2020-12-01", freq="MS")
    vix_dates = pd.date_range(vix_start, "2020-12-01", freq="MS")
    rng = np.random.Generator(np.random.PCG64(20260726))
    n = len(long_dates)
    equity = rng.normal(0.007, 0.04, size=n)
    series: dict[str, tuple[pd.DatetimeIndex, np.ndarray]] = {
        "fred.VIX": (vix_dates, 15.0 + rng.normal(0.0, 3.0, size=len(vix_dates))),
        "fred.CPI": (long_dates, 100.0 * np.power(1.003, np.arange(n))),
        "fred.INDPRO": (long_dates, 100.0 * np.power(1.002, np.arange(n))),
        "fred.USREC": (long_dates, (np.arange(n) % 60 < 6).astype(np.float64)),
        "french.mkt_rf": (long_dates, equity),
        "french.rf": (long_dates, np.full(n, 0.003)),
        "french.smb": (long_dates, rng.normal(0.001, 0.03, size=n)),
        "french.hml": (long_dates, rng.normal(0.001, 0.03, size=n)),
        "french.mom": (long_dates, rng.normal(0.004, 0.04, size=n)),
        "fred.BAA": (long_dates, 7.0 + rng.normal(0.0, 0.5, size=n)),
        "fred.AAA": (long_dates, 6.0 + rng.normal(0.0, 0.4, size=n)),
        "fred.FEDFUNDS": (long_dates, 3.0 + rng.normal(0.0, 1.0, size=n)),
        "fred.DGS2": (long_dates, 3.5 + rng.normal(0.0, 1.0, size=n)),
        "fred.DGS10": (long_dates, 4.5 + rng.normal(0.0, 1.0, size=n)),
        "treasury.hqm_curve": (long_dates, 5.5 + rng.normal(0.0, 0.8, size=n)),
        "fred.TEDRATE": (long_dates, 0.5 + rng.normal(0.0, 0.2, size=n)),
    }

    def reader(series_id: str) -> pd.DataFrame:
        entry = series.get(series_id)
        if entry is None:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})
        dates, values = entry
        return pd.DataFrame({"date": dates, "value": values})

    return DataAccess(reader)


def test_build_source_derives_the_sealed_span_and_labels_it() -> None:
    source = bs.build_source(_plausible_access(), load_manifest(), vintage_id="test-vintage")
    assert source.factor_names == bs.FACTOR_SET
    assert source.dates[0] == pd.Timestamp(bs.BLOCK_DRAW_SPAN_START)
    assert source.dates[-1] == pd.Timestamp(bs.BLOCK_DRAW_SPAN_END)
    assert source.n_rows == bs.BLOCK_DRAW_SPAN_MONTHS
    assert source.ruleset_version == "regime_ruleset_v1"
    assert source.active_blocks == load_manifest().active_blocks
    assert set(source.label_frequencies) <= set(bs.REGIME_LABELS)
    assert abs(sum(source.label_frequencies.values()) - 1.0) < 1e-9


def test_build_source_refuses_a_span_that_is_not_the_sealed_one() -> None:
    """The benchmark may not quietly resample a different window than the seal names."""
    access = _plausible_access(vix_start="1995-01-01")
    with pytest.raises(bs.BootstrapError, match="block_draw_span"):
        bs.build_source(access, load_manifest(), vintage_id="test-vintage")
    # the escape hatch is explicit, never implicit
    source = bs.build_source(
        access, load_manifest(), vintage_id="test-vintage", enforce_sealed_span=False
    )
    assert source.dates[0] == pd.Timestamp("1995-01-01")


def test_build_source_refuses_to_default_a_missing_regime_feature() -> None:
    """A defaulted feature changes labels, and a label change changes every draw."""
    access = _plausible_access()
    inner = access._reader

    def reader(series_id: str) -> pd.DataFrame:
        if series_id == bs.INDPRO_SERIES_ID:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})
        return inner(series_id)

    with pytest.raises(bs.BootstrapError, match=bs.INDPRO_SERIES_ID):
        bs.build_source(DataAccess(reader), load_manifest(), vintage_id="test-vintage")


# --------------------------------------------------------------------------- #
# 13. the layering invariant
# --------------------------------------------------------------------------- #

_EVAL_IMPORT = re.compile(
    r"(?m)^\s*(?:from\s+ah\.eval|import\s+ah\.eval|from\s+ah\s+import\s+eval)"
)


def test_no_gen_module_imports_ah_eval() -> None:
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in GEN_DIR.rglob("*.py")
        if _EVAL_IMPORT.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"ah.gen must never import ah.eval: {offenders}"


# --------------------------------------------------------------------------- #
# the schema alias (WP2.4b)
# --------------------------------------------------------------------------- #


def test_an_authored_world_resolves_to_the_benchmark() -> None:
    """A checked-in WorldSpec naming the schema's id must reach the generator.

    Before the alias this raised ``UnknownGeneratorError``: ``schemas/``'s
    ``generator_id`` enum offers ``bootstrap-stratified``, WP2.4 registered
    ``bootstrap-v1``, and every authored world under ``fixtures/worlds/conditional/``
    names the former. The schema is read-only vendored truth, so the code carries both.
    """
    import json

    from ah.core.loader import load_worldspec
    from ah.gen import registry

    doc = json.loads(
        (
            ROOT / "fixtures" / "worlds" / "conditional" / "crisis_severity_mild.worldspec.json"
        ).read_text(encoding="utf-8")
    )
    generator = registry.resolve_for_world(load_worldspec(doc))
    assert generator.generator_id == bs.GENERATOR_ID


def test_both_ids_resolve_to_the_same_generator() -> None:
    """The alias is a second name, not a second generator."""
    from ah.gen import registry

    assert registry.resolve(bs.GENERATOR_ID).generator_id == bs.GENERATOR_ID
    assert registry.resolve(bs.SCHEMA_GENERATOR_ID).generator_id == bs.GENERATOR_ID
    assert registry.snapshot()[bs.SCHEMA_GENERATOR_ID] is bs.bootstrap_v1_factory


def test_the_alias_is_the_id_the_schema_actually_permits() -> None:
    """Pin the alias to ``schemas/``, so a schema bump cannot silently orphan it."""
    import json

    schema = json.loads(
        (ROOT / "schemas" / "worldspec-v1.0.schema.json").read_text(encoding="utf-8")
    )
    allowed = schema["properties"]["engine_defaults"]["properties"]["generator_id"]["enum"]
    assert bs.SCHEMA_GENERATOR_ID in allowed
    assert bs.GENERATOR_ID not in allowed, (
        "STEP2R Sec.WP2R.6 has bumped the schema to include bootstrap-v1; "
        "the alias can now be retired and this test deleted."
    )
