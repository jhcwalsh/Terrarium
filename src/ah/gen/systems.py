"""WP2.10 — the five ablation systems A-E as named compositions.

DN-1.1 §II.7's publishable experiment, verbatim, and what each composition here
does about it:

===  =====================================  ==========================================
Sys  DN-1.1 composition                     What it is here
===  =====================================  ==========================================
A    L1+L2 + Gaussian residuals             L1+L2+L4 with :class:`GaussianResidual
     ("modern Wilkie")                      BlockSampler` in place of L3
B    L3 chained autoregressively,           L1+L2+L3+bridge with
     no waypoints                           ``bind_waypoints=False`` (no Δw, no Denton)
C    L3 blocks + naive chaining under       B, plus ``use_climate=False``
     sampled regimes, no L1
D    L1+L2+L3+L4 as specified               ``hier-diffusion-v1`` / ``hier-flow-v1``
E    Regime-stratified block bootstrap      ``bootstrap-v1``
===  =====================================  ==========================================

Every id resolves through :mod:`ah.gen.registry`. D and E were registered by
WP2.8/2.9 and WP2.4; A, B and C are registered here.

Composition choices, stated rather than left to be inferred
-----------------------------------------------------------
**A's residual model is regime-conditional in LOCATION and pooled in DISPERSION.**
The mean is the stratum mean when the stratum carries at least
:data:`GAUSSIAN_MIN_REGIME_OBS` months and the pooled mean otherwise; the
covariance is always the single pooled sample covariance over the whole source.
Two reasons, both about not inventing structure the control is supposed to lack.
(i) L2's output must actually enter A, or "L1+L2+Gaussian residuals" is really
"L1+waypoints+Gaussian residuals" and the letter is wrong; conditioning the mean
on the regime label is the same conditioning channel
:class:`~ah.gen.joinery.bridge.BootstrapBlockSampler` uses, so A-vs-E isolates
*Gaussian versus empirical blocks* rather than *conditioned versus unconditioned*.
(ii) A regime-conditional COVARIANCE cannot be estimated: on the campaign source
the STAG stratum is ~5 months and REF ~9 against twelve factors, so three of six
strata have fewer observations than a 12x12 covariance has free rows. A pooled
covariance over 372 months is always PSD, rests on n/p ~ 31, and adds no fitted
knob. Rows within a block are drawn iid — system A carries no block-level
temporal structure at all, which is the whole point of the control.

**A shares the benchmark's draw-span handicap, and D does not.** A's mean and
covariance come from the same :class:`~ah.gen.bootstrap.BootstrapSource` as
``bootstrap-v1``, i.e. the sealed 1990-01..2020-12 complete-case window, because a
complete-case multivariate covariance over the sealed factor set is bound by
``equity_vol``'s 1990 start exactly as the benchmark's ``block_draw_span`` is. A
pairwise-complete covariance over the longer ragged panel would reach further back
but is not guaranteed positive semi-definite, and repairing that needs a fitted
shrinkage constant. So: A is handicapped like E, D and B/C are not, and any
A-vs-D gap is a *joint* statement about the residual family and the window. This
is the same mechanism ``pre-registration.yaml``'s ``benchmark_draw_span_bias``
discloses for E, and it is recorded here for the same reason.

**A keeps the joinery (L4).** DN-1.1 calls A "L1+L2 + Gaussian residuals"; the
waypoints are the only binding point at which L1 and L2 reach the monthly path at
all, so removing L4 from A would remove L1 and L2 with it. A therefore runs the
full 7-step assembly and differs from D in exactly one component — the block
sampler — which is what makes it the control for "does the neural block generator
earn its place". It also means A's floors are guaranteed by Denton's floor
re-application, which matters because Gaussian draws are not floor-safe.

**B and C run the FLOW arm only.** Running both co-primary samplers through B and
C doubles the ablation grid, and the six extra diffusion cells are the most
expensive in it (WP2.9 measured hier-diffusion-v1 end to end through the joinery
at 4.6x hier-flow-v1). B and C ablate the JOINERY and the CLIMATE LAYER, not the
sampler family: the sampler-family question is answered at full strength in D,
which runs both. ``abl-b-neural-rollout-diffusion`` and
``abl-c-neural-only-diffusion`` are therefore **untested**, and that is recorded
in ``ABLATION.md`` rather than left implicit. Both ids are constructible here (see
:func:`build`) if a later work package wants them.

Seeds
-----
:data:`SEED_PLAN` pairs one TRAINING seed with one SAMPLING seed per index, and
every system uses the same sampling seed at the same index — so a cross-system
difference at index k is never a seed difference. Neural systems additionally
vary the training seed across indices (the sealed
``multi_seed_decision_rule.minimum_seeds`` is 3, and the plan asks for training
seeds, not sampling seeds, on those). Nothing here re-searches or re-selects: the
configs are the sealed selections ``cfg:505f9800900bd757`` (3a) and
``cfg:5943f6cd2f6f1048`` (3b), retrained at further seeds and nothing else.

This module is in ``ah.gen`` and therefore **never imports ``ah.eval``** — the
battery driving lives in ``scripts/run_ablation_grid.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from ah.core.numericworld import NumericWorld
from ah.gen import registry
from ah.gen.base import Ensemble
from ah.gen.bootstrap import BootstrapSource
from ah.gen.climate.simulate import ClimateArtifact
from ah.gen.joinery import bridge
from ah.gen.joinery.assemble import (
    DEFAULT_CLIMATE_ARTIFACT,
    DEFAULT_REGIMES_ARTIFACT,
    PINNED_CLIMATE_SHA256,
    PINNED_REGIMES_SHA256,
    JoineryConfig,
    assemble_decades,
)
from ah.gen.joinery.waypoints import JoineryError
from ah.gen.regimes.semimarkov import REGIME_LABELS, RegimesArtifact

__all__ = [
    "GAUSSIAN_MIN_REGIME_OBS",
    "REGISTERED_ABLATION_IDS",
    "SEED_PLAN",
    "SYSTEMS",
    "SYSTEM_A_ID",
    "SYSTEM_D_V2_ID",
    "SYSTEM_F_ID",
    "AblationSystem",
    "GaussianResidualBlockSampler",
    "SeedIndex",
    "StructureOnlyV1",
    "build",
    "campaign2_seed_checkpoint_manifest_path",
    "neural_only_id",
    "neural_rollout_id",
    "seed_checkpoint_manifest_path",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]

SYSTEM_A_ID = "abl-a-structure-only"

#: System F (ruling K3, AM-2026-08-10-001): the sealed ``ablation_systems.F``
#: id. System D's flow architecture, hyperparameters and seeds, trained with
#: equity_vol MISSING before 1986-01 (``bootstrap.har_masked_source``); at
#: SAMPLING time the composition is identical to D's -- only the checkpoint
#: differs. Its "family" is the flow family throughout: same config, same
#: selection, same train seeds (``train_seed_for`` maps it to flow).
SYSTEM_F_ID = "har-masked"

#: The campaign-3 D sampler (sealed ``ablation_systems.D``: ONE sampler at
#: campaign-3, hier-flow-v2 -- hier-diffusion does not race). The flow
#: architecture and the sealed campaign-2 SELECTION verbatim, retrained on the
#: extended panel; ``hier-flow-v1`` and its pins freeze as the campaign-2
#: replay surface and never move again.
SYSTEM_D_V2_ID = "hier-flow-v2"

#: A regime stratum below this many months does not get its own mean (see the
#: module docstring). Same shape of floor as
#: ``ah.eval.metrics.tails.BACKTEST_MIN_EXCEEDANCES`` and for the same reason: a
#: location estimated from a literal handful of months is noise wearing a label.
#: Twice the twelve-factor width, so the mean rests on more months than the panel
#: has columns.
GAUSSIAN_MIN_REGIME_OBS = 24


def neural_rollout_id(family: str) -> str:
    """System B's registered id for one L3 family (``"diffusion"`` / ``"flow"``)."""
    return f"abl-b-neural-rollout-{_check_family(family)}"


def neural_only_id(family: str) -> str:
    """System C's registered id for one L3 family (``"diffusion"`` / ``"flow"``)."""
    return f"abl-c-neural-only-{_check_family(family)}"


def _check_family(family: str) -> str:
    if family not in ("diffusion", "flow"):
        raise JoineryError(f"unknown L3 family {family!r}; expected 'diffusion' or 'flow'")
    return family


# --------------------------------------------------------------------------- #
# system A: the Gaussian residual block sampler
# --------------------------------------------------------------------------- #


class GaussianResidualBlockSampler:
    """System A's L3 replacement: iid multivariate-normal rows.

    Implements :class:`~ah.gen.joinery.bridge.BlockSampler`. A block is
    ``block_months`` independent draws from ``N(mu_R, Sigma)`` where ``R`` is the
    conditioned regime label, ``mu_R`` is that stratum's mean (or the pooled mean
    when the stratum is thinner than :data:`GAUSSIAN_MIN_REGIME_OBS`) and
    ``Sigma`` is the single pooled sample covariance. See this module's docstring
    for why the covariance is pooled and why that is the simplest defensible
    choice rather than a shortcut.

    Only the regime component of ``c_b`` is read — a Gaussian residual model
    cannot aim at ``s_t``, ``h_t`` or ``Δw``, exactly as the bootstrap stand-in
    cannot. The waypoints reach system A through Denton reconciliation, not
    through the block sampler.

    The Cholesky factor is computed once, at construction, on the pooled
    covariance plus a jitter of ``1e-12 * trace/p`` — enough to make a numerically
    semi-definite sample covariance factorable, far below any factor's own scale,
    and recorded in :attr:`fit_record` so it is never invisible.

    Determinism: every number comes from the ``rng`` the assembler passes in.
    """

    def __init__(self, source: BootstrapSource, *, block_months: int = bridge.BLOCK_MONTHS) -> None:
        if block_months < 1:
            raise JoineryError("block_months must be >= 1")
        values = np.asarray(source.values, dtype=np.float64)
        if values.ndim != 2 or values.shape[0] < 2:
            raise JoineryError("GaussianResidualBlockSampler needs a 2-D source with >= 2 rows")
        self.block_months = int(block_months)
        self.factor_names = tuple(source.factor_names)
        self._n_factors = values.shape[1]

        labels = np.asarray(source.labels)
        pooled_mean = values.mean(axis=0)
        cov = np.cov(values, rowvar=False)
        jitter = 1e-12 * float(np.trace(cov)) / self._n_factors
        self._chol = np.linalg.cholesky(cov + jitter * np.eye(self._n_factors))

        means: dict[str, np.ndarray] = {}
        record: dict[str, Any] = {}
        for label in REGIME_LABELS:
            mask = labels == label
            n_obs = int(mask.sum())
            use_regime = n_obs >= GAUSSIAN_MIN_REGIME_OBS
            means[label] = values[mask].mean(axis=0) if use_regime else pooled_mean
            record[label] = {
                "n_obs": n_obs,
                "mean_source": "regime" if use_regime else "pooled",
            }
        self._means = means
        self.fit_record: dict[str, Any] = {
            "kind": "iid-multivariate-normal",
            "mean_source": "regime-conditional with pooled fallback",
            "covariance_source": "pooled",
            "min_regime_obs": GAUSSIAN_MIN_REGIME_OBS,
            "n_rows": int(values.shape[0]),
            "n_factors": self._n_factors,
            "cholesky_jitter": float(jitter),
            "fitted_span": [str(source.dates[0].date()), str(source.dates[-1].date())],
            "vintage_id": str(source.vintage_id),
            "by_regime": record,
        }

    def sample_block(self, cond: bridge.BlockConditioning, rng: np.random.Generator) -> np.ndarray:
        label = REGIME_LABELS[int(np.argmax(cond.regime_onehot))]
        z = rng.standard_normal((self.block_months, self._n_factors))
        return self._means[label] + z @ self._chol.T


class StructureOnlyV1:
    """Ablation system **A**: L1 + L2 + L4 with Gaussian residual blocks.

    Implements :class:`ah.gen.base.Generator`. Identical to
    :class:`~ah.gen.joinery.assemble.JoineryBootstrapV0` in every respect except
    the block sampler, which is the comparison the letter exists to make.
    """

    generator_id = SYSTEM_A_ID
    system_description = "L1+L2+L4 (Gaussian residual blocks)"

    def __init__(
        self,
        climate: ClimateArtifact,
        regimes_artifact: RegimesArtifact,
        source: BootstrapSource,
        config: JoineryConfig | None = None,
    ) -> None:
        self._climate = climate
        self._regimes = regimes_artifact
        self._source = source
        self._config = JoineryConfig() if config is None else config
        self._sampler = GaussianResidualBlockSampler(source, block_months=self._config.block_months)
        self.checkpoint_hash: str | None = None
        self.config_hash: str | None = None

    def fit(self, data: Any) -> None:
        """Adopt a prepared :class:`BootstrapSource` and refit the residual model."""
        if not isinstance(data, BootstrapSource):
            raise JoineryError(
                f"{self.generator_id}.fit expects a BootstrapSource; got {type(data).__name__}"
            )
        self._source = data
        self._sampler = GaussianResidualBlockSampler(data, block_months=self._config.block_months)

    def _assemble(
        self, *, n_paths: int, seed: int, months: int, world: NumericWorld | None, config
    ) -> Ensemble:
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
        )
        cond = ensemble.meta.conditioning
        cond["system"] = self.system_description
        cond["residual_model"] = self._sampler.fit_record
        ensemble.meta = replace(ensemble.meta, generator_id=self.generator_id)
        return ensemble

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        months = int(world.horizon.quarters) * 3
        return self._assemble(
            n_paths=n_paths, seed=seed, months=months, world=world, config=self._config
        )

    def sample_months(
        self, months: int, n_paths: int, seed: int, *, unfiltered: bool = False
    ) -> Ensemble:
        config = replace(self._config, acceptance_filter=False) if unfiltered else self._config
        return self._assemble(n_paths=n_paths, seed=seed, months=months, world=None, config=config)


def _pinned_layers(*, campaign2: bool = False) -> tuple[ClimateArtifact, RegimesArtifact]:
    """The pinned L1/L2 artifacts, hash-verified — the same check every
    registered hierarchical factory makes. ``campaign2=True`` loads the frozen
    campaign-2 layers (the v1 replay surfaces); the default is the live
    campaign-3 pins (AM-2026-08-10-001)."""
    from ah.gen.climate.simulate import load_artifact as load_climate
    from ah.gen.joinery.assemble import (
        CAMPAIGN2_DEFAULT_CLIMATE_ARTIFACT,
        CAMPAIGN2_DEFAULT_REGIMES_ARTIFACT,
        CAMPAIGN2_PINNED_CLIMATE_SHA256,
        CAMPAIGN2_PINNED_REGIMES_SHA256,
    )
    from ah.gen.regimes.semimarkov import load_artifact as load_regimes

    climate_path = CAMPAIGN2_DEFAULT_CLIMATE_ARTIFACT if campaign2 else DEFAULT_CLIMATE_ARTIFACT
    regimes_path = CAMPAIGN2_DEFAULT_REGIMES_ARTIFACT if campaign2 else DEFAULT_REGIMES_ARTIFACT
    climate_pin = CAMPAIGN2_PINNED_CLIMATE_SHA256 if campaign2 else PINNED_CLIMATE_SHA256
    regimes_pin = CAMPAIGN2_PINNED_REGIMES_SHA256 if campaign2 else PINNED_REGIMES_SHA256
    climate = load_climate(climate_path)
    regimes = load_regimes(regimes_path)
    if climate.meta["content_sha256"] != climate_pin:
        raise JoineryError("climate artifact sha != its campaign's pin")
    if regimes.meta["content_sha256"] != regimes_pin:
        raise JoineryError("regimes artifact sha != its campaign's pin")
    return climate, regimes


def structure_only_v1_factory() -> StructureOnlyV1:
    from ah.gen.bootstrap import campaign_source

    climate, regimes = _pinned_layers()
    return StructureOnlyV1(climate, regimes, campaign_source())


# --------------------------------------------------------------------------- #
# systems B and C: the trained L3 families under reduced joinery
# --------------------------------------------------------------------------- #


def seed_checkpoint_manifest_path() -> Path:
    """Where the LIVE campaign's per-training-seed checkpoint pins live.

    Written by ``scripts/train_ablation_seeds.py``, read here. Same posture as
    ``diffusion.PINNED_CHECKPOINT_SHA256``: a checkpoint whose recomputed weight
    hash differs from its pin is refused, so a run can never quietly cite a
    checkpoint nobody recorded.

    CAMPAIGN-3 (AM-2026-08-10-001): this is the campaign-3 manifest. Retraining
    under the wp210 keys would have OVERWRITTEN the campaign-2 entries and
    broken every B/C/D seed replay -- the third instance of the campaign-split
    trap (vintage id, factor set, now the checkpoint namespace). The frozen
    campaign-2 manifest is :func:`campaign2_seed_checkpoint_manifest_path`,
    and nothing here falls back to it silently.
    """
    return _REPO_ROOT / "configs" / "campaign3-seed-checkpoints.json"


def campaign2_seed_checkpoint_manifest_path() -> Path:
    """HISTORICAL, never moves again: the wp210 (campaign-2) checkpoint pins.

    Read by the campaign-2 replay surfaces (the diffusion arm, which does not
    race at campaign-3, still resolves here)."""
    return _REPO_ROOT / "configs" / "wp210-seed-checkpoints.json"


def _family_module(family: str):
    from ah.gen.blocks import diffusion as df
    from ah.gen.blocks import flow as fl

    return {"diffusion": df, "flow": fl}[_check_family(family)]


def train_seed_for(family: str, seed_index: int) -> int:
    """The TRAINING seed one L3 family uses at one seed index.

    Index 0 is the family's own committed final-training seed — which differs
    between the arms (``configs/wp28-diffusion-search-v1.yaml``'s ``final.seed`` is
    20260727, ``configs/wp29-flow-search-v1.yaml``'s is 20260728) — and later
    indices step it by :data:`SEED_STRIDE`. Keying the grid by INDEX rather than by
    absolute seed is what lets "seed index 1" mean one column across both arms
    despite that historical difference.

    ``har-masked`` (system F) resolves to the FLOW seeds: the sealed K3 clause
    is "identical architecture, hyperparameters and seeds".
    """
    if family == SYSTEM_F_ID:
        family = "flow"
    base = PRIMARY_TRAIN_SEED_BY_FAMILY[_check_family(family)]
    if seed_index < 0:
        raise JoineryError(f"seed_index must be >= 0; got {seed_index}")
    return base + SEED_STRIDE * int(seed_index)


def _manifest_entry(manifest_path: Path, key: str, expected_train_seed: int) -> tuple[Path, str]:
    """Resolve ``key`` in one checkpoint manifest, seed-plan-checked."""
    if not manifest_path.exists():
        raise JoineryError(
            f"no seed-checkpoint manifest at {manifest_path}; run scripts/train_ablation_seeds.py"
        )
    doc = json.loads(manifest_path.read_text("utf-8"))
    if key not in doc:
        raise JoineryError(
            f"seed-checkpoint manifest {manifest_path.name} has no entry '{key}' "
            f"(have: {sorted(doc)})"
        )
    entry = doc[key]
    if int(entry["train_seed"]) != expected_train_seed:
        raise JoineryError(
            f"manifest entry '{key}' records train_seed {entry['train_seed']}, but the seed "
            f"plan says {expected_train_seed}"
        )
    return _REPO_ROOT / entry["checkpoint"], str(entry["checkpoint_hash"])


def _checkpoint_for(family: str, seed_index: int, *, campaign2: bool = False) -> tuple[Path, str]:
    """``(path, expected_weight_sha256)`` for one (family, seed index).

    ``campaign2=True`` is the EXPLICIT campaign-2 route (the hier-*-v1 replay
    surfaces): module pin at index 0, wp210 manifest otherwise -- stated by the
    caller, never inferred.

    Campaign-3 resolution, per the AM-2026-08-10-001 grid:

    - ``flow`` -- the LIVE flow weights are hier-flow-v2's, and EVERY index
      (including 0) resolves through the campaign-3 manifest under
      ``hier-flow-v2:<index>``. There is deliberately no fallback to the
      wp210 manifest or the v1 module pin: a campaign-3 cell evaluated on
      campaign-2 weights is exactly the silent failure this split exists to
      make impossible. The v1 pins remain, untouched, on the flow module for
      the campaign-2 replay surfaces that name them directly.
    - ``har-masked`` (system F) -- campaign-3 manifest, ``har-masked:<index>``.
    - ``diffusion`` -- does not race at campaign-3; still resolves the
      CAMPAIGN-2 pins (module pin at index 0, wp210 manifest otherwise), as
      its replay surfaces always did.
    """
    if family == SYSTEM_F_ID:
        return _manifest_entry(
            seed_checkpoint_manifest_path(),
            f"{SYSTEM_F_ID}:{seed_index}",
            train_seed_for(SYSTEM_F_ID, seed_index),
        )
    if family == "flow" and not campaign2:
        return _manifest_entry(
            seed_checkpoint_manifest_path(),
            f"{SYSTEM_D_V2_ID}:{seed_index}",
            train_seed_for("flow", seed_index),
        )
    module = _family_module(family)
    if seed_index == 0:
        pin = module.PINNED_CHECKPOINT_SHA256
        if pin is None:
            raise JoineryError(f"{family}: no pinned primary checkpoint (train first)")
        return Path(module.DEFAULT_CHECKPOINT), str(pin)
    return _manifest_entry(
        campaign2_seed_checkpoint_manifest_path(),
        f"{family}:{seed_index}",
        train_seed_for(family, seed_index),
    )


def _build_sampler(family: str, seed_index: int, *, campaign2: bool = False):
    """Load and hash-verify one family's checkpoint at one seed index.

    ``har-masked`` loads through the FLOW module (the architecture is D's) but
    resolves its checkpoint under its own manifest keys. ``campaign2=True`` is
    the explicit v1-replay route (see :func:`_checkpoint_for`).
    """
    path, expected = _checkpoint_for(family, seed_index, campaign2=campaign2)
    if family == SYSTEM_F_ID:
        family = "flow"
    module = _family_module(family)
    if not path.exists():
        raise JoineryError(f"{family} checkpoint for seed index {seed_index} not found: {path}")
    model, std, meta = module.load_checkpoint(path)
    if meta["checkpoint_hash"] != expected:
        raise JoineryError(
            f"{family} seed index {seed_index}: checkpoint {meta['checkpoint_hash'][:16]}... "
            f"!= pinned {expected[:16]}..."
        )
    # The lineage check names the checkpoint's OWN campaign's L1 pin: a
    # campaign-2 replay checkpoint records the campaign-2 climate sha, a live
    # (campaign-3) checkpoint records the campaign-3 one.
    from ah.gen.joinery.assemble import CAMPAIGN2_PINNED_CLIMATE_SHA256

    expected_l1 = CAMPAIGN2_PINNED_CLIMATE_SHA256 if campaign2 else PINNED_CLIMATE_SHA256
    if meta.get("climate_sha256") != expected_l1:
        raise JoineryError(f"{family} seed index {seed_index} was trained against a different L1")
    from ah.gen.bootstrap import CAMPAIGN2_VINTAGE_ID, campaign_source

    source = campaign_source(vintage_id=CAMPAIGN2_VINTAGE_ID) if campaign2 else campaign_source()
    kwargs: dict[str, Any] = dict(
        trained_fingerprint=meta["cb_fingerprint"],
        device=module.DEFAULT_SAMPLER_DEVICE,
        block_batch=module.DEFAULT_BLOCK_BATCH,
    )
    if family == "flow":
        kwargs["guidance_scale"] = module.DEFAULT_GUIDANCE_SCALE
        sampler_cls = module.FlowBlockSampler
    else:
        sampler_cls = module.DiffusionBlockSampler
    sampler = sampler_cls(model, std, tuple(source.factor_names), **kwargs)
    return sampler, source, meta


def _hier_class(family: str, letter: str):
    """The Generator wrapper for one (letter, family), built off the shared
    :class:`~ah.gen.blocks.diffusion.HierBlockSystem` so B, C and D differ only in
    their ``JoineryConfig`` and their id."""
    from ah.gen.blocks.diffusion import HierBlockSystem

    system_id = (neural_rollout_id if letter == "B" else neural_only_id)(family)
    description = {
        "B": f"L1+L2+L3+bridge, NO waypoint binding, NO Denton ({family} blocks)",
        "C": f"L2+L3+bridge, NO L1, NO waypoint binding, NO Denton ({family} blocks)",
    }[letter]

    class _Ablation(HierBlockSystem):
        generator_id = system_id
        system_description = description

    _Ablation.__name__ = f"Ablation{letter}{family.capitalize()}"
    _Ablation.__qualname__ = _Ablation.__name__
    return _Ablation


def _ablation_config(letter: str) -> JoineryConfig:
    if letter == "B":
        return JoineryConfig(bind_waypoints=False)
    if letter == "C":
        return JoineryConfig(bind_waypoints=False, use_climate=False)
    raise JoineryError(f"no reduced joinery config for letter {letter!r}")


def build(system_id: str, *, seed_index: int = 0):
    """Construct any ablation system by id, at one seed index.

    ``seed_index`` selects which trained checkpoint a neural system loads; it is
    ignored by the deterministic systems (A, E), which have none — their seed axis
    is the SAMPLING seed, which is an argument to ``sample_months``, not to
    construction.
    """
    seed_index = int(seed_index)
    if system_id == SYSTEM_A_ID:
        return structure_only_v1_factory()
    if system_id == SYSTEM_F_ID:
        # System F (K3): D's flow composition verbatim -- full campaign source,
        # pinned L1/L2, the standard joinery -- differing ONLY in the checkpoint,
        # which was trained on the har-masked dataset and lives under F's own
        # manifest keys. The mask is a TRAINING fact; sampling is identical.
        from ah.gen.blocks.flow import HierFlowV1

        sampler, source, meta = _build_sampler(SYSTEM_F_ID, seed_index)
        climate, regimes = _pinned_layers()

        class _HarMasked(HierFlowV1):
            generator_id = SYSTEM_F_ID
            system_description = (
                "system D's flow architecture trained with equity_vol MISSING "
                "pre-1986-01 (ruling K3; the har_masked_ablation cell)"
            )

        _HarMasked.__name__ = "HarMaskedFlow"
        _HarMasked.__qualname__ = _HarMasked.__name__
        system = _HarMasked(climate, regimes, source, sampler)
        system.checkpoint_hash = meta["checkpoint_hash"]
        system.config_hash = meta.get("config_hash")
        return system
    if system_id == SYSTEM_D_V2_ID:
        # The campaign-3 D: hier-flow-v1's composition verbatim under the v2
        # id, weights from the campaign-3 manifest (every index).
        from ah.gen.blocks.flow import HierFlowV1

        sampler, source, meta = _build_sampler("flow", seed_index)
        climate, regimes = _pinned_layers()

        class _HierFlowV2(HierFlowV1):
            generator_id = SYSTEM_D_V2_ID
            system_description = (
                "L1+L2+L3(flow)+L4 retrained on the extended campaign-3 panel "
                "(the sealed campaign-2 selection, never re-searched)"
            )

        _HierFlowV2.__name__ = "HierFlowV2"
        _HierFlowV2.__qualname__ = _HierFlowV2.__name__
        system = _HierFlowV2(climate, regimes, source, sampler)
        system.checkpoint_hash = meta["checkpoint_hash"]
        system.config_hash = meta.get("config_hash")
        return system
    for letter in ("B", "C"):
        for family in ("diffusion", "flow"):
            builder = neural_rollout_id if letter == "B" else neural_only_id
            if system_id != builder(family):
                continue
            sampler, source, meta = _build_sampler(family, seed_index)
            climate, regimes = _pinned_layers()
            system = _hier_class(family, letter)(
                climate, regimes, source, sampler, _ablation_config(letter)
            )
            system.checkpoint_hash = meta["checkpoint_hash"]
            system.config_hash = meta.get("config_hash")
            return system
    for family in ("diffusion", "flow"):
        module = _family_module(family)
        if system_id != module.GENERATOR_ID:
            continue
        # The v1 ids are CAMPAIGN-2 replay surfaces: explicit campaign-2
        # checkpoint resolution, never the live (campaign-3) manifest.
        if seed_index == 0:
            return registry.resolve(system_id)
        sampler, source, meta = _build_sampler(family, seed_index, campaign2=True)
        climate, regimes = _pinned_layers(campaign2=True)
        cls = module.HierDiffusionV1 if family == "diffusion" else module.HierFlowV1
        system = cls(climate, regimes, source, sampler)
        system.checkpoint_hash = meta["checkpoint_hash"]
        system.config_hash = meta.get("config_hash")
        return system
    return registry.resolve(system_id)


def _register_neural_ablations() -> tuple[str, ...]:
    ids: list[str] = []
    for letter in ("B", "C"):
        for family in ("diffusion", "flow"):
            builder = neural_rollout_id if letter == "B" else neural_only_id
            system_id = builder(family)
            ids.append(system_id)

            def factory(system_id: str = system_id):
                return build(system_id)

            registry.register(system_id, factory)
    return tuple(ids)


# --------------------------------------------------------------------------- #
# the ablation table + the seed plan
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AblationSystem:
    """One row of DN-1.1 §II.7's table, as this repo builds it."""

    letter: str
    system_id: str
    composition: str
    question: str
    neural: bool
    family: str | None = None


@dataclass(frozen=True)
class SeedIndex:
    """One column of the grid: a sampling seed every system shares."""

    index: int
    sample_seed: int

    def train_seed(self, family: str) -> int:
        return train_seed_for(family, self.index)


#: Each L3 family's own committed final-training seed (``final.seed`` of its sealed
#: search-space file). They differ; see :func:`train_seed_for`.
PRIMARY_TRAIN_SEED_BY_FAMILY: dict[str, int] = {"diffusion": 20260727, "flow": 20260728}

#: CLAUDE.md's platform-wide decade stride, reused as the seed stride so the three
#: seed indices are the same arithmetic every other multi-seed object in this repo
#: uses (``base + 7919*k``).
SEED_STRIDE = 7919

#: The shared SAMPLING seed base. Every system draws its ensemble at
#: ``SAMPLE_SEED_BASE + 7919*k`` at seed index k, so a cross-system difference at
#: one index is never a seed difference.
SAMPLE_SEED_BASE = 20260727

#: Three columns — the sealed ``multi_seed_decision_rule.minimum_seeds`` is a
#: FLOOR, and three is what the compute budget in ``ABLATION.md`` supports.
SEED_PLAN: tuple[SeedIndex, ...] = tuple(
    SeedIndex(index=k, sample_seed=SAMPLE_SEED_BASE + SEED_STRIDE * k) for k in range(3)
)

_B_FAMILY = "flow"
_C_FAMILY = "flow"

SYSTEMS: tuple[AblationSystem, ...] = (
    AblationSystem(
        letter="A",
        system_id=SYSTEM_A_ID,
        composition="L1 + L2 + L4, Gaussian residual blocks (no L3)",
        question="How far does interpretable structure alone go?",
        neural=False,
    ),
    AblationSystem(
        letter="B",
        system_id=neural_rollout_id(_B_FAMILY),
        composition=f"L1 + L2 + L3({_B_FAMILY}) chained, no waypoints, no Denton",
        question="Does rollout drift as predicted?",
        neural=True,
        family=_B_FAMILY,
    ),
    AblationSystem(
        letter="C",
        system_id=neural_only_id(_C_FAMILY),
        composition=f"L2 + L3({_C_FAMILY}) chained, no L1, no waypoints, no Denton",
        question="Is the climate layer necessary?",
        neural=True,
        family=_C_FAMILY,
    ),
    # Campaign-3 (AM-2026-08-10-001): ONE trained sampler, hier-flow-v2 --
    # hier-diffusion does not race (the sealed ablation_systems.D note: the
    # flow family was the promoted line; a diffusion retrain spends the K4
    # budget without a decision it would change). The campaign-2 table carried
    # both v1 arms here; the v1 ids remain buildable as replay surfaces.
    AblationSystem(
        letter="D",
        system_id=SYSTEM_D_V2_ID,
        composition="L1 + L2 + L3(flow) + L4, retrained on the extended panel",
        question="The proposed system",
        neural=True,
        family="flow",
    ),
    AblationSystem(
        letter="E",
        system_id="bootstrap-v1",
        composition="Regime-stratified stationary block bootstrap (the frozen benchmark)",
        question="The transparent benchmark (G2 opponent)",
        neural=False,
    ),
    # Campaign-3 (ruling K3, AM-2026-08-10-001): the har-masked cell.
    AblationSystem(
        letter="F",
        system_id=SYSTEM_F_ID,
        composition=(
            "system D's flow arm, trained with equity_vol MISSING pre-1986-01 "
            "(identical architecture, hyperparameters and seeds)"
        ),
        question="How much does the model learn from our own HAR reconstruction?",
        neural=True,
        family="flow",
    ),
)

#: The compositions this module adds to the registry (D and E were already there).
REGISTERED_ABLATION_IDS: tuple[str, ...] = (SYSTEM_A_ID, *_register_neural_ablations())

registry.register(SYSTEM_A_ID, structure_only_v1_factory)

#: The (letter, family) pairs deliberately NOT run — see the module docstring.
UNTESTED_ARMS: tuple[str, ...] = tuple(
    builder(family)
    for letter, builder in (("B", neural_rollout_id), ("C", neural_only_id))
    for family in ("diffusion", "flow")
    if builder(family) not in {row.system_id for row in SYSTEMS}
)
