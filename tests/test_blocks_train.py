"""WP2.8 train tests — CPU smoke train, bit-determinism, checkpoint identity."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ah.gen.blocks import data as bd
from ah.gen.blocks import diffusion as df
from ah.gen.blocks import losses as ls
from ah.gen.blocks import train as tr
from ah.gen.joinery import bridge
from joinery_common import make_climate_artifact, make_source

TINY = df.DiffusionConfig(
    d_model=32,
    n_layers=1,
    n_heads=2,
    batch_size=16,
    eval_nfe=5,
    aux_nfe=3,
    lambda_tail=0.1,
    aux_every=2,
    lr=1e-3,
)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    source = make_source(n_rows=240)
    climate = make_climate_artifact(
        tmp_path_factory.mktemp("clim-train"), t_months=480, state_noise=0.05
    )
    return bd.build_dataset(source, climate, validation_start_date="2005-01-01")


@pytest.fixture(scope="module")
def result(dataset):
    return tr.train_diffusion(
        dataset,
        TINY,
        seed=11,
        max_steps=30,
        eval_every=15,
        patience=10,
        device="cpu",
        n_rep_eval=2,
    )


class TestSmokeTrain:
    def test_runs_and_records_everything(self, result):
        assert result.steps_run == 30
        assert result.best_step in (15, 30)
        assert np.isfinite(result.best_s)
        assert len(result.per_fold_gen) == 3 and len(result.per_fold_aux) == 3
        assert result.checkpoint_hash and result.config_hash.startswith("cfg:")
        assert len(result.history) == 2

    def test_training_reduces_the_generative_objective_vs_init(self, dataset, result):
        init_model = df.ConditionalDenoiser(TINY)
        torch.manual_seed(0)
        compiled, _ = ls.compile_block_strategies(dataset.factor_names, dataset.block_months)
        init_scores = tr.evaluate_fold_scores(init_model, dataset, compiled, n_rep=2, device="cpu")
        assert result.best_gen_term < init_scores["gen_term"]

    def test_early_stopping_metric_is_the_sealed_s(self, result):
        expected = float(np.mean(result.per_fold_gen)) + tr.SELECTION_LAMBDA * float(
            np.mean(result.per_fold_aux)
        )
        assert result.best_s == pytest.approx(expected, rel=1e-12)


class TestDeterminism:
    def test_same_seed_bit_identical_checkpoint_on_cpu(self, dataset, result):
        again = tr.train_diffusion(
            dataset,
            TINY,
            seed=11,
            max_steps=30,
            eval_every=15,
            patience=10,
            device="cpu",
            n_rep_eval=2,
        )
        assert again.checkpoint_hash == result.checkpoint_hash
        assert again.best_s == result.best_s

    def test_different_seed_differs(self, dataset, result):
        other = tr.train_diffusion(
            dataset,
            TINY,
            seed=12,
            max_steps=4,
            eval_every=4,
            patience=10,
            device="cpu",
            n_rep_eval=1,
        )
        assert other.checkpoint_hash != result.checkpoint_hash


class TestCheckpoint:
    def test_save_load_round_trip_verifies_hash(self, dataset, result, tmp_path):
        path = tmp_path / "ck.pt"
        meta = tr.save_checkpoint(result, dataset, path, extra_meta={"note": "test"})
        assert meta["cb_fingerprint"] == bridge.contract_fingerprint()
        model, std, meta2 = df.load_checkpoint(path)
        assert meta2["checkpoint_hash"] == result.checkpoint_hash
        assert tr.state_dict_sha256(model.state_dict()) == result.checkpoint_hash
        np.testing.assert_array_equal(std.x_mean, dataset.standardization.x_mean)

    def test_tampered_checkpoint_refuses_to_load(self, dataset, result, tmp_path):
        path = tmp_path / "ck.pt"
        tr.save_checkpoint(result, dataset, path)
        doc = torch.load(path, weights_only=False)
        key = next(iter(doc["state_dict"]))
        doc["state_dict"][key] = doc["state_dict"][key] + 1e-3
        torch.save(doc, path)
        with pytest.raises(Exception, match="hash mismatch"):
            df.load_checkpoint(path)

    def test_state_dict_hash_is_canonical(self, result):
        a = tr.state_dict_sha256(result.model.state_dict())
        b = tr.state_dict_sha256(dict(reversed(list(result.model.state_dict().items()))))
        assert a == b  # order-independent (sorted names)
