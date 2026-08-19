"""Generator→engine adapter (su-gen-01) — factor slabs into the toy contracts.

The Task 0 survey's smallest seam, implemented: resolve the world's generator
through ``ah.gen.registry``, sample it, and translate the 16-factor
``Ensemble`` into the SAME ``EnsembleResult``/``EnginePaths`` dataclasses the
toy engine emits — so digest, replay, twin, play, and bundle need no new
contracts. Everything downstream keys off ``asset_order``.

**Source-space rule (the 1974 console finding).** The first draft differenced
resampled LEVEL factors along the generated path, which fabricated enormous
moves at block seams (an -88.8% bond month; 21,755% mean inflation). Every
derived series is therefore computed once on the SOURCE panel and indexed by
the ensemble's ``row_indices``: a generated month's yield change, credit
move, or trailing inflation is that real month's own value. Nothing is ever
differenced across a seam, and every channel is bounded by real history.

Stated conventions (each is a modelling choice recorded here, not a fact):

* **Assets** (`GEN_ASSETS`): the toy tuple minus ``reits`` — OD-3: the 16
  factor set has no REIT factor and we do not invent a proxy.
* **equity / commodities**: the factor IS the asset; decimal→percent (x100).
* **bonds**: the duration-8.5 first-order convention (the sealed
  ``govt_tr_10y`` shape), computed in source space.
* **hy**: carry net of losses + spread duration (source space) + an equity
  sensitivity — ``(y10 + (1-LOSS)*hs)/12 - DUR_HY*delta(y10+hs) +
  BETA*equity`` in percent, with ``LOSS = 0.45`` mirroring the toy's
  ``_HY_LOSS_SHARE``, ``DUR_HY = 4.0`` and ``BETA = 0.4`` (without the beta
  the 1974 preview printed HY at a decade Sharpe of 2.18).
* **pe / pc / re** (true): the sealed PM sleeve loadings
  (``mappings/sleeve-mappings-v1.0.yaml``) applied at MONTHLY frequency with
  ``alpha_quarterly/3`` plus the artifact's own ``residual_sigma_annual``
  drawn at ``PCG64(seed + RESIDUAL_SEED_OFFSET)`` — a distinct, stated
  stream so residuals never replay the sampler's draws. Independent across
  the three sleeves (the sealed residual correlation covers HF sleeves
  only). Sleeve choice: ``PM_SLEEVE_FOR_ASSET``.
* **reported pe/pc/re**: the toy's quarter-end appraisal shape
  (``engine._reported_marks``), driven by the WorldSpec's own smoothing
  weights — the world stays the authority for its reporting behaviour.
* **rate**: ``policy_rate`` as-is (percent, the toy scale).
* **spread**: ``hy_spread`` percent→bps — the toy spread channel IS the HY
  spread in bps (play's 400bp reference, the feed's 800bp threshold). A
  level, resampled directly: real values, no differencing.
* **inflation**: the drawn source month's OWN trailing YoY (source rows with
  under a year of panel history annualize the available window; row 0 is 0).
* **crisis**: months whose realized regime label is ``CRI``
  (``RegimeRecord``) — bootstrap ignores ``factor_conditions`` by seal.
* **Seed rule**: path ``k`` is ``sample(world, 1, base_seed + 7919*k)`` — the
  platform stride, so ``run_gen_path(base+7919k)`` IS ensemble path ``k``
  and a path's identity is independent of ``n_paths`` (the toy invariant).
"""

from __future__ import annotations

import math

import numpy as np

from ah.core.engine import (
    _OMEGA_PC,
    ASSETS,
    INFLATION_ANCHOR_PCT,
    INFLATION_TRAIL_MONTHS,
    REPORTED_SLEEVES,
    EnginePaths,
    EnsembleResult,
    _reported_marks,
    inflation_excess,
)
from ah.core.numericworld import NumericWorld
from ah.gen import registry
from ah.port.mapping import load_artifact

SEED_STRIDE = 7919  # the platform rule; asserted equal to the engine's in tests
RESIDUAL_SEED_OFFSET = 104729  # the 10,000th prime: a distinct, stated stream

GEN_ASSETS: tuple[str, ...] = tuple(a for a in ASSETS if a != "reits")

PM_SLEEVE_FOR_ASSET: dict[str, str] = {
    "pe": "pm_buyout",
    "pc": "pm_direct_lending",
    "re": "pm_re_value_add",
    # ER-14 close-out (D-ER14-2, Task S4): pm_infra is ALREADY estimated in
    # the sealed v1.1 artifact (60 quarters, sum-beta(2)) -- no new
    # estimation needed for the generated plane (design 2.7.1).
    "infra": "pm_infra",
}
# residual column order, fixed. APPENDED at the end, matching the toy
# engine's own e_infra convention -- but see the FINDING below: unlike the
# toy plane's up-front draw block, widening THIS matrix is NOT bit-identity
# preserving for pe/pc/re.
_PM_ASSET_ORDER: tuple[str, ...] = ("pe", "pc", "re", "infra")

# FINDING (not in the design, Task S4): rng.standard_normal((months, N))
# fills ROW-MAJOR, so widening N from 3 to 4 re-rolls every column's draw,
# including pe/pc/re -- even though "infra" is appended LAST in
# _PM_ASSET_ORDER. AT-14's bit-identity claim is therefore SCOPED TO THE
# TOY PLANE, exactly as AT-14 words it ("on every preset"). The generated
# plane's digests move in this release regardless of this fact
# (GEN_PLAY_ALPHA_VERSION bumps and the played generated world moves
# ...603 -> ...604), so nothing is lost -- but it must be STATED, not
# discovered. Do NOT "fix" this by restructuring the draw into per-sleeve
# streams: that would be a second, unattributed numeric change in the same
# release (the ER-12 lesson).

_HY_LOSS_SHARE = 0.45  # mirrors the toy engine's convention
_HY_SPREAD_DURATION = 4.0  # stated; HY duration is shorter than govt 8.5
_HY_EQUITY_BETA = 0.4  # stated; real HY moves with equities (the 1974 preview
# had it at Sharpe 2.18 without this term)
_BOND_DURATION_YEARS = 8.5  # the sealed govt_tr_10y convention


class AdapterError(ValueError):
    """A world or ensemble the adapter cannot translate honestly."""


# OD-3: the reits start weight moves to equity — its 0.84-correlated public
# neighbour — leaving the private allocation exactly as designed. Two scales
# for two layers: GEN_START_MIX mirrors the toy institution's fractions;
# GEN_START_TARGETS mirrors the play layer's points-of-100 book (reits' 8
# points to equity; privates and cash untouched).
#
# ER-14 close-out (D-ER14-2, Task S4, A15): infra enters at 5 points. The
# generated book has no REITs to carve from, so the two points come from
# real estate (7 -> 5, mirroring the toy carve exactly) and the remaining
# three from equity (41 -> 38) -- private stays at 38 (pe 20 + pc 8 + re 5 +
# infra 5), matching play.START_TARGETS' own total.
GEN_START_TARGETS: dict[str, float] = {
    "equity": 38.0,
    "bonds": 12.0,
    "hy": 5.0,
    "commodities": 5.0,
    "pe": 20.0,
    "pc": 8.0,
    "re": 5.0,
    "infra": 5.0,
}

# Scores from generated worlds carry their OWN alpha stamp — a distinct
# value, not a bump of the toy one — so a leaderboard row can never mix
# engines (survey S3; the world_id block separation is the second fence).
# v5: ER-14 close-out (D-ER14-2, 2026-08-18) — the v1.2 mapping artifact's
# inflation channel (C1 extended to pm_buyout) and F5's Student-t/EWMA fixes
# change the generated plane's returns; distinct from PLAY_ALPHA_VERSION's
# own v5 bump (survey S3: never a shared bump, the two planes score
# different tapes).
GEN_PLAY_ALPHA_VERSION = "port-v5-inflation-gen"

# ER-14 close-out (D-ER14-2, Task S4, A15): infra 0.05, carved 0.02 from re
# and 0.03 from equity -- equity's resulting 0.32 matches
# institution.START_MIX['equity'] + START_MIX['reits'] (0.30 + 0.02)
# exactly, so OD-3's own invariant ("reits' weight moves to equity") still
# holds after the carve (test_gen_start_mix_moves_reits_weight_to_equity).
GEN_START_MIX: dict[str, float] = {
    "equity": 0.32,
    "bonds": 0.10,
    "hy": 0.05,
    "commodities": 0.05,
    "pe": 0.25,
    "pc": 0.10,
    "re": 0.08,
    "infra": 0.05,
}


def _declared_inflation_average_pct(world: NumericWorld) -> float:
    """``world.factor_conditions.inflation.average_pct``, defensively —
    mirrors ``ah.core.engine._f``'s (possibly-None sub-model, non-numeric
    attribute) fallback locally rather than importing a private helper."""
    model = world.factor_conditions.inflation
    if model is None:
        return 2.0  # ah.core.engine._DEF["infl_avg"]
    value = getattr(model, "average_pct", None)
    return float(value) if isinstance(value, (int, float)) else 2.0


def _source_series(source, world: NumericWorld) -> dict[str, np.ndarray]:
    """Per-row derived series on the SOURCE panel (each row a real month).

    Row 0 has no predecessor inside the panel: its change terms are zero and
    its trailing inflation is zero — a stated neutral, hit only when a block
    draws the panel's very first month.
    """
    names = list(source.factor_names)

    def col(n: str) -> np.ndarray:
        return np.asarray(source.values[:, names.index(n)], dtype=float)

    y10, ust2, ig = col("ust_10y"), col("ust_2y"), col("ig_spread")
    hs, cpi = col("hy_spread"), col("cpi")
    n_rows = y10.shape[0]

    y = y10 / 100.0
    bond = np.empty(n_rows)
    bond[0] = y[0] / 12.0
    bond[1:] = y[:-1] / 12.0 + _BOND_DURATION_YEARS * (y[:-1] - y[1:])

    all_in = y10 + (1.0 - _HY_LOSS_SHARE) * hs  # percent per annum
    wide = y10 + hs
    hy = np.empty(n_rows)
    hy[0] = all_in[0] / 12.0
    hy[1:] = all_in[:-1] / 12.0 + _HY_SPREAD_DURATION * (wide[:-1] - wide[1:])

    infl = np.zeros(n_rows)
    for r in range(1, n_rows):
        back = min(r, 12)
        infl[r] = ((cpi[r] / cpi[r - back]) ** (12.0 / back) - 1.0) * 100.0

    # ER-14 close-out (D-ER14-2, Task G2). The generated plane's inflation
    # STATE, alongside infl_pct (the 12-month REAL historical display series
    # above, left untouched — this is a new, separate regressor). Not a
    # per-row real CPI trail: bootstrap-v1 stratifies row selection by REGIME
    # LABEL only and structurally ignores factor_conditions (the crisis
    # channel's own documented rule elsewhere in this module), so a trail
    # built from the drawn rows' real history could never respond to a
    # world's declared inflation.average_pct, and AT-10's probe (the SAME
    # one-field variation AT-1 uses on the toy plane) would be dead on
    # arrival by construction. The only inflation signal a generated world
    # actually carries is its OWN declared average — the same anchor C1's
    # C_ANCHOR cites (goldilocks/prehistory's declared average) — so
    # cpi_trail_excess is ``inflation_excess`` (K = 24 months, port -> core,
    # Task M2) applied to that constant, held flat across the whole source
    # panel. Consumes no RNG.
    avg_pct = _declared_inflation_average_pct(world)
    cpi_trail_excess = inflation_excess(
        np.full(n_rows, avg_pct), k=INFLATION_TRAIL_MONTHS, anchor=INFLATION_ANCHOR_PCT
    )

    def d(x: np.ndarray) -> np.ndarray:
        return np.concatenate([[0.0], np.diff(x)])

    return {
        "bond_pct": bond * 100.0,
        "hy_pct": hy,
        "infl_pct": infl,
        "cpi_trail_excess": cpi_trail_excess,
        "d_level": d(y10),
        "d_slope": d(y10 - ust2),
        "d_ig": d(ig),
    }


def _source_of(gen):
    src = getattr(gen, "source", None)
    if src is None:
        raise AdapterError(
            f"generator '{gen.generator_id}' exposes no source panel; the adapter "
            "derives its series in source space and cannot proceed without one"
        )
    return src


def _pm_true_monthly_path(
    ensemble, rows: np.ndarray, series: dict[str, np.ndarray], seed: int
) -> dict[str, np.ndarray]:
    """Monthly TRUE percent returns for pe/pc/re/infra on one path: sealed
    loadings on source-space regressors, C1's inflation pass-through where
    the v1.2 artifact declares it, + the artifact's residual (stated
    stream)."""
    artifact = load_artifact()
    reg = {
        "equity_mkt": ensemble.factor("equity_mkt")[0],
        "smb": ensemble.factor("smb")[0],
        "hml": ensemble.factor("hml")[0],
        "mom": ensemble.factor("mom")[0],
        "d_level": series["d_level"][rows],
        "d_slope": series["d_slope"][rows],
        "d_ig": series["d_ig"][rows],
    }
    rng = np.random.Generator(np.random.PCG64(seed + RESIDUAL_SEED_OFFSET))

    # F5c (DN5 SS9 SM-8): standardised Student-t residuals, correlated across
    # the PM block by the artifact's declared matrix, rescaled by
    # sqrt(df/(df-2)) to unit variance so no declared residual_sigma_annual
    # moves (the ER-7 precedent verbatim). A v1.1-only artifact (no
    # pm_residuals block) falls back to the pre-F5c independent normal draw,
    # so this function does not hard-require v1.2.
    pmr = artifact.get("pm_residuals")
    if pmr is not None:
        df = float(pmr["df"])
        names = [PM_SLEEVE_FOR_ASSET[a] for a in _PM_ASSET_ORDER]
        corr = np.array([[float(pmr["block_correlation"][a][b]) for b in names] for a in names])
        chol = np.linalg.cholesky(corr)
        raw_t = rng.standard_t(df, size=(ensemble.months, len(_PM_ASSET_ORDER)))
        raw_t = raw_t / math.sqrt(df / (df - 2.0))
        shocks = raw_t @ chol.T
    else:
        shocks = rng.standard_normal((ensemble.months, len(_PM_ASSET_ORDER)))

    out: dict[str, np.ndarray] = {}
    for j, asset in enumerate(_PM_ASSET_ORDER):
        spec = artifact["pm_sleeves"][PM_SLEEVE_FOR_ASSET[asset]]
        r = np.full(ensemble.months, float(spec["alpha_quarterly"]) / 3.0)
        for name, beta in spec["loadings"].items():
            if float(beta) != 0.0:
                r = r + float(beta) * reg[name]
        passthrough = spec.get("inflation_passthrough")
        if passthrough and asset == "pe":
            # AT-10 (the AT-2/3 half): the SIGN rules transfer unchanged --
            # PE's toy-plane net (LAMBDA_PE - MU_PE) is NEGATIVE (R-9;
            # multiple compression dominates income pass-through). The v1.2
            # artifact declares a single pm_buyout coefficient (LAMBDA_PE,
            # the income HALF, reused so both planes share "one belief"
            # about the pass-through itself) and the generated plane has no
            # second authored term to net it against, so the declared
            # magnitude is applied here with the toy plane's NET sign
            # instead of the pass-through's own sign.
            r = r - float(passthrough["b_infl"]) * (series["cpi_trail_excess"][rows] / 12.0) / 100.0
        elif passthrough:
            # b_infl * (annual pp excess / 12) / 100 -- annual pp to monthly
            # decimal fraction, the same convention engine.py's own
            # LAMBDA_RE * x/12 (in percent) uses one level up.
            r = r + float(passthrough["b_infl"]) * (series["cpi_trail_excess"][rows] / 12.0) / 100.0
        elif asset == "pc":
            # AT-10 (the AT-4 half): pc still takes a loss bite, one-sided on
            # excess inflation, using the toy engine's own OMEGA_PC constant
            # (0.03, "fractional loss uplift per pp of excess") applied
            # directly to the shared cpi_trail_excess tape -- NOT through the
            # sealed v1.2 artifact's b_infl mechanism, which C1 does not
            # extend to pm_direct_lending. This is a sign-only placeholder:
            # C2's measured loss beta (the toy plane's theta_toy convexity
            # equivalent) is deferred on the Cliffwater CDLI export
            # (D-ER14-2, ask A7) and adopts on the generated plane when it
            # lands.
            r = r - _OMEGA_PC * np.maximum(0.0, series["cpi_trail_excess"][rows]) / 12.0 / 100.0
        sigma_m = float(spec["residual_sigma_annual"]) / np.sqrt(12.0)
        out[asset] = (r + shocks[:, j] * sigma_m) * 100.0
    return out


def run_gen_path(world: NumericWorld, seed: int) -> EnginePaths:
    """One generated history in the toy ``EnginePaths`` contract."""
    gen = registry.resolve_for_world(world)
    if gen.generator_id == "toy-v0":  # pragma: no cover - guarded upstream
        raise AdapterError("the adapter is for generated worlds; toy-v0 has its own engine")
    ensemble = gen.sample(world, 1, seed)
    if ensemble.row_indices is None:
        raise AdapterError(
            "ensemble carries no row_indices; source-space derivation is impossible "
            "and path-space differencing fabricates block-seam moves (the 1974 finding)"
        )
    rows = np.asarray(ensemble.row_indices)[0]
    series = _source_series(_source_of(gen), world)

    returns = {
        "equity": ensemble.factor("equity_mkt")[0] * 100.0,
        "commodities": ensemble.factor("commodities")[0] * 100.0,
        "bonds": series["bond_pct"][rows],
        "hy": series["hy_pct"][rows] + _HY_EQUITY_BETA * ensemble.factor("equity_mkt")[0] * 100.0,
    }
    returns.update(_pm_true_monthly_path(ensemble, rows, series, seed))
    reported = _reported_marks(world, returns)
    return EnginePaths(
        months=ensemble.months,
        seed=seed,
        rate=ensemble.factor("policy_rate")[0].copy(),
        spread=ensemble.factor("hy_spread")[0] * 100.0,
        inflation=series["infl_pct"][rows],
        crisis=_crisis_mask(ensemble, 0),
        returns=returns,
        reported=reported,
        asset_order=GEN_ASSETS,
    )


def _crisis_mask(ensemble, k: int) -> np.ndarray:
    regimes = ensemble.regimes
    labels = getattr(regimes, "labels", None)
    legend = getattr(regimes, "legend", None)
    if labels is None or legend is None:
        raise AdapterError("ensemble carries no regime record; the crisis channel would be a guess")
    legend = tuple(legend)
    if "CRI" not in legend:
        return np.zeros(ensemble.months)
    return (np.asarray(labels)[k] == legend.index("CRI")).astype(float)


def gen_hold_course_twin(world: NumericWorld, seed: int):
    """The passive benchmark over a generated path (institution unchanged)."""
    from ah.core.institution import simulate_institution

    return simulate_institution(run_gen_path(world, seed), None, start_mix=GEN_START_MIX)


def gen_lineage(world: NumericWorld) -> dict[str, str]:
    """The honest ``resolved_engine`` stamp for a generated run: what actually
    produced the numbers, pinned per OD-4 (generator + campaign vintage)."""
    gen = registry.resolve_for_world(world)
    meta = gen.sample(world, 1, 0).meta
    return {
        "generator_id": world.engine_defaults.generator_id,
        "generator_version": meta.generator_id,
        "campaign_vintage_id": meta.vintage_id,
    }


def run_gen_ensemble(world: NumericWorld, n_paths: int, *, base_seed: int) -> EnsembleResult:
    """A generated ensemble in the toy ``EnsembleResult`` contract.

    Stacked from per-path ``run_gen_path`` calls at the platform stride, so
    path identity is independent of ensemble size.
    """
    seeds = [base_seed + SEED_STRIDE * k for k in range(n_paths)]
    paths = [run_gen_path(world, s) for s in seeds]
    months = paths[0].months
    returns = {a: np.stack([p.returns[a] for p in paths], axis=0) for a in GEN_ASSETS}
    reported = {s: np.stack([p.reported[s] for p in paths], axis=0) for s in REPORTED_SLEEVES}
    return EnsembleResult(
        months=months,
        n_paths=n_paths,
        seeds=seeds,
        returns=returns,
        reported=reported,
        asset_order=GEN_ASSETS,
    )
