"""WP2.8 losses tests — sealed-strategy parity, corrected elicitability direction."""

from __future__ import annotations

import numpy as np
import pytest
import torch

# Tests MAY import ah.eval (the src-side AST ban covers ah.gen only): parity with
# the sealed judged implementations is exactly what these tests exist to prove.
from ah.eval.metrics.tails import elicitability_score, strategy_returns, var_es
from ah.gen.base import Ensemble, EnsembleMeta
from ah.gen.blocks import losses as ls
from ah.gen.bootstrap import FACTOR_SET
from ah.strategies import load_d4_strategies, load_derived_series


@pytest.fixture(scope="module")
def compiled():
    return ls.compile_block_strategies(FACTOR_SET, block_months=6)


def _random_blocks(n: int, seed: int) -> np.ndarray:
    """(n, 6, 12) blocks in plausible factor units."""
    rng = np.random.Generator(np.random.PCG64(seed))
    out = np.empty((n, 6, len(FACTOR_SET)))
    for j, name in enumerate(FACTOR_SET):
        if name in ("equity_mkt", "smb", "hml", "mom"):
            out[..., j] = 0.04 * rng.standard_normal((n, 6))
        elif name == "cpi":
            out[..., j] = np.exp(0.002 * np.cumsum(rng.standard_normal((n, 6)), axis=1))
        elif name == "equity_vol":
            out[..., j] = 15.0 + 5.0 * rng.random((n, 6))
        else:
            out[..., j] = 2.0 + rng.standard_normal((n, 6)).cumsum(axis=1) * 0.2
    return out


class TestCompilation:
    def test_evaluable_set_and_recorded_exclusions(self, compiled):
        """Campaign-3 (AM-2026-08-10-001) flipped this: through campaign-2 the
        compiled set was {sixty_forty, carry} with eqw_factors and
        endowment_proxy excluded as the two sealed uncomputable strategies.
        Commodities joining FACTOR_SET (ruling K2 + the owner's emission
        ruling) makes both compilable, so only block-scale-degenerate momentum
        remains excluded -- the assertion is updated to the new truth rather
        than relaxed."""
        strategies, excluded = compiled
        ids = {s.strategy_id for s in strategies}
        assert ids == {"sixty_forty", "carry", "eqw_factors", "endowment_proxy"}
        assert set(excluded) == {"momentum"}
        assert "degenerate at block scale" in excluded["momentum"]

    def test_nothing_is_hard_coded_weights_come_from_the_seal(self, compiled):
        strategies, _ = compiled
        sealed = {s.strategy_id: s for s in load_d4_strategies()}
        sixty = next(s for s in strategies if s.strategy_id == "sixty_forty")
        weights = sorted(t.weight for t in sixty.terms)
        assert weights == sorted(float(w) for w in sealed["sixty_forty"].weights.values())
        carry = next(s for s in strategies if s.strategy_id == "carry")
        assert sorted(t.weight for t in carry.terms) == [-1.0, 1.0]


class TestStrategyReturnParity:
    """The torch block implementation must equal the sealed ah.eval implementation."""

    @pytest.mark.parametrize("strategy_id", ["sixty_forty", "carry"])
    def test_matches_sealed_strategy_returns_on_months_1_to_5(self, compiled, strategy_id):
        strategies, _ = compiled
        blocks = _random_blocks(16, seed=3)
        mine = ls.strategy_returns_torch(
            torch.as_tensor(blocks, dtype=torch.float64),
            next(s for s in strategies if s.strategy_id == strategy_id),
        ).numpy()

        # Sealed implementation on an Ensemble whose paths are the blocks.
        ensemble = Ensemble(
            paths=blocks,
            factor_names=list(FACTOR_SET),
            meta=EnsembleMeta(generator_id="test", vintage_id="t", seed=0, n_paths=16, months=6),
        )
        sealed = {s.strategy_id: s for s in load_d4_strategies()}
        theirs = strategy_returns(ensemble, sealed[strategy_id], load_derived_series())
        # Month 0 is warm-up (0.0) in the sealed path; the block path starts at month 1.
        np.testing.assert_allclose(mine, theirs[:, 1:], rtol=1e-12, atol=1e-14)


class TestElicitability:
    def test_fz_score_matches_sealed_elicitability_score(self):
        rng = np.random.Generator(np.random.PCG64(5))
        real = rng.standard_normal(4000) * 0.03
        var, es = 0.05, 0.07
        mine = float(
            ls.fz_score_torch(
                torch.as_tensor(real, dtype=torch.float64),
                torch.tensor(var, dtype=torch.float64),
                torch.tensor(es, dtype=torch.float64),
            )
        )
        assert mine == pytest.approx(elicitability_score(real, var, es), rel=1e-12)

    def test_gen_var_es_matches_sealed_var_es(self):
        rng = np.random.Generator(np.random.PCG64(7))
        r = rng.standard_normal(5000) * 0.04
        var_t, es_t = ls.gen_var_es_torch(torch.as_tensor(r, dtype=torch.float64))
        var_s, es_s = var_es(r, 0.95)
        # torch.quantile and np.quantile share the linear-interpolation default.
        assert float(var_t) == pytest.approx(var_s, rel=1e-10)
        # ES tails may differ by the boundary observation under interpolation;
        # both must agree when the cut lands on an observation.
        assert float(es_t) == pytest.approx(es_s, rel=5e-2)

    def test_direction_is_corrected_zero_generator_scores_worse(self, compiled):
        """The WP2.2c anti-gaming property ON THE LOCAL IMPLEMENTATION: a
        generator emitting identically zero must score WORSE than one matching
        the real distribution — the training-side clamp keeps it finite but huge."""
        strategies, _ = compiled
        real = _random_blocks(256, seed=11)
        matching = _random_blocks(256, seed=12)
        zeros = real.copy()
        for j, name in enumerate(FACTOR_SET):
            if name in ("equity_mkt", "smb", "hml", "mom"):
                zeros[..., j] = 0.0
            elif name in ("ust_10y", "policy_rate"):
                zeros[..., j] = 3.0  # constant levels -> zero derived returns
        real_t = torch.as_tensor(real, dtype=torch.float64)
        aux_matching = float(
            ls.tail_auxiliary_torch(
                torch.as_tensor(matching, dtype=torch.float64), real_t, strategies
            )
        )
        aux_zero = float(
            ls.tail_auxiliary_torch(torch.as_tensor(zeros, dtype=torch.float64), real_t, strategies)
        )
        assert aux_zero > aux_matching + 1.0

    def test_validation_rule_penalizes_nonpositive_es(self, compiled):
        strategies, _ = compiled
        real = _random_blocks(64, seed=13)
        zeros = np.zeros_like(real)
        zeros[..., list(FACTOR_SET).index("cpi")] = 1.0
        zeros[..., list(FACTOR_SET).index("equity_vol")] = 15.0
        mean, per = ls.tail_auxiliary_validation(zeros, real, strategies)
        assert mean == pytest.approx(ls.NONPOSITIVE_ES_PENALTY)
        assert all(v == ls.NONPOSITIVE_ES_PENALTY for v in per.values())

    def test_training_auxiliary_is_differentiable_toward_the_tail(self, compiled):
        strategies, _ = compiled
        real = _random_blocks(128, seed=17)
        gen = torch.as_tensor(_random_blocks(128, seed=19), dtype=torch.float64)
        gen.requires_grad_(True)
        aux = ls.tail_auxiliary_torch(gen, torch.as_tensor(real, dtype=torch.float64), strategies)
        aux.backward()
        assert gen.grad is not None
        assert bool(torch.isfinite(gen.grad).all())
        assert bool((gen.grad != 0).any())
