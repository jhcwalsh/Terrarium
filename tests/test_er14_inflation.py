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
    _DEF,
    _RATE_SHOCK_INFLATION_ANCHOR,
    INFLATION_ANCHOR_PCT,
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
    monkeypatch.setattr(
        engine, "inflation_excess", lambda infl, **_: np.zeros_like(infl, dtype=np.float64)
    )
    ref = np.load(ANCHOR_BASELINE_NPZ)
    for path in TOY_PRESETS:
        paths = run_path(project_numeric(load_worldspec(_anchored(path))), SEED)
        np.testing.assert_array_equal(
            paths.returns[asset], ref[f"{path.stem}/{asset}"], err_msg=f"{path.stem}/{asset}"
        )


# --------------------------------------------------------------------------- #
# Task M4: rider R1 - structural.real_estate.income_yield_pct
# --------------------------------------------------------------------------- #


def test_r1_income_yield_is_read_from_the_world():
    """R1 (A11, recommended in). The 4.5% income yield was hardcoded while the
    schema field structural.real_estate.income_yield_pct sat declared and dead
    (ER-14's unconsumed-field map). Schema range 2-8."""
    lo = annualised(probe(6.5, **{"structural.real_estate.income_yield_pct": 3.0}), "re")  # type: ignore[arg-type]
    hi = annualised(probe(6.5, **{"structural.real_estate.income_yield_pct": 7.0}), "re")  # type: ignore[arg-type]
    assert hi - lo == pytest.approx(4.0, abs=0.15)


def test_r1_changes_no_shipped_preset():
    """NO shipped preset declares income_yield_pct, so every preset is
    numerically unchanged by R1 - the cheapest honest repair in the package."""
    for path in TOY_PRESETS:
        doc = _load(path)
        assert "income_yield_pct" not in doc["structural"].get("real_estate", {}), path.stem


# --------------------------------------------------------------------------- #
# Task M5: private equity - nominal earnings vs multiple compression
# --------------------------------------------------------------------------- #


def test_at2_private_equity_differs_materially_across_inflation():
    """AT-2. |Delta annualised pe|, 1% -> 12%, >= 0.65 pp/yr (the asked net floor
    0.06 x the 11pp probe range). Today's measured value is EXACTLY 0.000: pe =
    1.4*eq + const, and equity carries no inflation term either."""
    delta = abs(annualised(probe(12.0), "pe") - annualised(probe(1.0), "pe"))
    assert delta >= 0.65, delta


def test_the_pe_net_floor_is_respected():
    """A3, ratified: |lambda_PE - mu_PE| >= 0.06, so no in-range combination can
    produce a near-zero net and quietly re-create ER-14 in weaker form."""
    assert abs(engine._LAMBDA_PE - engine._MU_PE) >= 0.06


def test_pe_responds_negatively_to_inflation():
    """Net PE = lambda_PE - mu_PE = -0.10 pp/yr per pp: a 12% world's private
    equity runs about 1.1 pp/yr below a 1% world's (design 2.2)."""
    assert annualised(probe(12.0), "pe") < annualised(probe(1.0), "pe")


def test_the_live_presets_no_longer_hand_author_the_inflation_drift():
    """A5. mu_PE makes multiple compression endogenous; leaving the authored
    -2.0 in place would charge it twice. The field now means NON-inflation
    multiple drift (secular dry-powder, sector re-rating)."""
    for stem in ("stagflation", "stagflation_1974"):
        doc = json.loads((PRESETS / f"{stem}.json").read_text(encoding="utf-8"))
        assert doc["structural"]["private_equity"]["entry_multiple_drift_annual_pct"] == 0.0


# --------------------------------------------------------------------------- #
# Task M6: the infrastructure return mechanism (pure function)
# --------------------------------------------------------------------------- #


def _flat_infra_kwargs(x_level: float, nm: int = 24) -> dict:
    return dict(
        x=np.full(nm, x_level),
        d_x=np.zeros(nm),
        d_rate=np.zeros(nm),
        eq=np.zeros(nm),
        e_infra=np.zeros(nm),
        crisis=np.zeros(nm),
        linkage=0.6,
        disc_shift_bps=0.0,
        yield_pct=5.0,
        nm=nm,
    )


def test_infra_escalator_is_the_declared_linkage_share():
    """lambda_INFRA is not a constant - it is
    structural.infrastructure.inflation_linkage, 'Share of revenues contractually
    inflation-linked', bounded 0-1. That IS the pass-through coefficient,
    definitionally (design 2.6)."""
    kw = _flat_infra_kwargs(x_level=4.5)
    hi = engine.infra_return(**{**kw, "linkage": 0.9}).mean() * 12
    lo = engine.infra_return(**{**kw, "linkage": 0.3}).mean() * 12
    assert (hi - lo) == pytest.approx((0.9 - 0.3) * 4.5, abs=0.05)


def test_infra_response_ratio_is_linear_in_the_linkage_share():
    """AT-12's property at the function level: the ratio of two worlds'
    inflation responses is the ratio of their declared linkages, 0.3/0.9 = 0.33."""
    base = _flat_infra_kwargs(x_level=0.0)
    hot = _flat_infra_kwargs(x_level=4.5)

    def resp(k: float) -> float:
        return (
            engine.infra_return(**{**hot, "linkage": k}).mean()
            - engine.infra_return(**{**base, "linkage": k}).mean()
        )

    assert resp(0.3) / resp(0.9) == pytest.approx(0.333, abs=0.05)


def test_infra_reprices_less_than_property_for_the_same_acceleration():
    """gamma_INFRA 0.30 on a 4.0 duration charges -1.2 x dx against real estate's
    -2.0 x dx. Infrastructure both earns more from sustained inflation and is
    marked down less when inflation surges - the class's investment case, and the
    design reproduces both without either being asserted."""
    assert engine._D_INFRA * engine._GAMMA_INFRA < engine._D_RE * engine._GAMMA_RE


def test_infra_reads_the_discount_rate_shift_field():
    """structural.infrastructure.discount_rate_shift_bps was declared and dead
    (the second half of ER-14's most quotable line)."""
    kw = _flat_infra_kwargs(x_level=0.0)
    assert (
        engine.infra_return(**{**kw, "disc_shift_bps": 300.0}).sum()
        < engine.infra_return(**kw).sum()
    )


def test_infra_uses_the_transplanted_pm_infra_constants():
    """beta_INFRA and sigma_INFRA come straight out of the sealed pm_infra row in
    sleeve-mappings-v1.1.yaml: equity_mkt 0.3337 and residual_sigma_annual 0.0569,
    which at monthly resolution is 0.0569/sqrt(12) = 1.64%. Label: chosen
    (transplanted from a measured row)."""
    import yaml

    row = yaml.safe_load(Path("mappings/sleeve-mappings-v1.1.yaml").read_text())["pm_sleeves"][
        "pm_infra"
    ]
    assert pytest.approx(row["loadings"]["equity_mkt"], abs=0.005) == engine._BETA_INFRA
    assert (
        pytest.approx(row["residual_sigma_annual"] / math.sqrt(12) * 100, abs=0.02)
        == engine._SIGMA_INFRA
    )


# --------------------------------------------------------------------------- #
# Task C1: private credit's floating coupon (phi_PC)
# --------------------------------------------------------------------------- #


def test_at5_the_floating_benefit_is_visible_when_the_policy_rate_moves():
    """AT-5, as RESTATED and ratified (A10). D-ER14-1 asked that PC's floating
    benefit be visible; measuring that by varying INFLATION with rates pinned asks
    the coupon to respond to something it is not connected to, and would fail a
    correct model. So: +2 pp on policy_rate.end_pct, all else held, must lift
    annualised pc by >= +0.80 pp/yr (a glide ending 2pp higher raises the mean
    policy rate ~1pp, which is ~1 pp/yr of coupon; 0.80 leaves room for the loss
    side to offset)."""
    base = annualised(probe(6.5), "pc")
    up = annualised(probe(6.5, **{"factor_conditions.policy_rate.end_pct": 9.5}), "pc")  # type: ignore[arg-type]
    assert up - base >= 0.80, up - base


def test_phi_pc_measures_excess_against_the_worlds_own_declared_average():
    """The asymmetry with RE and PE is the whole point (design 2.3). Property and
    buyout have NO authored inflation channel anywhere in the WorldSpec, so their
    excess is measured against the platform anchor. Private credit's level is
    already authored through factor_conditions.policy_rate; measuring its excess
    against C_ANCHOR would charge stagflation the benefit twice and print a
    ~12%/yr private credit book. Only the WITHIN-world dynamics change."""
    ens_lo, ens_hi = probe(1.0), probe(12.0)
    # a 12x change in the DECLARED average must not move the coupon term's mean
    # by anything like 11pp/12: the coupon tracks deviations from that average.
    assert abs(annualised(ens_hi, "pc") - annualised(ens_lo, "pc")) < 2.0


# --------------------------------------------------------------------------- #
# Task C2: the borrower-coverage squeeze (omega_PC)
# --------------------------------------------------------------------------- #


def test_at4_the_loss_bite_is_negative_under_the_rates_held_probe():
    """AT-4. Delta annualised pc, 1% -> 12%, rates HELD, must be <= -0.30 pp/yr.
    Today's measured value is +0.022. A lender whose rate does not rise while its
    borrowers' costs do is in trouble - that is the whole content of the test."""
    delta = annualised(probe(12.0), "pc") - annualised(probe(1.0), "pc")
    assert delta <= -0.30, delta


def test_the_squeeze_is_one_sided_at_the_anchor(monkeypatch):
    """max(0, x): deflation does not squeeze borrower coverage through INPUT
    costs - it squeezes it through revenue, a different channel, deliberately not
    modelled (design 4, the mirror). So on deflation_bust the term is inert, and
    zeroing omega_PC changes nothing."""
    bust = annualised(ensemble_of("deflation_bust"), "pc")
    monkeypatch.setattr(engine, "_OMEGA_PC", 0.0)
    assert annualised(ensemble_of("deflation_bust"), "pc") == pytest.approx(bust, abs=1e-12)


def test_inflation_stress_never_exceeds_the_engines_own_crisis_stress():
    """omega_PC's value is derived from a BOUNDING rule, not picked: the schema
    caps inflation.average_pct at 20 (x_max = 18) and _CRISIS_LOSS_AMPLIFIER is
    1.6, so omega_PC <= 0.6/18 = 0.033."""
    assert engine._OMEGA_PC <= (engine._CRISIS_LOSS_AMPLIFIER - 1.0) / 18.0


# --------------------------------------------------------------------------- #
# Task C3: the C2 convexity, decoupled from CDLI (theta_toy)
# --------------------------------------------------------------------------- #


def _pc_at(peak_bps: float, **extra) -> float:
    """Annualised pc on a calm-inflation world whose HY spread peak is set."""
    return annualised(
        probe(2.0, **{"factor_conditions.credit.hy_spread_peak_bps": peak_bps, **extra}), "pc"
    )


def test_theta_is_additive_never_a_replacement():
    """C2's bare form implies ZERO loss below the median spread. Substituting it
    for the toy engine's through-cycle loss would delete ER-1's close-out and hand
    private credit back the Sharpe near 2 that ER-1 and ER-4 were written to
    remove. The convex term is ADDED on top of the existing linear loss - so below
    s_bar the world's declared annual_loss_rate_pct still bites, hard."""
    lo = _pc_at(350.0, **{"structural.private_credit.annual_loss_rate_pct": 0.5})  # type: ignore[arg-type]
    hi = _pc_at(350.0, **{"structural.private_credit.annual_loss_rate_pct": 5.0})  # type: ignore[arg-type]
    assert lo - hi > 2.0


def test_theta_is_convex_above_the_engines_own_spread_reference():
    """s_bar = _SPREAD_REFERENCE_BPS = 400, documented in place as 'the spread a
    normal credit market prices' - no new constant, and it plays exactly the role
    C2's s_bar plays. Each extra 200bp of peak spread must cost MORE when spreads
    are already wide than when they are near the reference."""
    near = _pc_at(400.0) - _pc_at(600.0)
    wide = _pc_at(1600.0) - _pc_at(1800.0)
    assert wide > near


def test_theta_toy_is_the_ratified_declared_value_pending_cdli():
    """D-ER14-2: CDLI decoupled - the convexity ships DECLARED at 0.10 and C2's
    measured half awaits the Cliffwater export. Anchor: _HY_LOSS_SHARE 0.45 x the
    engine's own pc/hy spread-sensitivity ratio (0.8/3.5 = 0.229) = 0.103."""
    assert engine._THETA_TOY == 0.10
    assert engine._THETA_TOY == pytest.approx(engine._HY_LOSS_SHARE * (0.8 / 3.5), abs=0.005)


def test_private_credit_has_not_recovered_its_pre_er1_sharpe():
    """ER-1/ER-4 regression guard: the convex term must not be a net GIFT.
    Decade Sharpe of pc on the stagflation preset stays well under 2.0."""
    assert sharpe(probe(6.5), "pc") < 1.5
