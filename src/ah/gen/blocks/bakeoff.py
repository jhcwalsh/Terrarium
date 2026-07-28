"""WP2.9 bake-off — the like-for-like harness over both L3 sampler families.

§WP2.9: *"Bake-off harness: same data, seeds, conditioning, compute budget;
report quality **and** sampling cost (NFE, wall-clock per 10k decades)."*
Acceptance: *"both samplers through one entry point; like-for-like bake-off
table."* This module is that entry point, in library form so WP2.10 can drive
both arms of ablation system D from one call rather than two scripts.

WHAT IS COMPARABLE AND WHAT IS NOT — the sealed honesty requirement, wired in
rather than left to the writer. ``pre-registration.yaml``'s
``tuning_protocol.selection_criterion`` records that system D runs two samplers
whose generative objectives are different quantities, that they are therefore
SEPARATELY SELECTED, that a fixed ``selection_lambda`` gives the D4 tail
auxiliary a different EFFECTIVE weight in each, and that the binding
consequence is to *report BOTH terms of S separately, per sampler, with their
scales*. So :func:`render_markdown` prints the two S terms in separate columns,
never a cross-sampler S ranking, and prints
:data:`INCOMPARABILITY_NOTE` verbatim above the table. What IS like-for-like
and is compared directly: sampling cost (NFE, wall clock, throughput), the D4
tail auxiliary term alone (the same estimator on the same folds with the same
noise seeds for both), conditioning response, and — once WP2.10 runs them —
battery outcomes and reconciliation diagnostics.

Everything here is measurement only: no module in this package imports
``ah.eval`` (AST-enforced), nothing reads the holdout, and nothing written here
feeds a training or selection decision. The conditioning-response measurement is
the ``artifacts/wp28/ig-spread-diagnosis.md`` §4 table generalized over an
arbitrary sampler, so the two families' responsiveness is measured the same way.
"""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ah.gen.blocks import constraints as ct
from ah.gen.blocks import data as bd
from ah.gen.joinery import bridge

__all__ = [
    "ARM_IDS",
    "INCOMPARABILITY_NOTE",
    "BakeoffRow",
    "SamplingCost",
    "build_sampler",
    "conditioning_response",
    "fold_scores",
    "measure_sampling_cost",
    "render_markdown",
]

#: The two arms of ablation system D, in registry-id form.
ARM_IDS: tuple[str, ...] = ("hier-diffusion-v1", "hier-flow-v1")

INCOMPARABILITY_NOTE = (
    "The two `gen` columns are NOT on one scale and must not be ranked against "
    "each other: 3a's is a sigma-weighted denoising MSE on a fixed sigma grid, "
    "3b's is an unweighted velocity MSE on a fixed time grid. The sealed "
    "tuning_protocol records exactly this and requires both terms of S to be "
    "reported separately, per sampler, with their scales -- so `S` is shown "
    "per arm as the quantity each arm was SELECTED by, never as a cross-arm "
    "ranking. Directly comparable: the `aux` column (the same D4 elicitability "
    "estimator, same folds, same noise seeds), sampling cost, conditioning "
    "response, and battery outcomes."
)


#: Blocks a decade costs at the joinery's stride: starts at 0, stride, 2*stride...
def blocks_per_decade(months: int = 120, stride: int = bridge.BLOCK_STRIDE) -> int:
    return len(range(0, months, stride))


@dataclass(frozen=True)
class SamplingCost:
    """What one arm costs to sample from, at a DECLARED width and device."""

    arm: str
    device: str
    block_batch: int
    nfe_per_block: int
    n_blocks_measured: int
    wall_seconds: float

    @property
    def blocks_per_second(self) -> float:
        return self.n_blocks_measured / self.wall_seconds if self.wall_seconds > 0 else float("inf")

    @property
    def seconds_per_decade(self) -> float:
        return blocks_per_decade() / self.blocks_per_second

    @property
    def seconds_per_10k_decades(self) -> float:
        return 10_000.0 * self.seconds_per_decade

    @property
    def nfe_per_10k_decades(self) -> int:
        return 10_000 * blocks_per_decade() * self.nfe_per_block

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "device": self.device,
            "block_batch": self.block_batch,
            "nfe_per_block": self.nfe_per_block,
            "n_blocks_measured": self.n_blocks_measured,
            "wall_seconds": self.wall_seconds,
            "blocks_per_second": self.blocks_per_second,
            "seconds_per_decade": self.seconds_per_decade,
            "seconds_per_10k_decades": self.seconds_per_10k_decades,
            "nfe_per_10k_decades": self.nfe_per_10k_decades,
        }


@dataclass
class BakeoffRow:
    """One arm's row of the like-for-like table."""

    arm: str
    checkpoint_hash: str | None = None
    config_hash: str | None = None
    generative_objective: str = ""
    gen_term: float = float("nan")
    aux_term: float = float("nan")
    selection_lambda: float = 1.0
    guidance_scale: float = 1.0
    cost: SamplingCost | None = None
    conditioning: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def s_value(self) -> float:
        return self.gen_term + self.selection_lambda * self.aux_term

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "checkpoint_hash": self.checkpoint_hash,
            "config_hash": self.config_hash,
            "generative_objective": self.generative_objective,
            "gen_term": self.gen_term,
            "aux_term": self.aux_term,
            "selection_lambda": self.selection_lambda,
            "s_value": self.s_value,
            "guidance_scale": self.guidance_scale,
            "cost": self.cost.as_dict() if self.cost else None,
            "conditioning": self.conditioning,
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------- #
# construction — one call reaches either family
# --------------------------------------------------------------------------- #


def build_sampler(
    arm: str,
    checkpoint_path: Any = None,
    *,
    device: str = "cpu",
    block_batch: int = 1,
    factor_names: tuple[str, ...] | None = None,
    standardization: bd.Standardization | None = None,
    guidance_scale: float | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Load one arm's trained sampler; returns ``(sampler, checkpoint meta)``.

    ``arm`` is the registry generator id. The two families' ``load_checkpoint``
    functions return the identical ``(model, standardization, meta)`` triple, so
    this dispatch is the only place the harness knows there are two of them.
    """
    if arm == "hier-diffusion-v1":
        from ah.gen.blocks import diffusion as fam

        path = fam.DEFAULT_CHECKPOINT if checkpoint_path is None else checkpoint_path
        model, std, meta = fam.load_checkpoint(path, map_location=device)
        sampler_cls: Any = fam.DiffusionBlockSampler
        extra: dict[str, Any] = {}
    elif arm == "hier-flow-v1":
        from ah.gen.blocks import flow as fam  # type: ignore[no-redef]

        path = fam.DEFAULT_CHECKPOINT if checkpoint_path is None else checkpoint_path
        model, std, meta = fam.load_checkpoint(path, map_location=device)
        sampler_cls = fam.FlowBlockSampler
        extra = {"guidance_scale": guidance_scale}
    else:
        raise ValueError(f"unknown bake-off arm '{arm}'; known: {list(ARM_IDS)}")

    # The WP2.8 checkpoint predates train.py's `generative_objective` key, so it
    # is filled from the model class rather than left blank -- the bake-off's
    # whole point is that each `gen` number is labelled with the quantity it is.
    meta = {**meta}
    meta.setdefault("generative_objective", type(model).objective_name)
    meta["supports_guidance"] = bool(getattr(model.config, "cond_dropout", 0.0) > 0.0)

    names = tuple(meta["factor_names"]) if factor_names is None else factor_names
    sampler = sampler_cls(
        model,
        standardization if standardization is not None else std,
        names,
        trained_fingerprint=meta["cb_fingerprint"],
        device=device,
        block_batch=block_batch,
        **extra,
    )
    return sampler, meta


def fold_scores(
    sampler: Any,
    dataset: bd.BlockDataset,
    compiled: Any,
    *,
    n_rep: int = 16,
    device: str = "cpu",
) -> dict[str, Any]:
    """Both sealed S terms for an arm, scored AS IT IS ACTUALLY SAMPLED.

    Delegates to :func:`ah.gen.blocks.train.evaluate_fold_scores` — the same code
    path both arms were selected by — but binds the auxiliary's generation step
    to the SAMPLER, not to the model's config. That matters for exactly one
    thing: a guidance-ablation arm is the selected checkpoint sampled at a
    different guidance scale, and scoring it through ``model.sample`` would hand
    it the selected arm's numbers. The ``gen`` term is unaffected either way,
    because a velocity/denoising objective involves no sampling at all — which
    is itself worth stating rather than leaving for a reader to infer.
    """
    from ah.gen.blocks.train import evaluate_fold_scores

    scale = getattr(sampler, "guidance_scale", None)
    model = sampler._model
    sample_fn: Any = None
    if scale is not None:
        sample_fn = functools.partial(model.sample, guidance_scale=scale)

    return evaluate_fold_scores(
        model, dataset, compiled, n_rep=n_rep, device=device, sample_fn=sample_fn
    )


# --------------------------------------------------------------------------- #
# sampling cost
# --------------------------------------------------------------------------- #


def measure_sampling_cost(
    sampler: Any,
    *,
    arm: str,
    n_blocks: int = 256,
    seed: int = 20260728,
    warmup_blocks: int = 8,
) -> SamplingCost:
    """Wall clock for ``n_blocks`` blocks through the sampler's batched entry.

    Measured at the sampler's OWN declared width and device (both are recorded
    on the result, per §WP2.9's "batched-throughput numbers at a declared
    width/device"). A warm-up pass is run and discarded so tracing, kernel
    selection and CUDA context creation are not charged to the measurement.
    The RNG contract is the joinery's: one generator per block.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    n_cond = bridge.C_B_DIM

    def slate(n: int, offset: int) -> tuple[list[Any], list[Any]]:
        conds = [
            bridge.BlockConditioning(
                regime_onehot=np.eye(6)[i % 6],
                state_snapshot=rng.standard_normal(5),
                history_summary=rng.standard_normal(3),
                waypoint_increments=rng.standard_normal(4),
                start_month=3 * i,
            )
            for i in range(n)
        ]
        assert len(conds[0].to_vector()) == n_cond
        return conds, [np.random.Generator(np.random.PCG64(seed + offset + i)) for i in range(n)]

    if warmup_blocks > 0:
        c, r = slate(warmup_blocks, 10_000)
        sampler.sample_blocks(c, r)

    conds, rngs = slate(n_blocks, 0)
    t0 = time.perf_counter()
    sampler.sample_blocks(conds, rngs)
    wall = time.perf_counter() - t0
    return SamplingCost(
        arm=arm,
        device=str(getattr(sampler, "device", "cpu")),
        block_batch=int(getattr(sampler, "block_batch", 1)),
        nfe_per_block=int(getattr(sampler, "nfe_per_block", getattr(sampler, "nfe", 0))),
        n_blocks_measured=int(n_blocks),
        wall_seconds=float(wall),
    )


# --------------------------------------------------------------------------- #
# conditioning response (the ig-spread-diagnosis §4 table, generalized)
# --------------------------------------------------------------------------- #

#: (c_b component index, the block feature it is supposed to steer). The five
#: rows WP2.8's diagnosis measured, in its order, so the two tables line up.
RESPONSE_CHANNELS: tuple[tuple[str, int, str, float, float], ...] = (
    ("dw_equity_cum_log", 16, "equity_cum_log", -0.10, 0.10),
    ("state_pi_star", 6, "policy_mean_pct", 0.0, 4.0),
    ("dw_log_cpi", 15, "cpi_within_block_log", -0.02, 0.02),
    ("h_spread_level_pct", 13, "spread_mean_pct", 0.5, 1.5),
    ("dw_spread_center_pct", 17, "spread_within_block_change", -0.5, 0.5),
    ("dw_policy_rate_pct", 14, "policy_mean_pct", -1.0, 1.0),
)


def _block_features(blocks: np.ndarray, names: list[str]) -> dict[str, np.ndarray]:
    """The quantities the c_b channels are supposed to steer, per block."""
    pcol = names.index("policy_rate")
    ccol = names.index("cpi")
    ecol = names.index("equity_mkt")
    scol = names.index("ig_spread")
    return {
        "policy_mean_pct": blocks[:, :, pcol].mean(axis=1),
        "cpi_within_block_log": np.log(blocks[:, -1, ccol] / blocks[:, 0, ccol]),
        "equity_cum_log": np.log1p(blocks[:, :, ecol]).sum(axis=1),
        "spread_mean_pct": blocks[:, :, scol].mean(axis=1),
        "spread_within_block_change": blocks[:, -1, scol] - blocks[:, 0, scol],
    }


def _ols_slope(y: np.ndarray, x: np.ndarray) -> float:
    x = x - x.mean()
    denom = float(x @ x)
    return float(x @ (y - y.mean()) / denom) if denom > 0 else float("nan")


def conditioning_response(
    sampler: Any,
    dataset: bd.BlockDataset,
    *,
    n_probe: int = 256,
    seed: int = 4242,
) -> dict[str, Any]:
    """Finite-difference channel response vs the historical OLS slope.

    Reproduces ``artifacts/wp28/ig-spread-diagnosis.md`` §4 for ANY sampler:
    ``n_probe`` historical conditioning vectors form the base slate, the
    sampling noise is held FIXED across every sweep, and one c_b component is
    moved at a time. The historical side is the univariate OLS slope of the same
    relation over the dataset's own overlapping blocks — train+validation only,
    the holdout is not reachable from this package.

    ``ratio`` is model slope / historical slope: 1.0 is a sampler that steers
    its output as strongly as the data says it should, and WP2.8's trained 3a
    model measured 0.78 down to 0.02 depending on the channel.

    ONE DELIBERATE DIFFERENCE FROM THE WP2.8 DIAGNOSIS SCRIPT, stated so the two
    tables are not read as identical: the regime row's historical side here is
    ``dataset.stats.spread_mean_by_regime``, which ``build_dataset`` computes on
    the TRAIN SEGMENT only (split hygiene, ``data.py``), where
    ``scripts/diagnose_ig_spread.py`` used whole-panel stats. The difference is
    a few basis points on the band centres and it applies identically to every
    arm, so the cross-arm comparison this function exists for is unaffected;
    only a direct read-across to the diagnosis' printed numbers is.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    names = list(dataset.factor_names)
    base = dataset.cond[rng.choice(dataset.cond.shape[0], size=n_probe, replace=True)].copy()
    noise = rng.standard_normal((n_probe, dataset.block_months, len(names)))

    hist_blocks = ct.panel_to_constrained(dataset.x, dataset.factor_names)
    hist_features = _block_features(hist_blocks, names)

    def model_slope(component: int, feature: str, lo: float, hi: float) -> float:
        values = []
        for value in (lo, hi):
            v = base.copy()
            v[:, component] = value
            blocks = sampler.sample_batch(v, noise)
            values.append(float(_block_features(blocks, names)[feature].mean()))
        return (values[1] - values[0]) / (hi - lo)

    channels: dict[str, Any] = {}
    for label, component, feature, lo, hi in RESPONSE_CHANNELS:
        hist = _ols_slope(hist_features[feature], dataset.cond[:, component])
        model = model_slope(component, feature, lo, hi)
        channels[label] = {
            "feature": feature,
            "historical_ols": hist,
            "model_finite_difference": model,
            "ratio": model / hist if hist not in (0.0,) and np.isfinite(hist) else float("nan"),
            "swept_from": lo,
            "swept_to": hi,
        }

    # the regime one-hot: a categorical channel, so its "slope" is the RANGE of
    # generated block-mean ig_spread over the six labels against the range of
    # the historical per-regime means (the diagnosis' bottom row).
    from ah.gen.regimes.semimarkov import REGIME_LABELS

    regime_response: dict[str, float] = {}
    for i, label in enumerate(REGIME_LABELS):
        v = base.copy()
        v[:, 0:6] = 0.0
        v[:, i] = 1.0
        blocks = sampler.sample_batch(v, noise)
        regime_response[label] = float(_block_features(blocks, names)["spread_mean_pct"].mean())
    hist_regime = {
        label: float(x)
        for label, x in zip(REGIME_LABELS, dataset.stats.spread_mean_by_regime, strict=True)
    }
    model_range = max(regime_response.values()) - min(regime_response.values())
    hist_range = max(hist_regime.values()) - min(hist_regime.values())
    channels["regime_onehot"] = {
        "feature": "spread_mean_pct",
        "historical_ols": hist_range,
        "model_finite_difference": model_range,
        "ratio": model_range / hist_range if hist_range > 0 else float("nan"),
        "swept_from": 0.0,
        "swept_to": 1.0,
    }

    return {
        "n_probe": int(n_probe),
        "seed": int(seed),
        "channels": channels,
        "regime_sweep_generated_spread": regime_response,
        "regime_band_centre": hist_regime,
    }


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #


def render_markdown(rows: list[BakeoffRow], *, title: str = "Sampler bake-off") -> str:
    """The like-for-like table, with the sealed incomparability note above it."""
    out = [f"# {title}", "", "> " + INCOMPARABILITY_NOTE.replace("\n", " "), ""]
    out += [
        "| arm | generative objective | gen (own scale) | aux (D4 FZ, shared) | "
        "S = gen + 1.0*aux | guidance | NFE/block | blocks/s | s/decade | s/10k decades |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        c = r.cost
        out.append(
            f"| {r.arm} | {r.generative_objective} | {r.gen_term:.6f} | {r.aux_term:.6f} | "
            f"{r.s_value:.6f} | {r.guidance_scale:g} | "
            + (
                f"{c.nfe_per_block} | {c.blocks_per_second:.1f} | "
                f"{c.seconds_per_decade:.4f} | {c.seconds_per_10k_decades:,.0f} |"
                if c
                else "n/a | n/a | n/a | n/a |"
            )
        )
    if rows and rows[0].cost is not None:
        out += [
            "",
            f"Cost measured at block width "
            f"{', '.join(f'{r.arm}={r.cost.block_batch}@{r.cost.device}' for r in rows if r.cost)}"
            f"; a decade is {blocks_per_decade()} blocks at stride {bridge.BLOCK_STRIDE}.",
        ]

    responsive = [r for r in rows if r.conditioning]
    if responsive:
        labels = [c[0] for c in RESPONSE_CHANNELS] + ["regime_onehot"]
        out += [
            "",
            "## Conditioning response (finite difference vs historical OLS)",
            "",
            "| channel | historical | "
            + " | ".join(f"{r.arm} model / ratio" for r in responsive)
            + " |",
            "|---" * (2 + len(responsive)) + "|",
        ]
        for label in labels:
            first = responsive[0].conditioning["channels"].get(label)
            if first is None:
                continue
            cells = []
            for r in responsive:
                ch = r.conditioning["channels"][label]
                cells.append(f"{ch['model_finite_difference']:+.4f} / {ch['ratio']:.0%}")
            out.append(f"| {label} | {first['historical_ols']:+.4f} | " + " | ".join(cells) + " |")

    notes = [(r.arm, n) for r in rows for n in r.notes]
    if notes:
        out += ["", "## Notes", ""] + [f"- **{arm}**: {n}" for arm, n in notes]
    return "\n".join(out) + "\n"
