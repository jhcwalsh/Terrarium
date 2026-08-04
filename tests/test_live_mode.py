"""WP4.6 — live mode: the seal, the three rules, the wall, the policy.

The information-wall tests are the blocking ones per the plan: data past
the pointer must be structurally unreachable, not merely impolite to ask
for. Tamper detection, provenance completeness, pointer arithmetic at
the boundaries, and the chaptered flag's OFF default round it out.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.artifacts import live

RNG = np.random.Generator(np.random.PCG64(7))
ENSEMBLE = RNG.normal(0.005, 0.04, size=(50, 120, 3))


class TestSeal:
    def test_seal_verifies_and_detects_tamper(self):
        tape = ENSEMBLE[0]
        sealed = live.seal_tape(tape)
        assert live.verify_tape(tape, sealed)
        tampered = tape.copy()
        tampered[60, 0] += 1e-6  # one mark, one month, barely
        assert not live.verify_tape(tampered, sealed)

    def test_seal_format_is_singly_prefixed_and_cross_language_pinned(self):
        """The seal is exactly ``sha256:<64 hex>`` — a doubled prefix once
        shipped here — and the literal vector below is the SAME tape the
        app's TypeScript verifier hashes (app/src/lib/bundle.test.ts), so
        the two implementations are pinned to each other by value."""
        sealed = live.seal_tape(np.array([[1.5, -2.25], [0.125, 3.0]]))
        assert sealed == ("sha256:7e327e9a0eb36f457386e18c60046f8a51ef4097be849fcfa1e387e90f57017b")

    def test_waypoints_seal_at_t0(self):
        waypoints = [{"chapter": 1, "regime": "stress"}, {"chapter": 2, "regime": "recovery"}]
        sealed = live.seal_waypoints(waypoints)
        assert sealed.startswith("sha256:")
        assert live.seal_waypoints(list(reversed(waypoints))) != sealed  # order is content

    def test_chaptered_generation_is_off_by_default(self):
        assert live.CHAPTERED_GENERATION_DEFAULT is False


class TestTapeSelection:
    def test_random_is_seed_deterministic_with_provenance(self):
        a, prov_a = live.select_tape(ENSEMBLE, rule="random", base_seed=42)
        b, prov_b = live.select_tape(ENSEMBLE, rule="random", base_seed=42)
        live.select_tape(ENSEMBLE, rule="random", base_seed=43)  # different seed also runs
        assert a == b and prov_a == prov_b  # determinism is the claim
        assert prov_a["rule"] == "random" and prov_a["sealed_hash"].startswith("sha256:")

    def test_percentile_is_prestated_and_recorded(self):
        path_id, prov = live.select_tape(ENSEMBLE, rule="percentile", base_seed=1, percentile=50.0)
        terminal = np.prod(1.0 + ENSEMBLE[:, :, 0], axis=1)
        median = np.percentile(terminal, 50.0)
        assert terminal[path_id] == pytest.approx(terminal[np.argmin(np.abs(terminal - median))])
        assert prov["percentile"] == 50.0 and prov["metric"] == "terminal_wealth"
        with pytest.raises(live.LiveModeError, match="PRE-STATED"):
            live.select_tape(ENSEMBLE, rule="percentile", base_seed=1)

    def test_pinned_validates_and_records(self):
        path_id, prov = live.select_tape(ENSEMBLE, rule="pinned", base_seed=1, pinned_path_id=7)
        assert path_id == 7 and prov["pinned_path_id"] == 7
        with pytest.raises(live.LiveModeError, match="outside"):
            live.select_tape(ENSEMBLE, rule="pinned", base_seed=1, pinned_path_id=99)
        with pytest.raises(live.LiveModeError, match="unknown"):
            live.select_tape(ENSEMBLE, rule="vibes", base_seed=1)


class TestRevealPointerAndWall:
    def test_pointer_arithmetic_at_the_boundaries(self):
        assert live.reveal_pointer(days_elapsed=0, cadence_days=1.0, horizon_months=120) == 0
        assert live.reveal_pointer(days_elapsed=59.9, cadence_days=1.0, horizon_months=120) == 59
        assert live.reveal_pointer(days_elapsed=1e6, cadence_days=1.0, horizon_months=120) == 120
        with pytest.raises(live.LiveModeError):
            live.reveal_pointer(days_elapsed=-1, cadence_days=1.0, horizon_months=120)

    def test_the_wall_is_structural(self):
        tape = ENSEMBLE[0]
        revealed = live.RevealedTape.cut(tape, 60)
        assert revealed.month(59).shape == (3,)
        with pytest.raises(live.LiveModeError, match="information wall"):
            revealed.month(60)
        # the strong claim: the unrevealed data never entered the object
        assert revealed.data.shape[0] == 60
        assert revealed.data.base is None  # a copy, not a view into the full tape

    def test_wall_survives_pointer_growth(self):
        tape = ENSEMBLE[0]
        early = live.RevealedTape.cut(tape, 12)
        later = live.RevealedTape.cut(tape, 13)
        np.testing.assert_array_equal(early.data, later.data[:12])  # reveal only appends


class TestNotificationPolicy:
    def test_push_only_regime_events(self):
        assert live.classify_notification("regime_event") == "push"
        for quiet in ("capital_call", "distribution", "forced_sale", "statement", "wire_item"):
            assert live.classify_notification(quiet) == "digest"
