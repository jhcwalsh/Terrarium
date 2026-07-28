"""WP2.8 train — deterministic training, hashed checkpoints, early stopping on S.

Determinism (plan §1, verbatim): ``torch.manual_seed`` + numpy ``PCG64`` for
data order + ``torch.use_deterministic_algorithms(True)`` + cuDNN flags
(``deterministic=True``, ``benchmark=False``) + ``CUBLAS_WORKSPACE_CONFIG`` set
before the first CUDA matmul. The backbone uses only deterministic ops
(hand-rolled attention; no fused SDPA kernels), so two same-seed runs on the
same device are bit-identical — asserted by test on CPU and measured on the GPU
by the training script (any residual cross-DEVICE difference is documented in
the run report, never waved away).

Early stopping (recorded exactly): the metric is the SEALED selection quantity
S = mean_folds(generative_objective) + selection_lambda *
mean_folds(D4_tail_elicitability_auxiliary) with selection_lambda = 1.0
(pre-registration ``tuning_protocol.selection_lambda``, pinned, not a
hyperparameter), evaluated every ``eval_every`` steps on the EMA weights over
the validation folds; training stops after ``patience`` evaluations without
improvement and the best-S EMA state is kept. No other statistic feeds the
stopping decision — nothing battery-flavoured beyond the two sealed S terms, so
there is nothing here for the teach-to-the-exam bar to catch.

Checkpoint identity: SHA-256 over the canonical serialized state-dict bytes
(sorted parameter names, shapes, little-endian float bytes) plus the config
hash — recorded in the experiment store and verified on every load.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ah.experiment import config_hash
from ah.gen.blocks import constraints as ct
from ah.gen.blocks import data as bd
from ah.gen.blocks import losses as ls
from ah.gen.blocks.diffusion import (
    ConditionalDenoiser,
    DiffusionConfig,
    EdmObjective,
    sample_heun,
)
from ah.gen.joinery import bridge

__all__ = [
    "SELECTION_LAMBDA",
    "TrainResult",
    "configure_determinism",
    "evaluate_fold_scores",
    "save_checkpoint",
    "state_dict_sha256",
    "train_diffusion",
]

#: The SEALED selection weight (pre-registration ``tuning_protocol.selection_lambda``).
#: PINNED at 1.0 — never searched, never read off trials; a test asserts this
#: constant equals the sealed YAML value. Distinct from DN-1.1's lambda_tail (the
#: TRAINING loss weight, ``DiffusionConfig.lambda_tail``), which IS searchable.
SELECTION_LAMBDA = 1.0

_EVAL_NOISE_SEED = 9_106_001  # fold-eval sampling noise: fixed across trials/evals


def configure_determinism(seed: int) -> np.random.Generator:
    """The plan-§1 determinism block; returns the numpy generator for data order."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    return np.random.Generator(np.random.PCG64(seed))


def state_dict_sha256(state_dict: dict[str, torch.Tensor]) -> str:
    """Canonical SHA-256 over state-dict bytes (sorted names, shapes, LE bytes)."""
    h = hashlib.sha256()
    for name in sorted(state_dict):
        tensor = state_dict[name].detach().cpu().contiguous()
        h.update(name.encode("utf-8"))
        h.update(str(tuple(tensor.shape)).encode("utf-8"))
        h.update(tensor.numpy().tobytes())
    return h.hexdigest()


@dataclass
class TrainResult:
    model: ConditionalDenoiser  # loaded with the best-S EMA weights
    config: DiffusionConfig
    checkpoint_hash: str
    config_hash: str
    best_step: int
    best_s: float
    best_gen_term: float
    best_aux_term: float
    per_fold_gen: list[float]
    per_fold_aux: list[float]
    history: list[dict[str, float]] = field(default_factory=list)
    stopped_early: bool = False
    steps_run: int = 0


class _Ema:
    def __init__(self, model: torch.nn.Module, decay: float) -> None:
        self.decay = decay
        self.shadow = {k: v.detach().clone() for k, v in model.state_dict().items()}

    def update(self, model: torch.nn.Module) -> None:
        with torch.no_grad():
            for k, v in model.state_dict().items():
                if v.dtype.is_floating_point:
                    self.shadow[k].mul_(self.decay).add_(v.detach(), alpha=1.0 - self.decay)
                else:
                    self.shadow[k].copy_(v)


def _units_torch(
    z_std: torch.Tensor, std: bd.Standardization, factor_names: tuple[str, ...]
) -> torch.Tensor:
    """Standardized unconstrained -> factor units, differentiable (aux loss path)."""
    mean = torch.as_tensor(std.x_mean, dtype=z_std.dtype, device=z_std.device)
    scale = torch.as_tensor(std.x_std, dtype=z_std.dtype, device=z_std.device)
    return ct.panel_to_constrained_torch(z_std * scale + mean, factor_names)


def evaluate_fold_scores(
    model: ConditionalDenoiser,
    dataset: bd.BlockDataset,
    compiled: tuple[ls.CompiledStrategy, ...],
    *,
    n_rep: int = 8,
    nfe: int | None = None,
    device: str = "cpu",
) -> dict[str, Any]:
    """Both sealed S terms, per validation fold — ONE code path for early
    stopping, trial scoring, and the final report.

    The generative objective is the fixed-sigma-grid denoising objective
    (:meth:`EdmObjective.validation_objective`); the auxiliary generates
    ``n_rep`` blocks per fold conditioning vector with FIXED noise (PCG64 seeded
    per fold, identical across trials and evaluations) and scores the generated
    (VaR, ES) against the fold's REAL block realizations.
    """
    model = model.to(device).eval()
    config = model.config
    objective = EdmObjective(model, config)
    nfe = int(config.eval_nfe if nfe is None else nfe)
    std = dataset.standardization

    per_fold_gen: list[float] = []
    per_fold_aux: list[float] = []
    per_fold_aux_detail: list[dict[str, float]] = []
    for k in range(len(dataset.fold_indices)):
        x = torch.as_tensor(dataset.fold_x_standardized(k), dtype=torch.float32, device=device)
        cond = torch.as_tensor(
            dataset.fold_cond_standardized(k), dtype=torch.float32, device=device
        )
        per_fold_gen.append(objective.validation_objective(x, cond))

        rng = np.random.Generator(np.random.PCG64(_EVAL_NOISE_SEED + k))
        n_blocks = x.shape[0]
        noise = rng.standard_normal((n_rep * n_blocks, config.block_months, config.n_factors))
        cond_rep = cond.repeat(n_rep, 1)
        with torch.no_grad():
            z = sample_heun(
                model, cond_rep, torch.as_tensor(noise, dtype=torch.float32, device=device), nfe
            )
        gen_units = ct.panel_to_constrained(
            std.destandardize_x(z.double().cpu().numpy()), dataset.factor_names
        )
        aux, detail = ls.tail_auxiliary_validation(gen_units, dataset.fold_x_units(k), compiled)
        per_fold_aux.append(aux)
        per_fold_aux_detail.append(detail)

    gen_term = float(np.mean(per_fold_gen))
    aux_term = float(np.mean(per_fold_aux))
    return {
        "per_fold_gen": per_fold_gen,
        "per_fold_aux": per_fold_aux,
        "per_fold_aux_detail": per_fold_aux_detail,
        "gen_term": gen_term,
        "aux_term": aux_term,
        "selection_lambda": SELECTION_LAMBDA,
        "s_value": gen_term + SELECTION_LAMBDA * aux_term,
        "nfe": nfe,
        "n_rep": n_rep,
    }


def train_diffusion(
    dataset: bd.BlockDataset,
    config: DiffusionConfig,
    *,
    seed: int,
    max_steps: int,
    eval_every: int,
    patience: int,
    device: str = "cpu",
    n_rep_eval: int = 8,
    log: Callable[[str], None] | None = None,
) -> TrainResult:
    """Train one 3a model deterministically; early-stop on validation S.

    See the module docstring for the determinism and early-stopping contracts.
    ``max_steps``/``eval_every``/``patience`` are BUDGET parameters, not searched
    hyperparameters: trials use a short cap, the final run a long one.
    """
    rng = configure_determinism(seed)
    torch_gen = torch.Generator(device=device).manual_seed(seed + 1)

    model = ConditionalDenoiser(config).to(device)
    objective = EdmObjective(model, config)
    compiled, _ = ls.compile_block_strategies(dataset.factor_names, dataset.block_months)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )
    ema = _Ema(model, config.ema_decay)
    std = dataset.standardization

    xs = torch.as_tensor(std.standardize_x(dataset.x), dtype=torch.float32, device=device)
    cs = torch.as_tensor(std.standardize_cond(dataset.cond), dtype=torch.float32, device=device)

    def batches():
        while True:
            rows = bd.epoch_starts(dataset, rng)
            for i in range(0, rows.size, config.batch_size):
                yield rows[i : i + config.batch_size]

    best_s = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    best_step = -1
    best_scores: dict[str, Any] | None = None
    history: list[dict[str, float]] = []
    since_best = 0
    stopped_early = False

    batch_iter = batches()
    step = 0
    for step in range(1, max_steps + 1):
        rows = next(batch_iter)
        x = xs[rows]
        cond = cs[rows]
        if config.cond_noise_std > 0.0:
            jitter = torch.zeros_like(cond)
            jitter[:, 6:] = config.cond_noise_std * torch.randn(
                (cond.shape[0], cond.shape[1] - 6), generator=torch_gen, device=device
            )
            cond = cond + jitter

        loss = objective.training_loss(x, cond, torch_gen)
        if config.lambda_tail > 0.0 and step % config.aux_every == 0:
            noise = torch.randn(x.shape, generator=torch_gen, device=device)
            z_gen = sample_heun(model, cond, noise, config.aux_nfe)
            gen_units = _units_torch(z_gen, std, dataset.factor_names)
            real_units = _units_torch(x, std, dataset.factor_names)
            aux = ls.tail_auxiliary_torch(gen_units, real_units, compiled)
            loss = loss + config.lambda_tail * aux

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        ema.update(model)

        if step % eval_every == 0 or step == max_steps:
            eval_model = ConditionalDenoiser(config).to(device)
            eval_model.load_state_dict(ema.shadow)
            scores = evaluate_fold_scores(
                eval_model, dataset, compiled, n_rep=n_rep_eval, device=device
            )
            history.append(
                {
                    "step": float(step),
                    "train_loss": float(loss.detach()),
                    "s_value": scores["s_value"],
                    "gen_term": scores["gen_term"],
                    "aux_term": scores["aux_term"],
                }
            )
            if log is not None:
                log(
                    f"step {step:6d}  loss {float(loss.detach()):.4f}  "
                    f"S {scores['s_value']:.4f} (gen {scores['gen_term']:.4f} "
                    f"aux {scores['aux_term']:.4f})"
                )
            if scores["s_value"] < best_s:
                best_s = scores["s_value"]
                best_state = {k: v.detach().clone() for k, v in ema.shadow.items()}
                best_step = step
                best_scores = scores
                since_best = 0
            else:
                since_best += 1
                if since_best >= patience:
                    stopped_early = True
                    break

    assert best_state is not None and best_scores is not None
    final = ConditionalDenoiser(config)
    final.load_state_dict({k: v.cpu() for k, v in best_state.items()})
    return TrainResult(
        model=final,
        config=config,
        checkpoint_hash=state_dict_sha256(final.state_dict()),
        config_hash=config_hash(config.as_dict()),
        best_step=best_step,
        best_s=best_s,
        best_gen_term=best_scores["gen_term"],
        best_aux_term=best_scores["aux_term"],
        per_fold_gen=list(best_scores["per_fold_gen"]),
        per_fold_aux=list(best_scores["per_fold_aux"]),
        history=history,
        stopped_early=stopped_early,
        steps_run=step,
    )


def save_checkpoint(
    result: TrainResult,
    dataset: bd.BlockDataset,
    path: str | Path,
    *,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the checkpoint with its identity metadata; returns the meta dict."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "checkpoint_hash": result.checkpoint_hash,
        "config_hash": result.config_hash,
        "cb_fingerprint": bridge.contract_fingerprint(),
        "factor_names": list(dataset.factor_names),
        "best_step": result.best_step,
        "best_s": result.best_s,
        "best_gen_term": result.best_gen_term,
        "best_aux_term": result.best_aux_term,
        "selection_lambda": SELECTION_LAMBDA,
        "per_fold_gen": result.per_fold_gen,
        "per_fold_aux": result.per_fold_aux,
        "stopped_early": result.stopped_early,
        "steps_run": result.steps_run,
        "early_stopping_metric": (
            "sealed S = mean_folds(fixed-sigma-grid EDM objective) + 1.0 * "
            "mean_folds(D4 tail elicitability auxiliary), on EMA weights"
        ),
    }
    if extra_meta:
        meta.update(extra_meta)
    torch.save(
        {
            "state_dict": result.model.state_dict(),
            "config": result.config.as_dict(),
            "standardization": dataset.standardization.to_dict(),
            "meta": meta,
        },
        path,
    )
    return meta
