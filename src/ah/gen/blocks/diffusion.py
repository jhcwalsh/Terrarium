"""WP2.8 diffusion — EDM-style conditional block generator (DN-1.1 §II.4 (a)).

Model: Karras et al. (2022) "EDM" continuous-time diffusion. The denoiser is
preconditioned as ``D(x; sigma, c) = c_skip*x + c_out*F_θ(c_in*x, c_noise(sigma), c)``
with ``c_skip = sigma_d^2/(sigma^2+sigma_d^2)``, ``c_out = sigma*sigma_d/sqrt (sigma^2+sigma_d^2)``,
``c_in = 1/sqrt (sigma^2+sigma_d^2)``, ``c_noise = ln(sigma)/4``; training draws
``sigma ~ LogNormal(P_mean, P_std)`` with the EDM weight
``lambda(sigma) = (sigma^2+sigma_d^2)/(sigma*sigma_d)²``; sampling integrates the probability-flow ODE
with the Karras sigma schedule and a deterministic 2nd-order Heun corrector
(configurable NFE; the last step is Euler, so ``NFE = 2*steps - 1``).

Backbone (recorded justification): the data is x ∈ R^{6x12} — six month-tokens
of twelve factors, 72 numbers. A temporal U-Net has nothing to downsample at
length 6; a SMALL pre-norm transformer over the six month tokens with
cross-attention onto the conditioning is the right-sized inductive bias:
self-attention captures within-block temporal structure, cross-attention reads
the c_b groups (regime one-hot / s_t / h_t / Δw, one context token each, plus a
sigma token). Attention is hand-rolled (softmax matmuls — at sequence length 6
there is nothing for a fused kernel to win) so every op is deterministic under
``torch.use_deterministic_algorithms(True)`` on both CPU and CUDA. Default
width 128 / depth 3 ≈ 0.6M parameters — "low millions at most" per the brief,
and deliberately small against ~41 effective training blocks per epoch.

:class:`DiffusionBlockSampler` implements the joinery's frozen
:class:`~ah.gen.joinery.bridge.BlockSampler` protocol — ``assemble_decades``
drives it exactly as it drives the bootstrap stand-in (that wiring is WP2.10's
system D). It refuses to construct if the checkpoint's recorded cb-v1 contract
fingerprint differs from the runtime's, and draws ALL sampling noise from the
caller's ``numpy.random.Generator`` so decade assembly stays bit-deterministic
per seed.

``hier-diffusion-v1`` is registered in the generator registry; its factory pins
the trained checkpoint hash, the c_b contract fingerprint, and the L1/L2
artifact SHAs (raising on any mismatch) — the lineage claim every ensemble
makes.

WHAT WP2.9 REUSES FROM THIS MODULE (recorded, so the reuse is visible rather
than archaeological). §WP2.9 says flow matching sits "behind the identical
interface, sharing data/constraints/losses/training/tuning". Three pieces of
*sampler* machinery are shared too, and they live here because this is where
WP2.8b measured and pinned their properties:

* :class:`TorchBlockSampler` — the fixed-width/zero-padded batched
  ``BlockSampler`` implementation, the batch-1 tracing policy, the c_b
  fingerprint refusal, and the de-standardize/constrain output map. A sampler
  family supplies only ``_integrate``.
* :class:`HierBlockSystem` — the ablation-system-D wrapper around
  ``assemble_decades``. A family supplies only ``generator_id`` and its
  system description.
* :class:`Attention` / :class:`TransformerBlock` / :data:`COND_GROUPS` — the
  backbone layers. :class:`ConditionalDenoiser` itself is NOT refactored: its
  ``state_dict`` key names are inside the pinned checkpoint hash, so the class
  is structurally frozen and WP2.9 composes the same layers into its own net.

The alternative was a new shared module; it was not taken because the plan's
§2 package layout names ``blocks/`` contents explicitly and the shared pieces
are exactly the ones WP2.8b already documented here.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from ah.core.numericworld import NumericWorld
from ah.gen import registry
from ah.gen.base import Ensemble
from ah.gen.blocks import constraints as ct
from ah.gen.blocks.data import Standardization
from ah.gen.blocks.losses import VAL_SIGMA_GRID
from ah.gen.joinery import bridge
from ah.gen.joinery.waypoints import JoineryError

__all__ = [
    "COND_GROUPS",
    "GENERATOR_ID",
    "Attention",
    "ConditionalDenoiser",
    "DiffusionBlockSampler",
    "DiffusionConfig",
    "EdmObjective",
    "HierBlockSystem",
    "HierDiffusionV1",
    "TorchBlockSampler",
    "TransformerBlock",
    "heun_integrate",
    "hier_diffusion_v1_factory",
    "karras_sigmas",
    "load_checkpoint",
    "sample_heun",
    "sinusoidal_embedding",
]

GENERATOR_ID = "hier-diffusion-v1"

#: The c_b slices that become one cross-attention context token each: regime
#: one-hot, s_t snapshot, h_t trailing summary, Δw increments. Shared with
#: WP2.9's velocity field so both samplers read the frozen contract identically.
COND_GROUPS: tuple[tuple[int, int], ...] = ((0, 6), (6, 11), (11, 14), (14, 18))
_COND_GROUPS = COND_GROUPS  # historical private alias (WP2.8)


@dataclass(frozen=True)
class DiffusionConfig:
    """Everything tunable about the 3a sampler; hashed into every trial record."""

    # architecture
    d_model: int = 128
    n_layers: int = 3
    n_heads: int = 4
    ffn_mult: int = 2
    dropout: float = 0.0
    # EDM training distribution + preconditioning
    sigma_data: float = 1.0
    p_mean: float = -1.2
    p_std: float = 1.2
    # sampling schedule
    sigma_min: float = 0.01
    sigma_max: float = 20.0
    rho: float = 7.0
    eval_nfe: int = 31
    # optimization
    lr: float = 3e-4
    weight_decay: float = 1e-4
    batch_size: int = 32
    ema_decay: float = 0.999
    # auxiliary tail loss (DN-1.1 lambda_tail — a config hyperparameter, searched;
    # NOT the sealed selection_lambda, which is pinned at 1.0 in pre-registration)
    lambda_tail: float = 0.1
    aux_every: int = 4
    aux_nfe: int = 9
    # conditioning-noise augmentation (see data.py's recorded decision)
    cond_noise_std: float = 0.0
    # A' residual parameterization (campaign-2) — same field as FlowConfig so
    # the bake-off compares like with like; see flow.py for the contract.
    residual_drift: bool = False
    # data geometry (campaign-2: the sealed factor set is fifteen; pre-campaign
    # checkpoints recorded n_factors explicitly, so their hashes are unaffected)
    block_months: int = bridge.BLOCK_MONTHS
    n_factors: int = 15
    cond_dim: int = bridge.C_B_DIM

    def as_dict(self) -> dict[str, Any]:
        doc = {k: getattr(self, k) for k in sorted(self.__dataclass_fields__)}
        if not doc["residual_drift"]:
            # Hash stability: omitted at its default so every pre-A' config_hash
            # recomputes byte-identical (same recorded choice as FlowConfig).
            del doc["residual_drift"]
        return doc

    def build_model(self) -> ConditionalDenoiser:
        """The family's model factory (:class:`ah.gen.blocks.train.BlockConfig`)."""
        return ConditionalDenoiser(self)


class Attention(nn.Module):
    """Hand-rolled multi-head attention (deterministic softmax matmuls)."""

    def __init__(self, d_model: int, n_heads: int) -> None:
        super().__init__()
        if d_model % n_heads:
            raise JoineryError(f"d_model {d_model} not divisible by n_heads {n_heads}")
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.q = nn.Linear(d_model, d_model)
        self.k = nn.Linear(d_model, d_model)
        self.v = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)

    def forward(self, query: torch.Tensor, keyval: torch.Tensor) -> torch.Tensor:
        b, tq, _ = query.shape
        tk = keyval.shape[1]

        def split(t: torch.Tensor, length: int) -> torch.Tensor:
            return t.view(b, length, self.n_heads, self.d_head).transpose(1, 2)

        q = split(self.q(query), tq)
        k = split(self.k(keyval), tk)
        v = split(self.v(keyval), tk)
        attn = torch.softmax(q @ k.transpose(-2, -1) / math.sqrt(self.d_head), dim=-1)
        merged = (attn @ v).transpose(1, 2).reshape(b, tq, -1)
        return self.out(merged)


class TransformerBlock(nn.Module):
    """Pre-norm self-attention + cross-attention onto c_b + MLP."""

    def __init__(self, d_model: int, n_heads: int, ffn_mult: int, dropout: float) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.self_attn = Attention(d_model, n_heads)
        self.lnc = nn.LayerNorm(d_model)
        self.cross_attn = Attention(d_model, n_heads)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, ffn_mult * d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_mult * d_model, d_model),
        )
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        h = self.ln1(x)
        x = x + self.drop(self.self_attn(h, h))
        x = x + self.drop(self.cross_attn(self.lnc(x), context))
        return x + self.drop(self.mlp(self.ln2(x)))


_Attention = Attention  # historical private aliases (WP2.8); kept so the
_Block = TransformerBlock  # module's own history reads straight.


def sinusoidal_embedding(scalar: torch.Tensor, freq: torch.Tensor) -> torch.Tensor:
    """``[sin(s*f), cos(s*f)]`` for a ``(B,)`` scalar against ``(d/2,)`` frequencies."""
    ang = scalar[:, None] * freq[None, :]
    return torch.cat([torch.sin(ang), torch.cos(ang)], dim=-1)


class ConditionalDenoiser(nn.Module):
    """F_θ inside the EDM preconditioning; also exposes the full D(x; sigma, c).

    STRUCTURALLY FROZEN: the ``state_dict`` key names below are inside
    :data:`PINNED_CHECKPOINT_SHA256`. WP2.9 composes the same layer classes into
    its own network rather than refactoring this one.
    """

    #: What the checkpoint meta records as the S-term's generative half.
    objective_name = "fixed-sigma-grid EDM denoising objective"

    def __init__(self, config: DiffusionConfig) -> None:
        super().__init__()
        self.config = config
        d = config.d_model
        self.x_proj = nn.Linear(config.n_factors, d)
        self.pos = nn.Parameter(torch.zeros(config.block_months, d))
        self.sigma_mlp = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, d))
        freq = torch.exp(torch.linspace(0.0, math.log(1000.0), d // 2))
        self.register_buffer("freq", freq)
        self.cond_proj = nn.ModuleList(nn.Linear(hi - lo, d) for lo, hi in COND_GROUPS)
        self.blocks = nn.ModuleList(
            TransformerBlock(d, config.n_heads, config.ffn_mult, config.dropout)
            for _ in range(config.n_layers)
        )
        self.ln_out = nn.LayerNorm(d)
        self.out = nn.Linear(d, config.n_factors)
        nn.init.zeros_(self.out.weight)  # EDM convention: F_θ ≈ 0 at init
        nn.init.zeros_(self.out.bias)

    def _sigma_embedding(self, c_noise: torch.Tensor) -> torch.Tensor:
        return self.sigma_mlp(sinusoidal_embedding(c_noise, self.freq))

    def forward(
        self, x_in: torch.Tensor, c_noise: torch.Tensor, cond: torch.Tensor
    ) -> torch.Tensor:
        """F_θ: ``x_in`` (B, L, F) preconditioned input; ``cond`` (B, 18) standardized."""
        sig = self._sigma_embedding(c_noise)  # (B, d)
        tokens = [
            proj(cond[:, lo:hi]) for proj, (lo, hi) in zip(self.cond_proj, COND_GROUPS, strict=True)
        ]
        context = torch.stack([*tokens, sig], dim=1)  # (B, 5, d)
        h = self.x_proj(x_in) + self.pos[None, :, :] + sig[:, None, :]
        for block in self.blocks:
            h = block(h, context)
        return self.out(self.ln_out(h))

    def denoise(self, x: torch.Tensor, sigma: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """The preconditioned D(x; sigma, c). ``sigma`` is (B,)."""
        sd = self.config.sigma_data
        s2 = sigma[:, None, None] ** 2
        c_skip = sd**2 / (s2 + sd**2)
        c_out = sigma[:, None, None] * sd / torch.sqrt(s2 + sd**2)
        c_in = 1.0 / torch.sqrt(s2 + sd**2)
        c_noise = torch.log(sigma) / 4.0
        return c_skip * x + c_out * self.forward(c_in * x, c_noise, cond)

    # -- the shared BlockModel surface (ah.gen.blocks.train.BlockModel) ------ #

    def net_call(self, x: torch.Tensor, s: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """The one network entry the sampler traces and integrates: D(x; sigma, c)."""
        return self.denoise(x, s, cond)

    def make_objective(self) -> EdmObjective:
        return EdmObjective(self, self.config)

    def sample(self, cond: torch.Tensor, noise: torch.Tensor, nfe: int) -> torch.Tensor:
        """Differentiable probability-flow sampling (the training aux path uses it)."""
        return heun_integrate(self.net_call, self.config, cond, noise, nfe)


class EdmObjective:
    """The 3a generative objective behind :class:`losses.GenerativeObjective`.

    ``validation_objective`` is evaluated on the FIXED sigma grid
    (:data:`losses.VAL_SIGMA_GRID`) with noise from a fixed-seed generator —
    identical (x, sigma, n) triples for every trial and every evaluation, so the
    number is comparable across configs whose training sigma distributions differ.
    """

    VAL_NOISE_SEED = 774_001

    def __init__(self, model: ConditionalDenoiser, config: DiffusionConfig) -> None:
        self.model = model
        self.config = config

    def _weighted_mse(
        self, x: torch.Tensor, cond: torch.Tensor, sigma: torch.Tensor, noise: torch.Tensor
    ) -> torch.Tensor:
        sd = self.config.sigma_data
        denoised = self.model.denoise(x + sigma[:, None, None] * noise, sigma, cond)
        weight = (sigma**2 + sd**2) / (sigma * sd) ** 2
        return (weight[:, None, None] * (denoised - x) ** 2).mean()

    def training_loss(
        self, x: torch.Tensor, cond: torch.Tensor, generator: torch.Generator
    ) -> torch.Tensor:
        b = x.shape[0]
        ln_sigma = self.config.p_mean + self.config.p_std * torch.randn(
            b, generator=generator, device=x.device
        )
        sigma = torch.exp(ln_sigma)
        noise = torch.randn(x.shape, generator=generator, device=x.device, dtype=x.dtype)
        return self._weighted_mse(x, cond, sigma, noise)

    @torch.no_grad()
    def validation_objective(self, x: torch.Tensor, cond: torch.Tensor) -> float:
        gen = torch.Generator(device="cpu").manual_seed(self.VAL_NOISE_SEED)
        total = 0.0
        for s in VAL_SIGMA_GRID:
            sigma = torch.full((x.shape[0],), s, device=x.device, dtype=x.dtype)
            noise = torch.randn(x.shape, generator=gen).to(device=x.device, dtype=x.dtype)
            total += float(self._weighted_mse(x, cond, sigma, noise))
        return total / len(VAL_SIGMA_GRID)


def karras_sigmas(nfe: int, config: DiffusionConfig) -> torch.Tensor:
    """The Karras sigma schedule with ``steps = (nfe+1)//2`` (Heun; last step Euler)."""
    steps = (int(nfe) + 1) // 2
    if steps < 2:
        raise JoineryError(f"nfe {nfe} gives {steps} step(s); need >= 2")
    i = torch.arange(steps, dtype=torch.float64)
    inv_rho = 1.0 / config.rho
    sig = (
        config.sigma_max**inv_rho
        + i / (steps - 1) * (config.sigma_min**inv_rho - config.sigma_max**inv_rho)
    ) ** config.rho
    return torch.cat([sig, torch.zeros(1, dtype=torch.float64)])


def heun_integrate(
    denoise: Any,  # callable (x, sigma_batch, cond) -> denoised
    config: DiffusionConfig,
    cond: torch.Tensor,
    noise: torch.Tensor,
    nfe: int,
) -> torch.Tensor:
    """Deterministic Heun ODE integration; NFE ``denoise`` evaluations exactly.

    ``noise`` is standard normal, ``(B, L, F)``; the caller owns its RNG.
    Differentiable when called under grad (the training-time auxiliary
    backpropagates through a small-NFE version of this loop). ``denoise`` may be
    the eager :meth:`ConditionalDenoiser.denoise` or a traced equivalent — the
    integration path is identical.
    """
    sigmas = karras_sigmas(nfe, config).to(device=noise.device, dtype=noise.dtype)
    x = noise * sigmas[0]
    for i in range(sigmas.shape[0] - 1):
        s_cur, s_next = sigmas[i], sigmas[i + 1]
        sig_b = s_cur.expand(x.shape[0])
        d_cur = (x - denoise(x, sig_b, cond)) / s_cur
        x_next = x + (s_next - s_cur) * d_cur
        if float(s_next) > 0.0:  # Heun correction (2nd model eval)
            sig_next_b = s_next.expand(x.shape[0])
            d_next = (x_next - denoise(x_next, sig_next_b, cond)) / s_next
            x_next = x + (s_next - s_cur) * 0.5 * (d_cur + d_next)
        x = x_next
    return x


def sample_heun(
    model: ConditionalDenoiser,
    cond: torch.Tensor,
    noise: torch.Tensor,
    nfe: int,
) -> torch.Tensor:
    """:func:`heun_integrate` with the eager model (training/eval code path)."""
    return heun_integrate(model.denoise, model.config, cond, noise, nfe)


# --------------------------------------------------------------------------- #
# the joinery-facing sampler (BlockSampler protocol)
# --------------------------------------------------------------------------- #


class TorchBlockSampler:
    """Shared torch ``BlockSampler`` machinery for every L3 sampler family.

    WP2.8 wrote this for diffusion; WP2.9 reuses it verbatim for flow matching
    (a family supplies only :meth:`_integrate`). Everything the joinery and the
    acceptance filter depend on lives here, once: the c_b fingerprint refusal,
    the noise-drawing contract, the fixed-width/zero-padded batching, the
    batch-1 tracing policy, and the de-standardize + constraint-inverse output
    map.

    Refuses to construct when the checkpoint's cb-v1 contract fingerprint
    differs from this runtime's (a sampler conditioned on a different contract
    must fail loudly, not silently). All noise comes from the caller's numpy
    generator; the model runs in float32 under ``no_grad`` and the result is
    mapped back through de-standardization and the constraint inverse — floors
    hold by construction for ANY model output.

    BATCH WIDTH (WP2.8b, corrected by WP2.9 — see below). ``block_batch`` is how
    many decades' blocks one network evaluation carries. It is a FIXED width, not
    "however many decades happen to be in flight": :meth:`sample_blocks` chunks
    its input into ``block_batch``-row batches and zero-pads the last one. Two
    properties come out of that, both measured and both pinned by test:

    * a row's output depends only on that row, on the width, and on its ROW
      INDEX WITHIN THE BATCH — never on its neighbours and never on how much of
      the batch is padding. Chunking maps decade ``m`` to row ``m % width`` for
      every run, so a decade's path is the same whether it is generated in a
      2-decade run or a 1024-decade one;
    * the ensemble is a deterministic function of (seed, width) alone.

    WP2.9 CORRECTION, stated because WP2.8b's wording overreached and its test
    could not catch it. WP2.8b claimed a row's output is independent of its
    POSITION too, and asserted it with a fixture whose output head is
    zero-initialized — i.e. a network that emits identically zero, for which any
    such claim is vacuous. Measured on a network with non-zero weights (both
    families, CPU oneDNN and CUDA alike): moving a row to a different index
    within the same width changes its output by ~2.4e-7 absolute, the same
    float32 GEMM round-off WP2.8b measured across widths. Holding the index
    fixed is EXACT — isolating any single row at its own index, with every other
    row zeroed, reproduces the full batch's value bit for bit. The invariant the
    acceptance filter and the ensemble digest actually rely on is the
    index-preserving one, and that one holds exactly; the tests now assert the
    true property on a non-trivial network rather than the stronger one on a
    trivial one.

    ``block_batch=1`` reproduces the per-block WP2.8 path BIT FOR BIT. Wider
    widths cannot: the float32 GEMM this network is built from is not batch-size
    invariant on any backend measured (CPU oneDNN and CUDA cuBLAS both change a
    row's denoiser output by ~1.5e-7 relative at batch 2 already, and no further
    as the batch grows). That is float round-off, not a behaviour change, but it
    is real and it is why the width is recorded in the ensemble lineage rather
    than hidden. It is deliberately left at 1 by default so that no existing
    result moves without someone asking for it.
    """

    def __init__(
        self,
        model: Any,
        standardization: Standardization,
        factor_names: tuple[str, ...],
        *,
        trained_fingerprint: str,
        nfe: int | None = None,
        device: str = "cpu",
        block_batch: int = 1,
    ) -> None:
        runtime = bridge.contract_fingerprint()
        if trained_fingerprint != runtime:
            raise JoineryError(
                f"c_b contract mismatch: checkpoint trained against "
                f"{trained_fingerprint[:16]}..., runtime speaks {runtime[:16]}... — "
                f"refusing to sample"
            )
        if len(factor_names) != model.config.n_factors:
            raise JoineryError(
                f"model emits {model.config.n_factors} factors; got {len(factor_names)} names"
            )
        if int(block_batch) < 1:
            raise JoineryError(f"block_batch must be >= 1; got {block_batch}")
        self._model = model.to(device).eval()
        self._std = standardization
        self._device = device
        self.device = str(device)
        self.factor_names = tuple(factor_names)
        self.block_months = int(model.config.block_months)
        self.nfe = int(model.config.eval_nfe if nfe is None else nfe)
        self.block_batch = int(block_batch)
        # Traced inference graph for the batch-1 path only (see _call_net).
        self._traced: dict[int, Any] = {}

    # -- what a sampler family supplies ------------------------------------- #

    def _integrate(self, cond: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
        """Family-specific deterministic integration; returns standardized x."""
        raise NotImplementedError

    @property
    def nfe_per_block(self) -> int:
        """Network evaluations one block costs (what the sealed tie-break reads)."""
        return int(self.nfe)

    def _call_net(self, x: torch.Tensor, s: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """The network: traced at batch 1, eager above it.

        Tracing exists to strip eager dispatch from a MILLION batch-1 calls, and
        at batch 1 it roughly halves the cost. Above batch 1 the dispatch is
        already amortized (measured: 7% left on CPU at width 128, 25% on CUDA at
        width 1024) while ``optimize_for_inference`` starts substituting fused
        reduced-precision kernels — measured divergence from the eager model of
        5e-5 on CPU at width 64 and 4.6e-4 on CUDA at width 256, i.e. it stops
        being the same computation. Trading a few percent for "the batched path
        is the model" is the right side of that. Recorded WP2.8b decision.
        """
        if int(x.shape[0]) != 1:
            return self._model.net_call(x, s, cond)
        key = int(x.shape[0])
        fn = self._traced.get(key)
        if fn is None:

            class _D(torch.nn.Module):
                def __init__(self, m: Any) -> None:
                    super().__init__()
                    self.m = m

                def forward(
                    self, x: torch.Tensor, s: torch.Tensor, c: torch.Tensor
                ) -> torch.Tensor:
                    return self.m.net_call(x, s, c)

            import warnings

            with torch.no_grad(), warnings.catch_warnings():
                # torch.jit.trace is deprecated in torch 2.13 but remains the
                # only zero-new-dependency way to strip eager dispatch from a
                # million batch-1 calls; parity with the eager model is asserted
                # below. WP2.9 re-checked torch.export: it still requires
                # torch.export.export + an ExportedProgram call path whose
                # deterministic-op guarantees are not established here, so the
                # traced path stands (recorded).
                warnings.simplefilter("ignore", DeprecationWarning)
                fn = torch.jit.optimize_for_inference(
                    torch.jit.trace(_D(self._model).eval(), (x, s, cond))
                )
                eager = self._model.net_call(x, s, cond)
                traced = fn(x, s, cond)
                if float((eager - traced).abs().max()) > 1e-5:
                    raise JoineryError("traced network diverged from the eager model at trace time")
            self._traced[key] = fn
        return fn(x, s, cond)

    def sample_batch(self, cond_vectors: np.ndarray, noise: np.ndarray) -> np.ndarray:
        """Blocks in FACTOR UNITS for ``(B, 18)`` raw c_b vectors + given noise.

        ONE network evaluation of exactly ``B`` rows — no chunking, no padding.
        :meth:`sample_blocks` is the entry point that imposes the fixed width.
        """
        cond = torch.as_tensor(
            self._std.standardize_cond(cond_vectors), dtype=torch.float32, device=self._device
        )
        noise_t = torch.as_tensor(noise, dtype=torch.float32, device=self._device)
        with torch.no_grad():
            z = self._integrate(cond, noise_t)
        z_np = self._std.destandardize_x(z.double().cpu().numpy())
        if getattr(self._model.config, "residual_drift", False):
            # A' symmetry: the network emitted deviations; the drift means come
            # from the same raw c_b vector the dataset subtracted them against.
            z_np = z_np + bridge.conditioning_drift_means(
                cond_vectors, self.factor_names, self.block_months
            )
        return ct.panel_to_constrained(z_np, self.factor_names)

    def _draw_noise(self, rng: np.random.Generator) -> np.ndarray:
        """One block's sampling noise — the ONLY place this sampler touches an RNG."""
        return rng.standard_normal((self.block_months, len(self.factor_names)))

    def sample_block(self, cond: bridge.BlockConditioning, rng: np.random.Generator) -> np.ndarray:
        return self.sample_batch(cond.to_vector()[None, :], self._draw_noise(rng)[None, ...])[0]

    def sample_blocks(
        self,
        conds: Sequence[bridge.BlockConditioning],
        rngs: Sequence[np.random.Generator],
    ) -> np.ndarray:
        """The batched entry point (:class:`bridge.BatchedBlockSampler`).

        Every decade's noise is drawn from ITS OWN generator, in decade order,
        exactly as the per-decade driver would have drawn it at this block — the
        RNG sees the identical call at the identical point in its stream. Only
        the network evaluation is grouped, at the fixed ``block_batch`` width with
        the tail zero-padded.
        """
        if len(conds) != len(rngs):
            raise JoineryError(f"got {len(conds)} conditionings and {len(rngs)} generators")
        n = len(conds)
        n_factors = len(self.factor_names)
        out = np.empty((n, self.block_months, n_factors), dtype=np.float64)
        if n == 0:
            return out
        vectors = np.stack([cond.to_vector() for cond in conds])
        noise = np.stack([self._draw_noise(rng) for rng in rngs])

        width = self.block_batch
        for lo in range(0, n, width):
            hi = min(lo + width, n)
            take = hi - lo
            chunk_c, chunk_n = vectors[lo:hi], noise[lo:hi]
            pad = width - take
            if pad:
                # Pad to the fixed width so the real rows see the same batch size
                # AND the same row index in every call. Rows are independent
                # through this network (no cross-row op anywhere: attention is
                # within a block, LayerNorm and softmax are per row), so the
                # padding cannot reach them — asserted by test, not assumed. What
                # padding does NOT buy is index independence; see the class
                # docstring's WP2.9 correction. Chunking at a fixed width is what
                # keeps decade m at row m % width in every run.
                chunk_c = np.concatenate([chunk_c, np.zeros((pad, chunk_c.shape[1]))])
                chunk_n = np.concatenate([chunk_n, np.zeros((pad, self.block_months, n_factors))])
            out[lo:hi] = self.sample_batch(chunk_c, chunk_n)[:take]
        return out


class DiffusionBlockSampler(TorchBlockSampler):
    """The trained 3a sampler: :func:`heun_integrate` over the EDM sigma schedule.

    Everything else — the fingerprint refusal, the RNG contract, the fixed-width
    batching, the output map — is :class:`TorchBlockSampler`'s and is shared
    verbatim with WP2.9's :class:`~ah.gen.blocks.flow.FlowBlockSampler`.
    """

    def _integrate(self, cond: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
        return heun_integrate(self._call_net, self._model.config, cond, noise, self.nfe)


# --------------------------------------------------------------------------- #
# checkpoint identity + the registered generator
# --------------------------------------------------------------------------- #


def load_checkpoint(path: str | Path, *, map_location: str = "cpu"):
    """Load a WP2.8 checkpoint dict; verify its recorded SHA-256 over weights.

    Returns ``(model, standardization, meta)``. The hash is recomputed from the
    serialized state-dict bytes exactly as :func:`ah.gen.blocks.train.state_dict_sha256`
    wrote it; a mismatch raises.
    """
    from ah.gen.blocks.train import state_dict_sha256

    doc = torch.load(Path(path), map_location=map_location, weights_only=False)
    config = DiffusionConfig(**doc["config"])
    model = ConditionalDenoiser(config)
    model.load_state_dict(doc["state_dict"])
    recorded = doc["meta"]["checkpoint_hash"]
    actual = state_dict_sha256(model.state_dict())
    if actual != recorded:
        raise JoineryError(
            f"checkpoint hash mismatch: recorded {recorded[:16]}..., recomputed {actual[:16]}..."
        )
    std = Standardization.from_dict(doc["standardization"])
    return model, std, doc["meta"]


# The primary trained checkpoint (filled by scripts/train_blocks_final.py after
# the sealed tuning search selected the config; verified on every factory call).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CHECKPOINT = _REPO_ROOT / "experiments" / "l3a-diffusion-final" / "checkpoint.pt"
#: The primary WP2.8 checkpoint: the sealed-selection config (cfg:505f9800900bd757)
#: trained to early stopping on validation S, seed 20260727, campaign vintage
#: 2026-07-26.1. Written by scripts/train_blocks_final.py and verified here on
#: every factory call.
PINNED_CHECKPOINT_SHA256: str | None = (
    "f0c79f000be659c8b443afba02a251ab8925d995fdebcf8e6e82195e8dd70c5a"
)

#: What :func:`hier_diffusion_v1_factory` builds its sampler with — the registry
#: resolves by id and takes no arguments, so a caller that wants the WP2.8b
#: batched path sets these BEFORE resolving (``scripts/run_diffusion_battery.py``
#: exposes them as ``--block-batch`` / ``--sampler-device``). They default to the
#: WP2.8 behaviour exactly: width 1, CPU. Both land in the ensemble's lineage
#: record, so a batched ensemble always says so.
DEFAULT_BLOCK_BATCH: int = 1
DEFAULT_SAMPLER_DEVICE: str = "cpu"


class HierBlockSystem:
    """Ablation system D: L1+L2+L4 joinery driven by a trained L3 block sampler.

    Implements :class:`ah.gen.base.Generator`. Subclasses set
    :attr:`generator_id` and :attr:`system_description`; nothing else differs
    between the 3a and 3b arms of system D, which is the point — §WP2.9's "both
    samplers through one entry point" is this class plus the registry.

    Same schema-enum wall as ``bootstrap-v1``/``joinery-bootstrap-v0`` (STEP2R
    bumps the enum).
    """

    generator_id = "hier-block-system"
    system_description = "L1+L2+L4 (trained L3 blocks)"

    def __init__(
        self,
        climate,
        regimes_artifact,
        source,
        sampler: TorchBlockSampler,
        config=None,
        guidance: bridge.GuidanceHook | None = None,
    ) -> None:
        from ah.gen.joinery.assemble import JoineryConfig

        self._climate = climate
        self._regimes = regimes_artifact
        self._source = source
        self._sampler = sampler
        self._config = JoineryConfig() if config is None else config
        #: DN-1.1 §II.5 design note (a) / §WP2.9's optional guidance hook. It is
        #: plumbed but DEFAULTS TO None, and it is an ADDITIONAL arm, never a
        #: replacement for reconciliation — Denton stays the guarantee, and any
        #: run with a hook must be reported alongside the same run without it.
        #: WP2.9 leaves it unused; see flow.py's module docstring for why
        #: guidance is implemented as classifier-free guidance INSIDE the
        #: sampler (learned aim) rather than as a post-hoc block adjustment
        #: (repair, the same category as Denton).
        self._guidance = guidance
        self.checkpoint_hash: str | None = None
        self.config_hash: str | None = None

    def fit(self, data: Any) -> None:
        raise JoineryError(
            f"{self.generator_id} is trained offline (scripts/train_blocks_final.py "
            f"/ scripts/train_flow_final.py); fit() is not a runtime operation"
        )

    def _assemble(self, *, n_paths: int, seed: int, months: int, world, config) -> Ensemble:
        from ah.gen.joinery.assemble import assemble_decades

        ensemble = assemble_decades(
            climate=self._climate,
            regimes_artifact=self._regimes,
            source=self._source,
            n_decades=n_paths,
            seed=seed,
            months=months,
            world=world,
            sampler=self._sampler,
            config=config,
            guidance=self._guidance,
        )
        ensemble.meta.conditioning["system"] = self.system_description
        ensemble.meta.conditioning["joinery_guidance_hook"] = (
            type(self._guidance).__name__ if self._guidance is not None else None
        )
        meta = replace(
            ensemble.meta,
            generator_id=self.generator_id,
            checkpoint_hash=self.checkpoint_hash,
            config_hash=self.config_hash,
        )
        ensemble.meta = meta
        return ensemble

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = int(world.horizon.quarters) * 3
        return self._assemble(
            n_paths=n_paths, seed=seed, months=months, world=world, config=self._config
        )

    def sample_months(
        self, months: int, n_paths: int, seed: int, *, unfiltered: bool = False
    ) -> Ensemble:
        from dataclasses import replace as dc_replace

        config = dc_replace(self._config, acceptance_filter=False) if unfiltered else self._config
        return self._assemble(n_paths=n_paths, seed=seed, months=months, world=None, config=config)


class HierDiffusionV1(HierBlockSystem):
    """System D, 3a arm — the trained EDM diffusion sampler."""

    generator_id = GENERATOR_ID
    system_description = "L1+L2+L4 (hier-diffusion-v1 blocks)"


def hier_diffusion_v1_factory() -> HierDiffusionV1:
    """Construct the trained system D from the pinned checkpoint + artifacts.

    Raises when the checkpoint is absent, its weight hash differs from
    :data:`PINNED_CHECKPOINT_SHA256`, its recorded c_b fingerprint differs from
    the runtime's, or the L1/L2 artifact SHAs differ from the WP2.7 pins.
    """
    from ah.gen.bootstrap import campaign_source
    from ah.gen.climate.simulate import load_artifact as load_climate
    from ah.gen.joinery.assemble import (
        DEFAULT_CLIMATE_ARTIFACT,
        DEFAULT_REGIMES_ARTIFACT,
        PINNED_CLIMATE_SHA256,
        PINNED_REGIMES_SHA256,
    )
    from ah.gen.regimes.semimarkov import load_artifact as load_regimes

    if PINNED_CHECKPOINT_SHA256 is None:
        raise JoineryError(f"{GENERATOR_ID} has no pinned checkpoint yet (train first)")
    model, std, meta = load_checkpoint(DEFAULT_CHECKPOINT)
    if meta["checkpoint_hash"] != PINNED_CHECKPOINT_SHA256:
        raise JoineryError(
            f"checkpoint {meta['checkpoint_hash'][:16]}... != pinned "
            f"{PINNED_CHECKPOINT_SHA256[:16]}..."
        )
    climate = load_climate(DEFAULT_CLIMATE_ARTIFACT)
    regimes_artifact = load_regimes(DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != PINNED_CLIMATE_SHA256:
        raise JoineryError("climate artifact sha != WP2.7 pin")
    if regimes_artifact.meta["content_sha256"] != PINNED_REGIMES_SHA256:
        raise JoineryError("regimes artifact sha != WP2.7 pin")
    if meta.get("climate_sha256") != PINNED_CLIMATE_SHA256:
        raise JoineryError("checkpoint was trained against a different L1 artifact")
    source = campaign_source()
    sampler = DiffusionBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device=DEFAULT_SAMPLER_DEVICE,
        block_batch=DEFAULT_BLOCK_BATCH,
    )
    system = HierDiffusionV1(climate, regimes_artifact, source, sampler)
    system.checkpoint_hash = meta["checkpoint_hash"]
    system.config_hash = meta.get("config_hash")
    return system


registry.register(GENERATOR_ID, hier_diffusion_v1_factory)

# WP2R.7: `conditional-diffusion` is WorldSpec v1.0's legacy name for the diffusion
# family (the v1.0 enum predates Step 2's registry). Sealed/vendored 1.0.x worlds
# carry it and may not be edited, so it resolves here as a deprecated alias — the
# same mechanism as bootstrap.py's `bootstrap-stratified`. New worlds author
# `hier-diffusion-v1` (or the promoted default `hier-flow-v1`).
LEGACY_SCHEMA_GENERATOR_ID = "conditional-diffusion"
registry.register(LEGACY_SCHEMA_GENERATOR_ID, hier_diffusion_v1_factory)
