"""ER-14 close-out: the inflation channels (D-ER14-2, 2026-08-18).

Acceptance tests AT-1..AT-8, AT-11, AT-12 (the probe suite). AT-7/AT-14 and
the stream-corruption guards live in ``tests/test_er14_streams.py``.

The shared helper block below is defined ONCE here; later tasks (M3, M5,
C1-C4, S1, G2) import these names and add no second implementation.

DEVIATION (recorded in the Task M1 commit body): ``src/ah/presets/`` holds
ten preset files, but only five (world ids ...511-515) declare
``engine_defaults.generator_id == "toy-v0"`` -- the other five (...603,
701, 703, 801, 802) are generated-plane presets that
``ah.core.engine.run_path`` structurally rejects
(``UnsupportedGeneratorError``), by design (they are the Step 2 generator's
worlds, not the toy engine's). This matches the plan's own Global
Constraints world-fence table (511-515 -> 521-525 is the toy-v0.7 move;
603/701/703/801/802 move or retire separately). Every PRESETS iteration in
this WP's tests and in ``scripts/gen_er14_baseline.py`` is therefore
filtered to the toy-v0 subset via ``TOY_PRESETS`` -- the plan's literal
"``for path in sorted(PRESETS.glob("*.json"))``" would otherwise crash on
the first generated-plane preset it reached.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from ah.core import engine
from ah.core.digest import sha256_of_arrays
from ah.core.engine import (
    INFLATION_ANCHOR_PCT,
    _DEF,
    _RATE_SHOCK_INFLATION_ANCHOR,
    EnsembleResult,
    inflation_excess,
    run_ensemble,
    run_path,
)
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
FIXTURES = ROOT / "fixtures" / "compiler"
BASELINE_NPZ = ROOT / "tests" / "fixtures" / "er14" / "public-baseline-toy-v0.6.npz"
BASELINE_JSON = BASELINE_NPZ.with_suffix(".json")
ANCHOR_BASELINE_NPZ = ROOT / "tests" / "fixtures" / "er14" / "anchor-baseline-toy-v0.6.npz"
SEED = 12345
PUBLIC_ASSETS = ("equity", "bonds", "hy", "commodities", "reits")
STAGFLATION = PRESETS / "stagflation.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_toy(path: Path) -> bool:
    return _load(path).get("engine_defaults", {}).get("generator_id") == "toy-v0"


TOY_PRESETS: list[Path] = [p for p in sorted(PRESETS.glob("*.json")) if _is_toy(p)]


def _set_dotted(doc: dict, dotted: str, value: float) -> None:
    """Set a dotted WorldSpec path, creating intermediate objects as needed."""
    node = doc
    *parents, leaf = dotted.split(".")
    for key in parents:
        node = node.setdefault(key, {})
    node[leaf] = value


def _world(infl_pct: float, preset: Path = STAGFLATION, **field_overrides):
    doc = copy.deepcopy(_load(preset))
    _set_dotted(doc, "factor_conditions.inflation.average_pct", infl_pct)
    for dotted, value in field_overrides.items():
        _set_dotted(doc, dotted, value)
    return project_numeric(load_worldspec(doc))


def probe(infl_pct: float, preset: Path = STAGFLATION, **field_overrides) -> EnsembleResult:
    """ER-14's own experiment, unchanged: one field varied, everything else held.
    200 paths, base_seed=12345 (design 6: reusing the exact experiment that found
    the defect is what makes 'inverted' mean something)."""
    return run_ensemble(_world(infl_pct, preset, **field_overrides), 200, base_seed=SEED)


def ensemble_of(preset_stem: str) -> EnsembleResult:
    """The preset AS AUTHORED - no field varied. Used by the world-basis tests."""
    doc = _load(PRESETS / f"{preset_stem}.json")
    return run_ensemble(project_numeric(load_worldspec(doc)), 200, base_seed=SEED)


def annualised(ens: EnsembleResult, asset: str) -> float:
    r = ens.returns[asset] / 100.0
    return float((np.prod(1 + r, axis=1).mean() ** (12 / r.shape[1]) - 1) * 100)


def sharpe(ens: EnsembleResult, asset: str) -> float:
    r = ens.returns[asset] / 100.0
    return float(r.mean() * 12 / (r.std(ddof=1) * math.sqrt(12)))


# --------------------------------------------------------------------------- #
# AT-6b: public assets are untouched, unconditionally
# --------------------------------------------------------------------------- #


def test_at6b_public_assets_are_bit_identical_to_toy_v06():
    """AT-6b. equity/bonds/hy/commodities/reits are bit-identical to toy-v0.6 on
    every toy-plane preset and every compiler fixture, unconditionally.

    Only three (later four) return equations move and no RNG draw is added or
    REORDERED. If a public asset moves, something was touched that should not
    have been - this is the STOP condition of the whole implementation."""
    ref = np.load(BASELINE_NPZ)
    for path in TOY_PRESETS:
        paths = run_path(project_numeric(load_worldspec(_load(path))), SEED)
        for asset in PUBLIC_ASSETS:
            np.testing.assert_array_equal(
                paths.returns[asset], ref[f"{path.stem}/{asset}"], err_msg=f"{path.stem}/{asset}"
            )


def test_at6b_public_assets_hold_on_every_compiler_fixture():
    """AT-6b, the fixture half: same claim, checked by digest over the committed
    compiler fixtures (adversarial reject/clamp fixtures are excluded upstream
    by the baseline generator's own skip list, recorded in the sidecar JSON)."""
    doc = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    for key, expected in doc["digests"].items():
        stem, asset = key.rsplit("/", 1)
        paths = run_path(project_numeric(load_worldspec(_load(FIXTURES / f"{stem}.json"))), SEED)
        assert sha256_of_arrays([paths.returns[asset]]) == expected, key


# --------------------------------------------------------------------------- #
# Task M2: inflation_excess, the shared state variable
# --------------------------------------------------------------------------- #


def test_inflation_excess_is_a_trailing_mean_demeaned_at_the_anchor():
    x = inflation_excess(np.full(36, 6.5))
    assert np.allclose(x, 4.5)


def test_inflation_excess_warms_up_over_available_months_not_from_zero():
    """K=24 with a 120-month world would leave a fifth of the game dead and put a
    visible step at month 24. The mean is taken over the months available, so a
    world that opens hot is hot from month 0 (design 2.0)."""
    infl = np.array([10.0, 0.0, 0.0, 0.0])
    x = inflation_excess(infl, k=24)
    assert x[0] == pytest.approx(10.0 - 2.0)
    assert x[1] == pytest.approx(5.0 - 2.0)
    assert x[3] == pytest.approx(2.5 - 2.0)


def test_inflation_excess_window_is_exactly_k_months():
    infl = np.concatenate([np.zeros(24), np.full(24, 12.0)])
    x = inflation_excess(infl, k=24)
    assert x[47] == pytest.approx(12.0 - 2.0)
    assert x[35] == pytest.approx(6.0 - 2.0)


def test_inflation_excess_consumes_no_rng():
    """The channel is derived state, not a new stream (AT-7's precondition)."""
    rng = np.random.Generator(np.random.PCG64(7))
    before = rng.standard_normal(3).tolist()
    inflation_excess(np.full(24, 3.0))
    rng2 = np.random.Generator(np.random.PCG64(7))
    assert rng2.standard_normal(3).tolist() == before


def test_the_anchor_is_the_engines_own_anchor():
    """C_ANCHOR is not a new number: it is _RATE_SHOCK_INFLATION_ANCHOR and
    _DEF['infl_avg'] (D-ER14-2 A1 row 1)."""
    assert INFLATION_ANCHOR_PCT == _RATE_SHOCK_INFLATION_ANCHOR == _DEF["infl_avg"] == 2.0


# --------------------------------------------------------------------------- #
# Task M3: real estate - income escalation vs cap-rate repricing
# --------------------------------------------------------------------------- #


def test_at1_private_returns_are_no_longer_bit_identical_across_inflation():
    """AT-1, the literal inversion. ER-14's headline is 'bit-identical across a
    twelvefold change'; this is that sentence negated. Break-proof: it cannot be
    satisfied by a test that restates the implementation."""
    lo = run_path(_world(1.0), 12345)
    hi = run_path(_world(12.0), 12345)
    for asset in ("pe", "re"):
        assert not np.array_equal(lo.returns[asset], hi.returns[asset]), asset


def test_at3_real_estate_moves_the_right_way_and_materially():
    """AT-3. Delta annualised re, 1% -> 12%, must be POSITIVE and >= +1.5 pp/yr
    (lambda_RE's declared range floor 0.15 x 11pp - rounding). Today's measured
    value is -0.117: this is a sign flip of ~1.6 pp/yr minimum."""
    delta = annualised(probe(12.0), "re") - annualised(probe(1.0), "re")
    assert delta >= 1.5, delta


def test_at8_the_deflation_mirror():
    """AT-8. deflation_bust (-1.0%) re sits at least 0.5 pp/yr BELOW goldilocks
    (2.0%) re. The mechanism must be symmetric - an inflation RESPONSE, not a
    one-sided bonus that only ever pays. lambda_RE's range floor 0.15 x 3.0pp =
    0.45, rounded to 0.5."""
    bust = annualised(ensemble_of("deflation_bust"), "re")
    gold = annualised(ensemble_of("goldilocks"), "re")
    assert gold - bust >= 0.5, (gold, bust)


def test_the_repricing_term_is_a_change_effect_not_a_level_effect():
    """Income escalation is proportional to x (permanent); cap-rate repricing is
    proportional to dx (transient). Modelling them with the same time signature
    is the single most common way to get this wrong (design 2.1). With inflation
    STEADY the repricing term contributes nothing."""
    steady = np.full(120, 6.5)
    x = inflation_excess(steady)
    d_x = np.diff(x, prepend=x[0])
    assert np.allclose(d_x[24:], 0.0, atol=1e-12)


def _anchored(path: Path) -> dict:
    doc = _load(path)
    _set_dotted(doc, "factor_conditions.inflation.average_pct", 2.0)
    doc["factor_conditions"]["crisis_windows"] = []
    return doc


@pytest.mark.parametrize("asset", ["pe", "re"])
def test_at6a_the_inflation_channel_is_inert_at_the_anchor(asset, monkeypatch):
    """AT-6a (pe/re half; pc joins in Task C5). Every new term is additive in
    x/d_x (LAMBDA*x, D*GAMMA*d_x), so x == 0 makes them vanish algebraically -
    that is the property under test, and it is exact, not statistical.

    DEVIATION from the plan's literal test body (recorded in the Task M3
    commit): the plan set only the DECLARED average to the anchor and expected
    "x == 0" from that alone. It does not - _inflation_path is a stochastic
    mean-REVERTING process (kappa=0.12, monthly noise std 0.28), so even with
    average_pct == C_ANCHOR and crisis cleared, the REALIZED trailing mean
    wanders around the anchor rather than sitting on it (measured: deflation_bust
    moved by up to 0.38pp/month on `re` under the literal test - a real,
    reproducible effect of the new terms firing on non-zero noise, not a
    determinism defect). inflation_excess is monkeypatched to return zero
    identically, forcing x (and therefore d_x) to exactly zero regardless of the
    realized path - the fixture never depended on inflation (pe/re/pc read no
    inflation term before this release), so it is still the correct reference
    under the patch. This tests the same claim the plan intended - the new
    terms are inert when x==0 - without the false premise."""
    monkeypatch.setattr(engine, "inflation_excess", lambda infl, **_: np.zeros_like(infl, dtype=np.float64))
    ref = np.load(ANCHOR_BASELINE_NPZ)
    for path in TOY_PRESETS:
        paths = run_path(project_numeric(load_worldspec(_anchored(path))), SEED)
        np.testing.assert_array_equal(
            paths.returns[asset], ref[f"{path.stem}/{asset}"], err_msg=f"{path.stem}/{asset}"
        )
