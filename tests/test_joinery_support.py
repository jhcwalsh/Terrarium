"""WP2.7 support: conditioning-support diagnostics (Mahalanobis + regime frequency)."""

from __future__ import annotations

import numpy as np
import pytest

from ah.gen.joinery import bridge, support
from ah.gen.joinery import waypoints as wp
from joinery_common import CODE, make_climate_artifact, make_source


@pytest.fixture(scope="module")
def climate(tmp_path_factory):
    return make_climate_artifact(tmp_path_factory.mktemp("climate"))


@pytest.fixture(scope="module")
def source():
    return make_source()


@pytest.fixture(scope="module")
def ref(source, climate):
    return support.build_support_reference(source, climate)


def _conds_from_rows(x: np.ndarray, labels: np.ndarray) -> list[bridge.BlockConditioning]:
    conds = []
    for i in range(x.shape[0]):
        conds.append(
            bridge.BlockConditioning(
                regime_onehot=np.eye(6)[int(labels[i])],
                state_snapshot=x[i, :5],
                history_summary=x[i, 5:8],
                waypoint_increments=x[i, 8:12],
                start_month=3 * i,
            )
        )
    return conds


class TestHistoricalConditioning:
    def test_shapes_and_component_count(self, source, climate):
        x, labels = support.historical_conditioning(source, climate)
        # starts at month 12 (a full trailing year), stride 3, block fits inside T
        expected = len(range(12, source.n_rows - 6 + 1, 3))
        assert x.shape == (expected, 12)
        assert labels.shape == (expected,)
        assert np.all(np.isfinite(x))

    def test_deterministic(self, source, climate):
        a, la = support.historical_conditioning(source, climate)
        b, lb = support.historical_conditioning(source, climate)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(la, lb)

    def test_artifact_grid_must_cover_the_span(self, source, tmp_path):
        short = make_climate_artifact(tmp_path, start="2005-01-01", t_months=60)
        with pytest.raises(wp.JoineryError, match="does not cover"):
            support.historical_conditioning(source, short)


class TestSupportReference:
    def test_threshold_is_the_stated_quantile_of_self_distances(self, source, climate, ref):
        x, _ = support.historical_conditioning(source, climate)
        d = support.mahalanobis(x, ref)
        assert ref.quantile == 0.99
        assert ref.threshold == pytest.approx(float(np.quantile(d, 0.99)))
        # by construction ~1% of historical blocks sit beyond their own p99
        assert float(np.mean(d > ref.threshold)) <= 0.02

    def test_label_frequencies_sum_to_one(self, ref):
        assert float(ref.label_frequencies.sum()) == pytest.approx(1.0)


class TestDecadeSupport:
    def test_on_support_historical_decade_scores_low(self, source, climate, ref):
        # a decade of ACTUAL historical conditioning vectors is on-support by
        # construction: extrapolation share near the nominal 1%, no flag
        x, labels = support.historical_conditioning(source, climate)
        conds = _conds_from_rows(x[:40], labels[:40])
        months_labels = np.repeat(labels[:40], 3)
        diag = support.decade_support(conds, months_labels, ref)
        assert diag["n_blocks"] == 40
        assert diag["extrapolation_share"] <= 0.10
        assert not diag["flag_off_support"]
        assert 0.0 <= diag["regime_freq_tv"] <= 1.0

    def test_far_off_support_conditioning_scores_high_and_flags(self, source, climate, ref):
        x, labels = support.historical_conditioning(source, climate)
        shifted = x[:40] + 25.0 * np.sqrt(np.diag(ref.cov))  # ~25 sd off in every axis
        diag = support.decade_support(
            _conds_from_rows(shifted, labels[:40]), np.repeat(labels[:40], 3), ref
        )
        assert diag["extrapolation_share"] >= 0.9
        assert diag["flag_off_support"]
        assert diag["mahalanobis_p95"] > ref.threshold

    def test_regime_frequency_check_flags_an_alien_mix(self, source, climate, ref):
        # an all-CRI decade against a history that is mostly EXP: TV distance high
        x, _labels = support.historical_conditioning(source, climate)
        conds = _conds_from_rows(x[:40], np.full(40, CODE["CRI"]))
        diag = support.decade_support(conds, np.full(120, CODE["CRI"]), ref)
        assert diag["regime_freq_tv"] > 0.5

    def test_thin_stag_support_is_visible_not_papered_over(self, climate):
        # STAG absent from the span: the reference records zero frequency, so a
        # STAG-leaning decade shows a large regime TV distance (support.py says so).
        no_stag = make_source(labels=tuple(("EXP",) * 240))
        ref = support.build_support_reference(no_stag, climate)
        assert ref.label_frequencies[CODE["STAG"]] == 0.0

    def test_summary_is_json_safe(self, source, climate, ref):
        import json

        x, labels = support.historical_conditioning(source, climate)
        diag = support.decade_support(
            _conds_from_rows(x[:10], labels[:10]), np.repeat(labels[:10], 3), ref
        )
        json.dumps(diag)
