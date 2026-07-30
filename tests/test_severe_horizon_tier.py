"""WP2.11: what "the horizon tier" resolves to -- and that it is AMBIGUOUS.

The sealed ``severe_test_protocol`` says to compare 1966-1984 behaviour "through
the HORIZON TIER". ``ah.eval.battery.TIERS`` is
``(monthly, 1_5yr, 10yr, economic, severe)`` -- **there is no tier named
"horizon"**, exactly as the seal's own ``tail_tier_definition`` had to resolve
"the tail tier" against a battery that has no tier of that name either.

Two readings are available, and THEY DO NOT COINCIDE:

- READING A (by suite): every MetricSpec with ``suite == "horizon"``, i.e. what
  ``ah.eval.metrics.horizon.build_horizon_suite`` registers. This is the direct
  analogue of the sealed ``tail_tier_definition``, which says in terms "THE TAIL
  TIER IS A SUITE, NOT A HORIZON TIER".
- READING B (by tier): every MetricSpec whose ``tier`` is one of the two
  horizon-LENGTH tiers ``1_5yr`` / ``10yr`` -- the sense in which that same
  sealed sentence uses the words "a horizon tier", and the sense
  ``ah.eval.reference.StatBand``'s docstring uses ("the DN-1.1 Sec.II.6 horizon
  tier this statistic belongs to").

**They differ by the calibration suite's five-year metrics.**
``ah.eval.metrics.calibration.CALIBRATION_TIER_BY_SUFFIX`` maps the ``5y``
suffix to tier ``1_5yr`` while carrying ``suite == "calibration"``, so reading B
contains metrics reading A does not. That is asserted below rather than
discovered later, because it is exactly the kind of unresolved phrase the
pre-registration exists to stop being resolved after the numbers are in.

RESOLUTION TAKEN BY WP2.11 PART 1: report the UNION, with each metric's suite
AND tier shown, so a reader can apply either reading to the same table. The
severe test's outcome is stated under both. Choosing one and quietly dropping
the other would be selecting a comparison set with results already in hand,
which is the forking path the seal forbids; reporting both costs nothing,
because both come out of the one battery run. Narrowing this to a single reading
is a dated ``protocol_change`` amendment for the governance step, not a decision
for the run that produces the evidence.
"""

from __future__ import annotations

from ah.eval import battery as bat
from ah.eval.metrics import calibration as cal
from ah.eval.metrics import horizon as hz

HORIZON_LENGTH_TIERS = ("1_5yr", "10yr")


class TestThereIsNoHorizonTier:
    def test_the_battery_has_no_tier_of_that_name(self):
        assert "horizon" not in bat.TIERS
        assert bat.TIERS == ("monthly", "1_5yr", "10yr", "economic", "severe")

    def test_horizon_is_a_suite_name(self):
        assert hz.SUITE == "horizon"

    def test_the_horizon_suite_owns_exactly_the_two_horizon_length_tiers(self):
        assert {hz.TIER_1_5YR, hz.TIER_10YR} == set(HORIZON_LENGTH_TIERS)

    def test_the_horizon_suite_is_in_the_reference_dependent_table(self):
        assert bat._REFERENCE_DEPENDENT_SUITE_BUILDERS["horizon"] == (
            "ah.eval.metrics.horizon",
            "build_horizon_suite",
        )


class TestTheTwoReadingsDiverge:
    """The finding: reading B is strictly larger than reading A, by calibration's
    five-year metrics. Pinned so the divergence cannot be re-discovered (or
    quietly resolved) after results exist."""

    def test_calibration_claims_a_horizon_length_tier(self):
        assert cal.SUITE == "calibration"
        assert cal.CALIBRATION_TIER_BY_SUFFIX["5y"] == "1_5yr"

    def test_and_therefore_by_tier_is_not_the_same_set_as_by_suite(self):
        claimed_by_calibration = {
            tier for tier in cal.CALIBRATION_TIER_BY_SUFFIX.values() if tier in HORIZON_LENGTH_TIERS
        }
        assert claimed_by_calibration, (
            "if calibration ever stops claiming a horizon-length tier the two "
            "readings coincide and this WP's union reporting can be narrowed -- "
            "by amendment, not silently"
        )

    def test_calibration_one_year_metrics_stay_monthly(self):
        """Only the 5y suffix crosses over; the 1y one does not."""
        assert cal.CALIBRATION_TIER_BY_SUFFIX["1y"] == "monthly"
