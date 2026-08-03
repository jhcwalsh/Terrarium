"""Re-coning (wp5-03): the conditional ensemble from any mid-path state.

"What could still happen from here": given one path of a hierarchical
ensemble observed through month ``m``, regenerate the CONDITIONAL distribution
of continuations. Every layer conditions EXACTLY -- the kickoff's halt
condition ("do not approximate silently") was verified before this module was
built, and nothing here approximates:

- **L1** is Markov in the five-state vector: the continuation runs
  :func:`ah.gen.climate.simulate.simulate_decades_from_state` from the path's
  own month-``m`` state, under the SAME posterior draw the original decade was
  simulated with (recovered exactly -- see below).
- **L2**'s conditioning state is (current regime, elapsed sojourn, the running
  spell's start-month covariates), all derivable from the ensemble's recorded
  labels and slow states; the remaining sojourn is exact truncated-NegBin
  arithmetic (:func:`ah.gen.regimes.semimarkov.simulate_regimes_from_spell`).
- **L3/bridge**: :func:`ah.gen.joinery.bridge.assemble_continuation_path`
  seeds the block assembly with the observed prefix -- h_t summarizes real
  history, chained factors rebase at the prefix's last level, and the prefix
  itself is held fixed (observed data is never blended).

**Theta recovery, exact and lineage-only.** The records carry no per-decade
posterior indices, and they do not need to: both layers draw their index as
the FIRST integer of ``PCG64(base_seed + LAYER_SEED_OFFSETS[layer] +
SEED_STRIDE * decade)``, and the ensemble records ``meta.seed``. The recovery
replays that one draw -- bit-exact, no schema change, and a test pins it
against a freshly assembled ensemble.

**Scope: re-cone points sit on year boundaries** (``at_month % 12 == 0``).
Waypoint construction is year-aligned, and the platform's decision cadence is
annual (``ah.core.institution.decision_months``), so the re-cone grid IS the
decision grid. A scope choice, stated -- not an approximation.

The result is a plain :class:`ah.gen.base.Ensemble` whose meta records the
re-cone lineage (source seed, path index, month) -- inspectable, batteryable,
and consumed by the was-it-a-good-call metric in :mod:`ah.eval.counterfactual`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ah.gen.base import Ensemble, EnsembleMeta, RegimeRecord, SlowStateRecord
from ah.gen.climate.simulate import SimulatedClimate, simulate_decades_from_state
from ah.gen.joinery import bridge
from ah.gen.joinery import reconcile as rc
from ah.gen.joinery import waypoints as wp
from ah.gen.joinery.assemble import LAYER_SEED_OFFSETS, SEED_STRIDE, JoineryConfig
from ah.gen.regimes.semimarkov import (
    RegimePaths,
    simulate_regimes_from_spell,
)

__all__ = ["ReconeError", "recone", "recover_theta_index"]

RECONE_GENERATOR_SUFFIX = "+recone"


class ReconeError(RuntimeError):
    """A re-cone request the recorded lineage cannot support exactly."""


def recover_theta_index(base_seed: int, layer: str, decade: int, n_draws: int) -> int:
    """Replay the one posterior-index draw a layer made for ``decade``.

    Exactly the stream ``ah.gen.joinery.assemble._DecadeFactory._simulate_layers``
    opened: ``PCG64(base_seed + LAYER_SEED_OFFSETS[layer] + SEED_STRIDE*decade)``,
    whose FIRST ``integers(n_draws)`` call is the index. Bit-exact lineage
    recovery, pinned by test against a fresh assembly.
    """
    rng = np.random.Generator(
        np.random.PCG64(int(base_seed) + LAYER_SEED_OFFSETS[layer] + SEED_STRIDE * int(decade))
    )
    return int(rng.integers(int(n_draws)))


def _spell_state(labels: np.ndarray, at_month: int) -> tuple[int, int, int]:
    """(current_regime, elapsed_months, spell_start_month) at ``at_month``.

    ``elapsed`` counts the months of the running spell that are already
    observed, i.e. the run length of the current label through ``at_month - 1``.
    """
    current = int(labels[at_month - 1])
    start = at_month - 1
    while start > 0 and int(labels[start - 1]) == current:
        start -= 1
    return current, at_month - start, start


def recone(
    system: Any,
    ensemble: Ensemble,
    *,
    path_index: int,
    at_month: int,
    n_paths: int,
    seed: int,
    months: int | None = None,
) -> Ensemble:
    """The conditional continuation ensemble from ``ensemble``'s path at a month.

    ``system`` is the hierarchical system that produced ``ensemble`` (a
    :class:`~ah.gen.blocks.diffusion.HierBlockSystem`); its climate, regimes
    artifact, source and sampler are read directly -- a re-cone under a
    different system than the one that generated the path would answer a
    different question, so no substitution is offered. ``months`` defaults to
    the remaining horizon (``ensemble.months - at_month``).

    Raises :class:`ReconeError` when the recorded lineage cannot support exact
    conditioning (missing regime/slow-state records, an off-grid month) --
    refusal, never approximation.
    """
    if at_month % 12 != 0:
        raise ReconeError(
            f"re-cone points sit on year boundaries (the decision grid); got month {at_month}"
        )
    if not (12 <= at_month < ensemble.months):
        raise ReconeError(
            f"at_month must lie in [12, {ensemble.months}) with a full observed year; "
            f"got {at_month}"
        )
    if not isinstance(ensemble.regimes, RegimeRecord) or not isinstance(
        ensemble.slow_states, SlowStateRecord
    ):
        raise ReconeError(
            "exact re-coning needs the ensemble's regime and slow-state records; "
            "this ensemble carries "
            f"regimes={type(ensemble.regimes).__name__}, "
            f"slow_states={type(ensemble.slow_states).__name__}"
        )
    if not (0 <= path_index < ensemble.n_paths):
        raise ReconeError(f"path_index {path_index} outside [0, {ensemble.n_paths})")
    cond = ensemble.meta.conditioning
    if cond.get("factor_conditions_honoured"):
        raise ReconeError(
            "this ensemble was WORLD-CONDITIONED: its recorded labels carry crisis "
            "overlays and its waypoints carry authored conditions, so a spell state "
            "read off the labels is not the chain's state. Re-coning conditioned "
            "worlds needs an overlay-aware variant -- refused, not approximated."
        )
    if cond.get("regime_mode") not in (None, "semimarkov"):
        raise ReconeError(
            f"re-coning conditions the semi-Markov chain; this ensemble's regime mode "
            f"is {cond.get('regime_mode')!r}"
        )
    n_rejected = int((cond.get("acceptance_filter") or {}).get("n_rejected", 0))
    if n_rejected:
        raise ReconeError(
            f"the acceptance filter replaced {n_rejected} decade(s) in this ensemble, "
            "so the seed->decade mapping the exact theta recovery replays does not "
            "hold for every path. Re-cone from an unfiltered ensemble (the systems' "
            "sample_months(..., unfiltered=True)) -- refused, not approximated."
        )
    horizon = int(ensemble.months - at_month) if months is None else int(months)
    if horizon < 12 or horizon % 12 != 0:
        raise ReconeError(f"continuation horizon must be a positive multiple of 12; got {horizon}")

    climate = system._climate
    regimes_artifact = system._regimes
    source = system._source
    sampler = system._sampler
    config: JoineryConfig = system._config
    stats = wp.source_stats(source, climate)

    prefix_paths = np.asarray(ensemble.paths[path_index, :at_month], dtype=np.float64)
    prefix_states = np.asarray(ensemble.slow_states.states[path_index, :at_month], dtype=np.float64)
    prefix_labels = np.asarray(ensemble.regimes.labels[path_index, :at_month], dtype=np.int64)
    s_m = np.asarray(ensemble.slow_states.states[path_index, at_month], dtype=np.float64)

    base_seed = int(ensemble.meta.seed)
    l1_theta = recover_theta_index(base_seed, "climate", path_index, climate.n_draws)
    l2_theta = recover_theta_index(base_seed, "regimes", path_index, regimes_artifact.n_draws)

    # L1: conditional continuations from the observed state, one stream each.
    sim = simulate_decades_from_state(
        climate,
        n_paths,
        seed=seed + LAYER_SEED_OFFSETS["climate"],
        s0=s_m,
        theta_index=l1_theta,
        months=horizon,
    )

    # L2: continue the RUNNING spell exactly, then the ordinary chain.
    current_regime, elapsed, spell_start = _spell_state(prefix_labels, at_month)
    regime_paths = simulate_regimes_from_spell(
        regimes_artifact,
        sim.states,
        seed=seed + LAYER_SEED_OFFSETS["regimes"],
        theta_index=l2_theta,
        current_regime=current_regime,
        elapsed=elapsed,
        spell_start_state=prefix_states[spell_start],
    )

    factor_names = list(sampler.factor_names)
    n_factors = len(factor_names)
    out = np.empty((n_paths, horizon, n_factors), dtype=np.float64)

    for k in range(n_paths):
        # Padded frame (prefix + continuation): waypoints/targets for assembly
        # conditioning read observed history for prefix years, this
        # continuation's own states for the rest. Exact, per continuation path.
        padded_states = np.concatenate([prefix_states, sim.states[k]])[None, ...]
        padded_labels = np.concatenate([prefix_labels, regime_paths.labels[k]])[None, ...]
        padded_sim = SimulatedClimate(
            states=padded_states,
            theta_index=np.array([l1_theta]),
            params={n: np.asarray(v)[[0]] for n, v in sim.params.items()},
            s0_date=sim.s0_date,
            seed=sim.seed,
        )
        padded_regimes = RegimePaths(
            labels=padded_labels,
            cycle=regimes_artifact.cycle_by_regime[padded_labels],
            theta_index=np.array([l2_theta]),
            seed=regime_paths.seed,
            mode=regime_paths.mode,
            ruleset_version=regime_paths.ruleset_version,
        )
        padded_wp = wp.build_waypoints(padded_sim, padded_regimes, stats)[0]
        padded_targets = (
            wp.monthly_targets(padded_wp, at_month + horizon) if config.bind_waypoints else None
        )
        rng = np.random.Generator(
            np.random.PCG64(seed + LAYER_SEED_OFFSETS["blocks"] + SEED_STRIDE * k)
        )
        raw, _conds = bridge.assemble_continuation_path(
            prefix=prefix_paths,
            months=horizon,
            waypoints=padded_wp,
            targets=padded_targets,
            states_row=np.concatenate([prefix_states, sim.states[k]]),
            sampler=sampler,
            stats=stats,
            rng=rng,
            stride=config.block_stride,
        )

        if config.bind_waypoints:
            # Reconciliation runs on the continuation as its own frame, against
            # waypoints built from the continuation's states/labels alone (the
            # same deterministic construction, framed at the re-cone point).
            cont_sim = SimulatedClimate(
                states=sim.states[k][None, ...],
                theta_index=np.array([l1_theta]),
                params={n: np.asarray(v)[[0]] for n, v in sim.params.items()},
                s0_date=sim.s0_date,
                seed=sim.seed,
            )
            cont_regimes = RegimePaths(
                labels=regime_paths.labels[k][None, ...],
                cycle=regimes_artifact.cycle_by_regime[regime_paths.labels[k][None, ...]],
                theta_index=np.array([l2_theta]),
                seed=regime_paths.seed,
                mode=regime_paths.mode,
                ruleset_version=regime_paths.ruleset_version,
            )
            cont_wp = wp.build_waypoints(cont_sim, cont_regimes, stats)[0]
            reconciled, _diag = rc.reconcile_decade(
                raw, tuple(factor_names), cont_wp, config.reconcile
            )
            out[k] = reconciled
        else:
            out[k] = raw

    meta = EnsembleMeta(
        generator_id=str(getattr(system, "generator_id", "hier-block-system"))
        + RECONE_GENERATOR_SUFFIX,
        vintage_id=ensemble.meta.vintage_id,
        seed=seed,
        n_paths=n_paths,
        months=horizon,
        active_blocks=ensemble.meta.active_blocks,
        conditioning={
            "recone": {
                "source_seed": base_seed,
                "source_generator_id": ensemble.meta.generator_id,
                "path_index": int(path_index),
                "at_month": int(at_month),
                "l1_theta_index": l1_theta,
                "l2_theta_index": l2_theta,
                "current_regime": current_regime,
                "elapsed_in_spell": elapsed,
                "acceptance_filter": "none (counterfactual/diagnostic ensemble)",
            }
        },
    )
    regimes_record = RegimeRecord(
        labels=regime_paths.labels,
        legend=ensemble.regimes.legend,
        mode=regime_paths.mode,
        ruleset_version=regime_paths.ruleset_version,
    )
    slow_record = SlowStateRecord(
        states=sim.states, names=ensemble.slow_states.names, layer="simulated"
    )
    return Ensemble(
        paths=out,
        factor_names=factor_names,
        meta=meta,
        regimes=regimes_record,
        slow_states=slow_record,
    )
