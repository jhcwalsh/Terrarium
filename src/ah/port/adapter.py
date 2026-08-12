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

import numpy as np

from ah.core.engine import (
    ASSETS,
    REPORTED_SLEEVES,
    EnginePaths,
    EnsembleResult,
    _reported_marks,
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
}
_PM_ASSET_ORDER: tuple[str, ...] = ("pe", "pc", "re")  # residual column order, fixed

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
GEN_START_TARGETS: dict[str, float] = {
    "equity": 41.0,
    "bonds": 12.0,
    "hy": 5.0,
    "commodities": 5.0,
    "pe": 20.0,
    "pc": 8.0,
    "re": 7.0,
}

GEN_START_MIX: dict[str, float] = {
    "equity": 0.35,
    "bonds": 0.10,
    "hy": 0.05,
    "commodities": 0.05,
    "pe": 0.25,
    "pc": 0.10,
    "re": 0.10,
}


def _source_series(source) -> dict[str, np.ndarray]:
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

    def d(x: np.ndarray) -> np.ndarray:
        return np.concatenate([[0.0], np.diff(x)])

    return {
        "bond_pct": bond * 100.0,
        "hy_pct": hy,
        "infl_pct": infl,
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
    """Monthly TRUE percent returns for pe/pc/re on one path: sealed loadings
    on source-space regressors + the artifact's residual sigma (stated stream)."""
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
    shocks = rng.standard_normal((ensemble.months, len(_PM_ASSET_ORDER)))
    out: dict[str, np.ndarray] = {}
    for j, asset in enumerate(_PM_ASSET_ORDER):
        spec = artifact["pm_sleeves"][PM_SLEEVE_FOR_ASSET[asset]]
        r = np.full(ensemble.months, float(spec["alpha_quarterly"]) / 3.0)
        for name, beta in spec["loadings"].items():
            if float(beta) != 0.0:
                r = r + float(beta) * reg[name]
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
    series = _source_series(_source_of(gen))

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
