"""WP3.3 — the forward smoothing kernel.

SM-10 as a test: de-smooth(smooth(x)) recovers x through the SEALED public
de-smoother, so reported and true are provably one model seen two ways. Plus:
the smoothed series carries the serial correlation smoothing exists to create,
the stickiness mechanism moves marks toward the past exactly when told to, and
an unparameterized family refuses rather than pretends.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.data.desmooth import glm_ma
from ah.port import smoothing as sk

RNG = np.random.default_rng(20260801)


def _true_path(months: int = 240) -> np.ndarray:
    return RNG.normal(0.008, 0.03, size=months)


class TestKernelArtifact:
    def test_artifact_loads_with_all_seven_sleeves(self):
        doc = sk.load_kernel()
        assert doc["kernel_version"] == "smooth-2026.08"
        assert set(doc["families"]["glm"]["sleeves"]) == {
            "hf_credit",
            "hf_cta",
            "hf_equity_ls",
            "hf_event",
            "hf_macro",
            "hf_multi",
            "hf_rv",
        }
        for spec in doc["families"]["glm"]["sleeves"].values():
            theta = np.asarray(spec["theta"])
            assert np.isclose(theta.sum(), 1.0, atol=1e-3)  # weights are a partition

    def test_measured_zero_stickiness_with_its_evidence(self):
        """The negative finding ships as measured: s = 0, evidence recorded."""
        doc = sk.load_kernel()
        glm = doc["families"]["glm"]
        assert glm["stickiness"] == 0.0
        ev = glm["stickiness_evidence"]
        assert ev["theta0_stress_pooled"] > ev["theta0_calm_pooled"]  # the sign IS the finding

    def test_geltner_family_is_parameterized_and_still_refuses_what_it_lacks(self):
        """HISTORY: this asserted ``status == UNPARAMETERIZED`` and that asking
        for any appraisal sleeve raised — the honest state while no PM series
        was delivered. The first PriMaRS delivery (2026-08-08) fired the
        trigger the artifact carried, so the family is now fitted and the
        assertion is INVERTED rather than deleted.

        What must NOT change is the refusal for sleeves the delivery does not
        cover: two modeled sleeves is not all of them.
        """
        geltner = sk.load_kernel()["families"]["geltner"]
        assert geltner["status"] == "PARAMETERIZED"

        a, phi = sk.geltner_for("pm_re_value_add")
        assert 0.0 < a <= 1.0 and 0.0 <= phi < 1.0
        assert a == pytest.approx(1.0 - phi, abs=1e-9)  # the AR(1) identity

        # an appraisal sleeve is not a GLM sleeve, and says so
        with pytest.raises(sk.SmoothingError, match="APPRAISAL-CALENDAR"):
            sk.theta_for("pm_re_value_add")
        # and a sleeve the delivery never covered still refuses
        with pytest.raises(sk.SmoothingError, match="pm_re_core"):
            sk.geltner_for("pm_re_core")

    def test_pm_glm_sleeves_are_reachable_and_carry_their_own_stickiness(self):
        theta = sk.theta_for("pm_buyout")
        assert theta.ndim == 1 and theta.sum() == pytest.approx(1.0, abs=1e-6)
        # the two families are calibrated on different frequencies
        assert sk.stickiness(family="glm") == 0.0
        assert sk.stickiness(family="geltner") > 0.0


class TestSM10Inverse:
    def test_desmooth_recovers_truth_through_the_sealed_public_api(self):
        """The consistency requirement end to end: smooth with a known theta,
        hand the result to the SEALED de-smoother, require it to find ~theta
        and recover ~x. One model, two views — or this test fails."""
        theta = np.array([0.5, 0.3, 0.2])  # k=2 with identifiable lag-2 mass
        x = _true_path()
        reported = sk.smooth(x, theta)
        fit = glm_ma(reported)
        # Order selection may wobble +/-1 on finite noise; what SM-10 demands is
        # WEIGHT and TRUTH recovery, so that is what gets pinned:
        assert fit.k >= 2  # the real lag structure is found
        np.testing.assert_allclose(fit.theta[:3], theta, atol=0.08)
        assert all(w <= 0.10 for w in fit.theta[3:])  # anything extra is dust
        # recovered truth matches x where the recursion has warmed up
        np.testing.assert_allclose(fit.truth[24:], x[24:], atol=0.02)
        assert np.std(fit.truth[24:]) / np.std(reported[24:]) > 1.2  # vol comes back

    def test_smoothing_creates_the_serial_correlation_it_exists_to_create(self):
        theta = np.array([0.5, 0.3, 0.2])
        x = _true_path()
        reported = sk.smooth(x, theta)

        def ac1(v: np.ndarray) -> float:
            return float(np.corrcoef(v[:-1], v[1:])[0, 1])

        assert ac1(reported) > ac1(x) + 0.15  # visibly smoother marks

    def test_identity_theta_is_a_passthrough(self):
        x = _true_path(60)
        np.testing.assert_array_equal(sk.smooth(x, np.array([1.0])), x)


class TestStickiness:
    def test_stickiness_leans_on_the_past_exactly_in_drawdowns(self):
        theta = np.array([0.6, 0.4])
        x = np.full(48, 0.01)
        x[24:30] = -0.10  # a drawdown
        d = sk.drawdown_state_from_returns(x)
        base = sk.smooth(x, theta, s=0.0, drawdown_state=d)
        sticky = sk.smooth(x, theta, s=0.8, drawdown_state=d)
        # Stickiness bites exactly where current and lagged truth DIFFER
        # (constant-input stretches are invariant by construction):
        assert sticky[24] > base[24]  # crash arrives — the sticky mark lags the fall
        assert sticky[30] < base[30]  # recovery arrives — it lags the bounce too
        # before the drawdown, the state is zero and nothing differs
        np.testing.assert_allclose(sticky[:24], base[:24])

    def test_drawdown_state_is_causal_and_bounded(self):
        x = _true_path(120)
        d = sk.drawdown_state_from_returns(x)
        assert d.shape == x.shape and d.min() >= 0.0 and d.max() <= 1.0
        # causal: truncating the future never changes the past
        d_short = sk.drawdown_state_from_returns(x[:60])
        np.testing.assert_array_equal(d_short, d[:60])


class TestRefusals:
    def test_bad_theta_and_bad_state_refused(self):
        x = _true_path(36)
        with pytest.raises(sk.SmoothingError, match="sum to 1"):
            sk.smooth(x, np.array([0.9, 0.2]))
        with pytest.raises(sk.SmoothingError, match="\\[0, 1\\]"):
            sk.smooth(x, np.array([0.7, 0.3]), s=2.0)
        with pytest.raises(sk.SmoothingError, match="shape"):
            sk.smooth(x, np.array([0.7, 0.3]), s=0.5, drawdown_state=np.zeros(10))

    def test_paths_axis_round_trip(self):
        theta = sk.theta_for("hf_event")
        panel = RNG.normal(0.005, 0.04, size=(5, 120))
        out = sk.smooth(panel, theta)
        assert out.shape == (5, 120)
        np.testing.assert_allclose(out[2], sk.smooth(panel[2], theta))
