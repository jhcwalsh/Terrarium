"""WP2.9 flow — conditional flow matching / rectified flow (DN-1.1 §II.4 (b)).

CO-PRIMARY, NOT A FALLBACK. DN-1.1 §II.4 names two architectures "behind one
conditioning contract" and the G2 bake-off decides between them; §II.8 records
the sampler family as explicitly deferred to that bake-off. This module is the
second arm, and the whole point of it is that it is the *same* system with a
different generative objective.

THE MODEL. Rectified flow (Liu et al. 2022) / conditional flow matching
(Lipman et al. 2023) in its straight-line form: with ``x_0 ~ N(0, I)`` and
``x_1`` a standardized data block, the interpolant is ``x_t = (1-t)x_0 + t x_1``
and the conditional target velocity is the CONSTANT ``u = x_1 - x_0``. Training
regresses ``v_θ(x_t, t, c)`` onto ``u`` under a chosen distribution of ``t``;
sampling integrates ``dx/dt = v_θ(x, t, c)`` from t=0 (noise) to t=1 (data).
Deliberately the sigma_min = 0 case: an OT-CFM ``sigma_min > 0`` adds a knob whose
effect at this data scale is far below the noise floor of a 40-trial search.

WHY IT IS A DIFFERENT NUMBER, NOT A BETTER ONE. The 3a objective is a
sigma-weighted denoising MSE against ``x``; this one is an unweighted velocity
MSE against ``x_1 - x_0``. They are not on one scale and neither bounds the
other, which is exactly what the sealed ``tuning_protocol`` anticipated when it
required both terms of S to be reported separately per sampler. (For the record,
because the seal's own wording is loose: it describes the two as "an ELBO (a
bound) and an exact log-likelihood". Neither is literally that — both are
Monte-Carlo regression losses on their own fixed evaluation grids. The seal's
BINDING consequence, that the arms are separately selected and that a fixed
lambda weights the auxiliary differently in each, holds unchanged and is
strengthened by the correction, not weakened.)

THE BACKBONE IS SHARED. Same pre-norm transformer over the six month tokens,
same cross-attention onto the four c_b context tokens
(:data:`~ah.gen.blocks.diffusion.COND_GROUPS`), same hand-rolled deterministic
attention. Two differences, both deliberate:

* the scalar token is ``t ∈ (0,1)`` rather than ``ln(sigma)/4``;
* a LEARNED NULL CONDITIONING VECTOR (:attr:`ConditionalVelocityField.null_cond`,
  18 parameters, in standardized c_b space) makes classifier-free guidance
  available. Training drops the whole conditioning row to it with probability
  ``cond_dropout``; sampling with ``guidance_scale != 1`` evaluates both branches
  and extrapolates. That is the direct answer to WP2.8's measured conditioning
  attenuation (``artifacts/wp28/ig-spread-diagnosis.md`` §4: every channel
  damped, the spread-level channels worst) — and unlike an inference-time level
  correction it is LEARNED AIM, not post-hoc repair, because it amplifies what
  the model already reads instead of overwriting what it produced. It is also
  not free: CFG costs two network evaluations per step, and
  :attr:`FlowConfig.sampling_nfe` reports the doubled figure so the sealed
  tie-break on sampling cost cannot be gamed by it.

A null branch that was never trained must never be sampled from, so
:class:`FlowConfig` collapses ``guidance_scale`` to 1.0 whenever
``cond_dropout`` is 0 — BEFORE the config is hashed, so the sealed budget is not
spent twice on the same model.

EVERYTHING ELSE IS THE 3a STACK, UNFORKED: ``data.py`` (the same blocks, the
same cb-v1 conditioning, the same train-only standardization), ``constraints.py``
(the same coordinate map, so floors are structurally impossible here too),
``losses.py`` (the same D4 tail auxiliary, the same corrected elicitability
direction), ``train.py`` (the same trainer, determinism block, EMA and sealed
early-stopping metric), ``tuning.py`` (the same protocol code, its own log and
its own budget of 40 — the seal is per system PER SAMPLER), and
:class:`~ah.gen.blocks.diffusion.TorchBlockSampler` /
:class:`~ah.gen.blocks.diffusion.HierBlockSystem` for the sampler and system
wrappers. ``hier-flow-v1`` registers alongside ``hier-diffusion-v1``: one entry
point, two samplers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn

from ah.gen import registry
from ah.gen.blocks.data import Standardization
from ah.gen.blocks.diffusion import (
    COND_GROUPS,
    HierBlockSystem,
    TorchBlockSampler,
    TransformerBlock,
    sinusoidal_embedding,
)
from ah.gen.blocks.losses import VAL_TIME_GRID
from ah.gen.joinery import bridge
from ah.gen.joinery.waypoints import JoineryError

__all__ = [
    "GENERATOR_ID",
    "SOLVERS",
    "TIME_DISTRIBUTIONS",
    "ConditionalVelocityField",
    "FlowBlockSampler",
    "FlowConfig",
    "FlowMatchingObjective",
    "HierFlowV1",
    "flow_integrate",
    "hier_flow_v1_factory",
    "load_checkpoint",
]

GENERATOR_ID = "hier-flow-v1"

#: ``euler`` costs one velocity evaluation per step; ``heun`` costs two and is
#: exact for a field linear in t. Both are deterministic — no stochastic sampler
#: is offered, because DN-1.1 §II.4 (b) names deterministic few-step sampling as
#: the reason this family is co-primary.
SOLVERS: tuple[str, ...] = ("euler", "heun")

#: ``uniform`` is the plain rectified-flow choice; ``logit_normal`` is the
#: SD3-style reweighting that concentrates training on mid-path times, where the
#: velocity target is hardest.
TIME_DISTRIBUTIONS: tuple[str, ...] = ("uniform", "logit_normal")

_EVALS_PER_STEP = {"euler": 1, "heun": 2}


@dataclass(frozen=True)
class FlowConfig:
    """Everything tunable about the 3b sampler; hashed into every trial record.

    Field-for-field the 3a config where the two families share a knob, so a
    reader comparing the two search spaces is comparing like with like.
    """

    # architecture (same backbone classes as 3a)
    d_model: int = 128
    n_layers: int = 3
    n_heads: int = 4
    ffn_mult: int = 2
    dropout: float = 0.0
    # the interpolant's training-time distribution over t
    time_dist: str = "uniform"
    time_logit_std: float = 1.0
    # sampling
    solver: str = "euler"
    eval_nfe: int = 8
    # optimization
    lr: float = 3e-4
    weight_decay: float = 1e-4
    batch_size: int = 32
    ema_decay: float = 0.999
    # auxiliary tail loss (DN-1.1 lambda_tail — a config hyperparameter, searched;
    # NOT the sealed selection_lambda, which is pinned at 1.0 in pre-registration)
    lambda_tail: float = 0.1
    aux_every: int = 4
    aux_nfe: int = 4
    # conditioning strength (WP2.8's attenuation finding is what these attack)
    cond_noise_std: float = 0.0
    cond_dropout: float = 0.0
    guidance_scale: float = 1.0
    # A' residual parameterization (campaign-2): the network models deviations
    # around bridge.conditioning_drift_means; the dataset must be built with the
    # matching flag and the sampler adds the means back from the raw c_b vector.
    residual_drift: bool = False
    # data geometry (campaign-2: the sealed factor set is fifteen; pre-campaign
    # checkpoints recorded n_factors explicitly, so their hashes are unaffected)
    block_months: int = bridge.BLOCK_MONTHS
    n_factors: int = 15
    cond_dim: int = bridge.C_B_DIM

    def __post_init__(self) -> None:
        if self.solver not in SOLVERS:
            raise JoineryError(f"unknown solver '{self.solver}'; known: {list(SOLVERS)}")
        if self.time_dist not in TIME_DISTRIBUTIONS:
            raise JoineryError(
                f"unknown time_dist '{self.time_dist}'; known: {list(TIME_DISTRIBUTIONS)}"
            )
        per = _EVALS_PER_STEP[self.solver]
        for name in ("eval_nfe", "aux_nfe"):
            nfe = int(getattr(self, name))
            if nfe < per:
                raise JoineryError(f"{name} {nfe} is below one {self.solver} step ({per})")
            if nfe % per:
                raise JoineryError(
                    f"solver '{self.solver}' costs {per} evaluations per step, so {name} "
                    f"must be even; got {nfe}"
                )
        if self.cond_dropout <= 0.0 and self.guidance_scale != 1.0:
            # Normalized BEFORE hashing: the null branch has no gradient path
            # without dropout, so guiding on it would sample from an untrained
            # embedding, and two configs that differ only there are one model.
            object.__setattr__(self, "guidance_scale", 1.0)

    @property
    def guidance_active(self) -> bool:
        return self.cond_dropout > 0.0 and self.guidance_scale != 1.0

    @property
    def sampling_nfe(self) -> int:
        """TRUE network evaluations per block — what the sealed NFE tie-break means."""
        return int(self.eval_nfe) * (2 if self.guidance_active else 1)

    def as_dict(self) -> dict[str, Any]:
        doc = {k: getattr(self, k) for k in sorted(self.__dataclass_fields__)}
        if not doc["residual_drift"]:
            # Hash stability: the field postdates the sealed WP2.9 selection, so
            # omitting it at its default keeps every pre-A' config_hash — the
            # sealed selection's included — byte-identical on recomputation.
            del doc["residual_drift"]
        return doc

    def build_model(self) -> ConditionalVelocityField:
        """The family's model factory (:class:`ah.gen.blocks.train.BlockConfig`)."""
        return ConditionalVelocityField(self)


class ConditionalVelocityField(nn.Module):
    """v_θ(x_t, t, c) — the shared backbone with a time token and a null embedding."""

    #: What the checkpoint meta records as the S-term's generative half.
    objective_name = "fixed-time-grid rectified-flow velocity objective"

    def __init__(self, config: FlowConfig) -> None:
        super().__init__()
        self.config = config
        d = config.d_model
        self.x_proj = nn.Linear(config.n_factors, d)
        self.pos = nn.Parameter(torch.zeros(config.block_months, d))
        self.time_mlp = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, d))
        freq = torch.exp(torch.linspace(0.0, math.log(1000.0), d // 2))
        self.register_buffer("freq", freq)
        self.cond_proj = nn.ModuleList(nn.Linear(hi - lo, d) for lo, hi in COND_GROUPS)
        #: The learned unconditional embedding, in STANDARDIZED c_b space. Zero
        #: init makes it the standardized mean conditioning at step 0.
        self.null_cond = nn.Parameter(torch.zeros(config.cond_dim))
        self.blocks = nn.ModuleList(
            TransformerBlock(d, config.n_heads, config.ffn_mult, config.dropout)
            for _ in range(config.n_layers)
        )
        self.ln_out = nn.LayerNorm(d)
        self.out = nn.Linear(d, config.n_factors)
        nn.init.zeros_(self.out.weight)  # v_θ == 0 at init: the ODE is the identity
        nn.init.zeros_(self.out.bias)

    def _time_embedding(self, t: torch.Tensor) -> torch.Tensor:
        # t in (0, 1) scaled to the same order as the 3a sigma embedding's input
        return self.time_mlp(sinusoidal_embedding(t * 4.0 - 2.0, self.freq))

    def forward(self, x_t: torch.Tensor, t: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """``x_t`` (B, L, F) on the interpolant; ``t`` (B,); ``cond`` (B, 18) standardized."""
        emb = self._time_embedding(t)  # (B, d)
        tokens = [
            proj(cond[:, lo:hi]) for proj, (lo, hi) in zip(self.cond_proj, COND_GROUPS, strict=True)
        ]
        context = torch.stack([*tokens, emb], dim=1)  # (B, 5, d)
        h = self.x_proj(x_t) + self.pos[None, :, :] + emb[:, None, :]
        for block in self.blocks:
            h = block(h, context)
        return self.out(self.ln_out(h))

    # -- the shared BlockModel surface (ah.gen.blocks.train.BlockModel) ------ #

    def net_call(self, x: torch.Tensor, t: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """The one network entry the sampler traces and integrates: v_θ(x, t, c)."""
        return self.forward(x, t, cond)

    def guided_velocity(
        self, x: torch.Tensor, t: torch.Tensor, cond: torch.Tensor, scale: float
    ) -> torch.Tensor:
        """``v_uncond + scale * (v_cond - v_uncond)`` (one call when scale == 1)."""
        v_cond = self.net_call(x, t, cond)
        if scale == 1.0:
            return v_cond
        v_null = self.net_call(x, t, self.null_cond.expand(x.shape[0], -1))
        return v_null + scale * (v_cond - v_null)

    def make_objective(self) -> FlowMatchingObjective:
        return FlowMatchingObjective(self, self.config)

    def sample(
        self,
        cond: torch.Tensor,
        noise: torch.Tensor,
        nfe: int,
        guidance_scale: float | None = None,
    ) -> torch.Tensor:
        """Differentiable deterministic sampling (the training aux path uses it).

        ``nfe`` is the STEP BUDGET in unguided network evaluations, so the step
        count is the same with and without guidance and the validation-fold
        sampler is the one that will be deployed. Guidance then costs twice as
        many actual evaluations, which is what :attr:`FlowConfig.sampling_nfe`
        reports and what the sealed tie-break reads.

        ``guidance_scale`` overrides the config's own setting. It exists for the
        bake-off's guidance ABLATION, which must score the same checkpoint as it
        will actually be sampled — otherwise an ablation arm would carry the
        unguided arm's numbers. It is never used by training or by the sealed
        selection, both of which take the config's value.
        """
        scale = self.config.guidance_scale if guidance_scale is None else float(guidance_scale)
        guided = scale != 1.0 and self.config.cond_dropout > 0.0
        return flow_integrate(
            self.net_call,
            self.config,
            cond,
            noise,
            int(nfe) * (2 if guided else 1),
            null_cond=self.null_cond,
            guidance_scale=scale if guided else 1.0,
        )


class FlowMatchingObjective:
    """The 3b generative objective behind :class:`losses.GenerativeObjective`.

    ``validation_objective`` is evaluated on the FIXED time grid
    (:data:`losses.VAL_TIME_GRID`) with noise from a fixed-seed generator —
    identical (x, t, x_0) triples for every trial and every evaluation, so the
    number is comparable across configs whose *training* time distributions
    differ. Conditioning dropout is TRAINING ONLY: the validation number always
    measures the conditional model, or a config could improve its score by
    learning to ignore its conditioning.
    """

    VAL_NOISE_SEED = 774_002

    def __init__(self, model: ConditionalVelocityField, config: FlowConfig) -> None:
        self.model = model
        self.config = config

    def draw_time(
        self, n: int, generator: torch.Generator, device: torch.device | str
    ) -> torch.Tensor:
        """``t`` for a training batch, strictly inside (0, 1) under both laws."""
        if self.config.time_dist == "logit_normal":
            z = torch.randn(n, generator=generator, device=device)
            return torch.sigmoid(self.config.time_logit_std * z)
        # uniform, endpoints excluded (the target is degenerate at t in {0, 1})
        u = torch.rand(n, generator=generator, device=device)
        return u.clamp(1e-4, 1.0 - 1e-4)

    def _velocity_mse(
        self, x: torch.Tensor, cond: torch.Tensor, t: torch.Tensor, noise: torch.Tensor
    ) -> torch.Tensor:
        tb = t[:, None, None]
        x_t = (1.0 - tb) * noise + tb * x
        target = x - noise
        return ((self.model.forward(x_t, t, cond) - target) ** 2).mean()

    def training_loss(
        self, x: torch.Tensor, cond: torch.Tensor, generator: torch.Generator
    ) -> torch.Tensor:
        b = x.shape[0]
        t = self.draw_time(b, generator, x.device)
        noise = torch.randn(x.shape, generator=generator, device=x.device, dtype=x.dtype)
        if self.config.cond_dropout > 0.0:
            keep = (
                torch.rand(b, generator=generator, device=x.device) >= self.config.cond_dropout
            ).to(x.dtype)[:, None]
            cond = keep * cond + (1.0 - keep) * self.model.null_cond[None, :]
        return self._velocity_mse(x, cond, t, noise)

    @torch.no_grad()
    def validation_objective(self, x: torch.Tensor, cond: torch.Tensor) -> float:
        gen = torch.Generator(device="cpu").manual_seed(self.VAL_NOISE_SEED)
        total = 0.0
        for value in VAL_TIME_GRID:
            t = torch.full((x.shape[0],), value, device=x.device, dtype=x.dtype)
            noise = torch.randn(x.shape, generator=gen).to(device=x.device, dtype=x.dtype)
            total += float(self._velocity_mse(x, cond, t, noise))
        return total / len(VAL_TIME_GRID)


def flow_integrate(
    velocity: Any,  # callable (x, t_batch, cond) -> velocity
    config: FlowConfig,
    cond: torch.Tensor,
    noise: torch.Tensor,
    nfe: int,
    *,
    null_cond: torch.Tensor | None = None,
    guidance_scale: float = 1.0,
) -> torch.Tensor:
    """Deterministic ODE integration from t=0 (noise) to t=1; exactly ``nfe`` evals.

    ``nfe`` counts NETWORK evaluations, so under classifier-free guidance (two
    evaluations per velocity) the step count halves for the same budget — the
    honest accounting, and the one the sealed tie-break needs. Differentiable
    when called under grad (the training-time auxiliary backpropagates through a
    small-NFE version of this loop). ``velocity`` may be the eager
    :meth:`ConditionalVelocityField.net_call` or a traced equivalent — the
    integration path is identical.
    """
    per_velocity = 2 if (guidance_scale != 1.0 and null_cond is not None) else 1
    per_step = _EVALS_PER_STEP[config.solver] * per_velocity
    steps = int(nfe) // per_step
    if steps < 1:
        raise JoineryError(
            f"nfe {nfe} buys no complete {config.solver} step ({per_step} network evaluations each)"
        )

    def field(x: torch.Tensor, t_value: torch.Tensor) -> torch.Tensor:
        t = t_value.expand(x.shape[0])
        v_cond = velocity(x, t, cond)
        if per_velocity == 1:
            return v_cond
        assert null_cond is not None
        v_null = velocity(x, t, null_cond.expand(x.shape[0], -1))
        return v_null + guidance_scale * (v_cond - v_null)

    ts = torch.linspace(0.0, 1.0, steps + 1, dtype=noise.dtype, device=noise.device)
    x = noise
    for i in range(steps):
        t0, t1 = ts[i], ts[i + 1]
        dt = t1 - t0
        k1 = field(x, t0)
        if config.solver == "heun":
            k2 = field(x + dt * k1, t1)
            x = x + dt * 0.5 * (k1 + k2)
        else:
            x = x + dt * k1
    return x


# --------------------------------------------------------------------------- #
# the joinery-facing sampler (BlockSampler protocol) — shared machinery
# --------------------------------------------------------------------------- #


class FlowBlockSampler(TorchBlockSampler):
    """The trained 3b sampler: :func:`flow_integrate` over the rectified path.

    Everything the joinery depends on — the cb-v1 fingerprint refusal, the
    per-decade noise contract, the fixed-width/zero-padded batching that buys
    composition invariance, the batch-1 tracing policy, the de-standardize +
    constraint-inverse output map — is inherited verbatim from
    :class:`~ah.gen.blocks.diffusion.TorchBlockSampler`. Only ``_integrate``
    differs. That is what "behind the identical interface" means here: not two
    implementations that agree, one implementation with two integrators.

    ``guidance_scale`` overrides the checkpoint's own setting so the bake-off can
    report the SAME checkpoint with and without guidance, which §WP2.9 requires
    of any guidance arm.
    """

    def __init__(self, *args: Any, guidance_scale: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        config = self._model.config
        default = config.guidance_scale if config.guidance_active else 1.0
        self.guidance_scale = float(default if guidance_scale is None else guidance_scale)
        if self.guidance_scale != 1.0 and config.cond_dropout <= 0.0:
            raise JoineryError(
                "classifier-free guidance needs a trained null branch "
                "(cond_dropout > 0); this checkpoint has none"
            )

    @property
    def nfe_per_block(self) -> int:
        return int(self.nfe) * (2 if self.guidance_scale != 1.0 else 1)

    def _integrate(self, cond: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
        return flow_integrate(
            self._call_net,
            self._model.config,
            cond,
            noise,
            self.nfe_per_block,
            null_cond=self._model.null_cond,
            guidance_scale=self.guidance_scale,
        )


# --------------------------------------------------------------------------- #
# checkpoint identity + the registered generator
# --------------------------------------------------------------------------- #


def load_checkpoint(path: str | Path, *, map_location: str = "cpu"):
    """Load a WP2.9 checkpoint dict; verify its recorded SHA-256 over weights.

    Returns ``(model, standardization, meta)`` — the 3a contract exactly, so a
    caller that handles one handles both.
    """
    from ah.gen.blocks.train import state_dict_sha256

    doc = torch.load(Path(path), map_location=map_location, weights_only=False)
    config = FlowConfig(**doc["config"])
    model = config.build_model()
    model.load_state_dict(doc["state_dict"])
    recorded = doc["meta"]["checkpoint_hash"]
    actual = state_dict_sha256(model.state_dict())
    if actual != recorded:
        raise JoineryError(
            f"checkpoint hash mismatch: recorded {recorded[:16]}..., recomputed {actual[:16]}..."
        )
    std = Standardization.from_dict(doc["standardization"])
    return model, std, doc["meta"]


_REPO_ROOT = Path(__file__).resolve().parents[4]
#: CAMPAIGN-2 PROMOTION (2026-08-03, verdict PROMOTE, per-seed route -- see
#: artifacts/campaign2/promotion-verdict.json and PROMOTION.md): the primary
#: checkpoint is the campaign-2 seed-0 artifact, trained on the sealed
#: fifteen-factor vintage 2026-08-02.4 at the sealed WP2.9 selection config
#: (n_factors following the sealed factor set; C3: no residual drift, guidance
#: 1.0). The G2-era artifact (experiments/l3b-flow-final/checkpoint.pt,
#: b1fe26e100678a26...) remains the generator of record FOR G2'S CLAIMS on
#: vintage 2026-07-26.1 and is superseded, not invalidated.
DEFAULT_CHECKPOINT = _REPO_ROOT / "experiments" / "campaign2-flow-s0" / "checkpoint.pt"

#: The primary WP2.9 checkpoint: the sealed-selection config (cfg:5943f6cd2f6f1048
#: — d_model 192 / 4 layers, euler at NFE 4, cond_dropout 0.2, guidance_scale 1.0,
#: cond_noise_std 0.1, lambda_tail 0.3) trained to early stopping on validation S,
#: seed 20260728, campaign vintage 2026-07-26.1. Written by
#: ``scripts/train_flow_final.py`` and verified on every factory call, exactly as
#: the 3a pin is. NOTE the checkpoint HAS a trained null branch (cond_dropout
#: 0.2) even though the sealed criterion selected guidance OFF — so the same
#: weights can be sampled with and without guidance, which is what the bake-off's
#: guidance ablation uses.
PINNED_CHECKPOINT_SHA256: str | None = (
    "c6addb5420723e59c9966dd65c1127d18eca46097049ff7434295cab512f9873"
)

#: Sampler construction defaults for the registry factory (which takes no
#: arguments). Identical mechanism and identical defaults to 3a's, so no result
#: moves without someone asking for it. ``DEFAULT_GUIDANCE_SCALE = None`` means
#: "whatever the checkpoint was selected with".
DEFAULT_BLOCK_BATCH: int = 1
DEFAULT_SAMPLER_DEVICE: str = "cpu"
DEFAULT_GUIDANCE_SCALE: float | None = None


class HierFlowV1(HierBlockSystem):
    """System D, 3b arm — the trained rectified-flow sampler."""

    generator_id = GENERATOR_ID
    system_description = "L1+L2+L4 (hier-flow-v1 blocks)"


def hier_flow_v1_factory() -> HierFlowV1:
    """Construct the trained system D (3b) from the pinned checkpoint + artifacts.

    Raises when the checkpoint is absent, its weight hash differs from
    :data:`PINNED_CHECKPOINT_SHA256`, its recorded c_b fingerprint differs from
    the runtime's, or the L1/L2 artifact SHAs differ from the WP2.7 pins.
    """
    from ah.gen.bootstrap import CAMPAIGN2_VINTAGE_ID, campaign_source
    from ah.gen.climate.simulate import load_artifact as load_climate

    # CAMPAIGN-2 pins throughout: hier-flow-v1 is a campaign-2 artifact and
    # its whole lineage -- checkpoint, L1/L2 layers, vintage -- is frozen
    # history (the live PINNED_* moved to campaign-3 at AM-2026-08-10-001).
    from ah.gen.joinery.assemble import (
        CAMPAIGN2_DEFAULT_CLIMATE_ARTIFACT,
        CAMPAIGN2_DEFAULT_REGIMES_ARTIFACT,
        CAMPAIGN2_PINNED_CLIMATE_SHA256,
        CAMPAIGN2_PINNED_REGIMES_SHA256,
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
    climate = load_climate(CAMPAIGN2_DEFAULT_CLIMATE_ARTIFACT)
    regimes_artifact = load_regimes(CAMPAIGN2_DEFAULT_REGIMES_ARTIFACT)
    if climate.meta["content_sha256"] != CAMPAIGN2_PINNED_CLIMATE_SHA256:
        raise JoineryError("climate artifact sha != WP2.7 pin")
    if regimes_artifact.meta["content_sha256"] != CAMPAIGN2_PINNED_REGIMES_SHA256:
        raise JoineryError("regimes artifact sha != WP2.7 pin")
    if meta.get("climate_sha256") != CAMPAIGN2_PINNED_CLIMATE_SHA256:
        raise JoineryError("checkpoint was trained against a different L1 artifact")
    # hier-flow-v1 is a CAMPAIGN-2 artifact: its checkpoint's feature
    # dimensions and c_b fingerprint are facts about the campaign-2 vintage,
    # so its factory pins that vintage rather than the live campaign default
    # (which moves at the campaign-3 seal). hier-flow-v2 registers its own
    # factory against the extended panel when it trains.
    source = campaign_source(vintage_id=CAMPAIGN2_VINTAGE_ID)
    sampler = FlowBlockSampler(
        model,
        std,
        tuple(source.factor_names),
        trained_fingerprint=meta["cb_fingerprint"],
        device=DEFAULT_SAMPLER_DEVICE,
        block_batch=DEFAULT_BLOCK_BATCH,
        guidance_scale=DEFAULT_GUIDANCE_SCALE,
    )
    system = HierFlowV1(climate, regimes_artifact, source, sampler)
    system.checkpoint_hash = meta["checkpoint_hash"]
    system.config_hash = meta.get("config_hash")
    return system


registry.register(GENERATOR_ID, hier_flow_v1_factory)
