"""WP2.8 losses — the generative objective interface + the D4 tail auxiliary.

Two halves, both shared with WP2.9's flow-matching variant behind the same
interfaces:

1. **The generative objective.** :class:`GenerativeObjective` is the protocol a
   sampler family implements — a per-batch differentiable ``training_loss`` and
   a trial-comparable ``validation_objective``. WP2.8's EDM denoising
   score-matching implementation lives in :mod:`ah.gen.blocks.diffusion`
   (:class:`~ah.gen.blocks.diffusion.EdmObjective`); WP2.9 adds a
   velocity-matching implementation behind the identical protocol. The
   validation objective is evaluated on a FIXED sigma grid with FIXED noise
   (:data:`VAL_SIGMA_GRID`, stated in the committed search-space config), so it
   is comparable across trials whose *training* sigma distributions differ — a
   trial may not choose the ruler it is measured with.

2. **The D4 tail-elicitability auxiliary** (DN-1.1 §II.4: ``L = L_gen +
   lambda_tail*L_VaR/ES``), in the WP2.2c-CORRECTED direction recorded in the sealed
   conventions: (VaR, ES) are estimated from the GENERATED sample and scored
   against the comparison REALIZATIONS with the Fissler-Ziegel joint scoring
   function — never the reverse, which is minimized by a generator emitting
   identically zero. Implemented locally in torch (differentiable); this module
   NEVER imports ``ah.eval`` (AST-enforced) — the strategy definitions come
   from ``ah.strategies`` (top-level, sealed, importable by gen).

Strategy evaluability at block scale (recorded): of the five sealed D4
strategies, ``eqw_factors`` and ``endowment_proxy`` are unevaluable on the
campaign vintage (sealed ``uncomputable_d4_strategies`` — commodities /
credit_xs_hy legs have no data), and ``momentum`` (12-1, lookback 12) is
STRUCTURALLY DEGENERATE on an L=6 block: every month of the block is inside its
sealed warm-up window, so its return is identically 0.0 and its (VaR, ES) pair
carries no information. The auxiliary therefore runs on ``sixty_forty`` and
``carry`` — both fully reconstructible from the sealed weights/params, both
holding legs through the sealed derived series. Warm-up inside a block: month 0
of a block has no prior month for the derived-series lag, so strategy returns
are computed on months 1..L-1 of each block, identically for generated and real
blocks (symmetric estimator, no fake zeros diluting the tail).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import torch

from ah.gen.joinery.waypoints import JoineryError
from ah.strategies import (
    Strategy,
    load_conventions,
    load_d4_strategies,
    load_derived_series,
)

__all__ = [
    "VAL_SIGMA_GRID",
    "CompiledStrategy",
    "GenerativeObjective",
    "compile_block_strategies",
    "fz_score_torch",
    "gen_var_es_torch",
    "strategy_returns_torch",
    "tail_auxiliary_torch",
    "tail_auxiliary_validation",
]

#: The fixed validation sigma grid (comparable across trials; see module docstring).
VAL_SIGMA_GRID: tuple[float, ...] = tuple(float(s) for s in np.geomspace(0.05, 5.0, 8))

#: Sealed elicitability level (pre-registration ``elicitability_score_estimator``).
TAIL_LEVEL = 0.95

#: Validation-side penalty when a generated ES magnitude is not positive (the
#: strategy's generated losses never reach a positive tail) — stated in advance;
#: the WP2.2 anti-gaming rule: absence must never score better than presence.
NONPOSITIVE_ES_PENALTY = 10.0

_ES_TRAIN_FLOOR = 1e-6  # training-side clamp keeping the FZ score finite + coercive


class GenerativeObjective(Protocol):
    """What tuning/training require of a sampler family's objective (3a and 3b)."""

    def training_loss(
        self, x: torch.Tensor, cond: torch.Tensor, generator: torch.Generator
    ) -> torch.Tensor: ...

    def validation_objective(self, x: torch.Tensor, cond: torch.Tensor) -> float: ...


# --------------------------------------------------------------------------- #
# D4 strategies compiled to block-scale torch terms (sealed sources, local math)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Term:
    """One leg: ``weight` times a series resolved from the block panel.

    ``kind`` "factor" reads the factor column directly (return-bearing);
    "bond_total_return" / "spread_excess_return" apply the sealed derived-series
    transform to the source LEVEL column: r_t = p2d*(y_{t-1}/mpy - D*(y_t -
    y_{t-1})), with p2d/mpy from the sealed conventions.
    """

    weight: float
    kind: str
    column: int
    duration: float = 0.0


@dataclass(frozen=True)
class CompiledStrategy:
    strategy_id: str
    terms: tuple[_Term, ...]


def _resolve_leg(
    leg: str,
    weight: float,
    names: list[str],
    derived: dict[str, object],
    conventions_return_bearing: frozenset[str],
) -> _Term | None:
    if leg in names and leg in conventions_return_bearing:
        return _Term(weight=weight, kind="factor", column=names.index(leg))
    d = derived.get(leg)
    if d is not None:
        src = d.source_factor  # type: ignore[attr-defined]
        if src in names:
            params = dict(d.params)  # type: ignore[attr-defined]
            duration = float(params.get("duration_years", params.get("spread_duration_years", 0.0)))
            return _Term(
                weight=weight,
                kind=str(d.transform),  # type: ignore[attr-defined]
                column=names.index(src),
                duration=duration,
            )
    return None


def compile_block_strategies(
    factor_names: tuple[str, ...],
    block_months: int,
) -> tuple[tuple[CompiledStrategy, ...], dict[str, str]]:
    """Compile the sealed D4 set to block-scale terms; return (compiled, excluded).

    Everything is read from the sealed ``pre-registration.yaml`` objects
    (:func:`ah.strategies.load_d4_strategies` etc.) — no weight, duration or
    parameter is restated here. ``excluded`` maps strategy_id -> recorded reason.
    """
    strategies = load_d4_strategies()
    derived = dict(load_derived_series())
    conventions = load_conventions()
    names = list(factor_names)

    compiled: list[CompiledStrategy] = []
    excluded: dict[str, str] = {}
    for strategy in strategies:
        reason = _compile_one(strategy, names, derived, conventions, block_months, compiled)
        if reason is not None:
            excluded[strategy.strategy_id] = reason
    if not compiled:
        raise JoineryError("no D4 strategy is evaluable at block scale; auxiliary undefined")
    return tuple(compiled), excluded


def _compile_one(
    strategy: Strategy,
    names: list[str],
    derived: dict[str, object],
    conventions,
    block_months: int,
    out: list[CompiledStrategy],
) -> str | None:
    """Compile one strategy into ``out``; return an exclusion reason instead if any."""
    if strategy.kind == "rule" and strategy.rule == "momentum_12_1":
        lookback = int(strategy.lookback or 0)
        if lookback + 1 > block_months:
            return (
                f"structurally degenerate at block scale: sealed warm-up (lookback "
                f"{lookback}) covers every month of an L={block_months} block, so the "
                f"strategy return is identically 0.0 within any block"
            )
    if strategy.kind == "rule" and strategy.rule == "term_structure_carry":
        legs = {
            str(strategy.params["long_series"]): float(strategy.params["long_weight"]),
            str(strategy.params["funding_series"]): float(strategy.params["funding_weight"]),
        }
    elif strategy.kind == "static_weights":
        legs = {leg: float(w) for leg, w in strategy.weights.items()}
    else:
        return f"rule '{strategy.rule}' has no block-scale compilation"

    terms: list[_Term] = []
    for leg, weight in legs.items():
        term = _resolve_leg(leg, weight, names, derived, conventions.return_bearing_factors)
        if term is None:
            return (
                f"leg '{leg}' resolves to no generated factor (sealed missing_factors / "
                f"uncomputable_d4_strategies)"
            )
        terms.append(term)
    out.append(CompiledStrategy(strategy_id=strategy.strategy_id, terms=tuple(terms)))
    return None


def strategy_returns_torch(
    blocks_units: torch.Tensor,
    compiled: CompiledStrategy,
) -> torch.Tensor:
    """Realized returns of one compiled strategy on ``(B, L, F)`` blocks in units.

    Returns ``(B, L-1)`` — months 1..L-1 of each block (month 0 has no prior
    month for the derived-series lag; see the module docstring). Differentiable.
    """
    conventions = load_conventions()
    p2d = float(conventions.percent_to_decimal)
    mpy = float(conventions.months_per_year)
    total = None
    for term in compiled.terms:
        col = blocks_units[:, :, term.column]
        if term.kind == "factor":
            r = col[:, 1:]
        elif term.kind in ("bond_total_return", "spread_excess_return"):
            prev, curr = col[:, :-1], col[:, 1:]
            r = p2d * (prev / mpy - term.duration * (curr - prev))
        else:  # pragma: no cover - compile_block_strategies only emits the above
            raise JoineryError(f"unknown term kind '{term.kind}'")
        total = term.weight * r if total is None else total + term.weight * r
    assert total is not None
    return total


# --------------------------------------------------------------------------- #
# the corrected elicitability direction, differentiable
# --------------------------------------------------------------------------- #


def gen_var_es_torch(
    returns: torch.Tensor, level: float = TAIL_LEVEL
) -> tuple[torch.Tensor, torch.Tensor]:
    """(VaR, ES) loss magnitudes of the GENERATED sample, pooled, differentiable."""
    losses = -returns.reshape(-1)
    var = torch.quantile(losses, level)
    tail = losses[losses >= var]
    es = tail.mean() if tail.numel() > 0 else var
    return var, es


def fz_score_torch(
    real_returns: torch.Tensor,
    var: torch.Tensor,
    es: torch.Tensor,
    level: float = TAIL_LEVEL,
) -> torch.Tensor:
    """Fissler-Ziegel score of forecast (var, es) against REAL realizations.

    The exact sealed functional form (G1 = 0, G2 = 1/es), positive-loss
    convention, lower is better: s_t = 1{L>=var}(L-var)/(alpha*es) + var/es +
    ln(es) - 1, mean over pooled real observations. The REALIZATIONS are the
    fixed argument and the GENERATED pair is under judgement — the Tail-GAN
    direction the WP2.2c correction mandates.
    """
    alpha = 1.0 - level
    losses = -real_returns.reshape(-1)
    indicator = (losses >= var).to(losses.dtype)
    tail_term = (indicator * (losses - var)).mean() / (alpha * es)
    return tail_term + var / es + torch.log(es) - 1.0


def tail_auxiliary_torch(
    gen_blocks_units: torch.Tensor,
    real_blocks_units: torch.Tensor,
    compiled: tuple[CompiledStrategy, ...],
    level: float = TAIL_LEVEL,
) -> torch.Tensor:
    """TRAINING auxiliary: mean FZ score over evaluable strategies, differentiable.

    ES is clamped at a small positive floor so the score stays finite when a
    degenerate early-training sample has a non-positive generated tail — the
    score is then enormous, pushing the generated tail toward the data's, which
    is the coercive direction (the validation-side rule uses the exact sealed
    NaN convention instead; see :func:`tail_auxiliary_validation`).
    """
    scores = []
    for strat in compiled:
        gen_r = strategy_returns_torch(gen_blocks_units, strat)
        real_r = strategy_returns_torch(real_blocks_units, strat)
        var, es = gen_var_es_torch(gen_r, level)
        scores.append(fz_score_torch(real_r, var, es.clamp_min(_ES_TRAIN_FLOOR), level))
    return torch.stack(scores).mean()


def tail_auxiliary_validation(
    gen_blocks_units: np.ndarray,
    real_blocks_units: np.ndarray,
    compiled: tuple[CompiledStrategy, ...],
    level: float = TAIL_LEVEL,
) -> tuple[float, dict[str, float]]:
    """VALIDATION auxiliary (the second sealed S term): exact rule, numpy.

    A strategy whose generated ES magnitude is not positive contributes
    :data:`NONPOSITIVE_ES_PENALTY` (stated in advance; anti-gaming). Returns the
    mean and the per-strategy scores.
    """
    gen_t = torch.as_tensor(gen_blocks_units, dtype=torch.float64)
    real_t = torch.as_tensor(real_blocks_units, dtype=torch.float64)
    per: dict[str, float] = {}
    for strat in compiled:
        gen_r = strategy_returns_torch(gen_t, strat)
        real_r = strategy_returns_torch(real_t, strat)
        var, es = gen_var_es_torch(gen_r, level)
        if float(es) <= 0.0:
            per[strat.strategy_id] = NONPOSITIVE_ES_PENALTY
        else:
            per[strat.strategy_id] = float(fz_score_torch(real_r, var, es, level))
    return float(np.mean(list(per.values()))), per
